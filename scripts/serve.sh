#!/usr/bin/env bash
# Run the API server (foreground). Intended for a persistent terminal.
set -euo pipefail

cd "$(dirname "$0")/.."

# shellcheck disable=SC1091
. .venv/bin/activate

HOST="${FLASK_RUN_HOST:-0.0.0.0}"
PORT="${FLASK_RUN_PORT:-5000}"
WORKERS="${WEB_CONCURRENCY:-2}"

exec gunicorn -w "$WORKERS" -b "${HOST}:${PORT}" wsgi:app \
  --access-logfile - --error-logfile -
