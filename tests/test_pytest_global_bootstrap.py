"""Regresion: un test futuro sin import explicito del bootstrap sigue aislado."""

import os
from pathlib import Path

import database


def test_import_productivo_directo_ya_resuelve_base_temporal():
    assert os.environ.get("PECHY_TESTING") == "1"
    assert os.environ.get("PECHY_DB")
    assert Path(os.environ["PECHY_DB"]).expanduser().resolve() != database.REAL_DB
    assert Path(database.DB).expanduser().resolve() != database.REAL_DB
