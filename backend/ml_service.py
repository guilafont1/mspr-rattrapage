# -*- coding: utf-8 -*-
"""
Service ML — regression des ecarts departementaux, alignee sur ml/train.py.

Le modele predit ecart_B ; le score reconstruit est
niveau_national_B + ecart_B, clippe [0;100] puis renormalise a 100.
Le niveau national est un scenario (tendance ou saisi par l'utilisateur).
"""
from __future__ import annotations

import json
import os
import warnings
from datetime import date

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, RegressorMixin
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.metrics import accuracy_score, confusion_matrix
from sklearn.multioutput import MultiOutputRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

import load_data

ROOT = os.path.join(os.path.dirname(__file__), "..")
_HERE = os.path.dirname(__file__)
ML_REPORT_CANDIDATES = [
    os.path.join(ROOT, "data", "ml_report.json"),
    os.path.join(_HERE, "ml_report.json"),
]


def _ml_report_path() -> str:
    for path in ML_REPORT_CANDIDATES:
        if os.path.isfile(path):
            return path
    return ML_REPORT_CANDIDATES[0]


ML_REPORT = _ml_report_path()

BLOCS = ["EXG", "GAU", "CEN", "DRO", "EXD"]
TARGETS = [f"ecart_{b}" for b in BLOCS]
NAT_COLS = [f"pct_{b}_national" for b in BLOCS]

ECART_FEATURES = []
for b in BLOCS:
    ECART_FEATURES.extend([
        f"ecart_{b}_prec", f"delta_recent_ecart_{b}", f"delta_long_ecart_{b}",
        f"trend_ecart_{b}", f"volatility_ecart_{b}",
    ])

SOCIO_FEATURES = [
    "taux_chomage_n1", "delta_chomage_1a", "delta_chomage_5a",
    "emploi_pour_1000hab", "croissance_emploi_5a_pct", "croissance_pop_5a_pct",
]

NUM_ALL = ECART_FEATURES + SOCIO_FEATURES
SOMME_NATIONAL_MIN, SOMME_NATIONAL_MAX = 90.0, 110.0

_MODEL = None
_META = {}
_IMPORTANCE = {}
_CONFUSION = {}
_ENVELOPE = {}
_MEAN_SCORES = {b: 20.0 for b in BLOCS}
_NAT_HISTORY = pd.DataFrame()


class PersistenceBundle(BaseEstimator, RegressorMixin):
    def __init__(self, prec_cols=None):
        self.prec_cols = prec_cols

    def _prec(self):
        return list(self.prec_cols) if self.prec_cols is not None else [
            f"ecart_{b}_prec" for b in BLOCS
        ]

    def fit(self, X, y=None):
        if not isinstance(X, pd.DataFrame):
            raise TypeError("PersistenceBundle attend un DataFrame")
        self.feature_names_in_ = list(X.columns)
        self.n_features_in_ = X.shape[1]
        self.n_outputs_ = len(self._prec())
        return self

    def predict(self, X):
        if not isinstance(X, pd.DataFrame):
            X = pd.DataFrame(X, columns=self.feature_names_in_)
        return np.nan_to_num(X[self._prec()].to_numpy(dtype=float), nan=0.0)


class RidgeParBloc(BaseEstimator, RegressorMixin):
    def __init__(self, alpha=10.0, feature_names=None):
        self.alpha = alpha
        self.feature_names = feature_names

    def fit(self, X, y):
        if not isinstance(X, pd.DataFrame):
            cols = self.feature_names or NUM_ALL
            X = pd.DataFrame(X, columns=cols[: X.shape[1]])
        if not isinstance(y, pd.DataFrame):
            y = pd.DataFrame(y, columns=TARGETS)
        self.feature_names_in_ = list(X.columns)
        self.models_ = {}
        self.cols_per_bloc_ = {}
        socio = [c for c in SOCIO_FEATURES if c in X.columns]
        for b in BLOCS:
            cols = [c for c in X.columns if (
                c in socio
                or c == f"ecart_{b}_prec"
                or c.startswith(f"delta_recent_ecart_{b}")
                or c.startswith(f"delta_long_ecart_{b}")
                or c.startswith(f"trend_ecart_{b}")
                or c.startswith(f"volatility_ecart_{b}")
            )]
            self.cols_per_bloc_[b] = cols
            pipe = Pipeline([
                ("imp", SimpleImputer(strategy="median")),
                ("sc", StandardScaler()),
                ("ridge", Ridge(alpha=self.alpha)),
            ])
            pipe.fit(X[cols], y[f"ecart_{b}"])
            self.models_[b] = pipe
        self.n_outputs_ = len(BLOCS)
        return self

    def predict(self, X):
        if not isinstance(X, pd.DataFrame):
            X = pd.DataFrame(X, columns=self.feature_names_in_)
        preds = [self.models_[b].predict(X[self.cols_per_bloc_[b]]) for b in BLOCS]
        return np.column_stack(preds)


