# -*- coding: utf-8 -*-
"""
API FastAPI - Electio-Analytics.
Expose les donnees GOLD et les predictions du modele.
"""
import os
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import text
import pandas as pd

from database import get_engine
import load_data
import ml_service


def _records(df):
    """Convertit un DataFrame en liste de dicts JSON-safe (NaN -> None)."""
    import numpy as np
    return df.replace({np.nan: None}).to_dict(orient="records")


app = FastAPI(title="Electio-Analytics API", version="1.1")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

engine = get_engine()


@app.on_event("startup")
def startup():
    try:
        load_data.ensure_schema()
        if load_data.is_empty() or load_data.schema_outdated():
            print("[startup] GOLD absente/obsolete -> reload SILVER/GOLD...")
            load_data.load()
        else:
            print("[startup] GOLD a jour, skip load")
    except Exception as e:
        print(f"[startup] avertissement chargement : {e}")
    try:
        meta = ml_service.train_from_engine(engine)
        print(f"[startup] modele pret : {meta}")
    except Exception as e:
        print(f"[startup] avertissement entrainement : {e}")
        # Derniere chance : forcer reload puis re-entrainer
        try:
            print("[startup] tentative reload + retrain...")
            load_data.load()
            meta = ml_service.train_from_engine(engine)
            print(f"[startup] modele pret (apres reload) : {meta}")
        except Exception as e2:
            print(f"[startup] echec entrainement : {e2}")


@app.post("/admin/reload")
def admin_reload():
    """Recharge GOLD depuis les CSV + reentraine le modele (ops / debug)."""
    try:
        load_data.load()
        meta = ml_service.train_from_engine(engine)
        return {"status": "ok", "modele_pret": True, "meta": meta}
    except Exception as e:
        raise HTTPException(500, f"Reload KO : {e}") from e


@app.get("/health")
def health():
    return {"status": "ok", "modele_pret": ml_service.is_ready()}


@app.get("/health/db")
def health_db():
    """Ping PostgreSQL (SELECT 1) — pour monitoring front / bouton de test."""
    import time
    t0 = time.perf_counter()
    try:
        with engine.connect() as con:
            con.execute(text("SELECT 1"))
            n = con.execute(text("SELECT COUNT(*) FROM gold_dataset_analytique")).scalar()
        ms = round((time.perf_counter() - t0) * 1000, 1)
        return {
            "status": "ok",
            "database": "up",
            "latency_ms": ms,
            "gold_rows": int(n or 0),
        }
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail={"status": "error", "database": "down", "error": str(e)[:200]},
        )


@app.get("/departements")
def departements():
    df = pd.read_sql("SELECT DISTINCT code_dept FROM gold_dataset_analytique ORDER BY code_dept", engine)
    return df["code_dept"].tolist()


@app.get("/annees")
def annees():
    df = pd.read_sql("SELECT DISTINCT annee FROM gold_dataset_analytique ORDER BY annee", engine)
    return df["annee"].tolist()


@app.get("/indicateurs")
def indicateurs(dept: str = Query(None), annee: int = Query(None)):
    q = "SELECT * FROM gold_dataset_analytique WHERE 1=1"
    params = {}
    if dept:
        q += " AND code_dept = :dept"; params["dept"] = dept
    if annee:
        q += " AND annee = :annee"; params["annee"] = annee
    q += " ORDER BY annee, code_dept"
    df = pd.read_sql(text(q), engine, params=params)
    return _records(df)


@app.get("/resultats")
def resultats(annee: int = Query(None)):
    q = "SELECT * FROM fait_resultat_election"
    params = {}
    if annee:
        q += " WHERE annee = :annee"; params["annee"] = annee
    df = pd.read_sql(text(q), engine, params=params)
    return _records(df)


@app.get("/carte")
def carte(annee: int = Query(..., description="Annee d'election")):
    """Par departement : code_dept + bloc_gagnant (choroplèthe)."""
    q = text("""
        SELECT code_dept, bloc_gagnant
        FROM fait_resultat_election
        WHERE annee = :annee
        ORDER BY code_dept
    """)
    df = pd.read_sql(q, engine, params={"annee": annee})
    return _records(df)


