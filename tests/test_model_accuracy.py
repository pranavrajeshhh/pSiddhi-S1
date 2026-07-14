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


def load_models(pipeline):
    with open(os.path.join(MODELS_DIR, f'{pipeline}_scaler.pkl'), 'rb') as f: scaler = pickle.load(f)
    with open(os.path.join(MODELS_DIR, f'{pipeline}_iso.pkl'), 'rb') as f: iso = pickle.load(f)
    with open(os.path.join(MODELS_DIR, f'{pipeline}_lof.pkl'), 'rb') as f: lof = pickle.load(f)
    return scaler, iso, lof


class TestModelAccuracy:
    def test_isolation_forest_scores_in_valid_range(self):
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql_query(
            "SELECT * FROM job_runs WHERE pipeline_name='batch_ingestion_01' AND is_anomaly=0 LIMIT 50", conn
        )
        conn.close()
        scaler, iso, _ = load_models('batch_ingestion_01')
        scores = iso.decision_function(scaler.transform(df[FEATURES].fillna(0)))
        assert all(-1.0 <= s <= 1.0 for s in scores)

    def test_lof_produces_binary_predictions(self):
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql_query(
            "SELECT * FROM job_runs WHERE pipeline_name='batch_ingestion_01' AND is_anomaly=0 LIMIT 50", conn
        )
        conn.close()
        scaler, _, lof = load_models('batch_ingestion_01')
        preds = set(lof.predict(scaler.transform(df[FEATURES].fillna(0))))
        assert preds.issubset({0, 1}), f"LOF should predict 0 or 1, got: {preds}"

    def test_models_trained_on_sufficient_samples(self):
        conn = sqlite3.connect(DB_PATH)
        for pipeline in ['batch_ingestion_01', 'transformation_pipeline_01']:
            count = conn.execute(
                "SELECT COUNT(*) FROM job_runs WHERE pipeline_name=? AND is_anomaly=0", (pipeline,)
            ).fetchone()[0]
            assert count >= 50, f"Only {count} training samples for {pipeline}"
        conn.close()

    def test_false_positive_rate_within_threshold(self):
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql_query(
            "SELECT * FROM job_runs WHERE pipeline_name='batch_ingestion_01' AND is_anomaly=0", conn
        )
        conn.close()
        scaler, iso, lof = load_models('batch_ingestion_01')
        X = scaler.transform(df[FEATURES].fillna(0))
        combined = [(iso.predict(X)[i] == -1) or (lof.predict(X)[i] == 1) for i in range(len(X))]
        fp_rate = sum(combined) / len(combined)
        assert fp_rate <= 0.15, f"False positive rate {fp_rate:.1%} exceeds 15% threshold"

    def test_known_anomaly_is_detected(self):
        scaler, iso, lof = load_models('batch_ingestion_01')
        anomaly = pd.DataFrame([{
            'duration_seconds': 185.0, 'rows_ingested': 11000,
            'rows_output': 890, 'data_volume_mb': 52.0, 'processing_time_seconds': 178.0
        }])
        X = scaler.transform(anomaly[FEATURES].fillna(0))
        flagged = (iso.predict(X)[0] == -1) or (lof.predict(X)[0] == 1)
        assert flagged, "Known high-severity anomaly (duration=185s) was NOT detected"
