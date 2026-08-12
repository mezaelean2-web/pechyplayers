import json
import os
import sqlite3
import tempfile
import unittest
from datetime import date, timedelta

import database


class NotificacionesCortesNubeTest(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.original = database.DB
        database.DB = self.path
        conn = sqlite3.connect(self.path)
        conn.executescript("""
            CREATE TABLE nube_clientes(
                id INTEGER PRIMARY KEY, nombre TEXT, telefono TEXT,
                telefono_normalizado TEXT
            );
            CREATE TABLE nube_cuentas(
                id INTEGER PRIMARY KEY, plataforma TEXT, correo TEXT,
                contrasena TEXT DEFAULT '', pin TEXT DEFAULT '',
                cliente_id INTEGER, nombre_cliente TEXT DEFAULT '',
                telefono TEXT DEFAULT '', fecha_entrega TEXT DEFAULT '',
                dias_cuenta INTEGER DEFAULT 0, fecha_vencimiento TEXT DEFAULT '',
                estado TEXT DEFAULT 'disponible', modalidad TEXT DEFAULT 'perfiles',
                tipo_cuenta TEXT DEFAULT '', garantia_usada INTEGER DEFAULT 0,
                cantidad_garantias INTEGER DEFAULT 0, notas TEXT DEFAULT '',
                origen TEXT DEFAULT '', cantidad_perfiles INTEGER DEFAULT 0,
                tipo_pago TEXT DEFAULT '', valor_pin REAL DEFAULT 0,
                plan_pago TEXT DEFAULT '', precio_plan_referencia REAL DEFAULT 0,
                fecha_aplicacion_pin TEXT DEFAULT '', dias_estimados_pin INTEGER DEFAULT 0,
                fecha_proximo_pago TEXT DEFAULT '', fecha_creacion TEXT DEFAULT CURRENT_TIMESTAMP,
                fecha_actualizacion TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE nube_perfiles(
                id INTEGER PRIMARY KEY, cuenta_id INTEGER, nombre_perfil TEXT,
                pin TEXT DEFAULT '', cliente_id INTEGER, nombre_cliente TEXT DEFAULT '',
                telefono TEXT DEFAULT '', fecha_entrega TEXT DEFAULT '',
                dias_cuenta INTEGER DEFAULT 0, fecha_vencimiento TEXT DEFAULT '',
                estado TEXT DEFAULT 'disponible', notas TEXT DEFAULT '',
                garantia_usada INTEGER DEFAULT 0, cantidad_garantias INTEGER DEFAULT 0,
                orden INTEGER DEFAULT 0, fecha_creacion TEXT DEFAULT CURRENT_TIMESTAMP,
                fecha_actualizacion TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE nube_movimientos(
                id INTEGER PRIMARY KEY AUTOINCREMENT, cuenta_id INTEGER,
                tipo TEXT, descripcion TEXT, estado_anterior TEXT,
                estado_nuevo TEXT, cliente_nombre TEXT,
                fecha TEXT DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.commit()
        conn.close()

    def tearDown(self):
        database.DB = self.original
        os.remove(self.path)

    @staticmethod
    def fecha(dias):
        return (date.today() + timedelta(days=dias)).isoformat()

    def execute(self, sql, params=()):
        conn = sqlite3.connect(self.path)
        conn.execute(sql, params)
        conn.commit()
        conn.close()

    def scalar(self, sql, params=()):
        conn = sqlite3.connect(self.path)
        valor = conn.execute(sql, params).fetchone()[0]
        conn.close()
        return valor

    def cuenta(self, cuenta_id, plataforma="Netflix", modalidad="perfiles",
               estado="disponible", cliente="", vencimiento=-1,
               entrega=-31, dias=30, telefono="3001234567", cliente_id=1,
               contrasena="secreta", pin="0000"):
        if cliente and estado == "disponible":
            estado = "vencida" if vencimiento <= 0 else "activa"
        self.execute("""
            INSERT INTO nube_cuentas(
                id, plataforma, correo, contrasena, pin, cliente_id, nombre_cliente,
                telefono, fecha_entrega, dias_cuenta, fecha_vencimiento,
                estado, modalidad
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            cuenta_id, plataforma, f"madre{cuenta_id}@test.com", contrasena, pin,
            cliente_id if cliente else None, cliente, telefono if cliente else "",
            self.fecha(entrega) if cliente else "", dias if cliente else 0,
            self.fecha(vencimiento) if cliente else "", estado, modalidad
        ))

    def perfil(self, perfil_id, cuenta_id, plataforma="Netflix", cliente="Ana",
               vencimiento=-1, entrega=-31, dias=30, estado="activa",
               telefono="3001234567", cliente_id=1, pin="1111"):
        if not self.scalar("SELECT COUNT(*) FROM nube_cuentas WHERE id=?", (cuenta_id,)):
            self.cuenta(cuenta_id, plataforma=plataforma, modalidad="perfiles")
        self.execute("""
            INSERT INTO nube_perfiles(
                id, cuenta_id, nombre_perfil, pin, cliente_id, nombre_cliente,
                telefono, fecha_entrega, dias_cuenta, fecha_vencimiento, estado
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            perfil_id, cuenta_id, f"Perfil {perfil_id}", pin,
            cliente_id if cliente else None, cliente, telefono if cliente else "",
            self.fecha(entrega) if cliente else "", dias if cliente else 0,
            self.fecha(vencimiento) if cliente else "", estado
        ))

    def pendientes(self):
        return database.obtener_centro_notificaciones_renovacion_nube()["pendientes"]

    def notificar(self, unidad=None):
        unidad = unidad or self.pendientes()[0]
        return database.marcar_notificacion_renovacion_nube(
            unidad["servicios"], unidad["mensaje"], "manual"
        )

    def test_01_perfil_vencido_aparece_en_notificaciones(self):
        self.perfil(1, 1)
        self.assertEqual(len(self.pendientes()), 1)

    def test_02_cuenta_completa_vencida_aparece(self):
        self.cuenta(2, modalidad="cuenta_completa", cliente="Luis")
        self.assertEqual(self.pendientes()[0]["servicios"][0]["servicio_tipo"], "cuenta_completa")

    def test_03_disponible_no_aparece(self):
        self.perfil(1, 1, cliente="", estado="disponible")
        self.assertEqual(self.pendientes(), [])

    def test_04_renovado_no_aparece(self):
        self.perfil(1, 1, vencimiento=10, estado="activa")
        self.assertEqual(self.pendientes(), [])

    def test_05_papelera_no_aparece(self):
        self.cuenta(1, estado="papelera")
        self.perfil(1, 1)
        self.assertEqual(self.pendientes(), [])

    def test_06_reemplazada_no_aparece(self):
        self.perfil(1, 1, estado="reemplazada")
        self.assertEqual(self.pendientes(), [])

    def test_07_mismo_cliente_fechas_distintas_no_agrupa(self):
        self.perfil(1, 1, plataforma="Netflix", entrega=-31, vencimiento=-1)
        self.perfil(2, 2, plataforma="Disney", entrega=-36, vencimiento=-6)
        self.assertEqual(len(self.pendientes()), 2)

    def test_08_mismo_cliente_misma_compra_detecta_combo(self):
        self.perfil(1, 1, plataforma="Netflix")
        self.perfil(2, 2, plataforma="Disney")
        self.assertEqual(self.pendientes()[0]["tipo"], "combo")

    def test_09_combo_aparece_una_sola_vez(self):
        self.perfil(1, 1, plataforma="Netflix")
        self.perfil(2, 2, plataforma="Disney")
        self.perfil(3, 3, plataforma="Prime")
        self.assertEqual(len(self.pendientes()), 1)
        self.assertEqual(len(self.pendientes()[0]["servicios"]), 3)

    def test_10_notificar_individual_crea_registro(self):
        self.perfil(1, 1)
        self.assertTrue(self.notificar()["ok"])
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM nube_notificaciones_renovacion"), 1)

    def test_11_notificar_combo_relaciona_todos_los_servicios(self):
        self.perfil(1, 1, plataforma="Netflix")
        self.perfil(2, 2, plataforma="Disney")
        self.notificar()
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM nube_notificacion_servicios"), 2)

    def test_12_mismo_servicio_no_se_notifica_dos_veces_mismo_ciclo(self):
        self.perfil(1, 1)
        unidad = self.pendientes()[0]
        self.assertTrue(self.notificar(unidad)["ok"])
        self.assertFalse(database.marcar_notificacion_renovacion_nube(unidad["servicios"])["ok"])

    def test_13_renovacion_futura_puede_notificarse_nuevo_ciclo(self):
        self.perfil(1, 1)
        self.notificar()
        self.execute("UPDATE nube_perfiles SET fecha_vencimiento=? WHERE id=1", (self.fecha(30),))
        self.assertEqual(self.pendientes(), [])
        self.execute("UPDATE nube_perfiles SET fecha_entrega=?, fecha_vencimiento=? WHERE id=1", (self.fecha(-30), self.fecha(0)))
        self.assertEqual(len(self.pendientes()), 1)

    def test_14_notificado_aparece_en_cortes(self):
        self.perfil(1, 1)
        self.notificar()
        self.assertEqual(len(database.obtener_cortes_nube()["pendientes"]), 1)

    def test_15_renovacion_elimina_de_cortes(self):
        self.perfil(1, 1)
        self.notificar()
        self.execute("UPDATE nube_perfiles SET fecha_vencimiento=? WHERE id=1", (self.fecha(20),))
        self.assertEqual(database.obtener_cortes_nube()["pendientes"], [])

    def test_16_combo_parcial_renovado_conserva_otros_servicios(self):
        self.perfil(1, 1, plataforma="Netflix")
        self.perfil(2, 2, plataforma="Disney")
        self.notificar()
        self.execute("UPDATE nube_perfiles SET fecha_vencimiento=? WHERE id=1", (self.fecha(20),))
        pendientes = database.obtener_cortes_nube()["pendientes"]
        self.assertEqual(len(pendientes), 1)
        self.assertEqual(len(pendientes[0]["servicios"]), 1)
        self.assertEqual(pendientes[0]["servicios"][0]["plataforma"], "Disney")

    def test_17_corte_perfil_limpia_asignacion_y_deja_disponible(self):
        self.perfil(1, 1, pin="9999")
        self.notificar()
        servicio = database.obtener_cortes_nube()["pendientes"][0]["servicios"]
        self.assertTrue(database.cortar_servicios_nube(servicio)["ok"])
        self.assertEqual(self.scalar("SELECT estado FROM nube_perfiles WHERE id=1"), "disponible")
        self.assertEqual(self.scalar("SELECT pin FROM nube_perfiles WHERE id=1"), "9999")
        self.assertEqual(self.scalar("SELECT nombre_cliente FROM nube_perfiles WHERE id=1"), "")

    def test_18_corte_cuenta_completa_limpia_asignacion(self):
        self.cuenta(1, modalidad="cuenta_completa", cliente="Cuenta Cliente")
        self.notificar()
        servicio = database.obtener_cortes_nube()["pendientes"][0]["servicios"]
        self.assertTrue(database.cortar_servicios_nube(servicio)["ok"])
        self.assertEqual(self.scalar("SELECT estado FROM nube_cuentas WHERE id=1"), "disponible")
        self.assertEqual(self.scalar("SELECT nombre_cliente FROM nube_cuentas WHERE id=1"), "")

    def test_19_corte_crea_snapshot_historial(self):
        self.perfil(1, 1)
        self.notificar()
        servicio = database.obtener_cortes_nube()["pendientes"][0]["servicios"]
        database.cortar_servicios_nube(servicio)
        snapshot = self.scalar("SELECT snapshot FROM nube_notificacion_servicios")
        self.assertEqual(json.loads(snapshot)["nombre_cliente"], "Ana")
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM nube_movimientos WHERE tipo='servicio_cortado'"), 1)

    def test_20_no_elimina_historial_anterior(self):
        self.perfil(1, 1)
        self.execute("INSERT INTO nube_movimientos(cuenta_id,tipo,descripcion) VALUES(1,'previo','historia')")
        self.notificar()
        servicio = database.obtener_cortes_nube()["pendientes"][0]["servicios"]
        database.cortar_servicios_nube(servicio)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM nube_movimientos WHERE tipo='previo'"), 1)

    def test_21_corte_concurrente_no_corta_servicio_recien_renovado(self):
        self.perfil(1, 1)
        self.notificar()
        servicio = database.obtener_cortes_nube()["pendientes"][0]["servicios"]
        self.execute("UPDATE nube_perfiles SET fecha_vencimiento=? WHERE id=1", (self.fecha(10),))
        resultado = database.cortar_servicios_nube(servicio)
        self.assertFalse(resultado["ok"])
        self.assertEqual(self.scalar("SELECT nombre_cliente FROM nube_perfiles WHERE id=1"), "Ana")

    def test_22_telefono_se_normaliza_correctamente(self):
        self.perfil(1, 1, telefono="300 123 4567")
        self.assertEqual(self.pendientes()[0]["telefono_normalizado"], "573001234567")

    def test_23_whatsapp_genera_mensaje_individual(self):
        self.perfil(1, 1)
        unidad = self.pendientes()[0]
        self.assertIn("https://wa.me/573001234567?text=", unidad["whatsapp_url"])
        self.assertIn("Netflix", unidad["mensaje"])

    def test_24_whatsapp_genera_mensaje_combo(self):
        self.perfil(1, 1, plataforma="Netflix")
        self.perfil(2, 2, plataforma="Disney")
        unidad = self.pendientes()[0]
        self.assertIn("Tu combo", unidad["mensaje"])
        self.assertIn("Disney", unidad["mensaje"])

    def test_25_no_expone_contrasenas_en_centro_notificaciones(self):
        self.perfil(1, 1)
        self.notificar()
        servicio = database.obtener_cortes_nube()["pendientes"][0]["servicios"]
        database.cortar_servicios_nube(servicio)
        texto = json.dumps(database.obtener_centro_notificaciones_renovacion_nube())
        self.assertNotIn("secreta", texto)

    def test_26_editar_correo_desde_corte(self):
        self.perfil(1, 1)
        self.notificar()
        cuenta = database.obtener_cortes_nube()["pendientes"][0]["cuenta_madre"]
        resultado = database.actualizar_credenciales_cuenta_corte_nube(cuenta["id"], "nuevo@test.com", cuenta["contrasena"], cuenta["pin"])
        self.assertTrue(resultado["ok"])
        self.assertEqual(self.scalar("SELECT correo FROM nube_cuentas WHERE id=1"), "nuevo@test.com")

    def test_27_editar_contrasena_desde_corte(self):
        self.perfil(1, 1)
        self.notificar()
        resultado = database.actualizar_credenciales_cuenta_corte_nube(1, "madre1@test.com", "nueva-clave", "0000")
        self.assertTrue(resultado["ok"])
        self.assertEqual(self.scalar("SELECT contrasena FROM nube_cuentas WHERE id=1"), "nueva-clave")

    def test_28_editar_pin_desde_corte(self):
        self.perfil(1, 1)
        self.notificar()
        resultado = database.actualizar_credenciales_cuenta_corte_nube(1, "madre1@test.com", "secreta", "7777")
        self.assertTrue(resultado["ok"])
        self.assertEqual(self.scalar("SELECT pin FROM nube_cuentas WHERE id=1"), "7777")

    def test_29_editar_madre_desde_corte_de_perfil(self):
        self.perfil(3, 1, pin="perfil-pin")
        self.notificar()
        servicio = database.obtener_cortes_nube()["pendientes"][0]["servicios"][0]
        self.assertEqual(servicio["cuenta_id"], 1)
        database.actualizar_credenciales_cuenta_corte_nube(servicio["cuenta_id"], "madre-real@test.com", "madre-clave", "9090")
        self.assertEqual(self.scalar("SELECT contrasena FROM nube_cuentas WHERE id=1"), "madre-clave")
        self.assertEqual(self.scalar("SELECT pin FROM nube_perfiles WHERE id=3"), "perfil-pin")

    def test_30_guardar_credenciales_no_modifica_asignacion(self):
        self.perfil(1, 1)
        self.notificar()
        database.actualizar_credenciales_cuenta_corte_nube(1, "madre1@test.com", "otra", "1111")
        self.assertEqual(self.scalar("SELECT nombre_cliente FROM nube_perfiles WHERE id=1"), "Ana")
        self.assertEqual(self.scalar("SELECT telefono FROM nube_perfiles WHERE id=1"), "3001234567")

    def test_31_guardar_credenciales_no_modifica_estado(self):
        self.perfil(1, 1, estado="activa")
        self.notificar()
        database.actualizar_credenciales_cuenta_corte_nube(1, "madre1@test.com", "otra", "1111")
        self.assertEqual(self.scalar("SELECT estado FROM nube_perfiles WHERE id=1"), "activa")
        self.assertEqual(self.scalar("SELECT estado FROM nube_cuentas WHERE id=1"), "disponible")

    def test_32_corte_posterior_preserva_credenciales_nuevas(self):
        self.perfil(1, 1)
        self.notificar()
        database.actualizar_credenciales_cuenta_corte_nube(1, "post@test.com", "post-clave", "2323")
        servicio = database.obtener_cortes_nube()["pendientes"][0]["servicios"]
        self.assertTrue(database.cortar_servicios_nube(servicio)["ok"])
        self.assertEqual(self.scalar("SELECT correo FROM nube_cuentas WHERE id=1"), "post@test.com")
        self.assertEqual(self.scalar("SELECT contrasena FROM nube_cuentas WHERE id=1"), "post-clave")
        self.assertEqual(self.scalar("SELECT pin FROM nube_cuentas WHERE id=1"), "2323")

    def test_33_corte_cuenta_completa_limpia_cliente_no_credenciales(self):
        self.cuenta(1, modalidad="cuenta_completa", cliente="Cuenta Cliente", contrasena="clave-final", pin="1212")
        self.notificar()
        database.actualizar_credenciales_cuenta_corte_nube(1, "final@test.com", "clave-final-2", "3434")
        servicio = database.obtener_cortes_nube()["pendientes"][0]["servicios"]
        self.assertTrue(database.cortar_servicios_nube(servicio)["ok"])
        self.assertEqual(self.scalar("SELECT nombre_cliente FROM nube_cuentas WHERE id=1"), "")
        self.assertEqual(self.scalar("SELECT correo FROM nube_cuentas WHERE id=1"), "final@test.com")
        self.assertEqual(self.scalar("SELECT contrasena FROM nube_cuentas WHERE id=1"), "clave-final-2")
        self.assertEqual(self.scalar("SELECT pin FROM nube_cuentas WHERE id=1"), "3434")

    def test_34_pin_ausente_no_sobrescribe_pin_actual(self):
        self.perfil(1, 1)
        self.notificar()
        database.actualizar_credenciales_cuenta_corte_nube(1, "sin-pin@test.com", "clave", None)
        self.assertEqual(self.scalar("SELECT pin FROM nube_cuentas WHERE id=1"), "0000")

    def test_35_madre_con_tres_perfiles_aparece_una_sola_vez(self):
        self.perfil(1, 1, cliente="Ana", telefono="3001111111", cliente_id=1)
        self.perfil(2, 1, cliente="Luis", telefono="3002222222", cliente_id=2)
        self.perfil(3, 1, cliente="Mia", telefono="3003333333", cliente_id=3)
        for unidad in list(self.pendientes()):
            self.notificar(unidad)
        pendientes = database.obtener_cortes_nube()["pendientes"]
        self.assertEqual(len(pendientes), 1)
        self.assertEqual(pendientes[0]["cuenta_id"], 1)
        self.assertEqual(len(pendientes[0]["servicios"]), 3)
        self.assertEqual(pendientes[0]["pendientes_count"], 3)

    def test_36_perfil_renovado_reduce_contador_de_madre(self):
        self.perfil(1, 1, cliente="Ana", telefono="3001111111", cliente_id=1)
        self.perfil(2, 1, cliente="Luis", telefono="3002222222", cliente_id=2)
        self.perfil(3, 1, cliente="Mia", telefono="3003333333", cliente_id=3)
        for unidad in list(self.pendientes()):
            self.notificar(unidad)
        self.execute("UPDATE nube_perfiles SET fecha_vencimiento=? WHERE id=2", (self.fecha(15),))
        pendientes = database.obtener_cortes_nube()["pendientes"]
        self.assertEqual(len(pendientes), 1)
        self.assertEqual(len(pendientes[0]["servicios"]), 2)
        self.assertNotIn(2, [s["perfil_id"] for s in pendientes[0]["servicios"]])

    def test_37_renovar_todos_elimina_madre_de_cortes(self):
        self.perfil(1, 1, cliente="Ana", telefono="3001111111", cliente_id=1)
        self.perfil(2, 1, cliente="Luis", telefono="3002222222", cliente_id=2)
        for unidad in list(self.pendientes()):
            self.notificar(unidad)
        self.execute("UPDATE nube_perfiles SET fecha_vencimiento=?", (self.fecha(15),))
        self.assertEqual(database.obtener_cortes_nube()["pendientes"], [])

    def test_38_lectura_nube_obtiene_contrasena_actualizada_desde_cortes(self):
        self.perfil(1, 1)
        self.notificar()
        resultado = database.actualizar_credenciales_cuenta_corte_nube(1, "madre1@test.com", "NEW", "0000")
        self.assertTrue(resultado["ok"])
        cuentas = database.obtener_cuentas_nube(limite=5)
        self.assertEqual(cuentas[0]["contrasena"], "NEW")

    def test_39_pin_perfil_actualiza_solo_ese_perfil(self):
        self.perfil(1, 1, pin="1111", cliente="Ana", telefono="3001111111", cliente_id=1)
        self.perfil(2, 1, pin="2222", cliente="Luis", telefono="3002222222", cliente_id=2)
        resultado = database.actualizar_pin_perfil_corte_nube(1, 2, "9999")
        self.assertTrue(resultado["ok"])
        self.assertEqual(self.scalar("SELECT pin FROM nube_perfiles WHERE id=1"), "1111")
        self.assertEqual(self.scalar("SELECT pin FROM nube_perfiles WHERE id=2"), "9999")
        self.assertEqual(self.scalar("SELECT pin FROM nube_cuentas WHERE id=1"), "0000")

    def test_40_pin_perfil_valida_relacion_madre(self):
        self.perfil(1, 1, pin="1111")
        self.cuenta(2, plataforma="Disney")
        resultado = database.actualizar_pin_perfil_corte_nube(2, 1, "9999")
        self.assertFalse(resultado["ok"])
        self.assertEqual(self.scalar("SELECT pin FROM nube_perfiles WHERE id=1"), "1111")

    def test_41_cortar_seleccionados_solo_elegibles(self):
        self.perfil(1, 1, cliente="Ana", telefono="3001111111", cliente_id=1)
        self.perfil(2, 1, cliente="Luis", telefono="3002222222", cliente_id=2)
        self.perfil(3, 1, cliente="Mia", telefono="3003333333", cliente_id=3)
        for unidad in list(self.pendientes()):
            self.notificar(unidad)
        servicios = database.obtener_cortes_nube()["pendientes"][0]["servicios"]
        self.execute("UPDATE nube_perfiles SET fecha_vencimiento=? WHERE id=2", (self.fecha(20),))
        resultado = database.cortar_servicios_nube(servicios)
        self.assertTrue(resultado["ok"])
        self.assertEqual(resultado["cortados"], 2)
        self.assertEqual(resultado["retirados"], 1)
        self.assertEqual(self.scalar("SELECT estado FROM nube_perfiles WHERE id=1"), "disponible")
        self.assertEqual(self.scalar("SELECT nombre_cliente FROM nube_perfiles WHERE id=2"), "Luis")
        self.assertEqual(self.scalar("SELECT estado FROM nube_perfiles WHERE id=3"), "disponible")

    def test_42_cortar_pendientes_no_corta_vigentes(self):
        self.perfil(1, 1, cliente="Ana", telefono="3001111111", cliente_id=1)
        self.perfil(2, 1, cliente="Luis", telefono="3002222222", cliente_id=2, vencimiento=10, estado="activa")
        self.perfil(3, 1, cliente="Mia", telefono="3003333333", cliente_id=3)
        for unidad in list(self.pendientes()):
            self.notificar(unidad)
        servicios = database.obtener_cortes_nube()["pendientes"][0]["servicios"]
        resultado = database.cortar_servicios_nube(servicios)
        self.assertTrue(resultado["ok"])
        self.assertEqual(resultado["cortados"], 2)
        self.assertEqual(self.scalar("SELECT nombre_cliente FROM nube_perfiles WHERE id=2"), "Luis")

    def test_43_madre_desaparece_cuando_no_quedan_pendientes(self):
        self.perfil(1, 1)
        self.notificar()
        servicios = database.obtener_cortes_nube()["pendientes"][0]["servicios"]
        self.assertTrue(database.cortar_servicios_nube(servicios)["ok"])
        self.assertEqual(database.obtener_cortes_nube()["pendientes"], [])

    def test_44_cuenta_completa_sin_hijo_artificial(self):
        self.cuenta(1, modalidad="cuenta_completa", cliente="Cuenta Cliente")
        self.notificar()
        pendiente = database.obtener_cortes_nube()["pendientes"][0]
        self.assertEqual(len(pendiente["servicios"]), 1)
        self.assertEqual(pendiente["servicios"][0]["servicio_tipo"], "cuenta_completa")
        self.assertIsNone(pendiente["servicios"][0]["perfil_id"])

    def test_45_no_duplica_madre_por_multiples_notificaciones(self):
        self.perfil(1, 1, cliente="Ana", telefono="3001111111", cliente_id=1)
        self.perfil(2, 1, cliente="Luis", telefono="3002222222", cliente_id=2)
        for unidad in list(self.pendientes()):
            self.notificar(unidad)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM nube_notificaciones_renovacion"), 2)
        self.assertEqual(len(database.obtener_cortes_nube()["pendientes"]), 1)

    def test_46_combo_comercial_conserva_badge_operativo_por_madre(self):
        self.perfil(1, 1, plataforma="Netflix", cliente="Ana", cliente_id=1)
        self.perfil(2, 2, plataforma="Disney", cliente="Ana", cliente_id=1)
        self.notificar()
        pendientes = database.obtener_cortes_nube()["pendientes"]
        self.assertEqual(len(pendientes), 2)
        self.assertTrue(all(g["servicios"][0]["tipo_notificacion"] == "combo" for g in pendientes))

    def test_47_historial_no_expone_contrasena(self):
        self.perfil(1, 1)
        self.notificar()
        database.actualizar_credenciales_cuenta_corte_nube(1, "madre1@test.com", "SUPER-SECRETA", "0000")
        servicios = database.obtener_cortes_nube()["pendientes"][0]["servicios"]
        database.cortar_servicios_nube(servicios)
        texto = json.dumps(database.obtener_cortes_nube()["historial"])
        self.assertNotIn("SUPER-SECRETA", texto)

    def test_48_slot_cortado_reasignado_mismo_ciclo_puede_notificarse(self):
        self.perfil(1, 1, cliente="Cliente anterior", cliente_id=10)
        self.notificar()
        servicio = database.obtener_cortes_nube()["pendientes"][0]["servicios"][0]
        self.assertTrue(database.cortar_servicios_nube([servicio])["ok"])
        vencimiento = self.fecha(-1)
        self.execute("""
            UPDATE nube_perfiles
            SET cliente_id=20, nombre_cliente='Cliente nuevo', telefono='3009999999',
                fecha_entrega=?, dias_cuenta=30, fecha_vencimiento=?, estado='vencida'
            WHERE id=1
        """, (self.fecha(-31), vencimiento))
        pendientes_notificacion = self.pendientes()
        self.assertEqual(len(pendientes_notificacion), 1)
        self.assertEqual(pendientes_notificacion[0]["servicios"][0]["nombre_cliente"], "Cliente nuevo")
        perfil_reasignado = database.obtener_cuentas_nube(limite=10)[0]["perfiles"][0]
        self.assertFalse(perfil_reasignado["notificacion_activa"])
        self.assertEqual(perfil_reasignado["estado_visual"], "vencida")
        self.notificar(pendientes_notificacion[0])
        cortes = database.obtener_cortes_nube()["pendientes"]
        self.assertEqual(len(cortes), 1)
        self.assertEqual(len(cortes[0]["servicios"]), 1)
        self.assertEqual(cortes[0]["servicios"][0]["perfil_id"], 1)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM nube_notificacion_servicios WHERE servicio_id=1"), 2)

    def test_49_respuesta_credenciales_es_lectura_persistida(self):
        self.cuenta(1)
        resultado = database.actualizar_credenciales_cuenta_corte_nube(
            1, "persistida@test.com", "NEW", None
        )
        self.assertTrue(resultado["ok"])
        self.assertEqual(resultado["cuenta"]["contrasena"], "NEW")
        self.assertEqual(
            resultado["cuenta"]["contrasena"],
            self.scalar("SELECT contrasena FROM nube_cuentas WHERE id=1")
        )

    def test_50_respuesta_pin_es_lectura_persistida(self):
        self.perfil(4, 1, pin="1234")
        resultado = database.actualizar_pin_perfil_corte_nube(1, 4, "9876")
        self.assertTrue(resultado["ok"])
        self.assertEqual(resultado["perfil"], {"id": 4, "cuenta_id": 1, "pin": "9876"})
        self.assertEqual(self.scalar("SELECT pin FROM nube_perfiles WHERE id=4"), "9876")

    def test_51_metricas_cuentan_servicios_reales(self):
        self.perfil(1, 1, cliente="Ana", cliente_id=1, vencimiento=10)
        self.perfil(2, 1, cliente="Luis", cliente_id=2, vencimiento=2)
        self.perfil(3, 1, cliente="Mia", cliente_id=3, vencimiento=-2)
        self.cuenta(2, modalidad="cuenta_completa", cliente="Carlos", vencimiento=15)
        resumen = database.obtener_estadisticas_nube()
        self.assertEqual(resumen["total"], 4)
        self.assertEqual(resumen["vendidas"], 4)
        self.assertEqual(resumen["por_vencer"], 1)
        self.assertEqual(resumen["vencidas"], 1)

    def test_52_notificada_es_derivada_solo_del_ciclo_activo(self):
        self.perfil(1, 1, vencimiento=-1)
        self.notificar()
        cuenta = database.obtener_cuentas_nube(limite=10)[0]
        self.assertEqual(cuenta["perfiles"][0]["estado_calculado"], "vencida")
        self.assertEqual(cuenta["perfiles"][0]["estado_visual"], "notificada")
        resumen = database.obtener_estadisticas_nube()
        self.assertEqual(resumen["vencidas"], 1)
        self.assertEqual(resumen["notificadas"], 1)
        servicio = database.obtener_cortes_nube()["pendientes"][0]["servicios"][0]
        database.cortar_servicios_nube([servicio])
        perfil = database.obtener_cuentas_nube(limite=10)[0]["perfiles"][0]
        self.assertEqual(perfil["estado_visual"], "disponible")

    def test_53_caidas_cuentan_madres_no_hijos(self):
        self.cuenta(1, estado="caida")
        self.perfil(1, 1)
        self.perfil(2, 1)
        resumen = database.obtener_estadisticas_nube()
        self.assertEqual(resumen["caidas"], 1)
        self.assertEqual(resumen["vendidas"], 0)

    def test_54_vencidas_incluye_notificadas_durante_renovacion_y_corte(self):
        for perfil_id in range(1, 11):
            self.perfil(
                perfil_id, 1, cliente=f"Cliente {perfil_id}",
                telefono=f"300000{perfil_id:04d}", cliente_id=perfil_id
            )

        resumen = database.obtener_estadisticas_nube()
        self.assertEqual((resumen["vencidas"], resumen["notificadas"]), (10, 0))

        for unidad in self.pendientes()[:4]:
            self.notificar(unidad)
        resumen = database.obtener_estadisticas_nube()
        self.assertEqual((resumen["vencidas"], resumen["notificadas"]), (10, 4))

        for unidad in list(self.pendientes()):
            self.notificar(unidad)
        resumen = database.obtener_estadisticas_nube()
        self.assertEqual((resumen["vencidas"], resumen["notificadas"]), (10, 10))

        self.execute(
            "UPDATE nube_perfiles SET fecha_vencimiento=?, estado='activa' WHERE id IN (1, 2)",
            (self.fecha(30),)
        )
        resumen = database.obtener_estadisticas_nube()
        self.assertEqual((resumen["vencidas"], resumen["notificadas"]), (8, 8))

        servicios = database.obtener_cortes_nube()["pendientes"][0]["servicios"][:3]
        self.assertTrue(database.cortar_servicios_nube(servicios)["ok"])
        resumen = database.obtener_estadisticas_nube()
        self.assertEqual((resumen["vencidas"], resumen["notificadas"]), (5, 5))
        self.assertEqual(resumen["disponibles"], 3)


if __name__ == "__main__":
    unittest.main()
