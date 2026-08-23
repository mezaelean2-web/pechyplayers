try:
    from tests._bootstrap import TEST_DB
except ModuleNotFoundError:
    from _bootstrap import TEST_DB

import os
import sqlite3
import tempfile
import unittest
from datetime import datetime

import database
import reseller_accounts
import resellers
import wallets


class ResellerPurchaseEngineTest(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".db"); os.close(fd)
        self.original_db = database.DB; database.DB = self.path
        conn = database.conectar(); conn.executescript("""
          PRAGMA foreign_keys=ON;
          CREATE TABLE productos(id INTEGER PRIMARY KEY AUTOINCREMENT,nombre TEXT NOT NULL,imagen TEXT DEFAULT '',plan TEXT NOT NULL,precio TEXT NOT NULL,estado TEXT DEFAULT 'disponible');
          CREATE TABLE nube_clientes(id INTEGER PRIMARY KEY AUTOINCREMENT,nombre TEXT,telefono TEXT,telefono_normalizado TEXT UNIQUE,fecha_actualizacion TEXT DEFAULT CURRENT_TIMESTAMP);
          CREATE TABLE nube_cuentas(id INTEGER PRIMARY KEY AUTOINCREMENT,plataforma TEXT NOT NULL,correo TEXT,contrasena TEXT DEFAULT '',pin TEXT DEFAULT '',cliente_id INTEGER,nombre_cliente TEXT DEFAULT '',telefono TEXT DEFAULT '',fecha_entrega TEXT DEFAULT '',dias_cuenta INTEGER DEFAULT 0,fecha_vencimiento TEXT DEFAULT '',estado TEXT DEFAULT 'disponible',modalidad TEXT DEFAULT 'cuenta_completa',fecha_creacion TEXT DEFAULT CURRENT_TIMESTAMP,fecha_actualizacion TEXT DEFAULT CURRENT_TIMESTAMP);
          CREATE TABLE nube_perfiles(id INTEGER PRIMARY KEY AUTOINCREMENT,cuenta_id INTEGER NOT NULL,nombre_perfil TEXT DEFAULT '',pin TEXT DEFAULT '',cliente_id INTEGER,nombre_cliente TEXT DEFAULT '',telefono TEXT DEFAULT '',fecha_entrega TEXT DEFAULT '',dias_cuenta INTEGER DEFAULT 0,fecha_vencimiento TEXT DEFAULT '',estado TEXT DEFAULT 'disponible',fecha_actualizacion TEXT DEFAULT CURRENT_TIMESTAMP,FOREIGN KEY(cuenta_id) REFERENCES nube_cuentas(id));
          CREATE TABLE nube_movimientos(id INTEGER PRIMARY KEY AUTOINCREMENT,cuenta_id INTEGER NOT NULL,tipo TEXT NOT NULL,descripcion TEXT,estado_anterior TEXT,estado_nuevo TEXT,cliente_nombre TEXT,fecha TEXT DEFAULT CURRENT_TIMESTAMP);
        """); conn.commit(); conn.close()
        resellers.inicializar_revendedores(); reseller_accounts.inicializar_esquema()
        conn = database.conectar()
        conn.execute("INSERT INTO productos(nombre,imagen,plan,precio,estado) VALUES ('Netflix','n.png','Cuenta completa','99000','disponible')")
        self.plan_cuenta = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute("INSERT INTO productos(nombre,imagen,plan,precio,estado) VALUES ('Netflix','n.png','Perfil','55000','disponible')")
        self.plan_perfil = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.commit(); conn.close()
        self.reseller = resellers.crear_revendedor("Motor Uno","motor@example.com","3001112233","Motor","ClaveSegura123")
        wallets.apply_wallet_transaction(self.reseller,"manual_credit",200000,"Prueba aislada")
        conn=database.conectar()
        conn.execute("INSERT INTO nube_cuentas(plataforma,correo,modalidad,estado) VALUES ('Netflix','schema-account@example.com','cuenta_completa','caida')")
        conn.execute("INSERT INTO nube_cuentas(plataforma,correo,modalidad,estado) VALUES ('Netflix','schema-profiles@example.com','perfiles','caida')")
        conn.commit(); conn.close()
        reseller_accounts.guardar_regla_inventario_plan(self.plan_cuenta,"Netflix","cuenta",30)
        reseller_accounts.guardar_regla_inventario_plan(self.plan_perfil,"Netflix","perfil",15)
        resellers.guardar_precio_general(self.plan_cuenta,40000)
        resellers.guardar_precio_general(self.plan_perfil,20000)

    def tearDown(self):
        database.DB = self.original_db
        try: os.remove(self.path)
        except PermissionError: pass

    def cuenta(self, modalidad="cuenta_completa", perfiles=0, estado="disponible"):
        duracion = 15 if modalidad == "perfiles" else 30
        conn=database.conectar(); cur=conn.execute("INSERT INTO nube_cuentas(plataforma,correo,modalidad,estado,duracion_unidad_dias) VALUES ('Netflix',?,?,?,?)",(f"unit-{os.urandom(3).hex()}@example.com",modalidad,estado,duracion)); cuenta_id=cur.lastrowid
        for numero in range(perfiles): conn.execute("INSERT INTO nube_perfiles(cuenta_id,nombre_perfil) VALUES (?,?)",(cuenta_id,f"Perfil {numero+1}"))
        conn.commit(); conn.close()
        return cuenta_id

    def test_compra_cuenta_debita_crea_ledger_purchase_evento_y_ownership(self):
        cuenta_id=self.cuenta(); ahora=datetime(2026,8,21,10,0,tzinfo=reseller_accounts.ZONA_HORARIA)
        resultado=reseller_accounts.comprar_plan_reseller(self.reseller,self.plan_cuenta,"buy-1",ahora)
        self.assertEqual((resultado["precio_pagado"],resultado["saldo_restante"]),(40000,160000))
        self.assertTrue(resultado["fecha_vencimiento"].startswith("2026-09-20"))
        conn=database.conectar()
        compra=conn.execute("SELECT * FROM reseller_purchases WHERE id=?",(resultado["purchase_id"],)).fetchone()
        self.assertEqual((compra["cuenta_id"],compra["perfil_id"],compra["estado_persistido"]),(cuenta_id,None,"active"))
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM reseller_purchase_events WHERE purchase_id=?",(compra["id"],)).fetchone()[0],1)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM reseller_wallet_transactions WHERE tipo='purchase'").fetchone()[0],1)
        self.assertNotIn("password",conn.execute("SELECT datos_publicos_json FROM reseller_purchase_events").fetchone()[0].lower())
        conn.close()

    def test_idempotencia_no_repite_efectos_y_rechaza_parametros_distintos(self):
        self.cuenta(); primero=reseller_accounts.comprar_plan_reseller(self.reseller,self.plan_cuenta,"same")
        segundo=reseller_accounts.comprar_plan_reseller(self.reseller,self.plan_cuenta,"same")
        self.assertEqual(primero["purchase_id"],segundo["purchase_id"]); self.assertTrue(segundo["duplicado"])
        with self.assertRaisesRegex(reseller_accounts.ResellerPurchaseError,"otra operación"):
            reseller_accounts.comprar_plan_reseller(self.reseller,self.plan_perfil,"same")

    def test_precio_personalizado_prioritario_y_sin_fallback_publico(self):
        self.cuenta(); resellers.guardar_precio_personalizado(self.reseller,self.plan_cuenta,31000)
        self.assertEqual(reseller_accounts.comprar_plan_reseller(self.reseller,self.plan_cuenta,"personal")["precio_pagado"],31000)
        conn=database.conectar(); conn.execute("UPDATE precios_revendedor_generales SET activo=0 WHERE plan_id=?",(self.plan_perfil,)); conn.commit(); conn.close()
        self.cuenta("perfiles",1)
        with self.assertRaisesRegex(reseller_accounts.ResellerPurchaseError,"tarifa reseller"):
            reseller_accounts.comprar_plan_reseller(self.reseller,self.plan_perfil,"no-public")

    def test_seleccion_determinista_ignora_cuenta_no_elegible(self):
        self.cuenta(estado="caida"); elegible=self.cuenta()
        resultado=reseller_accounts.comprar_plan_reseller(self.reseller,self.plan_cuenta,"eligible")
        conn=database.conectar(); actual=conn.execute("SELECT cuenta_id FROM reseller_purchases WHERE id=?",(resultado["purchase_id"],)).fetchone()[0]; conn.close()
        self.assertEqual(actual,elegible)

    def test_una_sola_duracion_acepta_inventario_historico_null(self):
        conn=database.conectar(); cuenta_id=conn.execute(
            "INSERT INTO nube_cuentas(plataforma,correo,modalidad,estado,duracion_unidad_dias) VALUES ('Netflix','legacy-null@example.com','cuenta_completa','disponible',NULL)"
        ).lastrowid; conn.commit(); conn.close()
        resultado=reseller_accounts.comprar_plan_reseller(self.reseller,self.plan_cuenta,"legacy-null")
        conn=database.conectar(); asignada=conn.execute(
            "SELECT cuenta_id FROM reseller_purchases WHERE id=?",(resultado["purchase_id"],)
        ).fetchone()[0]; conn.close()
        self.assertEqual(asignada,cuenta_id)

    def test_multiples_duraciones_exigen_clasificacion_y_coincidencia_exacta(self):
        conn=database.conectar()
        conn.execute("INSERT INTO productos(nombre,imagen,plan,precio,estado) VALUES ('Netflix','n.png','Cuenta 90','99000','disponible')")
        plan_90=conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute("INSERT INTO reseller_plan_inventory_rules(plan_id,plataforma,tipo_unidad,duracion_dias,activo) VALUES (?,?,?,?,1)",(plan_90,'Netflix','cuenta',90))
        conn.execute("INSERT INTO precios_revendedor_generales(plan_id,precio,activo) VALUES (?,?,1)",(plan_90,40000))
        ids=[]
        for correo,duracion in [('sin-clasificar@example.com',None),('unidad-90@example.com',90),('unidad-30@example.com',30)]:
            ids.append(conn.execute("INSERT INTO nube_cuentas(plataforma,correo,modalidad,estado,duracion_unidad_dias) VALUES ('Netflix',?,'cuenta_completa','disponible',?)",(correo,duracion)).lastrowid)
        conn.commit(); conn.close()
        compra_30=reseller_accounts.comprar_plan_reseller(self.reseller,self.plan_cuenta,"exacta-30")
        compra_90=reseller_accounts.comprar_plan_reseller(self.reseller,plan_90,"exacta-90")
        conn=database.conectar()
        usadas=[conn.execute("SELECT cuenta_id FROM reseller_purchases WHERE id=?",(item["purchase_id"],)).fetchone()[0] for item in (compra_30,compra_90)]
        conn.close()
        self.assertEqual(usadas,[ids[2],ids[1]])

    def test_politica_se_deriva_por_plataforma_y_modalidad(self):
        conn=database.conectar()
        for producto,plataforma,tipo,dias in [
            ('YouTube 30','YouTube','cuenta',30),('YouTube 90','YouTube','cuenta',90),
            ('Spotify 30','Spotify','perfil',30),('Spotify 90','Spotify','perfil',90),
            ('YouTube perfil','YouTube','perfil',30)]:
            conn.execute("INSERT INTO productos(nombre,imagen,plan,precio,estado) VALUES (?,'x.png','Plan','1','disponible')",(producto,))
            plan=conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.execute("INSERT INTO reseller_plan_inventory_rules(plan_id,plataforma,tipo_unidad,duracion_dias,activo) VALUES (?,?,?,?,1)",(plan,plataforma,tipo,dias))
        conn.commit()
        youtube=database.politica_duracion_inventario('youtube','cuenta_completa',cursor=conn.cursor())
        spotify=database.politica_duracion_inventario('Spotify','perfiles',cursor=conn.cursor())
        youtube_perfil=database.politica_duracion_inventario('YouTube','perfiles',cursor=conn.cursor())
        netflix_cuenta=database.politica_duracion_inventario('Netflix','cuenta_completa',cursor=conn.cursor())
        conn.close()
        self.assertEqual(youtube,{"requiere_duracion_inventario":True,"duraciones_disponibles":[30,90]})
        self.assertEqual(spotify,{"requiere_duracion_inventario":True,"duraciones_disponibles":[30,90]})
        self.assertFalse(youtube_perfil["requiere_duracion_inventario"])
        self.assertFalse(netflix_cuenta["requiere_duracion_inventario"])

    def test_payload_duracion_se_valida_o_se_limpia(self):
        conn=database.conectar()
        self.assertIsNone(database.validar_duracion_unidad_inventario('Netflix','cuenta_completa',90,cursor=conn.cursor()))
        conn.execute("INSERT INTO productos(nombre,imagen,plan,precio,estado) VALUES ('Netflix 90','x.png','Plan','1','disponible')")
        plan=conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute("INSERT INTO reseller_plan_inventory_rules(plan_id,plataforma,tipo_unidad,duracion_dias,activo) VALUES (?,?,?,?,1)",(plan,'Netflix','cuenta',90))
        conn.commit()
        with self.assertRaises(ValueError):
            database.validar_duracion_unidad_inventario('Netflix','cuenta_completa',60,cursor=conn.cursor())
        self.assertEqual(database.validar_duracion_unidad_inventario('Netflix','cuenta_completa',90,cursor=conn.cursor()),90)
        conn.close()

    def test_perfil_solo_ocupa_un_perfil_y_no_la_madre(self):
        cuenta_id=self.cuenta("perfiles",2)
        resultado=reseller_accounts.comprar_plan_reseller(self.reseller,self.plan_perfil,"profile")
        conn=database.conectar(); estados=conn.execute("SELECT estado FROM nube_perfiles WHERE cuenta_id=? ORDER BY id",(cuenta_id,)).fetchall(); madre=conn.execute("SELECT estado FROM nube_cuentas WHERE id=?",(cuenta_id,)).fetchone()[0]; compra=conn.execute("SELECT cuenta_id,perfil_id FROM reseller_purchases WHERE id=?",(resultado["purchase_id"],)).fetchone(); conn.close()
        self.assertEqual([x[0] for x in estados],["activa","disponible"]); self.assertEqual(madre,"disponible"); self.assertEqual(compra[0],cuenta_id); self.assertIsNotNone(compra[1])

    def test_saldo_insuficiente_hace_rollback_total(self):
        cuenta_id=self.cuenta(); conn=database.conectar(); conn.execute("UPDATE reseller_wallets SET saldo=1 WHERE revendedor_id=?",(self.reseller,)); conn.commit(); conn.close()
        with self.assertRaisesRegex(reseller_accounts.ResellerPurchaseError,"Saldo insuficiente"):
            reseller_accounts.comprar_plan_reseller(self.reseller,self.plan_cuenta,"poor")
        conn=database.conectar(); self.assertEqual(conn.execute("SELECT COUNT(*) FROM reseller_purchases").fetchone()[0],0); self.assertEqual(conn.execute("SELECT estado FROM nube_cuentas WHERE id=?",(cuenta_id,)).fetchone()[0],"disponible"); self.assertEqual(conn.execute("SELECT COUNT(*) FROM reseller_purchase_operations").fetchone()[0],0); conn.close()


if __name__ == "__main__": unittest.main()
