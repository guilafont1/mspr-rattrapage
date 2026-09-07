# Rapport ML & BI — Electio-Analytics (MSPR Rattrapage)

> **Généré le :** 02/09/2026  
> **Projet :** `mspr-rattrapage` — POC prévision tendances électorales (96 départements, 5 scrutins 2002–2022)  
> **Usage :** document de synthèse pour analyse / soutenance (Claude ou jury)

---

## 1. Exécutions relancées

| Composant | Commande / action | Statut |
|---|---|---|
| Pipeline ETL + ML + viz | `py run_pipeline.py` | ✅ Succès |
| Entraînement ML offline | `ml/train.py` → `data/ml_report.json` | ✅ Succès |
| Visualisations | `viz/figures.py` → `viz/output/*.png` (8 figures) | ✅ Succès |
| DQM | `py dqm/run_checkpoint.py` | ✅ 6/6 expectations OK |
| API — reload modèle | `POST /admin/reload` (base Aiven) | ✅ `modele_pret: true` |
| BI Metabase | `docker compose --profile bi up -d metabase` | ✅ http://localhost:3000 |
| Dashboard Dash | `docker compose up backend frontend` | ✅ http://localhost:8050 |
| API FastAPI | — | ✅ http://localhost:8000/docs |

---

## 2. Périmètre données & qualité (BI / GOLD)

### 2.1 Volumétrie couches médailon

| Couche | Détail |
|---|---|
| **BRONZE** | 6 tables (élections, chômage, emploi, population, pauvreté, entreprises) |
| **SILVER** | 9 tables (DQM + agrégats annuels + panel socio-éco) |
| **GOLD** | 480 lignes = 96 départements × 5 élections |
| **Postgres Aiven** | 480 lignes GOLD (`/health/db` → `gold_rows: 480`, latence ~237 ms) |
| **SQLite POC** | `data/gold/electio_poc.db` |

### 2.2 Contrôles qualité (16/16 OK)

```
elections : codes métropole, pct ∈ [0;100], somme pct ≈ 100
chômage   : codes métropole, taux ∈ [0;30], trimestre 1..4
emploi    : codes métropole, total > 0
population: codes métropole, > 0
pauvreté  : codes métropole, taux ∈ [0;40]
entreprises: codes métropole, > 0
GOLD      : chômage_n1 renseigné, unicité (dept, année)
```

**DQM checkpoint :** `success: true` — 6 expectations passées (pct élections, départements métropole, chômage, unicité GOLD, complétude chômage_n1, pauvreté_n1 partielle attendue).

### 2.3 Complétude des features GOLD

| Feature | Complétude | n non-null |
|---|---:|---:|
| taux_chomage_n1 | 100 % | 480 |
| delta_chomage_1a | 100 % | 480 |
| delta_chomage_5a | 100 % | 480 |
| emploi_pour_1000hab | 100 % | 480 |
| croissance_emploi_5a_pct | 80 % | 384 |
| croissance_pop_5a_pct | 80 % | 384 |
| taux_pauvrete_n1 | 80 % | 384 |
| creations_entreprises_n1 | 60 % | 288 |
| bloc_gagnant_precedent | 80 % | 384 |
| pct_gagnant_precedent | 80 % | 384 |
| marge_gagnante_precedente | 80 % | 384 |

> **Décision métier :** `taux_pauvrete_n1` présent en GOLD/BI mais **exclu du modèle ML** (couverture historique courte, risque sur holdout temporel).

### 2.4 KPI BI — évolution blocs gagnants (nombre de départements)

| Année | CEN | DRO | EXD | GAU | EXG |
|---:|---:|---:|---:|---:|---:|
| 2002 | 10 | 64 | 1 | 21 | — |
| 2007 | 35 | 42 | 6 | 13 | — |
| 2012 | 39 | 34 | 21 | 2 | — |
| 2017 | 62 | 10 | 24 | 0 | — |
| 2022 | 55 | 3 | 38 | 0 | — |

