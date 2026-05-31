#!/bin/sh
set -e

# Fallback для Docker Compose (хост postgres, не localhost)
if [ -z "$DATABASE_URL" ]; then
  export DATABASE_URL="postgresql+asyncpg://app:${POSTGRES_PASSWORD:-app}@postgres:5432/cryptobot"
fi

run_migrations() {
  echo "Running database migrations..."
  echo "DATABASE_URL host: $(echo "$DATABASE_URL" | sed -E 's|.*@([^:/]+).*|\1|')"
  attempts=5
  while [ "$attempts" -gt 0 ]; do
    if alembic upgrade head; then
      return 0
    fi
    attempts=$((attempts - 1))
    if [ "$attempts" -eq 0 ]; then
      echo "Migration failed after retries"
      return 1
    fi
    echo "Migration busy or failed, retry in 2s... ($attempts left)"
    sleep 2
  done
}

if [ "${SKIP_MIGRATIONS:-0}" != "1" ]; then
  run_migrations
else
  echo "Skipping migrations (SKIP_MIGRATIONS=1)"
fi

echo "Starting: $*"
exec "$@"
