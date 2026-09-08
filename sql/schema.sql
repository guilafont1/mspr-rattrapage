-- =====================================================================
-- Schema de la base analytique POC Electio-Analytics (SQLite / Postgres)
--
-- CHOIX DE MODELISATION (argumentaire MSPR — compétence entrepôt) :
--
-- 1) ETOILE (retenu)
--    - Faits au centre, dimensions dénormalisées autour
--    - Avantage : requêtes BI simples, performance lecture, pédagogique
--    - Adapte au POC : peu de dimensions, charges analytiques (ML + Dash)
--
-- 2) FLOCON (evalue, non retenu)
--    - Dimensions normalisees (ex. region -> departement)
--    - Avantage : moins de redondance
--    - Inconvenient ici : jointures plus complexes pour peu de gain
--      (volumetrie faible : ~480 obs GOLD)
--
-- 3) GRAPPE / constellation (evalue, partiel)
--    - Plusieurs faits partageant des dimensions (elections, chomage, emploi)
--    - Present dans le POC via plusieurs fait_* + dims communes
--    - La table gold_ denormalise pour ML/BI (couche de service)
--
-- Convention : prefixe dim_/fait_/gold_, colonnes snake_case.
-- =====================================================================

CREATE TABLE IF NOT EXISTS dim_departement (
    code_dept   TEXT PRIMARY KEY,      -- '69'
    libelle     TEXT,                  -- 'Rhone'
    region      TEXT                   -- rattachement regional (optionnel)
);

CREATE TABLE IF NOT EXISTS dim_annee (
    annee            INTEGER PRIMARY KEY,
    est_annee_election INTEGER          -- 1 si scrutin presidentiel
);

CREATE TABLE IF NOT EXISTS dim_bloc (
    bloc     TEXT PRIMARY KEY,         -- EXG/GAU/CEN/DRO/EXD
    libelle  TEXT,
    axe      INTEGER                   -- position gauche(-) / droite(+)
);

-- Les tables de faits et la table gold sont (re)creees par pandas.to_sql
-- dans 02_transform.py. Schema cible GOLD (regression multi-sorties) :
--   cibles : pct_EXG..pct_EXD et ecart_EXG..ecart_EXD
--   niveau national : pct_{B}_national (pondere par inscrits)
--   features electorales anti-leakage : pct_{B}_prec, delta_recent_{B},
--     delta_long_{B}, trend_{B}, volatility_{B}
--   features d'ecart anti-leakage : ecart_{B}_prec, delta_recent_ecart_{B},
--     delta_long_ecart_{B}, trend_ecart_{B}, volatility_ecart_{B}
--   + features socio-eco N-1 et lags politiques existants.
-- Voir aussi db/init.sql (PostgreSQL).

-- Index conseilles (crees apres chargement dans 02_transform.py) :
--   CREATE INDEX idx_gold_dept ON gold_dataset_analytique(code_dept);
--   CREATE INDEX idx_gold_annee ON gold_dataset_analytique(annee);
