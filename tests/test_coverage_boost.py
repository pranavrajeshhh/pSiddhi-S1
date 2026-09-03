"""
Coverage boost tests — mocked unit tests targeting all previously uncovered lines
in score_all.py, export_powerbi.py, train.py, explain.py, benchmark.py, alert.py
"""
import pytest
import os
import sys
import json
import sqlite3
import tempfile
from unittest.mock import patch, MagicMock, call
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


# ── score_all.py ─────────────────────────────────────────────────────────────
from ml.score_all import (
    get_pipeline_key, severity, ensure_columns,
    fetch_all_runs, score_records, write_results, run_scoring,
    FEATURES, PIPELINE_KEY_MAP,
)

class TestScoreAllFunctions:
    def test_get_pipeline_key_known(self):
        assert get_pipeline_key('batch_ingestion_01') == 'batch_ingestion_01'

    def test_get_pipeline_key_unknown(self):
        assert get_pipeline_key('unknown_pipeline') is None

    def test_get_pipeline_key_transformation(self):
        assert get_pipeline_key('transformation_pipeline_01') == 'transformation_pipeline_01'

    def test_severity_high(self):
        assert severity(-0.4) == 'high'

    def test_severity_medium(self):
        assert severity(-0.2) == 'medium'

    def test_severity_low(self):
        assert severity(0.05) == 'low'

    def test_severity_boundary_high(self):
        assert severity(-0.31) == 'high'

    def test_severity_boundary_medium(self):
        assert severity(-0.11) == 'medium'

    def test_ensure_columns_runs_without_error(self, tmp_path):
        db = sqlite3.connect(str(tmp_path / 'test.db'))
        db.execute('CREATE TABLE anomaly_alerts (id INTEGER PRIMARY KEY)')
        db.commit()
        ensure_columns(db)
        db.close()

    def test_fetch_all_runs_empty(self, tmp_path):
        db = sqlite3.connect(str(tmp_path / 'test.db'))
        db.row_factory = sqlite3.Row
        db.execute('''CREATE TABLE job_runs (
            id INTEGER PRIMARY KEY, pipeline_name TEXT, stage TEXT,
            duration_seconds REAL, rows_ingested INTEGER, rows_output INTEGER,
            data_volume_mb REAL, processing_time_seconds REAL,
            status TEXT, is_anomaly INTEGER, start_time TEXT)''')
        db.commit()
        rows = fetch_all_runs(db)
        assert rows == []
        db.close()

    def test_score_records_no_model(self):
        rows = [{'id': 1, 'pipeline_name': 'unknown_pipe', 'stage': 'x',
                 'duration_seconds': 10, 'rows_ingested': 100, 'rows_output': 90,
                 'data_volume_mb': 5.0, 'processing_time_seconds': 8.0,
                 'status': 'success', 'is_anomaly': 0, 'start_time': '2026-01-01'}]
        results = score_records(rows, cache={})
        assert results[0]['ml_is_anomaly'] is None

    def test_score_records_with_mock_model(self):
        mock_iso = MagicMock()
        mock_lof = MagicMock()
        mock_scaler = MagicMock()
        mock_scaler.transform.return_value = np.array([[0.0] * 5])
        mock_iso.score_samples.return_value = np.array([-0.4])
        mock_iso.predict.return_value = np.array([-1])
        mock_lof.predict.return_value = np.array([1])

        rows = [{'id': 1, 'pipeline_name': 'batch_ingestion_01', 'stage': 'ingestion',
                 'duration_seconds': 100, 'rows_ingested': 1000, 'rows_output': 900,
                 'data_volume_mb': 50.0, 'processing_time_seconds': 80.0,
                 'status': 'success', 'is_anomaly': 0, 'start_time': '2026-01-01'}]

        cache = {'batch_ingestion_01': (mock_iso, mock_lof, mock_scaler)}
        results = score_records(rows, cache=cache)
        assert results[0]['ml_is_anomaly'] is True
        assert results[0]['ml_severity'] == 'high'
        assert 'Isolation Forest' in results[0]['models_flagged']

    def test_score_records_model_none_in_cache(self):
        rows = [{'id': 1, 'pipeline_name': 'batch_ingestion_01', 'stage': 'ingestion',
                 'duration_seconds': 10, 'rows_ingested': 100, 'rows_output': 90,
                 'data_volume_mb': 5.0, 'processing_time_seconds': 8.0,
                 'status': 'success', 'is_anomaly': 0, 'start_time': '2026-01-01'}]
        cache = {'batch_ingestion_01': (None, None, None)}
        results = score_records(rows, cache=cache)
        assert results[0]['ml_is_anomaly'] is None

    def test_write_results_updates_db(self, tmp_path):
        db = sqlite3.connect(str(tmp_path / 'test.db'))
        db.execute('''CREATE TABLE job_runs (id INTEGER PRIMARY KEY,
            pipeline_name TEXT, stage TEXT, is_anomaly INTEGER,
            duration_seconds REAL, rows_ingested INTEGER, rows_output INTEGER,
            data_volume_mb REAL, processing_time_seconds REAL, status TEXT, start_time TEXT)''')
        db.execute('''CREATE TABLE anomaly_alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT, pipeline_name TEXT, stage TEXT,
            anomaly_type TEXT, severity TEXT, iso_score REAL,
            detected_at TEXT, job_run_id INTEGER, models_flagged TEXT)''')
        db.execute("INSERT INTO job_runs VALUES (1,'batch_ingestion_01','ingest',0,14.5,10000,9500,45.0,13.0,'success','2026-01-01')")
        db.commit()
        results = [{'id': 1, 'pipeline_name': 'batch_ingestion_01', 'stage': 'ingest',
                    'ml_is_anomaly': True, 'ml_severity': 'high',
                    'iso_score': -0.4, 'models_flagged': ['Isolation Forest']}]
        write_results(db, results)
        row = db.execute('SELECT is_anomaly FROM job_runs WHERE id=1').fetchone()
        assert row[0] == 1
        db.close()

    def test_lof_only_flagged(self):
        mock_iso = MagicMock()
        mock_lof = MagicMock()
        mock_scaler = MagicMock()
        mock_scaler.transform.return_value = np.array([[0.0] * 5])
        mock_iso.score_samples.return_value = np.array([0.05])
        mock_iso.predict.return_value = np.array([1])   # IF says normal
        mock_lof.predict.return_value = np.array([1])   # LOF says anomaly

        rows = [{'id': 1, 'pipeline_name': 'batch_ingestion_01', 'stage': 'ingestion',
                 'duration_seconds': 10, 'rows_ingested': 100, 'rows_output': 90,
                 'data_volume_mb': 5.0, 'processing_time_seconds': 8.0,
                 'status': 'success', 'is_anomaly': 0, 'start_time': '2026-01-01'}]
        cache = {'batch_ingestion_01': (mock_iso, mock_lof, mock_scaler)}
        results = score_records(rows, cache=cache)
        assert results[0]['ml_is_anomaly'] is True
        assert 'LOF' in results[0]['models_flagged']


