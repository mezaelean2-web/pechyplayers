try:
    from tests._bootstrap import TEST_DB
except ModuleNotFoundError:
    from _bootstrap import TEST_DB

import os
import tempfile
import threading
import unittest
from datetime import datetime
from unittest import mock

import database
import reseller_accounts
import resellers
import wallets


class ResellerRecoveryTest(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".db"); os.close(fd)
        self.original_db = database.DB; database.DB = self.path
        conn = database.conectar()
        conn.executescript("""
          PRAGMA foreign_keys=ON;
          CREATE TABLE productos(id INTEGER PRIMARY KEY AUTOINCREMENT,nombre TEXT NOT NULL,imagen TEXT DEFAULT '',plan TEXT NOT NULL,precio TEXT NOT NULL,estado TEXT DEFAULT 'disponible');
          CREATE TABLE nube_clientes(id INTEGER PRIMARY KEY AUTOINCREMENT,nombre TEXT,telefono TEXT,telefono_normalizado TEXT UNIQUE,fecha_actualizacion TEXT DEFAULT CURRENT_TIMESTAMP);
          CREATE TABLE nube_cuentas(id INTEGER PRIMARY KEY AUTOINCREMENT,plataforma TEXT NOT NULL,correo TEXT,contrasena TEXT DEFAULT '',pin TEXT DEFAULT '',cliente_id INTEGER,nombre_cliente TEXT DEFAULT '',telefono TEXT DEFAULT '',fecha_entrega TEXT DEFAULT '',dias_cuenta INTEGER DEFAULT 0,fecha_vencimiento TEXT DEFAULT '',estado TEXT DEFAULT 'disponible',modalidad TEXT DEFAULT 'cuenta_completa',fecha_creacion TEXT DEFAULT CURRENT_TIMESTAMP,fecha_actualizacion TEXT DEFAULT CURRENT_TIMESTAMP);
          CREATE TABLE nube_perfiles(id INTEGER PRIMARY KEY AUTOINCREMENT,cuenta_id INTEGER NOT NULL,nombre_perfil TEXT DEFAULT '',pin TEXT DEFAULT '',cliente_id INTEGER,nombre_cliente TEXT DEFAULT '',telefono TEXT DEFAULT '',fecha_entrega TEXT DEFAULT '',dias_cuenta INTEGER DEFAULT 0,fecha_vencimiento TEXT DEFAULT '',estado TEXT DEFAULT 'disponible',fecha_actualizacion TEXT DEFAULT CURRENT_TIMESTAMP,FOREIGN KEY(cuenta_id) REFERENCES nube_cuentas(id));
          CREATE TABLE nube_movimientos(id INTEGER PRIMARY KEY AUTOINCREMENT,cuenta_id INTEGER NOT NULL,tipo TEXT NOT NULL,descripcion TEXT,estado_anterior TEXT,estado_nuevo TEXT,cliente_nombre TEXT,fecha TEXT DEFAULT CURRENT_TIMESTAMP);
        """)
        conn.execute("INSERT INTO productos(nombre,plan,precio) VALUES ('Netflix','Premium','99999')")
        self.plan = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.commit(); conn.close()
        resellers.inicializar_revendedores(); reseller_accounts.inicializar_esquema()
        self.reseller = resellers.crear_revendedor("Recovery", "recovery@test.com", "3001234567", "Recovery", "ClaveSegura123")
        wallets.apply_wallet_transaction(self.reseller, "manual_credit", 500000, "Prueba")
        conn = database.conectar()
        conn.execute("INSERT INTO reseller_plan_inventory_rules(plan_id,plataforma,tipo_unidad,duracion_dias,activo) VALUES (?,?,?,?,1)", (self.plan,"Netflix","cuenta",30))
        conn.commit(); conn.close()
        resellers.guardar_precio_general(self.plan, 10000)

    def tearDown(self):
        database.DB = self.original_db
        try: os.remove(self.path)
        except PermissionError: pass

    def antigua(self, tipo="cuenta"):
        conn = database.conectar()
        modalidad = "cuenta_completa" if tipo == "cuenta" else "perfiles"
        cuenta = conn.execute("INSERT INTO nube_cuentas(plataforma,correo,contrasena,modalidad,estado,duracion_unidad_dias) VALUES ('Netflix','actual@test.com','clave-actual',?,'disponible',30)", (modalidad,)).lastrowid
        perfil = None
        if tipo == "perfil":
            perfil = conn.execute("INSERT INTO nube_perfiles(cuenta_id,nombre_perfil,pin,estado) VALUES (?,'Uno','2468','disponible')", (cuenta,)).lastrowid
        compra = conn.execute("""INSERT INTO reseller_purchases
            (revendedor_id,plan_id,cuenta_id,perfil_id,tipo_unidad,operacion_origen,fecha_compra,
             fecha_activacion,fecha_vencimiento,dias_contratados,precio_pagado,estado_persistido,cortada_at)
            VALUES (?,?,?,?,?,'purchase','2026-06-01','2026-06-01','2026-07-01',30,8000,'cut','2026-07-02')""",
            (self.reseller,self.plan,cuenta,perfil,tipo)).lastrowid
        conn.commit(); conn.close(); return compra, cuenta, perfil

    def recuperar(self, compra, key="recovery-1", cantidad=3):
        return reseller_accounts.recuperar_purchase_reseller(
            self.reseller, compra, cantidad, key,
            datetime(2026,8,22,10,0,tzinfo=reseller_accounts.ZONA_HORARIA))

    def test_cuenta_nuevo_ciclo_precio_actual_idempotencia_y_credenciales(self):
        antigua, cuenta, _ = self.antigua()
        primero = self.recuperar(antigua); segundo = self.recuperar(antigua)
        self.assertEqual(primero["purchase_id"], segundo["purchase_id"]); self.assertTrue(segundo["duplicado"])
        conn = database.conectar()
        vieja = dict(conn.execute("SELECT * FROM reseller_purchases WHERE id=?",(antigua,)).fetchone())
        nueva = dict(conn.execute("SELECT * FROM reseller_purchases WHERE id=?",(primero["purchase_id"],)).fetchone())
        self.assertEqual((vieja["estado_persistido"],vieja["cortada_at"]),("cut","2026-07-02"))
        self.assertEqual((nueva["cuenta_id"],nueva["operacion_origen"],nueva["compra_anterior_id"],nueva["precio_pagado"],nueva["dias_contratados"]),(cuenta,"recovery",antigua,30000,90))
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM reseller_wallet_transactions WHERE tipo='recovery'").fetchone()[0],1)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM reseller_purchase_events WHERE tipo='recovery'").fetchone()[0],1)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM nube_movimientos WHERE tipo='recuperacion_reseller'").fetchone()[0],1)
        conn.close()
        self.assertFalse(reseller_accounts.obtener_credenciales_autorizadas(antigua,self.reseller)["autorizadas"])
        campos = reseller_accounts.obtener_credenciales_autorizadas(nueva["id"],self.reseller)["campos"]
        self.assertIn("clave-actual", [campo["valor"] for campo in campos])

    def test_perfil_recupera_el_mismo_y_solo_su_pin(self):
        conn=database.conectar(); conn.execute("UPDATE reseller_plan_inventory_rules SET tipo_unidad='perfil' WHERE plan_id=?",(self.plan,)); conn.commit(); conn.close()
        antigua, cuenta, perfil = self.antigua("perfil")
        conn=database.conectar(); otro=conn.execute("INSERT INTO nube_perfiles(cuenta_id,nombre_perfil,pin,estado) VALUES (?,'Otro','9999','disponible')",(cuenta,)).lastrowid; conn.commit(); conn.close()
        resultado=self.recuperar(antigua,"perfil",1)
        conn=database.conectar(); nueva=conn.execute("SELECT * FROM reseller_purchases WHERE id=?",(resultado["purchase_id"],)).fetchone()
        self.assertEqual(nueva["perfil_id"],perfil); self.assertEqual(conn.execute("SELECT estado FROM nube_perfiles WHERE id=?",(otro,)).fetchone()[0],"disponible"); conn.close()
        valores=[x["valor"] for x in reseller_accounts.obtener_credenciales_autorizadas(nueva["id"],self.reseller)["campos"]]
        self.assertIn("2468",valores); self.assertNotIn("9999",valores)

    def test_revalidacion_saldo_idempotencia_incompatible_y_rollback(self):
        antigua, cuenta, _ = self.antigua()
        conn=database.conectar(); conn.execute("UPDATE nube_cuentas SET nombre_cliente='Otro' WHERE id=?",(cuenta,)); conn.commit(); conn.close()
        with self.assertRaises(reseller_accounts.ResellerPurchaseError): self.recuperar(antigua)
        conn=database.conectar(); conn.execute("UPDATE nube_cuentas SET nombre_cliente='' WHERE id=?",(cuenta,)); conn.commit(); conn.close()
        original=wallets.apply_wallet_transaction
        def falla(*args,**kwargs): original(*args,**kwargs); raise RuntimeError("fallo")
        with mock.patch.object(wallets,"apply_wallet_transaction",side_effect=falla):
            with self.assertRaises(RuntimeError): self.recuperar(antigua,"rollback")
        conn=database.conectar()
        self.assertEqual(conn.execute("SELECT estado FROM nube_cuentas WHERE id=?",(cuenta,)).fetchone()[0],"disponible")
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM reseller_purchases").fetchone()[0],1); conn.close()

    def test_concurrencia_un_solo_recovery_efectivo(self):
        antigua, _, _ = self.antigua(); barrera=threading.Barrier(2); resultados=[]
        def tarea(key):
            barrera.wait()
            try: resultados.append(("ok",self.recuperar(antigua,key,1)))
            except Exception as error: resultados.append(("error",error))
        hilos=[threading.Thread(target=tarea,args=(f"c-{n}",)) for n in range(2)]
        [h.start() for h in hilos]; [h.join(15) for h in hilos]
        self.assertEqual(sum(tipo=="ok" for tipo,_ in resultados),1)
        conn=database.conectar()
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM reseller_wallet_transactions WHERE tipo='recovery'").fetchone()[0],1); conn.close()


if __name__ == "__main__": unittest.main()
