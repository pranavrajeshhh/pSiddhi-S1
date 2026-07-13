import sqlite3
import random
import os
from datetime import datetime, timedelta

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'etl_metrics.db')

def init_db(conn):
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

PIPELINES = {
    'batch_ingestion_01': [
        {'stage': 'ingestion',      'duration': (10, 20), 'rows': (8000, 12000), 'volume': (40, 60)},
        {'stage': 'transformation', 'duration': (15, 30), 'rows': (7000, 11000), 'volume': (35, 55)},
        {'stage': 'load',           'duration': (5, 12),  'rows': (7000, 11000), 'volume': (30, 50)},
    ],
    'transformation_pipeline_01': [
        {'stage': 'extract',    'duration': (8, 16),  'rows': (5000, 8000), 'volume': (25, 40)},
        {'stage': 'clean',      'duration': (10, 20), 'rows': (4500, 7500), 'volume': (22, 38)},
        {'stage': 'aggregate',  'duration': (12, 25), 'rows': (500, 1500),  'volume': (5, 15)},
    ]
}

def generate_baseline(num_runs=100):
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    init_db(conn)

    base_time = datetime.now() - timedelta(days=7)
    count = 0

    for run_num in range(num_runs):
        run_time = base_time + timedelta(minutes=run_num * 30)
        for pipeline_name, stages in PIPELINES.items():
            for stage_config in stages:
                duration = round(random.uniform(*stage_config['duration']), 2)
                rows_in = random.randint(*stage_config['rows'])
                rows_out = int(rows_in * random.uniform(0.88, 0.98))
                volume = round(random.uniform(*stage_config['volume']), 2)
                start = run_time
                end = run_time + timedelta(seconds=duration)

                conn.execute('''
                    INSERT INTO job_runs (pipeline_name, stage, start_time, end_time,
                        duration_seconds, rows_ingested, rows_transformed, rows_output,
                        data_volume_mb, processing_time_seconds, status, is_anomaly)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                ''', (pipeline_name, stage_config['stage'],
                      start.isoformat(), end.isoformat(),
                      duration, rows_in, rows_out, rows_out,
                      volume, duration, 'success'))
                count += 1

    conn.commit()
    conn.close()
    print(f"Generated {count} baseline records across {num_runs} runs for both pipelines.")

if __name__ == '__main__':
    generate_baseline(100)