# ── export_powerbi.py ─────────────────────────────────────────────────────────
from ml.export_powerbi import (
    export_anomaly_summary, export_pipeline_health,
    export_severity_trends, export_weekly_report, run_export,
)

class TestExportPowerBI:
    def _make_db(self, tmp_path):
        db_path = str(tmp_path / 'test.db')
        conn = sqlite3.connect(db_path)
        conn.execute('''CREATE TABLE job_runs (
            id INTEGER PRIMARY KEY, pipeline_name TEXT, stage TEXT,
            duration_seconds REAL, rows_ingested INTEGER, rows_output INTEGER,
            data_volume_mb REAL, processing_time_seconds REAL,
            status TEXT, is_anomaly INTEGER, start_time TEXT)''')
        conn.execute('''CREATE TABLE anomaly_alerts (
            id INTEGER PRIMARY KEY, pipeline_name TEXT, stage TEXT,
            anomaly_type TEXT, severity TEXT, iso_score REAL,
            detected_at TEXT, ai_explanation TEXT, job_run_id INTEGER)''')
        conn.execute("INSERT INTO job_runs VALUES (1,'batch_ingestion_01','ingest',14.5,10000,9500,45.0,13.0,'success',0,'2026-01-01 10:00:00')")
        conn.execute("INSERT INTO job_runs VALUES (2,'batch_ingestion_01','ingest',14.5,10000,9500,45.0,13.0,'success',1,'2026-01-01 10:30:00')")
        conn.execute("INSERT INTO anomaly_alerts VALUES (1,'batch_ingestion_01','ingest','ml_detected','high',-0.4,'2026-01-01 10:30:00','AI explanation here',2)")
        conn.commit()
        conn.close()
        return db_path

    def test_export_anomaly_summary(self, tmp_path):
        db_path = self._make_db(tmp_path)
        export_dir = str(tmp_path / 'exports')
        os.makedirs(export_dir)
        with patch('ml.export_powerbi.DB_PATH', db_path), \
             patch('ml.export_powerbi.EXPORT_DIR', export_dir):
            df = export_anomaly_summary()
        assert len(df) == 1
        assert os.path.exists(os.path.join(export_dir, 'anomaly_summary.csv'))

    def test_export_pipeline_health(self, tmp_path):
        db_path = self._make_db(tmp_path)
        export_dir = str(tmp_path / 'exports')
        os.makedirs(export_dir)
        with patch('ml.export_powerbi.DB_PATH', db_path), \
             patch('ml.export_powerbi.EXPORT_DIR', export_dir):
            df = export_pipeline_health()
        assert 'health_score' in df.columns
        assert os.path.exists(os.path.join(export_dir, 'pipeline_health.csv'))

    def test_export_severity_trends(self, tmp_path):
        db_path = self._make_db(tmp_path)
        export_dir = str(tmp_path / 'exports')
        os.makedirs(export_dir)
        with patch('ml.export_powerbi.DB_PATH', db_path), \
             patch('ml.export_powerbi.EXPORT_DIR', export_dir):
            df = export_severity_trends()
        assert 'severity' in df.columns
        assert os.path.exists(os.path.join(export_dir, 'severity_trends.csv'))

    def test_export_weekly_report(self, tmp_path):
        db_path = self._make_db(tmp_path)
        export_dir = str(tmp_path / 'exports')
        os.makedirs(export_dir)
        with patch('ml.export_powerbi.DB_PATH', db_path), \
             patch('ml.export_powerbi.EXPORT_DIR', export_dir):
            df = export_weekly_report()
        assert 'anomaly_rate_pct' in df.columns
        assert os.path.exists(os.path.join(export_dir, 'weekly_report.csv'))

    def test_run_export_creates_all_files(self, tmp_path):
        db_path = self._make_db(tmp_path)
        export_dir = str(tmp_path / 'exports')
        with patch('ml.export_powerbi.DB_PATH', db_path), \
             patch('ml.export_powerbi.EXPORT_DIR', export_dir):
            run_export()
        for f in ['anomaly_summary.csv', 'pipeline_health.csv', 'severity_trends.csv', 'weekly_report.csv']:
            assert os.path.exists(os.path.join(export_dir, f))


