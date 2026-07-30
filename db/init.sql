-- =====================================================================
-- Schema PostgreSQL - application Electio-Analytics (BI)
-- Modele en etoile : dimensions + faits + table gold analytique + KPI.
-- =====================================================================

CREATE TABLE IF NOT EXISTS dim_departement (
    code_dept  TEXT PRIMARY KEY,
    libelle    TEXT,
    region     TEXT
);

CREATE TABLE IF NOT EXISTS dim_annee (
    annee               INTEGER PRIMARY KEY,
    est_annee_election  BOOLEAN
);

CREATE TABLE IF NOT EXISTS dim_bloc (
    bloc     TEXT PRIMARY KEY,
    libelle  TEXT,
    axe      INTEGER
);

CREATE TABLE IF NOT EXISTS fait_resultat_election (
    annee        INTEGER,
    code_dept    TEXT REFERENCES dim_departement(code_dept),
    inscrits     INTEGER,
    pct_exg      REAL,
    pct_gau      REAL,
    pct_cen      REAL,
    pct_dro      REAL,
    pct_exd      REAL,
    bloc_gagnant TEXT,
    PRIMARY KEY (annee, code_dept)
);

CREATE TABLE IF NOT EXISTS gold_dataset_analytique (
    annee                     INTEGER,
    code_dept                 TEXT REFERENCES dim_departement(code_dept),
    taux_chomage_n1           REAL,
    delta_chomage_1a          REAL,
    delta_chomage_5a          REAL,
    emploi_pour_1000hab       REAL,
    croissance_emploi_5a_pct  REAL,
    croissance_pop_5a_pct     REAL,
    taux_pauvrete_n1          REAL,
    creations_entreprises_n1  REAL,
    bloc_gagnant              TEXT,
    pct_gagnant               REAL,
    marge_gagnante            REAL,
    bloc_gagnant_precedent    TEXT,
    pct_gagnant_precedent     REAL,
    marge_gagnante_precedente REAL,
    PRIMARY KEY (annee, code_dept)
);

CREATE TABLE IF NOT EXISTS kpi_evolution_blocs (
    annee           INTEGER,
    bloc            TEXT,
    n_departements  INTEGER,
    part_pct        REAL
);

CREATE TABLE IF NOT EXISTS kpi_completude_features (
    feature         TEXT,
    completude_pct  REAL,
    n_non_null      INTEGER
);

CREATE TABLE IF NOT EXISTS kpi_chomage_vs_bloc (
    bloc            TEXT,
    chomage_moyen   REAL,
    chomage_median  REAL,
    n               INTEGER
);

CREATE INDEX IF NOT EXISTS idx_gold_dept  ON gold_dataset_analytique(code_dept);
CREATE INDEX IF NOT EXISTS idx_gold_annee ON gold_dataset_analytique(annee);