def _modele_retenu() -> str:
    try:
        with open(ML_REPORT, encoding="utf-8") as f:
            name = json.load(f).get("modele_retenu")
        if name in ESTIMATEURS:
            return name
        print(f"[ml_service] modele_retenu inconnu ({name!r}) -> ridge_ecart_multisorties")
    except Exception as e:
        print(f"[ml_service] ml_report.json illisible ({e}) -> ridge_ecart_multisorties")
    return "ridge_ecart_multisorties"


def _ridge_alpha() -> float:
    try:
        with open(ML_REPORT, encoding="utf-8") as f:
            hp = json.load(f).get("hyperparams_retenus") or {}
        return float(hp.get("ridge_alpha", 10.0))
    except Exception:
        return 10.0


ESTIMATEURS = {
    "baseline_persistance_ecart": lambda: PersistenceBundle(),
    "ridge_ecart_par_bloc": lambda: RidgeParBloc(alpha=_ridge_alpha()),
    "ridge_ecart_multisorties": lambda: Pipeline([
        ("imp", SimpleImputer(strategy="median")),
        ("sc", StandardScaler()),
        ("reg", Ridge(alpha=_ridge_alpha())),
    ]),
    "random_forest_ecart_multisorties": lambda: Pipeline([
        ("imp", SimpleImputer(strategy="median")),
        ("sc", StandardScaler()),
        ("reg", MultiOutputRegressor(
            RandomForestRegressor(
                n_estimators=200, max_depth=6, min_samples_leaf=5, random_state=42,
            )
        )),
    ]),
}


def _renorm_clip(pred) -> np.ndarray:
    p = np.clip(np.asarray(pred, dtype=float), 0.0, 100.0)
    if p.ndim == 1:
        p = p.reshape(1, -1)
    s = p.sum(axis=1, keepdims=True)
    s = np.where(s <= 0, 1.0, s)
    return p / s * 100.0


def _compute_envelope(df: pd.DataFrame, num: list) -> dict:
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


def niveaux_nationaux_projetes(hist: pd.DataFrame, annee_cible: int) -> dict:
    """Tendance lineaire simple (identique a ml/train.py)."""
    if hist is None or hist.empty:
        arr = np.full(len(BLOCS), 20.0)
    else:
        h = (
            hist.loc[hist["annee"] < annee_cible, ["annee"] + [
                c for c in NAT_COLS if c in hist.columns
            ]]
            .drop_duplicates("annee")
            .sort_values("annee")
        )
        cols = [c for c in NAT_COLS if c in h.columns]
        if h.empty or not cols:
            arr = np.full(len(BLOCS), 20.0)
        elif len(h) == 1:
            arr = np.array([
                float(h.iloc[-1][f"pct_{b}_national"]) if f"pct_{b}_national" in h.columns else 20.0
                for b in BLOCS
            ], dtype=float)
        else:
            first, last = h.iloc[0], h.iloc[-1]
            span = int(last["annee"]) - int(first["annee"])
            dt = annee_cible - int(last["annee"])
            arr = np.array([
                float(last[f"pct_{b}_national"])
                + (((float(last[f"pct_{b}_national"]) - float(first[f"pct_{b}_national"])) / span) * dt
                   if span else 0.0)
                for b in BLOCS
            ], dtype=float)
    arr = _renorm_clip(arr)[0]
    return {b: round(float(arr[i]), 3) for i, b in enumerate(BLOCS)}


def valider_niveaux_nationaux(niveaux: dict) -> dict:
    """Normalise un dict {bloc: %} ; leve ValueError si la somme est hors [90;110]."""
    raw = {str(k).upper(): v for k, v in (niveaux or {}).items()}
    vals = []
    for b in BLOCS:
        try:
            v = float(raw[b])
        except (KeyError, TypeError, ValueError) as e:
            raise ValueError(f"niveau national manquant ou invalide pour {b}") from e
        vals.append(v)
    s = float(np.sum(vals))
    if s < SOMME_NATIONAL_MIN or s > SOMME_NATIONAL_MAX:
        raise ValueError(
            f"somme des niveaux nationaux = {s:.1f} ; attendu dans "
            f"[{SOMME_NATIONAL_MIN:.0f};{SOMME_NATIONAL_MAX:.0f}]"
        )
    arr = _renorm_clip(vals)[0]
    return {b: round(float(arr[i]), 3) for i, b in enumerate(BLOCS)}


