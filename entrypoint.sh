#!/bin/sh
set -e

# DB 대기 로직
echo "Waiting for Postgres at $DB_HOST:$DB_PORT..."
until pg_isready -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER"; do
  sleep 2
done

# 💡 핵심: migrations 폴더가 있을 때만 upgrade 실행
if [ -d "/app/migrations" ]; then
    echo "Found migrations folder, applying upgrade..."
    flask db upgrade
else
    echo "Migrations folder not found. Skipping upgrade."
fi

# 원래 실행하려던 CMD(Gunicorn) 실행
exec "$@"