# -*- coding: utf-8 -*-
"""
Service ML — aligne sur ml/train.py :
  estimateurs partagés, modèle retenu lu depuis data/ml_report.json,
  enveloppe d'entraînement et clamp des features what-if.
"""
from __future__ import annotations

import json
import os

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score
from sklearn.model_selection import GroupKFold, cross_val_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.tree import DecisionTreeClassifier

ROOT = os.path.join(os.path.dirname(__file__), "..")
ML_REPORT = os.path.join(ROOT, "data", "ml_report.json")

NUM_ALL = [
    "taux_chomage_n1", "delta_chomage_1a", "delta_chomage_5a",
    "emploi_pour_1000hab", "croissance_emploi_5a_pct", "croissance_pop_5a_pct",
    # pauvreté : Gold/BI seulement (voir ml/train.py)
    "creations_entreprises_n1",
    "pct_gagnant_precedent", "marge_gagnante_precedente",
]
CAT = ["bloc_gagnant_precedent"]

# Exactement les 4 estimateurs supervisés de ml/train.py (hors baseline dummy).
ESTIMATEURS = {
    "regression_logistique": lambda: LogisticRegression(
        max_iter=3000, class_weight="balanced", C=0.8,
    ),
    "arbre_decision": lambda: DecisionTreeClassifier(
        max_depth=4, min_samples_leaf=8, class_weight="balanced", random_state=42,
    ),
    "random_forest": lambda: RandomForestClassifier(
        n_estimators=400, max_depth=5, min_samples_leaf=5,
        class_weight="balanced_subsample", random_state=42,
    ),
    "gradient_boosting": lambda: GradientBoostingClassifier(
        n_estimators=200, max_depth=3, learning_rate=0.1, random_state=42,
    ),
}

_MODEL = None
_META = {}
_IMPORTANCE = {}
_CONFUSION = {}
_ENVELOPE = {}


def _modele_retenu() -> str:
    """Lit la clé modele_retenu de data/ml_report.json.

    Fallback random_forest si fichier illisible ou nom inconnu.
    """
    try:
        with open(ML_REPORT, encoding="utf-8") as f:
            name = json.load(f).get("modele_retenu")
        if name in ESTIMATEURS:
            return name
        print(f"[ml_service] modele_retenu inconnu ({name!r}) -> fallback random_forest")
    except Exception as e:
        print(f"[ml_service] ml_report.json illisible ({e}) -> fallback random_forest")
    return "random_forest"


def _build(df):
    num = [c for c in NUM_ALL if c in df.columns and df[c].notna().any()]
    pre = ColumnTransformer([
        ("num", Pipeline([
            ("imp", SimpleImputer(strategy="median")),
            ("sc", StandardScaler()),
        ]), num),
        ("cat", OneHotEncoder(handle_unknown="ignore"), CAT),
    ])
    name = _modele_retenu()
    model = Pipeline([
        ("prep", pre),
        ("clf", ESTIMATEURS[name]()),
    ])
    return model, num, name


def _feature_names(model, num):
    names = list(num)
    try:
        ohe = model.named_steps["prep"].named_transformers_["cat"]
        names += list(ohe.get_feature_names_out([CAT[0]]))
    except Exception:
        pass
    return names


def _exclure_annees_creations_absentes(df: pd.DataFrame) -> pd.DataFrame:
    """Exclut les scrutins où creations_entreprises_n1 est nulle sur toute l'année.

    Aligné sur ml/train.py (décision : drop des observations, pas de la variable).
    """
    if "creations_entreprises_n1" not in df.columns or "annee" not in df.columns:
        return df
    null_year = df.groupby("annee")["creations_entreprises_n1"].apply(
        lambda s: bool(s.isna().all())
    )
    years_drop = [int(y) for y, full in null_year.items() if full]
    if not years_drop:
        return df
    return df[~df["annee"].isin(years_drop)].reset_index(drop=True)


def _compute_envelope(df: pd.DataFrame, num: list) -> dict:
    """min / max / p01 / p99 par feature numérique (enveloppe d'entraînement)."""
    out = {}
    for c in num:
        if c not in df.columns:
            continue
        s = pd.to_numeric(df[c], errors="coerce").dropna()
        if s.empty:
            continue
        out[c] = {
            "min": round(float(s.min()), 4),
            "max": round(float(s.max()), 4),
            "p01": round(float(s.quantile(0.01)), 4),
            "p99": round(float(s.quantile(0.99)), 4),
        }
    return out


