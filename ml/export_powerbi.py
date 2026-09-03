"""
Exports SQLite data to CSV files ready for Power BI import.
Produces 4 views matching the Power BI dashboard design:
  1. anomaly_summary.csv    — one row per anomaly alert
  2. pipeline_health.csv    — daily health score per pipeline
  3. severity_trends.csv    — weekly severity counts
  4. weekly_report.csv      — KPI summary by week
"""
import sqlite3
import pandas as pd
import os
from datetime import datetime, timedelta

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'etl_metrics.db')
EXPORT_DIR = os.path.join(os.path.dirname(__file__), '..', 'data', 'powerbi_exports')


def get_conn():
    return sqlite3.connect(DB_PATH)


def export_anomaly_summary():
    conn = get_conn()
    df = pd.read_sql_query('''
        SELECT
            a.id,
            a.pipeline_name,
            a.stage,
            a.anomaly_type,
            a.severity,
            ROUND(a.iso_score, 4)       AS iso_score,
            a.detected_at,
            a.ai_explanation,
            j.duration_seconds,
            j.rows_ingested,
            j.rows_output,
            j.data_volume_mb,
            j.processing_time_seconds
        FROM anomaly_alerts a
        LEFT JOIN job_runs j ON a.job_run_id = j.id
        ORDER BY a.detected_at DESC
    ''', conn)
    conn.close()
    path = os.path.join(EXPORT_DIR, 'anomaly_summary.csv')
    df.to_csv(path, index=False)
    print(f"  anomaly_summary.csv — {len(df)} rows")
    return df


def export_pipeline_health():
    conn = get_conn()
    df = pd.read_sql_query('''
        SELECT
            pipeline_name,
            DATE(start_time)              AS run_date,
            COUNT(*)                      AS total_runs,
            SUM(is_anomaly)               AS anomaly_count,
            ROUND(AVG(duration_seconds), 2) AS avg_duration,
            ROUND(AVG(rows_output * 1.0 / NULLIF(rows_ingested, 0)), 4) AS avg_yield_rate,
            ROUND(AVG(data_volume_mb), 2) AS avg_volume_mb,
            SUM(CASE WHEN status='success' THEN 1 ELSE 0 END) AS success_count
        FROM job_runs
        GROUP BY pipeline_name, DATE(start_time)
        ORDER BY run_date DESC
    ''', conn)
    conn.close()

    df['anomaly_rate'] = (df['anomaly_count'] / df['total_runs']).round(4)
    df['health_score'] = ((1 - df['anomaly_rate']) * 100).round(1)

    path = os.path.join(EXPORT_DIR, 'pipeline_health.csv')
    df.to_csv(path, index=False)
    print(f"  pipeline_health.csv — {len(df)} rows")
    return df


def export_severity_trends():
    conn = get_conn()
    df = pd.read_sql_query('''
        SELECT
            pipeline_name,
            strftime('%Y-W%W', detected_at) AS week,
            severity,
            COUNT(*)                         AS count
        FROM anomaly_alerts
        GROUP BY pipeline_name, week, severity
        ORDER BY week DESC
    ''', conn)
    conn.close()
    path = os.path.join(EXPORT_DIR, 'severity_trends.csv')
    df.to_csv(path, index=False)
    print(f"  severity_trends.csv — {len(df)} rows")
    return df


def export_weekly_report():
    conn = get_conn()
    runs_df = pd.read_sql_query('''
        SELECT
            strftime('%Y-W%W', start_time) AS week,
            pipeline_name,
            COUNT(*)                        AS total_runs,
            SUM(is_anomaly)                 AS anomalies,
            ROUND(AVG(duration_seconds), 2) AS avg_duration,
            ROUND(AVG(rows_output), 0)      AS avg_rows_out,
            ROUND(AVG(data_volume_mb), 2)   AS avg_volume
        FROM job_runs
        GROUP BY week, pipeline_name
        ORDER BY week DESC
    ''', conn)

    high_df = pd.read_sql_query('''
        SELECT
            strftime('%Y-W%W', detected_at) AS week,
            pipeline_name,
            COUNT(*) AS high_severity_count
        FROM anomaly_alerts
        WHERE severity = 'high'
        GROUP BY week, pipeline_name
    ''', conn)
    conn.close()

    df = runs_df.merge(high_df, on=['week', 'pipeline_name'], how='left')
    df['high_severity_count'] = df['high_severity_count'].fillna(0).astype(int)
    df['anomaly_rate_pct'] = ((df['anomalies'] / df['total_runs']) * 100).round(1)

    path = os.path.join(EXPORT_DIR, 'weekly_report.csv')
    df.to_csv(path, index=False)
    print(f"  weekly_report.csv  — {len(df)} rows")
    return df


def run_export():
    os.makedirs(EXPORT_DIR, exist_ok=True)
    print(f"Exporting Power BI data to: {EXPORT_DIR}")
    export_anomaly_summary()
    export_pipeline_health()
    export_severity_trends()
    export_weekly_report()
    print("\nAll 4 Power BI export files ready.")
    print("  Import into Power BI Desktop: Get Data → Text/CSV → select each file.")


if __name__ == '__main__':
    run_export()
