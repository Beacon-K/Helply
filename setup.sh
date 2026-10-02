#!/usr/bin/env bash
# One-time setup for Helply on macOS / Linux. Requires Python 3.12+ and an internet connection.
set -euo pipefail
cd "$(dirname "$0")"

PY=$(command -v python3 || command -v python || true)
if [ -z "$PY" ]; then
  echo "Python was not found. Install Python 3.12 or newer from https://www.python.org/downloads/"; exit 1
fi
"$PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)' || {
  echo "Helply needs Python 3.12 or newer. Found: $("$PY" --version)"; exit 1; }

[ -x .venv/bin/python ] || "$PY" -m venv .venv
.venv/bin/python -m pip install --quiet --upgrade pip
.venv/bin/python -m pip install --quiet -r requirements.txt
.venv/bin/python manage.py migrate --verbosity 0
.venv/bin/python manage.py seed_demo --reset
echo
echo "Setup complete. Run ./start-demo.sh to start Helply."