def train_from_engine(engine):
    """Entraine sur la table GOLD lue depuis Postgres."""
    global _MODEL, _META, _IMPORTANCE, _CONFUSION, _ENVELOPE
    df = pd.read_sql("SELECT * FROM gold_dataset_analytique", engine)
    df = df.dropna(subset=["taux_chomage_n1", "bloc_gagnant_precedent"]).reset_index(drop=True)
    df = _exclure_annees_creations_absentes(df)
    if len(df) == 0:
        raise RuntimeError("GOLD vide apres filtrage (chomage_n1 / bloc precedent)")

    model, num, name = _build(df)
    X = df[num + CAT]
    y = df["bloc_gagnant"]
    groups = df["code_dept"]
    holdout = int(df["annee"].max())

    try:
        acc = cross_val_score(
            model, X, y, cv=GroupKFold(5), groups=groups, scoring="accuracy"
        ).mean()
    except Exception:
        acc = None

    labels = sorted(y.unique().tolist())
    te = df["annee"] == holdout
    if te.any() and (~te).any():
        model.fit(X[~te], y[~te])
        pred = model.predict(X[te])
        cm = confusion_matrix(y[te], pred, labels=labels)
        _CONFUSION = {
            "labels": labels,
            "matrix": cm.tolist(),
            "accuracy_test_2022": round(float(accuracy_score(y[te], pred)), 3),
            "f1_macro_test_2022": round(
                float(f1_score(y[te], pred, average="macro", zero_division=0)), 3
            ),
            "holdout_year": holdout,
        }
    else:
        _CONFUSION = {
            "labels": labels, "matrix": [],
            "accuracy_test_2022": None, "f1_macro_test_2022": None,
            "holdout_year": holdout,
        }

    # Fit production : historique hors holdout (coherent avec train.py)
    if te.any() and (~te).any():
        model.fit(X[~te], y[~te])
    else:
        model.fit(X, y)

    _MODEL = model
    _ENVELOPE = _compute_envelope(df, num)
    feat_names = _feature_names(model, num)
    clf = model.named_steps["clf"]
    if hasattr(clf, "feature_importances_"):
        imp = dict(zip(feat_names, [round(float(v), 4) for v in clf.feature_importances_]))
        _IMPORTANCE = dict(sorted(imp.items(), key=lambda kv: -kv[1]))
    else:
        _IMPORTANCE = {}

    _META = {
        "features_numeriques": num,
        "n_observations": int(len(df)),
        "n_departements": int(df["code_dept"].nunique()),
        "accuracy_cv_groupee": round(float(acc), 3) if acc is not None else None,
        "accuracy_test_2022": _CONFUSION.get("accuracy_test_2022"),
        "classes": labels,
        "modele_retenu": name,
        "protocole": "walk-forward / holdout temporel",
        "enveloppe_entrainement": _ENVELOPE,
    }
    return _META


def is_ready() -> bool:
    return _MODEL is not None


def meta() -> dict:
    return _META


def importance() -> dict:
    return {"modele_retenu": _META.get("modele_retenu"), "importances": _IMPORTANCE}


def confusion() -> dict:
    return _CONFUSION


def envelope() -> dict:
    """Enveloppe d'entraînement (min/max/p01/p99) des features numériques."""
    return _ENVELOPE


def clamp_features(features: dict) -> tuple[dict, list]:
    """Borne les features numériques dans l'enveloppe d'entraînement.

    Retourne (features_bornées, liste_des_dépassements).
    Chaque dépassement : {feature, valeur, min, max}.
    """
    out = dict(features)
    overs: list = []
    for col, bounds in (_ENVELOPE or {}).items():
        if col not in out:
            continue
        val = _as_float(out.get(col))
        if val is None:
            continue
        lo = float(bounds["min"])
        hi = float(bounds["max"])
        if val < lo or val > hi:
            overs.append({
                "feature": col,
                "valeur": val,
                "min": lo,
                "max": hi,
            })
            out[col] = min(hi, max(lo, val))
    return out, overs


