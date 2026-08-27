"""Activa aislamiento antes de importar cualquier módulo productivo."""

import atexit
import os
import sqlite3
import sys
import tempfile
from pathlib import Path
from urllib.parse import unquote


ROOT = Path(__file__).resolve().parents[1]
_root_entry = str(ROOT)
if _root_entry not in sys.path:
    sys.path.insert(0, _root_entry)

os.environ["PECHY_TESTING"] = "1"

REAL_DB = (ROOT / "pechy.db").resolve()
_configured_db = os.environ.get("PECHY_DB", "").strip()
if _configured_db:
    TEST_DB = Path(_configured_db).expanduser().resolve()
    if TEST_DB == REAL_DB:
        raise RuntimeError("El bootstrap de tests rechazó pechy.db.")
else:
    _directory = tempfile.TemporaryDirectory(prefix="pechy-tests-")
    atexit.register(_directory.cleanup)
    TEST_DB = (Path(_directory.name) / "suite.db").resolve()
    os.environ["PECHY_DB"] = str(TEST_DB)


class UnsafeTestSqliteConnectionError(RuntimeError):
    """Un test intento abrir directamente la base SQLite de produccion."""


def _resolved_sqlite_path(database, *, uri=False):
    try:
        value = os.fspath(database)
    except TypeError:
        return None
    if isinstance(value, bytes):
        value = os.fsdecode(value)
    if value == ":memory:":
        return None
    if uri or value.startswith("file:"):
        if not value.startswith("file:"):
            return None
        value = unquote(value[5:].split("?", 1)[0])
        if value in {"", ":memory:"}:
            return None
        if os.name == "nt" and len(value) >= 3 and value[0] == "/" and value[2] == ":":
            value = value[1:]
    return Path(value).expanduser().resolve()


_original_sqlite_connect = sqlite3.connect


def guarded_test_sqlite_connect(database, *args, **kwargs):
    resolved = _resolved_sqlite_path(database, uri=bool(kwargs.get("uri")))
    if resolved == REAL_DB:
        raise UnsafeTestSqliteConnectionError(
            f"La infraestructura de tests rechazo la base real: {REAL_DB}"
        )
    return _original_sqlite_connect(database, *args, **kwargs)


guarded_test_sqlite_connect._pechy_test_guard = True
if not getattr(sqlite3.connect, "_pechy_test_guard", False):
    sqlite3.connect = guarded_test_sqlite_connect


def subprocess_test_environment(extra=None):
    """Entorno explicito para futuros subprocess Python de la suite."""
    environment = os.environ.copy()
    if extra:
        environment.update(extra)
    environment["PECHY_TESTING"] = "1"
    environment["PECHY_DB"] = str(TEST_DB)
    return environment
