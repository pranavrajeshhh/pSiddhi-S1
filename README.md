# S1-D-03 — ML Anomaly Detection for ETL Pipelines

**pSiddhi Semester 1 | EMP-2025-P499 · Pranav Rajesh | Track: Data**

Detects anomalies in ETL pipeline runs using Isolation Forest and LOF, generates AI-written explanations via Groq/Gemini, and exposes everything through a React dashboard.

---

## System Architecture

```
Airflow (:8080)
  └─ batch_ingestion_01 DAG        ─┐
  └─ transformation_pipeline_01 DAG ┘
          │ writes metrics
          ▼
    SQLite (data/etl_metrics.db)
          │
          ├─► Prometheus Exporter (:8000) ──► Prometheus (:9090) ──► Grafana (:3000)
          │
          └─► ML Models (ml/)
                ├─ IsolationForest  (models/*_iso.pkl)
                ├─ LOF             (models/*_lof.pkl)
                └─ AI Explanation  (Groq → Gemini → template)
                        │
                        ▼
              React Dashboard (:5173)
              [Overview | Pipeline Runs | Anomaly Alerts | Model Scores | Grafana | Airflow | Test Results]
```

---

## Prerequisites

- Python 3.11+ (WSL2/Ubuntu recommended)
- Docker Engine (not Docker Desktop — company policy)
- Node.js 18+

---

## Setup

### 1. Clone and configure environment

```bash
git clone https://gitlab.com/pranavrajeshhh/psiddhi-s1.git
cd psiddhi-s1
cp .env.example .env
# Edit .env and add your GROQ_API_KEY and GEMINI_API_KEY
```

### 2. Start the observability stack (Docker)

```bash
docker-compose up -d
# Starts: Airflow (:8080), Prometheus (:9090), Grafana (:3000), Metrics Exporter (:8000)
```

### 3. Set up Python environment (WSL2)

```bash
sudo apt install python3-full python3-venv -y
python3 -m venv venv
source venv/bin/activate
pip install pandas scikit-learn pyod numpy joblib sqlalchemy prometheus-client mlflow groq google-generativeai pytest pytest-cov
```

### 4. Generate baseline data and train models

```bash
source venv/bin/activate
python ml/generate_baseline.py   # generates 633 historical job runs
python ml/train.py               # trains IF + LOF per pipeline, logs to MLflow
```

### 5. Start the React dashboard

```bash
cd dashboard
npm install
npm run dev
# Opens at http://localhost:5173
# API server runs at http://localhost:3001
```

---

## ML Models

| Model | Library | Purpose |
|---|---|---|
| Isolation Forest | scikit-learn | Assigns an anomaly score; more negative = more isolated from normal cluster |
| LOF | PyOD | Compares local density; 1 = anomaly, 0 = normal |

A run is flagged if **either** model says anomaly (OR logic). Severity is derived from the IF score: `< −0.3` = high, `< −0.1` = medium, else low.

---

## Running Tests

```bash
source venv/bin/activate       # or use Windows venv: venv\Scripts\activate
pytest tests/ -v               # run all 90 tests
pytest tests/ --cov=ml --cov-report=term-missing   # with coverage
```

Test categories:

| File | Category | Tests |
|---|---|---|
| `test_smoke.py` | Smoke / infra checks | 17 |
| `test_metric_ingestion.py` | Metric ingestion units | 6 |
| `test_model_accuracy.py` | Model accuracy + drift | 5 |
| `test_false_positive.py` | False positive rate | 3 |
| `test_integration_e2e.py` | Integration + E2E | 5 |
| `test_prompt_quality.py` | AI explanation quality | 5 |
| `test_ml_units.py` | ML function unit tests | 49 |

---

## MLflow Experiment Tracking

```bash
source venv/bin/activate
mlflow ui --backend-store-uri sqlite:///data/mlflow.db --port 5000
# Open http://localhost:5000
```

All training runs are logged under the experiment `etl_anomaly_detection`.

---

## Project Structure

```
pSiddhi/
├── dags/               Airflow DAG definitions
├── ml/                 ML training, detection, scoring, explanation
├── exporter/           Prometheus metrics exporter
├── tests/              Pytest test suite (62 tests)
├── dashboard/          React frontend + Express API server
│   ├── src/            React components (7 tabs)
│   └── server.js       Express API (/api/stats, /api/scores, ...)
├── grafana/            Grafana provisioning (dashboards + datasource)
├── prometheus/         Prometheus scrape config
├── models/             Serialised .pkl model files
├── data/               SQLite databases (etl_metrics.db, mlflow.db)
├── docker-compose.yml  Orchestrates Airflow, Prometheus, Grafana, Exporter
└── .env.example        API key template (copy to .env)
```

---

## Deliverables Status (Phase 1 — Week 10)

| D-ID | Deliverable | Status |
|---|---|---|
| D-01 | 2 Airflow DAGs in Docker, Prometheus metrics | ✓ Done |
| D-02 | Prometheus exporter running, 633 baseline records | ✓ Done |
| D-03 | Isolation Forest trained and tracked in MLflow | ✓ Done |
| D-04 | LOF trained, dual-model scoring, severity | ✓ Done |
| D-05 | AI explanation engine (Groq + Gemini fallback) | ✓ Done |
| D-06 | React dashboard (7 tabs), 90 tests passing, 48% ml/ coverage | ✓ Done |
