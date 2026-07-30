# -*- coding: utf-8 -*-
"""
Initialise une base PostgreSQL distante (ex. Aiven) puis charge SILVER/GOLD.

Usage (depuis la racine du projet, avec .env Aiven renseigne) :
  cd backend
  python init_remote.py

Ou depuis la racine :
  python -m backend.init_remote   # si package
  python backend/init_remote.py

Etapes :
  1. Connexion via database.get_engine() (DB_* + DB_SSLMODE=require)
  2. Application de db/init.sql (CREATE TABLE IF NOT EXISTS)
  3. Chargement des donnees via load_data.load() (inclut dim_bloc)
"""
import os
import sys

# .env a la racine
ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.dirname(__file__))

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(ROOT, ".env"))
except ImportError:
    pass

from database import get_engine, get_database_url
import load_data


def main():
    # Masquer le mot de passe dans le log
    url = get_database_url()
    safe = url.split("@")[-1] if "@" in url else url
    print(f"Cible : ...@{safe}")
    eng = get_engine()
    with eng.connect() as con:
        ver = con.exec_driver_sql("SELECT version()").scalar()
        print(f"Connecte : {ver.split(',')[0]}")
    load_data.ensure_schema(eng)
    load_data.load()
    with eng.connect() as con:
        n_gold = con.exec_driver_sql(
            "SELECT COUNT(*) FROM gold_dataset_analytique"
        ).scalar()
        n_bloc = con.exec_driver_sql("SELECT COUNT(*) FROM dim_bloc").scalar()
    print(f"OK — gold={n_gold} lignes, dim_bloc={n_bloc} blocs")


if __name__ == "__main__":
    main()