# ── train.py ──────────────────────────────────────────────────────────────────
from ml.train import load_data, inject_anomalies, train_pipeline, FEATURES as TRAIN_FEATURES

class TestTrainFunctions:
    def test_load_data_returns_dataframe(self, tmp_path):
        db_path = str(tmp_path / 'test.db')
        conn = sqlite3.connect(db_path)
        conn.execute('''CREATE TABLE job_runs (
            id INTEGER PRIMARY KEY, pipeline_name TEXT, is_anomaly INTEGER, status TEXT,
            duration_seconds REAL, rows_ingested INTEGER, rows_output INTEGER,
            data_volume_mb REAL, processing_time_seconds REAL)''')
        conn.execute("INSERT INTO job_runs VALUES (1,'batch_ingestion_01',0,'success',14.5,10000,9500,45.0,13.0)")
        conn.commit()
        conn.close()
        with patch('ml.train.DB_PATH', db_path):
            df = load_data('batch_ingestion_01')
        assert len(df) == 1
        assert 'duration_seconds' in df.columns

    def test_load_data_filters_anomalies(self, tmp_path):
        db_path = str(tmp_path / 'test.db')
        conn = sqlite3.connect(db_path)
        conn.execute('''CREATE TABLE job_runs (
            id INTEGER PRIMARY KEY, pipeline_name TEXT, is_anomaly INTEGER, status TEXT,
            duration_seconds REAL, rows_ingested INTEGER, rows_output INTEGER,
            data_volume_mb REAL, processing_time_seconds REAL)''')
        conn.execute("INSERT INTO job_runs VALUES (1,'batch_ingestion_01',0,'success',14.5,10000,9500,45.0,13.0)")
        conn.execute("INSERT INTO job_runs VALUES (2,'batch_ingestion_01',1,'success',80.0,10000,100,45.0,13.0)")
        conn.commit()
        conn.close()
        with patch('ml.train.DB_PATH', db_path):
            df = load_data('batch_ingestion_01')
        assert len(df) == 1  # anomaly excluded

    def test_train_pipeline_skips_when_not_enough_data(self, tmp_path):
        db_path = str(tmp_path / 'test.db')
        conn = sqlite3.connect(db_path)
        conn.execute('''CREATE TABLE job_runs (
            id INTEGER PRIMARY KEY, pipeline_name TEXT, is_anomaly INTEGER, status TEXT,
            duration_seconds REAL, rows_ingested INTEGER, rows_output INTEGER,
            data_volume_mb REAL, processing_time_seconds REAL)''')
        conn.commit()
        conn.close()
        with patch('ml.train.DB_PATH', db_path), \
             patch('ml.train.MLFLOW_DB', str(tmp_path / 'mlflow.db')), \
             patch('ml.train.MODELS_DIR', str(tmp_path / 'models')):
            result = train_pipeline('batch_ingestion_01')
        assert result is None


