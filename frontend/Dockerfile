FROM python:3.12-slim

WORKDIR /app

COPY frontend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY frontend/ ./

EXPOSE 8050
# gunicorn sert l'objet `server` exposé par Dash (app.py)
# Render injecte $PORT ; WEB_CONCURRENCY=1 recommandé sur le plan free
CMD ["sh", "-c", "gunicorn -b 0.0.0.0:${PORT:-8050} -w ${WEB_CONCURRENCY:-2} app:server"]
