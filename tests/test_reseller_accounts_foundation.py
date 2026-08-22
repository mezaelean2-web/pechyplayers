import json
import os
import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone

import database
import reseller_accounts
import resellers


class ResellerAccountsFoundationTest(unittest.TestCase):
    def setUp(self):
        descriptor, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(descriptor)
        self.original_db = database.DB
        database.DB = self.db_path
        conn = sqlite3.connect(self.db_path)
        conn.executescript("""
            PRAGMA foreign_keys=ON;
            CREATE TABLE productos (
                id INTEGER PRIMARY KEY, nombre TEXT NOT NULL,
                imagen TEXT NOT NULL DEFAULT '', plan TEXT NOT NULL,
                precio TEXT NOT NULL, estado TEXT DEFAULT 'disponible'
            );
            CREATE TABLE nube_cuentas (
                id INTEGER PRIMARY KEY, plataforma TEXT NOT NULL,
                modalidad TEXT NOT NULL DEFAULT 'cuenta_completa',
                estado TEXT NOT NULL DEFAULT 'disponible'
            );
            CREATE TABLE nube_perfiles (
                id INTEGER PRIMARY KEY, cuenta_id INTEGER NOT NULL,
                estado TEXT NOT NULL DEFAULT 'disponible',
                FOREIGN KEY(cuenta_id) REFERENCES nube_cuentas(id)
            );
            INSERT INTO productos(id,nombre,plan,precio)
                VALUES (1,'Netflix','Cuenta completa','999999'),
                       (2,'Netflix','Perfil','888888'),
                       (3,'Sin regla','1 mes','777777');
            INSERT INTO nube_cuentas(id,plataforma,modalidad)
                VALUES (10,'Netflix','cuenta_completa'),
                       (20,'Netflix','perfiles'),
                       (30,'Netflix','perfiles');
            INSERT INTO nube_perfiles(id,cuenta_id) VALUES (21,20),(31,30);
        """)
        conn.commit()
        conn.close()
        resellers.inicializar_revendedores()
        self.reseller_id = resellers.crear_revendedor(
            "Reseller Uno", "uno@example.com", "3001234567",
            "Negocio Uno", "ClaveSegura123"
        )
        self.otro_id = resellers.crear_revendedor(
            "Reseller Dos", "dos@example.com", "3007654321",
            "Negocio Dos", "ClaveSegura456"
        )
        reseller_accounts.guardar_regla_inventario_plan(
            1, "Netflix", "cuenta", 30
        )
        reseller_accounts.guardar_regla_inventario_plan(
            2, "Netflix", "perfil", 30
        )

    def tearDown(self):
        database.DB = self.original_db
        os.remove(self.db_path)

    def purchase(self, **changes):
        data = {
            "revendedor_id": self.reseller_id,
            "plan_id": 1,
            "cuenta_id": 10,
            "perfil_id": None,
            "tipo_unidad": "cuenta",
            "operacion_origen": "purchase",
            "fecha_compra": "2026-08-21",
            "fecha_activacion": "2026-08-21",
            "fecha_vencimiento": "2026-09-20",
            "dias_contratados": 30,
            "precio_pagado": 40000,
        }
        data.update(changes)
        return reseller_accounts.crear_purchase_fundacion(**data)

    def test_esquema_es_idempotente_y_crea_indices_requeridos(self):
        reseller_accounts.inicializar_esquema()
        reseller_accounts.inicializar_esquema()
        conn = sqlite3.connect(self.db_path)
        nombres = {row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type IN ('table','index','trigger')"
        )}
        conn.close()
        for nombre in {
            "reseller_purchases", "reseller_purchase_events",
            "reseller_purchase_operations", "reseller_plan_inventory_rules",
            "idx_reseller_purchases_owner", "idx_reseller_purchases_expiry",
            "idx_reseller_purchases_inventory", "uq_reseller_purchase_event_key",
            "trg_reseller_purchase_events_immutable_update",
        }:
            self.assertIn(nombre, nombres)

    def test_fk_reseller_y_plan_se_validan(self):
        with self.assertRaises(LookupError):
            self.purchase(revendedor_id=9999)
        with self.assertRaises(LookupError):
            self.purchase(plan_id=9999)

    def test_cuenta_completa_exige_perfil_nulo(self):
        compra = self.purchase()
        self.assertEqual(compra["cuenta_id"], 10)
        self.assertIsNone(compra["perfil_id"])
        with self.assertRaises(ValueError):
            self.purchase(perfil_id=21)

    def test_perfil_debe_pertenecer_a_cuenta(self):
        compra = self.purchase(
            plan_id=2, cuenta_id=20, perfil_id=21, tipo_unidad="perfil"
        )
        self.assertEqual((compra["cuenta_id"], compra["perfil_id"]), (20, 21))
        with self.assertRaisesRegex(ValueError, "no pertenece"):
            self.purchase(
                plan_id=2, cuenta_id=20, perfil_id=31, tipo_unidad="perfil"
            )

    def test_regla_rechaza_duracion_no_positiva(self):
        for duracion in (0, -1):
            with self.assertRaises(ValueError):
                reseller_accounts.guardar_regla_inventario_plan(
                    1, "Netflix", "cuenta", duracion
                )

    def test_purchase_rechaza_precio_negativo(self):
        with self.assertRaises(ValueError):
            self.purchase(precio_pagado=-1)

    def test_ownership_es_fail_closed(self):
        compra = self.purchase()
        self.assertIsNotNone(reseller_accounts.obtener_purchase_reseller(
            compra["id"], self.reseller_id
        ))
        self.assertIsNone(reseller_accounts.obtener_purchase_reseller(
            compra["id"], self.otro_id
        ))
        self.assertEqual(reseller_accounts.listar_purchases_reseller(self.otro_id), [])

    def test_idempotencia_misma_operacion_es_determinista(self):
        compra = self.purchase()
        primera = reseller_accounts.iniciar_operacion_idempotente(
            "renewal-unique-1", self.reseller_id, "renewal", compra["id"],
            {"ciclo": "2026-09-20"},
        )
        segunda = reseller_accounts.iniciar_operacion_idempotente(
            "renewal-unique-1", self.reseller_id, "renewal", compra["id"],
            {"ciclo": "2026-09-20"},
        )
        self.assertFalse(primera["duplicado"])
        self.assertTrue(segunda["duplicado"])
        self.assertEqual(primera["id"], segunda["id"])

    def test_idempotencia_rechaza_reutilizacion_incompatible(self):
        compra = self.purchase()
        reseller_accounts.iniciar_operacion_idempotente(
            "shared-key", self.reseller_id, "renewal", compra["id"],
            {"ciclo": "2026-09-20"},
        )
        with self.assertRaisesRegex(ValueError, "otra operación"):
            reseller_accounts.iniciar_operacion_idempotente(
                "shared-key", self.reseller_id, "mark_no_renew", compra["id"],
                {"ciclo": "2026-09-20"},
            )

    def test_operacion_no_admite_purchase_ajena(self):
        compra = self.purchase()
        with self.assertRaises(LookupError):
            reseller_accounts.iniciar_operacion_idempotente(
                "foreign-purchase", self.otro_id, "renewal", compra["id"], {}
            )

    def test_eventos_rechazan_secretos_y_son_inmutables(self):
        compra = self.purchase()
        for metadata in ({"password": "x"}, {"perfil": {"pin": "1234"}},
                         {"access_token": "x"}, {"correo_acceso": "x@y.com"}):
            with self.assertRaises(ValueError):
                reseller_accounts.registrar_evento_seguro(
                    compra["id"], "purchase", "system", datos_publicos=metadata
                )
        evento_id = reseller_accounts.registrar_evento_seguro(
            compra["id"], "purchase", "system",
            datos_publicos={"producto": "Netflix", "tipo": "cuenta"},
        )
        conn = sqlite3.connect(self.db_path)
        fila = conn.execute(
            "SELECT datos_publicos_json FROM reseller_purchase_events WHERE id=?",
            (evento_id,),
        ).fetchone()
        self.assertEqual(json.loads(fila[0])["producto"], "Netflix")
        with self.assertRaises(sqlite3.IntegrityError):
            conn.execute(
                "UPDATE reseller_purchase_events SET tipo='expired' WHERE id=?",
                (evento_id,),
            )
        conn.close()

    def test_estado_visual_y_zona_horaria_bogota(self):
        ahora = datetime(2026, 8, 21, 23, 30, tzinfo=reseller_accounts.ZONA_HORARIA)
        casos = {
            "2026-08-26": "ACTIVA",
            "2026-08-24": "PROXIMA_A_VENCER",
            "2026-08-21": "VENCE_HOY",
            "2026-08-20": "VENCIDA",
        }
        for fecha, esperado in casos.items():
            self.assertEqual(
                reseller_accounts.calcular_estado_visual(fecha, ahora=ahora),
                esperado,
            )
        self.assertEqual(
            reseller_accounts.calcular_estado_visual(
                "2026-08-26", no_renovar=True, ahora=ahora
            ),
            "NO_RENOVADA",
        )
        instante_utc = datetime(2026, 8, 22, 3, 30, tzinfo=timezone.utc)
        self.assertEqual(
            reseller_accounts.calcular_estado_visual("2026-08-21", ahora=instante_utc),
            "VENCE_HOY",
        )

    def test_plan_sin_regla_no_infiere_nombre_ni_precio_publico(self):
        self.assertIsNone(reseller_accounts.obtener_regla_inventario_plan(3))
        with self.assertRaisesRegex(ValueError, "regla de inventario"):
            self.purchase(plan_id=3)

    def test_regla_inactiva_no_es_elegible(self):
        reseller_accounts.guardar_regla_inventario_plan(
            1, "Netflix", "cuenta", 30, activo=False
        )
        self.assertIsNone(reseller_accounts.obtener_regla_inventario_plan(1))
        self.assertEqual(
            reseller_accounts.obtener_regla_inventario_plan(
                1, incluir_inactiva=True
            )["activo"],
            0,
        )
        with self.assertRaisesRegex(ValueError, "regla de inventario"):
            self.purchase()


if __name__ == "__main__":
    unittest.main()
