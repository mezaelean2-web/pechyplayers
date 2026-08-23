try:
    from tests._bootstrap import TEST_DB
except ModuleNotFoundError:
    from _bootstrap import TEST_DB

import io
import os
import shutil
import sqlite3
import tempfile
import unittest

from PIL import Image

import app as app_module
import configuracion_centro as centro
import database


def imagen_prueba(color):
    salida = io.BytesIO()
    Image.new("RGB", (320, 180), color).save(salida, "PNG")
    salida.seek(0)
    return salida


class ImagenesResponsiveTest(unittest.TestCase):
    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.assets = tempfile.mkdtemp()
        self.db_original = database.DB
        self.promo_original = app_module.PROMO_FOLDER
        database.DB = self.db_path
        app_module.PROMO_FOLDER = self.assets
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE productos(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT, imagen TEXT, plan TEXT, precio TEXT
            )
        """)
        conn.commit()
        conn.close()
        database.inicializar_db()
        self.cliente = app_module.app.test_client()
        with self.cliente.session_transaction() as sesion:
            sesion["admin"] = True

    def tearDown(self):
        database.DB = self.db_original
        app_module.PROMO_FOLDER = self.promo_original
        shutil.rmtree(self.assets)
        os.remove(self.db_path)

    def test_migracion_promocion_antigua_es_no_destructiva(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("DROP TABLE promociones")
        conn.execute("CREATE TABLE promociones(id INTEGER PRIMARY KEY, imagen TEXT NOT NULL, activa INTEGER DEFAULT 1, orden INTEGER DEFAULT 999)")
        conn.execute("INSERT INTO promociones(imagen, activa, orden) VALUES('antigua.jpg', 1, 1)")
        conn.commit()
        conn.close()

        promociones = database.obtener_promociones()
        self.assertEqual(promociones[0][1], "antigua.jpg")
        self.assertIsNone(promociones[0][3])

    def test_fallback_desktop_mobile_y_archivo_ausente(self):
        for nombre in ("mobile.webp", "desktop.webp"):
            with open(os.path.join(self.assets, nombre), "wb") as archivo:
                archivo.write(b"imagen")
        solo_mobile = app_module.resolver_variantes_promociones([(1, "mobile.webp", 1, None)])
        ambas = app_module.resolver_variantes_promociones([(2, "mobile.webp", 1, "desktop.webp")])
        mobile_ausente = app_module.resolver_variantes_promociones([(3, "no-existe.webp", 1, "desktop.webp")])
        self.assertEqual(solo_mobile[0][3], "mobile.webp")
        self.assertEqual(ambas[0][1:], ("mobile.webp", 1, "desktop.webp"))
        self.assertEqual(mobile_ausente[0][1], "desktop.webp")

    def test_promocion_guarda_variantes_sin_mezclarlas(self):
        respuesta = self.cliente.post("/agregar-promocion", data={
            "activa": "on",
            "imagen": (imagen_prueba("red"), "mobile.png"),
            "imagen_desktop": (imagen_prueba("blue"), "desktop.png"),
        }, content_type="multipart/form-data")
        self.assertEqual(respuesta.status_code, 302)
        promo = database.obtener_promociones()[0]
        mobile_inicial, desktop_inicial = promo[1], promo[3]
        self.assertNotEqual(mobile_inicial, desktop_inicial)

        self.cliente.post("/actualizar-promocion", data={
            "id": promo[0], "activa": "on",
            "imagen_desktop": (imagen_prueba("green"), "desktop-nueva.png"),
        }, content_type="multipart/form-data")
        actualizada = database.obtener_promociones()[0]
        self.assertEqual(actualizada[1], mobile_inicial)
        self.assertNotEqual(actualizada[3], desktop_inicial)

        desktop_actual = actualizada[3]
        self.cliente.post("/actualizar-promocion", data={
            "id": promo[0], "activa": "on",
            "imagen": (imagen_prueba("yellow"), "mobile-nueva.png"),
        }, content_type="multipart/form-data")
        actualizada_mobile = database.obtener_promociones()[0]
        self.assertNotEqual(actualizada_mobile[1], mobile_inicial)
        self.assertEqual(actualizada_mobile[3], desktop_actual)

    def test_eliminar_mobile_conserva_desktop(self):
        self.cliente.post("/agregar-promocion", data={
            "activa": "on",
            "imagen": (imagen_prueba("red"), "mobile.png"),
            "imagen_desktop": (imagen_prueba("blue"), "desktop.png"),
        }, content_type="multipart/form-data")
        promo = database.obtener_promociones()[0]
        desktop_inicial = promo[3]

        respuesta = self.cliente.post("/actualizar-promocion", data={
            "id": promo[0], "activa": "on", "eliminar_imagen": "1",
        }, content_type="multipart/form-data")

        self.assertEqual(respuesta.status_code, 302)
        actualizada = database.obtener_promociones()[0]
        self.assertEqual(actualizada[1], "")
        self.assertEqual(actualizada[3], desktop_inicial)
        self.assertEqual(
            app_module.resolver_variantes_promociones([actualizada])[0][1],
            desktop_inicial,
        )

    def test_eliminar_desktop_conserva_mobile(self):
        self.cliente.post("/agregar-promocion", data={
            "activa": "on",
            "imagen": (imagen_prueba("red"), "mobile.png"),
            "imagen_desktop": (imagen_prueba("blue"), "desktop.png"),
        }, content_type="multipart/form-data")
        promo = database.obtener_promociones()[0]
        mobile_inicial = promo[1]

        respuesta = self.cliente.post("/actualizar-promocion", data={
            "id": promo[0], "activa": "on", "eliminar_imagen_desktop": "1",
        }, content_type="multipart/form-data")

        self.assertEqual(respuesta.status_code, 302)
        actualizada = database.obtener_promociones()[0]
        self.assertEqual(actualizada[1], mobile_inicial)
        self.assertIsNone(actualizada[3])
        self.assertEqual(
            app_module.resolver_variantes_promociones([actualizada])[0][3],
            mobile_inicial,
        )

    def test_configuracion_hero_variantes_y_white_label(self):
        centro.guardar_borrador("inicio", {
            "hero_imagen_mobile": "/static/uploads/configuracion/default/mobile.webp",
            "hero_imagen_desktop": "/static/uploads/configuracion/default/desktop.webp",
        })
        centro.guardar_borrador("cliente", {"activo": True, "marca": "Marca Demo"})
        efectiva = centro.configuracion_efectiva(borrador=True)
        self.assertEqual(efectiva["modulos"]["inicio"]["hero_imagen_mobile_efectiva"], "/static/uploads/configuracion/default/mobile.webp")
        self.assertEqual(efectiva["modulos"]["inicio"]["hero_imagen_desktop_efectiva"], "/static/uploads/configuracion/default/desktop.webp")
        self.assertEqual(efectiva["modulos"]["cliente"]["marca"], "Marca Demo")

    def test_hero_solo_mobile_y_fallback_historico(self):
        centro.guardar_borrador("inicio", {"hero_imagen_mobile": "/static/uploads/configuracion/default/mobile.webp"})
        solo_mobile = centro.configuracion_efectiva(borrador=True)
        self.assertEqual(solo_mobile["hero_imagen_desktop_efectiva"], "/static/uploads/configuracion/default/mobile.webp")
        centro.guardar_borrador("inicio", {
            "hero_imagen": "/static/uploads/configuracion/default/legacy.webp",
            "hero_imagen_mobile": "",
        })
        historico = centro.configuracion_efectiva(borrador=True)
        self.assertEqual(historico["hero_imagen_mobile_efectiva"], "/static/uploads/configuracion/default/legacy.webp")

    def test_hero_borrador_publicacion_y_restauracion(self):
        mobile = "/static/uploads/configuracion/default/mobile.webp"
        desktop = "/static/uploads/configuracion/default/desktop.webp"
        centro.guardar_borrador("inicio", {"hero_imagen_mobile": mobile, "hero_imagen_desktop": desktop})
        self.assertEqual(centro.configuracion_efectiva()["hero_imagen_mobile_efectiva"], "")
        centro.publicar()
        self.assertEqual(centro.configuracion_efectiva()["hero_imagen_desktop_efectiva"], desktop)
        centro.restaurar_modulo("inicio")
        self.assertEqual(centro.configuracion_efectiva()["hero_imagen_desktop_efectiva"], desktop)
        self.assertEqual(centro.configuracion_efectiva(borrador=True)["hero_imagen_desktop_efectiva"], "")

    def test_variantes_hero_aisladas_por_tenant(self):
        centro.guardar_borrador("inicio", {"hero_imagen_mobile": "/static/uploads/configuracion/a/a.webp"}, tenant="a")
        centro.guardar_borrador("inicio", {"hero_imagen_mobile": "/static/uploads/configuracion/b/b.webp"}, tenant="b")
        self.assertNotEqual(
            centro.configuracion_efectiva("a", borrador=True)["hero_imagen_mobile_efectiva"],
            centro.configuracion_efectiva("b", borrador=True)["hero_imagen_mobile_efectiva"],
        )

    def test_asset_rechaza_traversal(self):
        with self.assertRaises(ValueError):
            centro.guardar_borrador("inicio", {"hero_imagen_mobile": "/static/uploads/configuracion/default/../secreto.png"})

    def test_upload_promocion_invalido_no_crea_registro(self):
        respuesta = self.cliente.post("/agregar-promocion", data={
            "activa": "on", "imagen": (io.BytesIO(b"<script>alert(1)</script>"), "foto.png")
        }, content_type="multipart/form-data")
        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(database.obtener_promociones(), [])

    def test_inicio_responde_con_promocion_legacy(self):
        with open(os.path.join(self.assets, "legacy.webp"), "wb") as archivo:
            archivo.write(b"imagen")
        conn = database.conectar()
        conn.execute("INSERT INTO promociones(imagen, activa, orden) VALUES('legacy.webp', 1, 1)")
        conn.execute("INSERT INTO cartelera(titulo, categoria, publicado, orden) VALUES('Prueba', 'Otros', 1, 1)")
        conn.commit()
        conn.close()
        respuesta = self.cliente.get("/")
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn(b"legacy.webp", respuesta.data)


if __name__ == "__main__":
    unittest.main()
