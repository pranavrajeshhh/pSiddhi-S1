import pytest
import sqlite3
import os
import sys
import tempfile
import pickle
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'etl_metrics.db')
MODELS_DIR = os.path.join(os.path.dirname(__file__), '..', 'models')


# ── Helpers ───────────────────────────────────────────────────────────────────

def _tmp_db():
    f = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
    f.close()
    return f.name


def _make_test_db(path, n_normal=30, n_anomaly=3):
    from ml.generate_baseline import init_db, PIPELINES
    import random
    conn = sqlite3.connect(path)
    init_db(conn)
    for _ in range(n_normal):
        for pipeline_name, stages in PIPELINES.items():
            for sc in stages:
                dur = round(random.uniform(*sc['duration']), 2)
                rows_in = random.randint(*sc['rows'])
                rows_out = int(rows_in * 0.95)
                vol = round(random.uniform(*sc['volume']), 2)
                conn.execute(
                    '''INSERT INTO job_runs
                       (pipeline_name, stage, start_time, end_time, duration_seconds,
                        rows_ingested, rows_transformed, rows_output, data_volume_mb,
                        processing_time_seconds, status, is_anomaly)
                       VALUES (?,?,datetime('now'),datetime('now'),?,?,?,?,?,?,'success',0)''',
                    (pipeline_name, sc['stage'], dur, rows_in, rows_out, rows_out, vol, dur)
                )
    conn.commit()
    conn.close()
    return path


# ── ml.detect unit tests ─────────────────────────────────────────────────────

class TestClassifyAnomaly:
    def setup_method(self):
        from ml.detect import classify_anomaly
        self.classify = classify_anomaly

    def test_duration_spike_detected(self):
        row = {'duration_seconds': 200, 'rows_output': 900, 'processing_time_seconds': 20}
        base = {'duration_seconds': 60, 'rows_output': 1000, 'processing_time_seconds': 20}
        assert 'duration_spike' in self.classify(row, base)

    def test_volume_drop_detected(self):
        row = {'duration_seconds': 60, 'rows_output': 100, 'processing_time_seconds': 20}
        base = {'duration_seconds': 60, 'rows_output': 1000, 'processing_time_seconds': 20}
        assert 'volume_drop' in self.classify(row, base)

    def test_processing_time_deviation_detected(self):
        row = {'duration_seconds': 60, 'rows_output': 900, 'processing_time_seconds': 120}
        base = {'duration_seconds': 60, 'rows_output': 1000, 'processing_time_seconds': 20}
        assert 'processing_time_deviation' in self.classify(row, base)

    def test_multiple_types_combined(self):
        row = {'duration_seconds': 300, 'rows_output': 50, 'processing_time_seconds': 200}
        base = {'duration_seconds': 60, 'rows_output': 1000, 'processing_time_seconds': 20}
        result = self.classify(row, base)
        assert 'duration_spike' in result
        assert 'volume_drop' in result

    def test_normal_run_returns_unknown(self):
        row = {'duration_seconds': 60, 'rows_output': 950, 'processing_time_seconds': 20}
        base = {'duration_seconds': 60, 'rows_output': 1000, 'processing_time_seconds': 20}
        assert self.classify(row, base) == 'unknown_anomaly'

    def test_boundary_duration_not_spike(self):
        row = {'duration_seconds': 119, 'rows_output': 950, 'processing_time_seconds': 20}
        base = {'duration_seconds': 60, 'rows_output': 1000, 'processing_time_seconds': 20}
        assert 'duration_spike' not in self.classify(row, base)

    def test_boundary_rows_not_drop(self):
        row = {'duration_seconds': 60, 'rows_output': 501, 'processing_time_seconds': 20}
        base = {'duration_seconds': 60, 'rows_output': 1000, 'processing_time_seconds': 20}
        assert 'volume_drop' not in self.classify(row, base)


