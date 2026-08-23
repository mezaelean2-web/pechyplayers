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

import app as app_module
import database
import reseller_accounts
import resellers
import wallets


class ResellerCartOrdersTest(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".db"); os.close(fd)
        self.original_db = database.DB; database.DB = self.path
        conn = database.conectar(); conn.executescript("""
          CREATE TABLE productos(id INTEGER PRIMARY KEY AUTOINCREMENT,nombre TEXT NOT NULL,imagen TEXT DEFAULT '',plan TEXT NOT NULL,precio TEXT NOT NULL,estado TEXT DEFAULT 'disponible',visible INTEGER DEFAULT 1);
          CREATE TABLE nube_clientes(id INTEGER PRIMARY KEY AUTOINCREMENT,nombre TEXT,telefono TEXT,telefono_normalizado TEXT UNIQUE,fecha_actualizacion TEXT DEFAULT CURRENT_TIMESTAMP);
          CREATE TABLE nube_cuentas(id INTEGER PRIMARY KEY AUTOINCREMENT,plataforma TEXT NOT NULL,correo TEXT,contrasena TEXT DEFAULT '',pin TEXT DEFAULT '',cliente_id INTEGER,nombre_cliente TEXT DEFAULT '',telefono TEXT DEFAULT '',fecha_entrega TEXT DEFAULT '',dias_cuenta INTEGER DEFAULT 0,fecha_vencimiento TEXT DEFAULT '',estado TEXT DEFAULT 'disponible',modalidad TEXT DEFAULT 'cuenta_completa',fecha_creacion TEXT DEFAULT CURRENT_TIMESTAMP,fecha_actualizacion TEXT DEFAULT CURRENT_TIMESTAMP);
          CREATE TABLE nube_perfiles(id INTEGER PRIMARY KEY AUTOINCREMENT,cuenta_id INTEGER NOT NULL,nombre_perfil TEXT DEFAULT '',pin TEXT DEFAULT '',cliente_id INTEGER,nombre_cliente TEXT DEFAULT '',telefono TEXT DEFAULT '',fecha_entrega TEXT DEFAULT '',dias_cuenta INTEGER DEFAULT 0,fecha_vencimiento TEXT DEFAULT '',estado TEXT DEFAULT 'disponible',fecha_actualizacion TEXT DEFAULT CURRENT_TIMESTAMP);
          CREATE TABLE nube_movimientos(id INTEGER PRIMARY KEY AUTOINCREMENT,cuenta_id INTEGER NOT NULL,tipo TEXT NOT NULL,descripcion TEXT,estado_anterior TEXT,estado_nuevo TEXT,cliente_nombre TEXT,fecha TEXT DEFAULT CURRENT_TIMESTAMP);
        """)
        conn.execute("INSERT INTO productos(nombre,plan,precio) VALUES('Disney','Cuenta','999999')"); self.cuenta_plan = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute("INSERT INTO productos(nombre,plan,precio) VALUES('Max','Perfil','999999')"); self.perfil_plan = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.commit(); conn.close()
        resellers.inicializar_revendedores(); reseller_accounts.inicializar_esquema()
        self.reseller = resellers.crear_revendedor("Pedido", "pedido@example.com", "3001112233", "Pedido", "ClaveSegura123")
        wallets.apply_wallet_transaction(self.reseller, "manual_credit", 500000, "Saldo de prueba")
        conn = database.conectar()
        conn.execute("INSERT INTO nube_cuentas(plataforma,modalidad,estado) VALUES('Disney','cuenta_completa','caida')")
        madre = conn.execute("INSERT INTO nube_cuentas(plataforma,modalidad,estado) VALUES('Max','perfiles','caida')").lastrowid
        conn.execute("INSERT INTO nube_perfiles(cuenta_id,nombre_perfil,estado) VALUES(?,'Esquema','caida')", (madre,))
        conn.commit(); conn.close()
        reseller_accounts.guardar_regla_inventario_plan(self.cuenta_plan, "Disney", "cuenta", 30)
        reseller_accounts.guardar_regla_inventario_plan(self.perfil_plan, "Max", "perfil", 15)
        resellers.guardar_precio_general(self.cuenta_plan, 20000)
        resellers.guardar_precio_general(self.perfil_plan, 10000)
        app_module.app.config.update(TESTING=True, RESELLER_PURCHASES_ENABLED=True)
        self.client = app_module.app.test_client()

    def tearDown(self):
        database.DB = self.original_db
        try: os.remove(self.path)
        except PermissionError: pass

    def cuenta(self, plataforma="Disney", modalidad="cuenta_completa", perfiles=0):
        conn = database.conectar()
        duracion = 15 if modalidad == "perfiles" else 30
        cuenta = conn.execute("INSERT INTO nube_cuentas(plataforma,correo,contrasena,pin,modalidad,duracion_unidad_dias) VALUES(?,?,?,?,?,?)",
                              (plataforma, f"{os.urandom(3).hex()}@secret.test", "clave-secreta", "1234", modalidad, duracion)).lastrowid
        for indice in range(perfiles):
            conn.execute("INSERT INTO nube_perfiles(cuenta_id,nombre_perfil,pin) VALUES(?,?,?)", (cuenta, f"P{indice}", "9999"))
        conn.commit(); conn.close(); return cuenta

    def lineas(self):
        return [{"plan_id": self.cuenta_plan, "cantidad_unidades": 2, "cantidad_periodos": 2},
                {"plan_id": self.perfil_plan, "cantidad_unidades": 2, "cantidad_periodos": 3}]

    def snapshot(self, lineas, intent="snapshot"):
        preview = reseller_accounts.previsualizar_carrito_reseller(
            self.reseller, lineas, intent)
        return app_module._snapshot_preview_carrito(self.reseller, preview)

    def test_pedido_multi_producto_un_ledger_purchases_individuales_y_fechas(self):
        self.cuenta(); self.cuenta(); self.cuenta("Max", "perfiles", 2)
        ahora = datetime(2026, 8, 22, 10, 30, tzinfo=reseller_accounts.ZONA_HORARIA)
        pedido = reseller_accounts.comprar_carrito_reseller(self.reseller, "cart-1", self.lineas(), ahora)
        self.assertEqual((pedido["cantidad_productos"], pedido["cantidad_unidades"], pedido["total_pagado"]), (2, 4, 140000))
        conn = database.conectar()
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM reseller_orders WHERE estado='completed'").fetchone()[0], 1)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM reseller_order_lines").fetchone()[0], 2)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM reseller_purchases").fetchone()[0], 4)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM reseller_purchase_events").fetchone()[0], 4)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM reseller_wallet_transactions WHERE tipo='purchase'").fetchone()[0], 1)
        self.assertEqual(len({x[0] for x in conn.execute("SELECT fecha_activacion FROM reseller_purchases")}), 1)
        metadata = " ".join(x[0] for x in conn.execute("SELECT datos_publicos_json FROM reseller_purchase_events")).lower()
        for secreto in ("clave-secreta", "secret.test", "1234", "9999"):
            self.assertNotIn(secreto, metadata)
        conn.close()

    def test_idempotencia_durable_e_incompatible(self):
        self.cuenta()
        lineas = [{"plan_id": self.cuenta_plan, "cantidad_unidades": 1, "cantidad_periodos": 1}]
        uno = reseller_accounts.comprar_carrito_reseller(self.reseller, "same", lineas)
        dos = reseller_accounts.comprar_carrito_reseller(self.reseller, "same", lineas)
        self.assertEqual(uno["order_id"], dos["order_id"]); self.assertTrue(dos["duplicado"])
        with self.assertRaises(reseller_accounts.ResellerPurchaseError) as error:
            reseller_accounts.comprar_carrito_reseller(self.reseller, "same", [{**lineas[0], "cantidad_periodos": 2}])
        self.assertEqual(error.exception.codigo, "idempotencia_incompatible")

    def test_inventario_insuficiente_y_fallos_inyectados_revierten_todo(self):
        for punto in ("despues_order", "despues_lineas", "despues_inventario_parcial",
                      "despues_purchases_parciales", "despues_debito", "despues_eventos", "antes_completar_order"):
            with self.subTest(punto=punto):
                self.cuenta()
                antes = self._estado()
                with self.assertRaises(RuntimeError):
                    reseller_accounts.comprar_carrito_reseller(
                        self.reseller, f"fail-{punto}",
                        [{"plan_id": self.cuenta_plan, "cantidad_unidades": 1, "cantidad_periodos": 1}],
                        fallo_inyectado=punto)
                self.assertEqual(self._estado(), antes)
        with self.assertRaises(reseller_accounts.ResellerPurchaseError) as error:
            reseller_accounts.comprar_carrito_reseller(
                self.reseller, "sin-stock",
                [{"plan_id": self.cuenta_plan, "cantidad_unidades": 20, "cantidad_periodos": 1}])
        self.assertEqual(error.exception.codigo, "inventario_agotado")

    def _estado(self):
        conn = database.conectar()
        estado = (conn.execute("SELECT saldo FROM reseller_wallets WHERE revendedor_id=?", (self.reseller,)).fetchone()[0],
                  conn.execute("SELECT COUNT(*) FROM reseller_orders").fetchone()[0],
                  conn.execute("SELECT COUNT(*) FROM reseller_purchases").fetchone()[0],
                  conn.execute("SELECT COUNT(*) FROM reseller_purchase_events").fetchone()[0],
                  conn.execute("SELECT COUNT(*) FROM reseller_wallet_transactions WHERE tipo='purchase'").fetchone()[0],
                  tuple(conn.execute("SELECT estado,nombre_cliente FROM nube_cuentas ORDER BY id")))
        conn.close(); return estado

    def test_endpoint_sesion_csrf_payload_y_respuesta_sin_credenciales(self):
        url = "/revendedores/productos/carrito/comprar"
        self.assertEqual(self.client.post(url, json={}).status_code, 401)
        revendedor = resellers.obtener_revendedor(self.reseller)
        with self.client.session_transaction() as session:
            session["reseller_id"] = self.reseller; session["reseller_auth_version"] = revendedor["auth_version"]; session["csrf_reseller"] = "csrf"
        self.assertEqual(self.client.post(url, json={}).status_code, 403)
        self.cuenta()
        items = [{"plan_id": self.cuenta_plan, "cantidad_unidades": 1, "cantidad_periodos": 1}]
        preview_response = self.client.post(
            "/revendedores/productos/carrito/preview",
            json={"cart_intent_id": "http", "lineas": items},
            headers={"X-CSRF-Token": "csrf"})
        payload = {"cart_intent_id": "http", "items": items,
                   "preview_token": preview_response.get_json()["preview"]["preview_token"]}
        response = self.client.post(url, json=payload, headers={"X-CSRF-Token": "csrf"})
        self.assertEqual(response.status_code, 200)
        texto = json.dumps(response.get_json()).lower()
        for secreto in ("clave-secreta", "secret.test", "1234", "cuenta_id", "perfil_id"):
            self.assertNotIn(secreto, texto)
        manipulado = {**payload, "precio": 1}
        self.assertEqual(self.client.post(url, json=manipulado, headers={"X-CSRF-Token": "csrf"}).status_code, 400)

    def test_precio_sin_cambios_compra_y_cambios_subida_bajada_revierten(self):
        linea = [{"plan_id": self.cuenta_plan, "cantidad_unidades": 1, "cantidad_periodos": 1}]
        for indice, nuevo in enumerate((35000, 15000)):
            with self.subTest(nuevo=nuevo):
                self.cuenta(); antes = self._estado()
                snapshot = self.snapshot(linea, f"precio-{indice}")
                resellers.guardar_precio_general(self.cuenta_plan, nuevo)
                with self.assertRaises(reseller_accounts.ResellerPurchaseError) as error:
                    reseller_accounts.comprar_carrito_reseller(
                        self.reseller, f"precio-{indice}", linea, preview_snapshot=snapshot)
                self.assertEqual(error.exception.codigo, "price_changed")
                self.assertEqual((error.exception.detalles["total_anterior"],
                                  error.exception.detalles["total_actual"]), (20000, nuevo))
                self.assertEqual(self._estado(), antes)
                resellers.guardar_precio_general(self.cuenta_plan, 20000)
        self.cuenta()
        snapshot = self.snapshot(linea, "igual")
        pedido = reseller_accounts.comprar_carrito_reseller(
            self.reseller, "igual", linea, preview_snapshot=snapshot)
        self.assertEqual(pedido["total_pagado"], 20000)

    def test_una_linea_cambia_rollback_total_y_nuevo_preview_nueva_intencion(self):
        self.cuenta(); self.cuenta("Max", "perfiles", 1)
        lineas = [{"plan_id": self.cuenta_plan, "cantidad_unidades": 1, "cantidad_periodos": 1},
                  {"plan_id": self.perfil_plan, "cantidad_unidades": 1, "cantidad_periodos": 1}]
        snapshot = self.snapshot(lineas, "vieja"); antes = self._estado()
        resellers.guardar_precio_general(self.perfil_plan, 12000)
        with self.assertRaises(reseller_accounts.ResellerPurchaseError) as error:
            reseller_accounts.comprar_carrito_reseller(
                self.reseller, "vieja", lineas, preview_snapshot=snapshot)
        self.assertEqual(error.exception.codigo, "price_changed")
        self.assertEqual(len(error.exception.detalles["lineas_cambiadas"]), 1)
        self.assertEqual(self._estado(), antes)
        nuevo = self.snapshot(lineas, "nueva")
        pedido = reseller_accounts.comprar_carrito_reseller(
            self.reseller, "nueva", lineas, preview_snapshot=nuevo)
        self.assertEqual(pedido["total_pagado"], 32000)
        conn = database.conectar()
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM reseller_wallet_transactions WHERE tipo='purchase'").fetchone()[0], 1)
        conn.close()

    def test_cambio_duracion_y_regla_inactiva_son_cart_changed(self):
        linea = [{"plan_id": self.cuenta_plan, "cantidad_unidades": 1, "cantidad_periodos": 1}]
        for indice, sql in enumerate((
                "UPDATE reseller_plan_inventory_rules SET duracion_dias=60 WHERE plan_id=%d" % self.cuenta_plan,
                "UPDATE reseller_plan_inventory_rules SET activo=0 WHERE plan_id=%d" % self.cuenta_plan)):
            with self.subTest(indice=indice):
                self.cuenta(); snapshot = self.snapshot(linea, f"regla-{indice}"); antes = self._estado()
                conn = database.conectar(); conn.execute(sql); conn.commit(); conn.close()
                with self.assertRaises(reseller_accounts.ResellerPurchaseError) as error:
                    reseller_accounts.comprar_carrito_reseller(
                        self.reseller, f"regla-{indice}", linea, preview_snapshot=snapshot)
                self.assertIn(error.exception.codigo, {"cart_changed", "inventario_agotado"})
                self.assertEqual(self._estado(), antes)
                reseller_accounts.guardar_regla_inventario_plan(self.cuenta_plan, "Disney", "cuenta", 30)

    def test_flag_fail_closed_y_endpoint_no_alcanza_motor(self):
        for valor, esperado in ((None, False), (False, False), (0, False), ("false", False),
                                ("ambiguo", False), (True, True), (1, True), ("yes", True)):
            self.assertEqual(app_module._config_bool_explicita(valor), esperado)
        revendedor = resellers.obtener_revendedor(self.reseller)
        with self.client.session_transaction() as session:
            session["reseller_id"] = self.reseller
            session["reseller_auth_version"] = revendedor["auth_version"]
            session["csrf_reseller"] = "csrf"
        app_module.app.config["RESELLER_PURCHASES_ENABLED"] = "false"
        original = reseller_accounts.comprar_carrito_reseller
        llamado = []
        reseller_accounts.comprar_carrito_reseller = lambda *args, **kwargs: llamado.append(True)
        try:
            response = self.client.post("/revendedores/productos/carrito/comprar", json={},
                                        headers={"X-CSRF-Token": "csrf"})
        finally:
            reseller_accounts.comprar_carrito_reseller = original
        self.assertEqual(response.get_json()["codigo"], "purchases_disabled")
        self.assertFalse(llamado)

    def test_doble_envio_concurrente_mismo_intent_un_solo_debito(self):
        self.cuenta(); barrera = threading.Barrier(2); resultados = []; errores = []
        lineas = [{"plan_id": self.cuenta_plan, "cantidad_unidades": 1, "cantidad_periodos": 1}]
        def comprar():
            try:
                barrera.wait(); resultados.append(reseller_accounts.comprar_carrito_reseller(self.reseller, "race", lineas))
            except Exception as error: errores.append(error)
        hilos = [threading.Thread(target=comprar) for _ in range(2)]
        for hilo in hilos: hilo.start()
        for hilo in hilos: hilo.join()
        self.assertFalse(errores); self.assertEqual({x["order_id"] for x in resultados}, {resultados[0]["order_id"]})
        self.assertEqual(sum(bool(x["duplicado"]) for x in resultados), 1)
        conn = database.conectar(); self.assertEqual(conn.execute("SELECT COUNT(*) FROM reseller_wallet_transactions WHERE tipo='purchase'").fetchone()[0], 1); conn.close()

    def test_dos_resellers_compiten_por_ultima_unidad(self):
        self.cuenta()
        otro = resellers.crear_revendedor("Competidor", "competidor@example.com", "3111111111", "Competidor", "ClaveSegura123")
        wallets.apply_wallet_transaction(otro, "manual_credit", 100000, "Saldo competidor")
        barrera = threading.Barrier(2); exitos = []; errores = []
        linea = [{"plan_id": self.cuenta_plan, "cantidad_unidades": 1, "cantidad_periodos": 1}]
        def comprar(reseller_id):
            try:
                barrera.wait(); exitos.append(reseller_accounts.comprar_carrito_reseller(reseller_id, f"last-{reseller_id}", linea))
            except reseller_accounts.ResellerPurchaseError as error: errores.append(error.codigo)
        hilos = [threading.Thread(target=comprar, args=(identificador,)) for identificador in (self.reseller, otro)]
        for hilo in hilos: hilo.start()
        for hilo in hilos: hilo.join()
        self.assertEqual((len(exitos), errores), (1, ["inventario_agotado"]))
        conn = database.conectar()
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM reseller_purchases").fetchone()[0], 1)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM reseller_wallet_transactions WHERE tipo='purchase'").fetchone()[0], 1)
        conn.close()


if __name__ == "__main__": unittest.main()
