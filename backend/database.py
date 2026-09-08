# -*- coding: utf-8 -*-
"""
Connexion base de donnees - bascule local <-> Aiven via variables d'env.

La chaine de connexion est construite depuis les variables d'environnement
(fichier .env en local, secrets Aiven / Render en distant). AUCUN identifiant en dur.

Variables attendues :
  DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD
  DB_SSLMODE (optionnel : 'require' / 'verify-ca' / 'verify-full' pour Aiven)
  DB_SSLROOTCERT (optionnel : chemin vers le CA Aiven, ex. db/aiven-ca.pem)
  DB_CA_PEM (optionnel : contenu PEM du CA, secret Render — prioritaire)
"""
import os
import tempfile
from urllib.parse import quote_plus, urlencode

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

ROOT = os.path.join(os.path.dirname(__file__), "..")
DEFAULT_CA = os.path.join(ROOT, "db", "aiven-ca.pem")


def _normalize_pem(raw: str) -> str:
    pem = raw.strip().strip('"').strip("'")
    # Render / CI : le PEM est souvent collé sur une ligne avec \n échappés
    if "\\n" in pem and "\n" not in pem:
        pem = pem.replace("\\n", "\n")
    if not pem.endswith("\n"):
        pem += "\n"
    return pem


def _ca_from_secret() -> str | None:
    """Écrit le secret DB_CA_PEM dans un fichier temporaire (Render)."""
    raw = (os.getenv("DB_CA_PEM") or os.getenv("AIVEN_CA_PEM") or "").strip()
    if not raw:
        return None
    pem = _normalize_pem(raw)
    dest = (os.getenv("DB_CA_PEM_PATH") or "").strip()
    if not dest:
        dest = os.path.join(tempfile.gettempdir(), "aiven-ca.pem")
    elif not os.path.isabs(dest):
        dest = os.path.join(ROOT, dest)
    dest = os.path.abspath(dest)
    parent = os.path.dirname(dest)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(dest, "w", encoding="utf-8") as fh:
        fh.write(pem)
    return dest


def _resolve_ca_path() -> str | None:
    from_secret = _ca_from_secret()
    if from_secret:
        return from_secret

    ca = (os.getenv("DB_SSLROOTCERT") or "").strip()
    if not ca and os.path.isfile(DEFAULT_CA):
        ca = DEFAULT_CA
    if not ca:
        return None
    if not os.path.isabs(ca):
        ca = os.path.join(ROOT, ca)
    ca = os.path.abspath(ca)
    if not os.path.isfile(ca):
        raise FileNotFoundError(f"Certificat SSL introuvable : {ca}")
    return ca


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
    ca = _resolve_ca_path()
    if ca:
        params["sslrootcert"] = ca
        # Si on a un CA, renforcer le mode si l'utilisateur a mis seulement require
        if sslmode == "require":
            params["sslmode"] = "verify-ca"

    url += "?" + urlencode(params)
    return url


def get_engine() -> Engine:
    return create_engine(get_database_url(), pool_pre_ping=True)
