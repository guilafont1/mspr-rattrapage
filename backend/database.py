# -*- coding: utf-8 -*-
"""
Connexion base de donnees - bascule local <-> Aiven via variables d'env.

La chaine de connexion est construite depuis les variables d'environnement
(fichier .env en local, secrets Aiven en distant). AUCUN identifiant en dur.

Variables attendues :
  DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD
  DB_SSLMODE (optionnel : 'require' / 'verify-ca' / 'verify-full' pour Aiven)
  DB_SSLROOTCERT (optionnel : chemin vers le CA Aiven, ex. db/aiven-ca.pem)
"""
import os
from urllib.parse import quote_plus, urlencode

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

ROOT = os.path.join(os.path.dirname(__file__), "..")
DEFAULT_CA = os.path.join(ROOT, "db", "aiven-ca.pem")


def get_database_url() -> str:
    host = os.getenv("DB_HOST", "db")
    port = os.getenv("DB_PORT", "5432")
    name = os.getenv("DB_NAME", "electio")
    user = quote_plus(os.getenv("DB_USER", "electio"))
    pwd = quote_plus(os.getenv("DB_PASSWORD", "electio"))
    url = f"postgresql+psycopg2://{user}:{pwd}@{host}:{port}/{name}"

    sslmode = (os.getenv("DB_SSLMODE") or "").strip()
    if not sslmode:
        return url

    params = {"sslmode": sslmode}
    # Certificat CA Aiven (verify-ca / verify-full) ou require + rootcert
    ca = (os.getenv("DB_SSLROOTCERT") or "").strip()
    if not ca and os.path.isfile(DEFAULT_CA):
        ca = DEFAULT_CA
    if ca:
        # Relatif au projet si pas absolu (évite le piège WORKDIR Docker)
        if not os.path.isabs(ca):
            ca = os.path.join(ROOT, ca)
        ca = os.path.abspath(ca)
        if not os.path.isfile(ca):
            raise FileNotFoundError(f"Certificat SSL introuvable : {ca}")
        params["sslrootcert"] = ca
        # Si on a un CA, renforcer le mode si l'utilisateur a mis seulement require
        if sslmode == "require":
            params["sslmode"] = "verify-ca"

    url += "?" + urlencode(params)
    return url


def get_engine() -> Engine:
    return create_engine(get_database_url(), pool_pre_ping=True)
