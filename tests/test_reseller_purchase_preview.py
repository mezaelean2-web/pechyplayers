try:
    from tests._bootstrap import TEST_DB
except ModuleNotFoundError:
    from _bootstrap import TEST_DB

import os
import sqlite3
import tempfile
import unittest
from datetime import datetime
from unittest import mock

import app as app_module
import database
import reseller_accounts
import resellers
import wallets


class ResellerPurchasePreviewTest(unittest.TestCase):
    def setUp(self):
        descriptor, self.path = tempfile.mkstemp(suffix=".db")
        os.close(descriptor)
        self.original_db = database.DB
        database.DB = self.path
        conn = sqlite3.connect(self.path)
        conn.executescript("""
          CREATE TABLE productos(id INTEGER PRIMARY KEY AUTOINCREMENT,nombre TEXT NOT NULL,
            imagen TEXT DEFAULT '',plan TEXT NOT NULL,precio TEXT NOT NULL,estado TEXT DEFAULT 'disponible',
            visible INTEGER DEFAULT 1, oferta_precio TEXT, oferta_activa INTEGER DEFAULT 0,
            destacado INTEGER DEFAULT 0, orden INTEGER DEFAULT 1, categoria TEXT DEFAULT 'Streaming',
            orden_categoria INTEGER DEFAULT 1);
          CREATE TABLE nube_clientes(id INTEGER PRIMARY KEY AUTOINCREMENT,nombre TEXT,telefono TEXT,telefono_normalizado TEXT UNIQUE,fecha_actualizacion TEXT DEFAULT CURRENT_TIMESTAMP);
          CREATE TABLE nube_cuentas(id INTEGER PRIMARY KEY AUTOINCREMENT,plataforma TEXT NOT NULL,correo TEXT,
            contrasena TEXT DEFAULT '',pin TEXT DEFAULT '',cliente_id INTEGER,nombre_cliente TEXT DEFAULT '',telefono TEXT DEFAULT '',
            fecha_entrega TEXT DEFAULT '',dias_cuenta INTEGER DEFAULT 0,fecha_vencimiento TEXT DEFAULT '',estado TEXT DEFAULT 'disponible',
            modalidad TEXT DEFAULT 'cuenta_completa',fecha_creacion TEXT DEFAULT CURRENT_TIMESTAMP,fecha_actualizacion TEXT DEFAULT CURRENT_TIMESTAMP);
          CREATE TABLE nube_perfiles(id INTEGER PRIMARY KEY AUTOINCREMENT,cuenta_id INTEGER NOT NULL,nombre_perfil TEXT DEFAULT '',
            pin TEXT DEFAULT '',cliente_id INTEGER,nombre_cliente TEXT DEFAULT '',telefono TEXT DEFAULT '',fecha_entrega TEXT DEFAULT '',
            dias_cuenta INTEGER DEFAULT 0,fecha_vencimiento TEXT DEFAULT '',estado TEXT DEFAULT 'disponible',fecha_actualizacion TEXT DEFAULT CURRENT_TIMESTAMP);
          CREATE TABLE nube_movimientos(id INTEGER PRIMARY KEY AUTOINCREMENT,cuenta_id INTEGER NOT NULL,tipo TEXT NOT NULL,descripcion TEXT,estado_anterior TEXT,estado_nuevo TEXT,cliente_nombre TEXT,fecha TEXT DEFAULT CURRENT_TIMESTAMP);
        """)
        conn.execute("INSERT INTO productos(nombre,plan,precio) VALUES('Netflix','Cuenta','999999')")
        self.plan = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.commit(); conn.close()
        resellers.inicializar_revendedores(); reseller_accounts.inicializar_esquema()
        self.reseller = resellers.crear_revendedor("Preview", "preview@example.com", "3001234567", "Preview", "ClaveSegura123")
        wallets.apply_wallet_transaction(self.reseller, "manual_credit", 50000, "Saldo preview")
        app_module.app.config.update(TESTING=True, SECRET_KEY="preview-test", RESELLER_PURCHASES_ENABLED=False)
        self.client = app_module.app.test_client()

    def tearDown(self):
        database.DB = self.original_db
        try: os.remove(self.path)
        except PermissionError: pass

    def login(self):
        revendedor = resellers.obtener_revendedor(self.reseller)
        with self.client.session_transaction() as session:
            session["reseller_id"] = self.reseller
            session["reseller_auth_version"] = revendedor["auth_version"]
            session["csrf_reseller"] = "csrf-preview"

    def unidad_cuenta(self):
        conn = database.conectar()
        conn.execute("INSERT INTO nube_cuentas(plataforma,correo,contrasena,pin,modalidad,duracion_unidad_dias) VALUES('Netflix','secret@example.com','clave','1234','cuenta_completa',30)")
        conn.commit(); conn.close()

    def estado(self):
        conn = database.conectar()
        resultado = tuple(conn.execute(sql).fetchone()[0] for sql in (
            "SELECT saldo FROM reseller_wallets WHERE revendedor_id=1",
            "SELECT COUNT(*) FROM reseller_purchases",
            "SELECT COUNT(*) FROM reseller_purchase_events",
            "SELECT COUNT(*) FROM reseller_purchase_operations",
            "SELECT COUNT(*) FROM reseller_wallet_transactions WHERE tipo='purchase'",
            "SELECT COUNT(*) FROM nube_movimientos",
        ))
        inventario = [tuple(fila) for fila in conn.execute("SELECT id,estado,nombre_cliente,fecha_entrega FROM nube_cuentas ORDER BY id")]
        conn.close()
        return resultado, inventario

    def test_preview_exige_sesion(self):
        self.assertEqual(self.client.get(f"/revendedores/productos/planes/{self.plan}/compra").status_code, 401)

    def test_preview_precio_general_cuenta_disponible_calculos_saldo_y_sin_secretos(self):
        self.unidad_cuenta()
        reseller_accounts.guardar_regla_inventario_plan(self.plan, "Netflix", "cuenta", 30)
        resellers.guardar_precio_general(self.plan, 8000); self.login()
        antes = self.estado()
        response = self.client.get(f"/revendedores/productos/planes/{self.plan}/compra")
        data = response.get_json()["preview"]
        self.assertEqual(response.status_code, 200)
        self.assertEqual((data["precio_unitario"], data["origen_precio"], data["tipo_unidad"]), (8000, "precio_general", "cuenta"))
        self.assertEqual((data["duracion_base_dias"], data["precio_total"], data["saldo"], data["saldo_estimado"]), (30, 8000, 50000, 42000))
        self.assertEqual((data["min_periodos"], data["max_periodos"], data["disponibilidad"]), (1, 12, "Disponible"))
        serialized = response.get_data(as_text=True).lower()
        for secret in ("secret@example.com", "clave", "1234", "cuenta_id", "perfil_id"):
            self.assertNotIn(secret, serialized)
        self.assertEqual(self.estado(), antes)

    def test_prioridad_oferta_personalizado_y_general(self):
        self.unidad_cuenta()
        reseller_accounts.guardar_regla_inventario_plan(self.plan, "Netflix", "cuenta", 15)
        resellers.guardar_precio_general(self.plan, 12000)
        resellers.guardar_precio_personalizado(self.reseller, self.plan, 10000)
        self.assertEqual(reseller_accounts.previsualizar_compra_plan(self.reseller, self.plan)["origen_precio"], "precio_personalizado")
        resellers.guardar_precio_personalizado(self.reseller, self.plan, 10000, True, 7000, "2026-08-01", "2026-08-31")
        preview = reseller_accounts.previsualizar_compra_plan(self.reseller, self.plan, ahora=datetime(2026, 8, 22))
        self.assertEqual((preview["precio_unitario"], preview["origen_precio"]), (7000, "oferta_personalizada"))

    def test_sin_tarifa_regla_ausente_inactiva_y_agotado(self):
        preview = reseller_accounts.previsualizar_compra_plan(self.reseller, self.plan)
        self.assertFalse(preview["tarifa_configurada"]); self.assertEqual(preview["estado_disponibilidad"], "configuracion_pendiente")
        resellers.guardar_precio_general(self.plan, 8000)
        conn = database.conectar(); conn.execute("INSERT INTO nube_cuentas(plataforma,modalidad,estado) VALUES('Netflix','cuenta_completa','caida')"); conn.commit(); conn.close()
        reseller_accounts.guardar_regla_inventario_plan(self.plan, "Netflix", "cuenta", 30)
        preview = reseller_accounts.previsualizar_compra_plan(self.reseller, self.plan)
        self.assertEqual(preview["estado_disponibilidad"], "agotado")
        conn = database.conectar(); conn.execute("UPDATE reseller_plan_inventory_rules SET activo=0 WHERE plan_id=?", (self.plan,)); conn.commit(); conn.close()
        self.assertEqual(reseller_accounts.previsualizar_compra_plan(self.reseller, self.plan)["estado_disponibilidad"], "configuracion_pendiente")

    def test_perfil_disponible_y_periodos_validan_helper_compartido(self):
        conn = database.conectar(); cur = conn.execute("INSERT INTO nube_cuentas(plataforma,modalidad,duracion_unidad_dias) VALUES('Netflix','perfiles',15)"); conn.execute("INSERT INTO nube_perfiles(cuenta_id,nombre_perfil) VALUES(?,'P1')", (cur.lastrowid,)); conn.commit(); conn.close()
        reseller_accounts.guardar_regla_inventario_plan(self.plan, "Netflix", "perfil", 15)
        resellers.guardar_precio_general(self.plan, 6000)
        preview = reseller_accounts.previsualizar_compra_plan(self.reseller, self.plan, 12)
        self.assertEqual((preview["tipo_unidad"], preview["duracion_total_dias"], preview["precio_total"]), ("perfil", 180, 72000))
        with self.assertRaises(reseller_accounts.ResellerPurchaseError): reseller_accounts.previsualizar_compra_plan(self.reseller, self.plan, 13)

    def test_varias_unidades_por_periodos_y_limite_de_inventario(self):
        for indice in range(4):
            conn = database.conectar(); conn.execute(
                "INSERT INTO nube_cuentas(plataforma,correo,modalidad,duracion_unidad_dias) VALUES('Netflix',?,'cuenta_completa',30)",
                (f"unidad{indice}@example.com",)); conn.commit(); conn.close()
        reseller_accounts.guardar_regla_inventario_plan(self.plan, "Netflix", "cuenta", 30)
        resellers.guardar_precio_general(self.plan, 8000)
        preview = reseller_accounts.previsualizar_compra_plan(self.reseller, self.plan, 2, 3)
        self.assertEqual((preview["cantidad_unidades"], preview["cantidad_periodos"]), (3, 2))
        self.assertEqual((preview["disponibilidad_unidades"], preview["precio_por_unidad"],
                          preview["precio_total"], preview["duracion_total_dias"]),
                         (4, 16000, 48000, 60))
        with self.assertRaises(reseller_accounts.ResellerPurchaseError) as error:
            reseller_accounts.previsualizar_compra_plan(self.reseller, self.plan, 2, 5)
        self.assertEqual(error.exception.codigo, "cantidad_unidades_excedida")

    def test_preview_carrito_multiple_combina_linea_y_revalida_servidor(self):
        for indice in range(4):
            conn = database.conectar(); conn.execute(
                "INSERT INTO nube_cuentas(plataforma,correo,modalidad,duracion_unidad_dias) VALUES('Netflix',?,'cuenta_completa',30)",
                (f"cart{indice}@example.com",)); conn.commit(); conn.close()
        conn = database.conectar()
        conn.execute("INSERT INTO productos(nombre,plan,precio) VALUES('Max','Perfil','123456')")
        plan_max = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        cuenta = conn.execute("INSERT INTO nube_cuentas(plataforma,modalidad,duracion_unidad_dias) VALUES('Max','perfiles',15)").lastrowid
        conn.execute("INSERT INTO nube_perfiles(cuenta_id,nombre_perfil) VALUES(?,'P1')", (cuenta,))
        conn.commit(); conn.close()
        reseller_accounts.guardar_regla_inventario_plan(self.plan, "Netflix", "cuenta", 30)
        reseller_accounts.guardar_regla_inventario_plan(plan_max, "Max", "perfil", 15)
        resellers.guardar_precio_general(self.plan, 8000); resellers.guardar_precio_general(plan_max, 6000)
        self.login(); antes = self.estado()
        payload = {"cart_intent_id": "pedido-uno", "lineas": [
            {"plan_id": self.plan, "cantidad_unidades": 2, "cantidad_periodos": 2},
            {"plan_id": self.plan, "cantidad_unidades": 1, "cantidad_periodos": 2},
            {"plan_id": plan_max, "cantidad_unidades": 1, "cantidad_periodos": 1}]}
        response = self.client.post("/revendedores/productos/carrito/preview", json=payload,
                                    headers={"X-CSRF-Token": "csrf-preview"})
        data = response.get_json()["preview"]
        self.assertEqual(response.status_code, 200)
        self.assertEqual((data["total_productos"], data["total_unidades"], data["total"]), (2, 4, 54000))
        self.assertEqual((data["saldo_suficiente"], data["saldo_estimado"]), (False, -4000))
        self.assertEqual(data["lineas"][0]["cantidad_unidades"], 3)
        self.assertEqual(self.estado(), antes)
        with self.assertRaises(reseller_accounts.ResellerPurchaseError) as error:
            reseller_accounts.previsualizar_carrito_reseller(self.reseller, [
                {"plan_id": self.plan, "cantidad_unidades": 3, "cantidad_periodos": 2},
                {"plan_id": self.plan, "cantidad_unidades": 2, "cantidad_periodos": 1}])
        self.assertEqual(error.exception.codigo, "cantidad_unidades_excedida")

    def test_cuenta_y_perfil_mismo_producto_coexisten_y_periodos_separan(self):
        conn = database.conectar()
        conn.execute("UPDATE productos SET plan='Cuenta completa' WHERE id=?", (self.plan,))
        conn.execute("INSERT INTO productos(nombre,plan,precio) VALUES('Netflix','Perfil','999999')")
        plan_perfil = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        for indice in range(4):
            conn.execute("INSERT INTO nube_cuentas(plataforma,correo,modalidad,duracion_unidad_dias) VALUES('Netflix',?,'cuenta_completa',30)", (f"full{indice}@example.com",))
        cuenta_perfiles = conn.execute("INSERT INTO nube_cuentas(plataforma,modalidad,duracion_unidad_dias) VALUES('Netflix','perfiles',15)").lastrowid
        for indice in range(5):
            conn.execute("INSERT INTO nube_perfiles(cuenta_id,nombre_perfil) VALUES(?,?)", (cuenta_perfiles, f"P{indice}"))
        conn.commit(); conn.close()
        reseller_accounts.guardar_regla_inventario_plan(self.plan, "Netflix", "cuenta", 30)
        reseller_accounts.guardar_regla_inventario_plan(plan_perfil, "Netflix", "perfil", 30)
        resellers.guardar_precio_general(self.plan, 25000)
        resellers.guardar_precio_general(plan_perfil, 10000)
        preview = reseller_accounts.previsualizar_carrito_reseller(self.reseller, [
            {"plan_id": self.plan, "cantidad_unidades": 2, "cantidad_periodos": 3},
            {"plan_id": plan_perfil, "cantidad_unidades": 4, "cantidad_periodos": 1},
            {"plan_id": plan_perfil, "cantidad_unidades": 1, "cantidad_periodos": 2},
        ])
        self.assertEqual(len(preview["lineas"]), 3)
        self.assertEqual(preview["total_productos"], 3)
        self.assertEqual(preview["total_unidades"], 7)
        self.assertEqual(preview["total"], 210000)
        self.assertEqual(
            [(linea["plan_id"], linea["cantidad_periodos"], linea["cantidad_unidades"]) for linea in preview["lineas"]],
            [(self.plan, 3, 2), (plan_perfil, 1, 4), (plan_perfil, 2, 1)],
        )

    def test_carrito_rechaza_campos_autoritativos_y_aisla_saldo(self):
        self.login()
        response = self.client.post("/revendedores/productos/carrito/preview", json={"lineas": [{
            "plan_id": self.plan, "cantidad_unidades": 1, "cantidad_periodos": 1,
            "precio": 1}]}, headers={"X-CSRF-Token": "csrf-preview"})
        self.assertEqual((response.status_code, response.get_json()["codigo"]), (400, "payload_invalido"))
        otro = resellers.crear_revendedor("Otro", "otro-preview@example.com", "3110000000", "Otro", "ClaveSegura123")
        wallets.apply_wallet_transaction(otro, "manual_credit", 900000, "Saldo ajeno")
        self.unidad_cuenta(); reseller_accounts.guardar_regla_inventario_plan(self.plan, "Netflix", "cuenta", 30); resellers.guardar_precio_general(self.plan, 8000)
        response = self.client.post("/revendedores/productos/carrito/preview", json={"lineas": [{
            "plan_id": self.plan, "cantidad_unidades": 1, "cantidad_periodos": 1}]}, headers={"X-CSRF-Token": "csrf-preview"})
        self.assertEqual(response.get_json()["preview"]["saldo"], 50000)

    def test_post_csrf_guard_y_cero_efectos_sin_llamar_motor(self):
        self.login(); antes = self.estado()
        url = f"/revendedores/productos/planes/{self.plan}/comprar"
        self.assertEqual(self.client.post(url, json={"cantidad_periodos": 1, "idempotency_key": "key"}).status_code, 403)
        with mock.patch.object(reseller_accounts, "comprar_plan_reseller", side_effect=AssertionError("motor llamado")) as engine:
            response = self.client.post(url, json={"cantidad_periodos": 1, "idempotency_key": "key"}, headers={"X-CSRF-Token": "csrf-preview"})
        self.assertEqual((response.status_code, response.get_json()["codigo"]), (409, "purchases_disabled"))
        engine.assert_not_called(); self.assertEqual(self.estado(), antes)

    def test_post_anonimo_y_rechaza_campos_autoritativos(self):
        url = f"/revendedores/productos/planes/{self.plan}/comprar"
        self.assertEqual(self.client.post(url, json={}).status_code, 401)
        self.login()
        response = self.client.post(url, json={"precio_total": 1}, headers={"X-CSRF-Token": "csrf-preview"})
        self.assertEqual((response.status_code, response.get_json()["codigo"]), (400, "payload_invalido"))


if __name__ == "__main__": unittest.main()
