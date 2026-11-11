#!/usr/bin/env bash
# One-time setup for the Codespace. Run automatically by devcontainer.json.
set -e

# .env is not in git. Create it from the template; add your keys afterwards
# (or set GROQ_API_KEY / GEMINI_API_KEY as Codespaces secrets).
if [ ! -f .env ]; then
  cp .env.example .env
  echo "Created .env from .env.example - add GROQ_API_KEY and GEMINI_API_KEY."
fi
# Codespaces secrets, if set, override the template values.
[ -n "$GROQ_API_KEY" ]   && sed -i "s|^GROQ_API_KEY=.*|GROQ_API_KEY=$GROQ_API_KEY|" .env
[ -n "$GEMINI_API_KEY" ] && sed -i "s|^GEMINI_API_KEY=.*|GEMINI_API_KEY=$GEMINI_API_KEY|" .env

# Python env for ML scripts, tests and MLflow (Airflow runs inside Docker).
python -m venv venv
./venv/bin/pip install --quiet --upgrade pip
./venv/bin/pip install --quiet pandas scikit-learn pyod numpy joblib sqlalchemy \
  prometheus-client flask mlflow groq google-genai requests pytest pytest-cov coverage

# Dashboard dependencies.
(cd dashboard && npm install --no-audit --no-fund)

echo "Setup done. Start the demo with: bash .devcontainer/start-demo.sh"
