# -*- coding: utf-8 -*-
"""
ML — Regression multi-sorties sur les ECARTS departementaux.

Decomposition : pct_B = niveau_national_B + ecart_B.
Le modele apprend l'ecart (geographie). Le niveau national est une entree
de scenario (oracle en eval A, tendance en eval B, curseurs en production).

Protocole (inchange) :
  1. Features anti-leakage : derivees d'ecart (scrutins < N) + socio-eco N-1.
  2. Walk-forward leave-one-election-out ; selection = plis hors holdout.
  3. Holdout = dernier scrutin : metrique REPORTEE uniquement.
  4. CV geographique GroupKFold en metrique secondaire.
"""
from __future__ import annotations

import json
import os
import warnings

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, RegressorMixin, clone
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.metrics import (
    ConfusionMatrixDisplay,
    accuracy_score,
    confusion_matrix,
    mean_absolute_error,
    mean_squared_error,
    r2_score,
)
from sklearn.model_selection import GroupKFold, cross_val_score
from sklearn.multioutput import MultiOutputRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

ROOT = os.path.join(os.path.dirname(__file__), "..")
GOLD = f"{ROOT}/data/gold"
VIZ = f"{ROOT}/viz/output"
os.makedirs(VIZ, exist_ok=True)

BLOCS = ["EXG", "GAU", "CEN", "DRO", "EXD"]
TARGETS = [f"ecart_{b}" for b in BLOCS]
SCORE_COLS = [f"pct_{b}" for b in BLOCS]
NAT_COLS = [f"pct_{b}_national" for b in BLOCS]

ECART_FEATURES = []
for b in BLOCS:
    ECART_FEATURES.extend([
        f"ecart_{b}_prec",
        f"delta_recent_ecart_{b}",
        f"delta_long_ecart_{b}",
        f"trend_ecart_{b}",
        f"volatility_ecart_{b}",
    ])

SOCIO_FEATURES = [
    "taux_chomage_n1", "delta_chomage_1a", "delta_chomage_5a",
    "emploi_pour_1000hab", "croissance_emploi_5a_pct", "croissance_pop_5a_pct",
]

HASARD_5_CLASSES = 0.20

# Diagnostic du Ridge-par-bloc sur les NIVEAUX (pipeline precedent).
# Chiffres issus de l'inspection holdout 2022 avant bascule ecarts.
DIAGNOSTIC_RIDGE_NIVEAUX = {
    "verdict": "comportement_legitime",
    "pas_un_bug_de_code": True,
    "fait": (
        "ridge_par_bloc (alpha=10, selection argmax/R2) : MAE holdout 14,38 "
        "contre 7,23 pour la persistance. Ce n'est pas une erreur d'implementation."
    ),
    "grille_alpha": (
        "L'optimum MAE est en BOUT de grille (alpha=1000 : MAE 11,99 ; "
        "alpha=10000 : 11,49) et reste au-dessus de la persistance. "
        "La selection sur accuracy argmax a retenu alpha=10 (sel_acc=0,203), "
        "pire en MAE. Pas un alpha hors grille manquant qui inverserait le constat."
    ),
    "coefficients": (
        "A alpha=10, trend_DRO=+3,8 et delta_long_EXD=-6,1 (features standardisees). "
        "A alpha=0,1 les predictions sortent de [-16;82]. Le Ridge extrapole la "
        "pente apprise sur 2007-2017, qui encode des chocs nationaux, pas une "
        "derivee departementale stable."
    ),
    "imputation": (
        "En 2007 (un seul prior) : delta_recent, trend et volatility sont 100 % NaN "
        "(imputes mediane) ; delta_long vaut 0 (premier=dernier). En 2022 toutes "
        "les features de tendance sont observees : l'imputation n'explique pas "
        "la MAE holdout."
    ),
    "renormalisation": (
        "Les cinq Ridge independants ne somment pas a 100. Clip+renorm degrade "
        "peu a alpha=10 (MAE brute 14,14 vs 14,38 renormalisee)."
    ),
    "conclusion": (
        "Un Ridge sur la trajectoire d'un bloc predit le prochain NIVEAU en "
        "extrapoleant une tendance qui, ici, est nationale. Recopier le score "
        "precedent reste meilleur. Non retune."
    ),
}


df_raw = pd.read_csv(f"{GOLD}/dataset_analytique.csv", dtype={"code_dept": str})
if "ecart_EXG" not in df_raw.columns:
    raise RuntimeError(
        "GOLD sans decomposition nationale/ecart — relancer etl/02_transform.py"
    )

