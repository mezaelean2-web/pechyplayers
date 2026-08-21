import os
import sqlite3
import tempfile
import unittest

import app as app_module
import database
import resellers
import wallets


class WalletsResellerTest(unittest.TestCase):
    def setUp(self):
        descriptor, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(descriptor)
        self.original_db = database.DB
        database.DB = self.db_path
        conn = sqlite3.connect(self.db_path)
        conn.execute("""CREATE TABLE productos (
            id INTEGER PRIMARY KEY, nombre TEXT NOT NULL, imagen TEXT NOT NULL DEFAULT '',
            plan TEXT NOT NULL, precio TEXT NOT NULL, oferta_precio TEXT,
            oferta_activa INTEGER DEFAULT 0, destacado INTEGER DEFAULT 0,
            visible INTEGER DEFAULT 1, orden INTEGER DEFAULT 999,
            categoria TEXT DEFAULT 'Streaming', orden_categoria INTEGER DEFAULT 999,
            estado TEXT DEFAULT 'disponible')""")
        conn.commit()
        conn.close()
        resellers.inicializar_revendedores()
        self.reseller_id = resellers.crear_revendedor(
            "José Santo", "jose@example.com", "+57 300 123 4567",
            "Santo TV", "ClaveSegura123"
        )
        app_module.app.config.update(TESTING=True, SECRET_KEY="wallet-test")
        self.admin = app_module.app.test_client()
        with self.admin.session_transaction() as session:
            session["admin"] = True
            session["admin_usuario"] = "admin-prueba"
            session["csrf_revendedores"] = "csrf-wallet"
        self.headers = {"X-CSRF-Token": "csrf-wallet"}

    def tearDown(self):
        database.DB = self.original_db
        os.remove(self.db_path)

    def movimientos(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        filas = conn.execute("SELECT * FROM reseller_wallet_transactions ORDER BY id").fetchall()
        conn.close()
        return [dict(fila) for fila in filas]

    def test_wallet_cero_unica_y_creacion_futura(self):
        wallet = wallets.asegurar_wallet(self.reseller_id)
        segunda = wallets.asegurar_wallet(self.reseller_id)
        self.assertEqual(wallet["saldo"], 0)
        self.assertEqual(wallet["id"], segunda["id"])
        conn = sqlite3.connect(self.db_path)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM reseller_wallets WHERE revendedor_id=?", (self.reseller_id,)).fetchone()[0], 1)
        conn.close()

    def test_creditos_debito_y_ledger_consistente(self):
        primero = wallets.apply_wallet_transaction(self.reseller_id, "manual_credit", 50000, "Transferencia", actor="admin")
        segundo = wallets.apply_wallet_transaction(self.reseller_id, "manual_credit", "20000", "Efectivo", actor="admin")
        debito = wallets.apply_wallet_transaction(self.reseller_id, "manual_debit", 15000, "Ajuste acordado", actor="admin")
        self.assertEqual((primero["saldo_anterior"], primero["saldo_posterior"]), (0, 50000))
        self.assertEqual((segundo["saldo_anterior"], segundo["saldo_posterior"]), (50000, 70000))
        self.assertEqual((debito["monto"], debito["saldo_anterior"], debito["saldo_posterior"]), (15000, 70000, 55000))
        self.assertEqual(wallets.obtener_saldo(self.reseller_id), 55000)
        self.assertEqual([item["monto"] for item in self.movimientos()], [50000, 20000, 15000])

    def test_validaciones_no_cambian_saldo_ni_ledger(self):
        wallets.apply_wallet_transaction(self.reseller_id, "manual_credit", 20000, "Base")
        casos = [
            ("manual_debit", 30000, "Excede", "Saldo insuficiente"),
            ("manual_credit", 0, "Cero", "mayor que cero"),
            ("manual_credit", -1, "Negativo", "mayor que cero"),
            ("manual_credit", "abc", "Inválido", "entero positivo"),
            ("manual_credit", 100, " ", "motivo"),
        ]
        for tipo, monto, motivo, texto in casos:
            with self.subTest(monto=monto, motivo=motivo):
                with self.assertRaisesRegex(ValueError, texto):
                    wallets.apply_wallet_transaction(self.reseller_id, tipo, monto, motivo)
        self.assertEqual(wallets.obtener_saldo(self.reseller_id), 20000)
        self.assertEqual(len(self.movimientos()), 1)
        with self.assertRaises(LookupError):
            wallets.apply_wallet_transaction(9999, "manual_credit", 1000, "No existe")

    def test_idempotencia_no_duplica_credito(self):
        primero = wallets.apply_wallet_transaction(
            self.reseller_id, "recharge", 50000, "Futuro Bold",
            provider="bold", external_reference="evt-1", idempotency_key="bold:evt-1"
        )
        segundo = wallets.apply_wallet_transaction(
            self.reseller_id, "recharge", 50000, "Futuro Bold",
            provider="bold", external_reference="evt-1", idempotency_key="bold:evt-1"
        )
        self.assertFalse(primero["duplicado"])
        self.assertTrue(segundo["duplicado"])
        self.assertEqual(wallets.obtener_saldo(self.reseller_id), 50000)
        self.assertEqual(len(self.movimientos()), 1)

    def test_rollback_si_falla_insert_o_actualizacion(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("""CREATE TRIGGER falla_movimiento BEFORE INSERT ON reseller_wallet_transactions
                        BEGIN SELECT RAISE(ABORT, 'fallo ledger'); END""")
        conn.commit(); conn.close()
        with self.assertRaises(sqlite3.IntegrityError):
            wallets.apply_wallet_transaction(self.reseller_id, "manual_credit", 1000, "Falla")
        self.assertEqual(wallets.obtener_saldo(self.reseller_id), 0)
        conn = sqlite3.connect(self.db_path); conn.execute("DROP TRIGGER falla_movimiento")
        conn.execute("""CREATE TRIGGER falla_wallet BEFORE UPDATE ON reseller_wallets
                        BEGIN SELECT RAISE(ABORT, 'fallo wallet'); END""")
        conn.commit(); conn.close()
        with self.assertRaises(sqlite3.IntegrityError):
            wallets.apply_wallet_transaction(self.reseller_id, "manual_credit", 1000, "Falla")
        self.assertEqual(wallets.obtener_saldo(self.reseller_id), 0)
        self.assertEqual(len(self.movimientos()), 0)

    def test_rutas_admin_csrf_resumen_filtros_e_historial(self):
        anonimo = app_module.app.test_client()
        self.assertEqual(anonimo.get("/admin/saldos").status_code, 302)
        self.assertEqual(anonimo.get(f"/admin/saldos/{self.reseller_id}/control").status_code, 401)
        self.assertEqual(self.admin.post(f"/admin/saldos/{self.reseller_id}/credito", json={"monto": 1000, "motivo": "X"}).status_code, 403)
        credito = self.admin.post(f"/admin/saldos/{self.reseller_id}/credito", json={"monto": 50000, "motivo": "Transferencia"}, headers=self.headers)
        self.assertEqual(credito.status_code, 200)
        pagina = self.admin.get("/admin/saldos").get_data(as_text=True)
        self.assertIn("$50.000 COP", pagina)
        self.assertIn('data-wallet-filter="with"', pagina)
        self.assertIn('data-wallet-filter="bloqueado"', pagina)
        self.assertIn("Santo TV", pagina)
        control = self.admin.get(f"/admin/saldos/{self.reseller_id}/control").get_data(as_text=True)
        self.assertIn("Transferencia", control)
        self.assertIn("Crédito manual", control)
        self.assertEqual(self.admin.post("/admin/saldos/9999/credito", json={"monto": 1000, "motivo": "X"}, headers=self.headers).status_code, 404)

    def test_reseller_ve_saldo_solo_lectura_y_bloqueo_lo_conserva(self):
        wallets.apply_wallet_transaction(self.reseller_id, "manual_credit", 50000, "Saldo visible")
        reseller = app_module.app.test_client()
        with reseller.session_transaction() as session:
            session["reseller_id"] = self.reseller_id
            session["reseller_auth_version"] = 1
        cuenta = reseller.get("/revendedores/cuenta").get_data(as_text=True)
        self.assertIn("Saldo disponible", cuenta)
        self.assertIn("$50.000 COP", cuenta)
        respuesta = reseller.post("/revendedores/cuenta", data={"accion": "wallet", "csrf_token": "incorrecto"})
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(wallets.obtener_saldo(self.reseller_id), 50000)
        resellers.cambiar_estado_revendedor(self.reseller_id, "bloqueado")
        self.assertEqual(wallets.obtener_saldo(self.reseller_id), 50000)
        self.assertEqual(len(self.movimientos()), 1)

    def test_historial_mas_reciente_primero_y_resumen_real(self):
        wallets.apply_wallet_transaction(self.reseller_id, "manual_credit", 50000, "Primero")
        wallets.apply_wallet_transaction(self.reseller_id, "manual_debit", 10000, "Segundo")
        resumen = wallets.resumen_saldos()
        self.assertEqual(resumen["saldo_total"], 40000)
        self.assertEqual(resumen["con_saldo"], 1)
        self.assertGreaterEqual(resumen["creditos_hoy"], 50000)
        self.assertGreaterEqual(resumen["debitos_hoy"], 10000)
        _, _, movimientos = wallets.obtener_control_saldo(self.reseller_id)
        self.assertEqual([item["descripcion"] for item in movimientos], ["Segundo", "Primero"])


if __name__ == "__main__":
    unittest.main()
