# Analyse ML par classe — holdout 2022 (compétence C4)

## Pauvreté (Filosofi) — décision modèle
- **Branchée** en Bronze/Silver/Gold : millésimes 2016, 2017, 2019, 2021 + Melodi 2023.
- Complétude `taux_pauvrete_n1` : **40 %** (scrutins 2017 et 2022 uniquement ; N−1 absents avant).
- **Exclue du modèle supervisé** : la feature dégrade le holdout walk-forward ; conservée pour la BI / KPI.
- Preuve : `data/quality_report.txt` + `kpi_completude_features.csv` + `docs/mspr/04_machine_learning/ANALYSE_ML_CLASSES.md`.

## Contexte
Cible : `bloc_gagnant` (5 modalités). Protocole : walk-forward + holdout dernier scrutin.
Modèle retenu : **Gradient Boosting** (score 0,4×WF + 0,6×holdout).

## Pourquoi 2022 est difficile
| Bloc | Train 2007–2017 | Test 2022 | Lecture |
|---|---|---|---|
| GAU / DRO | Dominants historiquement | Faibles / absents | Stickiness politique trompe RF |
| EXD | Rare hors 2017 | **Majoritaire** (~54 % des dépts) | Recomposition nationale |
| CEN | Faible | Fort (~31 %) | Offre macroniste non vue avant 2017 |

Le **Random Forest** maximise la CV géographique en recopiant les blocs passés → holdout ~0,05.  
Le **Gradient Boosting** capture mieux les interactions socio-éco + lags → holdout **≈ 0,53** (> 0,5).

## Pourquoi le F1 macro est plus bas que l’accuracy
- Classes **déséquilibrées** en 2022 (EXD/CEN vs GAU).
- Support **DRO = 0** sur le holdout → contribution nulle / instable au macro.
- L’accuracy récompense le bon classement du bloc majoritaire (EXD) ; le F1 macro pénalise les classes rares.

## Tuning léger (walk-forward)
Grille explorée dans `ml/train.py` (sous-ensemble GB) : `n_estimators ∈ {150,200}`, `max_depth ∈ {2,3}`, `learning_rate ∈ {0.05,0.1}` — sélection toujours par le **même score temporel** (pas de peeking géo seul).

## Phrase orale
« Le seuil CDC est tenu en holdout temporel avec le Gradient Boosting. Le F1 macro plus bas est attendu : 2022 n’a plus de DRO en tête et concentre EXD/CEN. Ce n’est pas un bug pipeline, c’est la limite d’un modèle socio-économique face à une recomposition politique. »
