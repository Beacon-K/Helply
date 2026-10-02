#!/usr/bin/env bash
# Helply demo launcher for macOS / Linux: refreshes demo data (deletes ALL tickets), starts the server.
set -euo pipefail
cd "$(dirname "$0")"
VENV=".venv-$(hostname -s)"
[ -x "$VENV/bin/python" ] || { echo "Run ./setup.sh once on this computer first."; exit 1; }
source tools/start-db.sh
"$VENV/bin/python" manage.py migrate --verbosity 0
"$VENV/bin/python" manage.py seed_demo --reset
echo "Starting Helply at http://127.0.0.1:8000  (Ctrl+C to stop)"
( sleep 2; command -v open >/dev/null && open http://127.0.0.1:8000 || xdg-open http://127.0.0.1:8000 ) >/dev/null 2>&1 &
"$VENV/bin/python" manage.py runserver 127.0.0.1:8000
