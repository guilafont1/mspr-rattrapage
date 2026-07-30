# POC Electio-Analytics — MSPR TPRE813 (Bloc 3 : Big Data & BI)

Prévision des tendances électorales (1–3 ans) à partir d'indicateurs
socio-économiques publics. Périmètre : 96 départements métropolitains,
5 scrutins présidentiels (2002–2022) → 480 observations.

## Démarrage rapide
```bash
python run_pipeline.py         # mode démo (données simulées, hors ligne)
python -m pytest tests/ -v     # tests qualité du pipeline
python run_pipeline.py --real  # télécharge + normalise les vraies sources (data.gouv / INSEE)
```
Le script `etl/01_download.py` résout les URL via l’API data.gouv et les pages
catalogue INSEE, normalise vers le contrat BRONZE, et agrège les candidats en
5 blocs via `etl/mapping_blocs.py` (modifiable). Les bruts sont archivés dans
`data/raw/` ; la couche `data/bronze/` ne contient que les CSV normalisés.

## Structure
- `run_pipeline.py` — orchestrateur (collecte → transform → ML → viz → datalake optionnel)
- `etl/00_demo_data.py` — [DÉMO] génère une couche BRONZE simulée (même contrat + manifeste)
- `etl/01_download.py` — téléchargement parallèle + normalisation Bronze (schéma validé)
- `etl/02_transform.py` — BRONZE → SILVER (DQM + agrégats) → GOLD (features + KPI) + SQLite
- `etl/03_sync_datalake.py` — sync médailon vers MinIO (S3)
- `etl/referentiels.py` — contrats Bronze, dims département/région, blocs
- `etl/mapping_blocs.py` — table candidat → bloc (EXG/GAU/CEN/DRO/EXD)
- `sql/schema.sql` — schéma en étoile (argumentaire étoile/flocon/grappe inclus)
- `ml/train.py` — modèles comparés, CV groupée, matrice de confusion
- `viz/figures.py` — figures exploratoires + restitution
- `tests/test_pipeline.py` — tests qualité + anti-leakage + contrats de couches
- `docs/` — index dans `docs/README.md` (sujet, archi, données, ML, BI, RGPD, soutenance, livrables)
- `data/bronze|silver|gold/` — couches médailon (+ manifests JSON)
- `data/gold/electio_poc.db` — livrable SQL (dims + faits + gold + kpi)

## Modèle retenu
Gradient Boosting — sélection par **walk-forward temporel** (leave-one-election-out).
Holdout 2022 ≈ **0,53** (seuil CDC > 0,5), CV géo secondaire ≈ 0,70.
Le Random Forest reste fort en CV géo mais échoue sur la recomposition 2022 : d’où le critère temporel.
Variables clés : dynamique du chômage, lags politiques, emploi / population.

## ⚠️ Avant remise finale
Relancer `python run_pipeline.py --real` puis figer les chiffres du dossier / deck
sur `data/ml_report.json` et `docs/mspr/04_machine_learning/CHIFFRES_FIGES.md`.

Docs grille (rangés par thème) :
- `docs/mspr/03_donnees/` — référentiel + techniques dataviz
- `docs/mspr/02_architecture/` — diagrammes flux / scale-out
- `docs/mspr/04_machine_learning/` — analyse classes + chiffres
- `docs/mspr/05_bi_restitution/` — Metabase + étoile
- `docs/mspr/07_soutenance/ARGUMENTAIRE_NIVEAU3.md`

Datalake / BI jury :
```bash
docker compose --profile datalake up -d minio
python etl/03_sync_datalake.py
docker compose --profile bi up -d metabase   # http://localhost:3000
```

Soutenance : `docs/mspr/07_soutenance/ARGUMENTAIRE_NIVEAU3.md`.

Sources : data.gouv.fr (élections), INSEE (chômage, emploi, population,
Filosofi historique + Melodi, entreprises) — Licence Ouverte v2.0 (Etalab).
