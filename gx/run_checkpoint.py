# -*- coding: utf-8 -*-
"""Compatibilité : la suite DQM a été déplacée vers dqm/run_checkpoint.py.

Ce wrapper conserve l'ancien chemin gx/ pour les scripts / docs obsolètes.
"""
from __future__ import annotations

import runpy
import sys
from pathlib import Path

print(
    "NOTE: gx/ est un alias. Suite DQM = dqm/run_checkpoint.py "
    "(outil interne, pattern expectations — pas Great Expectations).",
    file=sys.stderr,
)
runpy.run_path(str(Path(__file__).resolve().parent.parent / "dqm" / "run_checkpoint.py"), run_name="__main__")