class TestGetSeverity:
    def setup_method(self):
        from ml.detect import get_severity
        self.sev = get_severity

    def test_high_severity_deep(self):
        assert self.sev(-0.5) == 'high'

    def test_high_severity_at_threshold(self):
        assert self.sev(-0.31) == 'high'

    def test_medium_severity(self):
        assert self.sev(-0.2) == 'medium'

    def test_medium_at_lower_boundary(self):
        assert self.sev(-0.11) == 'medium'

    def test_low_severity_near_zero(self):
        assert self.sev(-0.05) == 'low'

    def test_low_severity_positive(self):
        assert self.sev(0.15) == 'low'

    def test_boundary_high_medium(self):
        # -0.3 is NOT < -0.3, so it falls to medium
        assert self.sev(-0.3) == 'medium'

    def test_boundary_medium_low(self):
        # -0.1 is NOT < -0.1, so it falls to low
        assert self.sev(-0.1) == 'low'


class TestInitAnomalyTable:
    def test_creates_table(self):
        from ml.detect import init_anomaly_table
        tmp = _tmp_db()
        conn = sqlite3.connect(tmp)
        init_anomaly_table(conn)
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()]
        conn.close()
        os.unlink(tmp)
        assert 'anomaly_alerts' in tables

    def test_table_has_required_columns(self):
        from ml.detect import init_anomaly_table
        tmp = _tmp_db()
        conn = sqlite3.connect(tmp)
        init_anomaly_table(conn)
        cols = [r[1] for r in conn.execute("PRAGMA table_info(anomaly_alerts)").fetchall()]
        conn.close()
        os.unlink(tmp)
        for col in ['id', 'job_run_id', 'pipeline_name', 'stage', 'severity', 'iso_score']:
            assert col in cols

    def test_idempotent_create(self):
        from ml.detect import init_anomaly_table
        tmp = _tmp_db()
        conn = sqlite3.connect(tmp)
        init_anomaly_table(conn)
        init_anomaly_table(conn)  # second call must not raise
        conn.close()
        os.unlink(tmp)


class TestLoadModelDetect:
    def test_missing_model_returns_nones(self):
        from ml.detect import load_model
        s, i, l = load_model('nonexistent_pipeline_xyz')
        assert s is None and i is None and l is None

    def test_existing_model_loads(self):
        from ml.detect import load_model
        s, iso, lof = load_model('batch_ingestion_01')
        assert s is not None
        assert iso is not None
        assert lof is not None


# ── ml.explain unit tests ─────────────────────────────────────────────────────

class TestDevianceLabel:
    def setup_method(self):
        from ml.explain import deviance_label
        self.dl = deviance_label

    def test_very_high_positive(self):
        label = self.dl(100, 10, 5)   # z=18
        assert 'HIGHER' in label and '⚠⚠' in label

    def test_very_high_negative(self):
        label = self.dl(1, 100, 10)   # z=9.9
        assert 'LOWER' in label and '⚠⚠' in label

    def test_moderate_deviance(self):
        label = self.dl(22, 10, 4)    # z=3 > 2
        assert '⚠' in label

    def test_minor_deviance(self):
        label = self.dl(16, 10, 4)    # z=1.5 > 1
        assert 'HIGHER' in label

    def test_no_deviance(self):
        assert self.dl(10, 10, 5) == ''

    def test_zero_std_returns_empty(self):
        assert self.dl(50, 10, 0) == ''

    def test_direction_lower(self):
        label = self.dl(1, 100, 5)    # z=19.8, value < mean
        assert 'LOWER' in label


class TestBuildPrompt:
    def setup_method(self):
        from ml.explain import build_prompt
        self.build = build_prompt

    def _anomaly(self, **kw):
        base = {
            'pipeline_name': 'batch_ingestion_01',
            'stage': 'load',
            'iso_score': -0.42,
            'models_flagged': 'Isolation Forest',
            'anomaly_type': 'duration_spike'
        }
        base.update(kw)
        return base

    def test_pipeline_name_in_prompt(self):
        p = self.build(self._anomaly(), None, None)
        assert 'batch_ingestion_01' in p

    def test_stage_in_prompt(self):
        p = self.build(self._anomaly(), None, None)
        assert 'load' in p

    def test_score_in_prompt(self):
        p = self.build(self._anomaly(), None, None)
        assert '-0.4200' in p

    def test_metric_comparison_with_stats(self):
        job_run = {
            'duration_seconds': 180.0,
            'rows_ingested': 10000,
            'rows_output': 500,
            'data_volume_mb': 50.0,
            'processing_time_seconds': 170.0
        }
        stats = {feat: {'mean': 30.0, 'std': 5.0} for feat in
                 ['duration_seconds', 'rows_ingested', 'rows_output',
                  'data_volume_mb', 'processing_time_seconds']}
        p = self.build(self._anomaly(), job_run, stats)
        assert 'METRIC COMPARISON' in p
        assert 'duration_seconds' in p

    def test_no_stats_still_returns_prompt(self):
        p = self.build(self._anomaly(), None, None)
        assert len(p) > 50
        assert 'plain English' in p


