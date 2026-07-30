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
-- dans 02_transform.py ; ce fichier documente le schema cible et cree les
-- dimensions de reference + des index utiles aux requetes analytiques.

-- Index conseilles (crees apres chargement dans 02_transform.py) :
--   CREATE INDEX idx_gold_dept ON gold_dataset_analytique(code_dept);
--   CREATE INDEX idx_gold_annee ON gold_dataset_analytique(annee);
