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
                print("[schema] GOLD 0 ligne")
                return True
            # Postgres plie les identifiants non quotés en minuscules
            n_new = con.execute(text(
                "SELECT COUNT(*) FROM gold_dataset_analytique "
                "WHERE ecart_exg IS NOT NULL OR pct_exg_national IS NOT NULL"
            )).scalar()
            print(f"[schema] n={n} n_ecart_ou_national={n_new}")
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


def gold_diagnostics(eng=None) -> dict:
    """État GOLD pour les logs Render (colonnes, nulls, échantillon)."""
    import traceback
    eng = eng or get_engine()
    info = {"ok": False}
    try:
        raw_cols = sorted(_existing_columns(eng, "gold_dataset_analytique"))
        info["colonnes_pg"] = raw_cols
        df = canonicalize_gold_df(
            pd.read_sql("SELECT * FROM gold_dataset_analytique", eng)
        )
        info["n_lignes"] = int(len(df))
        info["colonnes_canon"] = list(df.columns)
        watch = (
            ["bloc_gagnant", "annee", "code_dept"]
            + [f"pct_{b}" for b in BLOCS]
            + [f"ecart_{b}" for b in BLOCS]
            + [f"ecart_{b}_prec" for b in BLOCS]
            + [f"pct_{b}_national" for b in BLOCS]
        )
        nn = {}
        for c in watch:
            if c in df.columns:
                nn[c] = int(pd.to_numeric(df[c], errors="coerce").notna().sum()) if c not in (
                    "bloc_gagnant", "code_dept"
                ) else int(df[c].notna().sum())
            else:
                nn[c] = "ABSENT"
        info["non_null"] = nn
        if "annee" in df.columns and len(df):
            info["annees"] = sorted(pd.to_numeric(df["annee"], errors="coerce").dropna().astype(int).unique().tolist())
        if len(df):
            sample = df.iloc[0].to_dict()
            info["sample0"] = {k: (None if pd.isna(v) else v) for k, v in list(sample.items())[:20]}
        try:
            fait = pd.read_sql("SELECT * FROM fait_resultat_election", eng)
            info["fait_n"] = int(len(fait))
            info["fait_colonnes"] = list(fait.columns)
            fnn = {}
            for c in fait.columns:
                cl = str(c).lower()
                if cl.startswith("pct_") or cl in ("bloc_gagnant", "inscrits"):
                    fnn[str(c)] = int(fait[c].notna().sum())
            info["fait_non_null"] = fnn
        except Exception as fe:
            info["fait_error"] = str(fe)
        info["ok"] = True
    except Exception as e:
        info["error"] = str(e)
        info["traceback"] = traceback.format_exc()
    print("[debug:gold] " + str({k: v for k, v in info.items() if k != "sample0"}))
    return info


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


def silver_gold_available() -> bool:
    return os.path.isfile(os.path.join(SILVER, "elections.csv")) and os.path.isfile(
        os.path.join(GOLD, "dataset_analytique.csv")
    )


def _lag_from_priors(values: list, years: list, ndigits: int = 2) -> tuple:
    """Dérivées anti-leakage : uniquement les observations d'indice < i."""
    n = len(values)
    prec, d_rec, d_long, trend, vol = [], [], [], [], []
    for i in range(n):
        prior_s = values[:i]
        prior_y = years[:i]
        if not prior_s:
            prec.append(None)
            d_rec.append(None)
            d_long.append(None)
            trend.append(None)
            vol.append(None)
            continue
        p_last = prior_s[-1]
        prec.append(round(p_last, ndigits))
        d_rec.append(
            round(p_last - prior_s[-2], ndigits) if len(prior_s) >= 2 else None
        )
        p_first = prior_s[0]
        y_first, y_last = prior_y[0], prior_y[-1]
        dl = p_last - p_first
        d_long.append(round(dl, ndigits))
        span = y_last - y_first
        trend.append(round(dl / span, 4) if span > 0 else None)
        if len(prior_s) >= 2:
            vol.append(round(float(pd.Series(prior_s).std(ddof=1)), 4))
        else:
            vol.append(None)
    return prec, d_rec, d_long, trend, vol


