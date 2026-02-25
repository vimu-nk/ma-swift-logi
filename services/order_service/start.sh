#!/bin/bash
set -e

echo "Running Alembic migrations..."
alembic upgrade head

echo "Starting gunicorn..."
exec gunicorn app.main:app -c gunicorn_conf.py
