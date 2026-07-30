# Modélisation multidimensionnelle — choix argumenté

## Les trois modèles (compétence entrepôt)

### Étoile (retenu)
- Un (ou plusieurs) fait(s) connecté(s) à des dimensions **dénormalisées**.
- **Pourquoi retenu** : volumétrie faible (~480 lignes GOLD), besoins BI/ML simples, requêtes lisibles, enseignable.
- Implémentation : `dim_departement`, `dim_annee`, `dim_bloc` + `fait_*` + `gold_dataset_analytique`.

### Flocon (évalué, non retenu)
- Dimensions **normalisées** (ex. `dim_region` → `dim_departement`).
- **Avantage** : moins de redondance, intégrité référentielle forte.
- **Rejet POC** : complexité de jointure injustifiée à cette échelle ; la région n’est pas un axe d’analyse prioritaire du CDC.

### Grappe / constellation (partiellement présent)
- Plusieurs tables de faits partageant des dimensions.
- **Présent** : `fait_resultat_election`, `fait_chomage_trimestriel`, `fait_emploi_trimestriel` autour des mêmes dims.
- La table **GOLD** est une couche de service dénormalisée pour le ML et le dashboard (anti-pattern OLTP, pattern analytique voulu).

## Déploiement BI
- Livrable fichier : SQLite `data/gold/electio_poc.db`
- Application : PostgreSQL via Docker / option Aiven
- Consommateurs : API FastAPI, Dash, notebooks, exports CSV

## Phrase orale type niveau 3
« Nous avons comparé étoile, flocon et grappe ; l’étoile a été retenue pour la lisibilité BI, avec une constellation de faits pour les sources hétérogènes, et une table gold de service pour le ML. »
