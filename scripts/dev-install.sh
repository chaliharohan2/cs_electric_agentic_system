#!/usr/bin/env bash
# Idempotent dependency setup for the CS Electric support system.
# Creates a Python 3.11 virtualenv and installs pinned requirements.
set -euo pipefail

cd "$(dirname "$0")/.."

PYTHON="python3.11"
if ! command -v "$PYTHON" >/dev/null 2>&1; then
  echo "python3.11 not found; falling back to python3 ($(python3 --version 2>&1))" >&2
  PYTHON="python3"
fi

if [ ! -d .venv ]; then
  "$PYTHON" -m venv .venv
fi

# shellcheck disable=SC1091
. .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt

echo "install complete: $(python --version) with requirements.txt"
