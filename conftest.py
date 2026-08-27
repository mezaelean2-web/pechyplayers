"""Bootstrap global fail-closed para cualquier ejecucion directa de pytest."""

import os
from pathlib import Path

from tests._bootstrap import (
    REAL_DB,
    TEST_DB,
    UnsafeTestSqliteConnectionError,
    guarded_test_sqlite_connect,
)


if os.environ.get("PECHY_TESTING") != "1":
    raise RuntimeError("pytest debe activar PECHY_TESTING antes de coleccionar tests.")
if Path(os.environ["PECHY_DB"]).expanduser().resolve() != TEST_DB:
    raise RuntimeError("pytest y tests._bootstrap resolvieron bases diferentes.")
if TEST_DB == REAL_DB:
    raise RuntimeError("pytest se nego a utilizar pechy.db.")