def _hydrate_pct_from_fait(gold: pd.DataFrame, eng) -> pd.DataFrame:
    """Copie pct_* / inscrits depuis fait_resultat_election (GOLD Aiven incomplète)."""
    try:
        fait = pd.read_sql("SELECT * FROM fait_resultat_election", eng)
    except Exception as e:
        print(f"[enrich] fait_resultat_election illisible : {e}")
        return gold
    if fait is None or fait.empty:
        print("[enrich] fait_resultat_election vide")
        return gold

    fait = fait.copy()
    fait.columns = [str(c).lower() for c in fait.columns]
    gold = gold.copy()
    gold["_k_an"] = pd.to_numeric(gold["annee"], errors="coerce").astype("Int64")
    gold["_k_dep"] = gold["code_dept"].astype(str).str.strip().str.zfill(2)
    fait["_k_an"] = pd.to_numeric(fait["annee"], errors="coerce").astype("Int64")
    fait["_k_dep"] = fait["code_dept"].astype(str).str.strip().str.zfill(2)

    keep = ["_k_an", "_k_dep"]
    ren = {}
    for b in BLOCS:
        src = f"pct_{b.lower()}"
        if src in fait.columns:
            keep.append(src)
            ren[src] = f"_fait_pct_{b}"
    if "inscrits" in fait.columns:
        keep.append("inscrits")
        ren["inscrits"] = "_fait_inscrits"
    f2 = fait[keep].drop_duplicates(["_k_an", "_k_dep"]).rename(columns=ren)
    print(f"[enrich] fait n={len(fait)} join_cols={list(f2.columns)}")
    gold = gold.merge(f2, on=["_k_an", "_k_dep"], how="left")

    for b in BLOCS:
        src = f"_fait_pct_{b}"
        dest = f"pct_{b}"
        if src not in gold.columns:
            continue
        incoming = pd.to_numeric(gold[src], errors="coerce")
        current = (
            pd.to_numeric(gold[dest], errors="coerce")
            if dest in gold.columns
            else pd.Series(pd.NA, index=gold.index)
        )
        gold[dest] = current.where(current.notna(), incoming)
        gold.drop(columns=[src], inplace=True)
        print(f"[enrich] hydrate {dest} non-null={int(gold[dest].notna().sum())}/{len(gold)}")
    if "_fait_inscrits" in gold.columns:
        incoming = pd.to_numeric(gold["_fait_inscrits"], errors="coerce")
        current = (
            pd.to_numeric(gold["inscrits"], errors="coerce")
            if "inscrits" in gold.columns
            else pd.Series(pd.NA, index=gold.index)
        )
        gold["inscrits"] = current.where(current.notna(), incoming)
        gold.drop(columns=["_fait_inscrits"], inplace=True)
    gold.drop(columns=["_k_an", "_k_dep"], inplace=True)
    return gold


