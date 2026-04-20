#!/bin/bash
set -e

echo "Running database migrations..."
cd /app/models/db_schemas/connexio/
alembic upgrade head
cd /app
exec "$@"