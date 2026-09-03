import os
import json
import sqlite3
import pickle
import datetime
import numpy as np
from collections import defaultdict

BASE = os.path.join(os.path.dirname(__file__), '..')
DB_PATH = os.path.join(BASE, 'data', 'etl_metrics.db')
MODELS_DIR = os.path.join(BASE, 'models')
FEATURES = ['duration_seconds', 'rows_ingested', 'rows_output', 'data_volume_mb', 'processing_time_seconds']

PIPELINE_KEY_MAP = {
    'batch_ingestion_01': 'batch_ingestion_01',
    'transformation_pipeline_01': 'transformation_pipeline_01',
}
model_cache = {}


def load_model(pipeline_key):
    iso_path = os.path.join(MODELS_DIR, f'{pipeline_key}_iso.pkl')
    lof_path = os.path.join(MODELS_DIR, f'{pipeline_key}_lof.pkl')
    scaler_path = os.path.join(MODELS_DIR, f'{pipeline_key}_scaler.pkl')
    if not os.path.exists(iso_path):
        return None, None, None
    with open(iso_path, 'rb') as f:
        iso = pickle.load(f)
    with open(lof_path, 'rb') as f:
        lof = pickle.load(f)
    with open(scaler_path, 'rb') as f:
        scaler = pickle.load(f)
    return iso, lof, scaler


def get_pipeline_key(pipeline_name):
    for k in PIPELINE_KEY_MAP:
        if k in pipeline_name:
            return k
    return None


def severity(score):
    if score < -0.3:
        return 'high'
    if score < -0.1:
        return 'medium'
    return 'low'


def ensure_columns(conn):
    for col in ['job_run_id INTEGER', 'models_flagged TEXT', 'explanation_source TEXT']:
        try:
            conn.execute(f'ALTER TABLE anomaly_alerts ADD COLUMN {col}')
            conn.commit()
        except Exception:
            pass


def fetch_all_runs(conn):
    cur = conn.cursor()
    cur.execute("""
        SELECT id, pipeline_name, stage, duration_seconds, rows_ingested,
               rows_output, data_volume_mb, processing_time_seconds, status, is_anomaly, start_time
        FROM job_runs ORDER BY id
    """)
    return [dict(r) for r in cur.fetchall()]


def score_records(all_rows, cache=None):
    if cache is None:
        cache = {}
    groups = defaultdict(list)
    no_model = []
    for rec in all_rows:
        key = get_pipeline_key(rec['pipeline_name'])
        if key:
            groups[key].append(rec)
        else:
            no_model.append(rec)

    results_map = {}
    for rec in no_model:
        results_map[rec['id']] = {
            **rec,
            'iso_score': None, 'iso_pred': None, 'lof_pred': None,
            'ml_is_anomaly': None, 'ml_severity': None, 'models_flagged': [],
        }

    for key, recs in groups.items():
        if key not in cache:
            cache[key] = load_model(key)
        iso, lof, scaler = cache[key]

        if iso is None:
            for rec in recs:
                results_map[rec['id']] = {
                    **rec,
                    'iso_score': None, 'iso_pred': None, 'lof_pred': None,
                    'ml_is_anomaly': None, 'ml_severity': None, 'models_flagged': [],
                }
            continue

        feat_matrix = np.array([[rec[f] or 0.0 for f in FEATURES] for rec in recs])
        feat_scaled = scaler.transform(feat_matrix)
        iso_scores = iso.score_samples(feat_scaled)
        iso_preds  = iso.predict(feat_scaled)
        lof_preds  = lof.predict(feat_scaled)

        for i, rec in enumerate(recs):
            ml_anomaly = bool((iso_preds[i] == -1) or (lof_preds[i] == 1))
            flagged = []
            if iso_preds[i] == -1: flagged.append('Isolation Forest')
            if lof_preds[i] == 1:  flagged.append('LOF')
            results_map[rec['id']] = {
                **rec,
                'iso_score': round(float(iso_scores[i]), 6),
                'iso_pred':  int(iso_preds[i]),
                'lof_pred':  int(lof_preds[i]),
                'ml_is_anomaly': ml_anomaly,
                'ml_severity': severity(float(iso_scores[i])) if ml_anomaly else None,
                'models_flagged': flagged,
            }

    return [results_map[r['id']] for r in all_rows]


def write_results(conn, results):
    cur = conn.cursor()
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cur.executemany(
        'UPDATE job_runs SET is_anomaly = ? WHERE id = ?',
        [(1 if r['ml_is_anomaly'] else 0, r['id']) for r in results if r['ml_is_anomaly'] is not None]
    )
    existing_ids = {row[0] for row in cur.execute(
        'SELECT job_run_id FROM anomaly_alerts WHERE job_run_id IS NOT NULL'
    ).fetchall()}
    new_alerts = [
        (r['pipeline_name'], r['stage'], 'ml_detected', r['ml_severity'],
         r['iso_score'], now, r['id'], ', '.join(r['models_flagged']))
        for r in results
        if r['ml_is_anomaly'] and r['id'] not in existing_ids
    ]
    if new_alerts:
        cur.executemany(
            '''INSERT INTO anomaly_alerts
               (pipeline_name, stage, anomaly_type, severity, iso_score, detected_at, job_run_id, models_flagged)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
            new_alerts
        )
    conn.commit()
    return new_alerts


def run_scoring(db_path=None):
    db_path = db_path or DB_PATH
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    ensure_columns(conn)
    all_rows = fetch_all_runs(conn)
    results = score_records(all_rows, cache=model_cache)
    write_results(conn, results)
    conn.close()
    return results


if __name__ == '__main__':
    results = run_scoring()
    print(json.dumps(results))
