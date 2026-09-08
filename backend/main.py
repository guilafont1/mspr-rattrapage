# -*- coding: utf-8 -*-
"""
API FastAPI - Electio-Analytics.
Expose les donnees GOLD et les predictions du modele.
"""
import os
import sys
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.wsgi import WSGIMiddleware
from pydantic import BaseModel
from sqlalchemy import text
import pandas as pd

from database import get_engine
import load_data
import ml_service

FRONT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))
SERVE_DASH = os.path.isfile(os.path.join(FRONT_DIR, "app.py"))


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
        load_data.refresh_if_needed()
    except Exception as e:
        print(f"[startup] avertissement chargement : {e}")
    try:
        meta = ml_service.train_from_engine(engine)
        print(f"[startup] modele pret : {meta}")
    except Exception as e:
        print(f"[startup] avertissement entrainement : {e}")
        try:
            print("[startup] tentative enrichissement + retrain...")
            load_data.enrich_gold_ecarts(engine)
            meta = ml_service.train_from_engine(engine)
            print(f"[startup] modele pret (apres enrich) : {meta}")
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


if not SERVE_DASH:
    @app.get("/")
    def root():
        """JSON si l'image n'embarque pas Dash (backend Docker seul)."""
        return {
            "service": "Electio-Analytics API",
            "docs": "/docs",
            "health": "/health",
            "health_db": "/health/db",
            "modele_pret": ml_service.is_ready(),
        }


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


def _require_model():
    if not ml_service.ensure_ready(engine):
        raise HTTPException(503, "Modele non entraine")


@app.get("/model/info")
def model_info():
    _require_model()
    return ml_service.meta()


@app.get("/model/importance")
def model_importance():
    _require_model()
    return ml_service.importance()


@app.get("/model/comparison")
def model_comparison():
    """Comparaison des modeles depuis data/ml_report.json."""
    return ml_service.comparison_from_report()


@app.get("/model/confusion")
def model_confusion():
    _require_model()
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
    # Features electorales (lags)
    pct_EXG_prec: float | None = None
    pct_GAU_prec: float | None = None
    pct_CEN_prec: float | None = None
    pct_DRO_prec: float | None = None
    pct_EXD_prec: float | None = None
    delta_recent_EXG: float | None = None
    delta_recent_GAU: float | None = None
    delta_recent_CEN: float | None = None
    delta_recent_DRO: float | None = None
    delta_recent_EXD: float | None = None
    delta_long_EXG: float | None = None
    delta_long_GAU: float | None = None
    delta_long_CEN: float | None = None
    delta_long_DRO: float | None = None
    delta_long_EXD: float | None = None
    trend_EXG: float | None = None
    trend_GAU: float | None = None
    trend_CEN: float | None = None
    trend_DRO: float | None = None
    trend_EXD: float | None = None
    volatility_EXG: float | None = None
    volatility_GAU: float | None = None
    volatility_CEN: float | None = None
    volatility_DRO: float | None = None
    volatility_EXD: float | None = None
    # Derivees de l'ecart departemental
    ecart_EXG_prec: float | None = None
    ecart_GAU_prec: float | None = None
    ecart_CEN_prec: float | None = None
    ecart_DRO_prec: float | None = None
    ecart_EXD_prec: float | None = None
    delta_recent_ecart_EXG: float | None = None
    delta_recent_ecart_GAU: float | None = None
    delta_recent_ecart_CEN: float | None = None
    delta_recent_ecart_DRO: float | None = None
    delta_recent_ecart_EXD: float | None = None
    delta_long_ecart_EXG: float | None = None
    delta_long_ecart_GAU: float | None = None
    delta_long_ecart_CEN: float | None = None
    delta_long_ecart_DRO: float | None = None
    delta_long_ecart_EXD: float | None = None
    trend_ecart_EXG: float | None = None
    trend_ecart_GAU: float | None = None
    trend_ecart_CEN: float | None = None
    trend_ecart_DRO: float | None = None
    trend_ecart_EXD: float | None = None
    volatility_ecart_EXG: float | None = None
    volatility_ecart_GAU: float | None = None
    volatility_ecart_CEN: float | None = None
    volatility_ecart_DRO: float | None = None
    volatility_ecart_EXD: float | None = None


