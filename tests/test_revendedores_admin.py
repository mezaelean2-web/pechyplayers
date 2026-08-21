import os
import sqlite3
import tempfile
import unittest

from werkzeug.security import check_password_hash

import app as app_module
import database
import resellers


class RevendedoresAdminTest(unittest.TestCase):
    def setUp(self):
        descriptor, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(descriptor)
        self.original_db = database.DB
        database.DB = self.db_path
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("""CREATE TABLE productos (
            id INTEGER PRIMARY KEY, nombre TEXT NOT NULL, imagen TEXT NOT NULL DEFAULT '',
            plan TEXT NOT NULL, precio TEXT NOT NULL, oferta_precio TEXT,
            oferta_activa INTEGER DEFAULT 0, destacado INTEGER DEFAULT 0,
            visible INTEGER DEFAULT 1, orden INTEGER DEFAULT 999,
            categoria TEXT DEFAULT 'Streaming', orden_categoria INTEGER DEFAULT 999,
            estado TEXT DEFAULT 'disponible')""")
        conn.execute("INSERT INTO productos(id,nombre,plan,precio) VALUES(1,'Netflix','Perfil','15000')")
        conn.commit()
        conn.close()
        resellers.inicializar_revendedores()
        app_module.app.config.update(TESTING=True, SECRET_KEY="test-only")
        self.client = app_module.app.test_client()
        with self.client.session_transaction() as session:
            session["admin"] = True
            session["csrf_revendedores"] = "csrf-test"
        self.headers = {"X-CSRF-Token": "csrf-test"}

    def tearDown(self):
        database.DB = self.original_db
        os.remove(self.db_path)

    def crear(self, correo="reseller@example.com"):
        return self.client.post("/admin/revendedores", json={
            "nombre": "Revendedor Prueba", "negocio": "Negocio",
            "correo": correo, "telefono": "+57 300 123 4567",
            "password": "ClaveSegura123"
        }, headers=self.headers)

    def test_acceso_y_partial_requieren_admin(self):
        anonimo = app_module.app.test_client()
        self.assertEqual(anonimo.get("/admin/revendedores").status_code, 302)
        self.assertEqual(anonimo.get("/admin/revendedores/1/control").status_code, 401)
        self.assertEqual(self.client.get("/admin/revendedores").status_code, 200)

    def test_creacion_hash_duplicado_csrf_e_id_inexistente(self):
        self.assertEqual(self.client.post("/admin/revendedores", json={}, headers={"X-CSRF-Token": "incorrecto"}).status_code, 403)
        respuesta = self.crear()
        self.assertEqual(respuesta.status_code, 201)
        reseller_id = respuesta.get_json()["revendedor_id"]
        conn = sqlite3.connect(self.db_path)
        hash_guardado = conn.execute("SELECT password_hash FROM revendedores WHERE id=?", (reseller_id,)).fetchone()[0]
        conn.close()
        self.assertNotEqual(hash_guardado, "ClaveSegura123")
        self.assertTrue(check_password_hash(hash_guardado, "ClaveSegura123"))
        self.assertEqual(self.crear("RESELLER@example.com").status_code, 400)
        self.assertEqual(self.client.get(f"/admin/revendedores/{reseller_id}/control").status_code, 200)
        self.assertEqual(self.client.get("/admin/revendedores/999/control").status_code, 404)

    def test_bloqueo_precio_override_jerarquia_y_restauracion(self):
        reseller_id = self.crear().get_json()["revendedor_id"]
        activo = self.client.get("/admin/revendedores").get_data(as_text=True)
        self.assertIn('<strong>1</strong><i data-lucide="badge-check">', activo)
        self.assertIn('<strong>0</strong><i data-lucide="shield-ban">', activo)
        self.assertIn('data-status="activo"', activo)
        self.assertIn('reseller-status is-activo">Activo', activo)

        bloqueo = self.client.post(f"/admin/revendedores/{reseller_id}/estado", json={"estado": "bloqueado"}, headers=self.headers)
        self.assertEqual(bloqueo.status_code, 200)
        self.assertEqual(resellers.obtener_revendedor(reseller_id)["estado"], "bloqueado")
        bloqueado = self.client.get("/admin/revendedores").get_data(as_text=True)
        self.assertIn('<strong>0</strong><i data-lucide="badge-check">', bloqueado)
        self.assertIn('<strong>1</strong><i data-lucide="shield-ban">', bloqueado)
        self.assertIn('data-status="bloqueado"', bloqueado)
        self.assertIn('reseller-status is-bloqueado">Bloqueado', bloqueado)
        control_bloqueado = self.client.get(f"/admin/revendedores/{reseller_id}/control").get_data(as_text=True)
        self.assertIn("El acceso está bloqueado.", control_bloqueado)
        self.assertIn('data-reseller-state="activo"', control_bloqueado)

        desbloqueo = self.client.post(f"/admin/revendedores/{reseller_id}/estado", json={"estado": "activo"}, headers=self.headers)
        self.assertEqual(desbloqueo.status_code, 200)
        self.assertEqual(resellers.obtener_revendedor(reseller_id)["estado"], "activo")
        desbloqueado = self.client.get("/admin/revendedores").get_data(as_text=True)
        self.assertIn('<strong>1</strong><i data-lucide="badge-check">', desbloqueado)
        self.assertIn('<strong>0</strong><i data-lucide="shield-ban">', desbloqueado)
        self.assertIn('data-status="activo"', desbloqueado)

        self.assertEqual(self.client.put("/admin/revendedores/precios/generales/1", json={"precio": 11000}, headers=self.headers).status_code, 200)
        self.assertEqual(resellers.resolver_precio_revendedor(1, reseller_id), {"precio": 11000, "origen": "precio_general"})
        override = self.client.put(f"/admin/revendedores/{reseller_id}/precios/1", json={"precio": 9000, "oferta_activa": True, "oferta_precio": 8000}, headers=self.headers)
        self.assertEqual(override.status_code, 200)
        self.assertEqual(resellers.resolver_precio_revendedor(1, reseller_id), {"precio": 8000, "origen": "oferta_personalizada"})
        restaurar = self.client.delete(f"/admin/revendedores/{reseller_id}/precios/1", headers=self.headers)
        self.assertEqual(restaurar.status_code, 200)
        self.assertEqual(resellers.resolver_precio_revendedor(1, reseller_id), {"precio": 11000, "origen": "precio_general"})
        self.assertEqual(self.client.put(f"/admin/revendedores/{reseller_id}/precios/999", json={"precio": 1}, headers=self.headers).status_code, 404)

    def test_filtros_comparten_estado_real_con_badge_y_respetan_hidden(self):
        activo_id = self.crear("activo@example.com").get_json()["revendedor_id"]
        bloqueado_id = self.crear("jose@example.com").get_json()["revendedor_id"]
        resellers.cambiar_estado_revendedor(bloqueado_id, "bloqueado")
        pagina = self.client.get("/admin/revendedores").get_data(as_text=True)

        self.assertIn(f'data-reseller-id="{activo_id}" data-status="activo"', pagina)
        self.assertIn(f'data-reseller-id="{bloqueado_id}" data-status="bloqueado"', pagina)
        self.assertIn('data-reseller-filter="activo">Activos', pagina)
        self.assertIn('data-reseller-filter="bloqueado">Bloqueados', pagina)
        with open("static/css/admin/revendedores.css", encoding="utf-8") as archivo:
            self.assertIn(".reseller-card[hidden]{display:none}", archivo.read())
        with open("static/js/admin/revendedores.js", encoding="utf-8") as archivo:
            javascript = archivo.read()
        self.assertIn("card.dataset.status === currentFilter", javascript)
        self.assertIn('(card.dataset.search || "").includes(term)', javascript)
        self.assertIn("empty.hidden = visible !== 0", javascript)

    def test_actualizacion_devuelve_datos_normalizados_para_la_tarjeta(self):
        reseller_id = self.crear().get_json()["revendedor_id"]
        respuesta = self.client.patch(f"/admin/revendedores/{reseller_id}", json={
            "nombre": "  Nombre Nuevo  ", "negocio": "Nueva Empresa",
            "correo": "NUEVO@EXAMPLE.COM", "telefono": "+57 310 987 6543"
        }, headers=self.headers)
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.get_json()["revendedor"], {
            "nombre": "Nombre Nuevo", "negocio": "Nueva Empresa",
            "correo": "nuevo@example.com", "telefono": "+573109876543"
        })

    def test_partial_incluye_busqueda_local_de_producto_y_plan(self):
        reseller_id = self.crear().get_json()["revendedor_id"]
        partial = self.client.get(f"/admin/revendedores/{reseller_id}/control").get_data(as_text=True)
        self.assertIn("data-reseller-price-search", partial)
        self.assertIn('data-price-search="netflix perfil"', partial)
        self.assertIn("No encontramos productos o planes con esa búsqueda.", partial)
        with open("static/js/admin/revendedores.js", encoding="utf-8") as archivo:
            javascript = archivo.read()
        self.assertIn("terms.every(term => haystack.includes(term))", javascript)
        self.assertIn("window.setTimeout(closeControl, 450)", javascript)
        self.assertIn("updateResellerCard(id, data.revendedor)", javascript)


if __name__ == "__main__":
    unittest.main()