def comparison_from_report() -> dict:
    if not os.path.isfile(ML_REPORT):
        return {"modele_retenu": _META.get("modele_retenu"), "modeles": [], "source": None}
    with open(ML_REPORT, encoding="utf-8") as f:
        report = json.load(f)
    rows = []
    for name, metrics in (report.get("modeles_compares") or {}).items():
        rows.append({
            "modele": name,
            "accuracy_walkforward": metrics.get("accuracy_walkforward"),
            "f1_macro_walkforward": metrics.get("f1_macro_walkforward"),
            "accuracy_cv_groupee": metrics.get("accuracy_cv_groupee"),
            "f1_macro_cv": metrics.get("f1_macro_cv"),
            "accuracy_test_2022": metrics.get("accuracy_test_2022"),
            "f1_macro_test_2022": metrics.get("f1_macro_test_2022"),
            "retenu": name == report.get("modele_retenu"),
        })
    rows.sort(
        key=lambda r: (r.get("f1_macro_walkforward") or r.get("f1_macro_cv") or 0),
        reverse=True,
    )
    return {
        "modele_retenu": report.get("modele_retenu"),
        "n_observations": report.get("n_observations"),
        "protocole": report.get("protocole"),
        "metriques_retenues": report.get("metriques_retenues"),
        "modeles": rows,
        "source": "data/ml_report.json",
    }


def predict_proba(features: dict) -> dict:
    if _MODEL is None:
        raise RuntimeError("Modele non entraine")
    clamped, _ = clamp_features(features)
    row = {
        **{c: clamped.get(c) for c in NUM_ALL},
        "bloc_gagnant_precedent": clamped.get("bloc_gagnant_precedent"),
    }
    X = pd.DataFrame([row])
    proba = _MODEL.predict_proba(X)[0]
    classes = _MODEL.named_steps["clf"].classes_.tolist()
    return {c: round(float(p), 3) for c, p in zip(classes, proba)}


def _as_float(val):
    if val is None:
        return None
    try:
        f = float(val)
    except (TypeError, ValueError):
        return None
    if np.isnan(f):
        return None
    return f


def extrapolate_features(features: dict, horizon_ans: int) -> dict:
    """Projette les indicateurs N−1 vers l'horizon H (1–3 ans).

    Hypothèse pédagogique (sujet préfecture) : on prolonge les tendances
    annuelles implicites (Δ chômage / 5, croissance emploi / 5, …).
    Horizon 1 = features telles quelles.
    """
    h = max(1, min(3, int(horizon_ans)))
    out = dict(features)
    if h == 1:
        return out

    years = h - 1  # projection au-delà de N−1
    chom = _as_float(out.get("taux_chomage_n1"))
    d5 = _as_float(out.get("delta_chomage_5a"))
    if chom is not None and d5 is not None:
        out["taux_chomage_n1"] = round(chom + (d5 / 5.0) * years, 3)

    emp = _as_float(out.get("emploi_pour_1000hab"))
    g_emp = _as_float(out.get("croissance_emploi_5a_pct"))
    if emp is not None and g_emp is not None:
        annual = (1.0 + g_emp / 100.0) ** (1.0 / 5.0)
        out["emploi_pour_1000hab"] = round(emp * (annual ** years), 2)

    pop = _as_float(out.get("croissance_pop_5a_pct"))
    if pop is not None:
        # la feature reste un rythme ; on la laisse, l'effet passe via emploi
        pass

    return out


def apply_horizon_uncertainty(proba: dict, horizon_ans: int) -> dict:
    """Élargit l'incertitude avec l'horizon (mélange vers uniforme).

    α = 0 / 0.12 / 0.25 pour H=1 / 2 / 3 — plus l'horizon est lointain,
    moins la prédiction est affirmée (exigence CDC 1–3 ans).
    """
    h = max(1, min(3, int(horizon_ans)))
    alpha = {1: 0.0, 2: 0.12, 3: 0.25}[h]
    if alpha <= 0 or not proba:
        return {k: round(float(v), 3) for k, v in proba.items()}
    n = len(proba)
    uni = 1.0 / n
    mixed = {k: (1.0 - alpha) * float(v) + alpha * uni for k, v in proba.items()}
    s = sum(mixed.values()) or 1.0
    return {k: round(v / s, 3) for k, v in mixed.items()}


def predict_proba_horizons(features: dict) -> tuple[dict, dict]:
    """Retourne (probabilités H=1..3, dépassements d'enveloppe par horizon)."""
    if _MODEL is None:
        raise RuntimeError("Modele non entraine")
    result = {}
    overs_by_h = {}
    for h in (1, 2, 3):
        feats = extrapolate_features(features, h)
        clamped, overs = clamp_features(feats)
        raw = predict_proba(clamped)
        result[str(h)] = apply_horizon_uncertainty(raw, h)
        overs_by_h[str(h)] = overs
    return result, overs_by_h