class TestFallbackExplanation:
    def setup_method(self):
        from ml.explain import fallback_explanation
        self.fb = fallback_explanation

    def _anomaly(self, atype='ml_detected'):
        return {
            'pipeline_name': 'batch_ingestion_01',
            'stage': 'load',
            'iso_score': -0.4,
            'anomaly_type': atype
        }

    def test_without_stats_uses_template(self):
        result = self.fb(self._anomaly(), None, None)
        assert 'batch_ingestion_01' in result
        assert len(result) > 20

    def test_with_stats_returns_metric_details(self):
        job_run = {
            'duration_seconds': 200.0,
            'rows_ingested': 10000,
            'rows_output': 800,
            'data_volume_mb': 50.0,
            'processing_time_seconds': 190.0
        }
        stats = {feat: {'mean': 30.0, 'std': 5.0} for feat in
                 ['duration_seconds', 'rows_ingested', 'rows_output',
                  'data_volume_mb', 'processing_time_seconds']}
        result = self.fb(self._anomaly(), stats, job_run)
        assert 'batch_ingestion_01' in result

    def test_unknown_anomaly_type(self):
        result = self.fb(self._anomaly('unknown_anomaly'), None, None)
        assert 'batch_ingestion_01' in result

    def test_result_is_string(self):
        result = self.fb(self._anomaly(), None, None)
        assert isinstance(result, str)


class TestGetNormalStats:
    def test_returns_none_for_empty_db(self):
        from ml.explain import get_normal_stats
        tmp = _tmp_db()
        from ml.generate_baseline import init_db
        conn = sqlite3.connect(tmp)
        init_db(conn)
        result = get_normal_stats(conn, 'batch_ingestion_01')
        conn.close()
        os.unlink(tmp)
        assert result is None

    def test_returns_stats_with_data(self):
        from ml.explain import get_normal_stats
        tmp = _make_test_db(_tmp_db(), n_normal=10)
        conn = sqlite3.connect(tmp)
        result = get_normal_stats(conn, 'batch_ingestion_01')
        conn.close()
        os.unlink(tmp)
        assert result is not None
        assert 'duration_seconds' in result
        assert 'mean' in result['duration_seconds']
        assert 'std' in result['duration_seconds']

    def test_stats_values_are_numbers(self):
        from ml.explain import get_normal_stats
        tmp = _make_test_db(_tmp_db(), n_normal=15)
        conn = sqlite3.connect(tmp)
        stats = get_normal_stats(conn, 'batch_ingestion_01')
        conn.close()
        os.unlink(tmp)
        if stats:
            for feat, s in stats.items():
                assert isinstance(s['mean'], float)
                assert isinstance(s['std'], float)


# ── ml.generate_baseline unit tests ──────────────────────────────────────────