# ── explain.py ────────────────────────────────────────────────────────────────
from ml.explain import explain_with_groq, explain_with_gemini, generate_explanations

class TestExplainFunctions:
    def test_explain_with_groq_success(self):
        mock_response = MagicMock()
        mock_response.choices[0].message.content = '  Groq explanation.  '
        mock_client_instance = MagicMock()
        mock_client_instance.chat.completions.create.return_value = mock_response
        mock_groq_class = MagicMock(return_value=mock_client_instance)
        with patch('ml.explain.GROQ_API_KEY', 'fake_key'), \
             patch.dict('sys.modules', {'groq': MagicMock(Groq=mock_groq_class)}):
            result = explain_with_groq('test prompt')
        assert result == 'Groq explanation.'

    def test_explain_with_groq_returns_none_on_error(self):
        mock_client_instance = MagicMock()
        mock_client_instance.chat.completions.create.side_effect = Exception('API error')
        mock_groq_class = MagicMock(return_value=mock_client_instance)
        with patch('ml.explain.GROQ_API_KEY', 'bad_key'), \
             patch.dict('sys.modules', {'groq': MagicMock(Groq=mock_groq_class)}):
            result = explain_with_groq('test prompt')
        assert result is None

    def test_explain_with_gemini_returns_none_on_error(self):
        mock_genai = MagicMock()
        mock_genai.Client.side_effect = Exception('Auth error')
        with patch('ml.explain.GEMINI_API_KEY', 'bad_key'), \
             patch.dict('sys.modules', {'google': MagicMock(genai=mock_genai), 'google.genai': mock_genai}):
            result = explain_with_gemini('test prompt')
        assert result is None

    def test_explain_with_gemini_success(self):
        mock_response = MagicMock()
        mock_response.text = '  Gemini explanation.  '
        mock_client_instance = MagicMock()
        mock_client_instance.models.generate_content.return_value = mock_response
        mock_genai = MagicMock()
        mock_genai.Client.return_value = mock_client_instance
        with patch('ml.explain.GEMINI_API_KEY', 'fake_key'), \
             patch.dict('sys.modules', {'google': MagicMock(genai=mock_genai), 'google.genai': mock_genai}):
            result = explain_with_gemini('test prompt')
        assert result == 'Gemini explanation.'

    def test_generate_explanations_skips_when_none(self, tmp_path):
        db_path = str(tmp_path / 'test.db')
        conn = sqlite3.connect(db_path)
        conn.execute('''CREATE TABLE anomaly_alerts (
            id INTEGER PRIMARY KEY, pipeline_name TEXT, stage TEXT,
            anomaly_type TEXT, severity TEXT, iso_score REAL,
            job_run_id INTEGER, models_flagged TEXT,
            ai_explanation TEXT, explanation_source TEXT)''')
        conn.execute('''CREATE TABLE job_runs (
            id INTEGER PRIMARY KEY, pipeline_name TEXT, is_anomaly INTEGER,
            duration_seconds REAL, rows_ingested INTEGER, rows_output INTEGER,
            data_volume_mb REAL, processing_time_seconds REAL)''')
        conn.commit()
        conn.close()
        with patch('ml.explain.DB_PATH', db_path), \
             patch('ml.explain.GROQ_API_KEY', ''), \
             patch('ml.explain.GEMINI_API_KEY', ''):
            generate_explanations()  # should run with 0 anomalies, no error

    def test_generate_explanations_uses_fallback(self, tmp_path):
        db_path = str(tmp_path / 'test.db')
        conn = sqlite3.connect(db_path)
        conn.execute('''CREATE TABLE anomaly_alerts (
            id INTEGER PRIMARY KEY, pipeline_name TEXT, stage TEXT,
            anomaly_type TEXT, severity TEXT, iso_score REAL,
            job_run_id INTEGER, models_flagged TEXT,
            ai_explanation TEXT, explanation_source TEXT)''')
        conn.execute('''CREATE TABLE job_runs (
            id INTEGER PRIMARY KEY, pipeline_name TEXT, is_anomaly INTEGER,
            duration_seconds REAL, rows_ingested INTEGER, rows_output INTEGER,
            data_volume_mb REAL, processing_time_seconds REAL)''')
        conn.execute("INSERT INTO anomaly_alerts VALUES (1,'batch_ingestion_01','ingest','ml_detected','high',-0.4,1,'Isolation Forest',NULL,NULL)")
        conn.execute("INSERT INTO job_runs VALUES (1,'batch_ingestion_01',1,80.0,10000,100,45.0,80.0)")
        conn.commit()
        conn.close()
        with patch('ml.explain.DB_PATH', db_path), \
             patch('ml.explain.GROQ_API_KEY', ''), \
             patch('ml.explain.GEMINI_API_KEY', ''):
            generate_explanations()
        result = sqlite3.connect(db_path).execute(
            'SELECT explanation_source FROM anomaly_alerts WHERE id=1'
        ).fetchone()
        assert result[0] == 'template'


