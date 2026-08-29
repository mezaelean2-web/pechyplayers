try:
    from tests._bootstrap import TEST_DB
except ModuleNotFoundError:
    from _bootstrap import TEST_DB

import contextlib
import io
import imaplib
import json
import os
import socket
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import database
import inventory_assignment_access
import reseller_accounts
import reseller_mailbox
import reseller_mailbox_persistence
import resellers
from mailbox_bindings import MailboxBindingResolver
from mail_providers import FakeMailProvider
from pilot_message_adapter import PilotMessageAdapterRegistry
from pilot_private_email_gate import PilotPrivateEmailGate
from private_email_provider import PrivateEmailMailProvider


NOW = datetime(2026, 8, 28, 17, 0, tzinfo=timezone.utc)


class Clock:
    def __init__(self): self.value = NOW
    def __call__(self): return self.value
    def advance(self, seconds): self.value += timedelta(seconds=seconds)


class FakeIMAPTransport:
    def __init__(self):
        self.uidvalidity, self.uidnext, self.rows, self.commands = 77, 100, {}, []
    def examine(self, config, folder):
        self.commands.append(("EXAMINE", config, folder))
        return {"uidvalidity":self.uidvalidity,"uidnext":self.uidnext}
    def search_uids(self, config, folder, minimum, limit):
        self.commands.append(("UID SEARCH",config,folder,minimum,limit))
        return [uid for uid in sorted(self.rows) if uid >= minimum][:limit]
    def fetch_metadata(self, config, folder, uid):
        self.commands.append(("FETCH",config,folder,uid)); return self.rows[uid][0]
    def fetch_body_peek(self, config, folder, uid, part):
        self.commands.append(("BODY.PEEK",config,folder,uid,part)); return self.rows[uid][1]


def message(value):
    return f"CODE: {value}\r\n".encode()


def metadata(moment):
    return {"internaldate":moment,"size":500,"from":"mezaelean2@gmail.com",
            "to":"pilot@local.invalid","subject":"PECHY-PILOT-CODE",
            "authentication_results":"dkim=pass; spf=pass","content_type":"text/plain",
            "content_transfer_encoding":"","body_part":"TEXT"}


