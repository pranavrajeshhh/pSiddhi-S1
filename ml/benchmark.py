import sqlite3
import pandas as pd
import numpy as np
import os
import pickle
import json
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import precision_score, recall_score, f1_score
from pyod.models.lof import LOF

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'etl_metrics.db')
MODELS_DIR = os.path.join(os.path.dirname(__file__), '..', 'models')
REPORT_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'benchmark_report.json')

FEATURES = ['duration_seconds', 'rows_ingested', 'rows_output', 'data_volume_mb', 'processing_time_seconds']
CONTAMINATION_VALUES = [0.03, 0.05, 0.07, 0.10]


def load_labeled_data(pipeline_name):
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query('''
        SELECT duration_seconds, rows_ingested, rows_output,
               data_volume_mb, processing_time_seconds, is_anomaly
        FROM job_runs
        WHERE pipeline_name = ? AND status = 'success'
    ''', conn, params=(pipeline_name,))
    conn.close()
    return df


def evaluate_model(y_true, y_pred_raw, model_name, contamination):
    y_pred = [1 if p == -1 else 0 for p in y_pred_raw]
    if sum(y_true) == 0:
        return None
    return {
        'model': model_name,
        'contamination': contamination,
        'precision': round(precision_score(y_true, y_pred, zero_division=0), 4),
        'recall': round(recall_score(y_true, y_pred, zero_division=0), 4),
        'f1': round(f1_score(y_true, y_pred, zero_division=0), 4),
        'fp_rate': round(sum(1 for t, p in zip(y_true, y_pred) if t == 0 and p == 1) / max(sum(1 for t in y_true if t == 0), 1), 4),
        'total_flagged': sum(y_pred),
        'actual_anomalies': sum(y_true),
    }


def benchmark_pipeline(pipeline_name):
    df = load_labeled_data(pipeline_name)
    if df.empty or len(df) < 20:
        return []

    X = df[FEATURES].fillna(0).values
    y_true = df['is_anomaly'].fillna(0).astype(int).tolist()

    results = []
    for c in CONTAMINATION_VALUES:
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)

        iso = IsolationForest(contamination=c, n_estimators=100, random_state=42)
        iso.fit(X_scaled)
        iso_preds = iso.predict(X_scaled)
        r = evaluate_model(y_true, iso_preds, 'IsolationForest', c)
        if r:
            results.append(r)

        lof = LOF(n_neighbors=20, contamination=c)
        lof.fit(X_scaled)
        lof_raw = [-1 if p == 1 else 1 for p in lof.predict(X_scaled)]
        r = evaluate_model(y_true, lof_raw, 'LOF', c)
        if r:
            results.append(r)

    return results


def find_best_contamination(results, model_name, metric='f1'):
    model_results = [r for r in results if r['model'] == model_name]
    if not model_results:
        return None
    return max(model_results, key=lambda r: r[metric])


def run_benchmark():
    report = {}
    for pipeline in ['batch_ingestion_01', 'transformation_pipeline_01']:
        print(f"\nBenchmarking: {pipeline}")
        results = benchmark_pipeline(pipeline)
        best_if = find_best_contamination(results, 'IsolationForest')
        best_lof = find_best_contamination(results, 'LOF')
        report[pipeline] = {
            'all_results': results,
            'best_isolation_forest': best_if,
            'best_lof': best_lof,
            'recommendation': best_if['contamination'] if best_if else 0.05,
        }
        if best_if:
            print(f"  Best IF  — contamination={best_if['contamination']}, F1={best_if['f1']}, FP rate={best_if['fp_rate']}")
        if best_lof:
            print(f"  Best LOF — contamination={best_lof['contamination']}, F1={best_lof['f1']}, FP rate={best_lof['fp_rate']}")

    with open(REPORT_PATH, 'w') as f:
        json.dump(report, f, indent=2)
    print(f"\nBenchmark report saved to: {REPORT_PATH}")
    return report


if __name__ == '__main__':
    run_benchmark()
