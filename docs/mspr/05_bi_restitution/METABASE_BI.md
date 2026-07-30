# Metabase — démo BI (compétence C7)

## Démarrage
```bash
# Option A : Postgres Aiven déjà dans .env du backend
docker compose --profile bi up -d metabase

# Option B : Postgres local
docker compose --profile localdb --profile bi up -d db metabase
```

UI : http://localhost:3000

## Connexion base
- Host : hostname Aiven **ou** `host.docker.internal` / `db` (profil localdb)
- Port / DB / user / password : variables `.env`
- SSL : requis sur Aiven (activer dans Metabase)

## 3 questions à sauvegarder (schéma étoile)

1. **Forces par scrutin**  
   `SELECT annee, bloc_gagnant, COUNT(*) AS n_dept FROM gold_dataset_analytique GROUP BY 1,2 ORDER BY 1,3 DESC;`

2. **Chômage moyen selon le bloc**  
   `SELECT bloc_gagnant, AVG(taux_chomage_n1) AS chomage_moy FROM gold_dataset_analytique GROUP BY 1;`

3. **Complétude features** (si table chargée)  
   `SELECT * FROM kpi_completude_features ORDER BY completude_pct;`

Ces questions prouvent la restitution BI sur le modèle en étoile (dims + gold + kpi).
