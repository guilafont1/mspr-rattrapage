# -*- coding: utf-8 -*-
"""
Data visualisation - analyse exploratoire + restitution (multi-departements).
Genere les figures du dossier dans viz/output/.
"""
import os
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns

ROOT = os.path.join(os.path.dirname(__file__), "..")
OUT = os.path.join(os.path.dirname(__file__), "output")
os.makedirs(OUT, exist_ok=True)
sns.set_theme(style="whitegrid")

elec = pd.read_csv(f"{ROOT}/data/silver/elections.csv", dtype={"code_dept": str})
gold = pd.read_csv(f"{ROOT}/data/gold/dataset_analytique.csv", dtype={"code_dept": str})
with open(f"{ROOT}/data/ml_report.json") as f:
    ml = json.load(f)

BLOCS = ["EXG", "GAU", "CEN", "DRO", "EXD"]
COLORS = {"EXG": "#6B0F1A", "GAU": "#C8102E", "CEN": "#C4922A",
          "DRO": "#2A5F9E", "EXD": "#0B1F33"}

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "axes.facecolor": "#F7F9FB",
    "figure.facecolor": "white",
    "axes.edgecolor": "#D5E0EA",
    "axes.labelcolor": "#5A6B7D",
    "xtick.color": "#5A6B7D",
    "ytick.color": "#5A6B7D",
    "grid.color": "#0B1F3314",
    "axes.titlesize": 13,
    "axes.titleweight": "bold",
})
sns.set_theme(style="whitegrid")

# 1 - Evolution nationale des blocs (moyenne des departements)
nat = elec.groupby("annee")[[f"pct_{b}" for b in BLOCS]].mean()
fig, ax = plt.subplots(figsize=(9, 5))
for b in BLOCS:
    ax.plot(nat.index, nat[f"pct_{b}"], marker="o", label=b, color=COLORS[b])
ax.set_title("Presidentielles T1 - score moyen par bloc (96 depts)")
ax.set_xlabel("Election"); ax.set_ylabel("% moyen exprimes"); ax.legend()
fig.tight_layout(); fig.savefig(f"{OUT}/1_evolution_blocs.png", dpi=150); plt.close(fig)

# 2 - Distribution du bloc gagnant par election (barres empilees)
piv = elec.groupby(["annee", "bloc_gagnant"]).size().unstack(fill_value=0)
piv = piv.reindex(columns=[b for b in BLOCS if b in piv.columns])
fig, ax = plt.subplots(figsize=(9, 4.8))
bottom = np.zeros(len(piv))
for b in piv.columns:
    ax.bar(piv.index.astype(str), piv[b], bottom=bottom, label=b, color=COLORS[b])
    bottom += piv[b].values
ax.set_title("Nombre de departements ou chaque bloc arrive en tete")
ax.set_ylabel("Nb departements"); ax.legend(ncol=5)
fig.tight_layout(); fig.savefig(f"{OUT}/2_gagnant_par_election.png", dpi=150); plt.close(fig)

# 3 - Heatmap de correlation indicateurs <-> cible
g = gold.dropna().copy()
g["cible"] = g["bloc_gagnant"].astype("category").cat.codes
NUM = ["taux_chomage_n1", "delta_chomage_1a", "delta_chomage_5a",
       "emploi_pour_1000hab", "croissance_emploi_5a_pct", "croissance_pop_5a_pct",
       "taux_pauvrete_n1", "creations_entreprises_n1",
       "pct_gagnant_precedent", "marge_gagnante_precedente"]
fig, ax = plt.subplots(figsize=(8, 6.5))
sns.heatmap(g[NUM + ["cible"]].corr(), annot=True, fmt=".2f", cmap="RdBu_r",
            center=0, ax=ax)
ax.set_title("Correlations indicateurs <-> resultat")
fig.tight_layout(); fig.savefig(f"{OUT}/3_correlations.png", dpi=150); plt.close(fig)

# 4 - Chomage N-1 selon le bloc gagnant (boxplot -> lien socio-eco/vote)
fig, ax = plt.subplots(figsize=(8, 5))
order = [b for b in BLOCS if b in g["bloc_gagnant"].unique()]
sns.boxplot(data=g, x="bloc_gagnant", y="taux_chomage_n1", order=order,
            palette={b: COLORS[b] for b in order}, ax=ax)
ax.set_title("Taux de chomage (N-1) selon le bloc arrive en tete")
ax.set_xlabel("Bloc gagnant"); ax.set_ylabel("Taux de chomage N-1 (%)")
fig.tight_layout(); fig.savefig(f"{OUT}/4_chomage_par_bloc.png", dpi=150); plt.close(fig)

# 7 - Importance des variables du modele retenu
imp = ml["importance_variables"]
fig, ax = plt.subplots(figsize=(8, 4.8))
items = list(imp.items())[:8][::-1]
ax.barh([k for k, _ in items], [v for _, v in items], color="#0B1F33")
ax.set_title(f"Importance des variables -- {ml['modele_retenu']}")
fig.tight_layout(); fig.savefig(f"{OUT}/7_importance.png", dpi=150); plt.close(fig)

# 8 - Projection probabiliste (modele retenu)
proj = ml["projection_probabilites_par_bloc"]["1_an(s)"]
proj = dict(sorted(proj.items(), key=lambda kv: -kv[1]))
fig, ax = plt.subplots(figsize=(7, 4.5))
ax.bar(proj.keys(), proj.values(), color=[COLORS.get(b, "#999") for b in proj])
ax.set_title("Probabilite de bloc en tete -- projection prospective")
ax.set_ylabel("Probabilite"); ax.set_ylim(0, 1)
fig.tight_layout(); fig.savefig(f"{OUT}/8_projection.png", dpi=150); plt.close(fig)

print("Figures ecrites :", sorted(os.listdir(OUT)))