def train_from_engine(engine):
    """Entraine le regresseur d'ecarts sur GOLD Postgres."""
    global _MODEL, _META, _IMPORTANCE, _CONFUSION, _ENVELOPE, _MEAN_SCORES, _NAT_HISTORY
    df = load_data.canonicalize_gold_df(
        pd.read_sql("SELECT * FROM gold_dataset_analytique", engine)
    )
    if "ecart_EXG" not in df.columns:
        raise RuntimeError(
            "GOLD sans ecarts — relancer etl/02_transform.py puis reload"
        )
    _NAT_HISTORY = (
        df[["annee"] + [c for c in NAT_COLS if c in df.columns]]
        .drop_duplicates("annee")
        .sort_values("annee")
        .copy()
    )
    df_ml = df.dropna(subset=["ecart_EXG_prec"]).reset_index(drop=True)
    if len(df_ml) == 0:
        raise RuntimeError("GOLD vide apres filtrage ecart_*_prec")

    num = [c for c in NUM_ALL if c in df_ml.columns and df_ml[c].notna().any()]
    name = _modele_retenu()
    model = ESTIMATEURS[name]()
    X = df_ml[num]
    y = df_ml[[c for c in TARGETS if c in df_ml.columns]]
    holdout = int(df_ml["annee"].max())
    te = df_ml["annee"] == holdout

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        if te.any() and (~te).any():
            model.fit(X[~te], y[~te])
            pred_ecart = np.asarray(model.predict(X[te]), dtype=float)
            nat = df_ml.loc[te, NAT_COLS].to_numpy(dtype=float)
            scores = _renorm_clip(nat + pred_ecart)
            y_true_bloc = df_ml.loc[te, "bloc_gagnant"].to_numpy()
            y_pred_bloc = np.array(BLOCS)[np.argmax(scores, axis=1)]
            labels = sorted(set(y_true_bloc) | set(y_pred_bloc))
            cm = confusion_matrix(y_true_bloc, y_pred_bloc, labels=labels)
            acc = float(accuracy_score(y_true_bloc, y_pred_bloc))
            _CONFUSION = {
                "labels": labels,
                "matrix": cm.tolist(),
                "accuracy_test_2022": round(acc, 3),
                "holdout_year": holdout,
                "tache": "argmax_ecarts_oracle",
            }
            model.fit(X[~te], y[~te])
        else:
            model.fit(X, y)
            _CONFUSION = {
                "labels": BLOCS, "matrix": [],
                "accuracy_test_2022": None, "holdout_year": holdout,
            }

    _MODEL = model
    _ENVELOPE = _compute_envelope(df_ml, num)
    _MEAN_SCORES = {
        b: round(float(pd.to_numeric(df[f"pct_{b}"], errors="coerce").mean()), 2)
        for b in BLOCS if f"pct_{b}" in df.columns
    }

    _IMPORTANCE = {}
    if os.path.isfile(ML_REPORT):
        try:
            with open(ML_REPORT, encoding="utf-8") as f:
                rep = json.load(f)
            _IMPORTANCE = rep.get("importance_variables") or {}
        except Exception:
            pass

    annee_max = int(df["annee"].max()) if len(df) else 2022
    _META = {
        "tache": "regression_ecarts_departementaux",
        "features_numeriques": num,
        "n_observations": int(len(df_ml)),
        "n_departements": int(df_ml["code_dept"].nunique()),
        "accuracy_test_2022": _CONFUSION.get("accuracy_test_2022"),
        "classes": BLOCS,
        "modele_retenu": name,
        "protocole": "walk-forward / holdout temporel / ecarts + scenario national",
        "enveloppe_entrainement": _ENVELOPE,
        "scores_moyens_entrainement": _MEAN_SCORES,
        "niveaux_nationaux_tendance": niveaux_nationaux_projetes(
            _NAT_HISTORY, annee_max + 5
        ),
        "annee_cible_tendance": annee_max + 5,
    }
    return _META


def is_ready() -> bool:
    return _MODEL is not None


