# -*- coding: utf-8 -*-
"""
Orchestrateur du pipeline POC Electio-Analytics.
Enchaine les etapes dans l'ordre et s'arrete a la premiere erreur.
Usage :
  python run_pipeline.py            # mode demo (donnees simulees)
  python run_pipeline.py --real     # telecharge les vraies donnees d'abord

Simule le role d'un ordonnanceur (Airflow/cron) : chaque etape est idempotente
et journalisee. En production, remplacer par un DAG Airflow (1 tache/etape).
"""
import subprocess
import sys
import os

HERE = os.path.dirname(__file__)
REAL = "--real" in sys.argv

STEPS = []
if REAL:
    STEPS.append(("Telechargement (donnees officielles)", "etl/01_download.py"))
else:
    STEPS.append(("Generation donnees demo", "etl/00_demo_data.py"))
STEPS += [
    ("Transformation BRONZE->SILVER->GOLD", "etl/02_transform.py"),
    ("Entrainement & evaluation ML", "ml/train.py"),
    ("Generation des visualisations", "viz/figures.py"),
]
# Sync datalake optionnel (MinIO) si le profil est disponible — non bloquant
if "--datalake" in sys.argv or os.environ.get("SYNC_DATALAKE") == "1":
    STEPS.append(("Sync datalake MinIO (bronze/silver/gold)", "etl/03_sync_datalake.py"))


def run(label, script):
    print(f"\n{'='*60}\n>> {label}\n{'='*60}")
    r = subprocess.run([sys.executable, os.path.join(HERE, script)])
    if r.returncode != 0:
        print(f"ECHEC a l'etape : {label}")
        sys.exit(r.returncode)


if __name__ == "__main__":
    for label, script in STEPS:
        run(label, script)
    print("\nPipeline termine avec succes.")
    print("Lancer les tests : python -m pytest tests/ -v")
    print("Datalake : docker compose --profile datalake up -d minio"
          " && python etl/03_sync_datalake.py")
    print("Argumentaire grille : docs/mspr/07_soutenance/ARGUMENTAIRE_NIVEAU3.md")