_n_avant = len(df_raw)
df = df_raw.dropna(subset=["ecart_EXG_prec"]).reset_index(drop=True)
_DECISIONS_FEATURES = {
    "scrutins_exploitables_regression": {
        "choix": "exiger_un_prior_ecart",
        "option_retenue": "B",
        "n_observations_avant": int(_n_avant),
        "n_observations_apres": int(len(df)),
        "fait": (
            "delta_recent_ecart et volatility_ecart demandent 2 scrutins "
            "anterieurs ; ecart_*_prec en demande 1. Sur GOLD reel : 5 elections "
            "-> 4 avec lag."
        ),
        "option_A_ecartee": (
            "Exiger 2 priors (drop 2007) -> annees 2012/2017/2022 -> 1 seul pli "
            "de selection hors holdout (2017)."
        ),
        "option_B_retenue": (
            "Exiger 1 prior (ecart_*_prec non nul) -> 384 obs (2007..2022) -> "
            "2 plis de selection (2012, 2017). Les NaN de delta_recent/volatility "
            "sur le premier scrutin concerne sont imputes (mediane)."
        ),
        "justification": (
            "Maximiser le nombre de plis de selection hors holdout (minimum 2) "
            "tout en restant anti-leakage."
        ),
    },
    "creations_entreprises_n1": {
        "choix": "exclure_variable",
        "motif": (
            "Serie SIDE trop courte au regard du lag N-1 (null 2007/2012) ; "
            "hors modele supervise, reste en GOLD/BI."
        ),
    },
    "taux_pauvrete_n1": {
        "choix": "exclure_variable",
        "motif": "Couverture trop courte (scrutins 2017/2022 seulement).",
    },
    "cible": {
        "choix": "ecart_departemental",
        "motif": (
            "Le choc 2022 est national (DRO -17,5 pts). Un modele sur les niveaux "
            "departementaux ne peut pas l'anticiper. On apprend l'ecart au national ; "
            "le niveau national est un scenario."
        ),
    },
}

NUM = [c for c in ECART_FEATURES + SOCIO_FEATURES if c in df.columns and df[c].notna().any()]
if not NUM:
    raise RuntimeError("Aucune feature numerique exploitable")

X = df[NUM]
y = df[TARGETS]
groups = df["code_dept"]
years = sorted(int(a) for a in df["annee"].unique())
holdout_year = years[-1]
PLIS_SELECTION = [y for y in years[1:] if y != holdout_year]


class PersistenceBundle(BaseEstimator, RegressorMixin):
    """Baseline : ecart_B predit = ecart_B_prec."""

    def __init__(self, prec_cols=None):
        self.prec_cols = prec_cols

    def _prec(self):
        return list(self.prec_cols) if self.prec_cols is not None else [
            f"ecart_{b}_prec" for b in BLOCS
        ]

    def fit(self, X, y=None):
        if not isinstance(X, pd.DataFrame):
            X = pd.DataFrame(X, columns=NUM)
        prec = self._prec()
        missing = [c for c in prec if c not in X.columns]
        if missing:
            raise ValueError(f"Colonnes prec manquantes : {missing}")
        self.feature_names_in_ = list(X.columns)
        self.n_features_in_ = X.shape[1]
        self.n_outputs_ = len(prec)
        return self

    def predict(self, X):
        if not isinstance(X, pd.DataFrame):
            X = pd.DataFrame(X, columns=self.feature_names_in_)
        return np.nan_to_num(X[self._prec()].to_numpy(dtype=float), nan=0.0)


class RidgeParBloc(BaseEstimator, RegressorMixin):
    """Un Ridge par bloc : trajectoire de SON ecart + features socio-eco."""

    def __init__(self, alpha=10.0):
        self.alpha = alpha

    def fit(self, X, y):
        if not isinstance(X, pd.DataFrame):
            X = pd.DataFrame(X, columns=NUM)
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


def make_ridge_multi(alpha: float) -> Pipeline:
    return Pipeline([
        ("imp", SimpleImputer(strategy="median")),
        ("sc", StandardScaler()),
        ("reg", Ridge(alpha=alpha)),
    ])


def make_rf() -> Pipeline:
    return Pipeline([
        ("imp", SimpleImputer(strategy="median")),
        ("sc", StandardScaler()),
        ("reg", MultiOutputRegressor(
            RandomForestRegressor(
                n_estimators=200, max_depth=6, min_samples_leaf=5, random_state=42,
            )
        )),
    ])


def _as_df_X(X_):
    return X_ if isinstance(X_, pd.DataFrame) else pd.DataFrame(X_, columns=NUM)


def _as_df_y(y_):
    return y_ if isinstance(y_, pd.DataFrame) else pd.DataFrame(y_, columns=TARGETS)


def _renorm_clip(pred: np.ndarray) -> np.ndarray:
    p = np.clip(np.asarray(pred, dtype=float), 0.0, 100.0)
    s = p.sum(axis=1, keepdims=True)
    s = np.where(s <= 0, 1.0, s)
    return p / s * 100.0


