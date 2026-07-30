# Diagrammes de flux — Electio-Analytics

## C1 — Flux ETL / médailon (timing indicatif)

```mermaid
flowchart LR
  subgraph SRC["Sources publiques"]
    DG[data.gouv.fr<br/>élections]
    IN[INSEE<br/>chômage emploi pop<br/>Filosofi SIDE]
  end

  subgraph ING["Ingestion ~2–5 min"]
    P[ThreadPoolExecutor<br/>téléchargements parallèles]
    RAW[(data/raw<br/>immuable)]
  end

  subgraph B["Bronze ~30 s"]
    BR[Normalisation contrat<br/>codes dept / blocs]
    BM[bronze_manifest.json]
  end

  subgraph S["Silver ~20 s"]
    DQ[DQM 16 contrôles]
    AG[Agrégats annuels<br/>socioeco_annuel]
  end

  subgraph G["Gold ~15 s"]
    FE[Features ≤ N−1<br/>lags politiques]
    KPI[kpi_*]
    SQL[(SQLite / Postgres)]
  end

  subgraph OUT["Restitution"]
    ML[ML walk-forward<br/>Gradient Boosting]
    BI[Dash + API<br/>Metabase]
  end

  DG --> P
  IN --> P
  P --> RAW --> BR --> BM --> DQ --> AG --> FE --> KPI --> SQL
  SQL --> ML
  SQL --> BI
```

**Timing POC (ordi portable)** : ingestion I/O-bound parallèle sur 5 fichiers élections ; transform pandas local < 1 min ; ML walk-forward ~20–40 s.

**PNG livrés** : [`diagrams/flux_etl_medaillon.png`](diagrams/flux_etl_medaillon.png) (flux ETL) et [`diagrams/scale_out.png`](diagrams/scale_out.png) — insérés dans le dossier Word et le deck. Sources : `flux_etl.mmd` / `flux_etl.html`, `scale_out.mmd` / `scale_out.html`.

## C3 — Pipeline distribué (scale-out)

```mermaid
flowchart TB
  subgraph ORCH["Orchestration Airflow"]
    T1[task_download_elections]
    T2[task_download_insee]
    T3[task_normalize_bronze]
    T4[task_silver_dqm]
    T5[task_gold_features]
    T6[task_train_ml]
    T7[task_publish_bi]
  end

  T1 --> T3
  T2 --> T3
  T3 --> T4 --> T5
  T5 --> T6
  T5 --> T7

  subgraph SPARK["Scale-out Spark"]
    PART[Partitionnement<br/>code_dept × annee]
    JOB[Jobs Silver/Gold<br/>Spark SQL / pandas UDFs]
  end

  T4 -. production .-> PART --> JOB
```

### Paragraphe scale-out chiffré
En production, chaque source est une tâche Airflow **idempotente**. Les élections (5 fichiers) restent **parallèles** (fan-in vers Bronze). Silver/Gold passent sur Spark avec partitionnement `code_dept` (96 partitions naturelles) × `annee` : pour ~10³–10⁶ lignes le gain est surtout organisationnel ; au-delà (infra-communal, quotidien), le même DAG scale horizontalement. Object storage S3/OVH remplace MinIO ; le warehouse Postgres/Metabase consomme uniquement **Gold**.

Voir aussi `ARCHITECTURE_BIGDATA.md` (même dossier) et le stub `orchestration/dags/electio_etl_dag.py`.
