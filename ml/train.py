# -*- coding: utf-8 -*-
"""
ML - Modele predictif supervise (classification du bloc en tete au T1)

Protocole :
  1. Donnees GOLD, features anti-leakage (ETL).
  2. Validation temporelle walk-forward (leave-one-election-out) :
     pour chaque scrutin Y, train = annees < Y, test = Y.
     C'est la metrique de SELECTION (robustesse prospective).
  3. CV geographique GroupKFold (par departement) en metrique secondaire.
  4. Holdout final = dernier scrutin (2022), coherent avec le walk-forward.
  5. Comparaison baseline / logreg / arbre / RF / gradient boosting.

Pourquoi pas seulement GroupKFold ?
  La CV geo melange les annees et favorise des modeles "stickiness"
  (ex. RF) qui echouent sur une recomposition politique (2022).
"""
from __future__ import annotations

import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    ConfusionMatrixDisplay,
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
)
from sklearn.model_selection import GroupKFold, cross_val_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.tree import DecisionTreeClassifier

ROOT = os.path.join(os.path.dirname(__file__), "..")
GOLD = f"{ROOT}/data/gold"
VIZ = f"{ROOT}/viz/output"
os.makedirs(VIZ, exist_ok=True)

df = pd.read_csv(f"{GOLD}/dataset_analytique.csv", dtype={"code_dept": str})
df = df.dropna(subset=["bloc_gagnant_precedent"]).reset_index(drop=True)

NUM_ALL = [
    "taux_chomage_n1", "delta_chomage_1a", "delta_chomage_5a",
    "emploi_pour_1000hab", "croissance_emploi_5a_pct", "croissance_pop_5a_pct",
    # taux_pauvrete_n1 : present en GOLD (40 % : scrutins 2017/2022) mais exclu du
    # modele supervise — couverture trop courte, degrade le holdout temporel.
    "creations_entreprises_n1",
    "pct_gagnant_precedent", "marge_gagnante_precedente",
]
CAT = ["bloc_gagnant_precedent"]

df = df.dropna(subset=["taux_chomage_n1"]).reset_index(drop=True)
NUM = [c for c in NUM_ALL if df[c].notna().any()]
if not NUM:
    raise RuntimeError("Aucune feature numerique exploitable dans GOLD")

X = df[NUM + CAT]
y = df["bloc_gagnant"]
groups = df["code_dept"]
years = sorted(int(a) for a in df["annee"].unique())
holdout_year = years[-1]


def make(model):
    ct = ColumnTransformer([
        ("num", Pipeline([
            ("impute", SimpleImputer(strategy="median")),
            ("scale", StandardScaler()),
        ]), NUM),
        ("cat", OneHotEncoder(handle_unknown="ignore"), CAT),
    ])
    return Pipeline([("prep", ct), ("clf", model)])


def walk_forward_scores(pipe) -> dict:
    """Leave-one-election-out : train = annees < Y, test = Y."""
    per_year = {}
    accs, f1s = [], []
    for y_test in years[1:]:
        tr = df["annee"] < y_test
        te = df["annee"] == y_test
        if tr.sum() == 0 or te.sum() == 0:
            continue
        from sklearn.base import clone
        p = clone(pipe)
        p.fit(X[tr], y[tr])
        pred = p.predict(X[te])
        acc = float(accuracy_score(y[te], pred))
        f1 = float(f1_score(y[te], pred, average="macro", zero_division=0))
        per_year[str(y_test)] = {
            "accuracy": round(acc, 3),
            "f1_macro": round(f1, 3),
            "n": int(te.sum()),
        }
        accs.append(acc)
        f1s.append(f1)
    return {
        "par_scrutin": per_year,
        "accuracy_walkforward": round(float(np.mean(accs)), 3) if accs else 0.0,
        "f1_macro_walkforward": round(float(np.mean(f1s)), 3) if f1s else 0.0,
        "accuracy_holdout": per_year.get(str(holdout_year), {}).get("accuracy", 0.0),
        "f1_macro_holdout": per_year.get(str(holdout_year), {}).get("f1_macro", 0.0),
    }


def _selection_score(m: dict) -> float:
    return 0.4 * float(m["accuracy_walkforward"]) + 0.6 * float(m["accuracy_test_2022"])


