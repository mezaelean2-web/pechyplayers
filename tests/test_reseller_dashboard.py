try:
    from tests._bootstrap import TEST_DB
except ModuleNotFoundError:
    from _bootstrap import TEST_DB

import os
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

import app as app_module
import database
import resellers
import wallets


class ResellerDashboardTest(unittest.TestCase):
    def setUp(self):
        descriptor, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(descriptor)
        self.original_db = database.DB
        database.DB = self.db_path
        conn = sqlite3.connect(self.db_path)
        conn.execute("""CREATE TABLE productos (
            id INTEGER PRIMARY KEY, nombre TEXT NOT NULL,
            imagen TEXT NOT NULL DEFAULT 'producto.jpg', plan TEXT NOT NULL,
            precio TEXT NOT NULL, oferta_precio TEXT, oferta_activa INTEGER DEFAULT 0,
            destacado INTEGER DEFAULT 0, visible INTEGER DEFAULT 1,
            orden INTEGER DEFAULT 1, categoria TEXT DEFAULT 'Streaming',
            orden_categoria INTEGER DEFAULT 1, estado TEXT DEFAULT 'disponible'
        )""")
        conn.commit()
        conn.close()
        resellers.inicializar_revendedores()
        app_module.app.config.update(TESTING=True, SECRET_KEY="dashboard-test")
        app_module._intentos_login_reseller.clear()
        self.client = app_module.app.test_client()
        self.reseller_id = self.crear("principal@example.com", "Andrea Principal")

    def tearDown(self):
        database.DB = self.original_db
        os.remove(self.db_path)

    def crear(self, correo, nombre="Persona Prueba"):
        return resellers.crear_revendedor(
            nombre, correo, "3001234567", "Tienda Prueba", "ClaveSegura123"
        )

    def autenticar(self, reseller_id=None, client=None):
        client = client or self.client
        reseller = resellers.obtener_revendedor(reseller_id or self.reseller_id)
        with client.session_transaction() as session:
            session["reseller_id"] = reseller["id"]
            session["reseller_auth_version"] = reseller["auth_version"]
            session["csrf_reseller"] = "csrf-dashboard"
        return client

    def respuesta_dashboard(self, productos=None, categorias=None, client=None):
        productos = [] if productos is None else productos
        categorias = [] if categorias is None else categorias
        with patch.object(app_module, "obtener_productos", return_value=productos), \
             patch.object(app_module, "obtener_categorias", return_value=categorias):
            return (client or self.client).get("/revendedores")

    @staticmethod
    def producto(producto_id, nombre, plan_id, visible=1, categoria="Streaming",
                 precio_publico="999999"):
        return {
            "nombre": nombre, "visible": visible, "categoria": categoria,
            "estado": "disponible", "planes": [{
                "id": plan_id, "plan": "Perfil", "precio": precio_publico
            }]
        }

    def token(self, client=None, ruta="/revendedores/login"):
        client = client or self.client
        client.get(ruta)
        with client.session_transaction() as session:
            return session["csrf_reseller"]

    def insertar_planes(self, *plan_ids):
        conn = sqlite3.connect(self.db_path)
        conn.executemany(
            "INSERT INTO productos(id, nombre, plan, precio) VALUES (?, ?, 'Perfil', '15000')",
            [(plan_id, f"Producto {plan_id}") for plan_id in plan_ids]
        )
        conn.commit()
        conn.close()

    def test_anonimo_no_accede(self):
        respuesta = self.respuesta_dashboard()
        self.assertEqual(respuesta.status_code, 302)
        self.assertTrue(respuesta.headers["Location"].endswith("/revendedores/login"))

    def test_reseller_activo_accede_y_bloqueado_no(self):
        self.autenticar()
        self.assertEqual(self.respuesta_dashboard().status_code, 200)
        resellers.cambiar_estado_revendedor(self.reseller_id, "bloqueado")
        bloqueado = self.respuesta_dashboard()
        self.assertEqual(bloqueado.status_code, 302)
        self.assertTrue(bloqueado.headers["Location"].endswith("/revendedores/login"))

    def test_login_redirige_al_dashboard(self):
        token = self.token()
        respuesta = self.client.post("/revendedores/login", data={
            "csrf_token": token, "correo": "principal@example.com",
            "password": "ClaveSegura123"
        })
        self.assertEqual(respuesta.status_code, 302)
        self.assertTrue(respuesta.headers["Location"].endswith("/revendedores"))

    def test_registro_redirige_al_dashboard(self):
        client = app_module.app.test_client()
        token = self.token(client, "/revendedores/registro")
        respuesta = client.post("/revendedores/registro", data={
            "csrf_token": token, "nombre": "Nuevo Revendedor",
            "negocio": "Nuevo Negocio", "correo": "nuevo@example.com",
            "telefono": "3007654321", "password": "ClaveNueva123",
            "confirmar_password": "ClaveNueva123"
        })
        self.assertEqual(respuesta.status_code, 302)
        self.assertTrue(respuesta.headers["Location"].endswith("/revendedores"))

    def test_saldo_y_movimientos_estan_aislados(self):
        otro_id = self.crear("otro@example.com", "Otro Revendedor")
        wallets.apply_wallet_transaction(
            self.reseller_id, "manual_credit", 45000, "Saldo principal"
        )
        wallets.apply_wallet_transaction(
            otro_id, "manual_credit", 987654, "MOVIMIENTO AJENO"
        )
        self.autenticar()
        html = self.respuesta_dashboard().get_data(as_text=True)
        self.assertIn("$45.000 COP", html)
        self.assertIn("Saldo principal", html)
        self.assertNotIn("$987.654 COP", html)
        self.assertNotIn("MOVIMIENTO AJENO", html)

    def test_total_recargado_usa_solo_recargas_reales_propias(self):
        otro_id = self.crear("recargas-otro@example.com")
        wallets.apply_wallet_transaction(self.reseller_id, "recharge", 30000, "Recarga")
        wallets.apply_wallet_transaction(self.reseller_id, "manual_credit", 7000, "Manual")
        wallets.apply_wallet_transaction(otro_id, "recharge", 90000, "Ajena")
        self.autenticar()
        html = self.respuesta_dashboard().get_data(as_text=True)
        self.assertIn("$30.000 COP", html)
        self.assertNotIn("$90.000 COP", html)

    def test_conteo_agrupa_planes_y_exige_precio_reseller(self):
        self.insertar_planes(1, 2, 3)
        resellers.guardar_precio_general(1, 11000)
        resellers.guardar_precio_general(2, 18000)
        productos = [
            {"nombre": "Netflix", "visible": 1, "categoria": "Streaming", "planes": [
                {"id": 1, "plan": "Perfil", "precio": "15000"},
                {"id": 2, "plan": "Cuenta", "precio": "25000"},
            ]},
            self.producto(3, "MAX", 3),
        ]
        self.autenticar()
        html = self.respuesta_dashboard(
            productos, [{"nombre": "Streaming", "visible": 1}]
        ).get_data(as_text=True)
        self.assertIn("Productos disponibles</span><strong>1</strong>", html)

    def test_precio_publico_nunca_es_fallback(self):
        producto = self.producto(1, "Netflix", 1, precio_publico="777777")
        self.autenticar()
        html = self.respuesta_dashboard(
            [producto], [{"nombre": "Streaming", "visible": 1}]
        ).get_data(as_text=True)
        self.assertIn("Productos disponibles</span><strong>0</strong>", html)
        self.assertNotIn("777777", html)

    def test_conteo_respeta_visibilidad_de_producto_y_categoria(self):
        self.insertar_planes(1, 2, 3)
        for plan_id in (1, 2, 3):
            resellers.guardar_precio_general(plan_id, 10000 + plan_id)
        productos = [
            self.producto(1, "Visible", 1),
            self.producto(2, "Producto oculto", 2, visible=0),
            self.producto(3, "Categoría oculta", 3, categoria="Oculta"),
        ]
        self.autenticar()
        html = self.respuesta_dashboard(productos, [
            {"nombre": "Streaming", "visible": 1},
            {"nombre": "Oculta", "visible": 0},
        ]).get_data(as_text=True)
        self.assertIn("Productos disponibles</span><strong>1</strong>", html)

    def test_dashboard_funciona_sin_movimientos_ni_productos(self):
        self.autenticar()
        html = self.respuesta_dashboard().get_data(as_text=True)
        self.assertIn("Aún no tienes movimientos", html)
        self.assertIn("Productos disponibles</span><strong>0</strong>", html)
        self.assertIn("$0 COP", html)

    def test_logout_sigue_siendo_post_y_exige_csrf(self):
        self.autenticar()
        self.assertEqual(self.client.get("/revendedores/logout").status_code, 405)
        self.assertEqual(self.client.post("/revendedores/logout").status_code, 403)
        respuesta = self.client.post("/revendedores/logout", data={
            "csrf_token": "csrf-dashboard"
        })
        self.assertEqual(respuesta.status_code, 302)

    def test_shell_contiene_navegacion_desktop_y_movil(self):
        self.autenticar()
        html = self.respuesta_dashboard().get_data(as_text=True)
        self.assertIn('class="reseller-sidebar"', html)
        self.assertIn('class="reseller-mobile-nav"', html)
        for etiqueta in ("Inicio", "Productos", "Billetera", "Mi cuenta"):
            self.assertIn(etiqueta, html)
        self.assertNotIn('<span>Movimientos</span>', html)
        self.assertNotIn('<span>Recargar saldo</span>', html)
        self.assertIn('action="/revendedores/logout" method="POST"', html)
        self.assertIn('data-reseller-global-cart', html)
        self.assertIn('js/reseller-cart.js', html)
        self.assertIn('css/reseller-cart.css', html)

    def test_no_muestra_metricas_falsas_de_compras(self):
        self.autenticar()
        html = self.respuesta_dashboard().get_data(as_text=True).lower()
        for metrica in (
            "compras realizadas", "gasto acumulado", "producto más comprado",
            "ticket promedio", "facturación", "productos entregados"
        ):
            self.assertNotIn(metrica, html)
        self.assertNotIn("compras desde el panel", html)

    def test_navegacion_y_destacados_permanecen_en_panel_privado(self):
        self.insertar_planes(1)
        resellers.guardar_precio_general(1, 11000)
        self.autenticar()
        html = self.respuesta_dashboard(
            [self.producto(1, "Netflix", 1)],
            [{"nombre": "Streaming", "visible": 1}],
        ).get_data(as_text=True)
        self.assertIn('href="/revendedores/productos"', html)
        self.assertIn("Productos para ti", html)
        self.assertIn("$11.000 COP", html)
        self.assertNotIn('href="/">Ver cat', html)


if __name__ == "__main__":
    unittest.main()