def enrich_gold_ecarts(eng=None) -> int:
    """Recalcule national + écarts + lags à partir des pct_* déjà en base.

    Sur Render les CSV silver/gold sont absents : on enrichit la GOLD Aiven
    sans TRUNCATE des faits (la carte continue de marcher).
    """
    eng = eng or get_engine()
    ensure_schema(eng)
    gold = canonicalize_gold_df(
        pd.read_sql("SELECT * FROM gold_dataset_analytique", eng)
    )
    print(f"[enrich] start n={0 if gold is None else len(gold)} cols={list(gold.columns) if gold is not None else []}")
    if gold is None or gold.empty:
        raise RuntimeError("GOLD vide — impossible d'enrichir les écarts")

    gold = _hydrate_pct_from_fait(gold, eng)

    missing_pct = [f"pct_{b}" for b in BLOCS if f"pct_{b}" not in gold.columns]
    if missing_pct:
        print(f"[enrich] colonnes brutes={list(gold.columns)}")
        raise RuntimeError(f"GOLD sans scores de blocs : {missing_pct}")
    for b in BLOCS:
        nn = int(pd.to_numeric(gold[f"pct_{b}"], errors="coerce").notna().sum())
        print(f"[enrich] pct_{b} non-null={nn}/{len(gold)}")

    gold = gold.sort_values(["code_dept", "annee"]).reset_index(drop=True)
    has_inscrits = (
        "inscrits" in gold.columns
        and pd.to_numeric(gold["inscrits"], errors="coerce").fillna(0).sum() > 0
    )

    for an, idx in gold.groupby("annee").groups.items():
        g = gold.loc[idx]
        if has_inscrits:
            w = pd.to_numeric(g["inscrits"], errors="coerce").fillna(0).astype(float)
            sw = float(w.sum())
        else:
            w = pd.Series(1.0, index=g.index)
            sw = float(len(g))
        if sw <= 0:
            continue
        for b in BLOCS:
            scores = pd.to_numeric(g[f"pct_{b}"], errors="coerce")
            nat = float((scores * w).sum() / sw)
            gold.loc[idx, f"pct_{b}_national"] = round(nat, 4)
            gold.loc[idx, f"ecart_{b}"] = (scores - nat).round(4)

    parts = []
    for _, sub in gold.groupby("code_dept", sort=False):
        sub = sub.sort_values("annee").copy()
        years = sub["annee"].astype(int).tolist()
        for b in BLOCS:
            prec, d_rec, d_long, trend, vol = _lag_from_priors(
                pd.to_numeric(sub[f"pct_{b}"], errors="coerce").astype(float).tolist(),
                years,
                ndigits=2,
            )
            sub[f"pct_{b}_prec"] = prec
            sub[f"delta_recent_{b}"] = d_rec
            sub[f"delta_long_{b}"] = d_long
            sub[f"trend_{b}"] = trend
            sub[f"volatility_{b}"] = vol
            prec_e, d_rec_e, d_long_e, trend_e, vol_e = _lag_from_priors(
                pd.to_numeric(sub[f"ecart_{b}"], errors="coerce").astype(float).tolist(),
                years,
                ndigits=4,
            )
            sub[f"ecart_{b}_prec"] = prec_e
            sub[f"delta_recent_ecart_{b}"] = d_rec_e
            sub[f"delta_long_ecart_{b}"] = d_long_e
            sub[f"trend_ecart_{b}"] = trend_e
            sub[f"volatility_ecart_{b}"] = vol_e
        parts.append(sub)
    gold = pd.concat(parts, ignore_index=True)

    n_prec = int(pd.to_numeric(gold["ecart_EXG_prec"], errors="coerce").notna().sum())
    n_ecart = int(pd.to_numeric(gold["ecart_EXG"], errors="coerce").notna().sum())
    print(f"[enrich] apres calcul ecart_EXG={n_ecart} ecart_EXG_prec={n_prec} / {len(gold)}")
    if n_prec == 0:
        raise RuntimeError("Enrichissement écarts : toujours 0 ligne avec ecart_*_prec")

    pg_cols = _existing_columns(eng, "gold_dataset_analytique")
    pg_by_lower = {c.lower(): c for c in pg_cols}
    to_pg = {
        c: pg_by_lower[c.lower()]
        for c in gold.columns
        if c.lower() in pg_by_lower
    }
    out = gold.rename(columns=to_pg)[list(to_pg.values())]
    with eng.begin() as con:
        con.execute(text("TRUNCATE TABLE gold_dataset_analytique"))
        out.to_sql("gold_dataset_analytique", con, if_exists="append", index=False)
    print(f"[schema] GOLD enrichie in-place ({n_prec} lignes avec ecart_*_prec)")
    return n_prec


def refresh_if_needed() -> str:
    """Recharge depuis CSV si dispo, sinon enrichit la GOLD déjà en base."""
    gold_diagnostics()
    outdated = schema_outdated()
    print(f"[refresh] schema_outdated={outdated} csv={silver_gold_available()}")
    if not outdated:
        print("[startup] GOLD a jour, skip load")
        return "skip"
    if silver_gold_available():
        print("[startup] GOLD absente/obsolete -> reload SILVER/GOLD...")
        load()
        return "csv"
    print("[startup] CSV silver/gold absents -> enrichissement GOLD in-place")
    enrich_gold_ecarts()
    return "enrich"


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
