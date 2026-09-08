# -*- coding: utf-8 -*-
"""
Tests automatises du pipeline (qualite des donnees + anti data-leakage + couches).
"""
import json
import os
import sqlite3
import pandas as pd
import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..")
BRONZE = f"{ROOT}/data/bronze"
SILVER = f"{ROOT}/data/silver"
GOLD = f"{ROOT}/data/gold"


@pytest.fixture(scope="module")
def gold():
    return pd.read_csv(f"{GOLD}/dataset_analytique.csv", dtype={"code_dept": str})


def test_bronze_manifest_et_schemas():
    path = f"{BRONZE}/bronze_manifest.json"
    assert os.path.exists(path), "bronze_manifest.json manquant"
    meta = json.load(open(path, encoding="utf-8"))
    assert meta.get("layer") == "BRONZE"
    for name in meta["schemas"]:
        assert os.path.exists(f"{BRONZE}/{name}"), f"Bronze manquant : {name}"


def test_silver_enrichi():
    required = [
        "elections.csv", "chomage.csv", "emploi.csv", "population.csv",
        "pauvrete.csv", "entreprises.csv",
        "chomage_annuel.csv", "emploi_annuel.csv", "socioeco_annuel.csv",
        "silver_manifest.json",
    ]
    for name in required:
        assert os.path.exists(f"{SILVER}/{name}"), f"Silver manquant : {name}"
    elec = pd.read_csv(f"{SILVER}/elections.csv", dtype={"code_dept": str})
    for col in ("bloc_gagnant", "somme_pct", "marge_gagnante", "concentration_top2"):
        assert col in elec.columns, f"Colonne Silver elections absente : {col}"
    socio = pd.read_csv(f"{SILVER}/socioeco_annuel.csv", dtype={"code_dept": str})
    assert "emploi_pour_1000hab" in socio.columns
    assert "completude_score" in socio.columns


def test_gold_non_vide(gold):
    assert len(gold) > 0, "La couche GOLD est vide"


def test_pas_de_doublon_cle(gold):
    dup = gold.duplicated(subset=["code_dept", "annee"]).sum()
    assert dup == 0, f"{dup} doublons (code_dept, annee) dans GOLD"


def test_chomage_dans_bornes(gold):
    s = gold["taux_chomage_n1"].dropna()
    assert s.between(0, 30).all(), "Taux de chomage hors [0;30]"


def test_cible_valide(gold):
    blocs = {"EXG", "GAU", "CEN", "DRO", "EXD"}
    assert set(gold["bloc_gagnant"].unique()).issubset(blocs), "Bloc gagnant inconnu"


def test_features_anterieures(gold):
    ech = gold.dropna(subset=["taux_chomage_n1"]).sort_values(["code_dept", "annee"])
    assert ech.groupby("code_dept")["taux_chomage_n1"].nunique().mean() > 1


def test_gold_features_enrichies(gold):
    for col in ("delta_chomage_1a", "croissance_pop_5a_pct",
                "pct_gagnant_precedent", "marge_gagnante_precedente",
                "pct_EXG", "pct_EXD", "pct_EXG_prec", "delta_recent_CEN",
                "volatility_DRO"):
        assert col in gold.columns, f"Feature Gold absente : {col}"


def test_gold_scores_somment_100(gold):
    pct = [f"pct_{b}" for b in ("EXG", "GAU", "CEN", "DRO", "EXD")]
    s = gold[pct].sum(axis=1)
    assert s.between(95, 105).all(), "Somme des pct_* hors [95;105]"


def test_gold_prec_anti_leakage(gold):
    """pct_*_prec ne doit jamais egaler le score courant (sauf coincidence rare)."""
    g = gold.dropna(subset=["pct_EXG_prec"]).copy()
    g = g.sort_values(["code_dept", "annee"])
    shifted = g.groupby("code_dept")["pct_EXG"].shift(1)
    both = g["pct_EXG_prec"].notna() & shifted.notna()
    assert (g.loc[both, "pct_EXG_prec"] - shifted[both]).abs().max() < 0.06


def test_gold_decomposition_nationale(gold):
    for col in ("inscrits", "pct_EXG_national", "ecart_DRO", "ecart_EXD_prec",
                "delta_recent_ecart_CEN", "trend_ecart_GAU"):
        assert col in gold.columns, f"Colonne GOLD absente : {col}"
    nat = [f"pct_{b}_national" for b in ("EXG", "GAU", "CEN", "DRO", "EXD")]
    assert gold[nat].sum(axis=1).between(95, 105).all()
    # Moyenne ponderee des ecarts ~ 0
    for an, g in gold.groupby("annee"):
        w = g["inscrits"].astype(float)
        sw = float(w.sum())
        for b in ("EXG", "GAU", "CEN", "DRO", "EXD"):
            wm = float((g[f"ecart_{b}"] * w).sum() / sw)
            assert abs(wm) <= 0.15, f"{an}/{b} moyenne ponderee = {wm}"


def test_gold_ecart_prec_anti_leakage(gold):
    g = gold.dropna(subset=["ecart_EXG_prec"]).sort_values(["code_dept", "annee"])
    shifted = g.groupby("code_dept")["ecart_EXG"].shift(1)
    both = g["ecart_EXG_prec"].notna() & shifted.notna()
    assert (g.loc[both, "ecart_EXG_prec"] - shifted[both]).abs().max() < 0.0006


def test_gold_kpi_artefacts():
    for name in ("kpi_evolution_blocs.csv", "kpi_completude_features.csv",
                 "kpi_chomage_vs_bloc.csv", "gold_manifest.json"):
        assert os.path.exists(f"{GOLD}/{name}"), f"Artefact Gold manquant : {name}"


def test_base_sqlite_coherente():
    con = sqlite3.connect(f"{GOLD}/electio_poc.db")
    tables = pd.read_sql(
        "SELECT name FROM sqlite_master WHERE type='table'", con)["name"].tolist()
    dim = pd.read_sql("SELECT * FROM dim_departement", con)
    con.close()
    for t in ["gold_dataset_analytique", "fait_resultat_election",
              "fait_socioeco_annuel", "dim_departement", "dim_annee", "dim_bloc",
              "kpi_evolution_blocs", "kpi_completude_features", "kpi_chomage_vs_bloc"]:
        assert t in tables, f"Table manquante : {t}"
    assert dim["libelle"].notna().all(), "dim_departement.libelle vide"
    assert dim["region"].notna().all(), "dim_departement.region vide"


def test_quality_report_existe():
    path = f"{ROOT}/data/quality_report.txt"
    assert os.path.exists(path), "quality_report.txt manquant"
    txt = open(path, encoding="utf-8").read()
    assert "JOURNAL QUALITE" in txt
    assert "SILVER" in txt and "GOLD" in txt
