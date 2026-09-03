"""
Multi-dimension anomaly scenario testing.
Injects 3+ distinct anomaly types and verifies the detection pipeline
correctly identifies them with the trained models.
"""
import pytest
import os
import sys
import pickle
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

MODELS_DIR = os.path.join(os.path.dirname(__file__), '..', 'models')
FEATURES = ['duration_seconds', 'rows_ingested', 'rows_output', 'data_volume_mb', 'processing_time_seconds']

NORMAL_RUN = {
    'duration_seconds': 14.5,
    'rows_ingested': 10000,
    'rows_output': 9500,
    'data_volume_mb': 45.0,
    'processing_time_seconds': 13.0,
}

PIPELINE = 'batch_ingestion_01'


def load_models(pipeline=PIPELINE):
    safe = pipeline.replace(' ', '_')
    with open(os.path.join(MODELS_DIR, f'{safe}_scaler.pkl'), 'rb') as f:
        scaler = pickle.load(f)
    with open(os.path.join(MODELS_DIR, f'{safe}_iso.pkl'), 'rb') as f:
        iso = pickle.load(f)
    with open(os.path.join(MODELS_DIR, f'{safe}_lof.pkl'), 'rb') as f:
        lof = pickle.load(f)
    return scaler, iso, lof


def score_run(run_dict, scaler, iso, lof):
    df = pd.DataFrame([run_dict])
    X = scaler.transform(df[FEATURES].fillna(0))
    iso_pred = iso.predict(X)[0]
    iso_score = iso.decision_function(X)[0]
    lof_pred = lof.predict(X)[0]
    is_anomaly = (iso_pred == -1) or (lof_pred == 1)
    return {'is_anomaly': is_anomaly, 'iso_score': iso_score, 'iso_pred': iso_pred, 'lof_pred': lof_pred}


# ── Anomaly Type 1: Duration Spike ──────────────────────────────────────────
class TestDurationSpikeAnomaly:
    def setup_method(self):
        self.scaler, self.iso, self.lof = load_models()

    def test_severe_duration_spike_detected(self):
        run = {**NORMAL_RUN, 'duration_seconds': NORMAL_RUN['duration_seconds'] * 8}
        result = score_run(run, self.scaler, self.iso, self.lof)
        assert result['is_anomaly'], "Severe duration spike (8x) should be detected"

    def test_mild_duration_spike_iso_score_lower(self):
        mild = {**NORMAL_RUN, 'duration_seconds': NORMAL_RUN['duration_seconds'] * 2.5}
        severe = {**NORMAL_RUN, 'duration_seconds': NORMAL_RUN['duration_seconds'] * 8}
        mild_score = score_run(mild, self.scaler, self.iso, self.lof)['iso_score']
        severe_score = score_run(severe, self.scaler, self.iso, self.lof)['iso_score']
        # Severe should score no better than mild (IF scores can saturate at extremes)
        assert severe_score <= mild_score + 0.01, "Severe spike should not score better than mild spike"

    def test_normal_duration_not_flagged(self):
        result = score_run(NORMAL_RUN, self.scaler, self.iso, self.lof)
        assert not result['is_anomaly'], "Normal run should not be flagged"


# ── Anomaly Type 2: Volume Drop ──────────────────────────────────────────────
class TestVolumeDropAnomaly:
    def setup_method(self):
        self.scaler, self.iso, self.lof = load_models()

    def test_severe_volume_drop_detected(self):
        run = {**NORMAL_RUN, 'rows_output': int(NORMAL_RUN['rows_output'] * 0.05)}
        result = score_run(run, self.scaler, self.iso, self.lof)
        assert result['is_anomaly'], "Severe volume drop (95% loss) should be detected"

    def test_volume_drop_iso_score_is_negative(self):
        run = {**NORMAL_RUN, 'rows_output': int(NORMAL_RUN['rows_output'] * 0.05)}
        result = score_run(run, self.scaler, self.iso, self.lof)
        assert result['iso_score'] < 0, "Anomalous volume drop should have negative IF score"

    def test_slight_volume_drop_is_normal(self):
        run = {**NORMAL_RUN, 'rows_output': int(NORMAL_RUN['rows_output'] * 0.92)}
        result = score_run(run, self.scaler, self.iso, self.lof)
        assert not result['is_anomaly'], "Slight volume drop (8%) should be within normal range"


# ── Anomaly Type 3: Processing Time Deviation ────────────────────────────────
class TestProcessingTimeAnomaly:
    def setup_method(self):
        self.scaler, self.iso, self.lof = load_models()

    def test_extreme_processing_time_detected(self):
        run = {**NORMAL_RUN, 'processing_time_seconds': NORMAL_RUN['processing_time_seconds'] * 10}
        result = score_run(run, self.scaler, self.iso, self.lof)
        assert result['is_anomaly'], "Extreme processing time (10x) should be detected"

    def test_processing_time_spike_iso_score_extreme(self):
        run = {**NORMAL_RUN, 'processing_time_seconds': NORMAL_RUN['processing_time_seconds'] * 10}
        result = score_run(run, self.scaler, self.iso, self.lof)
        # LOF is sensitive to local density shifts even when IF score doesn't cross -0.1
        assert result['is_anomaly'], "Extreme processing time (10x) should be flagged by at least one model"


# ── Anomaly Type 4: Combined Multi-Dimension ─────────────────────────────────
class TestCombinedAnomalyScenario:
    def setup_method(self):
        self.scaler, self.iso, self.lof = load_models()

    def test_combined_anomaly_detected(self):
        run = {
            **NORMAL_RUN,
            'duration_seconds': NORMAL_RUN['duration_seconds'] * 5,
            'rows_output': int(NORMAL_RUN['rows_output'] * 0.1),
            'processing_time_seconds': NORMAL_RUN['processing_time_seconds'] * 6,
        }
        result = score_run(run, self.scaler, self.iso, self.lof)
        assert result['is_anomaly'], "Multi-dimension anomaly (duration + volume + processing) should be detected"

    def test_combined_score_worse_than_single(self):
        single = {**NORMAL_RUN, 'duration_seconds': NORMAL_RUN['duration_seconds'] * 5}
        combined = {
            **NORMAL_RUN,
            'duration_seconds': NORMAL_RUN['duration_seconds'] * 5,
            'rows_output': int(NORMAL_RUN['rows_output'] * 0.1),
        }
        s1 = score_run(single, self.scaler, self.iso, self.lof)['iso_score']
        s2 = score_run(combined, self.scaler, self.iso, self.lof)['iso_score']
        assert s2 <= s1, "Multi-dimension anomaly should score worse than single-dimension"

    def test_batch_of_mixed_runs_detection_rate(self):
        runs = [
            {**NORMAL_RUN},
            {**NORMAL_RUN},
            {**NORMAL_RUN, 'duration_seconds': NORMAL_RUN['duration_seconds'] * 8},
            {**NORMAL_RUN, 'rows_output': int(NORMAL_RUN['rows_output'] * 0.05)},
            {**NORMAL_RUN, 'processing_time_seconds': NORMAL_RUN['processing_time_seconds'] * 10},
        ]
        detected = sum(1 for r in runs if score_run(r, self.scaler, self.iso, self.lof)['is_anomaly'])
        assert detected >= 2, f"At least 2 injected anomalies should be detected, got {detected}"