def _reg_vec(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    per = {}
    for i, b in enumerate(BLOCS):
        yt, yp = y_true[:, i], y_pred[:, i]
        per[b] = {
            "r2": round(float(r2_score(yt, yp)), 3),
            "rmse": round(float(np.sqrt(mean_squared_error(yt, yp))), 3),
            "mae": round(float(mean_absolute_error(yt, yp)), 3),
        }
    per["agrege"] = {
        "r2_macro": round(float(np.mean([per[b]["r2"] for b in BLOCS])), 3),
        "rmse_moyen": round(float(np.mean([per[b]["rmse"] for b in BLOCS])), 3),
        "mae_moyen": round(float(np.mean([per[b]["mae"] for b in BLOCS])), 3),
    }
    return per


def niveaux_nationaux_projetes(frame: pd.DataFrame, annee_cible: int) -> np.ndarray:
    """Tendance lineaire simple sur les niveaux nationaux anterieurs.

    pente = (dernier - premier) / span_annees, puis
    niveau = dernier + pente * (cible - dernier).
    Un seul scrutin anterieur : persistance du niveau national.
    Puis clip [0;100] et renormalisation a 100.
    """
    hist = (
        frame.loc[frame["annee"] < annee_cible, ["annee"] + NAT_COLS]
        .drop_duplicates("annee")
        .sort_values("annee")
    )
    if hist.empty:
        arr = np.full(len(BLOCS), 20.0)
    elif len(hist) == 1:
        arr = hist[NAT_COLS].iloc[-1].to_numpy(dtype=float)
    else:
        first, last = hist.iloc[0], hist.iloc[-1]
        span = int(last["annee"]) - int(first["annee"])
        dt = annee_cible - int(last["annee"])
        arr = np.array([
            float(last[c]) + ((float(last[c]) - float(first[c])) / span) * dt
            if span else float(last[c])
            for c in NAT_COLS
        ], dtype=float)
    return _renorm_clip(arr.reshape(1, -1))[0]


def reconstruct(ecart_pred: np.ndarray, national: np.ndarray) -> np.ndarray:
    nat = np.asarray(national, dtype=float)
    if nat.ndim == 1:
        nat = np.broadcast_to(nat, (len(ecart_pred), nat.shape[0]))
    return _renorm_clip(nat + np.asarray(ecart_pred, dtype=float))


def _argmax_blocs(scores: np.ndarray) -> np.ndarray:
    idx = np.argmax(_renorm_clip(scores), axis=1)
    return np.array(BLOCS)[idx]


def _eval_fold(df_te, pred_ecart, y_ecart, y_scores, nat_true, nat_proj) -> dict:
    m_ecart = _reg_vec(y_ecart, pred_ecart)
    scores_a = reconstruct(pred_ecart, nat_true)
    scores_b = reconstruct(pred_ecart, nat_proj)
    m_a = _reg_vec(y_scores, scores_a)
    m_b = _reg_vec(y_scores, scores_b)
    y_true_bloc = df_te["bloc_gagnant"].to_numpy()
    acc_a = float(accuracy_score(y_true_bloc, _argmax_blocs(scores_a)))
    acc_b = float(accuracy_score(y_true_bloc, _argmax_blocs(scores_b)))
    prec_bloc = df_te["bloc_gagnant_precedent"].to_numpy()
    mask = pd.notna(prec_bloc)
    acc_prec = float(accuracy_score(y_true_bloc[mask], prec_bloc[mask])) if mask.any() else 0.0
    mode_bloc = pd.Series(y_true_bloc).mode().iloc[0]
    acc_maj = float((y_true_bloc == mode_bloc).mean())
    persist_scores = df_te[[f"pct_{b}_prec" for b in BLOCS]].to_numpy(dtype=float)
    persist_scores = _renorm_clip(np.nan_to_num(persist_scores, nan=0.0))
    acc_persist_level = float(accuracy_score(y_true_bloc, _argmax_blocs(persist_scores)))
    m_persist_level = _reg_vec(y_scores, persist_scores)
    persist_ecart = df_te[[f"ecart_{b}_prec" for b in BLOCS]].to_numpy(dtype=float)
    persist_ecart = np.nan_to_num(persist_ecart, nan=0.0)
    m_persist_ecart = _reg_vec(y_ecart, persist_ecart)
    scores_persist_a = reconstruct(persist_ecart, nat_true)
    scores_persist_b = reconstruct(persist_ecart, nat_proj)
    acc_persist_ecart_a = float(accuracy_score(y_true_bloc, _argmax_blocs(scores_persist_a)))
    acc_persist_ecart_b = float(accuracy_score(y_true_bloc, _argmax_blocs(scores_persist_b)))
    m_persist_a = _reg_vec(y_scores, scores_persist_a)
    m_persist_b = _reg_vec(y_scores, scores_persist_b)
    return {
        "n": int(len(df_te)),
        "mae_ecart": m_ecart["agrege"]["mae_moyen"],
        "rmse_ecart": m_ecart["agrege"]["rmse_moyen"],
        "r2_ecart": m_ecart["agrege"]["r2_macro"],
        "par_bloc_ecart": {b: m_ecart[b] for b in BLOCS},
        "oracle": {
            "mae_score": m_a["agrege"]["mae_moyen"],
            "rmse_score": m_a["agrege"]["rmse_moyen"],
            "r2_score": m_a["agrege"]["r2_macro"],
            "par_bloc_score": {b: m_a[b] for b in BLOCS},
            "accuracy_argmax": round(acc_a, 3),
            "baseline_persistance_ecart": {
                "mae_score": m_persist_a["agrege"]["mae_moyen"],
                "accuracy_argmax": round(acc_persist_ecart_a, 3),
                "par_bloc_score": {b: m_persist_a[b] for b in BLOCS},
            },
        },
        "projete": {
            "mae_score": m_b["agrege"]["mae_moyen"],
            "rmse_score": m_b["agrege"]["rmse_moyen"],
            "r2_score": m_b["agrege"]["r2_macro"],
            "par_bloc_score": {b: m_b[b] for b in BLOCS},
            "accuracy_argmax": round(acc_b, 3),
            "baseline_persistance_ecart": {
                "mae_score": m_persist_b["agrege"]["mae_moyen"],
                "accuracy_argmax": round(acc_persist_ecart_b, 3),
                "par_bloc_score": {b: m_persist_b[b] for b in BLOCS},
            },
        },
        "baseline_persistance_niveau": {
            "mae_score": m_persist_level["agrege"]["mae_moyen"],
            "rmse_score": m_persist_level["agrege"]["rmse_moyen"],
            "par_bloc_score": {b: m_persist_level[b] for b in BLOCS},
            "accuracy_argmax": round(acc_persist_level, 3),
        },
        "baseline_persistance_ecart_mae": m_persist_ecart["agrege"]["mae_moyen"],
        "accuracy_baseline_gagnant_precedent": round(acc_prec, 3),
        "accuracy_baseline_classe_majoritaire": round(acc_maj, 3),
        "classe_majoritaire": str(mode_bloc),
    }


def walk_forward_scores(estimator) -> dict:
    per_year = {}
    sel_mae, sel_acc_a = [], []
    all_mae, all_acc_a = [], []
    for y_test in years[1:]:
        tr = df["annee"] < y_test
        te = df["annee"] == y_test
        if tr.sum() == 0 or te.sum() == 0:
            continue
        est = clone(estimator)
        Xtr, Xte = _as_df_X(X[tr]), _as_df_X(X[te])
        ytr = _as_df_y(y[tr])
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            est.fit(Xtr, ytr)
            pred = np.asarray(est.predict(Xte), dtype=float)
        nat_true = df.loc[te, NAT_COLS].to_numpy(dtype=float)
        nat_proj = niveaux_nationaux_projetes(df_raw, int(y_test))
        entry = _eval_fold(
            df.loc[te],
            pred,
            y.loc[te].to_numpy(dtype=float),
            df.loc[te, SCORE_COLS].to_numpy(dtype=float),
            nat_true,
            nat_proj,
        )
        per_year[str(y_test)] = entry
        all_mae.append(entry["mae_ecart"])
        all_acc_a.append(entry["oracle"]["accuracy_argmax"])
        if int(y_test) != holdout_year:
            sel_mae.append(entry["mae_ecart"])
            sel_acc_a.append(entry["oracle"]["accuracy_argmax"])

    def _mean(xs):
        return round(float(np.mean(xs)), 3) if xs else 0.0

    hold = per_year.get(str(holdout_year), {})
    return {
        "par_scrutin": per_year,
        "mae_ecart_walkforward": _mean(all_mae),
        "mae_ecart_walkforward_hors_holdout": _mean(sel_mae),
        "accuracy_oracle_walkforward": _mean(all_acc_a),
        "accuracy_oracle_hors_holdout": _mean(sel_acc_a),
        "mae_ecart_holdout": hold.get("mae_ecart", 0.0),
        "accuracy_oracle_holdout": (hold.get("oracle") or {}).get("accuracy_argmax", 0.0),
        "accuracy_projete_holdout": (hold.get("projete") or {}).get("accuracy_argmax", 0.0),
        "mae_score_oracle_holdout": (hold.get("oracle") or {}).get("mae_score", 0.0),
        "mae_score_projete_holdout": (hold.get("projete") or {}).get("mae_score", 0.0),
    }


def _selection_tuple(m: dict) -> tuple:
    """Selection hors holdout : MAE des ecarts (principale), argmax oracle en departage.

    Le R2 n'entre pas dans la selection (denominateur trop faible, voir note_r2).
    """
    return (
        -float(m["mae_ecart_walkforward_hors_holdout"]),
        float(m["accuracy_oracle_hors_holdout"]),
    )


ridge_grid = []
for alpha in [0.1, 1, 10, 100, 1000]:
    for kind in ("multi", "par_bloc"):
        name = f"ridge_{kind}_a{alpha}"
        est = make_ridge_multi(alpha) if kind == "multi" else RidgeParBloc(alpha=alpha)
        wf = walk_forward_scores(est)
        ridge_grid.append((name, kind, alpha, est, wf))

ridge_grid.sort(key=lambda t: _selection_tuple(t[4]), reverse=True)
best_ridge_name, best_ridge_kind, best_ridge_alpha, _, best_ridge_wf = ridge_grid[0]
print(
    f"Meilleur Ridge grille : {best_ridge_name} "
    f"sel_mae_ecart={best_ridge_wf['mae_ecart_walkforward_hors_holdout']:.3f} "
    f"holdout_oracle_acc={best_ridge_wf['accuracy_oracle_holdout']:.3f}"
)

models = {
    "baseline_persistance_ecart": PersistenceBundle(),
    "ridge_ecart_par_bloc": RidgeParBloc(
        alpha=best_ridge_alpha if best_ridge_kind == "par_bloc" else 10.0
    ),
    "ridge_ecart_multisorties": make_ridge_multi(
        best_ridge_alpha if best_ridge_kind == "multi" else 10.0
    ),
    "random_forest_ecart_multisorties": make_rf(),
}
if best_ridge_kind == "par_bloc":
    models["ridge_ecart_par_bloc"] = RidgeParBloc(alpha=best_ridge_alpha)
else:
    models["ridge_ecart_multisorties"] = make_ridge_multi(best_ridge_alpha)

results = {}
for name, est in models.items():
    wf = walk_forward_scores(est)
    results[name] = {
        "mae_ecart_walkforward": wf["mae_ecart_walkforward"],
        "mae_ecart_walkforward_hors_holdout": wf["mae_ecart_walkforward_hors_holdout"],
        "accuracy_oracle_hors_holdout": wf["accuracy_oracle_hors_holdout"],
        "accuracy_oracle_walkforward": wf["accuracy_oracle_walkforward"],
        "mae_ecart_holdout": wf["mae_ecart_holdout"],
        "accuracy_oracle_holdout": wf["accuracy_oracle_holdout"],
        "accuracy_projete_holdout": wf["accuracy_projete_holdout"],
        "mae_score_oracle_holdout": wf["mae_score_oracle_holdout"],
        "mae_score_projete_holdout": wf["mae_score_projete_holdout"],
        "walkforward_par_scrutin": wf["par_scrutin"],
    }

cand = {k: v for k, v in results.items() if k != "baseline_persistance_ecart"}
best_name = max(cand, key=lambda k: _selection_tuple(cand[k]))
best = clone(models[best_name])

tr = df["annee"] < holdout_year
te = df["annee"] == holdout_year
Xtr, Xte = _as_df_X(X[tr]), _as_df_X(X[te])
ytr = _as_df_y(y[tr])
best.fit(Xtr, ytr)
pred_te = np.asarray(best.predict(Xte), dtype=float)
nat_true = df.loc[te, NAT_COLS].to_numpy(dtype=float)
nat_proj = niveaux_nationaux_projetes(df_raw, holdout_year)
hold_eval = _eval_fold(
    df.loc[te],
    pred_te,
    y.loc[te].to_numpy(dtype=float),
    df.loc[te, SCORE_COLS].to_numpy(dtype=float),
    nat_true,
    nat_proj,
)

y_true_bloc = df.loc[te, "bloc_gagnant"].to_numpy()
scores_oracle = reconstruct(pred_te, nat_true)
y_pred_bloc = _argmax_blocs(scores_oracle)
acc_holdout_a = hold_eval["oracle"]["accuracy_argmax"]
acc_holdout_b = hold_eval["projete"]["accuracy_argmax"]
acc_prec = hold_eval["accuracy_baseline_gagnant_precedent"]
acc_maj = hold_eval["accuracy_baseline_classe_majoritaire"]
mode_2022 = hold_eval["classe_majoritaire"]

std_holdout = {
    b: round(float(df.loc[te, f"pct_{b}"].std(ddof=1)), 3) for b in BLOCS
}
nat_holdout = {
    b: round(float(df.loc[te, f"pct_{b}_national"].iloc[0]), 3) for b in BLOCS
}
nat_prev_year = int(df.loc[tr, "annee"].max())
nat_prev = {
    b: round(float(df.loc[df["annee"] == nat_prev_year, f"pct_{b}_national"].iloc[0]), 3)
    for b in BLOCS
}
nat_delta = {b: round(nat_holdout[b] - nat_prev[b], 3) for b in BLOCS}

note_r2 = (
    f"Le R2 a un denominateur minuscule quand la variance inter-departements "
    f"est faible. Holdout {holdout_year} : ecart-type DRO={std_holdout['DRO']} pt "
    f"alors que le choc national DRO vaut {nat_delta['DRO']} pts "
    f"({nat_prev['DRO']} -> {nat_holdout['DRO']}). "
    "Des R2 tres negatifs ne sont pas des bugs : ne pas les citer comme "
    "mesure de performance. Metrique principale = MAE."
)

# CV geo (MAE des ecarts) — secondaire, hors selection
try:
    cv_geo = GroupKFold(n_splits=5)

    def _mae_scorer(est, X_, y_):
        p = est.predict(_as_df_X(X_))
        return -mean_absolute_error(_as_df_y(y_).to_numpy(), p)

    cv_scores = cross_val_score(
        clone(best), X, y, cv=cv_geo, groups=groups, scoring=_mae_scorer,
    )
    mae_cv = round(float(-cv_scores.mean()), 3)
except Exception:
    mae_cv = None

labels = sorted(set(y_true_bloc) | set(y_pred_bloc))
cm = confusion_matrix(y_true_bloc, y_pred_bloc, labels=labels)
fig, ax = plt.subplots(figsize=(6, 5))
ConfusionMatrixDisplay(cm, display_labels=labels).plot(ax=ax, cmap="Blues", colorbar=False)
ax.set_title(f"Confusion argmax oracle — {best_name} (test {holdout_year})")
fig.tight_layout()
fig.savefig(f"{VIZ}/5_confusion.png", dpi=150)
plt.close(fig)

fig, ax = plt.subplots(figsize=(8.5, 4.8))
names = list(results.keys())
acc_a = [results[n]["accuracy_oracle_holdout"] for n in names]
acc_b = [results[n]["accuracy_projete_holdout"] for n in names]
xpos = np.arange(len(names))
ax.bar(xpos - 0.2, acc_a, 0.4, label="Argmax oracle (nat. connu)", color="#0066CC")
ax.bar(xpos + 0.2, acc_b, 0.4, label="Argmax projeté (tendance)", color="#E31B23")
ax.axhline(acc_maj, ls="--", color="grey", label=f"Majoritaire {holdout_year}")
ax.axhline(acc_prec, ls=":", color="black", label="Gagnant précédent")
ax.set_xticks(xpos)
ax.set_xticklabels([n.replace("_", "\n") for n in names], fontsize=8)
ax.set_ylim(0, 1)
ax.legend(fontsize=8)
ax.set_title("Accuracy de l'argmax — régimes A (oracle) et B (projeté)")
fig.tight_layout()
fig.savefig(f"{VIZ}/6_model_compare.png", dpi=150)
plt.close(fig)

fig, axes = plt.subplots(1, 2, figsize=(9, 4))
mae_a = [hold_eval["oracle"]["par_bloc_score"][b]["mae"] for b in BLOCS]
mae_persist_a = [
    hold_eval["oracle"]["baseline_persistance_ecart"]["par_bloc_score"][b]["mae"]
    for b in BLOCS
]
mae_b = [hold_eval["projete"]["par_bloc_score"][b]["mae"] for b in BLOCS]
mae_niv = [hold_eval["baseline_persistance_niveau"]["par_bloc_score"][b]["mae"] for b in BLOCS]
x = np.arange(len(BLOCS))
axes[0].bar(x - 0.2, mae_a, 0.4, label=best_name, color="#0066CC")
axes[0].bar(x + 0.2, mae_persist_a, 0.4, label="persist. écart", color="#888888")
axes[0].set_xticks(x)
axes[0].set_xticklabels(BLOCS)
axes[0].set_title(f"MAE scores — oracle {holdout_year}")
axes[0].legend(fontsize=8)
axes[1].bar(x - 0.2, mae_b, 0.4, label=best_name, color="#E31B23")
axes[1].bar(x + 0.2, mae_niv, 0.4, label="persist. niveau", color="#888888")
axes[1].set_xticks(x)
axes[1].set_xticklabels(BLOCS)
axes[1].set_title(f"MAE scores — projeté {holdout_year}")
axes[1].legend(fontsize=8)
fig.tight_layout()
fig.savefig(f"{VIZ}/7_importance.png", dpi=150)
plt.close(fig)

socio_weight = {}
if best_name.startswith("ridge") and hasattr(best, "named_steps"):
    coefs = np.abs(best.named_steps["reg"].coef_)
    mean_abs = coefs.mean(axis=0)
    imp = dict(zip(NUM, np.round(mean_abs, 4).tolist()))
    imp = dict(sorted(imp.items(), key=lambda kv: -kv[1]))
elif isinstance(best, RidgeParBloc):
    imp = {}
    for b, pipe in best.models_.items():
        cols = best.cols_per_bloc_[b]
        c = np.abs(pipe.named_steps["ridge"].coef_)
        for col, v in zip(cols, c):
            imp[col] = imp.get(col, 0.0) + float(v)
    imp = {k: round(v / len(BLOCS), 4) for k, v in imp.items()}
    imp = dict(sorted(imp.items(), key=lambda kv: -kv[1]))
elif hasattr(best, "named_steps") and hasattr(best.named_steps.get("reg"), "estimators_"):
    imps = [est_i.feature_importances_ for est_i in best.named_steps["reg"].estimators_]
    mean_imp = np.mean(imps, axis=0)
    imp = dict(zip(NUM, np.round(mean_imp, 4).tolist()))
    imp = dict(sorted(imp.items(), key=lambda kv: -kv[1]))
else:
    imp = {}

socio_in_imp = {k: v for k, v in imp.items() if k in SOCIO_FEATURES}
elec_in_imp = {k: v for k, v in imp.items() if k not in SOCIO_FEATURES}
tot = sum(imp.values()) or 1.0
socio_weight = {
    "part_socio_eco": round(sum(socio_in_imp.values()) / tot, 3),
    "part_electorale": round(sum(elec_in_imp.values()) / tot, 3),
    "top_socio": list(socio_in_imp.items())[:5],
    "top_global": list(imp.items())[:10],
}


def _enveloppe(frame, cols):
    out = {}
    for c in cols:
        if c not in frame.columns:
            continue
        s = pd.to_numeric(frame[c], errors="coerce").dropna()
        if s.empty:
            continue
        out[c] = {
            "min": round(float(s.min()), 4),
            "max": round(float(s.max()), 4),
            "p01": round(float(s.quantile(0.01)), 4),
            "p99": round(float(s.quantile(0.99)), 4),
            "moyenne": round(float(s.mean()), 4),
            "ecart_type": round(float(s.std(ddof=1)), 4) if len(s) > 1 else 0.0,
        }
    return out


sel_acc = results[best_name]["accuracy_oracle_hors_holdout"]
avert_sel = (
    f"Selection sur {len(PLIS_SELECTION)} pli(s) {PLIS_SELECTION} ; "
    f"holdout {holdout_year} reporte uniquement. "
)
if sel_acc < HASARD_5_CLASSES:
    avert_sel += (
        f"L'accuracy de selection oracle ({sel_acc}) est sous le hasard a 5 classes "
        f"({HASARD_5_CLASSES:.2f}) : deux plis de 96 lignes n'ont pas de pouvoir "
        "discriminant. Ne pas interpreter le modele retenu comme 'meilleur predicteur'."
    )

mae_oracle = hold_eval["oracle"]["mae_score"]
mae_persist_ecart_a = hold_eval["oracle"]["baseline_persistance_ecart"]["mae_score"]
mae_persist_niv = hold_eval["baseline_persistance_niveau"]["mae_score"]
bat_persist_a = mae_oracle < mae_persist_ecart_a
note_regime_a = (
    "Le modele bat la persistance de l'ecart en regime A (national connu)."
    if bat_persist_a else
    "Le modele NE BAT PAS la persistance de l'ecart en regime A (national connu). "
    "Non retune : meme avec le niveau national oriente, la geographie n'est pas "
    "mieux predite qu'un simple decalage constant. Conclusion exploitable."
)

nat_proj_dict = {b: round(float(nat_proj[i]), 3) for i, b in enumerate(BLOCS)}

report = {
    "tache": "regression_ecarts_departementaux",
    "metrique_principale": "MAE",
    "note_r2": note_r2,
    "n_observations": int(len(df)),
    "n_departements": int(df["code_dept"].nunique()),
    "annees": years,
    "cibles": TARGETS,
    "features": NUM,
    "protocole": {
        "selection": "walk-forward hors holdout uniquement",
        "formule_selection": (
            "minimiser MAE_ecart_hors_holdout ; departage = accuracy_argmax_oracle"
        ),
        "plis_selection": PLIS_SELECTION,
        "n_plis_selection": len(PLIS_SELECTION),
        "avertissement": avert_sel,
        "holdout": holdout_year,
        "anti_leakage": (
            "features d'ecart = scrutins < N ; socio-eco <= N-1 ; "
            "le niveau national du scrutin teste n'entre JAMAIS dans X"
        ),
        "cv_geographique": "GroupKFold (metrique secondaire, MAE des ecarts)",
        "hasard_5_classes": HASARD_5_CLASSES,
        "projection_nationale": (
            "tendance lineaire : dernier niveau + (dernier-premier)/span * "
            "(cible-dernier) ; un seul prior = persistance ; clip+renorm 100"
        ),
    },
    "decisions_features": _DECISIONS_FEATURES,
    "diagnostic_ridge_par_bloc_niveaux": DIAGNOSTIC_RIDGE_NIVEAUX,
    "enveloppe_entrainement": _enveloppe(df, NUM),
    "choc_national_holdout": {
        "annee": holdout_year,
        "annee_precedente": nat_prev_year,
        "niveau_national": nat_holdout,
        "niveau_national_precedent": nat_prev,
        "delta_national": nat_delta,
        "ecart_type_inter_departements": std_holdout,
        "niveau_national_projete": nat_proj_dict,
    },
    "modeles_compares": results,
    "modele_retenu": best_name,
    "hyperparams_retenus": {
        "ridge_grille_meilleure": best_ridge_name,
        "ridge_alpha": best_ridge_alpha,
        "ridge_kind": best_ridge_kind,
    },
    "ridge_grille": [
        {
            "name": n,
            "kind": k,
            "alpha": a,
            "mae_ecart_hors_holdout": w["mae_ecart_walkforward_hors_holdout"],
            "accuracy_oracle_hors_holdout": w["accuracy_oracle_hors_holdout"],
            "accuracy_oracle_holdout": w["accuracy_oracle_holdout"],
            "mae_ecart_holdout": w["mae_ecart_holdout"],
        }
        for n, k, a, _, w in ridge_grid
    ],
    "holdout": {
        "annee": holdout_year,
        "note_regime_A": note_regime_a,
        "bat_persistance_ecart_oracle": bat_persist_a,
        "ecart": hold_eval["par_bloc_ecart"],
        "mae_ecart": hold_eval["mae_ecart"],
        "mae_ecart_persistance": hold_eval["baseline_persistance_ecart_mae"],
        "ecart_mae_ecart_vs_persistance": round(
            hold_eval["mae_ecart"] - hold_eval["baseline_persistance_ecart_mae"], 3
        ),
        "oracle": {
            **hold_eval["oracle"],
            "ecart_mae_vs_persistance_ecart": round(
                hold_eval["oracle"]["mae_score"]
                - hold_eval["oracle"]["baseline_persistance_ecart"]["mae_score"], 3
            ),
            "ecart_mae_vs_persistance_niveau": round(
                hold_eval["oracle"]["mae_score"] - mae_persist_niv, 3
            ),
            "ecart_acc_vs_gagnant_precedent": round(acc_holdout_a - acc_prec, 3),
            "ecart_acc_vs_classe_majoritaire": round(acc_holdout_a - acc_maj, 3),
            "ecart_acc_vs_persistance_ecart": round(
                acc_holdout_a
                - hold_eval["oracle"]["baseline_persistance_ecart"]["accuracy_argmax"],
                3,
            ),
        },
        "projete": {
            **hold_eval["projete"],
            "ecart_mae_vs_persistance_ecart": round(
                hold_eval["projete"]["mae_score"]
                - hold_eval["projete"]["baseline_persistance_ecart"]["mae_score"], 3
            ),
            "ecart_mae_vs_persistance_niveau": round(
                hold_eval["projete"]["mae_score"] - mae_persist_niv, 3
            ),
            "ecart_acc_vs_gagnant_precedent": round(acc_holdout_b - acc_prec, 3),
            "ecart_acc_vs_classe_majoritaire": round(acc_holdout_b - acc_maj, 3),
        },
        "baseline_persistance_niveau": hold_eval["baseline_persistance_niveau"],
        "accuracy_baseline_gagnant_precedent": acc_prec,
        "accuracy_baseline_classe_majoritaire": acc_maj,
        "classe_majoritaire_test": mode_2022,
        "confusion_oracle": {"labels": labels, "matrix": cm.tolist()},
    },
    "classification_argmax_holdout": {
        "regime": "oracle",
        "accuracy": acc_holdout_a,
        "accuracy_projete": acc_holdout_b,
        "accuracy_baseline_gagnant_precedent": acc_prec,
        "accuracy_baseline_classe_majoritaire": acc_maj,
        "classe_majoritaire_test": str(mode_2022),
        "ecart_vs_gagnant_precedent": round(acc_holdout_a - acc_prec, 3),
        "ecart_vs_classe_majoritaire": round(acc_holdout_a - acc_maj, 3),
        "confusion": {"labels": labels, "matrix": cm.tolist()},
    },
    "importance_variables": imp,
    "poids_socio_eco": socio_weight,
    "projection_scores_moyens_holdout_oracle": dict(
        zip(BLOCS, np.round(scores_oracle.mean(axis=0), 2).tolist())
    ),
    "metriques_retenues": {
        "mae_ecart_hors_holdout": results[best_name]["mae_ecart_walkforward_hors_holdout"],
        "accuracy_oracle_hors_holdout": sel_acc,
        "mae_ecart_holdout": hold_eval["mae_ecart"],
        "mae_score_oracle_holdout": mae_oracle,
        "mae_score_projete_holdout": hold_eval["projete"]["mae_score"],
        "accuracy_oracle_holdout": acc_holdout_a,
        "accuracy_projete_holdout": acc_holdout_b,
        "mae_cv_groupee": mae_cv,
        "accuracy_baseline_gagnant_precedent": acc_prec,
        "accuracy_baseline_classe_majoritaire": acc_maj,
        "ecart_acc_oracle_vs_majoritaire": round(acc_holdout_a - acc_maj, 3),
        "ecart_acc_oracle_vs_gagnant_precedent": round(acc_holdout_a - acc_prec, 3),
        "seuil_cdc_0_5": bool(sel_acc >= 0.5 or acc_holdout_a >= 0.5),
    },
}

with open(f"{ROOT}/data/ml_report.json", "w", encoding="utf-8", newline="\n") as f:
    json.dump(report, f, indent=2, ensure_ascii=False)

print(f"Observations: {len(df)} | Depts: {df['code_dept'].nunique()} | Holdout: {holdout_year}")
print(f"Plis selection: {PLIS_SELECTION} | Modele retenu: {best_name}")
for n, r in results.items():
    print(
        f"  {n:38s} sel_mae_ecart={r['mae_ecart_walkforward_hors_holdout']:.3f} "
        f"sel_acc_oracle={r['accuracy_oracle_hors_holdout']:.3f} "
        f"holdout_A_acc={r['accuracy_oracle_holdout']:.3f} "
        f"holdout_A_mae={r['mae_score_oracle_holdout']:.3f} "
        f"holdout_B_acc={r['accuracy_projete_holdout']:.3f} "
        f"holdout_B_mae={r['mae_score_projete_holdout']:.3f}"
    )
print(
    f"Oracle argmax={acc_holdout_a:.3f} | projete={acc_holdout_b:.3f} | "
    f"gagnant_prec={acc_prec:.3f} | maj={acc_maj:.3f} ({mode_2022})"
)
print(
    f"MAE ecart={hold_eval['mae_ecart']:.3f} vs persist_ecart="
    f"{hold_eval['baseline_persistance_ecart_mae']:.3f} | "
    f"MAE score oracle={mae_oracle:.3f} vs persist_ecart_A={mae_persist_ecart_a:.3f} "
    f"vs persist_niveau={mae_persist_niv:.3f}"
)
print("Poids socio-eco:", socio_weight.get("part_socio_eco"),
      "| electoral:", socio_weight.get("part_electorale"))
print("Top features:", list(imp.items())[:5])
print("Regime A:", note_regime_a)
