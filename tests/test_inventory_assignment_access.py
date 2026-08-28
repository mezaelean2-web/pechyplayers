try:
    from tests._bootstrap import TEST_DB
except ModuleNotFoundError:
    from _bootstrap import TEST_DB

import inspect
import os
import sqlite3
import tempfile
import unittest
from datetime import date

import database
import inventory_assignment_access as access


TODAY = date(2026, 8, 27)
START = "2026-08-01"
END = "2026-09-30"


class InventoryAssignmentAccessTest(unittest.TestCase):
    def setUp(self):
        descriptor, self.path = tempfile.mkstemp(suffix=".db")
        os.close(descriptor)
        self.original_db = database.DB
        database.DB = self.path
        conn = sqlite3.connect(self.path)
        conn.executescript("""
            PRAGMA foreign_keys=ON;
            CREATE TABLE revendedores(
                id INTEGER PRIMARY KEY, nombre TEXT NOT NULL, estado TEXT NOT NULL);
            CREATE TABLE reseller_purchases(
                id INTEGER PRIMARY KEY, revendedor_id INTEGER NOT NULL,
                cuenta_id INTEGER NOT NULL, perfil_id INTEGER, tipo_unidad TEXT NOT NULL,
                fecha_activacion TEXT, fecha_vencimiento TEXT,
                estado_persistido TEXT, cortada_at TEXT, updated_at TEXT);
            CREATE TABLE nube_cuentas(
                id INTEGER PRIMARY KEY, modalidad TEXT, estado TEXT,
                cliente_id INTEGER, nombre_cliente TEXT, fecha_entrega TEXT,
                dias_cuenta INTEGER, fecha_vencimiento TEXT, fecha_actualizacion TEXT);
            CREATE TABLE nube_perfiles(
                id INTEGER PRIMARY KEY, cuenta_id INTEGER NOT NULL, estado TEXT,
                cliente_id INTEGER, nombre_cliente TEXT, fecha_entrega TEXT,
                dias_cuenta INTEGER, fecha_vencimiento TEXT, fecha_actualizacion TEXT);
            CREATE TABLE nube_reemplazos(
                id INTEGER PRIMARY KEY, cuenta_anterior_id INTEGER,
                cuenta_nueva_id INTEGER, cliente_id INTEGER);
            CREATE TABLE nube_reemplazos_perfiles(
                id INTEGER PRIMARY KEY, perfil_anterior_id INTEGER,
                perfil_nuevo_id INTEGER, cuenta_anterior_id INTEGER,
                cuenta_nueva_id INTEGER);
            INSERT INTO revendedores VALUES(1,'Uno','activo');
            INSERT INTO revendedores VALUES(2,'Dos','activo');
        """)
        conn.commit()
        conn.close()

    def tearDown(self):
        database.DB = self.original_db
        os.remove(self.path)

    def execute(self, sql, params=()):
        conn = sqlite3.connect(self.path)
        try:
            conn.execute(sql, params)
            conn.commit()
        finally:
            conn.close()

    def account(self, account_id=10, *, mode="cuenta_completa", state="activa",
                reseller_id=1, assigned=True, start=START, end=END):
        label = f"Reseller #{reseller_id} - {'Uno' if reseller_id == 1 else 'Dos'}" if assigned else "Otra persona"
        self.execute("""INSERT INTO nube_cuentas VALUES(?,?,?,?,?,?,?,?,?)""",
                     (account_id, mode, state, reseller_id if assigned else 99, label,
                      start, 60, end, "v-account"))

    def profile(self, profile_id=20, account_id=10, *, state="activa",
                reseller_id=1, assigned=True, start=START, end=END):
        label = f"Reseller #{reseller_id} - {'Uno' if reseller_id == 1 else 'Dos'}" if assigned else "Otra persona"
        self.execute("""INSERT INTO nube_perfiles VALUES(?,?,?,?,?,?,?,?,?)""",
                     (profile_id, account_id, state, reseller_id if assigned else 99,
                      label, start, 60, end, f"v-profile-{profile_id}"))

    def purchase(self, purchase_id=100, *, reseller_id=1, account_id=10,
                 profile_id=None, unit_type="cuenta", state="active",
                 cut=None, start=START, end=END):
        self.execute("""INSERT INTO reseller_purchases VALUES(?,?,?,?,?,?,?,?,?,?)""",
                     (purchase_id, reseller_id, account_id, profile_id, unit_type,
                      start, end, state, cut, "v-purchase"))

    def authorize(self, reseller_id=1, purchase_id=100):
        return access.authorize_reseller_message_access(
            reseller_id, purchase_id, now=TODAY)

    def assert_denied(self, code, reseller_id=1, purchase_id=100):
        result = self.authorize(reseller_id, purchase_id)
        self.assertFalse(result["authorized"])
        self.assertEqual(result["safe_code"], code)
        self.assertIsNone(result["inventory_unit"])

    def test_active_owned_full_account_is_authorized(self):
        self.account(); self.purchase()
        result = self.authorize()
        self.assertTrue(result["authorized"])
        self.assertEqual(result["inventory_unit"], {
            "type": "cuenta", "account_id": 10, "profile_id": None})
        self.assertEqual(len(result["assignment_version"]), 64)

    def test_active_owned_profile_with_valid_parent_is_authorized(self):
        self.account(mode="perfiles", state="disponible", assigned=False)
        self.profile(); self.purchase(profile_id=20, unit_type="perfil")
        result = self.authorize()
        self.assertTrue(result["authorized"])
        self.assertEqual(result["inventory_unit"]["profile_id"], 20)

    def test_current_renewed_window_is_authorized(self):
        self.account(end="2027-01-01"); self.purchase(end="2027-01-01")
        self.assertTrue(self.authorize()["authorized"])

    def test_profile_replacement_a_to_b_is_authorized(self):
        self.account(10, mode="perfiles", state="disponible", assigned=False)
        self.account(11, mode="perfiles", state="disponible", assigned=False)
        self.profile(20, 10, state="reemplazada")
        self.profile(21, 11)
        self.purchase(profile_id=20, unit_type="perfil")
        self.execute("INSERT INTO nube_reemplazos_perfiles VALUES(1,20,21,10,11)")
        result = self.authorize()
        self.assertTrue(result["authorized"])
        self.assertEqual(result["inventory_unit"], {
            "type": "perfil", "account_id": 11, "profile_id": 21})

    def test_profile_replacement_chain_is_authorized(self):
        for account_id in (10, 11, 12):
            self.account(account_id, mode="perfiles", state="disponible", assigned=False)
        self.profile(20, 10, state="reemplazada")
        self.profile(21, 11, state="reemplazada")
        self.profile(22, 12)
        self.purchase(profile_id=20, unit_type="perfil")
        self.execute("INSERT INTO nube_reemplazos_perfiles VALUES(1,20,21,10,11)")
        self.execute("INSERT INTO nube_reemplazos_perfiles VALUES(2,21,22,11,12)")
        result = self.authorize()
        self.assertTrue(result["authorized"])
        self.assertEqual(result["inventory_unit"]["profile_id"], 22)

    def test_missing_purchase_is_denied(self):
        self.assert_denied("purchase_not_found")

    def test_purchase_owned_by_other_reseller_is_denied(self):
        self.account(reseller_id=2); self.purchase(reseller_id=2)
        self.assert_denied("ownership_mismatch")

    def test_expired_purchase_is_denied_even_if_persisted_active(self):
        self.account(); self.purchase(end="2026-08-20")
        self.assert_denied("purchase_expired")

    def test_cut_purchase_is_denied(self):
        self.account(); self.purchase(cut="2026-08-20T00:00:00Z")
        self.assert_denied("purchase_cut")

    def test_non_active_purchase_is_denied(self):
        self.account(); self.purchase(state="cut")
        self.assert_denied("purchase_inactive")

    def test_missing_account_is_denied(self):
        self.purchase()
        self.assert_denied("inventory_missing")

    def test_missing_profile_is_denied(self):
        self.account(mode="perfiles", state="disponible", assigned=False)
        self.purchase(profile_id=20, unit_type="perfil")
        self.assert_denied("inventory_missing")

    def test_profile_from_another_account_is_denied(self):
        self.account(10, mode="perfiles", state="disponible", assigned=False)
        self.account(11, mode="perfiles", state="disponible", assigned=False)
        self.profile(20, 11); self.purchase(profile_id=20, unit_type="perfil")
        self.assert_denied("assignment_mismatch")

    def test_down_parent_account_is_denied(self):
        self.account(mode="perfiles", state="caida", assigned=False)
        self.profile(); self.purchase(profile_id=20, unit_type="perfil")
        self.assert_denied("inventory_inactive")

    def test_down_profile_is_denied(self):
        self.account(mode="perfiles", state="disponible", assigned=False)
        self.profile(state="caida"); self.purchase(profile_id=20, unit_type="perfil")
        self.assert_denied("inventory_inactive")

    def test_trashed_account_is_denied(self):
        self.account(state="papelera"); self.purchase()
        self.assert_denied("inventory_inactive")

    def test_replaced_profile_without_successor_is_denied(self):
        self.account(mode="perfiles", state="disponible", assigned=False)
        self.profile(state="reemplazada"); self.purchase(profile_id=20, unit_type="perfil")
        self.assert_denied("replacement_unresolved")

    def test_ambiguous_profile_replacement_is_denied(self):
        for account_id in (10, 11, 12):
            self.account(account_id, mode="perfiles", state="disponible", assigned=False)
        self.profile(20, 10, state="reemplazada"); self.profile(21, 11); self.profile(22, 12)
        self.purchase(profile_id=20, unit_type="perfil")
        self.execute("INSERT INTO nube_reemplazos_perfiles VALUES(1,20,21,10,11)")
        self.execute("INSERT INTO nube_reemplazos_perfiles VALUES(2,20,22,10,12)")
        self.assert_denied("replacement_ambiguous")

    def test_replacement_cycle_is_denied(self):
        self.account(10, mode="perfiles", state="disponible", assigned=False)
        self.account(11, mode="perfiles", state="disponible", assigned=False)
        self.profile(20, 10, state="reemplazada"); self.profile(21, 11, state="reemplazada")
        self.purchase(profile_id=20, unit_type="perfil")
        self.execute("INSERT INTO nube_reemplazos_perfiles VALUES(1,20,21,10,11)")
        self.execute("INSERT INTO nube_reemplazos_perfiles VALUES(2,21,20,11,10)")
        self.assert_denied("replacement_cycle")

    def test_reassigned_unit_is_denied(self):
        self.account(assigned=False); self.purchase()
        self.assert_denied("assignment_mismatch")

    def test_competing_active_purchase_is_denied(self):
        self.account(); self.purchase(); self.purchase(101)
        self.assert_denied("ambiguous_assignment")

    def test_complete_account_replacement_fails_closed(self):
        self.account(state="reemplazada"); self.account(11)
        self.purchase()
        self.execute("INSERT INTO nube_reemplazos VALUES(1,10,11,1)")
        self.assert_denied("replacement_unresolved")

    def test_known_email_is_not_an_authorization_input(self):
        self.account(); self.purchase()
        result = access.authorize_reseller_message_access(
            1, "known-account@example.invalid", now=TODAY)
        self.assertFalse(result["authorized"])
        self.assertEqual(result["safe_code"], "invalid_request")
        self.assertEqual(
            tuple(inspect.signature(access.authorize_reseller_message_access).parameters)[:2],
            ("reseller_id", "reseller_purchase_id"))

    def test_result_never_contains_sensitive_fields(self):
        self.account(); self.purchase()
        serialized = repr(self.authorize()).lower()
        for forbidden in ("correo", "email", "contrasena", "password", "pin", "telefono", "otp"):
            self.assertNotIn(forbidden, serialized)

    def test_assignment_version_changes_when_inventory_changes(self):
        self.account(); self.purchase()
        before = self.authorize()["assignment_version"]
        self.execute("UPDATE nube_cuentas SET fecha_actualizacion='v-account-2' WHERE id=10")
        after = self.authorize()["assignment_version"]
        self.assertNotEqual(before, after)


if __name__ == "__main__":
    unittest.main()
