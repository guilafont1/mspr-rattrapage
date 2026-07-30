FROM python:3.12-slim

WORKDIR /app

# Dépendances système pour psycopg2
RUN apt-get update && apt-get install -y --no-install-recommends gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Code backend + données GOLD/SILVER + schéma SQL (Aiven / init_remote)
COPY backend/ ./backend/
COPY data/ ./data/
COPY db/ ./db/
COPY etl/referentiels.py ./etl/referentiels.py

WORKDIR /app/backend
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