# ── benchmark.py additional coverage ─────────────────────────────────────────
from ml.benchmark import load_labeled_data, benchmark_pipeline, run_benchmark

class TestBenchmarkCoverage:
    def test_load_labeled_data(self, tmp_path):
        db_path = str(tmp_path / 'test.db')
        conn = sqlite3.connect(db_path)
        conn.execute('''CREATE TABLE job_runs (
            id INTEGER PRIMARY KEY, pipeline_name TEXT, status TEXT, is_anomaly INTEGER,
            duration_seconds REAL, rows_ingested INTEGER, rows_output INTEGER,
            data_volume_mb REAL, processing_time_seconds REAL)''')
        for i in range(5):
            conn.execute(f"INSERT INTO job_runs VALUES ({i},'batch_ingestion_01','success',{i%2},14.5,10000,9500,45.0,13.0)")
        conn.commit()
        conn.close()
        with patch('ml.benchmark.DB_PATH', db_path):
            df = load_labeled_data('batch_ingestion_01')
        assert len(df) == 5
        assert 'is_anomaly' in df.columns

    def test_benchmark_pipeline_not_enough_data(self, tmp_path):
        db_path = str(tmp_path / 'test.db')
        conn = sqlite3.connect(db_path)
        conn.execute('''CREATE TABLE job_runs (
            id INTEGER PRIMARY KEY, pipeline_name TEXT, status TEXT, is_anomaly INTEGER,
            duration_seconds REAL, rows_ingested INTEGER, rows_output INTEGER,
            data_volume_mb REAL, processing_time_seconds REAL)''')
        conn.commit()
        conn.close()
        with patch('ml.benchmark.DB_PATH', db_path):
            results = benchmark_pipeline('batch_ingestion_01')
        assert results == []


# ── alert.py additional coverage ─────────────────────────────────────────────
from ml.alert import get_high_severity_alerts

class TestAlertCoverage:
    def test_get_high_severity_alerts_from_db(self, tmp_path):
        db_path = str(tmp_path / 'test.db')
        conn = sqlite3.connect(db_path)
        conn.execute('''CREATE TABLE anomaly_alerts (
            id INTEGER PRIMARY KEY, job_run_id INTEGER, pipeline_name TEXT,
            stage TEXT, anomaly_type TEXT, severity TEXT, iso_score REAL,
            ai_explanation TEXT, detected_at TEXT)''')
        conn.execute("INSERT INTO anomaly_alerts VALUES (1,10,'batch_ingestion_01','ingest','ml_detected','high',-0.4,NULL,'2026-01-01')")
        conn.execute("INSERT INTO anomaly_alerts VALUES (2,11,'batch_ingestion_01','ingest','ml_detected','medium',-0.2,NULL,'2026-01-01')")
        conn.commit()
        with patch('ml.alert.DB_PATH', db_path):
            results = get_high_severity_alerts(severity_filter='high')
        assert len(results) == 1
        assert results[0]['severity'] == 'high'

    def test_get_high_severity_with_existing_conn(self, tmp_path):
        db_path = str(tmp_path / 'test.db')
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        conn.execute('''CREATE TABLE anomaly_alerts (
            id INTEGER PRIMARY KEY, job_run_id INTEGER, pipeline_name TEXT,
            stage TEXT, anomaly_type TEXT, severity TEXT, iso_score REAL,
            ai_explanation TEXT, detected_at TEXT)''')
        conn.execute("INSERT INTO anomaly_alerts VALUES (1,10,'batch_ingestion_01','ingest','ml_detected','high',-0.4,NULL,'2026-01-01')")
        conn.commit()
        results = get_high_severity_alerts(conn=conn, severity_filter='high')
        assert len(results) == 1
        conn.close()


