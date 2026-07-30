# -*- coding: utf-8 -*-
"""
Service ML — aligne sur ml/train.py :
  selection walk-forward, modele retenu = Gradient Boosting (robustesse 2022).
"""
from __future__ import annotations

import json
import os

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score
from sklearn.model_selection import GroupKFold, cross_val_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

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

_MODEL = None
_META = {}
_IMPORTANCE = {}
_CONFUSION = {}


def _build(df):
    num = [c for c in NUM_ALL if c in df.columns and df[c].notna().any()]
    pre = ColumnTransformer([
        ("num", Pipeline([
            ("imp", SimpleImputer(strategy="median")),
            ("sc", StandardScaler()),
        ]), num),
        ("cat", OneHotEncoder(handle_unknown="ignore"), CAT),
    ])
    model = Pipeline([
        ("prep", pre),
        ("clf", GradientBoostingClassifier(
            n_estimators=200, max_depth=3, random_state=42,
        )),
    ])
    return model, num


def _feature_names(model, num):
    names = list(num)
    try:
        ohe = model.named_steps["prep"].named_transformers_["cat"]
        names += list(ohe.get_feature_names_out([CAT[0]]))
    except Exception:
        pass
    return names


def train_from_engine(engine):
    """Entraine sur la table GOLD lue depuis Postgres."""
    global _MODEL, _META, _IMPORTANCE, _CONFUSION
    df = pd.read_sql("SELECT * FROM gold_dataset_analytique", engine)
    df = df.dropna(subset=["taux_chomage_n1", "bloc_gagnant_precedent"]).reset_index(drop=True)
    if len(df) == 0:
        raise RuntimeError("GOLD vide apres filtrage (chomage_n1 / bloc precedent)")

    model, num = _build(df)
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
        "modele_retenu": "gradient_boosting",
        "protocole": "walk-forward / holdout temporel",
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
    row = {
        **{c: features.get(c) for c in NUM_ALL},
        "bloc_gagnant_precedent": features.get("bloc_gagnant_precedent"),
    }
    X = pd.DataFrame([row])
    proba = _MODEL.predict_proba(X)[0]
    classes = _MODEL.named_steps["clf"].classes_.tolist()
    return {c: round(float(p), 3) for c, p in zip(classes, proba)}
