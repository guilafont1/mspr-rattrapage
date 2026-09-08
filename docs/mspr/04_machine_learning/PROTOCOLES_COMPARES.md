# Comparaison des protocoles — niveaux vs écarts départementaux

Document de transparence. Les colonnes décrivent **deux cibles distinctes**
sur les mêmes données réelles.

## Tableau synthétique (données réelles, holdout 2022)

| Indicateur | Niveaux (précédent) | Écarts + oracle (A) | Écarts + tendance (B) |
|---|---|---|---|
| Cible apprise | cinq `pct_*` | cinq `ecart_*` | cinq `ecart_*` |
| Niveau national | implicite (à prédire) | **injecté (vrai 2022)** | extrapolé (tendance) |
| Observations ML | 384 | 384 | 384 |
| Plis de sélection | [2012, 2017] | [2012, 2017] | [2012, 2017] |
| Modèle retenu | random_forest_multisorties | **ridge_ecart_multisorties** | idem |
| MAE scores | 9,82 | **1,39** | **6,90** |
| Persist. niveau (MAE) | 7,23 | 7,23 | 7,23 |
| Persist. écart (MAE) | — | 1,53 | 6,76 |
| Acc. argmax | 0,156 | **0,812** | **0,448** |
| Gagnant précédent | 0,521 | 0,521 | 0,521 |
| Majoritaire EXD | 0,542 | 0,542 | 0,542 |

## Ce que chaque colonne mesure
Le protocole précédent apprenait le **niveau** et échouait sur le choc national
2022 (DRO −17,8 pts). La décomposition isole la géographie (A) de la vague
nationale (B). A et B ne sont pas interchangeables à l'oral.

## ridge_par_bloc (niveaux) — diagnostic
MAE 14,38 vs persistance 7,23 : **comportement légitime**, pas un bug.
La grille retenait α=10 (meilleure acc. de sélection) alors que le MAE s'améliore
en bout de grille (α=1000 : 11,99) sans jamais battre la persistance. Les
coefficients `trend_*` / `delta_long_*` extrapolaient un choc national.
Voir `diagnostic_ridge_par_bloc_niveaux` dans `data/ml_report.json`.

## Recommandation
Citer le régime A pour « le modèle sait-il la carte ? » et le régime B pour
« que vaut une prévision 2027 sans scénario national ? ».
