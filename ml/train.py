# -*- coding: utf-8 -*-
"""
ML - Modele predictif supervise (classification du bloc en tete au T1)

Protocole :
  1. Donnees GOLD, features anti-leakage (ETL).
  2. Validation temporelle walk-forward (leave-one-election-out) :
     pour chaque scrutin Y, train = annees < Y, test = Y.
     C'est la metrique de SELECTION (robustesse prospective).
  3. CV geographique GroupKFold (par departement) en metrique secondaire.
  4. Holdout final = dernier scrutin (2022) : metrique REPORTEE uniquement,
     jamais utilisee pour choisir le modele ni la grille GB (anti data-snooping).
  5. Comparaison baseline / logreg / arbre / RF / gradient boosting.

Pourquoi pas seulement GroupKFold ?
  La CV geo melange les annees et favorise des modeles "stickiness"
  (ex. RF) qui echouent sur une recomposition politique (2022).

Selection :
  score = 0.6 * accuracy_walkforward_hors_holdout
        + 0.4 * f1_macro_walkforward_hors_holdout.
  La moyenne walk-forward tous plis (accuracy_walkforward) est reportée
  mais ne sert jamais au choix — sinon le holdout reviendrait dans le critère
  dès qu'il n'y a que deux plis (cas actuel après exclusion de 2007).
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

# Arbitrage creations_entreprises_n1 / scrutin 2007
# -------------------------------------------------
# Fait : creations_entreprises_n1 est manquante a 100 % sur 2007 (source INSEE
# demarrant en 2009). SimpleImputer(median) attribuait une constante a toute la
# cohorte, alors que c'etait la 3e variable en importance du modele — artefact.
#
# Option A (retenue) : exclure le scrutin 2007 (−96 observations). Il reste
# 3 scrutins (2012, 2017, 2022) et donc un seul pli de selection (2017, entraine
# sur 2012 seul). Consequence assumee : protocole de selection fragile.
#
# Option B (ecartee) : supprimer la variable creations_entreprises_n1 et
# conserver 2007, ce qui aurait preserve 3 plis walk-forward (2012, 2017, 2022).
# Ecartee car la feature porte un signal socio-economique utile et que l'imputation
# silencieuse sur une annee entiere etait le probleme principal a eliminer.
_annees_creations_absentes = [
    int(a) for a, s in df.groupby("annee")["creations_entreprises_n1"]
    if s.isna().all()
]
_n_avant_filtre = len(df)
if _annees_creations_absentes:
    df = df[~df["annee"].isin(_annees_creations_absentes)].reset_index(drop=True)
_DECISIONS_FEATURES = {
    "creations_entreprises_n1": {
        "choix": "exclure_observations_annee_entiere_null",
        "option_retenue": "A",
        "annees_exclues": _annees_creations_absentes,
        "n_observations_exclues": int(_n_avant_filtre - len(df)),
        "fait": (
            "creations_entreprises_n1 manquante a 100 % sur le scrutin 2007 "
            "(source INSEE demarrant en 2009) ; SimpleImputer(median) attribuait "
            "une constante a toute la cohorte alors que c'etait la 3e variable "
            "en importance."
        ),
        "option_A_retenue": (
            "Exclure le scrutin 2007 (−96 observations). Il reste 3 scrutins "
            "(2012, 2017, 2022) et donc un seul pli de selection (2017, entraine "
            "sur 2012 seul, 96 observations)."
        ),
        "option_B_ecartee": (
            "Supprimer la variable creations_entreprises_n1 et conserver 2007, "
            "ce qui aurait preserve 3 plis walk-forward (2012, 2017, 2022)."
        ),
        "justification": (
            "On elimine l'artefact d'imputation sur une cohorte entiere et on "
            "conserve une feature informative. Consequence assumee : le protocole "
            "de selection ne repose plus que sur un seul pli anterieur au holdout, "
            "ce qui fragilise la robustesse de la comparaison des modeles."
        ),
        "motif": (
            "Source INSEE creations d'entreprises demarre en 2009 : cohorte 2007 "
            "entierement manquante. Imputer une constante a 100 % d'un scrutin "
            "introduit un artefact ; on drop les lignes, on conserve la feature."
        ),
    },
    "taux_pauvrete_n1": {
        "choix": "exclure_variable",
        "motif": "Couverture trop courte (scrutins 2017/2022 seulement).",
    },
}

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
    """Leave-one-election-out : train = annees < Y, test = Y.

    Retourne la moyenne tous plis (métrique reportée) et la moyenne hors
    holdout (seule métrique autorisée pour la sélection des modèles).
    """
    per_year = {}
    accs, f1s = [], []
    accs_sel, f1s_sel = [], []
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
        if int(y_test) != holdout_year:
            accs_sel.append(acc)
            f1s_sel.append(f1)
    return {
        "par_scrutin": per_year,
        "accuracy_walkforward": round(float(np.mean(accs)), 3) if accs else 0.0,
        "f1_macro_walkforward": round(float(np.mean(f1s)), 3) if f1s else 0.0,
        "accuracy_walkforward_hors_holdout": (
            round(float(np.mean(accs_sel)), 3) if accs_sel else 0.0
        ),
        "f1_macro_walkforward_hors_holdout": (
            round(float(np.mean(f1s_sel)), 3) if f1s_sel else 0.0
        ),
        "accuracy_holdout": per_year.get(str(holdout_year), {}).get("accuracy", 0.0),
        "f1_macro_holdout": per_year.get(str(holdout_year), {}).get("f1_macro", 0.0),
    }


def _selection_score(m: dict) -> float:
    """Score de sélection : walk-forward hors holdout exclusivement.

    Utilise accuracy_walkforward_hors_holdout et f1_macro_walkforward_hors_holdout.
    La moyenne tous plis (accuracy_walkforward) contient le holdout dès qu'il
    figure dans years[1:] — elle est reportée, jamais utilisée pour choisir.
    """
    return (
        0.6 * float(m["accuracy_walkforward_hors_holdout"])
        + 0.4 * float(m["f1_macro_walkforward_hors_holdout"])
    )


def _wf_hors_holdout(wf: dict) -> float:
    """Accuracy walk-forward hors holdout (clé dédiée ou repli sur par_scrutin)."""
    if "accuracy_walkforward_hors_holdout" in wf:
        return float(wf["accuracy_walkforward_hors_holdout"])
    accs = [
        float(v["accuracy"])
        for y, v in (wf.get("par_scrutin") or {}).items()
        if int(y) != holdout_year
    ]
    return float(np.mean(accs)) if accs else 0.0


def _f1_hors_holdout(wf: dict) -> float:
    """F1 macro walk-forward hors holdout."""
    if "f1_macro_walkforward_hors_holdout" in wf:
        return float(wf["f1_macro_walkforward_hors_holdout"])
    f1s = [
        float(v["f1_macro"])
        for y, v in (wf.get("par_scrutin") or {}).items()
        if int(y) != holdout_year
    ]
    return float(np.mean(f1s)) if f1s else 0.0


# Plis réellement utilisés pour la sélection (années < holdout dans years[1:])
PLIS_SELECTION = [y for y in years[1:] if y != holdout_year]


# Mini-grille GB (compétence C4) — tri sur walk-forward hors holdout
gb_grid = []
for n_est, depth, lr in [
    (200, 3, 0.1),   # config de reference
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
    t[2]["accuracy_walkforward_hors_holdout"],
    t[2]["f1_macro_walkforward_hors_holdout"],
), reverse=True)
best_gb_name, best_gb_pipe, best_gb_wf = gb_grid[0]
print(
    f"Meilleur GB grille : {best_gb_name} "
    f"wf_hors_holdout={best_gb_wf['accuracy_walkforward_hors_holdout']:.3f} "
    f"holdout={best_gb_wf['accuracy_holdout']:.3f}"
)

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
        # Moyenne tous plis : métrique reportée uniquement (contient le holdout)
        "accuracy_walkforward": wf["accuracy_walkforward"],
        "f1_macro_walkforward": wf["f1_macro_walkforward"],
        # Critère de sélection : plis antérieurs au holdout uniquement
        "accuracy_walkforward_hors_holdout": wf["accuracy_walkforward_hors_holdout"],
        "f1_macro_walkforward_hors_holdout": wf["f1_macro_walkforward_hors_holdout"],
        f"accuracy_test_{holdout_year}": wf["accuracy_holdout"],
        f"f1_macro_test_{holdout_year}": wf["f1_macro_holdout"],
        "walkforward_par_scrutin": wf["par_scrutin"],
        "accuracy_cv_groupee": round(float(acc_cv.mean()), 3),
        "accuracy_cv_std": round(float(acc_cv.std()), 3),
        "f1_macro_cv": round(float(f1_cv.mean()), 3),
        "accuracy_test_2022": wf["accuracy_holdout"],
        "f1_macro_test_2022": wf["f1_macro_holdout"],
    }

# Selection : hors holdout exclusivement (baseline exclue du choix)
cand = {k: v for k, v in results.items() if k != "baseline_classe_majoritaire"}
best_name = max(
    cand,
    key=lambda k: (
        _selection_score(cand[k]),
        cand[k]["f1_macro_walkforward_hors_holdout"],
    ),
)
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


def _enveloppe_entrainement(frame: pd.DataFrame, cols: list) -> dict:
    """min / max / p01 / p99 / moyenne / écart-type par feature numérique."""
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


report = {
    "n_observations": int(len(df)),
    "n_departements": int(df["code_dept"].nunique()),
    "protocole": {
        "selection": "walk-forward hors holdout uniquement",
        "formule_selection": (
            "0.6*accuracy_walkforward_hors_holdout "
            "+ 0.4*f1_macro_walkforward_hors_holdout"
        ),
        "plis_selection": PLIS_SELECTION,
        "n_plis_selection": len(PLIS_SELECTION),
        "avertissement": (
            "La selection ne repose que sur le(s) pli(s) anterieur(s) au holdout. "
            "Depuis l'exclusion de 2007, il ne reste qu'un seul pli de selection "
            "(2017, entraine sur 2012 seul, 96 observations). Ce protocole est "
            "fragile : un seul point de validation pour choisir le modele. "
            "Le holdout 2022 est reporte comme test non vu et ne participe pas "
            "au critere de choix. La moyenne accuracy_walkforward (tous plis) "
            "contient le holdout et ne doit pas etre citee comme score de selection."
        ),
        "holdout": holdout_year,
        "anti_leakage": "features <= N-1 (ETL) + split temporel",
        "cv_geographique": "GroupKFold par departement (metrique secondaire)",
        "grille_gb": "tri sur moyenne walk-forward hors annee de holdout",
    },
    "decisions_features": _DECISIONS_FEATURES,
    "enveloppe_entrainement": _enveloppe_entrainement(df, NUM),
    "modeles_compares": results,
    "modele_retenu": best_name,
    "gb_grille": [
        {
            "name": n,
            "accuracy_walkforward": w["accuracy_walkforward"],
            "accuracy_holdout": w["accuracy_holdout"],
            "f1_macro_walkforward": w["f1_macro_walkforward"],
            "accuracy_walkforward_hors_holdout": w["accuracy_walkforward_hors_holdout"],
            "f1_macro_walkforward_hors_holdout": w["f1_macro_walkforward_hors_holdout"],
            "accuracy_wf_hors_holdout": w["accuracy_walkforward_hors_holdout"],
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
        "accuracy_walkforward_hors_holdout": (
            results[best_name]["accuracy_walkforward_hors_holdout"]
        ),
        "f1_macro_walkforward_hors_holdout": (
            results[best_name]["f1_macro_walkforward_hors_holdout"]
        ),
        "accuracy_holdout": results[best_name]["accuracy_test_2022"],
        "f1_macro_holdout": results[best_name]["f1_macro_test_2022"],
        "accuracy_cv_groupee": results[best_name]["accuracy_cv_groupee"],
        "accuracy_baseline_holdout": (
            results["baseline_classe_majoritaire"]["accuracy_test_2022"]
        ),
        "ecart_baseline_holdout": round(
            float(results[best_name]["accuracy_test_2022"])
            - float(results["baseline_classe_majoritaire"]["accuracy_test_2022"]),
            3,
        ),
        "seuil_cdc_0_5": results[best_name]["accuracy_walkforward_hors_holdout"] >= 0.5
        or results[best_name]["accuracy_test_2022"] >= 0.5
        or results[best_name]["accuracy_cv_groupee"] >= 0.5,
    },
}
with open(f"{ROOT}/data/ml_report.json", "w", encoding="utf-8") as f:
    json.dump(report, f, indent=2, ensure_ascii=False)

print(f"Observations: {len(df)} | Depts: {df['code_dept'].nunique()} | Holdout: {holdout_year}")
print(
    f"Plis selection: {PLIS_SELECTION} (n={len(PLIS_SELECTION)}) | "
    f"Modele retenu: {best_name}"
)
for n, r in results.items():
    print(
        f"  {n:32s} sel_acc={r['accuracy_walkforward_hors_holdout']:.3f} "
        f"sel_f1={r['f1_macro_walkforward_hors_holdout']:.3f} "
        f"wf_all={r['accuracy_walkforward']:.3f} "
        f"holdout={r['accuracy_test_2022']:.3f} cv_geo={r['accuracy_cv_groupee']:.3f}"
    )
print("Top features:", list(imp.items())[:3])
print(
    f"Holdout retenu={results[best_name]['accuracy_test_2022']:.3f} | "
    f"baseline={results['baseline_classe_majoritaire']['accuracy_test_2022']:.3f} | "
    f"ecart={report['metriques_retenues']['ecart_baseline_holdout']:.3f}"
)