def _lag_from_series(series: pd.Series, years: pd.Series, ndigits: int = 4) -> dict:
    """Derivees anti-leakage a partir d'une serie deja triee chronologiquement.

    Pour un usage prospectif : le dernier point observe devient le « precedent ».
    """
    s = pd.to_numeric(series, errors="coerce")
    y = pd.to_numeric(years, errors="coerce")
    mask = s.notna() & y.notna()
    s, y = s[mask], y[mask]
    out = {}
    if len(s) == 0:
        return out
    last = float(s.iloc[-1])
    out["prec"] = round(last, ndigits)
    if len(s) >= 2:
        out["delta_recent"] = round(last - float(s.iloc[-2]), ndigits)
        out["volatility"] = round(float(s.std(ddof=1)), 4)
    first = float(s.iloc[0])
    out["delta_long"] = round(last - first, ndigits)
    span = int(y.iloc[-1]) - int(y.iloc[0])
    out["trend"] = round((last - first) / span, 4) if span > 0 else None
    return out


def _electoral_lags_from_history(df_hist: pd.DataFrame) -> dict:
    """Derive pct_{B}_prec, ecart_{B}_prec et trajectoires (anti-leakage)."""
    blocs = ["EXG", "GAU", "CEN", "DRO", "EXD"]
    hist = df_hist.sort_values("annee")
    out = {}
    if hist.empty:
        return out
    for b in blocs:
        if f"pct_{b}" in hist.columns:
            lag = _lag_from_series(hist[f"pct_{b}"], hist["annee"], ndigits=3)
            if "prec" in lag:
                out[f"pct_{b}_prec"] = lag["prec"]
            if "delta_recent" in lag:
                out[f"delta_recent_{b}"] = lag["delta_recent"]
            if "delta_long" in lag:
                out[f"delta_long_{b}"] = lag["delta_long"]
            if "trend" in lag:
                out[f"trend_{b}"] = lag["trend"]
            if "volatility" in lag:
                out[f"volatility_{b}"] = lag["volatility"]
        col_e = f"ecart_{b}"
        if col_e not in hist.columns and f"pct_{b}" in hist.columns and f"pct_{b}_national" in hist.columns:
            hist = hist.copy()
            hist[col_e] = (
                pd.to_numeric(hist[f"pct_{b}"], errors="coerce")
                - pd.to_numeric(hist[f"pct_{b}_national"], errors="coerce")
            )
        if col_e in hist.columns:
            lag = _lag_from_series(hist[col_e], hist["annee"], ndigits=4)
            if "prec" in lag:
                out[f"ecart_{b}_prec"] = lag["prec"]
            if "delta_recent" in lag:
                out[f"delta_recent_ecart_{b}"] = lag["delta_recent"]
            if "delta_long" in lag:
                out[f"delta_long_ecart_{b}"] = lag["delta_long"]
            if "trend" in lag:
                out[f"trend_ecart_{b}"] = lag["trend"]
            if "volatility" in lag:
                out[f"volatility_ecart_{b}"] = lag["volatility"]
    return out


