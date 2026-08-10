#!/usr/bin/env bash
# Per-boot reconciliation: bring up PostgreSQL, ensure the role/databases
# exist, and create the schema. Safe to run repeatedly.
set -euo pipefail

cd "$(dirname "$0")/.."

DB_USER="${DB_USER:-cselectric}"
DB_PASSWORD="${DB_PASSWORD:-cselectric}"
APP_DB="${APP_DB:-cs_electric}"
TEST_DB="${TEST_DB:-cs_electric_test}"

# Run a command as the postgres superuser, using sudo when we are not root.
pg_super() {
  if [ "$(id -u)" -eq 0 ]; then
    su -s /bin/bash postgres -c "$*"
  else
    sudo -u postgres bash -c "$*"
  fi
}

as_root() {
  if [ "$(id -u)" -eq 0 ]; then
    bash -c "$*"
  else
    sudo bash -c "$*"
  fi
}

PG_VER="$(ls /usr/lib/postgresql 2>/dev/null | sort -V | tail -1)"
if [ -z "$PG_VER" ]; then
  echo "PostgreSQL is not installed" >&2
  exit 1
fi

# Start the default cluster if it is not already online.
if ! pg_lsclusters -h 2>/dev/null | awk '{print $4}' | grep -q online; then
  as_root "pg_ctlcluster ${PG_VER} main start" || true
fi

# Wait for the server to accept connections.
for _ in $(seq 1 30); do
  if pg_super "pg_isready -q"; then
    break
  fi
  sleep 1
done

# Ensure the application role exists.
if ! pg_super "psql -tAc \"SELECT 1 FROM pg_roles WHERE rolname='${DB_USER}'\"" | grep -q 1; then
  pg_super "psql -c \"CREATE ROLE ${DB_USER} LOGIN PASSWORD '${DB_PASSWORD}';\""
fi

# Ensure the application and test databases exist.
for dbname in "$APP_DB" "$TEST_DB"; do
  if ! pg_super "psql -tAc \"SELECT 1 FROM pg_database WHERE datname='${dbname}'\"" | grep -q 1; then
    pg_super "createdb -O ${DB_USER} ${dbname}"
  fi
done

# Create tables (idempotent).
# shellcheck disable=SC1091
. .venv/bin/activate
python -m scripts.init_db

echo "start complete: PostgreSQL ${PG_VER} online, schema ready"
