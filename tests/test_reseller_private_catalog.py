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


class ResellerPrivateCatalogTest(unittest.TestCase):
    def setUp(self):
        descriptor, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(descriptor)
        self.original_db = database.DB
        database.DB = self.db_path
        conn = sqlite3.connect(self.db_path)
        conn.execute("""CREATE TABLE productos (
            id INTEGER PRIMARY KEY, nombre TEXT NOT NULL, imagen TEXT DEFAULT 'netflix.jpg',
            plan TEXT NOT NULL, precio TEXT NOT NULL, oferta_precio TEXT,
            oferta_activa INTEGER DEFAULT 0, destacado INTEGER DEFAULT 0,
            visible INTEGER DEFAULT 1, orden INTEGER DEFAULT 1,
            categoria TEXT DEFAULT 'Streaming', orden_categoria INTEGER DEFAULT 1,
            estado TEXT DEFAULT 'disponible',
            participa_descuento_carrito INTEGER NOT NULL DEFAULT 0)""")
        conn.execute("""CREATE TABLE categorias (
            id INTEGER PRIMARY KEY, nombre TEXT NOT NULL, icono TEXT DEFAULT '',
            color TEXT DEFAULT '', visible INTEGER DEFAULT 1, orden INTEGER DEFAULT 1)""")
        conn.execute("INSERT INTO categorias(nombre, visible) VALUES('Streaming', 1)")
        conn.executemany("INSERT INTO productos(id,nombre,plan,precio) VALUES(?,?,?,?)", [
            (1, "Netflix", "Perfil", "777777"), (2, "Netflix", "Cuenta", "888888"),
            (3, "Sin precio", "Perfil", "999999")])
        conn.commit(); conn.close()
        resellers.inicializar_revendedores()
        self.reseller_id = resellers.crear_revendedor("Propio", "propio@example.com", "3001234567", "Tienda", "ClaveSegura123")
        self.otro_id = resellers.crear_revendedor("Otro", "otro@example.com", "3007654321", "Otra", "ClaveSegura123")
        app_module.app.config.update(TESTING=True, SECRET_KEY="catalog-test")
        self.merchandising_patches = [
            patch.object(app_module, "obtener_promociones", return_value=[]),
            patch.object(app_module, "obtener_cartelera", return_value=[]),
            patch.object(app_module, "obtener_categorias_cartelera", return_value=[]),
        ]
        for item in self.merchandising_patches:
            item.start()
        self.client = app_module.app.test_client()

    def tearDown(self):
        for item in reversed(self.merchandising_patches):
            item.stop()
        database.DB = self.original_db
        os.remove(self.db_path)

    def autenticar(self, reseller_id=None):
        revendedor = resellers.obtener_revendedor(reseller_id or self.reseller_id)
        with self.client.session_transaction() as session:
            session["reseller_id"] = revendedor["id"]
            session["reseller_auth_version"] = revendedor["auth_version"]

    def test_anonimo_y_bloqueado_no_acceden(self):
        self.assertEqual(self.client.get("/revendedores/productos").status_code, 302)
        self.autenticar()
        resellers.cambiar_estado_revendedor(self.reseller_id, "bloqueado")
        respuesta = self.client.get("/revendedores/productos")
        self.assertEqual(respuesta.status_code, 302)
        self.assertTrue(respuesta.headers["Location"].endswith("/revendedores/login"))

    def test_solo_precio_reseller_sin_fallback_publico_y_aislado(self):
        resellers.guardar_precio_personalizado(self.reseller_id, 1, 11000)
        resellers.guardar_precio_personalizado(self.otro_id, 1, 22000)
        self.autenticar()
        html = self.client.get("/revendedores/productos").get_data(as_text=True)
        self.assertIn("Netflix", html)
        self.assertIn("$11.000 COP", html)
        self.assertNotIn("$22.000 COP", html)
        for publico in ("777777", "888888", "999999"):
            self.assertNotIn(publico, html)
        self.assertIn("Sin precio", html)
        self.assertIn("Precio por configurar", html)

    def test_cliente_publico_conserva_precio_y_apertura_actuales(self):
        html = self.client.get("/").get_data(as_text=True)
        self.assertIn("777777", html)
        self.assertIn("888888", html)
        self.assertIn('class="buy"', html)
        self.assertIn("✨ Ver planes", html)
        self.assertIn('id="productoModal"', html)
        self.assertIn('id="modalProductoComprar"', html)
        self.assertNotIn("Precio por configurar", html)
        self.assertNotIn("data-reseller-global-cart", html)
        self.assertNotIn("js/reseller-cart.js", html)

    def test_reseller_abre_modal_publico_con_precios_privados(self):
        resellers.guardar_precio_personalizado(self.reseller_id, 1, 11000)
        self.autenticar()
        html = self.client.get("/revendedores/productos").get_data(as_text=True)

        self.assertIn('<button class="buy" type="button">', html)
        self.assertIn("✨ Ver planes", html)
        self.assertIn('id="productoModal"', html)
        self.assertIn("$11.000 COP", html)
        self.assertIn("Precio por configurar", html)
        for publico in ("777777", "888888", "999999"):
            self.assertNotIn(publico, html)

        self.assertIn(
            'id="modalProductoComprar" class="modal-producto-comprar reseller-buy-disabled" type="button" disabled',
            html,
        )
        self.assertIn('data-reseller-plan-id="1" data-reseller-price-ready="true"', html)
        self.assertIn('data-reseller-plan-id="2" data-reseller-price-ready="false"', html)
        self.assertIn("Compra reseller próximamente", html)
        self.assertEqual(html.count("data-reseller-global-cart"), 1)
        self.assertIn("js/reseller-cart.js", html)
        self.assertNotIn("data-cart-total", html)

    def test_visibilidad_categoria_disponibilidad_y_planes_validos(self):
        resellers.guardar_precio_general(1, 11000)
        resellers.guardar_precio_general(2, 18000)
        productos = [
            {"nombre": "Visible", "imagen": "netflix.jpg", "visible": 1, "estado": "disponible", "categoria": "Streaming", "planes": [{"id": 1, "plan": "Perfil", "precio": "777777"}, {"id": 3, "plan": "Sin precio", "precio": "999999"}]},
            {"nombre": "Oculto", "visible": 0, "estado": "disponible", "categoria": "Streaming", "planes": [{"id": 2, "plan": "P", "precio": "1"}]},
            {"nombre": "Agotado", "visible": 1, "estado": "agotado", "categoria": "Streaming", "planes": [{"id": 2, "plan": "P", "precio": "1"}]},
            {"nombre": "Categoria oculta", "visible": 1, "estado": "disponible", "categoria": "Oculta", "planes": [{"id": 2, "plan": "P", "precio": "1"}]},
        ]
        self.autenticar()
        with patch.object(app_module, "obtener_productos", return_value=productos), patch.object(app_module, "obtener_categorias", return_value=[{"nombre": "Streaming", "visible": 1}, {"nombre": "Oculta", "visible": 0}]):
            html = self.client.get("/revendedores/productos").get_data(as_text=True)
        self.assertIn("Visible", html)
        self.assertIn("Perfil", html)
        self.assertIn("Sin precio", html)
        self.assertIn("Agotado", html)
        for excluido in ("Oculto", "Categoria oculta"):
            self.assertNotIn(excluido, html)

    def test_catalogo_es_solo_lectura_y_comprar_no_transacciona(self):
        resellers.guardar_precio_general(1, 11000)
        wallets.apply_wallet_transaction(self.reseller_id, "manual_credit", 40000, "Base")
        saldo_antes = wallets.obtener_saldo(self.reseller_id)
        self.autenticar()
        html = self.client.get("/revendedores/productos").get_data(as_text=True)
        self.assertIn('<button class="buy" type="button">', html)
        self.assertIn("✨ Ver planes", html)
        self.assertIn(
            'id="modalProductoComprar" class="modal-producto-comprar reseller-buy-disabled" type="button" disabled',
            html,
        )
        self.assertIn("Compra reseller próximamente", html)
        self.assertEqual(wallets.obtener_saldo(self.reseller_id), saldo_antes)


if __name__ == "__main__":
    unittest.main()