@app.get("/predict/baseline")
def predict_baseline(dept: str = Query("FR", min_length=1, max_length=10)):
    """Baseline what-if : France (agrégat national) ou un département.

    Usage prospectif : lags = résultats du dernier scrutin (annee_cible = annee+5),
    y compris pct_{B}_prec et dérivées électorales.
    """
    code = dept.strip().upper()
    if code in ("FR", "FRANCE", "NAT", "NATIONAL"):
        q_year = text("SELECT MAX(annee) AS annee FROM gold_dataset_analytique")
        ydf = pd.read_sql(q_year, engine)
        if ydf.empty or pd.isna(ydf.iloc[0]["annee"]):
            raise HTTPException(404, "Aucun historique GOLD")
        annee = int(ydf.iloc[0]["annee"])
        q = text("SELECT * FROM gold_dataset_analytique WHERE annee = :annee")
        df = load_data.canonicalize_gold_df(
            pd.read_sql(q, engine, params={"annee": annee})
        )
        if df.empty:
            raise HTTPException(404, f"Aucune donnée GOLD pour {annee}")

        # Historique national moyen par année (pour dérivées électorales)
        q_all = text("SELECT * FROM gold_dataset_analytique")
        all_df = load_data.canonicalize_gold_df(pd.read_sql(q_all, engine))
        nat = (
            all_df.groupby("annee", as_index=False)[
                [c for c in all_df.columns
                 if c.startswith("pct_") or c.startswith("ecart_")]
            ].mean(numeric_only=True)
        )

        num_cols = [
            "taux_chomage_n1", "delta_chomage_1a", "delta_chomage_5a",
            "emploi_pour_1000hab", "croissance_emploi_5a_pct", "croissance_pop_5a_pct",
            "taux_pauvrete_n1", "creations_entreprises_n1",
            "pct_gagnant", "marge_gagnante",
            "pct_EXG", "pct_GAU", "pct_CEN", "pct_DRO", "pct_EXD",
        ]
        rec = {"annee": annee, "code_dept": "FR", "libelle": "France"}
        for col in num_cols:
            if col in df.columns:
                val = pd.to_numeric(df[col], errors="coerce").mean()
                rec[col] = None if pd.isna(val) else round(float(val), 3)

        if "bloc_gagnant" in df.columns and df["bloc_gagnant"].notna().any():
            rec["bloc_gagnant"] = str(df["bloc_gagnant"].mode().iloc[0])
        else:
            rec["bloc_gagnant"] = None
        rec["bloc_gagnant_precedent"] = rec.get("bloc_gagnant")
        if rec.get("pct_gagnant") is not None:
            rec["pct_gagnant_precedent"] = rec["pct_gagnant"]
        if rec.get("marge_gagnante") is not None:
            rec["marge_gagnante_precedente"] = rec["marge_gagnante"]

        rec.update(_electoral_lags_from_history(nat))
        rec["annee_cible"] = annee + 5
        rec["n_departements"] = int(len(df))
        rec["perimetre"] = "france"
        rec["niveaux_nationaux_tendance"] = ml_service.tendance_nationale(annee + 5)
        rec["scenario_national_defaut"] = "tendance"
        return rec

    q = text("""
        SELECT g.*, d.libelle
        FROM gold_dataset_analytique g
        LEFT JOIN dim_departement d ON d.code_dept = g.code_dept
        WHERE g.code_dept = :dept
        ORDER BY g.annee
    """)
    df = load_data.canonicalize_gold_df(
        pd.read_sql(q, engine, params={"dept": code})
    )
    if df.empty:
        raise HTTPException(404, f"Aucun historique GOLD pour le département {code}")
    last = df.iloc[-1]
    rec = _records(df.tail(1))[0]
    if rec.get("bloc_gagnant") is not None:
        rec["bloc_gagnant_precedent"] = rec["bloc_gagnant"]
    if rec.get("pct_gagnant") is not None:
        rec["pct_gagnant_precedent"] = rec["pct_gagnant"]
    if rec.get("marge_gagnante") is not None:
        rec["marge_gagnante_precedente"] = rec["marge_gagnante"]
    rec.update(_electoral_lags_from_history(df))
    annee = rec.get("annee")
    rec["annee_cible"] = int(annee) + 5 if annee is not None else None
    rec["libelle"] = rec.get("libelle") or code
    rec["perimetre"] = "departement"
    cible = rec["annee_cible"] or 2027
    rec["niveaux_nationaux_tendance"] = ml_service.tendance_nationale(cible)
    rec["scenario_national_defaut"] = "tendance"
    return rec


class PredictRequest(Features):
    """Features what-if + horizon (année = dernier scrutin + h)."""
    horizon_ans: int = 1
    scenario_national: str | None = "tendance"
    niveaux_nationaux: dict | None = None
    annee_cible: int | None = None


