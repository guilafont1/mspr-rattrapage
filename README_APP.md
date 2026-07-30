# Electio-Analytics — Application conteneurisée

Application décisionnelle complète (BI) autour du POC de prévision des
tendances électorales : **base PostgreSQL + API Python + tableau de bord**,
le tout orchestré par Docker.

```
┌─────────────┐     HTTP      ┌─────────────┐    SQL     ┌──────────────┐
│  Frontend   │ ────────────► │   Backend   │ ─────────► │  PostgreSQL  │
│ Dash/Plotly │   API REST    │  FastAPI    │ SQLAlchemy │   (db)       │
│  :8050      │ ◄──────────── │  :8000      │ ◄───────── │   :5432      │
└─────────────┘               └──────┬──────┘            └──────────────┘
                                     │ scikit-learn
                                     ▼
                              Modèle Gradient Boosting (walk-forward)
                              (entraîné au démarrage)
```

## Démarrage avec Aiven (base distante)

1. Remplir `.env` (bloc AIVEN, `DB_SSLMODE=require`) — jamais committer `.env`.
2. Initialiser le schéma + charger les données :
   ```bash
   cd backend
   python init_remote.py
   ```
3. Lancer **uniquement** API + Dash (pas le Postgres local) :
   ```bash
   docker compose up --build backend frontend
   ```

Postgres local (optionnel) : `docker compose --profile localdb up -d db` et
remettre le bloc LOCAL dans `.env`.

## Démarrage local (Docker + Postgres local)

```bash
# .env en mode LOCAL (DB_HOST=db, sans SSL)
docker compose --profile localdb up --build
```

Puis ouvrir :
- **Tableau de bord** : http://localhost:8050
- **API + doc interactive (Swagger)** : http://localhost:8000/docs

Au premier démarrage, le backend charge automatiquement les données des
couches SILVER/GOLD (produites par le pipeline ETL) dans PostgreSQL, puis
entraîne le modèle.

## Basculer vers une base distante Aiven

1. Créer un service PostgreSQL sur Aiven, attendre le statut **Running**.
2. Dans `.env`, commenter le bloc LOCAL et remplir le bloc AIVEN
   (`DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_SSLMODE=require`).
3. Appliquer le schéma + charger SILVER/GOLD :
   ```bash
   python backend/init_remote.py
   ```
4. Lancer uniquement backend + frontend (pas le Postgres local) :
   ```bash
   docker compose up --build backend frontend
   ```
   Connexion via `backend/database.py` + `.env`. Aucun secret en dur dans le code.

## Endpoints de l'API

| Méthode | Route | Description |
|---|---|---|
| GET | `/health` | État de l'API et du modèle |
| GET | `/departements` | Liste des départements |
| GET | `/annees` | Années d'élection |
| GET | `/indicateurs?dept=&annee=` | Données GOLD filtrées |
| GET | `/resultats?annee=` | Résultats électoraux par bloc |
| GET | `/model/info` | Métriques du modèle |
| POST | `/predict` | Prédiction à partir d'indicateurs |

## Régénérer les données (pipeline ETL)

Les données chargées viennent du pipeline existant. Pour les régénérer sur
les vraies sources :
```bash
python run_pipeline.py --real   # data.gouv.fr / INSEE
```
puis relancer `docker compose up --build` (le backend rechargera la base).

## Structure

```
.
├── docker-compose.yml      orchestration db + backend + frontend
├── .env.example            config (local / Aiven)
├── db/init.sql             schéma PostgreSQL (joué au 1er démarrage)
├── backend/                API FastAPI
│   ├── main.py             endpoints
│   ├── database.py         connexion (bascule local/Aiven par env)
│   ├── load_data.py        chargement SILVER/GOLD -> Postgres
│   ├── ml_service.py       entraînement + prédiction (Gradient Boosting)
│   └── Dockerfile
├── frontend/               tableau de bord Dash
│   ├── app.py              3 onglets : vue d'ensemble, indicateurs, prédiction
│   └── Dockerfile
├── etl/  ml/  viz/  sql/   pipeline POC réutilisé
└── data/                   couches bronze/silver/gold
```
