# Techniques de data visualisation — Electio-Analytics (compétence C5)

Page déclarative des techniques envisagées, de celles **retenues** dans le POC, et du pourquoi.

## Catalogue (8–10 techniques)

| # | Technique | Quand l’utiliser | Retenue ? | Où / pourquoi |
|---|---|---|---|---|
| 1 | **Barres** | Comparer des catégories discrètes (blocs, modèles) | Oui | Évolution des blocs par scrutin ; comparaison accuracy / F1 des modèles |
| 2 | **Lignes** | Séries temporelles continues | Oui | Trajectoires d’indicateurs N−1 par département (Dash) |
| 3 | **Choroplèthe** | Distribution spatiale sur fond cartographique | Oui | Carte des forces politiques par département (Plotly + GeoJSON) |
| 4 | **Heatmap** | Matrice dense (confusion, corrélations) | Oui | Matrice de confusion holdout ; corrélations features (matplotlib/seaborn) |
| 5 | **Boxplot** | Distribution + outliers par groupe | Oui | Chômage N−1 selon `bloc_gagnant` |
| 6 | **Scatter** | Relation entre 2 variables quantitatives | Partiel | Exploratoire notebook ; non prioritaire en restitution (lisibilité jury) |
| 7 | **Stacked area / stacked bar** | Composition dans le temps | Non | Moins lisible pour 5 blocs sur 5 dates ; barres groupées préférées |
| 8 | **Donut / camembert** | Parts d’un tout à un instant | Non | Mal adapté aux comparaisons multi-scrutins ; barre > donut |
| 9 | **Importance (barres horizontales)** | Interprétabilité ML | Oui | Top features du Gradient Boosting |
| 10 | **Probabilités what-if** | Aide à la décision scénarisée | Oui | Radar/barres de proba par bloc après `/predict` |

## Principes de choix
1. **Une question = une forme** — carte pour le territoire, barres pour comparer, heatmap pour l’erreur de classe.
2. **Public jury / décideur** — éviter les graphiques « jolis » peu informatifs (donut, 3D).
3. **Cohérence médailon** — toutes les vues Dash/API lisent la couche **Gold** (pas le Bronze).
4. **Accessibilité** — légendes explicites, couleurs de blocs stables (`EXG`…`EXD`).

## Stack retenue
- **matplotlib / seaborn** — figures statiques du dossier (`viz/output/`).
- **Plotly + Dash** — restitution interactive.
- **Pas de Power BI** dans le POC (évoqué en scale-out) ; Metabase optionnel sur Postgres.

## Phrase orale
« Nous avons listé dix techniques classiques, n’en avons retenu que celles qui servent une décision : carte, barres, heatmap, boxplot, importance et scénario what-if. »
