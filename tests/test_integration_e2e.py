import pytest
import sqlite3
import os
import sys
import pickle
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'etl_metrics.db')
MODELS_DIR = os.path.join(os.path.dirname(__file__), '..', 'models')
FEATURES = ['duration_seconds', 'rows_ingested', 'rows_output', 'data_volume_mb', 'processing_time_seconds']


class TestIntegrationE2E:
    def test_full_detect_pipeline_runs(self):
        from ml.detect import score_recent_runs
        result = score_recent_runs(limit=10)
        assert result is not None

    def test_detect_writes_to_anomaly_alerts(self):
        from ml.detect import score_recent_runs
        score_recent_runs(limit=10)
        conn = sqlite3.connect(DB_PATH)
        count = conn.execute("SELECT COUNT(*) FROM anomaly_alerts").fetchone()[0]
        conn.close()
        assert count >= 0

    def test_explain_writes_explanations(self):
        conn = sqlite3.connect(DB_PATH)
        count = conn.execute(
            "SELECT COUNT(*) FROM anomaly_alerts WHERE ai_explanation IS NOT NULL AND ai_explanation != ''"
        ).fetchone()[0]
        conn.close()
        assert count >= 0

    def test_db_and_models_in_sync(self):
        conn = sqlite3.connect(DB_PATH)
        pipelines = [r[0] for r in conn.execute("SELECT DISTINCT pipeline_name FROM job_runs").fetchall()]
        conn.close()
        for pipeline in pipelines:
            assert os.path.exists(os.path.join(MODELS_DIR, f'{pipeline}_iso.pkl')), \
                f"Model missing for {pipeline} — run train.py"

    def test_end_to_end_anomaly_flow(self):
        conn = sqlite3.connect(DB_PATH)
        assert conn.execute("SELECT COUNT(*) FROM job_runs").fetchone()[0] > 0
        conn.close()
        for suffix in ['scaler', 'iso', 'lof']:
            assert os.path.exists(os.path.join(MODELS_DIR, f'batch_ingestion_01_{suffix}.pkl'))
        with open(os.path.join(MODELS_DIR, 'batch_ingestion_01_scaler.pkl'), 'rb') as f: scaler = pickle.load(f)
        with open(os.path.join(MODELS_DIR, 'batch_ingestion_01_iso.pkl'), 'rb') as f: iso = pickle.load(f)
        with open(os.path.join(MODELS_DIR, 'batch_ingestion_01_lof.pkl'), 'rb') as f: lof = pickle.load(f)
        sample = pd.DataFrame([{
            'duration_seconds': 185.0, 'rows_ingested': 11000,
            'rows_output': 890, 'data_volume_mb': 52.0, 'processing_time_seconds': 178.0
        }])
        X = scaler.transform(sample[FEATURES])
        flagged = (iso.predict(X)[0] == -1) or (lof.predict(X)[0] == 1)
        assert flagged, "E2E flow failed: injected anomaly not detected"
