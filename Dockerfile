FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt /tmp/backend-req.txt
COPY frontend/requirements.txt /tmp/frontend-req.txt
RUN pip install --no-cache-dir -r /tmp/backend-req.txt -r /tmp/frontend-req.txt

COPY backend/ ./backend/
COPY frontend/ ./frontend/
COPY db/ ./db/
COPY etl/referentiels.py ./etl/referentiels.py
COPY start.sh ./start.sh
RUN mkdir -p /app/data && chmod +x /app/start.sh

EXPOSE 8000
# Render : Dash sur $PORT, API FastAPI sur 127.0.0.1:8000
CMD ["/app/start.sh"]
