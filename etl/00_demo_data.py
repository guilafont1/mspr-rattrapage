# -*- coding: utf-8 -*-
"""
[DEMO UNIQUEMENT] Genere une couche BRONZE simulee (meme contrat que le reel).

Perimetre : 96 departements metropolitains x 5 scrutins (2002-2022).
Ecrit aussi bronze_manifest.json pour tracer le contrat de couche.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from referentiels import BLOCS, BRONZE_SCHEMAS, ELECTIONS, METRO_DEPTS

rng = np.random.default_rng(2025)
BRONZE = os.path.join(os.path.dirname(__file__), "..", "data", "bronze")
os.makedirs(BRONZE, exist_ok=True)

DEPTS = list(METRO_DEPTS)
tension = {d: rng.uniform(0, 1) for d in DEPTS}
vitalite = {d: rng.uniform(0, 1) for d in DEPTS}
pop_base = {d: rng.uniform(150_000, 1_400_000) for d in DEPTS}

written: dict[str, int] = {}


def _save(name: str, df: pd.DataFrame) -> None:
    cols = BRONZE_SCHEMAS[name]
    out = df.reindex(columns=cols)
    out.to_csv(os.path.join(BRONZE, name), index=False)
    written[name] = len(out)
    print(f"[BRONZE demo] {name}: {len(out)} lignes")


# --- Presidentielles T1 (wide, par bloc) ---
rows = []
for i, an in enumerate(ELECTIONS):
    drift = {"EXG": -0.2 * i, "GAU": -2.0 * i, "CEN": 1.2 * i,
             "DRO": -1.0 * i, "EXD": 2.2 * i}
    for d in DEPTS:
        t, v = tension[d], vitalite[d]
        base = {"EXG": 6 + 4 * t, "GAU": 24 - 4 * v + 3 * t,
                "CEN": 20 + 10 * v - 4 * t, "DRO": 26 + 4 * v - 2 * t,
                "EXD": 12 + 12 * t - 4 * v}
        parts = np.array([max(base[b] + drift[b] + rng.normal(0, 2), 0.5) for b in BLOCS])
        parts = parts / parts.sum() * 100
        row = {"annee": an, "code_dept": d,
               "inscrits": int(pop_base[d] * 0.72 * (1 + 0.02 * i))}
        for b, p in zip(BLOCS, parts):
            row[f"pct_{b}"] = round(float(p), 2)
        rows.append(row)
_save("elections_presidentielles_t1.csv", pd.DataFrame(rows))

# --- Chomage localise trimestriel ---
rows = []
for d in DEPTS:
    for an in range(2000, 2026):
        for tr in range(1, 5):
            val = (6.5 + 5 * tension[d] - 1.5 * vitalite[d] - 0.05 * (an - 2000)
                   + 1.0 * np.sin((an - 2000) / 3) + rng.normal(0, 0.2))
            rows.append({"code_dept": d, "annee": an, "trimestre": tr,
                         "taux_chomage": round(max(val, 3.0), 2)})
_save("chomage_localise_trim.csv", pd.DataFrame(rows))

# --- Emploi salarie trimestriel ---
rows = []
for d in DEPTS:
    for an in range(2000, 2026):
        for tr in range(1, 5):
            emploi = (pop_base[d] * (0.30 + 0.15 * vitalite[d])
                      * (1 + 0.008 * (an - 2000)) + rng.normal(0, 2000))
            rows.append({"code_dept": d, "annee": an, "trimestre": tr,
                         "emploi_total": int(max(emploi, 1000))})
_save("emploi_salarie_trim.csv", pd.DataFrame(rows))

# --- Population annuelle ---
rows = []
for d in DEPTS:
    for an in range(2000, 2026):
        rows.append({"code_dept": d, "annee": an,
                     "population": int(pop_base[d] * (1 + 0.006 * (an - 2000))
                                       + rng.normal(0, 2000))})
_save("population_dept.csv", pd.DataFrame(rows))

# --- Pauvrete annuelle (serie longue demo pour tester le Gold) ---
rows = []
for d in DEPTS:
    for an in range(2004, 2025):
        val = 10 + 9 * tension[d] - 3 * vitalite[d] + rng.normal(0, 0.6)
        rows.append({"code_dept": d, "annee": an, "taux_pauvrete": round(max(val, 4.0), 2)})
_save("pauvrete_dept.csv", pd.DataFrame(rows))

# --- Creations d'entreprises pour 10k hab ---
rows = []
for d in DEPTS:
    for an in range(2009, 2025):
        val = 80 + 90 * vitalite[d] - 20 * tension[d] + rng.normal(0, 6)
        rows.append({"code_dept": d, "annee": an,
                     "creations_entreprises_10k": round(max(val, 10), 1)})
_save("entreprises_dept.csv", pd.DataFrame(rows))

manifest = {
    "layer": "BRONZE",
    "mode": "demo",
    "role": "Contrat normalise (simule) — RAW reel absente en mode demo",
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "schemas": BRONZE_SCHEMAS,
    "tables": {
        name: {"rows": n, "columns": BRONZE_SCHEMAS[name]}
        for name, n in written.items()
    },
}
with open(os.path.join(BRONZE, "bronze_manifest.json"), "w", encoding="utf-8") as f:
    json.dump(manifest, f, indent=2, ensure_ascii=False)

print("Couche BRONZE (demo) generee + bronze_manifest.json")
