import pytest
import sqlite3
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'etl_metrics.db')


class TestPromptOutputQuality:
    def test_anomaly_alerts_table_exists(self):
        conn = sqlite3.connect(DB_PATH)
        tables = [t[0] for t in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        conn.close()
        assert 'anomaly_alerts' in tables

    def test_explanations_are_non_empty(self):
        conn = sqlite3.connect(DB_PATH)
        rows = conn.execute(
            "SELECT ai_explanation FROM anomaly_alerts WHERE ai_explanation IS NOT NULL"
        ).fetchall()
        conn.close()
        if not rows:
            pytest.skip("No explanations yet — run explain.py first")
        for row in rows:
            assert len(row[0].strip()) > 20, "Explanation is too short to be meaningful"

    def test_explanation_mentions_pipeline(self):
        conn = sqlite3.connect(DB_PATH)
        rows = conn.execute(
            "SELECT pipeline_name, ai_explanation FROM anomaly_alerts WHERE ai_explanation IS NOT NULL"
        ).fetchall()
        conn.close()
        if not rows:
            pytest.skip("No explanations yet")
        for pipeline, explanation in rows:
            exp_lower = explanation.lower()
            # Explanation should be meaningful: mention pipeline name, stage keyword, or anomaly-related terms
            keywords = [pipeline.split('_')[0], 'pipeline', 'stage', 'anomal', 'metric', 'rows', 'duration', 'data']
            assert any(kw in exp_lower for kw in keywords), \
                f"Explanation not meaningful for {pipeline}: {explanation[:80]}"

    def test_severity_labels_are_valid(self):
        conn = sqlite3.connect(DB_PATH)
        severities = [r[0] for r in conn.execute("SELECT DISTINCT severity FROM anomaly_alerts").fetchall()]
        conn.close()
        for s in severities:
            assert s in {'low', 'medium', 'high'}, f"Invalid severity: {s}"

    def test_anomaly_types_are_classified(self):
        conn = sqlite3.connect(DB_PATH)
        types = [r[0] for r in conn.execute("SELECT anomaly_type FROM anomaly_alerts").fetchall()]
        conn.close()
        # ml_detected is the type assigned by our ML scoring pipeline
        valid = {'duration_spike', 'volume_drop', 'processing_time_deviation', 'unknown_anomaly', 'ml_detected'}
        for t in types:
            for part in t.split(', '):
                assert part in valid, f"Unexpected anomaly type: {part}"
