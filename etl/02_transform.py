# -*- coding: utf-8 -*-
"""
ETL - Etape 2 : BRONZE -> SILVER -> GOLD (architecture medaillon)

Couches :
  RAW    : fichiers sources immuables (data/raw/) — hors de ce script
  BRONZE : contrat normalise (CSV schemas stables) — lu ici, jamais reecrit
  SILVER : nettoyage DQM + enrichissement metier (agregeats annuels, jointures)
  GOLD   : grain analytique 1 ligne = 1 (departement, election) + KPI + SQLite

Anti data-leakage : pour un scrutin N, toutes les features socio-eco
proviennent d'annees <= N-1 ; le lag politique vient du scrutin precedent.
"""
from __future__ import annotations

import json
import os
import sys
import sqlite3
from datetime import datetime, timezone

import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from referentiels import BLOCS, BRONZE_SCHEMAS, METRO_DEPTS, dim_departement_frame

ROOT = os.path.join(os.path.dirname(__file__), "..", "data")
BRONZE, SILVER, GOLD = (os.path.join(ROOT, x) for x in ("bronze", "silver", "gold"))
SQL = os.path.join(os.path.dirname(__file__), "..", "sql")
for d in (SILVER, GOLD):
    os.makedirs(d, exist_ok=True)

qlog: list[str] = []


def check(name: str, cond, df: pd.DataFrame, fatal: bool = True) -> int:
    n_bad = int((~cond).sum()) if hasattr(cond, "sum") else int(not cond)
    ok = n_bad == 0
    qlog.append(f"[{'OK ' if ok else 'KO '}] {name}: {len(df)} lignes, {n_bad} violations")
    if not ok and fatal:
        raise ValueError(f"Qualite KO -- {name} ({n_bad} violations)")
    return n_bad


def load_bronze(name: str) -> pd.DataFrame:
    path = os.path.join(BRONZE, name)
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Bronze manquant : {path}")
    expected = BRONZE_SCHEMAS.get(name)
    df = pd.read_csv(path, dtype={"code_dept": str})
    if expected:
        missing = [c for c in expected if c not in df.columns]
        if missing:
            raise ValueError(f"{name}: colonnes manquantes {missing}")
        df = df.reindex(columns=expected)
    if "code_dept" in df.columns:
        df["code_dept"] = df["code_dept"].astype(str).str.strip()
        check(f"{name}: codes metro", df["code_dept"].isin(METRO_DEPTS), df)
    return df


