#!/bin/sh
set -e
cd "$(dirname "$0")/.."

echo "Creating Metabase database if missing..."
docker compose exec -T postgres psql -U app -d cryptobot -tc \
  "SELECT 1 FROM pg_database WHERE datname = 'metabase'" | grep -q 1 \
  || docker compose exec -T postgres psql -U app -d cryptobot -c "CREATE DATABASE metabase;"

echo "Loading analytics views..."
docker compose exec -T postgres psql -U app -d cryptobot < docs/sql/analytics_views.sql

echo "Starting Metabase..."
docker compose --profile analytics up -d metabase

echo "Done. Open http://YOUR_SERVER_IP:3000 (or SSH tunnel to localhost:3000)"
