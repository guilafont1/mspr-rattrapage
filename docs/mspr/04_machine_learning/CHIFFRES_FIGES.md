# Chiffres figés — livraison (données réelles, écarts départementaux)

Source de vérité : `data/ml_report.json` + `data/quality_report.txt` + `data/bronze/bronze_manifest.json`.
**Générés le : 08/09/2026** (après décomposition national + écart).

## Pipeline
| Indicateur | Valeur |
|---|---|
| Mode Bronze | **real** |
| Observations GOLD | 480 (96 × 5) |
| Observations ML | **384** (≥ 1 prior d'écart) |
| Tâche | **Régression des écarts** `ecart_B` ; score = national + écart |
| Plis de sélection | **[2012, 2017]** (n=2) |
| Modèle retenu | **ridge_ecart_multisorties** (α = 10) |
| Métrique principale | **MAE** (le R² n'est pas citable) |
| MAE écart holdout | **1,406** (persist. écart : 1,538) |
| MAE scores oracle 2022 | **1,394** (persist. écart : 1,527 ; persist. niveau : 7,225) |
| Acc. argmax oracle 2022 | **0,812** |
| Acc. persist. écart (oracle) | **0,844** |
| Acc. gagnant précédent | **0,521** |
| Acc. majoritaire EXD 2022 | **0,542** |
| MAE scores projeté 2022 | **6,899** |
| Acc. argmax projeté 2022 | **0,448** |
| Part importance socio-éco INSEE | **12,8 %** (écart : 87,2 %) |
| Seuil CDC 0,5 (temporel, oracle) | **true** |

## Deux régimes (à ne pas confondre)
- **A — national connu (oracle)** : mesure la géographie. MAE 1,39 vs 7,23 pour recopier le score 2017.
- **B — national projeté (tendance)** : régime prospectif honnête. Acc. 0,448, sous le gagnant précédent.

## Lecture obligatoire
En régime A le modèle **bat** la persistance de l'écart en MAE (−0,13 pt) mais **pas** en argmax (0,812 vs 0,844). Non retuné. En régime B, le choc national DRO (−17,8 pts) n'est pas anticipé : c'est le résultat à citer, pas un échec à corriger.

## À recopier dans dossier / deck
Utiliser **uniquement** ces valeurs.
