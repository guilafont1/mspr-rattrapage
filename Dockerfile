FROM python:3.12-slim

WORKDIR /app

# Dépendances système pour psycopg2
RUN apt-get update && apt-get install -y --no-install-recommends gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Code backend + schéma SQL. data/ est gitignoré : déjà en base Aiven sur Render.
COPY backend/ ./backend/
COPY db/ ./db/
COPY etl/referentiels.py ./etl/referentiels.py
RUN mkdir -p /app/data

WORKDIR /app/backend
EXPOSE 8000
# Render injecte $PORT ; en local on reste sur 8000
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
