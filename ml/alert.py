import sqlite3
import json
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'etl_metrics.db')
ALERT_LOG_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'alert_log.json')

SEVERITY_LEVELS = {'high': 3, 'medium': 2, 'low': 1}


def get_high_severity_alerts(conn=None, severity_filter='high'):
    close_conn = conn is None
    if conn is None:
        conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute('''
        SELECT a.id, a.job_run_id, a.pipeline_name, a.stage,
               a.anomaly_type, a.severity, a.iso_score,
               a.ai_explanation, a.detected_at
        FROM anomaly_alerts a
        WHERE a.severity = ?
        ORDER BY a.detected_at DESC
    ''', (severity_filter,)).fetchall()
    if close_conn:
        conn.close()
    return [dict(r) for r in rows]


def load_alert_log():
    if not os.path.exists(ALERT_LOG_PATH):
        return []
    try:
        with open(ALERT_LOG_PATH, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return []


def save_alert_log(entries):
    os.makedirs(os.path.dirname(ALERT_LOG_PATH), exist_ok=True)
    with open(ALERT_LOG_PATH, 'w') as f:
        json.dump(entries, f, indent=2)


def format_alert_entry(alert, notified_at=None):
    return {
        'alert_id': alert['id'],
        'job_run_id': alert['job_run_id'],
        'pipeline_name': alert['pipeline_name'],
        'stage': alert['stage'],
        'anomaly_type': alert['anomaly_type'],
        'severity': alert['severity'],
        'iso_score': alert['iso_score'],
        'detected_at': alert['detected_at'],
        'notified_at': notified_at or datetime.now().isoformat(),
        'ai_explanation': alert.get('ai_explanation') or '',
    }


def send_alerts(severity_filter='high', dry_run=False):
    alerts = get_high_severity_alerts(severity_filter=severity_filter)
    if not alerts:
        return {'new': 0, 'total': len(load_alert_log()), 'alerts': []}

    existing_log = load_alert_log()
    already_notified = {e['alert_id'] for e in existing_log}

    new_entries = []
    for alert in alerts:
        if alert['id'] in already_notified:
            continue
        entry = format_alert_entry(alert)
        new_entries.append(entry)
        print(f"  ALERT [{entry['severity'].upper()}] {entry['pipeline_name']}/{entry['stage']}"
              f" — {entry['anomaly_type']} (score: {entry['iso_score']:.4f})")

    if new_entries and not dry_run:
        existing_log.extend(new_entries)
        save_alert_log(existing_log)

    return {
        'new': len(new_entries),
        'total': len(existing_log) + len(new_entries),
        'alerts': new_entries,
    }


def get_alert_summary():
    log = load_alert_log()
    by_pipeline = {}
    by_severity = {'high': 0, 'medium': 0, 'low': 0}
    for entry in log:
        pipe = entry.get('pipeline_name', 'unknown')
        by_pipeline[pipe] = by_pipeline.get(pipe, 0) + 1
        sev = entry.get('severity', 'low')
        by_severity[sev] = by_severity.get(sev, 0) + 1
    return {
        'total_notified': len(log),
        'by_pipeline': by_pipeline,
        'by_severity': by_severity,
        'last_alert': log[-1]['notified_at'] if log else None,
    }


if __name__ == '__main__':
    print("Checking for high-severity anomalies to route to alert log...")
    result = send_alerts(severity_filter='high')
    print(f"\n  New alerts: {result['new']}")
    print(f"  Total in log: {result['total']}")
    print(f"\nAlert log saved to: {ALERT_LOG_PATH}")
    summary = get_alert_summary()
    print(f"\nAlert Summary: {summary}")
