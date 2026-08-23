try:
    from tests._bootstrap import ROOT, TEST_DB
except ModuleNotFoundError:
    from _bootstrap import ROOT, TEST_DB

import hashlib
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import database
import run_tests
import bold_recharges
import reseller_accounts
import resellers


class DatabaseIsolationTest(unittest.TestCase):
    def test_bootstrap_expone_una_sola_raiz_importable(self):
        root_entry = str(ROOT)
        self.assertEqual(sys.path.count(root_entry), 1)
        self.assertIs(database, __import__("database"))

    def test_bootstrap_usa_base_temporal_fuera_del_repositorio(self):
        self.assertTrue(database.testing_activo())
        self.assertEqual(Path(database.DB).resolve(), TEST_DB)
        self.assertNotEqual(Path(database.DB).resolve(), database.REAL_DB)

    def test_modo_test_rechaza_base_real_antes_de_sqlite_y_preserva_hash(self):
        hash_antes = hashlib.sha256(database.REAL_DB.read_bytes()).hexdigest()
        original = database.DB
        database.DB = str(database.REAL_DB)
        try:
            with mock.patch.object(
                database.sqlite3, "connect",
                side_effect=AssertionError("sqlite3.connect no debe ejecutarse"),
            ) as conectar_sqlite:
                with self.assertRaises(database.UnsafeTestDatabaseError):
                    database.inicializar_db()
                conectar_sqlite.assert_not_called()
        finally:
            database.DB = original
        hash_despues = hashlib.sha256(database.REAL_DB.read_bytes()).hexdigest()
        self.assertEqual(hash_antes, hash_despues)

    def test_modo_test_sin_pechy_db_falla_antes_de_sqlite_y_wal(self):
        original_env = os.environ.pop("PECHY_DB", None)
        original_db = database.DB
        database.DB = str(database.REAL_DB)
        try:
            with mock.patch.object(database.sqlite3, "connect") as conectar_sqlite:
                with self.assertRaises(database.UnsafeTestDatabaseError):
                    database.conectar()
                conectar_sqlite.assert_not_called()
        finally:
            database.DB = original_db
            if original_env is not None:
                os.environ["PECHY_DB"] = original_env

    def test_runner_configura_una_ruta_temporal_explicita(self):
        entorno_anterior = {
            "PECHY_TESTING": os.environ.get("PECHY_TESTING"),
            "PECHY_DB": os.environ.get("PECHY_DB"),
        }
        with tempfile.TemporaryDirectory() as directory:
            ruta = run_tests.configure_test_environment(directory)
            self.assertEqual(os.environ["PECHY_TESTING"], "1")
            self.assertEqual(Path(os.environ["PECHY_DB"]).resolve(), ruta)
            self.assertNotEqual(ruta, database.REAL_DB)
        for nombre, valor in entorno_anterior.items():
            if valor is None:
                os.environ.pop(nombre, None)
            else:
                os.environ[nombre] = valor

    def test_app_backup_tambien_rechaza_la_base_real(self):
        import app_backup

        original = database.DB
        database.DB = str(database.REAL_DB)
        try:
            with mock.patch.object(database.sqlite3, "connect") as conectar_sqlite:
                with self.assertRaises(database.UnsafeTestDatabaseError):
                    app_backup.conectar()
                conectar_sqlite.assert_not_called()
        finally:
            database.DB = original

    def test_inicializadores_rechazan_la_base_real_antes_de_sqlite(self):
        inicializadores = (
            database.inicializar_db,
            reseller_accounts.inicializar_esquema,
            resellers.inicializar_revendedores,
            bold_recharges.initialize,
        )
        original = database.DB
        database.DB = str(database.REAL_DB)
        try:
            for inicializador in inicializadores:
                with self.subTest(inicializador=inicializador.__module__):
                    with mock.patch.object(database.sqlite3, "connect") as conectar_sqlite:
                        with self.assertRaises(database.UnsafeTestDatabaseError):
                            inicializador()
                        conectar_sqlite.assert_not_called()
        finally:
            database.DB = original

    def test_modo_test_permite_sqlite_temporal(self):
        descriptor, ruta = tempfile.mkstemp(suffix=".db")
        os.close(descriptor)
        original = database.DB
        database.DB = ruta
        try:
            conn = database.conectar()
            conn.execute("CREATE TABLE prueba(id INTEGER PRIMARY KEY)")
            conn.commit()
            conn.close()
        finally:
            database.DB = original
            os.remove(ruta)


if __name__ == "__main__":
    unittest.main()
