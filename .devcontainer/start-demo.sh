#!/usr/bin/env bash
# Start the full stack in the Codespace.
set -e
cd "$(dirname "$0")/.."

# Airflow runs as a non-root user inside Docker and must be able to write here.
mkdir -p logs
sudo chmod -R a+rwX logs data models mlruns 2>/dev/null || chmod -R a+rwX logs data models mlruns

# In Codespaces, services must advertise their public https URLs (not localhost),
# otherwise Airflow/Grafana redirect to localhost after login.
if [ -n "$CODESPACE_NAME" ]; then
  D="${GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN:-app.github.dev}"
  export AIRFLOW_BASE_URL="https://${CODESPACE_NAME}-8080.${D}"
  export GRAFANA_ROOT_URL="https://${CODESPACE_NAME}-3000.${D}"
  export COOKIE_SAMESITE=None GF_COOKIE_SAMESITE=none COOKIE_SECURE=True
fi

echo "Starting Docker services (Airflow, Postgres, Prometheus, Grafana, exporter)..."
docker compose up -d --build

echo "Waiting for Airflow to answer on :8080 (first start can take a few minutes)..."
for i in $(seq 1 60); do
  curl -fs http://localhost:8080/health >/dev/null 2>&1 && break
  sleep 5
done

echo "Starting the React dashboard (:5173) and API (:3001)..."
cd dashboard && npm run dev