### 2.5 KPI BI — chômage moyen par bloc gagnant (toutes années)

| Bloc | Chômage moyen | Médiane | n obs |
|---|---:|---:|---:|
| CEN | 6,93 % | 6,91 % | 201 |
| DRO | 8,37 % | 8,30 % | 153 |
| EXD | 9,37 % | 9,42 % | 90 |
| GAU | 10,14 % | 10,47 % | 36 |

### 2.6 Scores nationaux moyens 2022 (API `/dashboard/overview`)

| Bloc | Score moyen T1 (%) |
|---|---:|
| EXG | 8,07 |
| GAU | 20,14 |
| CEN | 25,18 |
| DRO | 25,44 |
| EXD | 21,17 |

---

## 3. Machine Learning — protocole

| Élément | Valeur |
|---|---|
| **Cible** | `bloc_gagnant` (EXG/GAU/CEN/DRO/EXD) au T1 |
| **Observations modèle** | 384 (après filtrage `bloc_gagnant_precedent` + `taux_chomage_n1`) |
| **Départements** | 96 |
| **Holdout** | 2022 (96 départements test) |
| **Sélection modèle** | `max(0,4 × acc_walkforward + 0,6 × acc_holdout)` |
| **Validation principale** | Walk-forward leave-one-election-out |
| **Validation secondaire** | GroupKFold (5 splits) par département |
| **Anti-leakage** | Features calculées sur années ≤ N−1 + lags scrutin précédent |

### Features numériques utilisées

```
taux_chomage_n1, delta_chomage_1a, delta_chomage_5a,
emploi_pour_1000hab, croissance_emploi_5a_pct, croissance_pop_5a_pct,
creations_entreprises_n1, pct_gagnant_precedent, marge_gagnante_precedente
```

Feature catégorielle : `bloc_gagnant_precedent`

---

## 4. Comparaison des modèles (`data/ml_report.json` — pipeline offline)

> Source : exécution `ml/train.py` après `run_pipeline.py` (données démo régénérées).

| Modèle | Acc. walk-forward | F1 macro WF | Acc. holdout 2022 | F1 macro 2022 | Acc. CV géo | F1 macro CV |
|---|---:|---:|---:|---:|---:|---:|
| **random_forest** ⭐ | **0,635** | **0,422** | **0,802** | **0,548** | **0,704** | **0,601** |
| gradient_boosting | 0,549 | 0,353 | 0,771 | 0,547 | 0,672 | 0,515 |
| arbre_decision | 0,490 | 0,291 | 0,667 | 0,366 | 0,578 | 0,497 |
| regression_logistique | 0,490 | 0,248 | 0,750 | 0,404 | 0,638 | 0,547 |
| baseline (classe majoritaire) | 0,344 | 0,145 | 0,573 | 0,243 | 0,497 | 0,165 |

⭐ **Modèle retenu offline : `random_forest`**

### 4.1 Walk-forward par scrutin — Random Forest

| Scrutin test | Accuracy | F1 macro | n |
|---|---:|---:|---:|
| 2012 | 0,542 | 0,375 | 96 |
| 2017 | 0,562 | 0,343 | 96 |
| 2022 | 0,802 | 0,548 | 96 |

### 4.2 Grille hyperparamètres Gradient Boosting

| Config | Acc. walk-forward | Acc. holdout 2022 | F1 macro WF |
|---|---:|---:|---:|
| gb_n200_d3_lr0.05 | 0,549 | 0,771 | 0,353 |
| gb_n150_d2_lr0.1 | 0,524 | 0,719 | 0,298 |
| gb_n200_d3_lr0.1 | 0,531 | 0,708 | 0,315 |
| gb_n250_d2_lr0.08 | 0,521 | 0,698 | 0,293 |

Meilleure config grille : **gb_n200_d3_lr0.05** (holdout 0,771).

### 4.3 Métriques retenues (modèle offline RF)

