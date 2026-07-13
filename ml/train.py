import sqlite3
import pandas as pd
import numpy as np
import os
import pickle
import mlflow
import mlflow.sklearn
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from pyod.models.lof import LOF

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'etl_metrics.db')
MODELS_DIR = os.path.join(os.path.dirname(__file__), '..', 'models')
MLFLOW_DB = os.path.join(os.path.dirname(__file__), '..', 'data', 'mlflow.db')

os.makedirs(MODELS_DIR, exist_ok=True)
mlflow.set_tracking_uri(f"sqlite:///{os.path.abspath(MLFLOW_DB)}")

FEATURES = ['duration_seconds', 'rows_ingested', 'rows_output', 'data_volume_mb', 'processing_time_seconds']

def load_data(pipeline_name):
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query(f"""
        SELECT {', '.join(FEATURES)}
        FROM job_runs
        WHERE pipeline_name = ? AND is_anomaly = 0 AND status = 'success'
        ORDER BY id
    """, conn, params=(pipeline_name,))
    conn.close()
    return df

def inject_anomalies(df, n=10):
    anomalies = df.copy().sample(n=min(n, len(df)), random_state=42)
    anomalies['duration_seconds'] = anomalies['duration_seconds'] * random.uniform(4, 6)
    anomalies['rows_output'] = (anomalies['rows_output'] * random.uniform(0.1, 0.3)).astype(int)
    return anomalies

def train_pipeline(pipeline_name):
    print(f"\nTraining models for: {pipeline_name}")
    df = load_data(pipeline_name)

    if len(df) < 10:
        print(f"Not enough data for {pipeline_name} — need at least 10 records.")
        return

    scaler = StandardScaler()
    X = scaler.fit_transform(df[FEATURES].fillna(0))

    with mlflow.start_run(run_name=f"{pipeline_name}_isolation_forest"):
        iso = IsolationForest(contamination=0.05, n_estimators=100, random_state=42)
        iso.fit(X)
        scores = iso.decision_function(X)
        mlflow.log_param("model", "IsolationForest")
        mlflow.log_param("pipeline", pipeline_name)
        mlflow.log_param("contamination", 0.05)
        mlflow.log_param("n_estimators", 100)
        mlflow.log_param("training_samples", len(df))
        mlflow.log_metric("mean_anomaly_score", float(np.mean(scores)))
        mlflow.sklearn.log_model(iso, "isolation_forest_model")
        print(f"  Isolation Forest trained — {len(df)} samples, mean score: {np.mean(scores):.4f}")

    with mlflow.start_run(run_name=f"{pipeline_name}_lof"):
        lof = LOF(n_neighbors=20, contamination=0.05)
        lof.fit(X)
        lof_scores = lof.decision_scores_
        mlflow.log_param("model", "LOF")
        mlflow.log_param("pipeline", pipeline_name)
        mlflow.log_param("n_neighbors", 20)
        mlflow.log_param("contamination", 0.05)
        mlflow.log_param("training_samples", len(df))
        mlflow.log_metric("mean_lof_score", float(np.mean(lof_scores)))
        print(f"  LOF trained — {len(df)} samples, mean score: {np.mean(lof_scores):.4f}")

    safe_name = pipeline_name.replace(' ', '_')
    with open(os.path.join(MODELS_DIR, f'{safe_name}_scaler.pkl'), 'wb') as f:
        pickle.dump(scaler, f)
    with open(os.path.join(MODELS_DIR, f'{safe_name}_iso.pkl'), 'wb') as f:
        pickle.dump(iso, f)
    with open(os.path.join(MODELS_DIR, f'{safe_name}_lof.pkl'), 'wb') as f:
        pickle.dump(lof, f)

    print(f"  Models saved to {MODELS_DIR}")

if __name__ == '__main__':
    import random
    mlflow.set_experiment("etl_anomaly_detection")
    for pipeline in ['batch_ingestion_01', 'transformation_pipeline_01']:
        train_pipeline(pipeline)
    print("\nAll models trained and saved successfully.")
