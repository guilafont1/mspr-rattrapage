# -*- coding: utf-8 -*-
"""
Chargement des donnees dans PostgreSQL a partir des couches SILVER/GOLD.

Ordre :
  1. ensure_schema() applique db/init.sql + migrations de colonnes
  2. TRUNCATE + INSERT dims / faits / gold / kpi

Idempotent. Recharge automatiquement si le schema GOLD est obsolete.
"""
from __future__ import annotations

import os
import sys

import pandas as pd
from sqlalchemy import text
from database import get_engine

ROOT = os.path.join(os.path.dirname(__file__), "..")
GOLD = os.path.join(ROOT, "data", "gold")
SILVER = os.path.join(ROOT, "data", "silver")
INIT_SQL = os.path.join(ROOT, "db", "init.sql")

sys.path.insert(0, os.path.join(ROOT, "etl"))
from referentiels import BLOCS, dim_departement_frame  # noqa: E402

DIM_BLOC = pd.DataFrame({
    "bloc": list(BLOCS),
    "libelle": ["Extreme gauche", "Gauche", "Centre", "Droite", "Extreme droite"],
    "axe": [-2, -1, 0, 1, 2],
})

# Colonnes GOLD attendues (apres enrichissement medaillon + regression multi-sorties)
GOLD_REQUIRED_COLS = [
    "annee", "code_dept",
    "taux_chomage_n1", "delta_chomage_1a", "delta_chomage_5a",
    "emploi_pour_1000hab", "croissance_emploi_5a_pct", "croissance_pop_5a_pct",
    "taux_pauvrete_n1", "creations_entreprises_n1",
    "bloc_gagnant", "pct_gagnant", "marge_gagnante",
    "bloc_gagnant_precedent", "pct_gagnant_precedent", "marge_gagnante_precedente",
    "pct_EXG", "pct_GAU", "pct_CEN", "pct_DRO", "pct_EXD",
    "pct_EXG_prec", "pct_GAU_prec", "pct_CEN_prec", "pct_DRO_prec", "pct_EXD_prec",
    "delta_recent_EXG", "delta_recent_GAU", "delta_recent_CEN",
    "delta_recent_DRO", "delta_recent_EXD",
    "volatility_EXG", "volatility_GAU", "volatility_CEN",
    "volatility_DRO", "volatility_EXD",
    "inscrits",
    "pct_EXG_national", "pct_GAU_national", "pct_CEN_national",
    "pct_DRO_national", "pct_EXD_national",
    "ecart_EXG", "ecart_GAU", "ecart_CEN", "ecart_DRO", "ecart_EXD",
    "ecart_EXG_prec", "ecart_GAU_prec", "ecart_CEN_prec",
    "ecart_DRO_prec", "ecart_EXD_prec",
    "delta_recent_ecart_EXG", "delta_recent_ecart_GAU",
    "delta_recent_ecart_CEN", "delta_recent_ecart_DRO",
    "delta_recent_ecart_EXD",
    "volatility_ecart_EXG", "volatility_ecart_GAU",
    "volatility_ecart_CEN", "volatility_ecart_DRO",
    "volatility_ecart_EXD",
]