def ensure_ready(engine) -> bool:
    """Ré-essaie l'entraînement si le startup a échoué (BDD Aiven tardive)."""
    if _MODEL is not None:
        return True
    try:
        train_from_engine(engine)
        print("[ml_service] modele pret (ensure_ready)")
        return True
    except Exception as e:
        print(f"[ml_service] ensure_ready echec : {e}")
        try:
            import load_data
            load_data.enrich_gold_ecarts(engine)
            train_from_engine(engine)
            print("[ml_service] modele pret (ensure_ready + enrich)")
            return True
        except Exception as e2:
            print(f"[ml_service] ensure_ready enrich echec : {e2}")
            return False


def meta() -> dict:
    return _META


def importance() -> dict:
    return {"modele_retenu": _META.get("modele_retenu"), "importances": _IMPORTANCE}


def confusion() -> dict:
    return _CONFUSION


def envelope() -> dict:
    return _ENVELOPE


def tendance_nationale(annee_cible: int | None = None) -> dict:
    cible = int(annee_cible or _META.get("annee_cible_tendance") or 2027)
    return niveaux_nationaux_projetes(_NAT_HISTORY, cible)


def clamp_features(features: dict) -> tuple[dict, list]:
    out = dict(features)
    overs: list = []
    for col, bounds in (_ENVELOPE or {}).items():
        if col not in out:
            continue
        val = _as_float(out.get(col))
        if val is None:
            continue
        lo, hi = float(bounds["min"]), float(bounds["max"])
        if val < lo or val > hi:
            overs.append({"feature": col, "valeur": val, "min": lo, "max": hi})
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
            "mae_ecart_walkforward_hors_holdout": metrics.get(
                "mae_ecart_walkforward_hors_holdout"
            ),
            "accuracy_oracle_hors_holdout": metrics.get("accuracy_oracle_hors_holdout"),
            "accuracy_oracle_holdout": metrics.get("accuracy_oracle_holdout"),
            "accuracy_projete_holdout": metrics.get("accuracy_projete_holdout"),
            "mae_score_oracle_holdout": metrics.get("mae_score_oracle_holdout"),
            "mae_score_projete_holdout": metrics.get("mae_score_projete_holdout"),
            "retenu": name == report.get("modele_retenu"),
        })
    rows.sort(
        key=lambda r: (r.get("mae_ecart_walkforward_hors_holdout") is not None,
                       -(r.get("mae_ecart_walkforward_hors_holdout") or 0)),
        reverse=True,
    )
    return {
        "modele_retenu": report.get("modele_retenu"),
        "n_observations": report.get("n_observations"),
        "protocole": report.get("protocole"),
        "metriques_retenues": report.get("metriques_retenues"),
        "holdout": report.get("holdout"),
        "classification_argmax_holdout": report.get("classification_argmax_holdout"),
        "poids_socio_eco": report.get("poids_socio_eco"),
        "note_r2": report.get("note_r2"),
        "metrique_principale": report.get("metrique_principale"),
        "modeles": rows,
        "source": "data/ml_report.json",
    }


def regression_metrics_from_report() -> dict:
    if not os.path.isfile(ML_REPORT):
        return {}
    with open(ML_REPORT, encoding="utf-8") as f:
        report = json.load(f)
    return {
        "holdout": report.get("holdout"),
        "regression_holdout": report.get("holdout"),
        "poids_socio_eco": report.get("poids_socio_eco"),
        "modele_retenu": report.get("modele_retenu"),
        "note_r2": report.get("note_r2"),
        "metrique_principale": report.get("metrique_principale", "MAE"),
        "choc_national_holdout": report.get("choc_national_holdout"),
    }


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


def _row_from_features(features: dict) -> pd.DataFrame:
    row = {c: features.get(c) for c in NUM_ALL}
    return pd.DataFrame([row])


def _predict_ecarts(features: dict) -> tuple[dict, list]:
    if _MODEL is None:
        raise RuntimeError("Modele non entraine")
    clamped, overs = clamp_features(features)
    X = _row_from_features(clamped)
    for c in getattr(_MODEL, "feature_names_in_", NUM_ALL):
        if c not in X.columns:
            X[c] = clamped.get(c)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        raw = np.asarray(_MODEL.predict(X), dtype=float)
    if raw.ndim == 1:
        raw = raw.reshape(1, -1)
    ecarts = {b: round(float(raw[0, i]), 3) for i, b in enumerate(BLOCS)}
    return ecarts, overs


def resolve_niveaux(
    scenario: str | None,
    niveaux: dict | None,
    annee_cible: int | None = None,
) -> tuple[dict, str]:
    """Retourne (niveaux renormalises, regime)."""
    sc = (scenario or "tendance").strip().lower()
    if niveaux:
        return valider_niveaux_nationaux(niveaux), "utilisateur"
    if sc in ("utilisateur", "user", "saisi"):
        raise ValueError("niveaux_nationaux requis pour le regime utilisateur")
    return tendance_nationale(annee_cible), "tendance"


