import pytest
import sqlite3
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'etl_metrics.db')
MODELS_DIR = os.path.join(os.path.dirname(__file__), '..', 'models')


class TestDatabase:
    def test_db_exists(self):
        assert os.path.exists(DB_PATH), "SQLite DB not found — run DAGs first"

    def test_job_runs_table_exists(self):
        conn = sqlite3.connect(DB_PATH)
        tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        conn.close()
        table_names = [t[0] for t in tables]
        assert 'job_runs' in table_names

    def test_job_runs_has_data(self):
        conn = sqlite3.connect(DB_PATH)
        count = conn.execute("SELECT COUNT(*) FROM job_runs").fetchone()[0]
        conn.close()
        assert count > 0, "No job run data found"

    def test_both_pipelines_present(self):
        conn = sqlite3.connect(DB_PATH)
        pipelines = conn.execute(
            "SELECT DISTINCT pipeline_name FROM job_runs"
        ).fetchall()
        conn.close()
        pipeline_names = [p[0] for p in pipelines]
        assert 'batch_ingestion_01' in pipeline_names
        assert 'transformation_pipeline_01' in pipeline_names

    def test_all_stages_present(self):
        conn = sqlite3.connect(DB_PATH)
        stages = conn.execute("SELECT DISTINCT stage FROM job_runs").fetchall()
        conn.close()
        stage_names = [s[0] for s in stages]
        expected = ['ingestion', 'transformation', 'load', 'extract', 'clean', 'aggregate']
        for stage in expected:
            assert stage in stage_names, f"Stage '{stage}' not found in job_runs"

    def test_no_null_durations(self):
        conn = sqlite3.connect(DB_PATH)
        nulls = conn.execute(
            "SELECT COUNT(*) FROM job_runs WHERE duration_seconds IS NULL"
        ).fetchone()[0]
        conn.close()
        assert nulls == 0

    def test_all_runs_successful(self):
        conn = sqlite3.connect(DB_PATH)
        failed = conn.execute(
            "SELECT COUNT(*) FROM job_runs WHERE status != 'success'"
        ).fetchone()[0]
        conn.close()
        assert failed == 0, f"{failed} failed job runs found"

    def test_metric_values_in_range(self):
        conn = sqlite3.connect(DB_PATH)
        rows = conn.execute(
            "SELECT duration_seconds, rows_ingested, data_volume_mb FROM job_runs"
        ).fetchall()
        conn.close()
        for row in rows:
            assert row[0] > 0, "Duration must be positive"
            assert row[1] >= 0, "Rows ingested must be non-negative"
            assert row[2] >= 0, "Data volume must be non-negative"


class TestMLModels:
    def test_models_directory_exists(self):
        assert os.path.exists(MODELS_DIR)

    def test_isolation_forest_model_saved(self):
        for pipeline in ['batch_ingestion_01', 'transformation_pipeline_01']:
            path = os.path.join(MODELS_DIR, f'{pipeline}_iso.pkl')
            assert os.path.exists(path), f"Isolation Forest model not found for {pipeline}"

    def test_lof_model_saved(self):
        for pipeline in ['batch_ingestion_01', 'transformation_pipeline_01']:
            path = os.path.join(MODELS_DIR, f'{pipeline}_lof.pkl')
            assert os.path.exists(path), f"LOF model not found for {pipeline}"

    def test_scaler_saved(self):
        for pipeline in ['batch_ingestion_01', 'transformation_pipeline_01']:
            path = os.path.join(MODELS_DIR, f'{pipeline}_scaler.pkl')
            assert os.path.exists(path), f"Scaler not found for {pipeline}"

    def test_models_loadable(self):
        import pickle
        for pipeline in ['batch_ingestion_01', 'transformation_pipeline_01']:
            for suffix in ['iso', 'lof', 'scaler']:
                path = os.path.join(MODELS_DIR, f'{pipeline}_{suffix}.pkl')
                if os.path.exists(path):
                    with open(path, 'rb') as f:
                        obj = pickle.load(f)
                    assert obj is not None


class TestMetricExporter:
    def test_exporter_file_exists(self):
        exporter_path = os.path.join(
            os.path.dirname(__file__), '..', 'exporter', 'metrics_exporter.py'
        )
        assert os.path.exists(exporter_path)

    def test_exporter_imports(self):
        try:
            from prometheus_client import Gauge, Counter
        except ImportError:
            pytest.skip("prometheus_client not installed")


class TestDAGFiles:
    def test_batch_ingestion_dag_exists(self):
        dag_path = os.path.join(
            os.path.dirname(__file__), '..', 'dags', 'batch_ingestion_dag.py'
        )
        assert os.path.exists(dag_path)

    def test_transformation_dag_exists(self):
        dag_path = os.path.join(
            os.path.dirname(__file__), '..', 'dags', 'transformation_dag.py'
        )
        assert os.path.exists(dag_path)

    def test_dag_files_not_empty(self):
        for fname in ['batch_ingestion_dag.py', 'transformation_dag.py']:
            path = os.path.join(os.path.dirname(__file__), '..', 'dags', fname)
            assert os.path.getsize(path) > 0
