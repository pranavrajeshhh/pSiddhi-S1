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


class TestFalsePositiveRate:
    def test_pipeline1_fp_rate_under_10_percent(self):
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql_query(
            "SELECT * FROM job_runs WHERE pipeline_name='batch_ingestion_01' AND is_anomaly=0", conn
        )
        conn.close()
        with open(os.path.join(MODELS_DIR, 'batch_ingestion_01_scaler.pkl'), 'rb') as f: scaler = pickle.load(f)
        with open(os.path.join(MODELS_DIR, 'batch_ingestion_01_iso.pkl'), 'rb') as f: iso = pickle.load(f)
        preds = iso.predict(scaler.transform(df[FEATURES].fillna(0)))
        fp_rate = (preds == -1).sum() / len(preds)
        assert fp_rate <= 0.10, f"Pipeline 1 FP rate: {fp_rate:.1%} (threshold: 10%)"

    def test_pipeline2_fp_rate_under_10_percent(self):
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql_query(
            "SELECT * FROM job_runs WHERE pipeline_name='transformation_pipeline_01' AND is_anomaly=0", conn
        )
        conn.close()
        with open(os.path.join(MODELS_DIR, 'transformation_pipeline_01_scaler.pkl'), 'rb') as f: scaler = pickle.load(f)
        with open(os.path.join(MODELS_DIR, 'transformation_pipeline_01_iso.pkl'), 'rb') as f: iso = pickle.load(f)
        preds = iso.predict(scaler.transform(df[FEATURES].fillna(0)))
        fp_rate = (preds == -1).sum() / len(preds)
        assert fp_rate <= 0.10, f"Pipeline 2 FP rate: {fp_rate:.1%} (threshold: 10%)"

    def test_normal_run_not_flagged(self):
        with open(os.path.join(MODELS_DIR, 'batch_ingestion_01_scaler.pkl'), 'rb') as f: scaler = pickle.load(f)
        with open(os.path.join(MODELS_DIR, 'batch_ingestion_01_iso.pkl'), 'rb') as f: iso = pickle.load(f)
        normal = pd.DataFrame([{
            'duration_seconds': 14.5, 'rows_ingested': 10000,
            'rows_output': 9500, 'data_volume_mb': 45.0, 'processing_time_seconds': 13.0
        }])
        pred = iso.predict(scaler.transform(normal[FEATURES].fillna(0)))[0]
        assert pred == 1, "A clearly normal run was incorrectly flagged as anomaly"
