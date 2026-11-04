#!/usr/bin/env bash
# RNU Thesis Copilot — first run creates a virtual environment and installs dependencies.
set -e
cd "$(dirname "$0")"
PY=${PYTHON:-python3}
if [ ! -d .venv ]; then
  echo "Creating virtual environment…"
  $PY -m venv .venv
  ./.venv/bin/pip install --upgrade pip
  ./.venv/bin/pip install -r requirements.txt
fi
exec ./.venv/bin/python -m app "$@"
