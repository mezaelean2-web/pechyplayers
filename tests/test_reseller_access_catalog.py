try:
    from tests._bootstrap import TEST_DB
except ModuleNotFoundError:
    from _bootstrap import TEST_DB

import os
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from werkzeug.security import check_password_hash

import app as app_module
import database
import resellers


class ResellerAccessCatalogTest(unittest.TestCase):
    def setUp(self):
        descriptor, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(descriptor)
        self.original_db = database.DB
        database.DB = self.db_path
        conn = sqlite3.connect(self.db_path)
        conn.execute("""CREATE TABLE productos (
          id INTEGER PRIMARY KEY, nombre TEXT NOT NULL, imagen TEXT NOT NULL DEFAULT 'netflix.jpg',
          plan TEXT NOT NULL, precio TEXT NOT NULL, oferta_precio TEXT, oferta_activa INTEGER DEFAULT 0,
          destacado INTEGER DEFAULT 0, visible INTEGER DEFAULT 1, orden INTEGER DEFAULT 1,
          categoria TEXT DEFAULT 'Streaming', orden_categoria INTEGER DEFAULT 1,
          estado TEXT DEFAULT 'disponible')""")
        conn.executemany("INSERT INTO productos(id,nombre,plan,precio) VALUES(?,?,?,?)", [
            (1, "Netflix", "Perfil", "15000"), (2, "Netflix", "Cuenta completa", "30000"),
            (3, "MAX", "Perfil", "14000")
        ])
        conn.commit(); conn.close()
        resellers.inicializar_revendedores()
        app_module.app.config.update(TESTING=True, SECRET_KEY="test-reseller-access")
        app_module._intentos_login_reseller.clear()
        self.client = app_module.app.test_client()

    def tearDown(self):
        database.DB = self.original_db
        os.remove(self.db_path)

    def crear(self, correo, password="ClaveSegura123"):
        return resellers.crear_revendedor(
            "Persona Prueba", correo, "+57 300 123 4567", "Negocio", password,
            actor="autorregistro", tipo_actividad="registro_publico"
        )

    def token(self, client=None):
        client = client or self.client
        client.get("/revendedores/login")
        with client.session_transaction() as session:
            return session["csrf_reseller"]

    def login(self, correo, password, client=None):
        client = client or self.client
        return client.post("/revendedores/login", data={
            "csrf_token": self.token(client), "correo": correo, "password": password
        })

    def test_registro_activo_hash_duplicado_e_invalido(self):
        self.client.get("/revendedores/registro")
        with self.client.session_transaction() as session:
            token = session["csrf_reseller"]
        respuesta = self.client.post("/revendedores/registro", data={
            "csrf_token": token, "nombre": "Elean Prueba", "negocio": "Elean Store",
            "correo": "elean@example.com", "telefono": "300 123 4567",
            "password": "ClaveSegura123", "confirmar_password": "ClaveSegura123"
        })
        self.assertEqual(respuesta.status_code, 302)
        revendedor = resellers.listar_revendedores()[0]
        self.assertEqual(revendedor["estado"], "activo")
        conn = sqlite3.connect(self.db_path)
        password_hash = conn.execute("SELECT password_hash FROM revendedores").fetchone()[0]
        conn.close()
        self.assertTrue(check_password_hash(password_hash, "ClaveSegura123"))
        otro = app_module.app.test_client(); otro.get("/revendedores/registro")
        with otro.session_transaction() as session: token2 = session["csrf_reseller"]
        duplicado = otro.post("/revendedores/registro", data={"csrf_token": token2, "nombre": "Otro", "correo": "ELEAN@example.com", "password": "ClaveSegura123", "confirmar_password": "ClaveSegura123"})
        self.assertIn("Ya existe", duplicado.get_data(as_text=True))
        invalido = otro.post("/revendedores/registro", data={"csrf_token": token2, "nombre": "Otro", "correo": "otro@example.com", "password": "corta", "confirmar_password": "corta"})
        self.assertIn("10 caracteres", invalido.get_data(as_text=True))

    def test_login_bloqueo_version_password_logout(self):
        reseller_id = self.crear("login@example.com")
        self.assertEqual(self.login("login@example.com", "incorrecta").status_code, 200)
        correcto = self.login("login@example.com", "ClaveSegura123")
        self.assertEqual(correcto.status_code, 302)
        self.assertEqual(self.client.get("/revendedores/cuenta").status_code, 200)
        resellers.cambiar_estado_revendedor(reseller_id, "bloqueado")
        expulsion = self.client.get("/revendedores/cuenta")
        self.assertEqual(expulsion.status_code, 302)
        self.assertTrue(expulsion.headers["Location"].endswith("/revendedores/login"))
        self.assertIn("temporalmente bloqueada", self.client.get(expulsion.headers["Location"]).get_data(as_text=True))
        bloqueado = self.login("login@example.com", "ClaveSegura123")
        self.assertIn("temporalmente bloqueada", bloqueado.get_data(as_text=True))
        resellers.cambiar_estado_revendedor(reseller_id, "activo")
        self.assertEqual(self.login("login@example.com", "ClaveSegura123").status_code, 302)

        sesion_anterior = app_module.app.test_client()
        self.assertEqual(self.login("login@example.com", "ClaveSegura123", sesion_anterior).status_code, 302)
        resellers.cambiar_password_revendedor(reseller_id, "NuevaClave456")
        version_expirada = sesion_anterior.get("/revendedores/cuenta")
        self.assertTrue(version_expirada.headers["Location"].endswith("/revendedores/login"))
        self.assertIn("sesión ha finalizado", sesion_anterior.get(version_expirada.headers["Location"]).get_data(as_text=True))
        self.assertIn("incorrectos", self.login("login@example.com", "ClaveSegura123").get_data(as_text=True))
        self.assertEqual(self.login("login@example.com", "NuevaClave456").status_code, 302)
        token = self.token()
        self.login("login@example.com", "NuevaClave456")
        salida = self.client.post("/revendedores/logout", data={"csrf_token": token})
        self.assertEqual(salida.status_code, 302)

    def test_cambio_password_propio_invalida_otra_sesion_y_throttling(self):
        self.crear("propio@example.com")
        principal = app_module.app.test_client()
        secundaria = app_module.app.test_client()
        self.assertEqual(self.login("propio@example.com", "ClaveSegura123", principal).status_code, 302)
        self.assertEqual(self.login("propio@example.com", "ClaveSegura123", secundaria).status_code, 302)
        principal.get("/revendedores/cuenta")
        with principal.session_transaction() as session: token = session["csrf_reseller"]
        cambio = principal.post("/revendedores/cuenta", data={
            "csrf_token": token, "accion": "password", "password_actual": "ClaveSegura123",
            "password_nueva": "PropiaNueva789", "confirmar_password": "PropiaNueva789"
        })
        self.assertIn("demás sesiones quedaron invalidadas", cambio.get_data(as_text=True))
        self.assertEqual(principal.get("/revendedores/cuenta").status_code, 200)
        self.assertEqual(secundaria.get("/revendedores/cuenta").status_code, 302)

        atacante = app_module.app.test_client()
        for _ in range(5):
            self.login("propio@example.com", "incorrecta", atacante)
        limitado = self.login("propio@example.com", "incorrecta", atacante)
        self.assertIn("Demasiados intentos", limitado.get_data(as_text=True))

    def test_contrato_modal_interno_y_whatsapp_se_conservan(self):
        with open("static/js/mobile.js", encoding="utf-8") as archivo:
            mobile = archivo.read()
        with open("templates/index.html", encoding="utf-8") as archivo:
            template = archivo.read()
        self.assertIn('evento.preventDefault();', mobile)
        self.assertIn('evento.stopPropagation();', mobile)
        self.assertIn('abrir({ navegacionInterna: true });', mobile)
        self.assertIn('productoAgotado(card) && !navegacionInterna', mobile)
        self.assertIn('id="modalProductoComprar"', template)
        self.assertIn('https://wa.me/', template)

    def test_aislamiento_general_ofertas_y_sin_fallback(self):
        reseller_a = self.crear("a@example.com")
        reseller_b = self.crear("b@example.com")
        resellers.guardar_precio_general(1, 11000)
        resellers.guardar_precio_personalizado(reseller_a, 1, 9000)
        resellers.guardar_precio_personalizado(reseller_b, 1, 10500)
        self.assertEqual(resellers.resolver_precios_revendedor(reseller_a, [1, 2])[1]["precio"], 9000)
        self.assertEqual(resellers.resolver_precios_revendedor(reseller_b, [1, 2])[1]["precio"], 10500)
        self.assertIsNone(resellers.resolver_precios_revendedor(reseller_a, [1, 2])[2]["precio"])
        resellers.guardar_precio_personalizado(reseller_a, 1, 9000, True, 8000, "2026-08-01", "2026-08-31")
        self.assertEqual(resellers.resolver_precios_revendedor(reseller_a, [1], "2026-08-20")[1]["precio"], 8000)
        self.assertEqual(resellers.resolver_precios_revendedor(reseller_a, [1], "2026-09-01")[1]["precio"], 9000)
        self.assertEqual(resellers.resolver_precios_revendedor(reseller_a, [1], "2026-07-01")[1]["precio"], 9000)

    def test_catalogo_visitante_y_reseller_usan_un_render_y_una_consulta_masiva(self):
        reseller_id = self.crear("catalogo@example.com")
        resellers.guardar_precio_general(1, 11000)
        productos = [{"nombre": "Netflix", "imagen": "netflix.jpg", "destacado": 0, "visible": 1,
                      "estado": "disponible", "categoria": "Streaming", "orden_categoria": 1,
                      "planes": [{"id": 1, "plan": "Perfil", "precio": "15000", "oferta_precio": None, "oferta_activa": 0}]}]
        pelicula = {"publicado": 1, "categoria_activa": 1, "categoria_clave": "accion", "titulo": "Prueba", "poster": "", "tipo": "Película", "plataformas": []}
        patches = [patch.object(app_module, "obtener_productos", return_value=productos), patch.object(app_module, "obtener_categorias", return_value=[]), patch.object(app_module, "obtener_promociones", return_value=[]), patch.object(app_module, "obtener_cartelera", return_value=[pelicula]), patch.object(app_module, "obtener_categorias_cartelera", return_value=[])]
        for item in patches: item.start()
        try:
            respuesta_visitante = self.client.get("/")
            self.assertEqual(respuesta_visitante.status_code, 200)
            visitante = respuesta_visitante.get_data(as_text=True)
            self.assertNotIn("Acceso revendedor", visitante)
            self.assertNotIn("/revendedores/login", visitante)
            self.assertNotIn("/revendedores/registro", visitante)
            self.assertIn('data-precio="15000"', visitante)
            with self.client.session_transaction() as session:
                session["reseller_id"] = reseller_id
                session["reseller_auth_version"] = 1
            with patch.object(resellers, "resolver_precios_revendedor", wraps=resellers.resolver_precios_revendedor) as masiva:
                reseller = self.client.get("/").get_data(as_text=True)
                self.assertEqual(masiva.call_count, 1)
            self.assertIn("TU PRECIO RESELLER", reseller)
            self.assertIn("Mi cuenta", reseller)
            self.assertIn("/revendedores/logout", reseller)
            self.assertIn('data-precio="11000"', reseller)
            self.assertNotIn('data-precio="15000"', reseller)
        finally:
            for item in reversed(patches): item.stop()

    def test_catalogo_no_degrada_sesion_reseller_invalidada_a_visitante(self):
        reseller_id = self.crear("expulsado@example.com")
        with self.client.session_transaction() as session:
            session["reseller_id"] = reseller_id
            session["reseller_auth_version"] = 1
        resellers.cambiar_estado_revendedor(reseller_id, "bloqueado")
        respuesta = self.client.get("/")
        self.assertEqual(respuesta.status_code, 302)
        self.assertTrue(respuesta.headers["Location"].endswith("/revendedores/login"))
        login = self.client.get(respuesta.headers["Location"]).get_data(as_text=True)
        self.assertIn("temporalmente bloqueada", login)

        with patch.object(app_module, "obtener_productos", return_value=[]), \
             patch.object(app_module, "obtener_categorias", return_value=[]), \
             patch.object(app_module, "obtener_promociones", return_value=[]), \
             patch.object(app_module, "obtener_cartelera", return_value=[{
                 "publicado": 1, "categoria_activa": 1, "categoria_clave": "prueba",
                 "titulo": "Prueba", "poster": "", "tipo": "PelÃ­cula", "plataformas": []
             }]), \
             patch.object(app_module, "obtener_categorias_cartelera", return_value=[]):
            visitante = app_module.app.test_client().get("/")
        self.assertEqual(visitante.status_code, 200)


if __name__ == "__main__":
    unittest.main()