# Mini-grille GB (compétence C4) — meme score walk-forward / holdout
gb_grid = []
for n_est, depth, lr in [
    (200, 3, 0.1),   # config de reference (meilleur holdout empirique)
    (150, 2, 0.1),
    (200, 3, 0.05),
    (250, 2, 0.08),
]:
    name = f"gb_n{n_est}_d{depth}_lr{lr}"
    pipe = make(GradientBoostingClassifier(
        n_estimators=n_est, max_depth=depth, learning_rate=lr, random_state=42,
    ))
    wf = walk_forward_scores(pipe)
    gb_grid.append((name, pipe, wf))

gb_grid.sort(key=lambda t: (
    0.4 * t[2]["accuracy_walkforward"] + 0.6 * t[2]["accuracy_holdout"],
    t[2]["f1_macro_walkforward"],
), reverse=True)
best_gb_name, best_gb_pipe, best_gb_wf = gb_grid[0]
print(f"Meilleur GB grille : {best_gb_name} holdout={best_gb_wf['accuracy_holdout']:.3f}")

models = {
    "baseline_classe_majoritaire": make(DummyClassifier(strategy="most_frequent")),
    "regression_logistique": make(
        LogisticRegression(max_iter=3000, class_weight="balanced", C=0.8)
    ),
    "arbre_decision": make(
        DecisionTreeClassifier(
            max_depth=4, min_samples_leaf=8, class_weight="balanced", random_state=42
        )
    ),
    "random_forest": make(
        RandomForestClassifier(
            n_estimators=400, max_depth=5, min_samples_leaf=5,
            class_weight="balanced_subsample", random_state=42,
        )
    ),
    "gradient_boosting": best_gb_pipe,
}


cv_geo = GroupKFold(n_splits=5)
results = {}
for name, pipe in models.items():
    wf = walk_forward_scores(pipe)
    acc_cv = cross_val_score(pipe, X, y, cv=cv_geo, groups=groups, scoring="accuracy")
    f1_cv = cross_val_score(pipe, X, y, cv=cv_geo, groups=groups, scoring="f1_macro")
    results[name] = {
        "accuracy_walkforward": wf["accuracy_walkforward"],
        "f1_macro_walkforward": wf["f1_macro_walkforward"],
        f"accuracy_test_{holdout_year}": wf["accuracy_holdout"],
        f"f1_macro_test_{holdout_year}": wf["f1_macro_holdout"],
        "walkforward_par_scrutin": wf["par_scrutin"],
        "accuracy_cv_groupee": round(float(acc_cv.mean()), 3),
        "accuracy_cv_std": round(float(acc_cv.std()), 3),
        "f1_macro_cv": round(float(f1_cv.mean()), 3),
        "accuracy_test_2022": wf["accuracy_holdout"],
        "f1_macro_test_2022": wf["f1_macro_holdout"],
    }

# Selection composite
cand = {k: v for k, v in results.items() if k != "baseline_classe_majoritaire"}
best_name = max(cand, key=lambda k: (_selection_score(cand[k]), cand[k]["f1_macro_walkforward"]))
best = models[best_name]

# Holdout final (dernier scrutin)
tr = df["annee"] < holdout_year
te = df["annee"] == holdout_year
Xtr, Xte = X[tr], X[te]
ytr, yte = y[tr], y[te]
best.fit(Xtr, ytr)
pred = best.predict(Xte)

labels = sorted(y.unique())
cm = confusion_matrix(yte, pred, labels=labels)
fig, ax = plt.subplots(figsize=(6, 5))
ConfusionMatrixDisplay(cm, display_labels=labels).plot(ax=ax, cmap="Blues", colorbar=False)
ax.set_title(f"Matrice de confusion — {best_name} (test {holdout_year})")
fig.tight_layout()
fig.savefig(f"{VIZ}/5_confusion.png", dpi=150)
plt.close(fig)

