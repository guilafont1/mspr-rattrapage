# Argumentaire grille MSPR — viser le niveau 3 partout

> Légende officielle : **3** = pratique approfondie + capacité à **transmettre** la compétence.
> Ce document est le script oral/écrit pour démontrer chaque compétence. Pointer toujours vers un artefact concret.

---

## 1. Collecter les besoins / stratégie Data — **viser 3**

**À dire (30 s)**  
« À partir du cahier des charges Electio-Analytics, nous avons reformulé le besoin métier : anticiper le bloc en tête au T1 par département via indicateurs socio-économiques publics. Nous avons cadré le périmètre (96 depts métro, 5 scrutins), listé les sources, et modélisé le flux collecter → structurer → valoriser. »

**Preuves à montrer**  
- Sujet / CDC dans `docs/mspr/01_sujet_grille/`  
- Dossier de synthèse (justification géographique + critères)  
- Schéma de flux (`docs/mspr/02_architecture/` + deck)  
- Sources documentées dans `etl/01_download.py` (`CATALOGUES`)

**Phrase “transmettre”**  
« Un junior peut reprendre le CDC + ce schéma et relancer `run_pipeline.py --real` sans ambiguïté. »

---

## 2. Architecture BI (3 couches) — **viser 3**

**À dire**  
« Couche 1 collecte : data.gouv / INSEE → `data/raw` + bronze. Couche 2 stockage/modélisation : silver/gold + SQLite/Postgres (étoile). Couche 3 restitution : Dash/Plotly + figures matplotlib, API FastAPI. »

**Preuves**  
- `README_APP.md` (schéma Docker)  
- `docker-compose.yml` (db / backend / frontend / minio)  
- Live : `:8050` + `:8000/docs`

---

## 3. Stratégie big data — **viser 3** (ex-point faible)

**À dire**  
« Stratégie datalake médailon : zone RAW immuable, bronze normalisé, silver nettoyé, gold consommable. Ingestion I/O parallèle (`ThreadPoolExecutor` sur les élections). Stockage objet MinIO compatible S3 (profil `datalake`). Transform en ELT léger (chargement puis transformation pandas → SQL). Restitution = Dash + API. Scale-out cible : Airflow + workers + object storage OVH/S3. »

**Preuves**  
- `etl/01_download.py` (parallélisation)  
- `etl/03_sync_datalake.py` + MinIO  
- `docs/mspr/02_architecture/ARCHITECTURE_BIGDATA.md`  
- `docs/mspr/02_architecture/DIAGRAMMES_FLUX.md`  
- Commandes :
  ```bash
  docker compose --profile datalake up -d minio
  python etl/03_sync_datalake.py
  # Console http://localhost:9011
  ```

---

## 4. Machine Learning — **viser 3**

**À dire**  
« Classification supervisée du `bloc_gagnant`. Python/scikit-learn. Comparaison Dummy / LogReg / RF / GB. **Sélection temporelle** : score 0,4×accuracy walk-forward + 0,6×accuracy holdout (évite le RF « stickiness » qui rate 2022). Holdout 2022 GB ≈ 0,53 > 0,5. CV géo secondaire ≈ 0,72. Importance des variables interprétée. »

**Preuves**  
- `ml/train.py`, `data/ml_report.json`  
- `docs/mspr/04_machine_learning/CHIFFRES_FIGES.md`  
- Figures confusion / compare / importance  
- API `/predict` en live

**Ne pas dire** : « Random Forest 2 % sur 2022 » comme modèle retenu — le retenu est le **Gradient Boosting** (≈ 0,53 holdout).

---

## 5. Data visualisation — **viser 3**

**À dire**  
« Techniques : séries temporelles, barres, corrélations/heatmap, boxplot, projection probabiliste, barres horizontales interactives. Outil : Plotly Dash (rapports interactifs) + Matplotlib/Seaborn (dossier). UI FR, contrastes, KPI décisionnels. »

**Preuves**  
- Live Dash (3 onglets)  
- `viz/figures.py` + `viz/output/`  
- `docs/mspr/03_donnees/TECHNIQUES_DATAVIZ.md`

---

## 6. Données de référence / référentiel — **viser 3**

**À dire**  
« Référentiels : codes dept (2A/2B), `dim_departement`, `dim_annee`, `dim_bloc`, mapping candidat→bloc documenté. Critères de sélection/validation : bornes, unicité de clé, SANITY anti-demo, anti-leakage N−1. »

**Preuves**  
- `etl/mapping_blocs.py`  
- `docs/mspr/03_donnees/REFERENTIEL_DONNEES.md`  
- `data/quality_report.txt`  
- Tables `dim_*` dans SQLite/Postgres

---

## 7. Entrepôt / modèle multidimensionnel — **viser 3**

**À dire**  
« Comparaison étoile / flocon / grappe documentée. **Étoile retenue** (simplicité BI + volumétrie faible). Constellation partielle via plusieurs `fait_*`. Déploiement dans SQLite (livrable) et Postgres (app). »

**Preuves**  
- `sql/schema.sql` (argumentaire dans les commentaires)  
- `docs/mspr/05_bi_restitution/MODELISATION_MULTIDIM.md`  
- `docs/mspr/05_bi_restitution/METABASE_BI.md`  
- Base `data/gold/electio_poc.db`

---

## 8. Qualité des données — **viser 3** (meilleur levier)

**À dire**  
« DQM opérationnel : exactitude (bornes), complétude, cohérence, unicité, traçabilité. Outil : pandas cleansing + journal `quality_report.txt` + pytest. Échec bloquant si KO. »

**Preuves**  
```bash
python -m pytest tests/ -v
python gx/run_checkpoint.py
type data\quality_report.txt
```

---

## 9. Sécurité & RGPD — **viser 3**

**À dire**  
« Méthodologie : données publiques agrégées → hors champ données personnelles. Minimisation, finalité POC, licence Ouverte v2.0. Secrets hors code (`.env`). Options hébergement (cloud neutre / on-prem) dans le deck. Si demain données d’opinion → AIPD. »

**Preuves**  
- `docs/mspr/06_rgpd_securite/RGPD_SECURITE.md`  
- `.env.example` (pas de secret en dur)  
- Section 8 du dossier

---

## Démo live (ordre recommandé — 4 min)

1. `quality_report.txt` + `pytest` (qualité = 3)  
2. Dash prédiction (dataviz + ML)  
3. Schéma SQL + `dim_bloc` (entrepôt + référentiel)  
4. MinIO console `:9001` ou explication datalake (big data)  
5. Une slide RGPD

## Phrase de clôture

« Le POC n’est pas seulement fonctionnel : chaque brique est documentée pour être reprise, enseignée et industrialisée — c’est le critère du niveau 3. »
