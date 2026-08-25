try:
    from tests._bootstrap import TEST_DB
except ModuleNotFoundError:
    from _bootstrap import TEST_DB

import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

import database
import reseller_accounts
import resellers
from app import app


class DuracionManualInventarioTest(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.original_db = database.DB
        database.DB = self.path
        conn = sqlite3.connect(self.path)
        conn.execute("""CREATE TABLE productos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT, imagen TEXT, plan TEXT, precio TEXT
        )""")
        conn.commit()
        conn.close()
        database.inicializar_db()
        resellers.inicializar_revendedores()
        self.client = app.test_client()
        with self.client.session_transaction() as session:
            session["admin"] = True

    def tearDown(self):
        database.DB = self.original_db
        try:
            os.remove(self.path)
        except PermissionError:
            pass

    def _post_individual(self, plataforma, duracion, indice):
        return self.client.post("/admin/nube-cuentas/nueva", data={
            "plataforma": plataforma,
            "correo": f"individual-{indice}@example.com",
            "contrasena": "clave-segura",
            "tipo_cuenta": "cuenta_completa",
            "duracion_unidad_dias": duracion,
        })

    def _post_lote(self, plataforma, duracion, prefijo):
        return self.client.post("/admin/nube-cuentas/carga-rapida", json={
            "plataforma": plataforma,
            "modalidad": "cuenta_completa",
            "tipo_pago": "",
            "plan_pago": "",
            "cantidad_perfiles": 0,
            "duracion_unidad_dias": duracion,
            "credenciales": [
                {"correo": f"{prefijo}-1@example.com", "contrasena": "clave-1"},
                {"correo": f"{prefijo}-2@example.com", "contrasena": "clave-2"},
            ],
        })

    def test_mapeos_individuales_youtube_y_spotify(self):
        casos = [
            ("YouTube Premium", 30), ("youtube premium", 90), ("YouTube", 180),
            ("Spotify Premium", 60), ("Spotify", 150),
        ]
        for indice, (plataforma, dias) in enumerate(casos):
            respuesta = self._post_individual(plataforma, str(dias), indice)
            self.assertEqual(respuesta.status_code, 302)
        conn = database.conectar()
        valores = [fila[0] for fila in conn.execute(
            "SELECT duracion_unidad_dias FROM nube_cuentas WHERE correo LIKE 'individual-%' ORDER BY id"
        ).fetchall()]
        conn.close()
        self.assertEqual(valores, [30, 90, 180, 60, 150])

    def test_lotes_guardan_una_duracion_uniforme(self):
        youtube = self._post_lote("YouTube Premium", 120, "youtube-lote")
        spotify = self._post_lote("Spotify Premium", 180, "spotify-lote")
        self.assertEqual((youtube.status_code, spotify.status_code), (200, 200))
        conn = database.conectar()
        youtube_dias = [fila[0] for fila in conn.execute(
            "SELECT duracion_unidad_dias FROM nube_cuentas WHERE correo LIKE 'youtube-lote-%'"
        ).fetchall()]
        spotify_dias = [fila[0] for fila in conn.execute(
            "SELECT duracion_unidad_dias FROM nube_cuentas WHERE correo LIKE 'spotify-lote-%'"
        ).fetchall()]
        conn.close()
        self.assertEqual(youtube_dias, [120, 120])
        self.assertEqual(spotify_dias, [180, 180])

    def test_requerida_y_valores_manipulados_se_rechazan(self):
        for indice, valor in enumerate(["", 45, 75, 365, 9999]):
            respuesta = self._post_lote("YouTube Premium", valor, f"invalido-{indice}")
            self.assertEqual(respuesta.status_code, 409)
            self.assertFalse(respuesta.get_json()["ok"])
            individual = self._post_individual("Spotify Premium", str(valor), f"invalido-{indice}")
            self.assertEqual(individual.status_code, 302)
        conn = database.conectar()
        total = conn.execute(
            "SELECT COUNT(*) FROM nube_cuentas WHERE correo LIKE 'invalido-%' OR correo LIKE 'individual-invalido-%'"
        ).fetchone()[0]
        conn.close()
        self.assertEqual(total, 0)

    def test_plataforma_normal_descarta_duracion_residual(self):
        respuesta = self._post_lote("Netflix", 90, "netflix")
        self.assertEqual(respuesta.status_code, 200)
        conn = database.conectar()
        valores = [fila[0] for fila in conn.execute(
            "SELECT duracion_unidad_dias FROM nube_cuentas WHERE correo LIKE 'netflix-%'"
        ).fetchall()]
        conn.close()
        self.assertEqual(valores, [None, None])

    def test_selector_limpia_al_cambiar_y_vuelve_a_exigir(self):
        fuente = Path(app.root_path, "static", "js", "admin", "nube_cuentas.js").read_text(encoding="utf-8")
        self.assertIn("const duracionesInventarioManual = [30, 60, 90, 120, 150, 180]", fuente)
        self.assertIn('tokens.includes("youtube") || tokens.includes("spotify")', fuente)
        self.assertIn('select.value = "";', fuente)
        self.assertIn("select.required = requiere", fuente)
        self.assertIn("select.disabled = !requiere", fuente)
        self.assertIn('plataformaNueva?.addEventListener("input", refrescarDuracionNueva)', fuente)
        self.assertIn('plataformaCargaRapida?.addEventListener("change", refrescarDuracionCargaRapida)', fuente)

    def test_reglas_30_90_180_separan_inventario_y_excluyen_null(self):
        conn = database.conectar()
        ids = {}
        for dias in (None, 30, 90, 180):
            correo = f"youtube-{dias}@example.com"
            ids[dias] = conn.execute(
                "INSERT INTO nube_cuentas(plataforma,correo,modalidad,estado,duracion_unidad_dias) "
                "VALUES ('YouTube Premium',?,'cuenta_completa','disponible',?)",
                (correo, dias),
            ).lastrowid
        cursor = conn.cursor()
        encontrados = {}
        for dias in (30, 90, 180):
            unidades = reseller_accounts._unidades_elegibles_en_cursor(cursor, {
                "plataforma": "YouTube Premium", "tipo_unidad": "cuenta", "duracion_dias": dias,
            })
            encontrados[dias] = [unidad["cuenta_id"] for unidad in unidades]
        conn.close()
        self.assertEqual(encontrados, {30: [ids[30]], 90: [ids[90]], 180: [ids[180]]})
        self.assertNotIn(ids[None], sum(encontrados.values(), []))


if __name__ == "__main__":
    unittest.main()
