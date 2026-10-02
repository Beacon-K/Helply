# Sourced by setup.sh / start-demo.sh: use PostgreSQL (Docker) if configured and available, else SQLite.
unset HELPLY_USE_SQLITE
if grep -q '^POSTGRES_DB=' .env 2>/dev/null; then
  if command -v docker >/dev/null && docker info >/dev/null 2>&1 && docker compose up -d --wait db; then
    echo "PostgreSQL is running."
  else
    echo "NOTE: PostgreSQL is configured but Docker is not running - using the SQLite database on this drive."
    export HELPLY_USE_SQLITE=1
  fi
else
  export HELPLY_USE_SQLITE=1
fi
