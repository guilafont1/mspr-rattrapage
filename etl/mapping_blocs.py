# -*- coding: utf-8 -*-
"""
Correspondance candidat -> bloc politique (presidentielles T1).

Blocs du contrat BRONZE / GOLD :
  EXG  extreme gauche
  GAU  gauche (inclut ecologistes et communistes)
  CEN  centre
  DRO  droite
  EXD  extreme droite

Ce fichier est volontairement MODIFIABLE : les frontieres entre blocs
(ex. Jadot, Dupont-Aignan, Lassalle, Melenchon) sont des choix pedagogiques
documentes, pas une verite institutionnelle. Ajuster ici puis relancer
`python etl/01_download.py` (ou `run_pipeline.py --real`).

Les cles sont des noms de famille NORMALISES (majuscules, sans accents,
sans particule "DE "). Le matching ignore la casse et les accents du fichier
source Ministere de l'Interieur.
"""
from __future__ import annotations

import unicodedata

BLOCS = ("EXG", "GAU", "CEN", "DRO", "EXD")

# --- Classification par scrutin ------------------------------------------------
# Sources des listes de candidats : fichiers officiels data.gouv.fr
# (Ministere de l'Interieur), onglets / fichiers departementaux T1.

MAPPING_PAR_ANNEE = {
    2002: {
        # EXG
        "GLUCKSTEIN": "EXG",      # Parti des travailleurs
        "LAGUILLER": "EXG",       # LO
        "BESANCENOT": "EXG",      # LCR
        # GAU
        "TAUBIRA": "GAU",         # PRG
        "MAMERE": "GAU",          # Les Verts
        "JOSPIN": "GAU",          # PS
        "HUE": "GAU",             # PCF
        "CHEVENEMENT": "GAU",     # Pôle républicain (souverainiste de gauche)
        # CEN
        "LEPAGE": "CEN",          # Cap21
        "BAYROU": "CEN",          # UDF
        # DRO
        "CHIRAC": "DRO",          # RPR / UMP
        "SAINT-JOSSE": "DRO",     # CPNT (ruraliste)
        "BOUTIN": "DRO",          # Forum des républicains sociaux
        "MADELIN": "DRO",         # DL
        # EXD
        "MEGRET": "EXD",          # MNR
        "LE PEN": "EXD",          # FN
    },
    2007: {
        "BESANCENOT": "EXG",      # LCR
        "SCHIVARDI": "EXG",       # PT
        "LAGUILLER": "EXG",       # LO
        "BUFFET": "GAU",          # PCF
        "BOVE": "GAU",            # altermondialiste
        "VOYNET": "GAU",          # Les Verts
        "ROYAL": "GAU",           # PS
        "BAYROU": "CEN",          # UDF / Modem
        "NIHOUS": "DRO",          # CPNT
        "VILLIERS": "DRO",        # MPF (souverainiste de droite)
        "SARKOZY": "DRO",         # UMP
        "LE PEN": "EXD",          # FN
    },
    2012: {
        "POUTOU": "EXG",          # NPA
        "ARTHAUD": "EXG",         # LO
        "MELENCHON": "GAU",       # FG
        "JOLY": "GAU",            # EELV
        "HOLLANDE": "GAU",        # PS
        "BAYROU": "CEN",          # Modem
        "CHEMINADE": "CEN",       # Solidarité & Progrès (classé centre par défaut)
        "SARKOZY": "DRO",         # UMP
        "DUPONT-AIGNAN": "DRO",   # DLF (souverainiste ; parfois EXD)
        "LE PEN": "EXD",          # FN
    },
    2017: {
        "POUTOU": "EXG",
        "ARTHAUD": "EXG",
        "MELENCHON": "GAU",       # FI
        "HAMON": "GAU",           # PS
        "MACRON": "CEN",          # EM
        "LASSALLE": "CEN",        # Résistons !
        "ASSELINEAU": "CEN",      # UPR (souverainiste ; choix pédagogique CEN)
        "CHEMINADE": "CEN",
        "FILLON": "DRO",          # LR
        "DUPONT-AIGNAN": "DRO",
        "LE PEN": "EXD",          # FN
    },
    2022: {
        "ARTHAUD": "EXG",
        "POUTOU": "EXG",
        "ROUSSEL": "GAU",         # PCF
        "MELENCHON": "GAU",       # LFI
        "HIDALGO": "GAU",         # PS
        "JADOT": "GAU",           # EELV (parfois CEN)
        "MACRON": "CEN",
        "LASSALLE": "CEN",
        "PECRESSE": "DRO",        # LR
        "DUPONT-AIGNAN": "DRO",
        "LE PEN": "EXD",          # RN
        "ZEMMOUR": "EXD",         # Reconquête
    },
}


def normaliser_nom(nom: str) -> str:
    """Normalise un nom de candidat pour le matching (majuscules, sans accents)."""
    if nom is None:
        return ""
    s = str(nom).strip().upper()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    # Particules / bruits frequents dans les fichiers MI
    for prefix in ("DE ", "D'", "D’"):
        if s.startswith(prefix):
            s = s[len(prefix):]
    s = " ".join(s.split())
    return s


def bloc_pour(annee: int, nom: str) -> str | None:
    """Retourne le bloc (EXG..EXD) ou None si candidat inconnu."""
    table = MAPPING_PAR_ANNEE.get(int(annee), {})
    return table.get(normaliser_nom(nom))


def assert_mapping_complet(annee: int, noms: list[str]) -> list[str]:
    """Retourne la liste des noms non mappees (doit etre vide apres controle)."""
    return [n for n in noms if bloc_pour(annee, n) is None]