def write_manifest(layer: str, folder: str, tables: dict[str, pd.DataFrame], extra: dict | None = None):
    payload = {
        "layer": layer,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "tables": {
            name: {
                "rows": int(len(df)),
                "columns": list(df.columns),
                "null_rate": {c: round(float(df[c].isna().mean()), 4) for c in df.columns},
            }
            for name, df in tables.items()
        },
    }
    if extra:
        payload.update(extra)
    path = os.path.join(folder, f"{layer.lower()}_manifest.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    return path


# ---------------------------------------------------------------------------
# SILVER — DQM + enrichissement metier
# ---------------------------------------------------------------------------
print("=== SILVER : DQM + enrichissement ===")

elec = load_bronze("elections_presidentielles_t1.csv").drop_duplicates(["annee", "code_dept"])
pct_cols = [f"pct_{b}" for b in BLOCS]
check("elections: pct dans [0;100]", elec[pct_cols].apply(lambda s: s.between(0, 100)).all(axis=1), elec)
elec["somme_pct"] = elec[pct_cols].sum(axis=1).round(2)
# Tolerance 2 pts (arrondis / candidats hors blocs)
check("elections: somme pct ~ 100", elec["somme_pct"].between(95, 105), elec)
elec["bloc_gagnant"] = elec[pct_cols].idxmax(axis=1).str.replace("pct_", "", regex=False)
elec["pct_gagnant"] = elec[pct_cols].max(axis=1).round(2)
# 2e score pour marge
second = elec[pct_cols].apply(lambda r: sorted(r.values, reverse=True)[1], axis=1)
elec["marge_gagnante"] = (elec["pct_gagnant"] - second).round(2)
elec["concentration_top2"] = (elec["pct_gagnant"] + second).round(2)

chom = load_bronze("chomage_localise_trim.csv").drop_duplicates(["code_dept", "annee", "trimestre"])
check("chomage: taux dans [0;30]", chom["taux_chomage"].between(0, 30), chom)
check("chomage: trimestre 1..4", chom["trimestre"].between(1, 4), chom)

emp = load_bronze("emploi_salarie_trim.csv").drop_duplicates(["code_dept", "annee", "trimestre"])
check("emploi: total > 0", emp["emploi_total"] > 0, emp)

pop = load_bronze("population_dept.csv").drop_duplicates(["code_dept", "annee"])
check("population: > 0", pop["population"] > 0, pop)

pauv = load_bronze("pauvrete_dept.csv").drop_duplicates(["code_dept", "annee"])
check("pauvrete: dans [0;40]", pauv["taux_pauvrete"].between(0, 40), pauv)

ent = load_bronze("entreprises_dept.csv").drop_duplicates(["code_dept", "annee"])
check("entreprises: > 0", ent["creations_entreprises_10k"] > 0, ent)

# Agregats annuels (enrichissement Silver)
chom_y = (
    chom.groupby(["code_dept", "annee"], as_index=False)
    .agg(taux_chomage=("taux_chomage", "mean"), n_trim_chomage=("taux_chomage", "count"))
)
chom_y["taux_chomage"] = chom_y["taux_chomage"].round(2)

emp_y = (
    emp.groupby(["code_dept", "annee"], as_index=False)
    .agg(emploi_total=("emploi_total", "mean"), n_trim_emploi=("emploi_total", "count"))
)
emp_y["emploi_total"] = emp_y["emploi_total"].round(0)

# Panel socio-eco annuel joint (Silver enrichi)
socio = (
    pop.merge(chom_y, on=["code_dept", "annee"], how="left")
    .merge(emp_y, on=["code_dept", "annee"], how="left")
    .merge(pauv, on=["code_dept", "annee"], how="left")
    .merge(ent, on=["code_dept", "annee"], how="left")
)
socio["emploi_pour_1000hab"] = (
    socio["emploi_total"] / socio["population"] * 1000
).round(1)
# Completude panel (indicateur DQM)
socio["completude_score"] = (
    socio[["taux_chomage", "emploi_total", "taux_pauvrete", "creations_entreprises_10k"]]
    .notna().mean(axis=1).round(2)
)

silver_tables = {
    "elections.csv": elec,
    "chomage.csv": chom,
    "emploi.csv": emp,
    "population.csv": pop,
    "pauvrete.csv": pauv,
    "entreprises.csv": ent,
    "chomage_annuel.csv": chom_y,
    "emploi_annuel.csv": emp_y,
    "socioeco_annuel.csv": socio,
}
for name, df in silver_tables.items():
    df.to_csv(os.path.join(SILVER, name), index=False)
    print(f"[SILVER] {name}: {len(df)} lignes")

write_manifest(
    "SILVER", SILVER, silver_tables,
    extra={"dqm_ok": sum(1 for L in qlog if L.startswith("[OK ")),
           "role": "DQM + agregats annuels + panel socio-eco joint"},
)

# ---------------------------------------------------------------------------
# GOLD — grain electionnel + features anti-leakage + KPI
# ---------------------------------------------------------------------------
print("\n=== GOLD : table analytique + KPI ===")

chom_idx = chom_y.set_index(["code_dept", "annee"])["taux_chomage"]
emp_idx = emp_y.set_index(["code_dept", "annee"])["emploi_total"]
pop_idx = pop.set_index(["code_dept", "annee"])["population"]
pauv_idx = pauv.set_index(["code_dept", "annee"])["taux_pauvrete"]
ent_idx = ent.set_index(["code_dept", "annee"])["creations_entreprises_10k"]


def safe(series: pd.Series, key):
    try:
        v = series.loc[key]
        return float(v)
    except (KeyError, TypeError, ValueError):
        return None


rows = []
for _, e in elec.iterrows():
    an, d = int(e["annee"]), e["code_dept"]
    p = an - 1  # N-1 strict
    ch_p = safe(chom_idx, (d, p))
    ch_p1 = safe(chom_idx, (d, p - 1))
    ch_vals = [safe(chom_idx, (d, y)) for y in range(p - 4, p + 1)]
    ch_p5 = pd.Series(ch_vals).dropna().mean()
    em_p = safe(emp_idx, (d, p))
    em_p5 = safe(emp_idx, (d, p - 5))
    po_p = safe(pop_idx, (d, p))
    po_p5 = safe(pop_idx, (d, p - 5))
    pa_p = safe(pauv_idx, (d, p))
    en_p = safe(ent_idx, (d, p))

    row = {
        "annee": an,
        "code_dept": d,
        "taux_chomage_n1": round(ch_p, 2) if ch_p is not None else None,
        "delta_chomage_1a": round(ch_p - ch_p1, 2) if ch_p is not None and ch_p1 is not None else None,
        "delta_chomage_5a": round(ch_p - ch_p5, 2) if ch_p is not None and pd.notna(ch_p5) else None,
        "emploi_pour_1000hab": round(em_p / po_p * 1000, 1) if em_p and po_p else None,
        "croissance_emploi_5a_pct": round((em_p / em_p5 - 1) * 100, 2) if em_p and em_p5 else None,
        "croissance_pop_5a_pct": round((po_p / po_p5 - 1) * 100, 2) if po_p and po_p5 else None,
        "taux_pauvrete_n1": round(pa_p, 2) if pa_p is not None else None,
        "creations_entreprises_n1": round(en_p, 1) if en_p is not None else None,
        "bloc_gagnant": e["bloc_gagnant"],
        "pct_gagnant": e["pct_gagnant"],
        "marge_gagnante": e["marge_gagnante"],
        "inscrits": int(e["inscrits"]) if pd.notna(e.get("inscrits")) else None,
    }
    # Cibles du scrutin courant (regression multi-sorties)
    for b in BLOCS:
        row[f"pct_{b}"] = round(float(e[f"pct_{b}"]), 2)
    rows.append(row)

gold = pd.DataFrame(rows).sort_values(["code_dept", "annee"]).reset_index(drop=True)

# Lags politiques (scrutin precedent uniquement) — anti-leakage
g = gold.groupby("code_dept", group_keys=False)
gold["bloc_gagnant_precedent"] = g["bloc_gagnant"].shift(1)
gold["pct_gagnant_precedent"] = g["pct_gagnant"].shift(1)
gold["marge_gagnante_precedente"] = g["marge_gagnante"].shift(1)

def _lag_from_priors(values: list, years: list, ndigits: int = 2) -> tuple:
    """Derivees anti-leakage : uniquement les observations d'indice < i."""
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


# Features electorales par bloc : uniquement scrutins strictement anterieurs
# (boucle par departement pour garantir qu'aucune valeur courante n'entre).
elec_feat_cols: list[str] = []
ecart_feat_cols: list[str] = []
_parts = []
for _, sub in gold.groupby("code_dept", sort=False):
    sub = sub.sort_values("annee").copy()
    years = sub["annee"].astype(int).tolist()
    for b in BLOCS:
        prec, d_rec, d_long, trend, vol = _lag_from_priors(
            sub[f"pct_{b}"].astype(float).tolist(), years, ndigits=2,
        )
        sub[f"pct_{b}_prec"] = prec
        sub[f"delta_recent_{b}"] = d_rec
        sub[f"delta_long_{b}"] = d_long
        sub[f"trend_{b}"] = trend
        sub[f"volatility_{b}"] = vol
    _parts.append(sub)

gold = pd.concat(_parts, ignore_index=True).sort_values(["code_dept", "annee"]).reset_index(drop=True)
for b in BLOCS:
    elec_feat_cols.extend([
        f"pct_{b}_prec", f"delta_recent_{b}", f"delta_long_{b}",
        f"trend_{b}", f"volatility_{b}",
    ])

# Niveau national pondere par les inscrits + ecart departemental
# (somme(pct_B * inscrits) / somme(inscrits) ; voix brutes absentes en GOLD).
if gold["inscrits"].isna().any():
    raise ValueError("GOLD : inscrits manquants, ponderation nationale impossible")
for an, idx in gold.groupby("annee").groups.items():
    g = gold.loc[idx]
    w = g["inscrits"].astype(float)
    sw = float(w.sum())
    if sw <= 0:
        raise ValueError(f"GOLD : somme des inscrits nulle pour {an}")
    for b in BLOCS:
        nat = float((g[f"pct_{b}"] * w).sum() / sw)
        gold.loc[idx, f"pct_{b}_national"] = round(nat, 4)
        gold.loc[idx, f"ecart_{b}"] = (g[f"pct_{b}"] - nat).round(4)

# Derivees de l'ecart (meme logique anti-leakage, scrutins < N)
_parts = []
for _, sub in gold.groupby("code_dept", sort=False):
    sub = sub.sort_values("annee").copy()
    years = sub["annee"].astype(int).tolist()
    for b in BLOCS:
        prec, d_rec, d_long, trend, vol = _lag_from_priors(
            sub[f"ecart_{b}"].astype(float).tolist(), years, ndigits=4,
        )
        sub[f"ecart_{b}_prec"] = prec
        sub[f"delta_recent_ecart_{b}"] = d_rec
        sub[f"delta_long_ecart_{b}"] = d_long
        sub[f"trend_ecart_{b}"] = trend
        sub[f"volatility_ecart_{b}"] = vol
    _parts.append(sub)

gold = pd.concat(_parts, ignore_index=True).sort_values(["code_dept", "annee"]).reset_index(drop=True)
for b in BLOCS:
    ecart_feat_cols.extend([
        f"ecart_{b}", f"pct_{b}_national",
        f"ecart_{b}_prec", f"delta_recent_ecart_{b}", f"delta_long_ecart_{b}",
        f"trend_ecart_{b}", f"volatility_ecart_{b}",
    ])

check("gold: chomage_n1 renseigne", gold["taux_chomage_n1"].notna(), gold)
check("gold: unicite (dept, annee)", ~gold.duplicated(["code_dept", "annee"]), gold)
check(
    "gold: pct_* dans [0;100]",
    gold[[f"pct_{b}" for b in BLOCS]].apply(lambda s: s.between(0, 100)).all(axis=1),
    gold,
)
gold["somme_pct_cibles"] = gold[[f"pct_{b}" for b in BLOCS]].sum(axis=1).round(2)
check("gold: somme pct_* ~ 100", gold["somme_pct_cibles"].between(95, 105), gold)

# Somme des niveaux nationaux (constante par scrutin) dans [95;105]
nat_sum = gold[[f"pct_{b}_national" for b in BLOCS]].sum(axis=1).round(2)
check("gold: somme pct_*_national ~ 100", nat_sum.between(95, 105), gold)

# Moyenne ponderee des ecarts ~ 0 (construction : national = moyenne ponderee).
# Tolerance 0,15 pt : arrondi des pct a 2 decimales + national a 4.
_TOL_ECART_PONDERE = 0.15
for b in BLOCS:
    wm = []
    ok_mask = pd.Series(True, index=gold.index)
    for an, idx in gold.groupby("annee").groups.items():
        g = gold.loc[idx]
        w = g["inscrits"].astype(float)
        val = float((g[f"ecart_{b}"] * w).sum() / w.sum())
        wm.append(val)
        ok_mask.loc[idx] = abs(val) <= _TOL_ECART_PONDERE
    check(
        f"gold: moyenne ponderee ecart_{b} ~ 0 (tol={_TOL_ECART_PONDERE})",
        ok_mask, gold,
    )

# Controle anti-leakage : pct_{B}_prec = score du scrutin N-1
elec_prev = elec[["code_dept", "annee"] + [f"pct_{b}" for b in BLOCS]].copy()
elec_prev = elec_prev.rename(
    columns={"annee": "annee_prec", **{f"pct_{b}": f"_ref_{b}" for b in BLOCS}}
)
_chk = gold[["code_dept", "annee"]].copy()
_chk["annee_prec"] = gold.groupby("code_dept")["annee"].shift(1)
_chk = _chk.merge(elec_prev, on=["code_dept", "annee_prec"], how="left")
for b in BLOCS:
    both = gold[f"pct_{b}_prec"].notna() & _chk[f"_ref_{b}"].notna()
    match = (gold.loc[both, f"pct_{b}_prec"] - _chk.loc[both, f"_ref_{b}"]).abs() < 0.06
    check(f"gold: pct_{b}_prec = scrutin N-1", match, gold.loc[both])

# Controle anti-leakage : ecart_{B}_prec = ecart du scrutin N-1
for b in BLOCS:
    shifted = gold.groupby("code_dept")[f"ecart_{b}"].shift(1)
    both = gold[f"ecart_{b}_prec"].notna() & shifted.notna()
    match = (gold.loc[both, f"ecart_{b}_prec"] - shifted[both]).abs() < 0.0006
    check(f"gold: ecart_{b}_prec = scrutin N-1", match, gold.loc[both])

gold = gold.drop(columns=["somme_pct_cibles"])
gold.to_csv(os.path.join(GOLD, "dataset_analytique.csv"), index=False)

# --- KPI decisionnels (artefacts Gold) ---
kpi_blocs = (
    gold.groupby(["annee", "bloc_gagnant"], as_index=False)
    .size()
    .rename(columns={"size": "n_departements", "bloc_gagnant": "bloc"})
)
kpi_blocs["part_pct"] = (
    kpi_blocs["n_departements"] / kpi_blocs.groupby("annee")["n_departements"].transform("sum") * 100
).round(1)

feat_cols = [
    "taux_chomage_n1", "delta_chomage_1a", "delta_chomage_5a",
    "emploi_pour_1000hab", "croissance_emploi_5a_pct", "croissance_pop_5a_pct",
    "taux_pauvrete_n1", "creations_entreprises_n1",
    "bloc_gagnant_precedent", "pct_gagnant_precedent", "marge_gagnante_precedente",
    "inscrits",
    *[f"pct_{b}" for b in BLOCS],
    *elec_feat_cols,
    *ecart_feat_cols,
]
kpi_completude = pd.DataFrame({
    "feature": feat_cols,
    "completude_pct": [round(float(gold[c].notna().mean() * 100), 1) for c in feat_cols],
    "n_non_null": [int(gold[c].notna().sum()) for c in feat_cols],
})

kpi_chomage_bloc = (
    gold.dropna(subset=["taux_chomage_n1"])
    .groupby("bloc_gagnant", as_index=False)
    .agg(
        chomage_moyen=("taux_chomage_n1", "mean"),
        chomage_median=("taux_chomage_n1", "median"),
        n=("taux_chomage_n1", "count"),
    )
)
kpi_chomage_bloc["chomage_moyen"] = kpi_chomage_bloc["chomage_moyen"].round(2)
kpi_chomage_bloc["chomage_median"] = kpi_chomage_bloc["chomage_median"].round(2)
kpi_chomage_bloc = kpi_chomage_bloc.rename(columns={"bloc_gagnant": "bloc"})

gold_tables = {
    "dataset_analytique.csv": gold,
    "kpi_evolution_blocs.csv": kpi_blocs,
    "kpi_completude_features.csv": kpi_completude,
    "kpi_chomage_vs_bloc.csv": kpi_chomage_bloc,
}
for name, df in gold_tables.items():
    if name != "dataset_analytique.csv":
        df.to_csv(os.path.join(GOLD, name), index=False)
    print(f"[GOLD] {name}: {len(df)} lignes")

write_manifest(
    "GOLD", GOLD, gold_tables,
    extra={
        "grain": "1 ligne = 1 (code_dept, annee election)",
        "anti_leakage": (
            "features socio-eco <= N-1 ; lags politiques = scrutin precedent ; "
            "features electorales et derivees d'ecart = scrutins strictement anterieurs"
        ),
        "decomposition": (
            "pct_B = pct_B_national (pondere inscrits) + ecart_B ; "
            "moyenne ponderee des ecarts ~ 0 (tolerance 0,15 pt)"
        ),
        "n_observations": len(gold),
        "n_departements": int(gold["code_dept"].nunique()),
        "elections": sorted(int(x) for x in gold["annee"].unique()),
    },
)

# ---------------------------------------------------------------------------
# SQLite (livrable + dims completes)
# ---------------------------------------------------------------------------
db = os.path.join(GOLD, "electio_poc.db")
if os.path.exists(db):
    os.remove(db)
con = sqlite3.connect(db)
schema_path = os.path.join(SQL, "schema.sql")
if os.path.isfile(schema_path):
    with open(schema_path, encoding="utf-8") as f:
        con.executescript(f.read())

dim_dep = dim_departement_frame()
# Ne garder que les depts presents
dim_dep = dim_dep[dim_dep["code_dept"].isin(gold["code_dept"].unique())]
dim_dep.to_sql("dim_departement", con, if_exists="replace", index=False)

annees = sorted(set(pop["annee"].astype(int).tolist()) | set(gold["annee"].astype(int).tolist()))
pd.DataFrame({
    "annee": annees,
    "est_annee_election": [1 if a in set(elec["annee"].astype(int)) else 0 for a in annees],
}).to_sql("dim_annee", con, if_exists="replace", index=False)

pd.DataFrame({
    "bloc": list(BLOCS),
    "libelle": ["Extreme gauche", "Gauche", "Centre", "Droite", "Extreme droite"],
    "axe": [-2, -1, 0, 1, 2],
}).to_sql("dim_bloc", con, if_exists="replace", index=False)

elec.to_sql("fait_resultat_election", con, if_exists="replace", index=False)
chom.to_sql("fait_chomage_trimestriel", con, if_exists="replace", index=False)
emp.to_sql("fait_emploi_trimestriel", con, if_exists="replace", index=False)
socio.to_sql("fait_socioeco_annuel", con, if_exists="replace", index=False)
gold.to_sql("gold_dataset_analytique", con, if_exists="replace", index=False)
kpi_blocs.to_sql("kpi_evolution_blocs", con, if_exists="replace", index=False)
kpi_completude.to_sql("kpi_completude_features", con, if_exists="replace", index=False)
kpi_chomage_bloc.to_sql("kpi_chomage_vs_bloc", con, if_exists="replace", index=False)

con.execute("CREATE INDEX IF NOT EXISTS idx_gold_dept ON gold_dataset_analytique(code_dept)")
con.execute("CREATE INDEX IF NOT EXISTS idx_gold_annee ON gold_dataset_analytique(annee)")
con.execute("CREATE INDEX IF NOT EXISTS idx_socio_dept ON fait_socioeco_annuel(code_dept)")
con.commit()
con.close()

# ---------------------------------------------------------------------------
# Journal DQM
# ---------------------------------------------------------------------------
n_ok = sum(1 for L in qlog if L.startswith("[OK "))
n_ko = sum(1 for L in qlog if L.startswith("[KO "))
dqm = [
    "JOURNAL QUALITE -- pipeline ETL Electio-Analytics",
    "Cadre DQM : Exactitude | Completude | Coherence | Unicite | Traçabilite",
    f"Controles passes : {n_ok} OK / {n_ko} KO",
    "",
    "=== Controles unitaires ===",
    *qlog,
    "",
    "=== Couches ===",
    f"BRONZE : contrat lu ({len(BRONZE_SCHEMAS)} tables schemas)",
    f"SILVER : {len(silver_tables)} tables (DQM + agregats + panel socioeco)",
    f"GOLD   : {len(gold)} obs | {gold['code_dept'].nunique()} depts | "
    f"{gold['annee'].nunique()} elections",
    "",
    "=== Metriques GOLD ===",
    f"lignes={len(gold)}",
    f"departements={gold['code_dept'].nunique()}",
    f"elections={gold['annee'].nunique()}",
    f"completude_chomage_n1={gold['taux_chomage_n1'].notna().mean():.1%}",
    f"completude_pauvrete_n1={gold['taux_pauvrete_n1'].notna().mean():.1%}",
    "decision_pauvrete=Filosofi histo 2016/17/19/21 + Melodi 2023 en GOLD ; "
    "exclue du modele ML (couverture 2 scrutins, degrade holdout) — "
    "voir docs/mspr/04_machine_learning/ANALYSE_ML_CLASSES.md",
    f"completude_emploi={gold['emploi_pour_1000hab'].notna().mean():.1%}",
    f"unicite_cle=(code_dept,annee) doublons={gold.duplicated(['code_dept','annee']).sum()}",
    "anti_leakage=features socio-eco <= N-1 + lags electoraux et d'ecart strictement anterieurs",
    "",
    "=== Referentiels ===",
    "dim_departement (libelle+region) | dim_annee | dim_bloc",
    "kpi_evolution_blocs | kpi_completude_features | kpi_chomage_vs_bloc",
]
with open(os.path.join(ROOT, "quality_report.txt"), "w", encoding="utf-8") as f:
    f.write("\n".join(dqm) + "\n")

print("\n".join(qlog))
print(f"\nGOLD : {len(gold)} lignes ({gold['code_dept'].nunique()} depts x "
      f"{gold['annee'].nunique()} elections)")
print("Base SQLite :", db)
print("Manifests : silver_manifest.json, gold_manifest.json")