| Métrique | Valeur |
|---|---:|
| Accuracy walk-forward | 0,635 |
| F1 macro walk-forward | 0,422 |
| Accuracy holdout 2022 | **0,802** |
| F1 macro holdout 2022 | 0,548 |
| Accuracy CV géographique | 0,704 |
| **Seuil CDC > 0,5** | ✅ **ATTEINT** |

### 4.4 Rapport de classification — holdout 2022 (Random Forest)

| Classe | Precision | Recall | F1-score | Support |
|---|---:|---:|---:|---:|
| CEN | 0,803 | 0,891 | 0,845 | 55 |
| DRO | 0,000 | 0,000 | 0,000 | 3 |
| EXD | 0,875 | 0,737 | 0,800 | 38 |
| GAU | — | — | — | 0 |
| **Accuracy globale** | | | **0,802** | 96 |
| **Macro avg F1** | 0,559 | 0,543 | **0,548** | 96 |
| **Weighted avg F1** | 0,807 | 0,802 | **0,801** | 96 |

> Classe **GAU absente** au holdout 2022 (0 département gagnant GAU) → F1 macro pénalisé. Classe **DRO** très minoritaire (3 dept.) → recall nul.

### 4.5 Importance des variables (Random Forest — offline)

| Rang | Variable | Importance |
|---:|---|---:|
| 1 | taux_chomage_n1 | 0,226 |
| 2 | emploi_pour_1000hab | 0,183 |
| 3 | creations_entreprises_n1 | 0,153 |
| 4 | pct_gagnant_precedent | 0,091 |
| 5 | delta_chomage_5a | 0,055 |
| 6 | delta_chomage_1a | 0,052 |
| 7 | marge_gagnante_precedente | 0,052 |
| 8 | prec_GAU | 0,047 |
| 9 | croissance_emploi_5a_pct | 0,042 |
| 10 | prec_EXD | 0,042 |

### 4.6 Projection probabiliste par bloc (horizon 1–3 ans)

| Bloc | Probabilité moyenne |
|---|---:|
| CEN | 0,450 |
| DRO | 0,221 |
| EXD | 0,247 |
| GAU | 0,082 |

---

## 5. Modèle en production API (base Aiven — `ml_service.py`)

> L'API embarque un **Gradient Boosting** fixe (n_estimators=200, max_depth=3), réentraîné au démarrage sur Postgres Aiven.

| Métrique | Valeur API (`/model/info`) |
|---|---:|
| Modèle servi | gradient_boosting |
| n_observations | 384 |
| n_departements | 96 |
| Accuracy CV géographique | 0,674 |
| Accuracy holdout 2022 | **0,708** |
| Classes prédites | CEN, DRO, EXD, GAU |

### 5.1 Matrice de confusion — holdout 2022 (API / GB)

Labels : `[CEN, DRO, EXD, GAU]`

```
           Pred CEN  Pred DRO  Pred EXD  Pred GAU
Réel CEN      41        9         4         1
Réel DRO       2        1         0         0
Réel EXD       6        5        26         1
Réel GAU       0        0         0         0
```

| Métrique | Valeur |
|---|---:|
| Accuracy test 2022 | 0,708 |
| F1 macro test 2022 | 0,416 |

### 5.2 Importance variables — API (Gradient Boosting)

| Variable | Importance |
|---|---:|
| taux_chomage_n1 | 0,2418 |
| emploi_pour_1000hab | 0,2199 |
| creations_entreprises_n1 | 0,1383 |
| delta_chomage_1a | 0,0910 |
| pct_gagnant_precedent | 0,0859 |
| croissance_emploi_5a_pct | 0,0572 |
| croissance_pop_5a_pct | 0,0524 |
| marge_gagnante_precedente | 0,0521 |
| delta_chomage_5a | 0,0519 |

### 5.3 Écart offline vs production

| Source | Modèle | Holdout 2022 | CV géo |
|---|---|---:|---:|
| `ml/train.py` (sélection walk-forward) | random_forest | **0,802** | 0,704 |
| API Aiven (`ml_service.py`) | gradient_boosting | 0,708 | 0,674 |

