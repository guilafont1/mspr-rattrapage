# Analyse ML — écarts départementaux (données réelles)

## Tâche
Prédire l'écart de chaque département au niveau national (`ecart_B`), puis
reconstruire `pct_B = national_B + ecart_B` (clip [0;100], somme 100).
Le bloc en tête est l'argmax. Le niveau national est un **scénario**, pas une
sortie du modèle.

## Diagnostic préalable (Ridge par bloc sur les niveaux)
`ridge_par_bloc` (MAE 14,38) n'était pas un bug : imputation 2007 OK ; α=10
choisi par l'argmax de sélection, pas par le MAE ; même α=1000 reste au-dessus
de la persistance (7,23). Le Ridge extrapolait `trend_*` / `delta_long_*`,
c'est-à-dire le choc national. Non retuné. Conservé dans `ml_report.json`.

## Features
- **Écart** (anti-leakage, scrutins < N) : `ecart_{B}_prec`, `delta_recent_ecart`,
  `delta_long_ecart`, `trend_ecart`, `volatility_ecart`.
- **Socio-éco INSEE** (N−1) : chômage, emploi, population.
- `creations_entreprises_n1` et `taux_pauvrete_n1` : exclus (couverture trop courte).

## Décision scrutins
Option B : exiger ≥ 1 prior (`ecart_*_prec`) → 384 obs., 2 plis de sélection
(2012, 2017). Option A (2 priors) n'aurait laissé qu'un pli.

## Régime A — national 2022 connu (oracle)
| Référence | MAE scores | Acc. argmax |
|---|---|---|
| **ridge_ecart_multisorties** (retenu) | **1,394** | **0,812** |
| Persistance de l'écart | 1,527 | 0,844 |
| Persistance du niveau (pct_2017) | 7,225 | 0,521 |
| Classe majoritaire EXD | — | 0,542 |

Le modèle **bat** la persistance en MAE (−0,133). Il ne la bat pas en argmax.
Non retuné. R² d'EXG / DRO très négatifs : σ inter-départements DRO = 1,16 pt
contre un choc national de −17,8 pts — ne pas citer le R² (`metrique_principale`: MAE).

## Régime B — national projeté (tendance)
Tendance linéaire : dernier niveau + (dernier−premier)/span × Δannées, puis
renormalisation. Acc. **0,448**, MAE **6,899** — le choc DRO n'est pas dans
l'extrapolation. Résultat prospectif à assumer.

## Poids socio-éco
**12,8 %** de l'importance (coefficients Ridge |moyen|) vs **87,2 %** pour les
dérivées d'écart. Les curseurs INSEE restent, avec un levier réel mais secondaire.

## Phrase orale
« Le modèle sait la carte, pas la vague. Avec le niveau national 2022 connu,
on est à 1,4 pt de MAE et 81 % d'argmax. Sans ce niveau, seulement 45 % :
c'est l'hypothèse nationale de l'utilisateur qui porte le choc, pas l'INSEE. »
