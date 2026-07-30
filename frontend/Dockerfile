FROM python:3.12-slim

WORKDIR /app

COPY frontend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY frontend/ ./

EXPOSE 8050
# gunicorn sert l'objet `server` exposé par Dash (app.py)
CMD ["gunicorn", "-b", "0.0.0.0:8050", "-w", "2", "app:server"]
