import os
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

import database


class CargaMasivaNubeTest(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".db"); os.close(fd)
        self.original = database.DB; database.DB = self.path
        conn = sqlite3.connect(self.path)
        conn.executescript("""
        CREATE TABLE nube_cuentas(
          id INTEGER PRIMARY KEY, plataforma TEXT, correo TEXT, contrasena TEXT,
          pin TEXT, tipo_cuenta TEXT, cliente_id INTEGER, nombre_cliente TEXT,
          telefono TEXT, fecha_entrega TEXT, dias_cuenta INTEGER,
          fecha_vencimiento TEXT, estado TEXT, garantia_usada INTEGER,
          cantidad_garantias INTEGER, notas TEXT, origen TEXT, modalidad TEXT,
          cantidad_perfiles INTEGER, tipo_pago TEXT, valor_pin INTEGER,
          plan_pago TEXT, precio_plan_referencia INTEGER, fecha_aplicacion_pin TEXT,
          dias_estimados_pin INTEGER, fecha_proximo_pago TEXT,
          fecha_creacion TEXT, fecha_actualizacion TEXT);
        CREATE TABLE nube_perfiles(
          id INTEGER PRIMARY KEY, cuenta_id INTEGER, nombre_perfil TEXT, pin TEXT,
          cliente_id INTEGER, nombre_cliente TEXT, telefono TEXT, fecha_entrega TEXT,
          dias_cuenta INTEGER, fecha_vencimiento TEXT, estado TEXT,
          garantia_usada INTEGER, cantidad_garantias INTEGER, notas TEXT,
          orden INTEGER, fecha_creacion TEXT, fecha_actualizacion TEXT);
        """)
        conn.executemany(
            "INSERT INTO nube_cuentas(id,plataforma,correo,estado,modalidad,cantidad_perfiles) VALUES(?,?,?,?,?,?)",
            [(1, "Netflix", "uno@test", "disponible", "perfiles", 2),
             (2, "Max", "dos@test", "disponible", "cuenta_completa", 0)])
        conn.executemany(
            "INSERT INTO nube_perfiles(id,cuenta_id,nombre_perfil,estado,orden) VALUES(?,?,?,?,?)",
            [(12, 1, "Segundo", "disponible", 2), (11, 1, "Primero", "activa", 1)])
        conn.commit(); conn.close()

    def tearDown(self):
        database.DB = self.original; os.remove(self.path)

    def test_usa_dos_selects_y_conserva_orden_y_calculos(self):
        selects = []
        conectar_original = database.conectar

        def conectar_contado():
            conn = conectar_original()
            conn.set_trace_callback(
                lambda sql: selects.append(sql)
                if sql.lstrip().upper().startswith(("SELECT", "WITH")) else None
            )
            return conn

        with patch.object(database, "conectar", side_effect=conectar_contado), \
             patch.object(database, "obtener_perfiles_nube", side_effect=AssertionError("N+1")):
            cuentas = database.obtener_cuentas_nube(limite=1000)

        self.assertEqual(len(selects), 2)
        self.assertEqual([p["id"] for p in cuentas[1]["perfiles"]], [11, 12])
        self.assertEqual(cuentas[1]["perfiles_totales"], 2)
        self.assertEqual(cuentas[1]["perfiles_disponibles"], 1)
        self.assertEqual(cuentas[0]["perfiles"], [])


if __name__ == "__main__":
    unittest.main()
