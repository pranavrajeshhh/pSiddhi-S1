import pytest
import sqlite3
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'etl_metrics.db')
FEATURES = ['duration_seconds', 'rows_ingested', 'rows_output', 'data_volume_mb', 'processing_time_seconds']


class TestMetricIngestion:
    def test_all_metric_columns_present(self):
        conn = sqlite3.connect(DB_PATH)
        row = conn.execute(
            "SELECT duration_seconds, rows_ingested, rows_output, data_volume_mb, processing_time_seconds FROM job_runs LIMIT 1"
        ).fetchone()
        conn.close()
        assert row is not None and len(row) == 5

    def test_metric_values_are_numeric(self):
        conn = sqlite3.connect(DB_PATH)
        rows = conn.execute(
            "SELECT duration_seconds, rows_ingested, rows_output, data_volume_mb, processing_time_seconds FROM job_runs LIMIT 50"
        ).fetchall()
        conn.close()
        for row in rows:
            for val in row:
                assert isinstance(val, (int, float)), f"Non-numeric value: {val}"

    def test_duration_within_expected_range(self):
        conn = sqlite3.connect(DB_PATH)
        rows = conn.execute("SELECT duration_seconds FROM job_runs WHERE is_anomaly = 0").fetchall()
        conn.close()
        durations = [r[0] for r in rows]
        avg = sum(durations) / len(durations)
        assert 5 <= avg <= 60, f"Average duration {avg:.1f}s outside expected range"

    def test_rows_ingested_positive(self):
        conn = sqlite3.connect(DB_PATH)
        bad = conn.execute("SELECT COUNT(*) FROM job_runs WHERE rows_ingested <= 0").fetchone()[0]
        conn.close()
        assert bad == 0, f"{bad} records have zero or negative rows_ingested"

    def test_both_pipelines_ingesting(self):
        conn = sqlite3.connect(DB_PATH)
        counts = conn.execute(
            "SELECT pipeline_name, COUNT(*) FROM job_runs GROUP BY pipeline_name"
        ).fetchall()
        conn.close()
        assert len(counts) == 2
        for name, count in counts:
            assert count >= 10, f"Pipeline {name} has only {count} records"

    def test_data_spans_multiple_time_periods(self):
        conn = sqlite3.connect(DB_PATH)
        distinct = conn.execute("SELECT COUNT(DISTINCT start_time) FROM job_runs").fetchone()[0]
        conn.close()
        assert distinct >= 10, f"Only {distinct} distinct timestamps — expected multiple ingestion periods"