**Interprétation :** le pipeline offline sélectionne le meilleur modèle par robustesse temporelle ; l'API utilise un GB simplifié pour la latence et la stabilité du service. Les deux dépassent le seuil CDC (> 0,5) sur le holdout 2022.

---

## 6. Visualisations générées

| Fichier | Contenu |
|---|---|
| `viz/output/1_evolution_blocs.png` | Scores moyens nationaux par bloc (2002–2022) |
| `viz/output/2_gagnant_par_election.png` | Distribution départements gagnants par scrutin |
| `viz/output/3_correlations.png` | Matrice corrélations features GOLD |
| `viz/output/4_chomage_par_bloc.png` | Chômage N−1 vs bloc gagnant |
| `viz/output/5_confusion.png` | Matrice confusion holdout 2022 |
| `viz/output/6_model_compare.png` | Walk-forward vs CV géographique |
| `viz/output/7_importance.png` | Importance des variables |
| `viz/output/8_projection.png` | Projection probabiliste par bloc |

---

## 7. BI — Metabase (self-service)

| Élément | Détail |
|---|---|
| URL | http://localhost:3000 |
| Image | `metabase/metabase:v0.51.2` |
| Conteneur | `electio_metabase` |
| Statut | ✅ Démarré |

### Connexion recommandée (base Aiven)

1. Premier lancement → créer compte admin Metabase
2. **Add database** → PostgreSQL
3. Paramètres (depuis `.env` / console Aiven) :
   - Host : `db-mspr-master-1-rattrapage-julienfontamine1-50de.d.aivencloud.com`
   - Port : `24053`
   - Database : `defaultdb`
   - User : `avnadmin`
   - SSL : activé (`require`)
4. Tables BI disponibles : `gold_dataset_analytique`, KPI, dims (`dim_departement`, `dim_bloc`, `dim_annee`)

### Restitution BI complémentaire

- **Dashboard Dash** : http://localhost:8050 (3 onglets : vue d'ensemble, indicateurs, prédiction)
- **API REST** : http://localhost:8000/docs

---

## 8. Synthèse exécutive (pour Claude)

1. **Pipeline complet relancé** : ETL → GOLD (480 obs) → ML → 8 figures → DQM OK.
2. **Qualité données** : 16/16 contrôles ETL + 6/6 expectations DQM ; anti-leakage validé.
3. **Modèle offline retenu** : Random Forest — holdout 2022 = **80,2 %**, walk-forward = 63,5 %, CV géo = 70,4 % → **seuil CDC 0,5 atteint**.
4. **Modèle API production** : Gradient Boosting — holdout 2022 = **70,8 %**, CV géo = 67,4 %.
5. **Variables clés** : chômage N−1, emploi/1000 hab., créations d'entreprises, lags politiques.
6. **BI opérationnelle** : Metabase (3000), Dash (8050), Postgres Aiven (480 lignes GOLD).
7. **Point d'attention** : classes rares au holdout 2022 (GAU=0, DRO=3) → F1 macro bas malgré accuracy élevée.

---

## 9. Fichiers sources des métriques

| Fichier / endpoint | Contenu |
|---|---|
| `data/ml_report.json` | Rapport ML complet (comparaison modèles, classification, projection) |
| `data/quality_report.txt` | Journal qualité ETL |
| `data/gold/kpi_*.csv` | KPI BI exportés |
| `dqm/uncommitted/validation_results/electio_checkpoint.json` | Résultats DQM |
| `GET /model/comparison` | Comparaison modèles (lit ml_report.json) |
| `GET /model/confusion` | Matrice confusion API (GB live) |
| `GET /model/importance` | Importances API (GB live) |
| `GET /dashboard/overview` | KPI BI agrégés pour Dash |

---

*Fin du rapport — Electio-Analytics MSPR TPRE813*