@app.post("/predict")
def predict(f: PredictRequest):
    _require_model()
    horizon = int(f.horizon_ans or 1)
    if horizon not in (1, 2, 3):
        raise HTTPException(400, "horizon_ans doit être 1, 2 ou 3")
    payload = f.model_dump() if hasattr(f, "model_dump") else f.dict()
    payload.pop("horizon_ans", None)
    scenario = payload.pop("scenario_national", "tendance")
    niveaux = payload.pop("niveaux_nationaux", None)
    annee_cible = payload.pop("annee_cible", None)
    try:
        scores_h, overs_by_h, blocs_h, ecarts_h, nat_h, annees_h, regime = (
            ml_service.predict_proba_horizons(
                payload,
                scenario_national=scenario,
                niveaux_nationaux=niveaux,
                annee_cible=annee_cible,
            )
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    key = str(horizon)
    scores = scores_h[key]
    proba_h = {
        h: {b: round(v / 100.0, 3) for b, v in sc.items()}
        for h, sc in scores_h.items()
    }
    return {
        "horizon_ans": horizon,
        "annee_horizon": annees_h.get(key),
        "annees_par_horizon": annees_h,
        "scores": scores,
        "scores_par_horizon": scores_h,
        "ecarts": ecarts_h.get(key, {}),
        "ecarts_par_horizon": ecarts_h,
        "niveaux_nationaux": nat_h.get(key, {}),
        "niveaux_nationaux_par_horizon": nat_h,
        "regime": regime,
        "bloc_predit": blocs_h[key],
        "bloc_predit_par_horizon": blocs_h,
        "probabilites": proba_h[key],
        "probabilites_par_horizon": proba_h,
        "hors_enveloppe": overs_by_h.get(key, []),
        "hors_enveloppe_par_horizon": overs_by_h,
        "enveloppe_entrainement": ml_service.envelope(),
        "methode": (
            "regression_ecarts + tendance_nationale(aujourd_hui+h)"
            " + socio_extrapole + renormalisation_100 + clamp_enveloppe"
        ),
    }


@app.get("/model/regression")
def model_regression():
    """MAE par bloc (regimes oracle / projete) depuis ml_report.json."""
    data = ml_service.regression_metrics_from_report()
    if not data.get("holdout") and not data.get("regression_holdout"):
        raise HTTPException(404, "Metriques regression indisponibles")
    return data


def _inproc_get(path: str, params: dict):
    """Appel direct des handlers FastAPI (pas de TestClient / httpx)."""
    try:
        if path == "/health":
            return health()
        if path == "/health/db":
            return health_db()
        if path == "/annees":
            return annees()
        if path == "/departements":
            return departements()
        if path == "/dashboard/overview":
            return dashboard_overview()
        if path == "/carte":
            return carte(annee=int(params["annee"]))
        if path == "/indicateurs":
            annee = params.get("annee")
            return indicateurs(
                dept=params.get("dept"),
                annee=int(annee) if annee is not None else None,
            )
        if path == "/resultats":
            annee = params.get("annee")
            return resultats(annee=int(annee) if annee is not None else None)
        if path == "/predict/baseline":
            return predict_baseline(dept=str(params.get("dept") or "FR"))
        if path == "/model/info":
            return model_info()
        if path == "/model/importance":
            return model_importance()
        if path == "/model/comparison":
            return model_comparison()
        if path == "/model/confusion":
            return model_confusion()
        if path == "/model/regression":
            return model_regression()
    except HTTPException:
        return None
    return None


def _inproc_post(path: str, payload: dict):
    try:
        if path == "/predict":
            return 200, predict(PredictRequest(**(payload or {})))
        if path == "/admin/reload":
            return 200, admin_reload()
    except HTTPException as exc:
        return exc.status_code, {"detail": exc.detail}
    except Exception as exc:
        return 500, {"detail": str(exc)}
    return 404, {"detail": "not found"}


# Même process : Dash monté sur / ; callbacks → handlers Python (pas d'HTTP).
if SERVE_DASH:
    if FRONT_DIR not in sys.path:
        sys.path.insert(0, FRONT_DIR)
    import app as dash_module  # noqa: E402
    from app import server as dash_server  # noqa: E402

    app.mount("/", WSGIMiddleware(dash_server))
    dash_module.bind_api_handlers(_inproc_get, _inproc_post)
