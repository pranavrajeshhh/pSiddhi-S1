from prometheus_client import start_http_server, Gauge, Counter
import sqlite3
import time
import os

DB_PATH = '/data/etl_metrics.db'

etl_duration = Gauge('etl_job_duration_seconds', 'Job duration in seconds',
                     ['pipeline_name', 'stage'])
etl_rows_ingested = Gauge('etl_rows_ingested_total', 'Total rows ingested',
                          ['pipeline_name', 'stage'])
etl_rows_output = Gauge('etl_rows_output_total', 'Total rows output',
                        ['pipeline_name', 'stage'])
etl_volume_mb = Gauge('etl_data_volume_mb', 'Data volume processed in MB',
                      ['pipeline_name', 'stage'])
etl_processing_time = Gauge('etl_processing_time_seconds', 'Processing time in seconds',
                            ['pipeline_name', 'stage'])
etl_anomaly_flag = Gauge('etl_anomaly_detected', 'Anomaly detected flag (1=anomaly)',
                         ['pipeline_name', 'stage'])
etl_runs_total = Counter('etl_runs_total', 'Total pipeline runs',
                         ['pipeline_name', 'stage'])


def collect_metrics():
    if not os.path.exists(DB_PATH):
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute('''
        SELECT pipeline_name, stage, duration_seconds, rows_ingested,
               rows_output, data_volume_mb, processing_time_seconds, is_anomaly
        FROM job_runs
        WHERE id IN (
            SELECT MAX(id) FROM job_runs GROUP BY pipeline_name, stage
        )
    ''')

    for row in cursor.fetchall():
        pipeline, stage, duration, rows_in, rows_out, volume, proc_time, anomaly = row
        labels = {'pipeline_name': pipeline, 'stage': stage}

        etl_duration.labels(**labels).set(duration or 0)
        etl_rows_ingested.labels(**labels).set(rows_in or 0)
        etl_rows_output.labels(**labels).set(rows_out or 0)
        etl_volume_mb.labels(**labels).set(volume or 0)
        etl_processing_time.labels(**labels).set(proc_time or 0)
        etl_anomaly_flag.labels(**labels).set(anomaly or 0)

    conn.close()


if __name__ == '__main__':
    print("Starting ETL Metrics Exporter on port 8000...")
    start_http_server(8000)
    while True:
        collect_metrics()
        time.sleep(15)