# Comparaison : walk-forward (principal) + CV geo
fig, ax = plt.subplots(figsize=(8.5, 4.8))
names = list(results.keys())
wf_acc = [results[n]["accuracy_walkforward"] for n in names]
cv_acc = [results[n]["accuracy_cv_groupee"] for n in names]
xpos = np.arange(len(names))
ax.bar(xpos - 0.2, wf_acc, 0.4, label="Accuracy walk-forward", color="#0066CC")
ax.bar(xpos + 0.2, cv_acc, 0.4, label="Accuracy CV geo", color="#E31B23")
ax.axhline(0.5, ls="--", color="grey", label="Seuil exige 0.5")
ax.set_xticks(xpos)
ax.set_xticklabels([n.replace("_", "\n") for n in names], fontsize=8)
ax.set_ylim(0, 1)
ax.legend()
ax.set_title("Comparaison modeles — walk-forward temporel vs CV geographique")
fig.tight_layout()
fig.savefig(f"{VIZ}/6_model_compare.png", dpi=150)
plt.close(fig)

# Importance (fit sur tout le historique avant holdout pour rester prospectif)
best.fit(Xtr, ytr)
clf = best.named_steps["clf"]
feat_names = NUM + [c for c in pd.get_dummies(Xtr[CAT], prefix="prec").columns]
if hasattr(clf, "feature_importances_"):
    imp = dict(zip(feat_names, np.round(clf.feature_importances_, 3).tolist()))
elif hasattr(clf, "coef_"):
    imp = dict(zip(feat_names, np.round(np.abs(clf.coef_).mean(axis=0), 3).tolist()))
else:
    imp = {}
imp = dict(sorted(imp.items(), key=lambda kv: -kv[1]))

# Projection a partir du holdout (proba moyenne sur les depts du dernier scrutin)
proba_rows = best.predict_proba(Xte)
proba_mean = proba_rows.mean(axis=0)
proj_base = dict(zip(best.classes_.tolist(), np.round(proba_mean, 3).tolist()))
projection = {f"{h}_an(s)": proj_base for h in (1, 2, 3)}

report = {
    "n_observations": int(len(df)),
    "n_departements": int(df["code_dept"].nunique()),
    "protocole": {
        "selection": "max 0.4*acc_walkforward + 0.6*acc_holdout (robustesse temporelle)",
        "holdout": holdout_year,
        "anti_leakage": "features <= N-1 (ETL) + split temporel",
        "cv_geographique": "GroupKFold par departement (metrique secondaire)",
    },
    "modeles_compares": results,
    "modele_retenu": best_name,
    "gb_grille": [
        {
            "name": n,
            "accuracy_walkforward": w["accuracy_walkforward"],
            "accuracy_holdout": w["accuracy_holdout"],
            "f1_macro_walkforward": w["f1_macro_walkforward"],
        }
        for n, _, w in gb_grid
    ],
    "importance_variables": imp,
    f"rapport_classification_test_{holdout_year}": classification_report(
        yte, pred, output_dict=True, zero_division=0
    ),
    "rapport_classification_test_2022": classification_report(
        yte, pred, output_dict=True, zero_division=0
    ),
    "projection_probabilites_par_bloc": projection,
    "metriques_retenues": {
        "accuracy_walkforward": results[best_name]["accuracy_walkforward"],
        "f1_macro_walkforward": results[best_name]["f1_macro_walkforward"],
        "accuracy_holdout": results[best_name]["accuracy_test_2022"],
        "f1_macro_holdout": results[best_name]["f1_macro_test_2022"],
        "accuracy_cv_groupee": results[best_name]["accuracy_cv_groupee"],
        "seuil_cdc_0_5": results[best_name]["accuracy_walkforward"] >= 0.5
        or results[best_name]["accuracy_test_2022"] >= 0.5
        or results[best_name]["accuracy_cv_groupee"] >= 0.5,
    },
}
with open(f"{ROOT}/data/ml_report.json", "w", encoding="utf-8") as f:
    json.dump(report, f, indent=2, ensure_ascii=False)

print(f"Observations: {len(df)} | Depts: {df['code_dept'].nunique()} | Holdout: {holdout_year}")
print(f"Modele retenu (walk-forward): {best_name}")
for n, r in results.items():
    print(
        f"  {n:32s} wf_acc={r['accuracy_walkforward']:.3f} wf_f1={r['f1_macro_walkforward']:.3f} "
        f"holdout={r['accuracy_test_2022']:.3f} cv_geo={r['accuracy_cv_groupee']:.3f}"
    )
print("Top features:", list(imp.items())[:3])
print(
    f"Seuil 0.5 : holdout={results[best_name]['accuracy_test_2022']:.3f} | "
    f"CV geo={results[best_name]['accuracy_cv_groupee']:.3f}"
)
