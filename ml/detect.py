import sqlite3
import pandas as pd
import numpy as np
import os
import pickle
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'etl_metrics.db')
MODELS_DIR = os.path.join(os.path.dirname(__file__), '..', 'models')

FEATURES = ['duration_seconds', 'rows_ingested', 'rows_output', 'data_volume_mb', 'processing_time_seconds']

def load_model(pipeline_name):
    safe_name = pipeline_name.replace(' ', '_')
    scaler_path = os.path.join(MODELS_DIR, f'{safe_name}_scaler.pkl')
    iso_path = os.path.join(MODELS_DIR, f'{safe_name}_iso.pkl')
    lof_path = os.path.join(MODELS_DIR, f'{safe_name}_lof.pkl')

    if not all(os.path.exists(p) for p in [scaler_path, iso_path, lof_path]):
        return None, None, None

    with open(scaler_path, 'rb') as f: scaler = pickle.load(f)
    with open(iso_path, 'rb') as f: iso = pickle.load(f)
    with open(lof_path, 'rb') as f: lof = pickle.load(f)
    return scaler, iso, lof

def classify_anomaly(row, baseline_means):
    anomaly_type = []
    if row['duration_seconds'] > baseline_means['duration_seconds'] * 2:
        anomaly_type.append('duration_spike')
    if row['rows_output'] < baseline_means['rows_output'] * 0.5:
        anomaly_type.append('volume_drop')
    if row['processing_time_seconds'] > baseline_means['processing_time_seconds'] * 2:
        anomaly_type.append('processing_time_deviation')
    return ', '.join(anomaly_type) if anomaly_type else 'unknown_anomaly'

def get_severity(iso_score):
    if iso_score < -0.3:
        return 'high'
    elif iso_score < -0.1:
        return 'medium'
    return 'low'

def score_recent_runs(limit=20):
    conn = sqlite3.connect(DB_PATH)

    init_anomaly_table(conn)

    df_all = pd.read_sql_query("SELECT * FROM job_runs WHERE status='success' ORDER BY id DESC", conn)
    if df_all.empty:
        print("No data found.")
        conn.close()
        return

    anomalies_found = []

    for pipeline_name in df_all['pipeline_name'].unique():
        scaler, iso, lof = load_model(pipeline_name)
        if iso is None:
            print(f"No model found for {pipeline_name} — run train.py first.")
            continue

        df_pipeline = df_all[df_all['pipeline_name'] == pipeline_name].copy()
        df_recent = df_pipeline.head(limit)

        baseline_means = df_pipeline[FEATURES].mean()
        X = scaler.transform(df_recent[FEATURES].fillna(0))

        iso_preds = iso.predict(X)
        iso_scores = iso.decision_function(X)
        lof_preds = lof.predict(X)

        for i, (idx, row) in enumerate(df_recent.iterrows()):
            is_anomaly = (iso_preds[i] == -1) or (lof_preds[i] == 1)
            if is_anomaly:
                anomaly_type = classify_anomaly(row, baseline_means)
                severity = get_severity(iso_scores[i])
                conn.execute('''
                    UPDATE job_runs SET is_anomaly = 1 WHERE id = ?
                ''', (row['id'],))
                conn.execute('''
                    INSERT OR IGNORE INTO anomaly_alerts
                    (job_run_id, pipeline_name, stage, anomaly_type, severity,
                     iso_score, detected_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (int(row['id']), pipeline_name, row['stage'],
                      anomaly_type, severity, float(iso_scores[i]),
                      datetime.now().isoformat()))
                anomalies_found.append({
                    'pipeline': pipeline_name,
                    'stage': row['stage'],
                    'type': anomaly_type,
                    'severity': severity,
                    'iso_score': round(iso_scores[i], 4)
                })
                print(f"  ANOMALY [{severity.upper()}] {pipeline_name}/{row['stage']} — {anomaly_type}")

    conn.commit()
    conn.close()

    if not anomalies_found:
        print("No anomalies detected in recent runs.")
    else:
        print(f"\nTotal anomalies detected: {len(anomalies_found)}")

    return anomalies_found

def init_anomaly_table(conn):
    conn.execute('''
        CREATE TABLE IF NOT EXISTS anomaly_alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_run_id INTEGER,
            pipeline_name TEXT,
            stage TEXT,
            anomaly_type TEXT,
            severity TEXT,
            iso_score REAL,
            ai_explanation TEXT,
            detected_at TEXT,
            UNIQUE(job_run_id)
        )
    ''')
    conn.commit()

if __name__ == '__main__':
    print("Scoring recent pipeline runs for anomalies...")
    score_recent_runs()
