try:
    from tests._bootstrap import TEST_DB
except ModuleNotFoundError:
    from _bootstrap import TEST_DB

import io
import os
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

import app as app_module
import database
import resellers


class ProductosResellerAdminTest(unittest.TestCase):
    def setUp(self):
        descriptor, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(descriptor)
        self.original_db = database.DB
        database.DB = self.db_path
        conn = sqlite3.connect(self.db_path)
        conn.execute("""CREATE TABLE productos (
            id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT NOT NULL,
            imagen TEXT NOT NULL DEFAULT '', plan TEXT NOT NULL, precio TEXT NOT NULL,
            oferta_precio TEXT, oferta_activa INTEGER DEFAULT 0, destacado INTEGER DEFAULT 0,
            visible INTEGER DEFAULT 1, orden INTEGER DEFAULT 999,
            categoria TEXT DEFAULT 'Streaming', orden_categoria INTEGER DEFAULT 999,
            estado TEXT DEFAULT 'disponible')""")
        conn.execute("INSERT INTO productos(nombre,imagen,plan,precio) VALUES('Existente','x.webp','Perfil','15000')")
        conn.commit()
        conn.close()
        resellers.inicializar_revendedores()
        app_module.app.config.update(TESTING=True, SECRET_KEY="productos-reseller")
        self.client = app_module.app.test_client()
        with self.client.session_transaction() as session:
            session["admin"] = True
            session["csrf_revendedores"] = "csrf-productos"

    def tearDown(self):
        database.DB = self.original_db
        os.remove(self.db_path)

    @staticmethod
    def imagen():
        salida = io.BytesIO()
        Image.new("RGB", (2, 2), "red").save(salida, format="PNG")
        salida.seek(0)
        return salida

    def crear(self, nombre, **campos):
        datos = {"nombre": nombre, "categoria": "Streaming", "csrf_token": "csrf-productos", "imagen": (self.imagen(), "plan.png")}
        datos.update(campos)
        with patch.object(app_module, "obtener_categorias", return_value=[{"nombre": "Streaming"}]), patch.object(app_module, "guardar_imagen_optimizada", return_value="plan.webp"):
            return self.client.post("/agregar-producto", data=datos, content_type="multipart/form-data")

    def test_crea_ambos_planes_con_precios_generales_independientes(self):
        respuesta = self.crear(
            "Nuevo", cuenta_completa_activa="on", precio_cuenta_completa="45.000",
            precio_reseller_cuenta_completa="38.000", perfil_activo="on",
            precio_perfil="15.000", precio_reseller_perfil="11.000"
        )
        self.assertEqual(respuesta.status_code, 302)
        conn = sqlite3.connect(self.db_path)
        filas = conn.execute("""SELECT p.plan,p.precio,g.precio FROM productos p
            LEFT JOIN precios_revendedor_generales g ON g.plan_id=p.id
            WHERE p.nombre='Nuevo' ORDER BY p.id""").fetchall()
        conn.close()
        self.assertEqual(filas, [("Cuenta completa", "45.000", 38000), ("Perfil", "15.000", 11000)])

    def test_plan_unico_vacio_queda_sin_precio_y_control_permite_guardarlo(self):
        self.crear("Solo perfil", perfil_activo="on", precio_perfil="15.000", precio_reseller_perfil="")
        conn = sqlite3.connect(self.db_path)
        plan_id = conn.execute("SELECT id FROM productos WHERE nombre='Solo perfil'").fetchone()[0]
        self.assertIsNone(conn.execute("SELECT precio FROM precios_revendedor_generales WHERE plan_id=?", (plan_id,)).fetchone())
        conn.close()
        with patch.object(app_module, "obtener_categorias", return_value=[{"nombre": "Streaming"}]):
            control = self.client.get(f"/admin/productos/{plan_id}/control")
        self.assertEqual(control.status_code, 200)
        self.assertIn("Sin precio reseller configurado", control.get_data(as_text=True))
        guardado = self.client.put(
            f"/admin/revendedores/precios/generales/{plan_id}", json={"precio": 11000},
            headers={"X-CSRF-Token": "csrf-productos"}
        )
        self.assertEqual(guardado.status_code, 200)
        self.assertEqual(resellers.resolver_precio_revendedor(plan_id, 999), {"precio": 11000, "origen": "precio_general"})

    def test_error_del_precio_relacionado_revierte_todos_los_planes(self):
        with patch.object(resellers, "guardar_precio_general_en_cursor", side_effect=RuntimeError("fallo")):
            self.crear("Rollback", perfil_activo="on", precio_perfil="15.000", precio_reseller_perfil="11.000")
        conn = sqlite3.connect(self.db_path)
        cantidad = conn.execute("SELECT COUNT(*) FROM productos WHERE nombre='Rollback'").fetchone()[0]
        conn.close()
        self.assertEqual(cantidad, 0)

    def test_precio_reseller_en_creacion_requiere_csrf(self):
        datos = {
            "nombre": "Sin CSRF", "categoria": "Streaming", "perfil_activo": "on",
            "precio_perfil": "15000", "precio_reseller_perfil": "11000",
            "imagen": (self.imagen(), "plan.png")
        }
        with patch.object(app_module, "obtener_categorias", return_value=[{"nombre": "Streaming"}]):
            respuesta = self.client.post("/agregar-producto", data=datos, content_type="multipart/form-data")
        self.assertEqual(respuesta.status_code, 302)
        conn = sqlite3.connect(self.db_path)
        cantidad = conn.execute("SELECT COUNT(*) FROM productos WHERE nombre='Sin CSRF'").fetchone()[0]
        conn.close()
        self.assertEqual(cantidad, 0)


if __name__ == "__main__":
    unittest.main()
