#!/usr/bin/env bash
# Start the full stack in the Codespace.
set -e
cd "$(dirname "$0")/.."

# Airflow runs as a non-root user inside Docker and must be able to write here.
mkdir -p logs
sudo chmod -R a+rwX logs data models mlruns 2>/dev/null || chmod -R a+rwX logs data models mlruns

echo "Starting Docker services (Airflow, Postgres, Prometheus, Grafana, exporter)..."
docker compose up -d --build

echo "Waiting for Airflow to answer on :8080 (first start can take a few minutes)..."
for i in $(seq 1 60); do
  curl -fs http://localhost:8080/health >/dev/null 2>&1 && break
  sleep 5
done

echo "Starting the React dashboard (:5173) and API (:3001)..."
cd dashboard && npm run dev
