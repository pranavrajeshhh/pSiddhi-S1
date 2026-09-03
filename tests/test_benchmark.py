import pytest
import os
import sys
import json
import sqlite3
import pandas as pd
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from ml.benchmark import (
    evaluate_model,
    find_best_contamination,
    benchmark_pipeline,
    CONTAMINATION_VALUES,
    FEATURES,
)


class TestEvaluateModel:
    def test_perfect_predictions(self):
        y_true = [0, 0, 0, 1, 1]
        y_pred = [1, 1, 1, -1, -1]
        result = evaluate_model(y_true, y_pred, 'IsolationForest', 0.05)
        assert result['precision'] == 1.0
        assert result['recall'] == 1.0
        assert result['f1'] == 1.0

    def test_no_true_positives(self):
        y_true = [0, 0, 0, 1, 1]
        y_pred = [1, 1, 1, 1, 1]  # all predicted normal (no -1)
        result = evaluate_model(y_true, y_pred, 'IsolationForest', 0.05)
        assert result['recall'] == 0.0

    def test_false_positive_rate_computed(self):
        y_true = [0, 0, 0, 0, 1]
        y_pred = [-1, 1, 1, 1, -1]  # 1 FP, 1 TP
        result = evaluate_model(y_true, y_pred, 'IsolationForest', 0.05)
        assert result['fp_rate'] == 0.25

    def test_result_contains_all_keys(self):
        y_true = [0, 0, 1]
        y_pred = [1, 1, -1]
        result = evaluate_model(y_true, y_pred, 'LOF', 0.05)
        for key in ['model', 'contamination', 'precision', 'recall', 'f1', 'fp_rate', 'total_flagged']:
            assert key in result

    def test_no_anomalies_in_true_returns_none(self):
        y_true = [0, 0, 0]
        y_pred = [-1, 1, 1]
        result = evaluate_model(y_true, y_pred, 'IsolationForest', 0.05)
        assert result is None

    def test_contamination_preserved_in_result(self):
        y_true = [0, 0, 1]
        y_pred = [1, 1, -1]
        result = evaluate_model(y_true, y_pred, 'IsolationForest', 0.07)
        assert result['contamination'] == 0.07


class TestFindBestContamination:
    def _make_results(self):
        return [
            {'model': 'IsolationForest', 'contamination': 0.03, 'f1': 0.60, 'precision': 0.7, 'recall': 0.5, 'fp_rate': 0.02},
            {'model': 'IsolationForest', 'contamination': 0.05, 'f1': 0.80, 'precision': 0.8, 'recall': 0.8, 'fp_rate': 0.05},
            {'model': 'IsolationForest', 'contamination': 0.10, 'f1': 0.70, 'precision': 0.6, 'recall': 0.9, 'fp_rate': 0.10},
            {'model': 'LOF', 'contamination': 0.05, 'f1': 0.75, 'precision': 0.75, 'recall': 0.75, 'fp_rate': 0.04},
        ]

    def test_finds_highest_f1(self):
        results = self._make_results()
        best = find_best_contamination(results, 'IsolationForest', metric='f1')
        assert best['contamination'] == 0.05
        assert best['f1'] == 0.80

    def test_filters_by_model_name(self):
        results = self._make_results()
        best = find_best_contamination(results, 'LOF', metric='f1')
        assert best['model'] == 'LOF'

    def test_returns_none_for_missing_model(self):
        results = self._make_results()
        best = find_best_contamination(results, 'NonExistentModel')
        assert best is None


class TestContaminationValues:
    def test_contamination_values_are_valid_floats(self):
        for c in CONTAMINATION_VALUES:
            assert 0 < c < 1

    def test_contamination_includes_default_005(self):
        assert 0.05 in CONTAMINATION_VALUES
