import json
import threading
import unittest
from datetime import datetime

import database
import reseller_accounts
import resellers
import wallets
from tests.test_reseller_purchase_periods import ResellerPurchasePeriodsTest


class ResellerRenewalsTest(unittest.TestCase):
    """Fase 3B sobre el mismo esquema real usado por el motor de compra."""

    def setUp(self):
        ResellerPurchasePeriodsTest.setUp(self)
        self._insertar_cuenta()
        self.compra = self._comprar("compra-base-renovacion", 1)
        self.purchase_id = self.compra["purchase_id"]

    def tearDown(self):
        ResellerPurchasePeriodsTest.tearDown(self)

    def _insertar_cuenta(self, estado="disponible"):
        return ResellerPurchasePeriodsTest._insertar_cuenta(self, estado)

    def _comprar(self, clave, periodos):
        return ResellerPurchasePeriodsTest._comprar(self, clave, periodos)

    def _renovar(self, clave, periodos=1, momento=None):
        return reseller_accounts.renovar_purchase_reseller(
            self.reseller, self.purchase_id, periodos, clave,
            momento or datetime(2026, 8, 25, 10, 0, tzinfo=reseller_accounts.ZONA_HORARIA),
        )

    def test_activa_conserva_dias_misma_purchase_y_misma_unidad(self):
        conn = database.conectar()
        antes = dict(conn.execute("SELECT * FROM reseller_purchases WHERE id=?", (self.purchase_id,)).fetchone())
        cantidad_antes = conn.execute("SELECT COUNT(*) FROM reseller_purchases").fetchone()[0]
        conn.close()
        resultado = self._renovar("renovar-activa", 2)
        self.assertTrue(resultado["fecha_vencimiento"].startswith("2026-11-19"))
        conn = database.conectar()
        despues = dict(conn.execute("SELECT * FROM reseller_purchases WHERE id=?", (self.purchase_id,)).fetchone())
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM reseller_purchases").fetchone()[0], cantidad_antes)
        self.assertEqual((antes["cuenta_id"], antes["perfil_id"]), (despues["cuenta_id"], despues["perfil_id"]))
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM reseller_purchase_events WHERE purchase_id=? AND tipo='renewal'", (self.purchase_id,)).fetchone()[0], 1)
        conn.close()

    def test_vencida_no_cortada_usa_ahora_como_base(self):
        conn = database.conectar()
        conn.execute("UPDATE reseller_purchases SET fecha_vencimiento='2026-08-10T10:00:00-05:00' WHERE id=?", (self.purchase_id,))
        conn.execute("UPDATE nube_cuentas SET fecha_vencimiento='2026-08-10' WHERE id=(SELECT cuenta_id FROM reseller_purchases WHERE id=?)", (self.purchase_id,))
        conn.commit(); conn.close()
        resultado = self._renovar("renovar-vencida", 1)
        self.assertTrue(resultado["fecha_vencimiento"].startswith("2026-09-24"))

    def test_precio_vigente_reemplaza_historico_y_no_fallback_publico(self):
        resellers.guardar_precio_personalizado(self.reseller, self.plan, 9000)
        resultado = self._renovar("precio-vigente", 3)
        self.assertEqual((resultado["precio_unitario"], resultado["precio_total"]), (9000, 27000))
        conn = database.conectar()
        self.assertEqual(conn.execute("SELECT precio_pagado FROM reseller_purchases WHERE id=?", (self.purchase_id,)).fetchone()[0], 8000)
        conn.execute("UPDATE precios_revendedor_personalizados SET activo=0 WHERE revendedor_id=? AND plan_id=?", (self.reseller, self.plan))
        conn.execute("UPDATE precios_revendedor_generales SET activo=0 WHERE plan_id=?", (self.plan,))
        conn.commit(); conn.close()
        with self.assertRaisesRegex(reseller_accounts.ResellerPurchaseError, "tarifa reseller"):
            self._renovar("sin-precio")

    def test_saldo_idempotencia_y_auditoria(self):
        saldo = wallets.obtener_saldo(self.reseller)
        primera = self._renovar("renovacion-idempotente", 2)
        segunda = self._renovar("renovacion-idempotente", 2)
        self.assertTrue(segunda["duplicado"])
        self.assertEqual(wallets.obtener_saldo(self.reseller), saldo - 16000)
        with self.assertRaisesRegex(reseller_accounts.ResellerPurchaseError, "otra operaciÃ³n"):
            self._renovar("renovacion-idempotente", 3)
        conn = database.conectar()
        evento = conn.execute("SELECT * FROM reseller_purchase_events WHERE tipo='renewal'").fetchone()
        datos = json.loads(evento["datos_publicos_json"])
        self.assertEqual((datos["precio_unitario"], datos["cantidad_periodos"], datos["duracion_base_dias"]), (8000, 2, 30))
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM reseller_wallet_transactions WHERE tipo='renewal'").fetchone()[0], 1)
        conn.close()

    def test_no_renovar_es_determinista_no_toca_wallet_inventario_y_se_revierte(self):
        conn = database.conectar()
        saldo = wallets.obtener_saldo(self.reseller)
        unidad = dict(conn.execute("SELECT * FROM nube_cuentas WHERE id=(SELECT cuenta_id FROM reseller_purchases WHERE id=?)", (self.purchase_id,)).fetchone())
        conn.close()
        primero = reseller_accounts.cambiar_no_renovar(self.purchase_id, self.reseller, True)
        segundo = reseller_accounts.cambiar_no_renovar(self.purchase_id, self.reseller, True)
        self.assertTrue(primero["cambio"]); self.assertFalse(segundo["cambio"])
        self.assertTrue(reseller_accounts.obtener_credenciales_autorizadas(self.purchase_id, self.reseller)["autorizadas"])
        reseller_accounts.cambiar_no_renovar(self.purchase_id, self.reseller, False)
        conn = database.conectar()
        actual = conn.execute("SELECT no_renovar,no_renovar_at FROM reseller_purchases WHERE id=?", (self.purchase_id,)).fetchone()
        self.assertEqual(tuple(actual), (0, None))
        self.assertEqual(wallets.obtener_saldo(self.reseller), saldo)
        self.assertEqual(dict(conn.execute("SELECT * FROM nube_cuentas WHERE id=?", (unidad["id"],)).fetchone()), unidad)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM reseller_purchase_events WHERE tipo='marked_no_renew'").fetchone()[0], 1)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM reseller_purchase_events WHERE tipo='unmarked_no_renew'").fetchone()[0], 1)
        conn.close()

    def test_renovar_limpia_no_renovar_y_cortada_se_rechaza(self):
        reseller_accounts.cambiar_no_renovar(self.purchase_id, self.reseller, True)
        self._renovar("renueva-marcada")
        conn = database.conectar()
        self.assertEqual(tuple(conn.execute("SELECT no_renovar,no_renovar_at FROM reseller_purchases WHERE id=?", (self.purchase_id,)).fetchone()), (0, None))
        conn.execute("UPDATE reseller_purchases SET cortada_at=CURRENT_TIMESTAMP WHERE id=?", (self.purchase_id,))
        conn.commit(); conn.close()
        with self.assertRaisesRegex(reseller_accounts.ResellerPurchaseError, "ya no admite"):
            self._renovar("renovar-cortada")
        with self.assertRaisesRegex(reseller_accounts.ResellerPurchaseError, "ya no admite"):
            reseller_accounts.cambiar_no_renovar(self.purchase_id, self.reseller, False)

    def test_concurrencia_serializa_renovaciones_y_misma_key_cobra_una_vez(self):
        barrera = threading.Barrier(2); resultados = []
        def ejecutar(clave):
            barrera.wait()
            try: resultados.append(self._renovar(clave))
            except Exception as error: resultados.append(error)
        hilos = [threading.Thread(target=ejecutar, args=(f"serial-{n}",)) for n in range(2)]
        for hilo in hilos: hilo.start()
        for hilo in hilos: hilo.join(15)
        self.assertEqual(len([r for r in resultados if isinstance(r, dict)]), 2)
        conn = database.conectar()
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM reseller_purchase_events WHERE tipo='renewal'").fetchone()[0], 2)
        conn.close()

    def test_limite_cantidad_regla_y_saldo(self):
        with self.assertRaises(reseller_accounts.ResellerPurchaseError): self._renovar("limite", 13)
        conn = database.conectar(); conn.execute("UPDATE reseller_plan_inventory_rules SET activo=0 WHERE plan_id=?", (self.plan,)); conn.commit(); conn.close()
        with self.assertRaisesRegex(reseller_accounts.ResellerPurchaseError, "inactiva"): self._renovar("regla-inactiva")
        conn = database.conectar(); conn.execute("UPDATE reseller_plan_inventory_rules SET activo=1 WHERE plan_id=?", (self.plan,)); conn.execute("UPDATE reseller_wallets SET saldo=1 WHERE revendedor_id=?", (self.reseller,)); conn.commit(); conn.close()
        with self.assertRaisesRegex(reseller_accounts.ResellerPurchaseError, "Saldo insuficiente"): self._renovar("sin-saldo")


if __name__ == "__main__":
    unittest.main()
