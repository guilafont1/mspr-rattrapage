# -*- coding: utf-8 -*-
"""
Referentiels partages Bronze / Silver / Gold.
Codes departement metropolitains, libelles, regions (decoupage 2016).
"""
from __future__ import annotations

import json
import os
from functools import lru_cache

METRO_DEPTS = [f"{i:02d}" for i in range(1, 96) if i != 20] + ["2A", "2B"]
BLOCS = ("EXG", "GAU", "CEN", "DRO", "EXD")
ELECTIONS = (2002, 2007, 2012, 2017, 2022)

# Contrats colonnes Bronze (ordre canonique)
BRONZE_SCHEMAS: dict[str, list[str]] = {
    "elections_presidentielles_t1.csv": [
        "annee", "code_dept", "inscrits",
        "pct_EXG", "pct_GAU", "pct_CEN", "pct_DRO", "pct_EXD",
    ],
    "chomage_localise_trim.csv": ["code_dept", "annee", "trimestre", "taux_chomage"],
    "emploi_salarie_trim.csv": ["code_dept", "annee", "trimestre", "emploi_total"],
    "population_dept.csv": ["code_dept", "annee", "population"],
    "pauvrete_dept.csv": ["code_dept", "annee", "taux_pauvrete"],
    "entreprises_dept.csv": ["code_dept", "annee", "creations_entreprises_10k"],
}

# Region administrative (2016) par code departement
REGION_BY_DEPT: dict[str, str] = {
    "01": "Auvergne-Rhone-Alpes", "03": "Auvergne-Rhone-Alpes", "07": "Auvergne-Rhone-Alpes",
    "15": "Auvergne-Rhone-Alpes", "26": "Auvergne-Rhone-Alpes", "38": "Auvergne-Rhone-Alpes",
    "42": "Auvergne-Rhone-Alpes", "43": "Auvergne-Rhone-Alpes", "63": "Auvergne-Rhone-Alpes",
    "69": "Auvergne-Rhone-Alpes", "73": "Auvergne-Rhone-Alpes", "74": "Auvergne-Rhone-Alpes",
    "21": "Bourgogne-Franche-Comte", "25": "Bourgogne-Franche-Comte", "39": "Bourgogne-Franche-Comte",
    "58": "Bourgogne-Franche-Comte", "70": "Bourgogne-Franche-Comte", "71": "Bourgogne-Franche-Comte",
    "89": "Bourgogne-Franche-Comte", "90": "Bourgogne-Franche-Comte",
    "22": "Bretagne", "29": "Bretagne", "35": "Bretagne", "56": "Bretagne",
    "18": "Centre-Val de Loire", "28": "Centre-Val de Loire", "36": "Centre-Val de Loire",
    "37": "Centre-Val de Loire", "41": "Centre-Val de Loire", "45": "Centre-Val de Loire",
    "08": "Grand Est", "10": "Grand Est", "51": "Grand Est", "52": "Grand Est",
    "54": "Grand Est", "55": "Grand Est", "57": "Grand Est", "67": "Grand Est",
    "68": "Grand Est", "88": "Grand Est",
    "02": "Hauts-de-France", "59": "Hauts-de-France", "60": "Hauts-de-France",
    "62": "Hauts-de-France", "80": "Hauts-de-France",
    "75": "Ile-de-France", "77": "Ile-de-France", "78": "Ile-de-France",
    "91": "Ile-de-France", "92": "Ile-de-France", "93": "Ile-de-France",
    "94": "Ile-de-France", "95": "Ile-de-France",
    "14": "Normandie", "27": "Normandie", "50": "Normandie", "61": "Normandie", "76": "Normandie",
    "16": "Nouvelle-Aquitaine", "17": "Nouvelle-Aquitaine", "19": "Nouvelle-Aquitaine",
    "23": "Nouvelle-Aquitaine", "24": "Nouvelle-Aquitaine", "33": "Nouvelle-Aquitaine",
    "40": "Nouvelle-Aquitaine", "47": "Nouvelle-Aquitaine", "64": "Nouvelle-Aquitaine",
    "79": "Nouvelle-Aquitaine", "86": "Nouvelle-Aquitaine", "87": "Nouvelle-Aquitaine",
    "09": "Occitanie", "11": "Occitanie", "12": "Occitanie", "30": "Occitanie",
    "31": "Occitanie", "32": "Occitanie", "34": "Occitanie", "46": "Occitanie",
    "48": "Occitanie", "65": "Occitanie", "66": "Occitanie", "81": "Occitanie", "82": "Occitanie",
    "44": "Pays de la Loire", "49": "Pays de la Loire", "53": "Pays de la Loire",
    "72": "Pays de la Loire", "85": "Pays de la Loire",
    "04": "Provence-Alpes-Cote d'Azur", "05": "Provence-Alpes-Cote d'Azur",
    "06": "Provence-Alpes-Cote d'Azur", "13": "Provence-Alpes-Cote d'Azur",
    "83": "Provence-Alpes-Cote d'Azur", "84": "Provence-Alpes-Cote d'Azur",
    "2A": "Corse", "2B": "Corse",
}


@lru_cache(maxsize=1)
def dept_libelles() -> dict[str, str]:
    """Libelles depuis le geojson Dash, avec repli minimal."""
    root = os.path.join(os.path.dirname(__file__), "..")
    path = os.path.join(root, "frontend", "assets", "departements.geojson")
    out = {d: d for d in METRO_DEPTS}
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as f:
            geo = json.load(f)
        for feat in geo.get("features", []):
            props = feat.get("properties") or {}
            code = str(props.get("code", "")).strip()
            nom = props.get("nom")
            if code in out and nom:
                out[code] = str(nom)
    return out


def dim_departement_frame():
    import pandas as pd
    libs = dept_libelles()
    return pd.DataFrame({
        "code_dept": METRO_DEPTS,
        "libelle": [libs.get(d, d) for d in METRO_DEPTS],
        "region": [REGION_BY_DEPT.get(d) for d in METRO_DEPTS],
    })
