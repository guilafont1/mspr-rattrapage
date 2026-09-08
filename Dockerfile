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
RUN mkdir -p /app/data

WORKDIR /app/backend
EXPOSE 8000
# Un seul process : FastAPI + Dash (monté sur /). Render injecte $PORT.
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