GOLD_ALTER = {
    "delta_chomage_1a": "REAL",
    "croissance_pop_5a_pct": "REAL",
    "pct_gagnant": "REAL",
    "marge_gagnante": "REAL",
    "pct_gagnant_precedent": "REAL",
    "marge_gagnante_precedente": "REAL",
    "pct_EXG": "REAL", "pct_GAU": "REAL", "pct_CEN": "REAL",
    "pct_DRO": "REAL", "pct_EXD": "REAL",
    "pct_EXG_prec": "REAL", "pct_GAU_prec": "REAL", "pct_CEN_prec": "REAL",
    "pct_DRO_prec": "REAL", "pct_EXD_prec": "REAL",
    "delta_recent_EXG": "REAL", "delta_recent_GAU": "REAL",
    "delta_recent_CEN": "REAL", "delta_recent_DRO": "REAL",
    "delta_recent_EXD": "REAL",
    "delta_long_EXG": "REAL", "delta_long_GAU": "REAL",
    "delta_long_CEN": "REAL", "delta_long_DRO": "REAL",
    "delta_long_EXD": "REAL",
    "trend_EXG": "REAL", "trend_GAU": "REAL", "trend_CEN": "REAL",
    "trend_DRO": "REAL", "trend_EXD": "REAL",
    "volatility_EXG": "REAL", "volatility_GAU": "REAL",
    "volatility_CEN": "REAL", "volatility_DRO": "REAL",
    "volatility_EXD": "REAL",
    "inscrits": "INTEGER",
    "pct_EXG_national": "REAL", "pct_GAU_national": "REAL",
    "pct_CEN_national": "REAL", "pct_DRO_national": "REAL",
    "pct_EXD_national": "REAL",
    "ecart_EXG": "REAL", "ecart_GAU": "REAL", "ecart_CEN": "REAL",
    "ecart_DRO": "REAL", "ecart_EXD": "REAL",
    "ecart_EXG_prec": "REAL", "ecart_GAU_prec": "REAL",
    "ecart_CEN_prec": "REAL", "ecart_DRO_prec": "REAL",
    "ecart_EXD_prec": "REAL",
    "delta_recent_ecart_EXG": "REAL", "delta_recent_ecart_GAU": "REAL",
    "delta_recent_ecart_CEN": "REAL", "delta_recent_ecart_DRO": "REAL",
    "delta_recent_ecart_EXD": "REAL",
    "delta_long_ecart_EXG": "REAL", "delta_long_ecart_GAU": "REAL",
    "delta_long_ecart_CEN": "REAL", "delta_long_ecart_DRO": "REAL",
    "delta_long_ecart_EXD": "REAL",
    "trend_ecart_EXG": "REAL", "trend_ecart_GAU": "REAL",
    "trend_ecart_CEN": "REAL", "trend_ecart_DRO": "REAL",
    "trend_ecart_EXD": "REAL",
    "volatility_ecart_EXG": "REAL", "volatility_ecart_GAU": "REAL",
    "volatility_ecart_CEN": "REAL", "volatility_ecart_DRO": "REAL",
    "volatility_ecart_EXD": "REAL",
}


def ensure_schema(eng=None):
    eng = eng or get_engine()
    if not os.path.isfile(INIT_SQL):
        raise FileNotFoundError(f"Schema introuvable : {INIT_SQL}")
    sql = open(INIT_SQL, encoding="utf-8").read()
    raw = eng.raw_connection()
    try:
        cur = raw.cursor()
        cur.execute(sql)
        # Migrations soft : ADD COLUMN si table deja creee avec ancien schema
        for col, typ in GOLD_ALTER.items():
            cur.execute(
                f"ALTER TABLE gold_dataset_analytique "
                f"ADD COLUMN IF NOT EXISTS {col} {typ}"
            )
        raw.commit()
        cur.close()
    finally:
        raw.close()
    print(f"Schema applique depuis {INIT_SQL}")


def _existing_columns(eng, table: str) -> set[str]:
    with eng.connect() as con:
        rows = con.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = :t"
        ), {"t": table}).fetchall()
    return {r[0] for r in rows}


def schema_outdated() -> bool:
    """True si GOLD absente, vide, ou sans les colonnes du contrat actuel."""
    eng = get_engine()
    try:
        cols = {c.lower() for c in _existing_columns(eng, "gold_dataset_analytique")}
        if not cols:
            return True
        missing = [c for c in GOLD_REQUIRED_COLS if c.lower() not in cols]
        if missing:
            print(f"[schema] colonnes GOLD manquantes : {missing}")
            return True
        with eng.connect() as con:
            n = con.execute(text("SELECT COUNT(*) FROM gold_dataset_analytique")).scalar()
            if (n or 0) == 0:
                return True
            # Jeu charge avant enrichissement multi-sorties : nouvelles colonnes NULL
            n_new = con.execute(text(
                "SELECT COUNT(*) FROM gold_dataset_analytique "
                "WHERE ecart_EXG IS NOT NULL OR pct_EXG_national IS NOT NULL"
            )).scalar()
            if (n_new or 0) == 0:
                print("[schema] GOLD presente mais decomposition nationale/ecart vide -> reload")
                return True
        return False
    except Exception as e:
        print(f"[schema] outdated check KO : {e}")
        return True


