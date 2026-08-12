import io
import os
import sqlite3
import tempfile
import unittest

import database
import configuracion_centro as centro
from app import app


class ConfiguracionCentroTest(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".db"); os.close(fd)
        self.original = database.DB; database.DB = self.path
        conn = sqlite3.connect(self.path)
        conn.execute("CREATE TABLE config(clave TEXT PRIMARY KEY, valor TEXT)")
        conn.executemany("INSERT INTO config VALUES(?,?)", [
            ("nombre_negocio", "PECHY PLAYERS"), ("whatsapp", "573147735950"),
            ("color_principal", "#e50914"), ("color_secundario", "#18191d"),
            ("color_acento", "#d4af37"), ("inicio_hero_activo", "1"),
            ("inicio_boton_catalogo", "Explorar catálogo →")])
        conn.commit(); conn.close()
        self.cliente = app.test_client()
        with self.cliente.session_transaction() as sesion: sesion["admin"] = True

    def tearDown(self):
        database.DB = self.original; os.remove(self.path)

    def test_defaults_preservan_diseno_actual(self):
        efectiva = centro.configuracion_efectiva()
        self.assertEqual(efectiva["nombre_negocio"], "PECHY PLAYERS")
        self.assertEqual(efectiva["color_principal"], "#e50914")
        self.assertEqual(efectiva["whatsapp"], "573147735950")

    def test_borrador_no_cambia_publicado_hasta_publicar(self):
        centro.guardar_borrador("identidad", {"nombre_negocio": "Stream House"})
        self.assertEqual(centro.configuracion_efectiva()["nombre_negocio"], "PECHY PLAYERS")
        self.assertEqual(centro.configuracion_efectiva(borrador=True)["nombre_negocio"], "Stream House")
        centro.publicar()
        self.assertEqual(centro.configuracion_efectiva()["nombre_negocio"], "Stream House")

    def test_restaurar_modulo_no_toca_otros(self):
        centro.guardar_borrador("identidad", {"nombre_negocio": "Otra"})
        centro.guardar_borrador("contacto", {"whatsapp": "+57 300 111 2233"})
        centro.restaurar_modulo("identidad")
        self.assertEqual(centro.obtener_modulo("identidad")["borrador"]["nombre_negocio"], "PECHY PLAYERS")
        self.assertEqual(centro.obtener_modulo("contacto")["borrador"]["whatsapp"], "573001112233")

    def test_color_whatsapp_mensaje_mantenimiento_y_white_label(self):
        centro.guardar_borrador("apariencia", {"brand_primary": "#123abc"})
        centro.guardar_borrador("mensajes", {"bienvenida": "Hola {cliente}, bienvenido a {negocio}."})
        centro.guardar_borrador("sistema", {"mantenimiento": True})
        centro.guardar_borrador("cliente", {"activo": True, "marca": "Marca Cliente"})
        self.assertEqual(centro.obtener_modulo("apariencia")["borrador"]["brand_primary"], "#123abc")
        self.assertTrue(centro.obtener_modulo("sistema")["borrador"]["mantenimiento"])
        self.assertEqual(centro.obtener_modulo("cliente")["borrador"]["marca"], "Marca Cliente")

    def test_rechaza_campos_variables_urls_y_upload_invalidos(self):
        with self.assertRaises(ValueError): centro.guardar_borrador("identidad", {"css": "body{}"})
        with self.assertRaises(ValueError): centro.guardar_borrador("mensajes", {"compra": "{codigo}"})
        with self.assertRaises(ValueError): centro.guardar_borrador("contacto", {"instagram": "javascript:alert(1)"})
        respuesta = self.cliente.post("/admin/configuracion/api/upload", data={"archivo": (io.BytesIO(b"no-image"), "logo.png")}, content_type="multipart/form-data")
        self.assertEqual(respuesta.status_code, 400)

    def test_tenants_no_se_mezclan(self):
        centro.guardar_borrador("identidad", {"nombre_negocio": "A"}, tenant="a")
        centro.guardar_borrador("identidad", {"nombre_negocio": "B"}, tenant="b")
        self.assertEqual(centro.obtener_modulo("identidad", "a")["borrador"]["nombre_negocio"], "A")
        self.assertEqual(centro.obtener_modulo("identidad", "b")["borrador"]["nombre_negocio"], "B")

    def test_restauracion_global_y_auditoria_sin_secretos(self):
        centro.guardar_borrador("identidad", {"nombre_negocio": "X"})
        centro.guardar_borrador("apariencia", {"brand_primary": "#112233"})
        centro.restaurar_todo(); estado = centro.estado_general()
        self.assertEqual(estado["modulos"]["identidad"]["borrador"]["nombre_negocio"], "PECHY PLAYERS")
        self.assertEqual(estado["modulos"]["apariencia"]["borrador"]["brand_primary"], "#e50914")
        eventos = centro.auditoria()
        self.assertTrue(any(e["accion"] == "restaurar_global" for e in eventos))
        self.assertNotIn("password", str(eventos).lower())

    def test_api_uniforme_y_confirmacion_fuerte(self):
        r = self.cliente.patch("/admin/configuracion/api/identidad", json={"datos": {"nombre_corto": "PP"}})
        self.assertEqual(r.status_code, 200); self.assertTrue(r.get_json()["pendiente"])
        self.assertEqual(self.cliente.post("/admin/configuracion/api/restaurar-todo", json={"confirmacion": "si"}).status_code, 400)
        self.assertEqual(self.cliente.post("/admin/configuracion/api/publicar", json={}).status_code, 200)

    def test_publicacion_hace_rollback_si_falla_auditoria(self):
        centro.guardar_borrador("identidad", {"nombre_negocio": "No publicar"})
        conn = sqlite3.connect(self.path)
        conn.execute("CREATE TRIGGER fallo_publicacion BEFORE INSERT ON configuracion_auditoria WHEN NEW.accion='publicar' BEGIN SELECT RAISE(ABORT,'fallo'); END")
        conn.commit(); conn.close()
        with self.assertRaises(sqlite3.IntegrityError): centro.publicar()
        self.assertEqual(centro.obtener_modulo("identidad")["publicado"]["nombre_negocio"], "PECHY PLAYERS")


if __name__ == "__main__": unittest.main()
