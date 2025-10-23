#!/bin/sh
set -e

# wait for db
if [ -n "$DATABASE_URL" ]; then
  echo "Waiting for database..."
  # Extract host and port from DATABASE_URL (supporting postgres+asyncpg)
  host=$(echo $DATABASE_URL | sed -n 's/.*@\([^:]*\):\([0-9]*\)\/.*$/\1/p')
  port=$(echo $DATABASE_URL | sed -n 's/.*@[^:]*:\([0-9]*\)\/.*$/\1/p')
  if [ -z "$host" ]; then
    host=postgres
  fi
  if [ -z "$port" ]; then
    port=5432
  fi
  until nc -z $host $port; do
    echo "Waiting for $host:$port..."
    sleep 1
  done
fi

# run alembic upgrade
alembic upgrade head || true

# start bot
python main.py
