# -*- coding: utf-8 -*-
"""
Suite DQM exécutable — Electio-Analytics (compétence C8).

Outil interne inspiré du pattern « expectations » (contrôles nommés + rapport).
Ce n'est PAS une installation du produit Great Expectations : pas d'import
great_expectations, pas de Data Context GE officiel.

Usage : python dqm/run_checkpoint.py
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone

import pandas as pd

ROOT = os.path.join(os.path.dirname(__file__), "..")
SILVER = os.path.join(ROOT, "data", "silver")
GOLD = os.path.join(ROOT, "data", "gold")
OUT = os.path.join(os.path.dirname(__file__), "uncommitted", "validation_results")
os.makedirs(OUT, exist_ok=True)

METRO = [f"{i:02d}" for i in range(1, 96) if i != 20] + ["2A", "2B"]


def expect(name: str, ok: bool, detail: str) -> dict:
    return {"expectation": name, "success": bool(ok), "detail": detail}


def run_suite() -> dict:
    results = []
    elec = pd.read_csv(f"{SILVER}/elections.csv", dtype={"code_dept": str})
    chom = pd.read_csv(f"{SILVER}/chomage.csv", dtype={"code_dept": str})
    gold = pd.read_csv(f"{GOLD}/dataset_analytique.csv", dtype={"code_dept": str})

    pct = [c for c in elec.columns if c.startswith("pct_")]
    ok = elec[pct].apply(lambda s: s.between(0, 100)).all(axis=1).all()
    results.append(expect("expect_election_pct_between_0_100", ok, f"rows={len(elec)}"))

    ok = elec["code_dept"].isin(METRO).all()
    results.append(expect("expect_election_dept_in_metro", ok, f"nunique={elec['code_dept'].nunique()}"))

    ok = chom["taux_chomage"].between(0, 30).all()
    results.append(expect("expect_chomage_between_0_30", ok, f"rows={len(chom)}"))

    ok = gold.duplicated(["code_dept", "annee"]).sum() == 0
    results.append(expect("expect_gold_unique_dept_annee", ok, f"rows={len(gold)}"))

    ok = gold["taux_chomage_n1"].notna().all()
    results.append(expect(
        "expect_gold_chomage_n1_complete", ok,
        f"completude={gold['taux_chomage_n1'].notna().mean():.1%}",
    ))

    pau_c = float(gold["taux_pauvrete_n1"].notna().mean()) if "taux_pauvrete_n1" in gold.columns else 0.0
    results.append(expect(
        "expect_gold_pauvrete_n1_not_all_null",
        pau_c > 0.0,
        f"completude={pau_c:.1%} (historique Filosofi attendu pour 2017/2022)",
    ))

    ok = all(c in gold.columns for c in (
        "ecart_EXG", "pct_EXG_national", "ecart_EXG_prec", "inscrits",
    ))
    results.append(expect(
        "expect_gold_decomposition_nationale",
        ok,
        "colonnes pct_*_national / ecart_* presentes",
    ))

    if "ecart_EXG" in gold.columns and "inscrits" in gold.columns:
        ok_wm = True
        details = []
        for an, g in gold.groupby("annee"):
            w = g["inscrits"].astype(float)
            sw = float(w.sum()) or 1.0
            for b in ("EXG", "GAU", "CEN", "DRO", "EXD"):
                wm = float((g[f"ecart_{b}"] * w).sum() / sw)
                if abs(wm) > 0.15:
                    ok_wm = False
                    details.append(f"{an}/{b}={wm:.3f}")
        results.append(expect(
            "expect_gold_ecart_pondere_proche_zero",
            ok_wm,
            "ok" if ok_wm else f"hors tol 0,15 : {details[:6]}",
        ))

    if all(f"pct_{b}_national" in gold.columns for b in ("EXG", "GAU", "CEN", "DRO", "EXD")):
        s = gold[["pct_EXG_national", "pct_GAU_national", "pct_CEN_national",
                  "pct_DRO_national", "pct_EXD_national"]].sum(axis=1)
        ok_nat = bool(s.between(95, 105).all())
        results.append(expect(
            "expect_gold_national_somme_100",
            ok_nat,
            f"min={float(s.min()):.2f} max={float(s.max()):.2f}",
        ))

    success = all(r["success"] for r in results)
    report = {
        "suite": "electio_silver_gold",
        "framework": "dqm_interne_pattern_expectations",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "success": success,
        "results": results,
    }
    path_json = os.path.join(OUT, "electio_checkpoint.json")
    with open(path_json, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    rows_html = "".join(
        f"<tr><td>{r['expectation']}</td><td>{'OK' if r['success'] else 'KO'}</td>"
        f"<td>{r['detail']}</td></tr>"
        for r in results
    )
    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Electio DQM Checkpoint</title>
<style>body{{font-family:Segoe UI,sans-serif;margin:2rem}}
table{{border-collapse:collapse;width:100%}}td,th{{border:1px solid #ccc;padding:.5rem}}
.ok{{color:#0a7}} .ko{{color:#c00}}</style></head>
<body>
<h1>Suite DQM electio_silver_gold</h1>
<p>Outil interne (pattern expectations) — pas Great Expectations.</p>
<p>Success global : <strong class="{'ok' if success else 'ko'}">{success}</strong></p>
<table><thead><tr><th>Contrôle</th><th>Status</th><th>Detail</th></tr></thead>
<tbody>{rows_html}</tbody></table>
<p>Généré : {report['generated_at']}</p>
</body></html>"""
    path_html = os.path.join(OUT, "electio_checkpoint.html")
    with open(path_html, "w", encoding="utf-8") as f:
        f.write(html)

    print(json.dumps({"success": success, "framework": report["framework"]}, indent=2))
    for r in results:
        print(f"[{'OK' if r['success'] else 'KO'}] {r['expectation']}: {r['detail']}")
    print(f"JSON : {path_json}")
    print(f"HTML : {path_html}")
    return report


if __name__ == "__main__":
    rep = run_suite()
    sys.exit(0 if rep["success"] else 1)
