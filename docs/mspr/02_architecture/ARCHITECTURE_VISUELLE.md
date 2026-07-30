# Architecture 3 couches (compétence C2) — vue synthétique

```mermaid
flowchart TB
  subgraph L1["Couche 1 — Collecte"]
    A[data.gouv / INSEE API]
    B[Python ThreadPoolExecutor]
    C[data/raw + MinIO S3]
  end
  subgraph L2["Couche 2 — Stockage & modèle"]
    D[Bronze CSV contrats]
    E[Silver DQM + panel]
    F[Gold étoile SQL<br/>SQLite / Postgres]
  end
  subgraph L3["Couche 3 — Restitution"]
    G[FastAPI]
    H[Dash Plotly]
    I[Metabase]
    J[ML Gradient Boosting]
  end
  A --> B --> C --> D --> E --> F
  F --> G --> H
  F --> I
  F --> J
```

| Couche | Techno POC | Preuve dans le repo |
|---|---|---|
| Collecte | Python, urllib, ThreadPoolExecutor | `etl/01_download.py` |
| Stockage | Pandas, SQLite, Postgres, MinIO | `etl/02_transform.py`, `etl/03_sync_datalake.py` |
| Restitution | FastAPI, Dash, Metabase, scikit-learn | `backend/`, `frontend/`, `docker-compose.yml` |
