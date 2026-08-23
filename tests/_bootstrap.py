"""Activa aislamiento antes de importar cualquier módulo productivo."""

import atexit
import os
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
_root_entry = str(ROOT)
if _root_entry not in sys.path:
    sys.path.insert(0, _root_entry)

os.environ["PECHY_TESTING"] = "1"

_real_db = (ROOT / "pechy.db").resolve()
_configured_db = os.environ.get("PECHY_DB", "").strip()
if _configured_db:
    TEST_DB = Path(_configured_db).expanduser().resolve()
    if TEST_DB == _real_db:
        raise RuntimeError("El bootstrap de tests rechazó pechy.db.")
else:
    _directory = tempfile.TemporaryDirectory(prefix="pechy-tests-")
    atexit.register(_directory.cleanup)
    TEST_DB = (Path(_directory.name) / "suite.db").resolve()
    os.environ["PECHY_DB"] = str(TEST_DB)
