#!/bin/sh
set -e
# API interne (Dash l'appelle en server-side). Port public Render = Dash.
uvicorn main:app --app-dir /app/backend --host 127.0.0.1 --port 8000 &
export API_URL="${API_URL:-http://127.0.0.1:8000}"
cd /app/frontend
exec gunicorn -b "0.0.0.0:${PORT:-8050}" -w "${WEB_CONCURRENCY:-1}" app:server
