# Comparaison des protocoles walk-forward (avec / sans 2007)

Document de transparence pour le dossier MSPR. Les deux colonnes décrivent
**deux protocoles distincts**, pas deux versions d'un même score.

## Tableau synthétique — modèle `random_forest` et baseline

| Indicateur | Protocole A (avec 2007) | Protocole B (sans 2007, retenu) |
|---|---|---|
| Décision features | Imputation médiane sur `creations_entreprises_n1` (cohorte 2007 entièrement manquante) | Exclusion du scrutin 2007 (−96 obs.) ; variable conservée |
| Observations ML | 384 (4 scrutins × 96) | 288 (3 scrutins × 96) |
| Scrutins | 2007, 2012, 2017, 2022 | 2012, 2017, 2022 |
| Plis walk-forward (tous) | 2012, 2017, 2022 | 2017, 2022 |
| Plis de **sélection** (hors holdout) | 2012, 2017 | **2017 seul** |
| Acc. RF — pli 2012 | 0,542 | — (pli absent) |
| Acc. RF — pli 2017 | 0,562 | 0,604 |
| Acc. RF — pli 2022 (holdout) | 0,802 | 0,844 |
| Acc. RF — moyenne tous plis | **0,635** | **0,724** |
| Acc. baseline — pli 2012 | 0,354 | — |
| Acc. baseline — pli 2017 | 0,104 | 0,646 |
| Acc. baseline — pli 2022 | 0,573 | 0,573 |
| Acc. baseline — moyenne tous plis | 0,344 | 0,609 |
| Acc. baseline holdout 2022 | 0,573 | 0,573 |
| Écart RF − baseline (holdout) | 0,229 | 0,271 |

Sources : `data/ml_report.json` avant exclusion de 2007 (protocole A) et après
(protocole B, génération courante). La baseline est le `DummyClassifier`
(classe majoritaire), évalué avec le même découpage temporel que les autres
modèles.

## Les deux colonnes ne sont pas comparables terme à terme

Le passage de 0,635 à 0,724 en accuracy walk-forward (moyenne tous plis) **n'est
pas un gain de modèle**. C'est un **changement de protocole** : le pli 2012,
historiquement le plus difficile pour la forêt (0,542), disparaît de la moyenne
dès que 2007 est exclu, faute d'année antérieure pour l'entraîner. La moyenne
restante (2017 + 2022) est mécaniquement plus haute.

De même, la baseline « moyenne walk-forward » passe de 0,344 à 0,609 parce que
le pli 2017, avec 2007 dans le train, était atypique (0,104) : sans 2007, le
pli 2017 de la baseline monte à 0,646 (classe majoritaire apprise sur 2012 seul).

## Recommandation pour le dossier

Citer **les deux protocoles** plutôt qu'une « progression » 0,635 → 0,724.
Pour le protocole B (retenu) :

- score de **sélection** = métriques hors holdout uniquement
  (`accuracy_walkforward_hors_holdout` / `f1_macro_walkforward_hors_holdout`),
  soit le pli 2017 seul ;
- holdout 2022 = test non vu, à confronter à la baseline 0,573
  (`ecart_baseline_holdout` dans `metriques_retenues`) ;
- faiblesse assumée : un seul pli de sélection (96 observations d'entraînement
  pour ce pli). Voir `protocole.avertissement` dans `data/ml_report.json`.

L'arbitrage features (option A vs B) est documenté sous
`decisions_features.creations_entreprises_n1`.
