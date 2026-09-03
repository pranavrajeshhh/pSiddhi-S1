from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
import time
import random
import sqlite3
import os
import json

default_args = {
    'owner': 'pranav',
    'retries': 1,
    'retry_delay': timedelta(minutes=2),
}

DB_PATH = '/opt/airflow/data/etl_metrics.db'


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS job_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pipeline_name TEXT,
            stage TEXT,
            start_time TEXT,
            end_time TEXT,
            duration_seconds REAL,
            rows_ingested INTEGER,
            rows_transformed INTEGER,
            rows_output INTEGER,
            data_volume_mb REAL,
            processing_time_seconds REAL,
            status TEXT,
            is_anomaly INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()


def ingest_data(**context):
    init_db()
    start = datetime.now()

    rows = random.randint(8000, 12000)
    volume_mb = round(random.uniform(40.0, 60.0), 2)
    duration = random.uniform(10.0, 20.0)
    time.sleep(min(duration * 0.1, 2))

    end = datetime.now()
    conn = sqlite3.connect(DB_PATH)
    conn.execute('''
        INSERT INTO job_runs (pipeline_name, stage, start_time, end_time,
            duration_seconds, rows_ingested, rows_transformed, rows_output,
            data_volume_mb, processing_time_seconds, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', ('batch_ingestion_01', 'ingestion',
          start.isoformat(), end.isoformat(),
          round(duration, 2), rows, 0, 0,
          volume_mb, round(duration, 2), 'success'))
    conn.commit()
    conn.close()

    context['ti'].xcom_push(key='rows_ingested', value=rows)
    context['ti'].xcom_push(key='volume_mb', value=volume_mb)
    print(f"Ingested {rows} rows | {volume_mb} MB | {round(duration, 2)}s")


def transform_data(**context):
    start = datetime.now()
    rows_in = context['ti'].xcom_pull(key='rows_ingested', task_ids='ingest_data')
    volume_mb = context['ti'].xcom_pull(key='volume_mb', task_ids='ingest_data')

    rows_out = int(rows_in * random.uniform(0.88, 0.96))
    duration = random.uniform(15.0, 30.0)
    time.sleep(min(duration * 0.1, 2))

    end = datetime.now()
    conn = sqlite3.connect(DB_PATH)
    conn.execute('''
        INSERT INTO job_runs (pipeline_name, stage, start_time, end_time,
            duration_seconds, rows_ingested, rows_transformed, rows_output,
            data_volume_mb, processing_time_seconds, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', ('batch_ingestion_01', 'transformation',
          start.isoformat(), end.isoformat(),
          round(duration, 2), rows_in, rows_out, 0,
          round(volume_mb * 0.9, 2), round(duration, 2), 'success'))
    conn.commit()
    conn.close()

    context['ti'].xcom_push(key='rows_transformed', value=rows_out)
    print(f"Transformed {rows_in} -> {rows_out} rows | {round(duration, 2)}s")


def load_data(**context):
    start = datetime.now()
    rows_in = context['ti'].xcom_pull(key='rows_transformed', task_ids='transform_data')

    rows_out = int(rows_in * random.uniform(0.97, 1.0))
    duration = random.uniform(5.0, 12.0)
    time.sleep(min(duration * 0.1, 1))

    end = datetime.now()
    conn = sqlite3.connect(DB_PATH)
    conn.execute('''
        INSERT INTO job_runs (pipeline_name, stage, start_time, end_time,
            duration_seconds, rows_ingested, rows_transformed, rows_output,
            data_volume_mb, processing_time_seconds, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', ('batch_ingestion_01', 'load',
          start.isoformat(), end.isoformat(),
          round(duration, 2), rows_in, rows_in, rows_out,
          round(rows_out * 0.005, 2), round(duration, 2), 'success'))
    conn.commit()
    conn.close()
    print(f"Loaded {rows_out} rows | {round(duration, 2)}s")


def score_runs(**context):
    import sys
    sys.path.insert(0, '/opt/airflow')
    from ml.score_all import run_scoring
    results = run_scoring(db_path=DB_PATH)
    anomalies = [r for r in results if r.get('ml_is_anomaly')]
    print(f"Scored {len(results)} runs — {len(anomalies)} anomalies detected")


def generate_explanations_task(**context):
    import sys
    sys.path.insert(0, '/opt/airflow')
    from ml.explain import generate_explanations, DB_PATH as EXPLAIN_DB
    import ml.explain as explain_mod
    explain_mod.DB_PATH = DB_PATH
    generate_explanations()
    print("AI explanations generated")


def run_alerts(**context):
    import sys
    sys.path.insert(0, '/opt/airflow')
    from ml.alert import send_alerts, DB_PATH as ALERT_DB
    import ml.alert as alert_mod
    alert_mod.DB_PATH = DB_PATH
    result = send_alerts(severity_filter='high', dry_run=False)
    print(f"Alert workflow done — {result['new']} new alerts, {result['total']} total")


with DAG(
    dag_id='batch_ingestion_01',
    default_args=default_args,
    description='Batch ingestion pipeline — S1-D-03',
    schedule_interval=timedelta(minutes=30),
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=['etl', 's1-d-03'],
) as dag:

    t1 = PythonOperator(task_id='ingest_data',              python_callable=ingest_data)
    t2 = PythonOperator(task_id='transform_data',           python_callable=transform_data)
    t3 = PythonOperator(task_id='load_data',                python_callable=load_data)
    t4 = PythonOperator(task_id='score_runs',               python_callable=score_runs)
    t5 = PythonOperator(task_id='generate_explanations',    python_callable=generate_explanations_task)
    t6 = PythonOperator(task_id='run_alerts',               python_callable=run_alerts)

    t1 >> t2 >> t3 >> t4 >> t5 >> t6
