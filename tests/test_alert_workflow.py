import pytest
import json
import os
import sys
import tempfile
import sqlite3
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from ml.alert import (
    format_alert_entry,
    get_alert_summary,
    load_alert_log,
    save_alert_log,
    send_alerts,
    get_high_severity_alerts,
    SEVERITY_LEVELS,
)


SAMPLE_ALERT = {
    'id': 1,
    'job_run_id': 42,
    'pipeline_name': 'batch_ingestion_01',
    'stage': 'ingestion',
    'anomaly_type': 'duration_spike',
    'severity': 'high',
    'iso_score': -0.45,
    'ai_explanation': 'Duration was 3x the normal baseline.',
    'detected_at': '2026-01-01T10:00:00',
}


class TestSeverityLevels:
    def test_high_severity_level(self):
        assert SEVERITY_LEVELS['high'] == 3

    def test_medium_severity_level(self):
        assert SEVERITY_LEVELS['medium'] == 2

    def test_low_severity_level(self):
        assert SEVERITY_LEVELS['low'] == 1

    def test_high_is_highest(self):
        assert SEVERITY_LEVELS['high'] > SEVERITY_LEVELS['medium'] > SEVERITY_LEVELS['low']


class TestFormatAlertEntry:
    def test_format_contains_all_keys(self):
        entry = format_alert_entry(SAMPLE_ALERT)
        for key in ['alert_id', 'job_run_id', 'pipeline_name', 'stage',
                    'anomaly_type', 'severity', 'iso_score', 'detected_at', 'notified_at']:
            assert key in entry

    def test_format_preserves_values(self):
        entry = format_alert_entry(SAMPLE_ALERT)
        assert entry['alert_id'] == 1
        assert entry['pipeline_name'] == 'batch_ingestion_01'
        assert entry['severity'] == 'high'
        assert entry['iso_score'] == -0.45

    def test_format_custom_notified_at(self):
        entry = format_alert_entry(SAMPLE_ALERT, notified_at='2026-01-01T12:00:00')
        assert entry['notified_at'] == '2026-01-01T12:00:00'

    def test_format_auto_notified_at_set(self):
        entry = format_alert_entry(SAMPLE_ALERT)
        assert entry['notified_at'] is not None
        assert len(entry['notified_at']) > 0

    def test_format_missing_explanation_defaults_empty(self):
        alert = dict(SAMPLE_ALERT)
        alert['ai_explanation'] = None
        entry = format_alert_entry(alert)
        assert entry['ai_explanation'] == ''


class TestAlertLog:
    def test_save_and_load_round_trip(self, tmp_path):
        log_path = str(tmp_path / 'alert_log.json')
        entries = [format_alert_entry(SAMPLE_ALERT)]
        with patch('ml.alert.ALERT_LOG_PATH', log_path):
            save_alert_log(entries)
            loaded = load_alert_log()
        assert len(loaded) == 1
        assert loaded[0]['alert_id'] == 1

    def test_load_returns_empty_list_when_file_missing(self, tmp_path):
        missing_path = str(tmp_path / 'nonexistent.json')
        with patch('ml.alert.ALERT_LOG_PATH', missing_path):
            result = load_alert_log()
        assert result == []

    def test_load_returns_empty_list_on_corrupt_json(self, tmp_path):
        bad_path = tmp_path / 'bad.json'
        bad_path.write_text('NOT JSON {{{')
        with patch('ml.alert.ALERT_LOG_PATH', str(bad_path)):
            result = load_alert_log()
        assert result == []


class TestGetAlertSummary:
    def test_summary_with_empty_log(self, tmp_path):
        log_path = str(tmp_path / 'empty.json')
        with patch('ml.alert.ALERT_LOG_PATH', log_path):
            summary = get_alert_summary()
        assert summary['total_notified'] == 0
        assert summary['last_alert'] is None

    def test_summary_counts_by_pipeline(self, tmp_path):
        log_path = str(tmp_path / 'log.json')
        entries = [
            format_alert_entry({**SAMPLE_ALERT, 'id': 1}),
            format_alert_entry({**SAMPLE_ALERT, 'id': 2, 'pipeline_name': 'transformation_pipeline_01'}),
        ]
        with patch('ml.alert.ALERT_LOG_PATH', log_path):
            save_alert_log(entries)
            summary = get_alert_summary()
        assert summary['total_notified'] == 2
        assert 'batch_ingestion_01' in summary['by_pipeline']

    def test_summary_counts_by_severity(self, tmp_path):
        log_path = str(tmp_path / 'log.json')
        entries = [
            format_alert_entry({**SAMPLE_ALERT, 'id': 1, 'severity': 'high'}),
            format_alert_entry({**SAMPLE_ALERT, 'id': 2, 'severity': 'medium'}),
        ]
        with patch('ml.alert.ALERT_LOG_PATH', log_path):
            save_alert_log(entries)
            summary = get_alert_summary()
        assert summary['by_severity']['high'] == 1
        assert summary['by_severity']['medium'] == 1


class TestSendAlerts:
    def test_dry_run_does_not_write_log(self, tmp_path):
        log_path = str(tmp_path / 'alert_log.json')
        sample_alerts = [SAMPLE_ALERT]
        with patch('ml.alert.ALERT_LOG_PATH', log_path), \
             patch('ml.alert.get_high_severity_alerts', return_value=sample_alerts):
            result = send_alerts(dry_run=True)
        assert not os.path.exists(log_path)
        assert result['new'] == 1

    def test_no_alerts_returns_zero_new(self, tmp_path):
        log_path = str(tmp_path / 'alert_log.json')
        with patch('ml.alert.ALERT_LOG_PATH', log_path), \
             patch('ml.alert.get_high_severity_alerts', return_value=[]):
            result = send_alerts()
        assert result['new'] == 0

    def test_deduplication_skips_already_notified(self, tmp_path):
        log_path = str(tmp_path / 'alert_log.json')
        existing = [format_alert_entry(SAMPLE_ALERT)]
        with patch('ml.alert.ALERT_LOG_PATH', log_path):
            save_alert_log(existing)
            with patch('ml.alert.get_high_severity_alerts', return_value=[SAMPLE_ALERT]):
                result = send_alerts()
        assert result['new'] == 0