class TestGenerateBaseline:
    def test_init_db_creates_job_runs_table(self):
        from ml.generate_baseline import init_db
        tmp = _tmp_db()
        conn = sqlite3.connect(tmp)
        init_db(conn)
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()]
        conn.close()
        os.unlink(tmp)
        assert 'job_runs' in tables

    def test_init_db_idempotent(self):
        from ml.generate_baseline import init_db
        tmp = _tmp_db()
        conn = sqlite3.connect(tmp)
        init_db(conn)
        init_db(conn)
        conn.close()
        os.unlink(tmp)

    def test_generate_creates_records(self):
        from ml.generate_baseline import generate_baseline
        import unittest.mock as mock
        tmp = _tmp_db()
        with mock.patch('ml.generate_baseline.DB_PATH', tmp):
            generate_baseline(num_runs=5)
        conn = sqlite3.connect(tmp)
        count = conn.execute("SELECT COUNT(*) FROM job_runs").fetchone()[0]
        conn.close()
        os.unlink(tmp)
        assert count > 0

    def test_generate_both_pipelines(self):
        from ml.generate_baseline import generate_baseline
        import unittest.mock as mock
        tmp = _tmp_db()
        with mock.patch('ml.generate_baseline.DB_PATH', tmp):
            generate_baseline(num_runs=3)
        conn = sqlite3.connect(tmp)
        pipelines = [r[0] for r in conn.execute(
            "SELECT DISTINCT pipeline_name FROM job_runs"
        ).fetchall()]
        conn.close()
        os.unlink(tmp)
        assert 'batch_ingestion_01' in pipelines
        assert 'transformation_pipeline_01' in pipelines

    def test_generate_all_stages(self):
        from ml.generate_baseline import generate_baseline
        import unittest.mock as mock
        tmp = _tmp_db()
        with mock.patch('ml.generate_baseline.DB_PATH', tmp):
            generate_baseline(num_runs=3)
        conn = sqlite3.connect(tmp)
        stages = [r[0] for r in conn.execute(
            "SELECT DISTINCT stage FROM job_runs"
        ).fetchall()]
        conn.close()
        os.unlink(tmp)
        for stage in ['ingestion', 'transformation', 'load', 'extract', 'clean', 'aggregate']:
            assert stage in stages

    def test_all_records_have_success_status(self):
        from ml.generate_baseline import generate_baseline
        import unittest.mock as mock
        tmp = _tmp_db()
        with mock.patch('ml.generate_baseline.DB_PATH', tmp):
            generate_baseline(num_runs=5)
        conn = sqlite3.connect(tmp)
        failed = conn.execute(
            "SELECT COUNT(*) FROM job_runs WHERE status != 'success'"
        ).fetchone()[0]
        conn.close()
        os.unlink(tmp)
        assert failed == 0

    def test_all_durations_positive(self):
        from ml.generate_baseline import generate_baseline
        import unittest.mock as mock
        tmp = _tmp_db()
        with mock.patch('ml.generate_baseline.DB_PATH', tmp):
            generate_baseline(num_runs=5)
        conn = sqlite3.connect(tmp)
        bad = conn.execute(
            "SELECT COUNT(*) FROM job_runs WHERE duration_seconds <= 0"
        ).fetchone()[0]
        conn.close()
        os.unlink(tmp)
        assert bad == 0


# ── ml.train unit tests ───────────────────────────────────────────────────────

class TestInjectAnomalies:
    def test_returns_dataframe(self):
        from ml.train import inject_anomalies
        import pandas as pd
        df = pd.DataFrame({
            'duration_seconds': [10.0, 15.0, 12.0, 14.0, 11.0],
            'rows_ingested': [1000, 1200, 1100, 1050, 980],
            'rows_output': [950, 1150, 1050, 1000, 930],
            'data_volume_mb': [40.0, 45.0, 42.0, 43.0, 41.0],
            'processing_time_seconds': [10.0, 14.0, 11.0, 13.0, 12.0],
        })
        result = inject_anomalies(df, n=3)
        assert isinstance(result, pd.DataFrame)

    def test_anomalies_have_high_duration(self):
        from ml.train import inject_anomalies
        import pandas as pd
        df = pd.DataFrame({
            'duration_seconds': [10.0] * 10,
            'rows_ingested': [1000] * 10,
            'rows_output': [950] * 10,
            'data_volume_mb': [40.0] * 10,
            'processing_time_seconds': [10.0] * 10,
        })
        result = inject_anomalies(df, n=5)
        assert result['duration_seconds'].mean() > 30.0

    def test_anomalies_have_low_rows_output(self):
        from ml.train import inject_anomalies
        import pandas as pd
        df = pd.DataFrame({
            'duration_seconds': [10.0] * 10,
            'rows_ingested': [1000] * 10,
            'rows_output': [950] * 10,
            'data_volume_mb': [40.0] * 10,
            'processing_time_seconds': [10.0] * 10,
        })
        result = inject_anomalies(df, n=5)
        assert result['rows_output'].mean() < 950 * 0.5
