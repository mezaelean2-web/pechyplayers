try:
    from tests._bootstrap import TEST_DB
except ModuleNotFoundError:
    from _bootstrap import TEST_DB

import json
import os
import tempfile
import threading
import unittest
from datetime import datetime
from unittest import mock

import database
import reseller_accounts
import resellers
import wallets


class ResellerPurchasePeriodsTest(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.original_db = database.DB
        database.DB = self.path
        conn = database.conectar()
        conn.executescript("""
          PRAGMA foreign_keys=ON;
          CREATE TABLE productos(id INTEGER PRIMARY KEY AUTOINCREMENT,nombre TEXT NOT NULL,imagen TEXT DEFAULT '',plan TEXT NOT NULL,precio TEXT NOT NULL,estado TEXT DEFAULT 'disponible');
          CREATE TABLE nube_clientes(id INTEGER PRIMARY KEY AUTOINCREMENT,nombre TEXT,telefono TEXT,telefono_normalizado TEXT UNIQUE,fecha_actualizacion TEXT DEFAULT CURRENT_TIMESTAMP);
          CREATE TABLE nube_cuentas(id INTEGER PRIMARY KEY AUTOINCREMENT,plataforma TEXT NOT NULL,correo TEXT,contrasena TEXT DEFAULT '',pin TEXT DEFAULT '',cliente_id INTEGER,nombre_cliente TEXT DEFAULT '',telefono TEXT DEFAULT '',fecha_entrega TEXT DEFAULT '',dias_cuenta INTEGER DEFAULT 0,fecha_vencimiento TEXT DEFAULT '',estado TEXT DEFAULT 'disponible',modalidad TEXT DEFAULT 'cuenta_completa',fecha_creacion TEXT DEFAULT CURRENT_TIMESTAMP,fecha_actualizacion TEXT DEFAULT CURRENT_TIMESTAMP);
          CREATE TABLE nube_perfiles(id INTEGER PRIMARY KEY AUTOINCREMENT,cuenta_id INTEGER NOT NULL,nombre_perfil TEXT DEFAULT '',pin TEXT DEFAULT '',cliente_id INTEGER,nombre_cliente TEXT DEFAULT '',telefono TEXT DEFAULT '',fecha_entrega TEXT DEFAULT '',dias_cuenta INTEGER DEFAULT 0,fecha_vencimiento TEXT DEFAULT '',estado TEXT DEFAULT 'disponible',fecha_actualizacion TEXT DEFAULT CURRENT_TIMESTAMP,FOREIGN KEY(cuenta_id) REFERENCES nube_cuentas(id));
          CREATE TABLE nube_movimientos(id INTEGER PRIMARY KEY AUTOINCREMENT,cuenta_id INTEGER NOT NULL,tipo TEXT NOT NULL,descripcion TEXT,estado_anterior TEXT,estado_nuevo TEXT,cliente_nombre TEXT,fecha TEXT DEFAULT CURRENT_TIMESTAMP);
        """)
        conn.execute("INSERT INTO productos(nombre,plan,precio) VALUES ('Netflix','Cuenta','99999')")
        self.plan = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.commit()
        conn.close()
        resellers.inicializar_revendedores()
        reseller_accounts.inicializar_esquema()
        self.reseller = resellers.crear_revendedor(
            "Períodos", "periodos@example.com", "3001002000", "Períodos", "ClaveSegura123"
        )
        wallets.apply_wallet_transaction(self.reseller, "manual_credit", 500000, "Prueba")
        self._insertar_cuenta("caida")
        reseller_accounts.guardar_regla_inventario_plan(self.plan, "Netflix", "cuenta", 30)
        resellers.guardar_precio_general(self.plan, 8000)

    def tearDown(self):
        database.DB = self.original_db
        try:
            os.remove(self.path)
        except PermissionError:
            pass

    def _insertar_cuenta(self, estado="disponible"):
        conn = database.conectar()
        cur = conn.execute(
            "INSERT INTO nube_cuentas(plataforma,correo,modalidad,estado,duracion_unidad_dias) VALUES ('Netflix',?,'cuenta_completa',?,30)",
            (f"{os.urandom(4).hex()}@example.com", estado),
        )
        cuenta_id = cur.lastrowid
        conn.commit()
        conn.close()
        return cuenta_id

    def _comprar(self, clave, periodos):
        return reseller_accounts.comprar_plan_reseller(
            self.reseller, self.plan, clave,
            datetime(2026, 8, 21, 10, 0, tzinfo=reseller_accounts.ZONA_HORARIA),
            cantidad_periodos=periodos,
        )

    def _estado(self):
        conn = database.conectar()
        estado = {
            "saldo": conn.execute("SELECT saldo FROM reseller_wallets WHERE revendedor_id=?", (self.reseller,)).fetchone()[0],
            "purchases": conn.execute("SELECT COUNT(*) FROM reseller_purchases").fetchone()[0],
            "events": conn.execute("SELECT COUNT(*) FROM reseller_purchase_events").fetchone()[0],
            "debits": conn.execute("SELECT COUNT(*) FROM reseller_wallet_transactions WHERE tipo='purchase'").fetchone()[0],
            "operations": conn.execute("SELECT COUNT(*) FROM reseller_purchase_operations").fetchone()[0],
            "available": conn.execute("SELECT COUNT(*) FROM nube_cuentas WHERE estado='disponible'").fetchone()[0],
        }
        conn.close()
        return estado

    def test_uno_dos_y_tres_periodos_calculan_totales_y_consumen_una_unidad(self):
        for periodos in (1, 2, 3):
            with self.subTest(periodos=periodos):
                cuenta_id = self._insertar_cuenta()
                saldo_antes = wallets.obtener_saldo(self.reseller)
                resultado = self._comprar(f"periodos-{periodos}", periodos)
                self.assertEqual(resultado["precio_unitario"], 8000)
                self.assertEqual(resultado["cantidad_periodos"], periodos)
                self.assertEqual(resultado["precio_total"], 8000 * periodos)
                self.assertEqual(resultado["precio_pagado"], 8000 * periodos)
                self.assertEqual(resultado["duracion_base_dias"], 30)
                self.assertEqual(resultado["duracion_total_dias"], 30 * periodos)
                self.assertEqual(resultado["saldo_restante"], saldo_antes - 8000 * periodos)
                self.assertTrue(resultado["fecha_vencimiento"].startswith({1: "2026-09-20", 2: "2026-10-20", 3: "2026-11-19"}[periodos]))
                conn = database.conectar()
                purchase = conn.execute("SELECT * FROM reseller_purchases WHERE id=?", (resultado["purchase_id"],)).fetchone()
                self.assertEqual(purchase["cuenta_id"], cuenta_id)
                self.assertEqual((purchase["precio_unitario_pagado"], purchase["cantidad_periodos"], purchase["duracion_base_dias"], purchase["dias_contratados"]), (8000, periodos, 30, 30 * periodos))
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM reseller_purchase_events WHERE purchase_id=?", (purchase["id"],)).fetchone()[0], 1)
                self.assertEqual(conn.execute("SELECT monto FROM reseller_wallet_transactions WHERE id=?", (purchase["wallet_transaction_id"],)).fetchone()[0], 8000 * periodos)
                datos = json.loads(conn.execute("SELECT datos_publicos_json FROM reseller_purchase_events WHERE purchase_id=?", (purchase["id"],)).fetchone()[0])
                self.assertEqual((datos["precio_unitario"], datos["precio_total"], datos["duracion_base_dias"], datos["duracion_total_dias"]), (8000, 8000 * periodos, 30, 30 * periodos))
                conn.close()

    def test_cantidad_invalida_se_rechaza_sin_efectos(self):
        for cantidad in (0, -1, 1.5, "3", "x", None, True):
            with self.subTest(cantidad=cantidad):
                antes = self._estado()
                with self.assertRaises(reseller_accounts.ResellerPurchaseError) as error:
                    self._comprar(f"invalid-{cantidad}", cantidad)
                self.assertEqual(error.exception.codigo, "cantidad_periodos_invalida")
                self.assertEqual(self._estado(), antes)

    def test_saldo_insuficiente_para_total_revierte_todo(self):
        cuenta_id = self._insertar_cuenta()
        conn = database.conectar()
        conn.execute("UPDATE reseller_wallets SET saldo=15999 WHERE revendedor_id=?", (self.reseller,))
        conn.commit()
        conn.close()
        with self.assertRaisesRegex(reseller_accounts.ResellerPurchaseError, "Saldo insuficiente"):
            self._comprar("insuficiente-multiple", 2)
        estado = self._estado()
        self.assertEqual((estado["saldo"], estado["purchases"], estado["events"], estado["debits"], estado["operations"]), (15999, 0, 0, 0, 0))
        conn = database.conectar()
        self.assertEqual(conn.execute("SELECT estado FROM nube_cuentas WHERE id=?", (cuenta_id,)).fetchone()[0], "disponible")
        conn.close()

    def test_idempotencia_incluye_cantidad_y_no_duplica_efectos(self):
        self._insertar_cuenta()
        primera = self._comprar("misma-key", 3)
        segunda = self._comprar("misma-key", 3)
        self.assertEqual(primera["purchase_id"], segunda["purchase_id"])
        self.assertTrue(segunda["duplicado"])
        with self.assertRaisesRegex(reseller_accounts.ResellerPurchaseError, "otra operación"):
            self._comprar("misma-key", 2)
        estado = self._estado()
        self.assertEqual((estado["purchases"], estado["events"], estado["debits"], estado["operations"]), (1, 1, 1, 1))

    def test_fallo_despues_del_debito_revierte_toda_la_transaccion(self):
        self._insertar_cuenta()
        original = wallets.apply_wallet_transaction

        def debitar_y_fallar(*args, **kwargs):
            original(*args, **kwargs)
            raise RuntimeError("fallo inyectado después del débito")

        with mock.patch.object(wallets, "apply_wallet_transaction", side_effect=debitar_y_fallar):
            with self.assertRaisesRegex(RuntimeError, "después del débito"):
                self._comprar("rollback-wallet", 2)
        self.assertEqual(self._estado(), {"saldo": 500000, "purchases": 0, "events": 0, "debits": 0, "operations": 0, "available": 1})

    def test_fallos_antes_despues_evento_y_antes_completar_revierten_todo(self):
        for etapa in ("antes_evento", "despues_evento", "antes_completar"):
            with self.subTest(etapa=etapa):
                self._insertar_cuenta()
                conn = database.conectar()
                if etapa == "despues_evento":
                    conn.execute("""CREATE TRIGGER fallo_movimiento BEFORE INSERT ON nube_movimientos
                                    BEGIN SELECT RAISE(ABORT, 'fallo después del evento'); END""")
                    conn.commit()
                elif etapa == "antes_completar":
                    conn.execute("""CREATE TRIGGER fallo_completar BEFORE UPDATE OF estado ON reseller_purchase_operations
                                    WHEN NEW.estado='completed'
                                    BEGIN SELECT RAISE(ABORT, 'fallo antes de completar'); END""")
                    conn.commit()
                conn.close()
                parche = mock.patch.object(reseller_accounts, "_validar_metadata_publica", side_effect=RuntimeError("fallo antes del evento")) if etapa == "antes_evento" else mock.patch.object(reseller_accounts, "_validar_metadata_publica", wraps=reseller_accounts._validar_metadata_publica)
                with parche:
                    with self.assertRaises(Exception):
                        self._comprar(f"rollback-{etapa}", 2)
                estado = self._estado()
                self.assertEqual((estado["saldo"], estado["purchases"], estado["events"], estado["debits"], estado["operations"]), (500000, 0, 0, 0, 0))
                conn = database.conectar()
                conn.execute("DROP TRIGGER IF EXISTS fallo_movimiento")
                conn.execute("DROP TRIGGER IF EXISTS fallo_completar")
                conn.execute("DELETE FROM nube_cuentas WHERE estado='disponible'")
                conn.commit()
                conn.close()

    def test_concurrencia_una_unidad_solo_permite_una_compra(self):
        self._insertar_cuenta()
        barrera = threading.Barrier(2)
        resultados = []

        def comprar(clave):
            barrera.wait()
            try:
                resultados.append(("ok", self._comprar(clave, 2)))
            except Exception as error:  # se inspecciona el error de dominio abajo
                resultados.append(("error", error))

        hilos = [threading.Thread(target=comprar, args=(f"concurrente-{n}",)) for n in range(2)]
        for hilo in hilos:
            hilo.start()
        for hilo in hilos:
            hilo.join(15)
        self.assertTrue(all(not hilo.is_alive() for hilo in hilos))
        exitos = [valor for tipo, valor in resultados if tipo == "ok"]
        errores = [valor for tipo, valor in resultados if tipo == "error"]
        self.assertEqual(len(exitos), 1)
        self.assertEqual(len(errores), 1)
        self.assertIsInstance(errores[0], reseller_accounts.ResellerPurchaseError)
        self.assertEqual(errores[0].codigo, "inventario_agotado")
        estado = self._estado()
        self.assertEqual((estado["purchases"], estado["events"], estado["debits"], estado["operations"], estado["saldo"]), (1, 1, 1, 1, 484000))


if __name__ == "__main__":
    unittest.main()
