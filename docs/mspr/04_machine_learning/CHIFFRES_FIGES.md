# Chiffres figés — livraison (données réelles `--real`)

Source de vérité : `data/ml_report.json` + `data/quality_report.txt` + `data/gold/kpi_completude_features.csv`.
**Générés le : 30/07/2026** (après `python run_pipeline.py --real`).

## Pipeline
| Indicateur | Valeur |
|---|---|
| Observations GOLD | 480 (96 × 5) |
| Observations ML (avec lag) | 384 |
| Contrôles DQM | 16 OK / 0 KO |
| Pauvreté N−1 | **40 %** (2017 & 2022) — Filosofi histo branché |
| Modèle retenu | **gradient_boosting** (`n=200`, `depth=3`, `lr=0.1`) |
| Accuracy holdout 2022 | **0,531** |
| Accuracy walk-forward | **0,365** |
| Accuracy CV géo | **0,718** |
| Baseline CV | 0,410 |
| Top features | `pct_gagnant_precedent`, `delta_chomage_5a`, `marge_gagnante_precedente` |

## À recopier dans dossier / deck
Utiliser **uniquement** ces valeurs. Ne pas citer les scores du mode démo.
