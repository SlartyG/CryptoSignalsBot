#!/bin/sh
set -e

# Fallback для Docker Compose (хост postgres, не localhost)
if [ -z "$DATABASE_URL" ]; then
  export DATABASE_URL="postgresql+asyncpg://app:${POSTGRES_PASSWORD:-app}@postgres:5432/cryptobot"
fi

echo "Running database migrations..."
echo "DATABASE_URL host: $(echo "$DATABASE_URL" | sed -E 's|.*@([^:/]+).*|\1|')"
alembic upgrade head
echo "Starting: $*"
exec "$@"
