#!/usr/bin/env bash
# One-time setup of Helply on THIS computer (macOS / Linux). Run once per computer using this drive.
set -euo pipefail
cd "$(dirname "$0")"
VENV=".venv-$(hostname -s)"

PY=$(command -v python3 || command -v python || true)
if [ -z "$PY" ]; then
  echo "Python was not found. Install Python 3.12 or newer from https://www.python.org/downloads/"; exit 1
fi
"$PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)' || {
  echo "Helply needs Python 3.12 or newer. Found: $("$PY" --version)"; exit 1; }

[ -x "$VENV/bin/python" ] || "$PY" -m venv "$VENV"
"$VENV/bin/python" -m pip install --quiet --upgrade pip
"$VENV/bin/python" -m pip install --quiet -r requirements.txt
source tools/start-db.sh
"$VENV/bin/python" manage.py migrate --verbosity 0
# --if-empty: running setup again on another computer that shares this drive must never wipe existing data.
"$VENV/bin/python" manage.py seed_demo --if-empty
echo
echo "Setup complete. Run ./start-demo.sh to start Helply."