# ── score_all.py: load_model, ensure_columns exception, run_scoring ───────────
import pickle
from ml.score_all import load_model, run_scoring

class TestScoreAllAdditional:
    def test_ensure_columns_hits_except_when_column_exists(self, tmp_path):
        db = sqlite3.connect(str(tmp_path / 'test.db'))
        db.execute('''CREATE TABLE anomaly_alerts (
            id INTEGER PRIMARY KEY, job_run_id INTEGER,
            models_flagged TEXT, explanation_source TEXT)''')
        db.commit()
        # All 3 columns already exist → ALTER raises → except block runs (lines 56-57)
        ensure_columns(db)
        db.close()

    def test_load_model_returns_none_when_no_file(self, tmp_path):
        with patch('ml.score_all.MODELS_DIR', str(tmp_path)):
            iso, lof, scaler = load_model('missing_pipeline')
        assert iso is None and lof is None and scaler is None

    def test_load_model_loads_from_file(self, tmp_path):
        from sklearn.ensemble import IsolationForest
        from sklearn.preprocessing import StandardScaler
        from pyod.models.lof import LOF
        import numpy as np

        X = np.random.randn(30, 5)
        scaler_obj = StandardScaler().fit(X)
        iso_obj = IsolationForest().fit(scaler_obj.transform(X))
        lof_obj = LOF()
        lof_obj.fit(scaler_obj.transform(X))

        for name, obj in [('p_iso.pkl', iso_obj), ('p_lof.pkl', lof_obj), ('p_scaler.pkl', scaler_obj)]:
            with open(str(tmp_path / name), 'wb') as f:
                pickle.dump(obj, f)

        with patch('ml.score_all.MODELS_DIR', str(tmp_path)):
            iso, lof, scaler = load_model('p')
        assert iso is not None
        assert lof is not None
        assert scaler is not None

    def test_run_scoring_full_cycle(self, tmp_path):
        db_path = str(tmp_path / 'metrics.db')
        conn = sqlite3.connect(db_path)
        conn.execute('''CREATE TABLE job_runs (
            id INTEGER PRIMARY KEY, pipeline_name TEXT, stage TEXT,
            duration_seconds REAL, rows_ingested INTEGER, rows_output INTEGER,
            data_volume_mb REAL, processing_time_seconds REAL,
            status TEXT, is_anomaly INTEGER, start_time TEXT)''')
        conn.execute('''CREATE TABLE anomaly_alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT, pipeline_name TEXT, stage TEXT,
            anomaly_type TEXT, severity TEXT, iso_score REAL, detected_at TEXT)''')
        conn.execute("INSERT INTO job_runs VALUES (1,'unknown_pipe','ingest',14.5,10000,9500,45.0,13.0,'success',0,'2026-01-01')")
        conn.commit()
        conn.close()
        with patch('ml.score_all.DB_PATH', db_path):
            results = run_scoring(db_path=db_path)
        assert len(results) == 1
        assert results[0]['ml_is_anomaly'] is None  # no model for unknown_pipe

    def test_score_records_cache_miss_triggers_load_model(self, tmp_path):
        with patch('ml.score_all.MODELS_DIR', str(tmp_path)):
            rows = [{'id': 1, 'pipeline_name': 'batch_ingestion_01', 'stage': 'ingest',
                     'duration_seconds': 10, 'rows_ingested': 100, 'rows_output': 90,
                     'data_volume_mb': 5.0, 'processing_time_seconds': 8.0,
                     'status': 'success', 'is_anomaly': 0, 'start_time': '2026-01-01'}]
            cache = {}
            results = score_records(rows, cache=cache)
        # No model files in tmp_path → load_model returns (None, None, None)
        assert results[0]['ml_is_anomaly'] is None
        assert 'batch_ingestion_01' in cache


# ── benchmark.py: benchmark_pipeline with enough data ────────────────────────
from ml.benchmark import benchmark_pipeline, run_benchmark