class PilotRealProviderIntegrationTests(unittest.TestCase):
    def setUp(self):
        fd,self.path=tempfile.mkstemp(suffix=".db"); os.close(fd)
        self.old_db=database.DB; database.DB=self.path
        conn=sqlite3.connect(self.path)
        conn.executescript("""
          CREATE TABLE productos(id INTEGER PRIMARY KEY,nombre TEXT,imagen TEXT,plan TEXT,precio TEXT,estado TEXT);
          CREATE TABLE nube_clientes(id INTEGER PRIMARY KEY,nombre TEXT,telefono TEXT,telefono_normalizado TEXT,correo TEXT,activo INTEGER);
          CREATE TABLE nube_cuentas(id INTEGER PRIMARY KEY,plataforma TEXT,correo TEXT,contrasena TEXT DEFAULT '',pin TEXT DEFAULT '',cliente_id INTEGER,nombre_cliente TEXT,telefono TEXT,fecha_entrega TEXT,dias_cuenta INTEGER,fecha_vencimiento TEXT,estado TEXT,modalidad TEXT,fecha_actualizacion TEXT);
          CREATE TABLE nube_perfiles(id INTEGER PRIMARY KEY,cuenta_id INTEGER,nombre_perfil TEXT,pin TEXT,cliente_id INTEGER,nombre_cliente TEXT,telefono TEXT,fecha_entrega TEXT,dias_cuenta INTEGER,fecha_vencimiento TEXT,estado TEXT,fecha_actualizacion TEXT);
          CREATE TABLE nube_reemplazos(id INTEGER PRIMARY KEY,cuenta_anterior_id INTEGER,cuenta_nueva_id INTEGER,cliente_id INTEGER);
          CREATE TABLE nube_reemplazos_perfiles(id INTEGER PRIMARY KEY,perfil_anterior_id INTEGER,perfil_nuevo_id INTEGER,cuenta_anterior_id INTEGER,cuenta_nueva_id INTEGER);
          INSERT INTO productos VALUES(40,'Pilot','','Pilot','0','disponible');
        """)
        conn.commit(); conn.close()
        resellers.inicializar_revendedores(); reseller_accounts.inicializar_esquema()
        for number in range(1,7):
            self.reseller=resellers.crear_revendedor(
                f"Pilot {number}",f"pilot-{number}@example.invalid","",f"Pilot {number}","Independent123")
        self.assertEqual(self.reseller,6)
        conn=database.conectar()
        conn.execute("""INSERT INTO nube_clientes VALUES(18,'Pilot','','','','1')""")
        conn.execute("""INSERT INTO nube_cuentas(id,plataforma,correo,contrasena,pin,cliente_id,
          nombre_cliente,telefono,fecha_entrega,dias_cuenta,fecha_vencimiento,estado,modalidad,
          fecha_actualizacion) VALUES(979,'PILOT','pilot@local.invalid','','',18,
          'Reseller #6 - Pilot 6','','2026-08-28',30,'2026-09-27','activa','cuenta_completa','account-v1')""")
        conn.execute("""INSERT INTO reseller_purchases(id,revendedor_id,plan_id,cuenta_id,perfil_id,
          tipo_unidad,operacion_origen,fecha_compra,fecha_activacion,fecha_vencimiento,dias_contratados,
          precio_pagado,estado_persistido,updated_at) VALUES(41,6,40,979,NULL,'cuenta','purchase',
          '2026-08-28','2026-08-28','2026-09-27',30,0,'active','purchase-v1')""")
        conn.commit(); conn.close()
        reseller_mailbox_persistence.initialize_schema()
        conn=database.conectar()
        conn.execute("""INSERT INTO reseller_mailbox_bindings(id,inventory_type,inventory_account_id,
          inventory_profile_id,provider,provider_config_id,folder_key,binding_version,enabled)
          VALUES(1,'cuenta',979,NULL,'private_email','pechy_pilot','INBOX',1,1)""")
        conn.commit(); conn.close()
        self.transport=FakeIMAPTransport()
        self.private=PrivateEmailMailProvider(
            self.transport,PilotMessageAdapterRegistry("pilot@local.invalid"))
        self.fake=FakeMailProvider(auto_message=False); self.clock=Clock()
        self.repo=reseller_mailbox_persistence.SQLiteMailboxRepository()
        self.service=reseller_mailbox.ResellerMailboxService(self.fake,self.repo,self.clock,
            binding_resolver=MailboxBindingResolver(),private_email_provider=self.private,
            private_email_gate=PilotPrivateEmailGate())
        self.socket_patch=patch.object(socket,"create_connection",side_effect=AssertionError("network forbidden"))
        self.socket_patch.start()
        self.imap_patch=patch.object(imaplib,"IMAP4_SSL",side_effect=AssertionError("real IMAP forbidden"))
        self.imap_patch.start()

    def tearDown(self):
        self.imap_patch.stop(); self.socket_patch.stop(); database.DB=self.old_db
        for suffix in ("-wal","-shm",""):
            try: os.remove(self.path+suffix)
            except FileNotFoundError: pass

    def request(self, email="pilot@local.invalid"):
        return self.service.request_message(6,email)

    def scalar(self,sql,args=()):
        conn=database.conectar()
        try: return conn.execute(sql,args).fetchone()[0]
        finally: conn.close()

    def add_valid(self,uid,value="482193",moment=None):
        self.transport.rows[uid]=(metadata(moment or self.clock.value+timedelta(seconds=1)),message(value))

    def test_exact_pilot_captures_t0_and_ignores_pre_t0(self):
        self.transport.rows[99]=(metadata(NOW+timedelta(seconds=1)),message("111111"))
        self.add_valid(100,"222222")
        result=self.request(); request_id=result["request_id"]
        row=self.repo.get_request(request_id,6)
        self.assertEqual((row["mailbox_binding_id"],row["binding_version"]),(1,1))
        self.assertEqual((row["provider_cursor"].uidvalidity,row["provider_cursor"].uidnext_boundary),(77,100))
        self.clock.advance(2); found=self.service.poll_request(6,request_id)
        self.assertEqual(found["message"]["value"],"222222")
        self.assertIn(("UID SEARCH","pechy_pilot","INBOX",100,20),self.transport.commands)

    def test_first_valid_post_t0_is_selected(self):
        self.add_valid(100,"222222"); self.add_valid(101,"333333")
        request_id=self.request()["request_id"]; self.clock.advance(2)
        self.assertEqual(self.service.poll_request(6,request_id)["message"]["value"],"222222")
        self.assertEqual(self.scalar("SELECT imap_uid FROM reseller_authorized_message_deliveries"),100)

    def test_email_input_cannot_change_binding_or_config(self):
        result=self.request("  PILOT@LOCAL.INVALID  ")
        self.assertEqual(result["status"],"waiting")
        self.assertEqual(self.transport.commands[0],("EXAMINE","pechy_pilot","INBOX"))

    def test_nonpilot_account_binding_and_config_stay_fake(self):
        cases=[(2,979,"pechy_pilot"),(1,979,"other_config"),(1,980,"pechy_pilot")]
        for binding_id,account_id,config in cases:
            with self.subTest(binding_id=binding_id,account_id=account_id,config=config):
                self.repo.reset(); self.fake.reset(); self.transport.commands.clear()
                conn=database.conectar()
                conn.execute("DELETE FROM reseller_mailbox_bindings")
                conn.execute("UPDATE reseller_purchases SET cuenta_id=? WHERE id=41",(account_id,))
                if account_id==980:
                    conn.execute("""INSERT OR IGNORE INTO nube_cuentas(id,plataforma,correo,
                      contrasena,pin,cliente_id,nombre_cliente,telefono,fecha_entrega,dias_cuenta,
                      fecha_vencimiento,estado,modalidad,fecha_actualizacion)
                      VALUES(980,'PILOT','other@local.invalid','','',18,'Reseller #6 - Pilot 6','','2026-08-28',30,
                      '2026-09-27','activa','cuenta_completa','other-v1')""")
                conn.execute("""INSERT INTO reseller_mailbox_bindings(id,inventory_type,inventory_account_id,
                  provider,provider_config_id,folder_key,binding_version,enabled)
                  VALUES(?,'cuenta',?,'private_email',?,'INBOX',1,1)""",(binding_id,account_id,config))
                conn.commit(); conn.close()
                email="other@local.invalid" if account_id==980 else "pilot@local.invalid"
                self.assertEqual(self.request(email)["status"],"waiting")
                self.assertEqual(self.fake.begin_calls,1); self.assertEqual(self.transport.commands,[])

    def test_other_purchase_and_reseller_do_not_reach_private(self):
        self.assertEqual(self.service.request_message(5,"pilot@local.invalid")["status"],"unavailable")
        conn=database.conectar(); conn.execute("UPDATE reseller_purchases SET id=42 WHERE id=41"); conn.commit(); conn.close()
        self.assertEqual(self.request()["status"],"waiting")
        self.assertEqual(self.fake.begin_calls,1); self.assertEqual(self.transport.commands,[])

    def test_uidvalidity_and_binding_version_changes_fail_closed(self):
        request_id=self.request()["request_id"]; self.transport.uidvalidity=78
        self.clock.advance(2)
        self.assertEqual(self.service.poll_request(6,request_id)["status"],"unavailable")
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM reseller_authorized_message_deliveries"),0)
        self.clock.advance(100); self.transport.uidvalidity=77
        request_id=self.request()["request_id"]
        conn=database.conectar(); conn.execute("UPDATE reseller_mailbox_bindings SET binding_version=2 WHERE id=1"); conn.commit(); conn.close()
        self.clock.advance(2)
        self.assertEqual(self.service.poll_request(6,request_id)["status"],"unavailable")

    def test_assignment_change_reauthorizes_before_reveal_and_idor_is_neutral(self):
        self.add_valid(100); request_id=self.request()["request_id"]
        conn=database.conectar(); conn.execute("UPDATE reseller_purchases SET updated_at='purchase-v2' WHERE id=41"); conn.commit(); conn.close()
        self.clock.advance(2)
        with patch.object(inventory_assignment_access,"authorize_reseller_message_access",
                          wraps=inventory_assignment_access.authorize_reseller_message_access) as authorize:
            self.assertEqual(self.service.poll_request(6,request_id)["status"],"unavailable")
        self.assertGreaterEqual(authorize.call_count,1)
        self.assertEqual(self.service.poll_request(5,request_id)["status"],"unavailable")
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM reseller_authorized_message_deliveries"),0)

    def test_reauthorization_immediately_before_reveal_fails_closed(self):
        self.add_valid(100); original=inventory_assignment_access.authorize_reseller_message_access
        calls=[]
        def authorization(*args,**kwargs):
            calls.append((args,kwargs))
            if len(calls)==3:
                return {"authorized":False,"safe_code":"purchase_inactive",
                        "inventory_unit":None,"assignment_version":None}
            return original(*args,**kwargs)
        with patch.object(inventory_assignment_access,"authorize_reseller_message_access",
                          side_effect=authorization):
            request_id=self.request()["request_id"]; self.clock.advance(2)
            result=self.service.poll_request(6,request_id)
        self.assertEqual(result["status"],"unavailable")
        self.assertEqual(len(calls),3)
        self.assertTrue(any(command[0]=="UID SEARCH" for command in self.transport.commands))
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM reseller_authorized_message_deliveries"),0)

    def test_safe_persistence_and_no_secret_output(self):
        secret="864209"; self.add_valid(100,secret); output=io.StringIO()
        with contextlib.redirect_stdout(output),contextlib.redirect_stderr(output):
            request_id=self.request()["request_id"]; self.clock.advance(2)
            found=self.service.poll_request(6,request_id)
        self.assertEqual(found["status"],"found")
        conn=database.conectar()
        stored=json.dumps([dict(row) for table in ("reseller_mailbox_requests",
          "reseller_authorized_message_deliveries","reseller_message_audit_events")
          for row in conn.execute(f"SELECT * FROM {table}")],default=str)
        conn.close()
        self.assertNotIn(secret,stored); self.assertNotIn(secret,output.getvalue())
        self.assertNotIn("pilot@local.invalid",stored)

    def test_reveal_revalidates_saved_assignment_and_binding_versions(self):
        self.add_valid(100); request_id=self.request()["request_id"]; self.clock.advance(2)
        delivery=self.service.poll_request(6,request_id)["message"]
        conn=database.conectar()
        conn.execute("UPDATE reseller_purchases SET updated_at='purchase-v2' WHERE id=41")
        conn.commit(); conn.close()
        self.assertEqual(self.service.read_delivery(6,delivery["id"])["status"],"unavailable")
        conn=database.conectar()
        conn.execute("UPDATE reseller_purchases SET updated_at='purchase-v1' WHERE id=41")
        conn.execute("UPDATE reseller_mailbox_bindings SET binding_version=2 WHERE id=1")
        conn.commit(); conn.close()
        revealed=self.service.read_delivery(6,delivery["id"])
        self.assertEqual(revealed["status"],"found")
        self.assertFalse(revealed["message"]["content_available"])


if __name__ == "__main__": unittest.main()
