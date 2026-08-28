try:
    from tests._bootstrap import TEST_DB
except ModuleNotFoundError:
    from _bootstrap import TEST_DB

import json
import os
import sqlite3
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import app as app_module
import database
import inventory_assignment_access
from mail_providers import FakeMailProvider
import reseller_accounts
import reseller_mailbox
import resellers


class Clock:
    def __init__(self):
        self.value = datetime(2026, 8, 28, 5, 0, tzinfo=timezone.utc)

    def __call__(self):
        return self.value

    def advance(self, seconds):
        self.value += timedelta(seconds=seconds)


class ResellerMailboxTest(unittest.TestCase):
    def setUp(self):
        descriptor, self.path = tempfile.mkstemp(suffix=".db")
        os.close(descriptor)
        self.original_db = database.DB
        self.original_service = app_module.reseller_mailbox_service
        database.DB = self.path
        conn = sqlite3.connect(self.path)
        conn.executescript("""
            CREATE TABLE productos(
              id INTEGER PRIMARY KEY,nombre TEXT NOT NULL,imagen TEXT DEFAULT '',
              plan TEXT NOT NULL,precio TEXT NOT NULL,estado TEXT DEFAULT 'disponible');
            CREATE TABLE nube_clientes(
              id INTEGER PRIMARY KEY AUTOINCREMENT,nombre TEXT,telefono TEXT,
              telefono_normalizado TEXT,correo TEXT,activo INTEGER DEFAULT 1);
            CREATE TABLE nube_cuentas(
              id INTEGER PRIMARY KEY,plataforma TEXT NOT NULL,correo TEXT,
              contrasena TEXT DEFAULT '',pin TEXT DEFAULT '',cliente_id INTEGER,
              nombre_cliente TEXT DEFAULT '',telefono TEXT DEFAULT '',fecha_entrega TEXT DEFAULT '',
              dias_cuenta INTEGER DEFAULT 0,fecha_vencimiento TEXT DEFAULT '',
              estado TEXT DEFAULT 'disponible',modalidad TEXT DEFAULT 'cuenta_completa',
              fecha_actualizacion TEXT DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE nube_perfiles(
              id INTEGER PRIMARY KEY,cuenta_id INTEGER NOT NULL,nombre_perfil TEXT DEFAULT '',
              pin TEXT DEFAULT '',cliente_id INTEGER,nombre_cliente TEXT DEFAULT '',
              telefono TEXT DEFAULT '',fecha_entrega TEXT DEFAULT '',dias_cuenta INTEGER DEFAULT 0,
              fecha_vencimiento TEXT DEFAULT '',estado TEXT DEFAULT 'disponible',
              fecha_actualizacion TEXT DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE nube_reemplazos(
              id INTEGER PRIMARY KEY,cuenta_anterior_id INTEGER,cuenta_nueva_id INTEGER,cliente_id INTEGER);
            CREATE TABLE nube_reemplazos_perfiles(
              id INTEGER PRIMARY KEY,perfil_anterior_id INTEGER,perfil_nuevo_id INTEGER,
              cuenta_anterior_id INTEGER,cuenta_nueva_id INTEGER);
            INSERT INTO productos VALUES(1,'Netflix','','Premium','10000','disponible');
        """)
        conn.commit(); conn.close()
        resellers.inicializar_revendedores()
        reseller_accounts.inicializar_esquema()
        self.owner = resellers.crear_revendedor(
            "Andrea", "andrea@example.invalid", "3001234567", "Tienda", "ClaveSegura123")
        self.other = resellers.crear_revendedor(
            "Luis", "luis@example.invalid", "3007654321", "Tienda", "ClaveSegura123")
        self.clock = Clock()
        self.provider = FakeMailProvider(auto_message=False)
        self.repository = reseller_mailbox.InMemoryMailboxRepository()
        self.service = reseller_mailbox.ResellerMailboxService(
            self.provider, self.repository, self.clock)
        app_module.reseller_mailbox_service = self.service
        app_module.app.config.update(TESTING=True, SECRET_KEY="mailbox-test")
        self.client = app_module.app.test_client()

    def tearDown(self):
        app_module.reseller_mailbox_service = self.original_service
        database.DB = self.original_db
        os.remove(self.path)

    def login(self, reseller_id=None, client=None):
        client = client or self.client
        reseller = resellers.obtener_revendedor(reseller_id or self.owner)
        with client.session_transaction() as session:
            session["reseller_id"] = reseller["id"]
            session["reseller_auth_version"] = reseller["auth_version"]
            session["csrf_reseller"] = "mailbox-csrf"
        return client

    def purchase(self, *, owner=None, email="account@pechy.org", account_id=None,
                 profile=False, state="activa", purchase_end="2026-09-30"):
        owner = owner or self.owner
        account_id = account_id or (100 + self.scalar("SELECT COUNT(*) FROM nube_cuentas"))
        reseller = resellers.obtener_revendedor(owner)
        label = f"Reseller #{owner} - {reseller['nombre']}"
        start = "2026-08-01"
        conn = database.conectar()
        conn.execute("""INSERT INTO nube_cuentas
          (id,plataforma,correo,cliente_id,nombre_cliente,fecha_entrega,dias_cuenta,
           fecha_vencimiento,estado,modalidad,fecha_actualizacion)
          VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
          (account_id,"Netflix",email,owner,label if not profile else "",start,60,
           "2026-09-30","disponible" if profile else state,
           "perfiles" if profile else "cuenta_completa","account-v1"))
        profile_id = None
        if profile:
            profile_id = account_id * 10
            conn.execute("""INSERT INTO nube_perfiles
              (id,cuenta_id,nombre_perfil,cliente_id,nombre_cliente,fecha_entrega,
               dias_cuenta,fecha_vencimiento,estado,fecha_actualizacion)
              VALUES(?,?,?,?,?,?,?,?,?,?)""",
              (profile_id,account_id,"Perfil",owner,label,start,60,"2026-09-30",state,"profile-v1"))
        cursor = conn.execute("""INSERT INTO reseller_purchases
          (revendedor_id,plan_id,cuenta_id,perfil_id,tipo_unidad,operacion_origen,
           fecha_compra,fecha_activacion,fecha_vencimiento,dias_contratados,
           precio_pagado,estado_persistido,updated_at)
          VALUES(?,?,?,?,?,'purchase',?,?,?,?,10000,'active','purchase-v1')""",
          (owner,1,account_id,profile_id,"perfil" if profile else "cuenta",
           start,start,purchase_end,60))
        purchase_id = cursor.lastrowid
        conn.commit(); conn.close()
        return purchase_id

    def scalar(self, sql, params=()):
        conn = database.conectar()
        try: return conn.execute(sql, params).fetchone()[0]
        finally: conn.close()

    def unit(self, request_id):
        return self.repository.requests[request_id]["unit"]

    def request(self, email="account@pechy.org", owner=None):
        return self.service.request_message(owner or self.owner, email)

    def add(self, request_id, *, seconds, reference="provider-1",
            kind="numeric_code", value="482193", unit=None):
        self.provider.add_message(
            reference=reference, unit=unit or self.unit(request_id), service="Netflix",
            kind=kind, value=value,
            received_at=self.repository.requests[request_id]["requested_at"] + timedelta(seconds=seconds))

    def test_valid_owned_email_starts_waiting_and_calls_phase2(self):
        purchase_id = self.purchase()
        with patch.object(inventory_assignment_access, "authorize_reseller_message_access",
                          wraps=inventory_assignment_access.authorize_reseller_message_access) as authorize:
            result = self.request()
        self.assertEqual(result["status"], "waiting")
        authorize.assert_called_once_with(self.owner, purchase_id, now=self.clock.value)
        self.assertEqual(self.provider.begin_calls, 1)

    def test_email_normalization_supports_spaces_and_case(self):
        self.purchase(email="Account@Pechy.org")
        self.assertEqual(self.request("  ACCOUNT@PECHY.ORG  ")["status"], "waiting")

    def test_missing_other_invalid_and_partial_email_are_neutral(self):
        self.purchase(owner=self.other, email="other@pechy.org")
        for value in ("missing@pechy.org", "other@pechy.org", "netflix@", "pechy.org", ""):
            result = self.request(value)
            self.assertEqual(result["status"], "unavailable")
            self.assertEqual(result["message"], "No hay mensajes disponibles para esta cuenta.")
        self.assertEqual(self.provider.begin_calls, 0)

    def test_ambiguous_distinct_profiles_fail_closed(self):
        self.purchase(email="shared@pechy.org", account_id=101, profile=True)
        self.purchase(email="shared@pechy.org", account_id=102, profile=True)
        self.assertEqual(self.request("shared@pechy.org")["status"], "unavailable")
        self.assertEqual(self.provider.begin_calls, 0)

    def test_unauthorized_states_never_reach_provider(self):
        for index, (state, end) in enumerate((("caida","2026-09-30"),("reemplazada","2026-09-30"),("activa","2026-08-20")), 1):
            email = f"blocked{index}@pechy.org"
            self.purchase(email=email, account_id=200 + index, state=state, purchase_end=end)
            self.assertEqual(self.request(email)["status"], "unavailable")
        self.assertEqual(self.provider.begin_calls, 0)

    def test_t0_ignores_old_irrelevant_and_unsupported_messages(self):
        self.purchase(); result = self.request(); request_id = result["request_id"]
        self.add(request_id, seconds=-1, reference="old", value="111111")
        self.add(request_id, seconds=2, reference="other", value="222222",
                 unit={"type":"cuenta","account_id":999,"profile_id":None})
        self.add(request_id, seconds=3, reference="unsupported", kind="unsupported", value="333333")
        self.clock.advance(4)
        polled = self.service.poll_request(self.owner, request_id)
        self.assertEqual(polled["status"], "waiting")

    def test_first_valid_message_after_t0_wins_and_is_not_replaced(self):
        self.purchase(); request_id = self.request()["request_id"]
        self.add(request_id, seconds=10, reference="first", value="482193")
        self.add(request_id, seconds=19, reference="later", value="999999")
        self.clock.advance(20)
        first = self.service.poll_request(self.owner, request_id)
        again = self.service.poll_request(self.owner, request_id)
        self.assertEqual(first["message"]["value"], "482193")
        self.assertEqual(again["message"]["value"], "482193")
        self.assertEqual(len(first["history"]), 1)

    def test_assignment_change_before_message_denies_reveal(self):
        self.purchase(); request_id = self.request()["request_id"]
        self.add(request_id, seconds=3, value="SECRET-CODE")
        conn = database.conectar()
        conn.execute("UPDATE nube_cuentas SET fecha_actualizacion='account-v2' WHERE id=?",
                     (self.unit(request_id)["account_id"],)); conn.commit(); conn.close()
        self.clock.advance(4)
        result = self.service.poll_request(self.owner, request_id)
        self.assertEqual(result["status"], "unavailable")
        self.assertNotIn("SECRET-CODE", json.dumps(result))

    def test_request_expires_without_message(self):
        self.purchase(); request_id = self.request()["request_id"]
        self.clock.advance(reseller_mailbox.REQUEST_TTL_SECONDS + 1)
        self.assertEqual(self.service.poll_request(self.owner, request_id)["status"], "expired")

    def test_polling_is_throttled(self):
        self.purchase(); request_id = self.request()["request_id"]
        self.clock.advance(2); self.service.poll_request(self.owner, request_id)
        calls = self.provider.query_calls
        result = self.service.poll_request(self.owner, request_id)
        self.assertEqual(result["status"], "waiting")
        self.assertEqual(self.provider.query_calls, calls)

    def test_repeated_search_reuses_active_waiting_request(self):
        self.purchase(); first = self.request(); second = self.request()
        self.assertEqual(first["request_id"], second["request_id"])
        self.assertEqual(self.provider.begin_calls, 1)

    def test_new_search_for_same_account_returns_authorized_history(self):
        self.purchase(); first_id = self.request()["request_id"]
        self.add(first_id, seconds=2); self.clock.advance(3)
        delivered = self.service.poll_request(self.owner, first_id)["message"]
        second = self.request()
        self.assertEqual(second["status"], "waiting")
        self.assertEqual([item["id"] for item in second["history"]], [delivered["id"]])

    def test_rate_limit_is_neutral(self):
        for index in range(6):
            result = self.request(f"missing{index}@pechy.org")
        self.assertEqual(result["status"], "unavailable")
        self.assertNotIn("rate", json.dumps(result).lower())

    def test_history_isolated_by_reseller_purchase_and_idor(self):
        purchase_a = self.purchase(email="a@pechy.org", account_id=301)
        request_a = self.request("a@pechy.org")["request_id"]
        self.add(request_a, seconds=2); self.clock.advance(3)
        delivered = self.service.poll_request(self.owner, request_a)["message"]
        purchase_b = self.purchase(owner=self.other, email="b@pechy.org", account_id=302)
        request_b = self.request("b@pechy.org", owner=self.other)["request_id"]
        self.add(request_b, seconds=2, reference="b", value="777777"); self.clock.advance(3)
        self.service.poll_request(self.other, request_b)
        self.assertEqual(self.service.read_delivery(self.other, delivered["id"])["status"], "unavailable")
        self.assertEqual(len(self.repository.history[(self.owner, purchase_a)]), 1)
        self.assertEqual(len(self.repository.history[(self.other, purchase_b)]), 1)

    def test_audit_contains_no_email_code_or_provider_reference(self):
        self.purchase(); request_id = self.request()["request_id"]
        self.add(request_id, seconds=2, reference="provider-secret-ref", value="482193")
        self.clock.advance(3); self.service.poll_request(self.owner, request_id)
        payload = json.dumps(self.repository.audit)
        for forbidden in ("account@pechy.org", "482193", "provider-secret-ref"):
            self.assertNotIn(forbidden, payload)
        self.assertRegex(self.repository.audit[-1]["provider_reference"], r"^[0-9a-f]{24}$")

    def test_page_requires_session_has_sidebar_form_and_accessibility(self):
        self.assertEqual(self.client.get("/revendedores/buzon").status_code, 302)
        self.login(); response = self.client.get("/revendedores/buzon")
        html = response.get_data(as_text=True)
        for marker in ("Buzón de correo", "data-mailbox-search", "data-csrf-token",
                       "aria-live=\"polite\"", "reseller-mailbox.css", "reseller-mailbox.js"):
            self.assertIn(marker, html)
        self.assertIn("no-store", response.headers["Cache-Control"])

    def test_post_requires_session_and_csrf(self):
        response = self.client.post("/revendedores/buzon/solicitudes", json={"email":"a@pechy.org"})
        self.assertEqual(response.status_code, 401)
        self.login()
        response = self.client.post("/revendedores/buzon/solicitudes", json={"email":"a@pechy.org"})
        self.assertEqual(response.status_code, 403)

    def test_route_end_to_end_no_store_and_neutral_idor(self):
        self.purchase(); self.login()
        created = self.client.post("/revendedores/buzon/solicitudes",
            json={"email":"account@pechy.org"}, headers={"X-CSRF-Token":"mailbox-csrf"})
        self.assertEqual(created.status_code, 200)
        self.assertIn("no-store", created.headers["Cache-Control"])
        request_id = created.get_json()["request_id"]
        self.add(request_id, seconds=2); self.clock.advance(3)
        found = self.client.get(f"/revendedores/buzon/solicitudes/{request_id}")
        self.assertEqual(found.get_json()["status"], "found")
        other_client = app_module.app.test_client(); self.login(self.other, other_client)
        denied = other_client.get(f"/revendedores/buzon/solicitudes/{request_id}")
        self.assertEqual(denied.get_json()["status"], "unavailable")
        self.assertIn("no-store", denied.headers["Cache-Control"])

    def test_frontend_uses_form_submit_polling_and_text_content(self):
        source = Path("static/js/reseller-mailbox.js").read_text(encoding="utf-8")
        self.assertIn('form.addEventListener("submit"', source)
        self.assertIn("window.setTimeout(poll", source)
        self.assertIn("textContent", source)
        self.assertNotIn("innerHTML", source)
        self.assertNotIn("setInterval", source)


if __name__ == "__main__":
    unittest.main()