class TestBenchmarkWithData:
    def _make_db_with_data(self, tmp_path, n=30):
        db_path = str(tmp_path / 'test.db')
        conn = sqlite3.connect(db_path)
        conn.execute('''CREATE TABLE job_runs (
            id INTEGER PRIMARY KEY, pipeline_name TEXT, status TEXT, is_anomaly INTEGER,
            duration_seconds REAL, rows_ingested INTEGER, rows_output INTEGER,
            data_volume_mb REAL, processing_time_seconds REAL)''')
        for i in range(n):
            anomaly = 1 if i % 10 == 0 else 0
            dur = 80.0 if anomaly else 14.5
            conn.execute(f"INSERT INTO job_runs VALUES ({i},'batch_ingestion_01','success',{anomaly},{dur},10000,9500,45.0,13.0)")
        conn.commit()
        conn.close()
        return db_path

    def test_benchmark_pipeline_with_enough_data(self, tmp_path):
        db_path = self._make_db_with_data(tmp_path, n=30)
        with patch('ml.benchmark.DB_PATH', db_path):
            results = benchmark_pipeline('batch_ingestion_01')
        # 4 contamination levels × 2 models = 8 results
        assert len(results) == 8
        assert all('f1' in r for r in results)

    def test_run_benchmark_saves_report(self, tmp_path):
        db_path = self._make_db_with_data(tmp_path, n=30)
        report_path = str(tmp_path / 'report.json')
        with patch('ml.benchmark.DB_PATH', db_path), \
             patch('ml.benchmark.REPORT_PATH', report_path):
            report = run_benchmark()
        assert os.path.exists(report_path)
        assert 'batch_ingestion_01' in report


# ── alert.py: send_alerts non-dry-run path (lines 79-80) ─────────────────────
from ml.alert import send_alerts

class TestAlertSendNonDryRun:
    def test_send_alerts_saves_to_log(self, tmp_path):
        db_path = str(tmp_path / 'test.db')
        log_path = str(tmp_path / 'alert_log.json')
        conn = sqlite3.connect(db_path)
        conn.execute('''CREATE TABLE anomaly_alerts (
            id INTEGER PRIMARY KEY, job_run_id INTEGER, pipeline_name TEXT,
            stage TEXT, anomaly_type TEXT, severity TEXT, iso_score REAL,
            ai_explanation TEXT, detected_at TEXT)''')
        conn.execute("INSERT INTO anomaly_alerts VALUES (1,10,'batch_ingestion_01','ingest','ml_detected','high',-0.4,NULL,'2026-01-01')")
        conn.commit()
        conn.close()
        with patch('ml.alert.DB_PATH', db_path), \
             patch('ml.alert.ALERT_LOG_PATH', log_path):
            result = send_alerts(severity_filter='high', dry_run=False)
        # Lines 79-80: new_entries saved to log
        assert result['new'] == 1
        assert os.path.exists(log_path)


# ── explain.py: build_prompt else branch, generate_explanations with groq ────
from ml.explain import build_prompt, get_normal_stats

