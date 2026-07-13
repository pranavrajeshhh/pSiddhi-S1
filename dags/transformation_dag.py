from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
import time
import random
import sqlite3

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


def extract_stage(**context):
    init_db()
    start = datetime.now()

    rows = random.randint(5000, 8000)
    volume_mb = round(random.uniform(25.0, 40.0), 2)
    duration = random.uniform(8.0, 16.0)
    time.sleep(min(duration * 0.1, 2))

    end = datetime.now()
    conn = sqlite3.connect(DB_PATH)
    conn.execute('''
        INSERT INTO job_runs (pipeline_name, stage, start_time, end_time,
            duration_seconds, rows_ingested, rows_transformed, rows_output,
            data_volume_mb, processing_time_seconds, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', ('transformation_pipeline_01', 'extract',
          start.isoformat(), end.isoformat(),
          round(duration, 2), rows, 0, 0,
          volume_mb, round(duration, 2), 'success'))
    conn.commit()
    conn.close()

    context['ti'].xcom_push(key='rows_extracted', value=rows)
    context['ti'].xcom_push(key='volume_mb', value=volume_mb)
    print(f"Extracted {rows} rows | {volume_mb} MB | {round(duration, 2)}s")


def clean_stage(**context):
    start = datetime.now()
    rows_in = context['ti'].xcom_pull(key='rows_extracted', task_ids='extract_stage')

    rows_clean = int(rows_in * random.uniform(0.90, 0.98))
    duration = random.uniform(10.0, 20.0)
    time.sleep(min(duration * 0.1, 2))

    end = datetime.now()
    conn = sqlite3.connect(DB_PATH)
    conn.execute('''
        INSERT INTO job_runs (pipeline_name, stage, start_time, end_time,
            duration_seconds, rows_ingested, rows_transformed, rows_output,
            data_volume_mb, processing_time_seconds, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', ('transformation_pipeline_01', 'clean',
          start.isoformat(), end.isoformat(),
          round(duration, 2), rows_in, rows_clean, 0,
          round(rows_clean * 0.006, 2), round(duration, 2), 'success'))
    conn.commit()
    conn.close()

    context['ti'].xcom_push(key='rows_clean', value=rows_clean)
    print(f"Cleaned {rows_in} -> {rows_clean} rows | {round(duration, 2)}s")


def aggregate_stage(**context):
    start = datetime.now()
    rows_in = context['ti'].xcom_pull(key='rows_clean', task_ids='clean_stage')

    rows_out = int(rows_in * random.uniform(0.10, 0.20))
    duration = random.uniform(12.0, 25.0)
    time.sleep(min(duration * 0.1, 2))

    end = datetime.now()
    conn = sqlite3.connect(DB_PATH)
    conn.execute('''
        INSERT INTO job_runs (pipeline_name, stage, start_time, end_time,
            duration_seconds, rows_ingested, rows_transformed, rows_output,
            data_volume_mb, processing_time_seconds, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', ('transformation_pipeline_01', 'aggregate',
          start.isoformat(), end.isoformat(),
          round(duration, 2), rows_in, rows_in, rows_out,
          round(rows_out * 0.004, 2), round(duration, 2), 'success'))
    conn.commit()
    conn.close()
    print(f"Aggregated {rows_in} -> {rows_out} rows | {round(duration, 2)}s")


with DAG(
    dag_id='transformation_pipeline_01',
    default_args=default_args,
    description='Transformation pipeline — S1-D-03',
    schedule_interval=timedelta(minutes=45),
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=['etl', 's1-d-03'],
) as dag:

    t1 = PythonOperator(task_id='extract_stage', python_callable=extract_stage)
    t2 = PythonOperator(task_id='clean_stage', python_callable=clean_stage)
    t3 = PythonOperator(task_id='aggregate_stage', python_callable=aggregate_stage)

    t1 >> t2 >> t3