@app.get("/dashboard/overview")
def dashboard_overview():
    """Agrégats pour le tableau de bord (données réelles, aucune invention)."""
    blocs = ["EXG", "GAU", "CEN", "DRO", "EXD"]
    res = pd.read_sql("SELECT * FROM fait_resultat_election", engine)
    gold = pd.read_sql(
        """
        SELECT annee, code_dept, taux_chomage_n1, emploi_pour_1000hab,
               creations_entreprises_n1, bloc_gagnant
        FROM gold_dataset_analytique
        """,
        engine,
    )
    empty = {
        "annees": [],
        "scores_nationaux": [],
        "gagnants_par_annee": [],
        "chomage_par_bloc": [],
        "emploi_par_bloc": [],
    }
    if res.empty:
        return empty

    annees = sorted(int(a) for a in res["annee"].dropna().unique().tolist())

    # Score moyen national par bloc et année
    scores = []
    for annee, g in res.groupby("annee"):
        for b in blocs:
            col = f"pct_{b.lower()}"
            if col in g.columns and g[col].notna().any():
                scores.append({
                    "annee": int(annee),
                    "bloc": b,
                    "score_moyen": round(float(g[col].mean()), 2),
                })

    # Nb de départements en tête par bloc / année
    wins = (
        res.groupby(["annee", "bloc_gagnant"])
        .size()
        .reset_index(name="n_departements")
    )
    gagnants = [
        {
            "annee": int(r.annee),
            "bloc": r.bloc_gagnant,
            "n_departements": int(r.n_departements),
        }
        for r in wins.itertuples(index=False)
        if r.bloc_gagnant in blocs
    ]

    # Indicateurs socio moyens selon le bloc gagnant × année (GOLD)
    chomage, emploi = [], []
    if not gold.empty and "bloc_gagnant" in gold.columns:
        gdf = gold[gold["bloc_gagnant"].isin(blocs)].copy()
        for (annee, b), g in gdf.groupby(["annee", "bloc_gagnant"]):
            if g["taux_chomage_n1"].notna().any():
                chomage.append({
                    "annee": int(annee),
                    "bloc": b,
                    "chomage_moyen": round(float(g["taux_chomage_n1"].mean()), 2),
                    "n": int(g["taux_chomage_n1"].notna().sum()),
                })
            if g["emploi_pour_1000hab"].notna().any():
                emploi.append({
                    "annee": int(annee),
                    "bloc": b,
                    "emploi_moyen": round(float(g["emploi_pour_1000hab"].mean()), 1),
                    "n": int(g["emploi_pour_1000hab"].notna().sum()),
                })

    return {
        "annees": annees,
        "scores_nationaux": scores,
        "gagnants_par_annee": gagnants,
        "chomage_par_bloc": chomage,
        "emploi_par_bloc": emploi,
    }


@app.get("/model/info")
def model_info():
    if not ml_service.is_ready():
        raise HTTPException(503, "Modele non entraine")
    return ml_service.meta()


@app.get("/model/importance")
def model_importance():
    if not ml_service.is_ready():
        raise HTTPException(503, "Modele non entraine")
    return ml_service.importance()


@app.get("/model/comparison")
def model_comparison():
    """Comparaison des modeles depuis data/ml_report.json."""
    return ml_service.comparison_from_report()


@app.get("/model/confusion")
def model_confusion():
    if not ml_service.is_ready():
        raise HTTPException(503, "Modele non entraine")
    data = ml_service.confusion()
    if not data.get("matrix"):
        raise HTTPException(404, "Matrice de confusion indisponible")
    return data


class Features(BaseModel):
    taux_chomage_n1: float | None = None
    delta_chomage_1a: float | None = None
    delta_chomage_5a: float | None = None
    emploi_pour_1000hab: float | None = None
    croissance_emploi_5a_pct: float | None = None
    croissance_pop_5a_pct: float | None = None
    taux_pauvrete_n1: float | None = None
    creations_entreprises_n1: float | None = None
    pct_gagnant_precedent: float | None = None
    marge_gagnante_precedente: float | None = None
    bloc_gagnant_precedent: str | None = None


@app.post("/predict")
def predict(f: Features):
    if not ml_service.is_ready():
        raise HTTPException(503, "Modele non entraine")
    return {"probabilites": ml_service.predict_proba(f.dict())}