GOLD_CANON = {}
for _c in list(GOLD_REQUIRED_COLS) + list(GOLD_ALTER.keys()):
    GOLD_CANON[_c.lower()] = _c
GOLD_CANON.update({
    "annee": "annee",
    "code_dept": "code_dept",
    "libelle": "libelle",
})


def canonicalize_gold_df(df: pd.DataFrame) -> pd.DataFrame:
    """Aligne les noms Postgres (souvent minuscules) sur le contrat GOLD."""
    if df is None or df.empty:
        return df
    rename = {}
    for c in df.columns:
        canon = GOLD_CANON.get(str(c).lower())
        if canon and canon != c:
            rename[c] = canon
    return df.rename(columns=rename) if rename else df


def _load_kpi(con, name: str, path: str):
    if not os.path.isfile(path):
        print(f"[WARN] KPI absent : {path}")
        return
    df = pd.read_csv(path)
    df.to_sql(name, con, if_exists="append", index=False)


def load():
    eng = get_engine()
    ensure_schema(eng)

    elec = pd.read_csv(f"{SILVER}/elections.csv", dtype={"code_dept": str})
    gold = pd.read_csv(f"{GOLD}/dataset_analytique.csv", dtype={"code_dept": str})
    elec = elec.rename(columns={c: c.lower() for c in elec.columns})

    dep = dim_departement_frame()
    dep = dep[dep["code_dept"].isin(gold["code_dept"].unique())].copy()
    ann = pd.DataFrame({"annee": sorted(gold["annee"].unique().astype(int).tolist())})
    ann["est_annee_election"] = True

    with eng.begin() as con:
        # Tables KPI peuvent ne pas exister sur tres ancienne base
        con.execute(text(
            "TRUNCATE TABLE "
            "kpi_chomage_vs_bloc, kpi_completude_features, kpi_evolution_blocs, "
            "gold_dataset_analytique, fait_resultat_election, "
            "dim_annee, dim_departement, dim_bloc "
            "RESTART IDENTITY CASCADE"
        ))
        dep.to_sql("dim_departement", con, if_exists="append", index=False)
        ann.to_sql("dim_annee", con, if_exists="append", index=False)
        DIM_BLOC.to_sql("dim_bloc", con, if_exists="append", index=False)
        cols = ["annee", "code_dept", "inscrits", "pct_exg", "pct_gau",
                "pct_cen", "pct_dro", "pct_exd", "bloc_gagnant"]
        elec[[c for c in cols if c in elec.columns]].to_sql(
            "fait_resultat_election", con, if_exists="append", index=False)
        # N'inserer que les colonnes presentes dans le CSV ET dans Postgres
        pg_cols = _existing_columns(eng, "gold_dataset_analytique")
        pg_by_lower = {c.lower(): c for c in pg_cols}
        gold_c = canonicalize_gold_df(gold)
        to_pg = {
            c: pg_by_lower[c.lower()]
            for c in gold_c.columns
            if c.lower() in pg_by_lower
        }
        if to_pg:
            gold_c.rename(columns=to_pg)[list(to_pg.values())].to_sql(
                "gold_dataset_analytique", con, if_exists="append", index=False
            )
        _load_kpi(con, "kpi_evolution_blocs", f"{GOLD}/kpi_evolution_blocs.csv")
        _load_kpi(con, "kpi_completude_features", f"{GOLD}/kpi_completude_features.csv")
        _load_kpi(con, "kpi_chomage_vs_bloc", f"{GOLD}/kpi_chomage_vs_bloc.csv")
    print("Chargement Postgres termine (dims + faits + gold + kpi).")


def is_empty() -> bool:
    return schema_outdated()


if __name__ == "__main__":
    load()