def predict_scores(
    features: dict,
    scenario_national: str | None = "tendance",
    niveaux_nationaux: dict | None = None,
    annee_cible: int | None = None,
) -> dict:
    """Scores reconstruits + ecarts + niveaux + regime."""
    ecarts, overs = _predict_ecarts(features)
    nat, regime = resolve_niveaux(scenario_national, niveaux_nationaux, annee_cible)
    raw_scores = [nat[b] + ecarts[b] for b in BLOCS]
    scores_arr = _renorm_clip(raw_scores)[0]
    scores = {b: round(float(scores_arr[i]), 2) for i, b in enumerate(BLOCS)}
    winner = max(scores, key=scores.get)
    return {
        "scores": scores,
        "ecarts": ecarts,
        "niveaux_nationaux": nat,
        "regime": regime,
        "bloc_predit": winner,
        "hors_enveloppe": overs,
    }


def predict_proba(features: dict) -> dict:
    out = predict_scores(features)
    return {b: round(v / 100.0, 3) for b, v in out["scores"].items()}


def extrapolate_features(features: dict, n_annees: int) -> dict:
    """Pousse les leviers socio de n_annees (rythme observé N−1)."""
    n = max(0, int(n_annees))
    out = dict(features)
    if n == 0:
        return out
    chom = _as_float(out.get("taux_chomage_n1"))
    d5 = _as_float(out.get("delta_chomage_5a"))
    if chom is not None and d5 is not None:
        out["taux_chomage_n1"] = round(chom + (d5 / 5.0) * n, 3)
    emp = _as_float(out.get("emploi_pour_1000hab"))
    g_emp = _as_float(out.get("croissance_emploi_5a_pct"))
    if emp is not None and g_emp is not None:
        annual = (1.0 + g_emp / 100.0) ** (1.0 / 5.0)
        out["emploi_pour_1000hab"] = round(emp * (annual ** n), 2)
    return out


def annee_observation(annee_cible: int | None = None) -> int:
    """Dernier scrutin GOLD (les features socio sont à cette date)."""
    if _NAT_HISTORY is not None and not _NAT_HISTORY.empty:
        return int(_NAT_HISTORY["annee"].max())
    if annee_cible:
        return int(annee_cible) - 5
    return 2022


def annee_courante() -> int:
    return int(date.today().year)


def predict_proba_horizons(
    features: dict,
    scenario_national: str | None = "tendance",
    niveaux_nationaux: dict | None = None,
    annee_cible: int | None = None,
) -> tuple[dict, dict, dict, dict, dict, dict, str]:
    """Scores = tendance(now+h) + écart(socio interpolé depuis le dernier scrutin).

    1 / 2 / 3 ans partent d'aujourd'hui (2026 → 2027, 2028, 2029),
    pas du dernier scrutin (ce qui rejouait 2023–2025).
    """
    if _MODEL is None:
        raise RuntimeError("Modele non entraine")
    obs = annee_observation(annee_cible)
    now = annee_courante()
    sc = (scenario_national or "tendance").strip().lower()
    freeze_nat = bool(niveaux_nationaux) or sc in ("utilisateur", "user", "saisi")
    nat_fixe, regime = resolve_niveaux(scenario_national, niveaux_nationaux, annee_cible)
    scores_h, overs_h, blocs_h = {}, {}, {}
    ecarts_h, nat_h, annees_h = {}, {}, {}
    for h in (1, 2, 3):
        annee_h = now + h
        n_extrap = max(0, annee_h - obs)
        feats = extrapolate_features(features, n_extrap)
        if freeze_nat:
            nat = nat_fixe
            reg = regime
        else:
            nat = tendance_nationale(annee_h)
            reg = "tendance"
        raw = predict_scores(
            feats,
            scenario_national="utilisateur",
            niveaux_nationaux=nat,
            annee_cible=annee_h,
        )
        key = str(h)
        scores_h[key] = raw["scores"]
        overs_h[key] = raw["hors_enveloppe"]
        blocs_h[key] = raw["bloc_predit"]
        ecarts_h[key] = raw["ecarts"]
        nat_h[key] = nat
        annees_h[key] = annee_h
        regime = reg
    return scores_h, overs_h, blocs_h, ecarts_h, nat_h, annees_h, regime
