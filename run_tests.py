"""Runner oficial y fail-closed de la suite de Pechy Players."""

import os
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REAL_DB = (ROOT / "pechy.db").resolve()


def configure_test_environment(directory):
    test_db = (Path(directory) / "suite.db").resolve()
    if test_db == REAL_DB:
        raise RuntimeError("El runner se negó a utilizar pechy.db.")
    os.environ["PECHY_TESTING"] = "1"
    os.environ["PECHY_DB"] = str(test_db)
    return test_db


def main():
    with tempfile.TemporaryDirectory(prefix="pechy-tests-") as directory:
        configure_test_environment(directory)

        suite = unittest.defaultTestLoader.discover(
            start_dir=str(ROOT / "tests"),
            pattern="test_*.py",
            top_level_dir=str(ROOT),
        )
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