class TestExplainAdditional:
    def test_build_prompt_with_feat_missing_from_stats(self):
        anomaly = {'pipeline_name': 'batch_ingestion_01', 'stage': 'ingest',
                   'iso_score': -0.4, 'models_flagged': 'Isolation Forest'}
        job_run = {'duration_seconds': 80.0, 'rows_ingested': 10000, 'rows_output': 100,
                   'data_volume_mb': 45.0, 'processing_time_seconds': 13.0}
        # partial normal_stats — missing 'rows_output' to hit the else branch (line 85)
        normal_stats = {
            'duration_seconds': {'mean': 14.5, 'std': 2.0},
            'rows_ingested': {'mean': 10000, 'std': 500},
            'data_volume_mb': {'mean': 45.0, 'std': 5.0},
            'processing_time_seconds': {'mean': 13.0, 'std': 1.0},
            # 'rows_output' intentionally omitted
        }
        prompt = build_prompt(anomaly, job_run, normal_stats)
        assert 'batch_ingestion_01' in prompt
        assert 'rows_output' in prompt  # still appears via the else branch

    def test_build_prompt_no_job_run(self):
        anomaly = {'pipeline_name': 'batch_ingestion_01', 'stage': 'ingest',
                   'iso_score': -0.4, 'models_flagged': 'Isolation Forest'}
        prompt = build_prompt(anomaly, None, None)
        assert 'ETL' in prompt

    def test_generate_explanations_with_groq_success(self, tmp_path):
        db_path = str(tmp_path / 'test.db')
        conn = sqlite3.connect(db_path)
        conn.execute('''CREATE TABLE anomaly_alerts (
            id INTEGER PRIMARY KEY, pipeline_name TEXT, stage TEXT,
            anomaly_type TEXT, severity TEXT, iso_score REAL,
            job_run_id INTEGER, models_flagged TEXT,
            ai_explanation TEXT, explanation_source TEXT)''')
        conn.execute('''CREATE TABLE job_runs (
            id INTEGER PRIMARY KEY, pipeline_name TEXT, is_anomaly INTEGER,
            duration_seconds REAL, rows_ingested INTEGER, rows_output INTEGER,
            data_volume_mb REAL, processing_time_seconds REAL)''')
        conn.execute("INSERT INTO anomaly_alerts VALUES (1,'batch_ingestion_01','ingest','ml_detected','high',-0.4,1,'Isolation Forest',NULL,NULL)")
        conn.execute("INSERT INTO job_runs VALUES (1,'batch_ingestion_01',1,80.0,10000,100,45.0,80.0)")
        conn.commit()
        conn.close()

        mock_response = MagicMock()
        mock_response.choices[0].message.content = 'Groq explanation text'
        mock_client_instance = MagicMock()
        mock_client_instance.chat.completions.create.return_value = mock_response
        mock_groq_class = MagicMock(return_value=mock_client_instance)

        with patch('ml.explain.DB_PATH', db_path), \
             patch('ml.explain.GROQ_API_KEY', 'fake_key'), \
             patch('ml.explain.GEMINI_API_KEY', ''), \
             patch.dict('sys.modules', {'groq': MagicMock(Groq=mock_groq_class)}):
            generate_explanations()

        result = sqlite3.connect(db_path).execute(
            'SELECT explanation_source FROM anomaly_alerts WHERE id=1'
        ).fetchone()
        assert 'Groq' in result[0]


# ── train.py: train_pipeline with enough data + mocked mlflow ────────────────
class TestTrainPipelineActual:
    def _make_train_db(self, tmp_path, n=20):
        db_path = str(tmp_path / 'train.db')
        conn = sqlite3.connect(db_path)
        conn.execute('''CREATE TABLE job_runs (
            id INTEGER PRIMARY KEY, pipeline_name TEXT, is_anomaly INTEGER, status TEXT,
            duration_seconds REAL, rows_ingested INTEGER, rows_output INTEGER,
            data_volume_mb REAL, processing_time_seconds REAL)''')
        for i in range(n):
            conn.execute(f"INSERT INTO job_runs VALUES ({i},'batch_ingestion_01',0,'success',14.5,10000,9500,45.0,13.0)")
        conn.commit()
        conn.close()
        return db_path

    def test_train_pipeline_with_mocked_mlflow(self, tmp_path):
        from ml.train import train_pipeline
        db_path = self._make_train_db(tmp_path, n=20)
        models_dir = str(tmp_path / 'models')
        os.makedirs(models_dir)
        mlflow_db = str(tmp_path / 'mlflow.db')

        mock_run = MagicMock()
        mock_run.__enter__ = MagicMock(return_value=mock_run)
        mock_run.__exit__ = MagicMock(return_value=False)

        with patch('ml.train.DB_PATH', db_path), \
             patch('ml.train.MODELS_DIR', models_dir), \
             patch('ml.train.MLFLOW_DB', mlflow_db), \
             patch('mlflow.start_run', return_value=mock_run), \
             patch('mlflow.log_param'), \
             patch('mlflow.log_metric'), \
             patch('mlflow.sklearn.log_model'):
            result = train_pipeline('batch_ingestion_01')

        # Models should be saved
        assert os.path.exists(os.path.join(models_dir, 'batch_ingestion_01_iso.pkl'))
        assert os.path.exists(os.path.join(models_dir, 'batch_ingestion_01_lof.pkl'))
        assert os.path.exists(os.path.join(models_dir, 'batch_ingestion_01_scaler.pkl'))

    def test_inject_anomalies_returns_n_rows(self, tmp_path):
        import pandas as pd
        from ml.train import inject_anomalies
        df = pd.DataFrame({
            'duration_seconds': [14.5] * 20,
            'rows_ingested': [10000] * 20,
            'rows_output': [9500] * 20,
            'data_volume_mb': [45.0] * 20,
            'processing_time_seconds': [13.0] * 20,
        })
        anomalies = inject_anomalies(df, n=5)
        assert len(anomalies) == 5
        assert anomalies['duration_seconds'].max() > 14.5
