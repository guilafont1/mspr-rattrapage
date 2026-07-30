# -*- coding: utf-8 -*-
"""
ETL - Etape 1 : Telechargement + normalisation des donnees brutes (couche BRONZE).
POC Electio-Analytics - perimetre : France metropolitaine par departement.

Sources publiques (Licence Ouverte v2.0 - Etalab / INSEE) :
  - Resultats presidentielles T1 par departement (data.gouv.fr / Ministere Interieur)
  - Chomage localise trimestriel (INSEE, serie longue)
  - Emploi salarie trimestriel (INSEE, serie longue)
  - Population departementale (INSEE Melodi - DS_ESTIMATION_POPULATION)
  - Taux de pauvrete (INSEE Melodi Filosofi - millesime disponible)
  - Creations d'entreprises (INSEE Melodi SIDE), ramenees pour 10 000 hab.

Pipeline :
  1) Telecharge les fichiers bruts dans data/raw/ (jamais ecrases en bronze)
  2) Normalise vers les CSV BRONZE au contrat exact attendu par 02_transform.py

Les URL de ressources data.gouv sont resolues via l'API (slug stable).
Les fichiers INSEE "serie longue" (sl_etc_*, sl_ete_*) changent de millesime :
on les resolut depuis la page catalogue, sans inventer d'identifiant.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Iterable

import numpy as np
import pandas as pd

# mapping candidat -> bloc (fichier dedie, modifiable)
sys.path.insert(0, os.path.dirname(__file__))
from mapping_blocs import BLOCS, assert_mapping_complet, bloc_pour, normaliser_nom
from referentiels import BRONZE_SCHEMAS, METRO_DEPTS as REF_METRO

ROOT = os.path.join(os.path.dirname(__file__), "..")
RAW = os.path.join(ROOT, "data", "raw")
BRONZE = os.path.join(ROOT, "data", "bronze")

UA = {"User-Agent": "ElectioAnalytics-POC/1.0 (MSPR TPRE813; educational)"}
ELECTIONS = [2002, 2007, 2012, 2017, 2022]
METRO_DEPTS = list(REF_METRO)

# Pages catalogue (stables) — les URL de fichier sont resolues dynamiquement
CATALOGUES = {
    "elections": "https://www.data.gouv.fr/fr/pages/donnees-des-elections/",
    "chomage": "https://www.insee.fr/fr/statistiques/2012804",
    "emploi": "https://www.insee.fr/fr/statistiques/2134435",
    # Estimations de population (fichier XLSX serie longue, resolu depuis la page)
    "population": "https://www.insee.fr/fr/statistiques/8721456",
    "pauvrete": "https://catalogue-donnees.insee.fr/fr/catalogue/recherche?q=DS_FILOSOFI_CC",
    "entreprises": "https://catalogue-donnees.insee.fr/fr/catalogue/recherche?q=DS_SIDE_CREA_DEP_REG_NAT",
    # TODO (pauvreté historique 2012-2021, Filosofi 1) : pages millésime sur
    # https://www.insee.fr/fr/statistiques?debut=0 — les id de fichier changent
    # à chaque publication ; brancher ici les CSV/XLS départementaux une fois
    # l'URL de ressource vérifiée (ne pas inventer d'identifiant).
    "pauvrete_historique": (
        "https://www.data.gouv.fr/datasets/"
        "revenus-et-pauvrete-des-menages-aux-niveaux-national-et-local-"
        "revenus-localises-sociaux-et-fiscaux"
    ),
}

# Controles anti-demo : ordres de grandeur INSEE (annees recentes).
# Si le bronze ressemble encore a 00_demo_data.py, ces bornes ECHOUENT.
SANITY = {
    "population": {
        # pop 2021-2024 approx : 75~2.1M, 01~0.66M, 23~0.12M
        "annee": 2021,
        "col": "population",
        "bounds": {
            "75": (1_800_000, 2_400_000),
            "01": (550_000, 750_000),
            "23": (90_000, 140_000),
        },
        "order": ("75", "01", "23"),  # pop_75 > pop_01 > pop_23
    },
    "chomage": {
        # Ain ~5-7%, Paris ~5-8%, Creuse ~6-10% (pas tous ~9.5% comme en demo)
        "annee": 2021,
        "col": "taux_chomage",
        "agg": "mean",  # moyenne annuelle des trimestres
        "bounds": {
            "75": (4.0, 9.0),
            "01": (4.0, 8.0),
            "23": (5.0, 12.0),
        },
    },
    "emploi": {
        # emploi salarie (unites) ~ 75:1.7M, 01:200k, 23:35k
        "annee": 2021,
        "col": "emploi_total",
        "agg": "mean",
        "bounds": {
            "75": (1_400_000, 2_200_000),
            "01": (150_000, 280_000),
            "23": (20_000, 55_000),
        },
        "order": ("75", "01", "23"),
    },
    "pauvrete": {
        # Filosofi : Paris eleve, Ain bas, Creuse eleve
        "annee": 2023,
        "col": "taux_pauvrete",
        "bounds": {
            "75": (12.0, 22.0),
            "01": (7.0, 14.0),
            "23": (14.0, 28.0),
        },
    },
    "entreprises": {
        # Paris tres dynamique (micro-entreprises) : souvent 300-450 / 10k
        "annee": 2021,
        "col": "creations_entreprises_10k",
        "bounds": {
            "75": (200.0, 550.0),
            "01": (50.0, 200.0),
            "23": (40.0, 200.0),
        },
    },
    "elections": {
        # Inscrits 2022 : Ain~438k, Paris~1.36M, Creuse~90k (demo inverse Creuse!!)
        "annee": 2022,
        "col": "inscrits",
        "bounds": {
            "75": (1_000_000, 1_600_000),
            "01": (380_000, 500_000),
            "23": (70_000, 120_000),
        },
        "order": ("75", "01", "23"),
    },
}

# Slugs data.gouv verifies (API /api/1/datasets/{slug}/)
ELECTION_DATASETS = {
    2022: {
        "slug": "election-presidentielle-des-10-et-24-avril-2022-resultats-definitifs-du-1er-tour",
        "prefer": ("dpt", "departement"),
        "sheet": None,  # 1ere feuille
        "header_row": 0,
    },
    2017: {
        "slug": "election-presidentielle-des-23-avril-et-7-mai-2017-resultats-du-1er-tour",
        "prefer": (),
        "sheet": "Départements Tour 1",
        "header_row": 3,
    },
    2012: {
        "slug": "election-presidentielle-2012-resultats-572124",
        "prefer": (),
        "sheet": "Départements T1",
        "header_row": 0,
    },
    2007: {
        "slug": "election-presidentielle-2007-resultats-572120",
        "prefer": (),
        "sheet": "Départements T1",
        "header_row": 0,
    },
    2002: {
        "slug": "election-presidentielle-2002-resultats-572114",
        "prefer": (),
        "sheet": "Départements T1",
        "header_row": 0,
    },
}


# ---------------------------------------------------------------------------
# Controles anti-demo (ordres de grandeur)
# ---------------------------------------------------------------------------

def assert_realistic(source: str, df: pd.DataFrame) -> None:
    """
    Compare 75 / 01 / 23 a des bornes INSEE. Echec bruyant si le bronze
    ressemble encore aux donnees simulees de 00_demo_data.py.
    """
    cfg = SANITY.get(source)
    if not cfg:
        return
    if df is None or df.empty:
        raise RuntimeError(
            f"[SANITY KO] {source}: DataFrame vide — probable echec de telechargement "
            f"ou ecrasement par la demo."
        )
    annee = cfg["annee"]
    col = cfg["col"]
    sub = df[df["annee"] == annee].copy() if "annee" in df.columns else df.copy()
    if sub.empty:
        # tenter annee proche
        for delta in (0, -1, 1, -2, 2):
            sub = df[df["annee"] == annee + delta]
            if not sub.empty:
                annee = annee + delta
                break
    if sub.empty:
        raise RuntimeError(
            f"[SANITY KO] {source}: aucune ligne pour annee~{cfg['annee']} "
            f"(colonnes={list(df.columns)}, annees={sorted(df['annee'].unique())[:8]}...)"
        )

    values = {}
    for code, (lo, hi) in cfg["bounds"].items():
        part = sub[sub["code_dept"].astype(str) == code]
        if part.empty:
            raise RuntimeError(
                f"[SANITY KO] {source}: departement {code} absent pour {annee} — "
                f"donnees incompletes ou encore en mode demo."
            )
        if cfg.get("agg") == "mean":
            val = float(part[col].mean())
        else:
            val = float(part.iloc[0][col])
        values[code] = val
        if not (lo <= val <= hi):
            raise RuntimeError(
                f"[SANITY KO] {source}: {code} {col}={val:.2f} hors [{lo}, {hi}] "
                f"(annee={annee}).\n"
                f"  -> Les donnees BRONZE ne sont PAS les vraies sources INSEE "
                f"(souvent: ecrasement par etl/00_demo_data.py).\n"
                f"  -> Relancer uniquement `python etl/01_download.py` puis "
                f"`python run_pipeline.py --real` SANS repasser par la demo."
            )
        print(f"  [SANITY OK] {source} {code} {col}={val:.2f} in [{lo}, {hi}] ({annee})")

    order = cfg.get("order")
    if order and len(order) >= 2:
        for a, b in zip(order, order[1:]):
            if values[a] <= values[b]:
                raise RuntimeError(
                    f"[SANITY KO] {source}: ordre attendu {a}>{b} mais "
                    f"{values[a]:.2f} <= {values[b]:.2f} (signature typique de la demo)."
                )


def find_cached(subdir: str, prefix: str, suffixes: tuple[str, ...]) -> str | None:
    d = os.path.join(RAW, subdir)
    if not os.path.isdir(d):
        return None
    for fname in sorted(os.listdir(d)):
        low = fname.lower()
        if low.startswith(prefix.lower()) and low.endswith(suffixes):
            return os.path.join(d, fname)
    return None


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def _request(url: str, timeout: int = 120, retries: int = 5) -> bytes:
    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except urllib.error.HTTPError as e:
            last_err = e
            # 429 Melodi (~30 req/min) : backoff plus long
            wait = 65.0 if e.code == 429 else 1.5 * (attempt + 1)
            print(f"[RETRY] {url} ({attempt + 1}/{retries}) : {e} — pause {wait:.1f}s")
            time.sleep(wait)
        except (urllib.error.URLError, TimeoutError, ConnectionResetError, OSError) as e:
            last_err = e
            wait = 1.5 * (attempt + 1)
            print(f"[RETRY] {url} ({attempt + 1}/{retries}) : {e} — pause {wait:.1f}s")
            time.sleep(wait)
    raise RuntimeError(f"Echec telechargement apres {retries} essais : {url} ({last_err})")


def download(url: str, dest: str, force: bool = False) -> str:
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    if os.path.exists(dest) and not force and os.path.getsize(dest) > 0:
        print(f"[CACHE] {dest}")
        return dest
    print(f"[GET ] {url}")
    print(f"    -> {dest}")
    data = _request(url)
    with open(dest, "wb") as f:
        f.write(data)
    return dest


def resolve_datagouv_resource(slug: str, prefer_tokens: Iterable[str] = ()) -> dict:
    """Recupere la 1re ressource utile d'un dataset data.gouv via l'API."""
    api = f"https://www.data.gouv.fr/api/1/datasets/{slug}/"
    meta = json.loads(_request(api))
    resources = meta.get("resources") or []
    if not resources:
        raise RuntimeError(f"Aucune ressource pour dataset {slug}")
    tokens = tuple(t.lower() for t in prefer_tokens)
    chosen = None
    if tokens:
        for res in resources:
            blob = f"{res.get('title', '')} {res.get('url', '')}".lower()
            if any(t in blob for t in tokens):
                # Preferer xlsx/xls/txt tabulaires
                fmt = (res.get("format") or "").lower()
                if fmt in {"xlsx", "xls", "csv", "txt"} or True:
                    chosen = res
                    if fmt in {"xlsx", "xls", "csv", "txt"}:
                        break
    if chosen is None:
        chosen = resources[0]
    return chosen


def resolve_insee_fichier(catalogue_url: str, name_regex: str) -> str:
    """
    Extrait depuis une page INSEE le lien /fr/statistiques/fichier/... correspondant.
    Les noms de fichiers (ex. sl_etc_2026T1.xls) changent a chaque millesime.
    """
    html = _request(catalogue_url).decode("utf-8", "replace")
    links = re.findall(r'href="(/fr/statistiques/fichier/[^"]+)"', html)
    pat = re.compile(name_regex, re.I)
    for rel in links:
        if pat.search(rel):
            return "https://www.insee.fr" + rel
    raise RuntimeError(
        f"Aucun fichier matching /{name_regex}/ sur {catalogue_url}. "
        f"Liens trouves : {links[:10]}"
    )


def melodi_fetch(dataset_id: str, params: dict, max_pages: int = 50) -> list[dict]:
    """Pagination Melodi (maxResult=1000)."""
    base = f"https://api.insee.fr/melodi/data/{dataset_id}"
    q = dict(params)
    q.setdefault("maxResult", 1000)
    page = 1
    out: list[dict] = []
    while page <= max_pages:
        q["page"] = page
        url = base + "?" + urllib.parse.urlencode(q)
        try:
            payload = json.loads(_request(url))
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"Melodi {dataset_id} page {page} : {e}") from e
        obs = payload.get("observations") or []
        out.extend(obs)
        paging = payload.get("paging") or {}
        if paging.get("isLast", True) or not obs:
            break
        page += 1
        time.sleep(0.05)  # respect ~30 req/min marge
    return out


def melodi_fetch_slow(dataset_id: str, params: dict, max_pages: int = 50) -> list[dict]:
    """Comme melodi_fetch avec pause plus longue (endpoints sensibles au quota)."""
    base = f"https://api.insee.fr/melodi/data/{dataset_id}"
    q = dict(params)
    q.setdefault("maxResult", 1000)
    page = 1
    out: list[dict] = []
    while page <= max_pages:
        q["page"] = page
        url = base + "?" + urllib.parse.urlencode(q)
        try:
            payload = json.loads(_request(url))
        except RuntimeError as e:
            raise RuntimeError(f"Melodi {dataset_id} page {page} : {e}") from e
        obs = payload.get("observations") or []
        out.extend(obs)
        paging = payload.get("paging") or {}
        if paging.get("isLast", True) or not obs:
            break
        page += 1
        time.sleep(2.1)
    return out


# ---------------------------------------------------------------------------
# Codes departement
# ---------------------------------------------------------------------------

def norm_code_dept(val) -> str | None:
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return None
    s = str(val).strip().upper()
    if not s or s.lower() in {"nan", "none", "na", "n/a", "-"}:
        return None
    # Enlever suffixe float "01.0"
    if re.fullmatch(r"\d+\.0", s):
        s = s[:-2]
    if s in {"2A", "2B"}:
        return s
    if s.isdigit():
        s = f"{int(s):02d}"
    if s in METRO_DEPTS:
        return s
    return None  # DOM/TOM / France entiere / etc.


def to_numeric_series(s: pd.Series) -> pd.Series:
    """Convertit nombres FR (virgule, espaces, N/A) en float."""
    if s.dtype.kind in "iufc":
        return pd.to_numeric(s, errors="coerce")
    cleaned = (
        s.astype(str)
        .str.strip()
        .str.replace("\u00a0", "", regex=False)
        .str.replace(" ", "", regex=False)
        .str.replace(",", ".", regex=False)
        .replace(
            {
                "": np.nan,
                "nan": np.nan,
                "None": np.nan,
                "NA": np.nan,
                "N/A": np.nan,
                "n/a": np.nan,
                "-": np.nan,
                "nd": np.nan,
                "ND": np.nan,
                "s": np.nan,  # secret statistique
                "so": np.nan,
            }
        )
    )
    # Enlever annotations (p), (r), (sd)
    cleaned = cleaned.str.replace(r"^\((?:p|r|sd)\)\s*", "", regex=True)
    cleaned = cleaned.str.replace(r"\s*\((?:p|r|sd)\)$", "", regex=True)
    return pd.to_numeric(cleaned, errors="coerce")


def geo_to_dept(geo: str) -> str | None:
    """Extrait le code dept depuis un code Melodi du type 2026-DEP-01."""
    if not geo or "-DEP-" not in geo:
        return None
    return norm_code_dept(geo.split("-DEP-")[-1])


# ---------------------------------------------------------------------------
# Elections
# ---------------------------------------------------------------------------

def _candidate_blocks(df: pd.DataFrame, header_row: int) -> tuple[int, list[tuple[int, int]]]:
    """
    Localise les blocs candidats (Sexe, Nom, Prenom, Voix, %Ins, %Exp).
    Retourne (col_inscrits, [(col_nom, col_voix), ...]).
    """
    header = [str(x).strip().lower() if pd.notna(x) else "" for x in df.iloc[header_row]]
    # Inscrits
    col_ins = next((i for i, h in enumerate(header) if h == "inscrits"), 2)
    # Premiere colonne Sexe / Nom du 1er candidat
    start = next((i for i, h in enumerate(header) if h in {"sexe", "nom"}), None)
    if start is None:
        raise ValueError("Impossible de trouver le debut des blocs candidats")
    # Detecter taille de bloc : apres 'nom' viennent prenom, voix...
    # Convention MI : 6 colonnes
    block = 6
    pairs = []
    col = start
    while col + 3 < df.shape[1]:
        # Nom = col+1, Voix = col+3 dans le schema standard
        nom_col = col + 1
        voix_col = col + 3
        # Verifier qu'il y a au moins une valeur de nom dans les donnees
        sample = df.iloc[header_row + 1 :, nom_col].dropna()
        if sample.empty:
            break
        # Arreter si on tombe sur des totaux / hors candidats
        first = str(sample.iloc[0]).strip().upper()
        if first in {"", "NAN", "TOTAL"}:
            break
        pairs.append((nom_col, voix_col))
        col += block
    if not pairs:
        raise ValueError("Aucun bloc candidat detecte")
    return col_ins, pairs


def _find_sheet(path: str, wanted: str | None):
    """Retourne le nom de feuille (tolerante aux accents) ou 0."""
    if wanted is None:
        return 0
    xl = pd.ExcelFile(path)
    if wanted in xl.sheet_names:
        return wanted
    want = wanted.lower().encode("ascii", "ignore").decode()
    for name in xl.sheet_names:
        norm = name.lower().encode("ascii", "ignore").decode()
        if want in norm or norm in want:
            return name
    # Fallback : premiere feuille contenant 'depart'
    for name in xl.sheet_names:
        if "depart" in name.lower().encode("ascii", "ignore").decode():
            return name
    raise ValueError(f"Feuille '{wanted}' introuvable dans {path}: {xl.sheet_names}")


def parse_election_file(path: str, annee: int, sheet, header_row: int) -> pd.DataFrame:
    sheet_name = _find_sheet(path, sheet)
    df = pd.read_excel(path, sheet_name=sheet_name, header=None)
    col_ins, pairs = _candidate_blocks(df, header_row)
    data = df.iloc[header_row + 1 :].copy()
    rows = []
    unknown = set()
    for _, r in data.iterrows():
        code = norm_code_dept(r.iloc[0])
        if code is None:
            continue
        inscrits = to_numeric_series(pd.Series([r.iloc[col_ins]])).iloc[0]
        voix_blocs = {b: 0.0 for b in BLOCS}
        total_voix = 0.0
        for nom_col, voix_col in pairs:
            nom = r.iloc[nom_col]
            if pd.isna(nom) or str(nom).strip() == "":
                continue
            voix = to_numeric_series(pd.Series([r.iloc[voix_col]])).iloc[0]
            if pd.isna(voix):
                continue
            bloc = bloc_pour(annee, nom)
            if bloc is None:
                unknown.add(normaliser_nom(nom))
                continue
            voix_blocs[bloc] += float(voix)
            total_voix += float(voix)
        if total_voix <= 0 or pd.isna(inscrits):
            continue
        row = {
            "annee": annee,
            "code_dept": code,
            "inscrits": int(inscrits),
        }
        for b in BLOCS:
            row[f"pct_{b}"] = round(100.0 * voix_blocs[b] / total_voix, 2)
        rows.append(row)
    if unknown:
        raise ValueError(
            f"Candidats non mappes pour {annee} : {sorted(unknown)}. "
            f"Completer etl/mapping_blocs.py"
        )
    # Controle mapping sur un echantillon de noms lus
    sample_noms = []
    for nom_col, _ in pairs:
        v = data.iloc[0, nom_col]
        if pd.notna(v):
            sample_noms.append(str(v))
    missing = assert_mapping_complet(annee, sample_noms)
    if missing:
        raise ValueError(f"Mapping incomplet {annee}: {missing}")
    return pd.DataFrame(rows)


def build_elections() -> pd.DataFrame:
    """Telecharge/parse les 5 scrutins — resolution+download en parallele (I/O bound)."""

    def _one(annee: int, cfg: dict) -> pd.DataFrame:
        cached = None
        elec_dir = os.path.join(RAW, "elections")
        if os.path.isdir(elec_dir):
            for fname in os.listdir(elec_dir):
                if f"presidentielle_t1_{annee}." in fname:
                    cached = os.path.join(elec_dir, fname)
                    break
        if cached:
            print(f"[CACHE] elections {annee}: {cached}")
            dest = cached
        else:
            res = resolve_datagouv_resource(cfg["slug"], cfg.get("prefer") or ())
            ext = (res.get("format") or "xls").lower()
            if ext not in {"xls", "xlsx", "csv", "txt"}:
                url = res["url"]
                ext = url.rsplit(".", 1)[-1].lower() if "." in url.rsplit("/", 1)[-1] else "bin"
            dest = os.path.join(RAW, "elections", f"presidentielle_t1_{annee}.{ext}")
            download(res["url"], dest)
        part = parse_election_file(dest, annee, cfg["sheet"], cfg["header_row"])
        print(f"  elections {annee}: {len(part)} depts metro")
        return part

    frames = []
    # Pipeline parallele d'ingestion (pattern big data I/O-bound ; scale-out = workers+)
    with ThreadPoolExecutor(max_workers=min(5, len(ELECTION_DATASETS))) as pool:
        futs = {
            pool.submit(_one, annee, cfg): annee
            for annee, cfg in ELECTION_DATASETS.items()
        }
        for fut in as_completed(futs):
            frames.append(fut.result())

    out = pd.concat(frames, ignore_index=True)
    # Dedup + filtre metro
    out = out[out["code_dept"].isin(METRO_DEPTS)]
    out = out.drop_duplicates(["annee", "code_dept"], keep="first")
    # Completer depts manquants : on n'invente PAS de scores ; on journalise
    missing = []
    for an in ELECTIONS:
        present = set(out.loc[out["annee"] == an, "code_dept"])
        for d in METRO_DEPTS:
            if d not in present:
                missing.append((an, d))
    if missing:
        print(f"[WARN] {len(missing)} (annee, dept) elections manquants (non imputes) : "
              f"{missing[:10]}{'...' if len(missing) > 10 else ''}")
    return out.sort_values(["annee", "code_dept"]).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Chomage / Emploi (fichiers wide INSEE serie longue)
# ---------------------------------------------------------------------------

def _melt_trim_wide(df_raw: pd.DataFrame, value_name: str, scale: float = 1.0) -> pd.DataFrame:
    """
    Transforme un fichier wide INSEE (Code, Libelle, T1_1982, ...) en long.
    Lignes d'en-tete : on cherche la ligne contenant 'Code'.
    """
    header_idx = None
    for i in range(min(15, len(df_raw))):
        row = df_raw.iloc[i].astype(str).str.lower()
        if row.str.contains("^code$").any() or (row == "code").any():
            header_idx = i
            break
    if header_idx is None:
        raise ValueError("Ligne d'en-tete 'Code' introuvable")
    df = df_raw.iloc[header_idx:].copy()
    df.columns = [str(c).strip() for c in df.iloc[0]]
    df = df.iloc[1:].reset_index(drop=True)
    # Emploi : ne garder que la ligne "Total" (tous secteurs)
    act_cols = [c for c in df.columns if str(c).lower().startswith("activit")]
    if act_cols:
        act_col = act_cols[0]
        df = df[df[act_col].astype(str).str.strip().str.lower() == "total"]
    code_col = next((c for c in df.columns if str(c).strip().lower() == "code"), df.columns[0])
    period_cols = [c for c in df.columns if re.fullmatch(r"T[1-4]_\d{4}", str(c))]
    long = df.melt(id_vars=[code_col], value_vars=period_cols,
                   var_name="periode", value_name=value_name)
    long["code_dept"] = long[code_col].map(norm_code_dept)
    long = long.dropna(subset=["code_dept"])
    long["trimestre"] = long["periode"].str[1].astype(int)
    long["annee"] = long["periode"].str[3:].astype(int)
    long[value_name] = to_numeric_series(long[value_name]) * scale
    long = long.dropna(subset=[value_name])
    return long[["code_dept", "annee", "trimestre", value_name]]


def build_chomage() -> pd.DataFrame:
    chom_dir = os.path.join(RAW, "chomage")
    cached = None
    if os.path.isdir(chom_dir):
        for fname in os.listdir(chom_dir):
            if fname.lower().startswith("sl_etc_") and fname.lower().endswith((".xls", ".xlsx")):
                cached = os.path.join(chom_dir, fname)
                break
    if cached:
        print(f"[CACHE] {cached}")
        dest = cached
    else:
        url = resolve_insee_fichier(CATALOGUES["chomage"], r"sl_etc_.*\.xls")
        dest = os.path.join(RAW, "chomage", os.path.basename(urllib.parse.urlparse(url).path))
        download(url, dest)
    sheet = _find_sheet(dest, "Département")
    raw = pd.read_excel(dest, sheet_name=sheet, header=None)
    out = _melt_trim_wide(raw, "taux_chomage")
    # Bornes plausibles : on droppe les hors [0;30] (qualite amont)
    before = len(out)
    out = out[out["taux_chomage"].between(0, 30)]
    if len(out) < before:
        print(f"[WARN] chomage: {before - len(out)} valeurs hors [0;30] ecartees")
    out["taux_chomage"] = out["taux_chomage"].round(2)
    return out.drop_duplicates(["code_dept", "annee", "trimestre"]).sort_values(
        ["code_dept", "annee", "trimestre"]).reset_index(drop=True)


def build_emploi() -> pd.DataFrame:
    emp_dir = os.path.join(RAW, "emploi")
    cached = None
    if os.path.isdir(emp_dir):
        for fname in os.listdir(emp_dir):
            if fname.lower().startswith("sl_ete_") and fname.lower().endswith((".xls", ".xlsx")):
                cached = os.path.join(emp_dir, fname)
                break
    if cached:
        print(f"[CACHE] {cached}")
        dest = cached
    else:
        url = resolve_insee_fichier(CATALOGUES["emploi"], r"sl_ete_.*\.xls")
        dest = os.path.join(RAW, "emploi", os.path.basename(urllib.parse.urlparse(url).path))
        download(url, dest)
    sheet = _find_sheet(dest, "Département")
    raw = pd.read_excel(dest, sheet_name=sheet, header=None)
    # Fichier en milliers d'emplois -> unites
    out = _melt_trim_wide(raw, "emploi_total", scale=1000.0)
    out = out[out["emploi_total"] > 0]
    out["emploi_total"] = out["emploi_total"].round(0).astype(int)
    # TODO : serie anterieure a 2011 (estimations annuelles 1989-2014) —
    # catalogue https://www.insee.fr/fr/statistiques/2045226 (URL fichier a verifier
    # sur la page ; ne pas inventer l'identifiant). Les features emploi des
    # elections 2002/2007 resteront partiellement vides (None en GOLD).
    return out.drop_duplicates(["code_dept", "annee", "trimestre"]).sort_values(
        ["code_dept", "annee", "trimestre"]).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Population / Pauvreté / Entreprises (Melodi)
# ---------------------------------------------------------------------------

def build_population() -> pd.DataFrame:
    """
    Population depuis le fichier officiel INSEE XLSX (1 feuille = 1 annee).
    Catalogue : https://www.insee.fr/fr/statistiques/8721456
    """
    cached = find_cached("population", "estim-pop-dep-sexe-gca-", (".xlsx",))
    if cached:
        print(f"[CACHE] {cached}")
        dest = cached
    else:
        url = resolve_insee_fichier(
            CATALOGUES["population"], r"estim-pop-dep-sexe-gca-.*\.xlsx"
        )
        dest = os.path.join(
            RAW, "population", os.path.basename(urllib.parse.urlparse(url).path)
        )
        download(url, dest)

    xl = pd.ExcelFile(dest)
    rows = []
    for sheet in xl.sheet_names:
        # Feuilles numeriques = annees (ignorer 'A savoir', etc.)
        if not re.fullmatch(r"\d{4}", str(sheet).strip()):
            continue
        annee = int(str(sheet).strip())
        raw = pd.read_excel(xl, sheet_name=sheet, header=None)
        # Ligne de donnees : col0=code, col7=Total (apres en-tetes)
        for _, r in raw.iterrows():
            code = norm_code_dept(r.iloc[0])
            if code is None:
                continue
            # Colonne Total = derniere colonne numerique de la partie Ensemble
            # Schema constate : index 7 = Total Ensemble
            total = to_numeric_series(pd.Series([r.iloc[7] if len(r) > 7 else np.nan])).iloc[0]
            if pd.isna(total) or total <= 0:
                # fallback : max numerique de la ligne
                nums = to_numeric_series(r)
                total = float(nums.max()) if nums.notna().any() else np.nan
            if pd.isna(total) or total <= 0:
                continue
            rows.append({
                "code_dept": code,
                "annee": annee,
                "population": int(round(float(total))),
            })
    out = pd.DataFrame(rows).drop_duplicates(["code_dept", "annee"])
    if out.empty:
        raise RuntimeError("Population: aucune ligne apres parsing du XLSX INSEE")
    # Archive normalisee dans raw pour tracabilite
    arch = os.path.join(RAW, "population", "population_dept_from_xlsx.csv")
    out.to_csv(arch, index=False)
    print(f"[RAW ] archive {arch} ({len(out)} lignes)")
    return out.sort_values(["code_dept", "annee"]).reset_index(drop=True)


def _parse_filosofi_dep_frame(df: pd.DataFrame, annee: int) -> pd.DataFrame:
    """Extrait code_dept + taux_pauvrete depuis un CSV/XLS Filosofi niveau DEP."""
    cols = {str(c).strip(): c for c in df.columns}
    # Colonne geo
    geo_col = None
    for cand in ("CODGEO", "Code", "code", "DEP", "COD_DEP", "code_dept"):
        if cand in cols:
            geo_col = cols[cand]
            break
    if geo_col is None:
        # 1re colonne souvent le code
        geo_col = df.columns[0]
    yy = str(annee)[-2:]
    tp_col = None
    for cand in (f"TP60{yy}", f"TP60_{yy}", "TP60", "taux_pauvrete"):
        if cand in cols:
            tp_col = cols[cand]
            break
    if tp_col is None:
        # fallback: colonne contenant TP60 et pas AGE/TOL
        for c in df.columns:
            cu = str(c).upper()
            if "TP60" in cu and "AGE" not in cu and "TOL" not in cu:
                tp_col = c
                break
    if tp_col is None:
        raise RuntimeError(f"Filosofi {annee}: colonne TP60 introuvable dans {list(df.columns)[:20]}")

    out = pd.DataFrame({
        "code_dept": df[geo_col].map(norm_code_dept),
        "annee": annee,
        "taux_pauvrete": to_numeric_series(df[tp_col]),
    }).dropna(subset=["code_dept", "taux_pauvrete"])
    out = out[out["taux_pauvrete"].between(0, 40)]
    out = out[out["code_dept"].isin(METRO_DEPTS)]
    return out.drop_duplicates(["code_dept", "annee"])


def _filosofi_from_zip(zip_path: str, annee: int) -> pd.DataFrame:
    import io
    import zipfile
    with zipfile.ZipFile(zip_path) as z:
        names = z.namelist()
        dep_csv = [
            n for n in names
            if re.search(r"DEP\.csv$", n, re.I) and "meta" not in n.lower()
        ]
        if dep_csv:
            df = pd.read_csv(z.open(dep_csv[0]), sep=";", encoding="utf-8", dtype=str)
            return _parse_filosofi_dep_frame(df, annee)
        # Fallback XLS dans le zip (ex. millésime 2016)
        xls = [n for n in names if n.lower().endswith((".xls", ".xlsx"))]
        if not xls:
            raise RuntimeError(
                f"Filosofi {annee}: aucun DEP/CSV/XLS dans {os.path.basename(zip_path)}"
            )
        raw = z.read(xls[0])
        xl = pd.ExcelFile(io.BytesIO(raw))
        sheet = next(
            (s for s in xl.sheet_names if re.search(r"^DEP$", s, re.I)),
            next(
                (s for s in xl.sheet_names if re.search(r"dep|département|departement", s, re.I)),
                xl.sheet_names[0],
            ),
        )
        # Fichiers Filosofi XLS : en-tetes souvent a la ligne 5/6
        preview = pd.read_excel(xl, sheet_name=sheet, header=None, nrows=12, dtype=str)
        header_row = 0
        for i, row in preview.iterrows():
            vals = " ".join(str(v) for v in row.values if pd.notna(v))
            if re.search(r"CODGEO|TP60", vals, re.I):
                header_row = int(i)
                break
        df = pd.read_excel(xl, sheet_name=sheet, header=header_row, dtype=str)
        return _parse_filosofi_dep_frame(df, annee)


def _filosofi_from_xls(path: str, annee: int) -> pd.DataFrame:
    xl = pd.ExcelFile(path)
    # Preferer feuille DEP / departement
    sheet = None
    for s in xl.sheet_names:
        if re.search(r"dep|département|departement", s, re.I):
            sheet = s
            break
    if sheet is None:
        sheet = xl.sheet_names[0]
    df = pd.read_excel(path, sheet_name=sheet, dtype=str)
    return _parse_filosofi_dep_frame(df, annee)


def build_pauvrete_historique() -> pd.DataFrame:
    """
    Millésimes Filosofi 1 (2016-2021) depuis pages INSEE officielles.
    Couvre N-1 des scrutins 2017 (2016) et 2022 (2021) a minima.
    """
    # Pages catalogue INSEE verifiees (pas d'id invente) + motif de fichier
    millesimes = [
        {
            "annee": 2016,
            "page": "https://www.insee.fr/fr/statistiques/4190004",
            "regex": r"filosofi-revenu-pauvrete-menage-2016\.zip",
            "kind": "zip",
        },
        {
            "annee": 2017,
            "page": "https://www.insee.fr/fr/statistiques/4507225",
            "regex": r"base-filosofi-2017_CSV\.zip",
            "kind": "zip",
        },
        {
            "annee": 2019,
            "page": "https://www.insee.fr/fr/statistiques/6036902",
            "regex": r"base-cc-filosofi-2019_CSV\.zip$",
            "kind": "zip",
        },
        {
            "annee": 2021,
            "page": "https://www.insee.fr/fr/statistiques/7756729",
            "regex": r"base-cc-filosofi-2021-geo2023-histo_CSV\.zip",
            "kind": "zip",
        },
    ]
    frames = []
    raw_dir = os.path.join(RAW, "pauvrete")
    os.makedirs(raw_dir, exist_ok=True)
    for m in millesimes:
        an = m["annee"]
        cache = find_cached("pauvrete", f"filosofi_{an}", (".zip", ".xls", ".xlsx", ".csv"))
        try:
            if cache is None:
                url = resolve_insee_fichier(m["page"], m["regex"])
                ext = ".zip" if ".zip" in url.lower() else os.path.splitext(url)[1]
                dest = os.path.join(raw_dir, f"filosofi_{an}{ext}")
                download(url, dest)
                cache = dest
            else:
                print(f"[CACHE] Filosofi {an}: {cache}")
            if cache.lower().endswith(".zip"):
                part = _filosofi_from_zip(cache, an)
            else:
                part = _filosofi_from_xls(cache, an)
            print(f"  Filosofi {an}: {len(part)} depts")
            frames.append(part)
        except Exception as e:
            print(f"  [WARN] Filosofi {an} ignore : {e}")
    if not frames:
        return pd.DataFrame(columns=["code_dept", "annee", "taux_pauvrete"])
    return pd.concat(frames, ignore_index=True).drop_duplicates(["code_dept", "annee"])


def build_pauvrete() -> pd.DataFrame:
    """
    Pauvreté départementale :
      1) millésimes Filosofi historiques (2016/2017/2019/2021) via pages INSEE
      2) millésime courant Melodi Filosofi 2 (PR_MD60), typiquement 2023
    Persiste les bruts dans data/raw/pauvrete/.
    """
    histo = build_pauvrete_historique()

    cache_csv = os.path.join(RAW, "pauvrete", "filosofi_pr_md60_dept.csv")
    rows = []
    if os.path.exists(cache_csv) and os.path.getsize(cache_csv) > 0:
        print(f"[CACHE] Melodi courant : {cache_csv}")
        cached = pd.read_csv(cache_csv, dtype={"code_dept": str})
        rows = cached.to_dict("records")
    else:
        for code in METRO_DEPTS:
            obs = []
            for geo_year in (2025, 2026, 2024):
                geo = f"{geo_year}-DEP-{code}"
                try:
                    obs = melodi_fetch_slow(
                        "DS_FILOSOFI_CC",
                        {"FILOSOFI_MEASURE": "PR_MD60", "GEO": geo, "maxResult": 50},
                        max_pages=1,
                    )
                except RuntimeError:
                    obs = []
                if obs:
                    break
            for o in obs:
                dims = o.get("dimensions") or {}
                val = (o.get("measures") or {}).get("OBS_VALUE_NIVEAU", {}).get("value")
                if val is None:
                    continue
                try:
                    annee = int(dims["TIME_PERIOD"])
                    taux = float(val)
                except (KeyError, TypeError, ValueError):
                    continue
                if 0 <= taux <= 40:
                    rows.append({
                        "code_dept": code,
                        "annee": annee,
                        "taux_pauvrete": round(taux, 2),
                    })
            time.sleep(2.1)
        os.makedirs(os.path.dirname(cache_csv), exist_ok=True)
        pd.DataFrame(rows).to_csv(cache_csv, index=False)
        print(f"[RAW ] archive Melodi {cache_csv} ({len(rows)} lignes)")

    courant = pd.DataFrame(rows)
    parts = [p for p in (histo, courant) if p is not None and not p.empty]
    if not parts:
        raise RuntimeError(
            "Pauvrete: aucune donnee — ni historique ni Melodi. "
            f"Catalogues: {CATALOGUES['pauvrete']} | {CATALOGUES['pauvrete_historique']}"
        )
    out = pd.concat(parts, ignore_index=True)
    out["code_dept"] = out["code_dept"].astype(str)
    out = out.drop_duplicates(["code_dept", "annee"], keep="last")
    print(
        f"Pauvrete consolidee : {len(out)} lignes | annees={sorted(out['annee'].unique().tolist())} "
        f"| histo={len(histo)} | courant={len(courant)}"
    )
    return out.sort_values(["code_dept", "annee"]).reset_index(drop=True)


def build_entreprises(pop: pd.DataFrame) -> pd.DataFrame:
    cache_csv = os.path.join(RAW, "entreprises", "side_creations_dept.csv")
    if os.path.exists(cache_csv) and os.path.getsize(cache_csv) > 0:
        print(f"[CACHE] {cache_csv}")
        crea = pd.read_csv(cache_csv, dtype={"code_dept": str})
    else:
        obs = melodi_fetch(
            "DS_SIDE_CREA_DEP_REG_NAT",
            {"SIDE_MEASURE": "BURE", "ACTIVITY": "_T", "LEGAL_FORM": "_T"},
        )
        rows = []
        for o in obs:
            dims = o.get("dimensions") or {}
            code = geo_to_dept(dims.get("GEO", ""))
            if code is None:
                continue
            val = (o.get("measures") or {}).get("OBS_VALUE_NIVEAU", {}).get("value")
            if val is None:
                continue
            try:
                annee = int(str(dims["TIME_PERIOD"])[:4])
                crea_n = float(val)
            except (KeyError, TypeError, ValueError):
                continue
            if crea_n <= 0:
                continue
            rows.append({"code_dept": code, "annee": annee, "creations": crea_n})
        crea = pd.DataFrame(rows).drop_duplicates(["code_dept", "annee"])
        os.makedirs(os.path.dirname(cache_csv), exist_ok=True)
        crea.to_csv(cache_csv, index=False)
        print(f"[RAW ] archive {cache_csv} ({len(crea)} lignes)")

    merged = crea.merge(pop, on=["code_dept", "annee"], how="left")
    if merged["population"].isna().any():
        pop_idx = pop.set_index(["code_dept", "annee"])["population"]

        def _pop_fallback(row):
            if pd.notna(row["population"]) and row["population"] > 0:
                return row["population"]
            for delta in (0, -1, 1, -2, 2):
                key = (row["code_dept"], int(row["annee"]) + delta)
                if key in pop_idx.index:
                    return float(pop_idx.loc[key])
            return np.nan

        merged["population"] = merged.apply(_pop_fallback, axis=1)
    merged = merged.dropna(subset=["population"])
    merged = merged[merged["population"] > 0]
    merged["creations_entreprises_10k"] = (
        merged["creations"] / merged["population"] * 10_000
    ).round(1)
    merged = merged[merged["creations_entreprises_10k"] > 0]
    out = merged[["code_dept", "annee", "creations_entreprises_10k"]]
    return out.drop_duplicates(["code_dept", "annee"]).sort_values(
        ["code_dept", "annee"]
    ).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def write_bronze(name: str, df: pd.DataFrame, cols: list[str], sanity_key: str | None = None) -> None:
    """Ecrit un CSV Bronze au contrat canonique + validations de schema."""
    os.makedirs(BRONZE, exist_ok=True)
    contract = BRONZE_SCHEMAS.get(name, cols)
    if list(contract) != list(cols):
        # Le contrat partage prime ; signaler tout ecart volontaire
        cols = list(contract)
    if sanity_key:
        assert_realistic(sanity_key, df)
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise ValueError(f"Bronze {name}: colonnes absentes {missing}")
    out = df.reindex(columns=cols).copy()
    if "code_dept" in out.columns:
        out["code_dept"] = out["code_dept"].astype(str).str.strip()
        bad = ~out["code_dept"].isin(METRO_DEPTS)
        if bad.any():
            raise ValueError(f"Bronze {name}: {int(bad.sum())} codes dept hors metro")
    if out.duplicated().any():
        n = int(out.duplicated().sum())
        print(f"[BRONZE WARN] {name}: {n} lignes strictement dupliquees (conservees jusqu'au Silver)")
    path = os.path.join(BRONZE, name)
    out.to_csv(path, index=False)
    print(f"[BRONZE] {name}: {len(out)} lignes | cols={cols} -> {path}")


def write_bronze_manifest(written: dict[str, int]) -> None:
    from datetime import datetime, timezone
    payload = {
        "layer": "BRONZE",
        "role": "Contrat normalise (sources RAW immuables dans data/raw/)",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "schemas": BRONZE_SCHEMAS,
        "tables": {
            name: {"rows": n, "columns": BRONZE_SCHEMAS.get(name, [])}
            for name, n in written.items()
        },
    }
    path = os.path.join(BRONZE, "bronze_manifest.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    print(f"[BRONZE] manifeste -> {path}")


def main():
    os.makedirs(RAW, exist_ok=True)
    os.makedirs(BRONZE, exist_ok=True)
    print("Catalogues de reference :")
    for k, v in CATALOGUES.items():
        print(f"  - {k}: {v}")

    written: dict[str, int] = {}

    print("\n== Elections ==")
    elec = build_elections()
    write_bronze(
        "elections_presidentielles_t1.csv",
        elec,
        ["annee", "code_dept", "inscrits", "pct_EXG", "pct_GAU", "pct_CEN", "pct_DRO", "pct_EXD"],
        sanity_key="elections",
    )
    written["elections_presidentielles_t1.csv"] = len(elec)

    print("\n== Chomage ==")
    chom = build_chomage()
    write_bronze(
        "chomage_localise_trim.csv",
        chom,
        ["code_dept", "annee", "trimestre", "taux_chomage"],
        sanity_key="chomage",
    )
    written["chomage_localise_trim.csv"] = len(chom)

    print("\n== Emploi ==")
    emp = build_emploi()
    write_bronze(
        "emploi_salarie_trim.csv",
        emp,
        ["code_dept", "annee", "trimestre", "emploi_total"],
        sanity_key="emploi",
    )
    written["emploi_salarie_trim.csv"] = len(emp)

    print("\n== Population (INSEE XLSX) ==")
    pop = build_population()
    write_bronze(
        "population_dept.csv", pop, ["code_dept", "annee", "population"],
        sanity_key="population",
    )
    written["population_dept.csv"] = len(pop)

    print("\n== Pauvrete (Melodi Filosofi) ==")
    pauv = build_pauvrete()
    write_bronze(
        "pauvrete_dept.csv", pauv, ["code_dept", "annee", "taux_pauvrete"],
        sanity_key="pauvrete",
    )
    written["pauvrete_dept.csv"] = len(pauv)

    print("\n== Entreprises (Melodi SIDE / 10k hab) ==")
    ent = build_entreprises(pop)
    write_bronze(
        "entreprises_dept.csv",
        ent,
        ["code_dept", "annee", "creations_entreprises_10k"],
        sanity_key="entreprises",
    )
    written["entreprises_dept.csv"] = len(ent)

    write_bronze_manifest(written)
    print("\nTermine. Couche BRONZE normalisee + controles SANITY OK.")
    print("Donnees brutes conservees dans data/raw/ (tracabilite).")
    print("ATTENTION: ne pas relancer etl/00_demo_data.py apres --real "
          "(ecrase le bronze reel).")


if __name__ == "__main__":
    main()
