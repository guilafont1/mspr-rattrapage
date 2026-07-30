# -*- coding: utf-8 -*-
"""
Sync BRONZE / RAW -> datalake objet (MinIO / S3).

Strategie Big Data du POC :
  - Zone RAW / BRONZE immuable dans un object store (pattern datalake)
  - Transform (SILVER/GOLD) reste en ELT leger : on charge puis on transforme
  - En production : remplacer MinIO local par S3/OVH Object Storage + Airflow

Variables d'environnement (defauts = docker-compose service `minio`) :
  MINIO_ENDPOINT=localhost:9000
  MINIO_ACCESS_KEY=electio
  MINIO_SECRET_KEY=electioelectio
  MINIO_BUCKET=electio-datalake
  MINIO_SECURE=0
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

ENDPOINT = os.getenv("MINIO_ENDPOINT", "localhost:9010")
ACCESS = os.getenv("MINIO_ACCESS_KEY", "electio")
SECRET = os.getenv("MINIO_SECRET_KEY", "electioelectio")
BUCKET = os.getenv("MINIO_BUCKET", "electio-datalake")
SECURE = os.getenv("MINIO_SECURE", "0") == "1"


def _client():
    try:
        from minio import Minio
    except ImportError as e:
        raise SystemExit(
            "Package manquant : pip install minio\n"
            "(ou lancer via le conteneur backend qui l'installe)"
        ) from e
    return Minio(ENDPOINT, access_key=ACCESS, secret_key=SECRET, secure=SECURE)


def ensure_bucket(client) -> None:
    if not client.bucket_exists(BUCKET):
        client.make_bucket(BUCKET)
        print(f"[DATALAKE] bucket cree : {BUCKET}")
    else:
        print(f"[DATALAKE] bucket OK : {BUCKET}")


def upload_tree(client, local_dir: Path, prefix: str) -> int:
    if not local_dir.is_dir():
        print(f"[SKIP] {local_dir} absent")
        return 0
    n = 0
    for path in local_dir.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(local_dir).as_posix()
        object_name = f"{prefix}/{rel}"
        client.fput_object(BUCKET, object_name, str(path))
        n += 1
    print(f"[DATALAKE] {prefix}: {n} objets -> s3://{BUCKET}/{prefix}/")
    return n


def main() -> int:
    print(f"Endpoint MinIO : {ENDPOINT} (secure={SECURE})")
    try:
        client = _client()
        # ping
        client.list_buckets()
    except Exception as e:
        print(
            f"[WARN] MinIO inaccessible ({e}).\n"
            "  Demarrer : docker compose --profile datalake up -d minio\n"
            "  Puis relancer : python etl/03_sync_datalake.py"
        )
        return 0  # non bloquant pour le POC offline

    ensure_bucket(client)
    total = 0
    total += upload_tree(client, DATA / "raw", "bronze/raw")
    total += upload_tree(client, DATA / "bronze", "bronze/normalized")
    total += upload_tree(client, DATA / "silver", "silver")
    total += upload_tree(client, DATA / "gold", "gold")
    print(f"Sync termine : {total} fichiers. Pattern datalake medaillon OK.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
