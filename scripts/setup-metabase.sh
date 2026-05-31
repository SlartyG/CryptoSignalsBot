#!/bin/sh
set -e
cd "$(dirname "$0")/.."

if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  . ./.env
  set +a
fi

echo "Creating Metabase database if missing..."
docker compose exec -T postgres psql -U app -d cryptobot -tc \
  "SELECT 1 FROM pg_database WHERE datname = 'metabase'" | grep -q 1 \
  || docker compose exec -T postgres psql -U app -d cryptobot -c "CREATE DATABASE metabase;"

echo "Loading analytics views..."
docker compose exec -T postgres psql -U app -d cryptobot < docs/sql/analytics_views.sql

echo "Starting Metabase..."
docker compose --profile analytics up -d metabase

echo "Waiting for Metabase to become ready..."
sleep 15

if [ -n "${METABASE_EMAIL:-}" ] && [ -n "${METABASE_PASSWORD:-}" ]; then
  echo "Creating analytics dashboard..."
  docker compose exec -T \
    -e METABASE_URL=http://metabase:3000 \
    -e METABASE_EMAIL="$METABASE_EMAIL" \
    -e METABASE_PASSWORD="$METABASE_PASSWORD" \
    -e METABASE_DB_PASSWORD="${POSTGRES_PASSWORD:-app}" \
    bot python scripts/metabase_setup_dashboard.py
else
  echo ""
  echo "Dashboard not created: set METABASE_EMAIL and METABASE_PASSWORD in .env, then run:"
  echo "  docker compose exec bot python scripts/metabase_setup_dashboard.py"
fi

echo ""
echo "Done. Open http://YOUR_SERVER_IP:3000 → Dashboards → CryptoSignalsBot Analytics"
