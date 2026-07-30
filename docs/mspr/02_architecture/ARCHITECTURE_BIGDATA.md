# Architecture Big Data — Electio-Analytics POC

## Objectif
Passer d’une collecte hétérogène (CSV/XLS/API) à un **datalake médailon** consommable par le ML et la BI, avec une voie claire vers le scale-out.

## Couches

| Zone | Rôle | Contenu POC | Scale-out |
|---|---|---|---|
| **RAW** | Sources immuables | `data/raw/` (+ MinIO `bronze/raw`) | S3 / OVH Object Storage |
| **Bronze** | Contrat normalisé + schéma validé | 6 CSV + `bronze_manifest.json` | Idem |
| **Silver** | DQM + enrichissement métier | 9 tables (dont agrégats annuels + `socioeco_annuel`) | dbt / Spark SQL |
| **Gold** | Grain analytique + KPI | `dataset_analytique` + 3 KPI + SQLite/Postgres | Warehouse managé |
| **Restitution** | Valeur métier | FastAPI + Dash + ML | Power BI / Looker |

### Contrats par couche
- **Bronze** : schémas canoniques dans `etl/referentiels.py` (`BRONZE_SCHEMAS`), contrôles codes métropole, manifeste.
- **Silver** : dédup, bornes, cohérence des %, `bloc_gagnant` / marge, agrégats trimestriels → annuels, panel socio-éco joint.
- **Gold** : 1 ligne = 1 (département, élection), features ≤ N−1, lags politiques, artefacts `kpi_*`, dims libellées (région).

## ELT vs ETL
- **ETL classique** : `02_transform` lit bronze et produit silver/gold.
- **ELT / datalake** : charge RAW dans MinIO (`03_sync_datalake.py`), puis transforme. Le POC combine les deux.

## Traitement parallèle
Ingestion des fichiers élections **parallélisée** (`ThreadPoolExecutor`). En production : Airflow + Spark.

## Commandes
```bash
python run_pipeline.py            # demo
python run_pipeline.py --real     # sources officielles
docker compose --profile datalake up -d minio
python etl/03_sync_datalake.py
```

## Création de valeur
Dash + `/predict` : scénarios what-if, forces territoriales, trajectoires d’indicateurs à partir de la couche Gold.
