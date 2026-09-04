#!/usr/bin/env bash
set -euo pipefail

host="${DATABASE_HOST:-bh-mysql-prod}"
port="${DATABASE_PORT:-3306}"

if command -v mysqladmin >/dev/null 2>&1; then
  echo "Waiting for MySQL at ${host}:${port}..."
  for _ in $(seq 1 30); do
    if mysqladmin ping -h "$host" -P "$port" --silent 2>/dev/null; then
      echo "MySQL is up."
      break
    fi
    sleep 2
  done
fi

exec "$@"
