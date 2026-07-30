# Référentiel des données — Electio-Analytics (compétence C6)

Document de sélection, validation et gouvernance des sources du POC.
Licence globale des jeux utilisés : **Licence Ouverte v2.0 (Etalab)** sauf mention contraire INSEE (réutilisation libre avec paternité).

## Tableau des sources

| Source | Producteur | Accès / licence | Granularité | Fraîcheur / couverture | Critères de sélection | Critères de validation (DQM) |
|---|---|---|---|---|---|---|
| Résultats présidentielles T1 | Ministère de l’Intérieur via **data.gouv.fr** | LO v2.0 | Département × scrutin (2002–2022) | 5 millésimes figés | Officiel, maille département, T1 comparable | Codes métro, 96 dépts/an, % ∈ [0;100], somme ≈ 100, SANITY inscrits 75/01/23 |
| Chômage localisé | **INSEE** (série longue `sl_etc_*`) | Réutilisation INSEE / LO | Département × trimestre | ~1982→millésime courant | Série longue, fréquence fine, anti-leakage N−1 | Taux ∈ [0;30], trimestre 1–4, dédup clé, SANITY 2021 |
| Emploi salarié | **INSEE** (série longue `sl_ete_*`) | Idem | Département × trimestre | Série longue | Cohérent avec chômage / population | `emploi_total` > 0, SANITY 2021 |
| Population | **INSEE** (estimations / Melodi) | Idem | Département × année | 1975→courant (POC filtre utile) | Dénominateur emploi / 1000 hab. | Population > 0, SANITY 2021 |
| Pauvreté (Filosofi) | **INSEE** Filosofi 1 (2016–2021) + Filosofi 2 Melodi (2023) | Idem | Département × année | Historique branché + millésime courant | Indicateur social ; N−1 pour 2017 & 2022 | Taux ∈ [0;40], codes métro, SANITY 2023 Melodi |
| Créations d’entreprises | **INSEE** Melodi SIDE | Idem | Département × année | Série récente | Proxy dynamisme économique / 10k hab. | Créations/10k > 0, SANITY 2021 |

## Critères transverses de sélection
1. **Publicité & licence** — réutilisation autorisée, citation possible.
2. **Maille département** — alignée sur le grain électoral du POC.
3. **Série temporelle** — suffisamment longue pour anti-leakage (features ≤ N−1).
4. **Traçabilité** — URL catalogue stable + fichiers archivés dans `data/raw/`.
5. **SANITY anti-démo** — ordres de grandeur INSEE sur 75 / 01 / 23.

## Les 16 contrôles DQM du pipeline (journal `data/quality_report.txt`)

| # | Couche | Contrôle |
|---|---|---|
| 1–6 | Bronze | Codes département ∈ métropole (6 tables sources) |
| 7 | Silver | % blocs ∈ [0;100] |
| 8 | Silver | Somme des % ≈ 100 (±5) |
| 9 | Silver | Chômage ∈ [0;30] |
| 10 | Silver | Trimestre ∈ {1..4} |
| 11 | Silver | Emploi total > 0 |
| 12 | Silver | Population > 0 |
| 13 | Silver | Pauvreté ∈ [0;40] |
| 14 | Silver | Créations entreprises > 0 |
| 15 | Gold | `taux_chomage_n1` renseigné |
| 16 | Gold | Unicité clé `(code_dept, annee)` |

Compléments : manifests JSON par couche, tests `pytest`, suite Great Expectations (`gx/`).

## Mapping candidat → bloc
Voir `etl/mapping_blocs.py` (EXG / GAU / CEN / DRO / EXD) — choix pédagogique documenté, modifiable, rejouable.

## Phrase orale (niveau 3)
« Chaque source est justifiée (licence, maille, série), validée par 16 contrôles DQM + SANITY anti-démo, et tracée RAW→Bronze→Silver→Gold. »
