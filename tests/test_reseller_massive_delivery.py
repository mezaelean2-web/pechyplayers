try:
    from tests._bootstrap import TEST_DB
except ModuleNotFoundError:
    from _bootstrap import TEST_DB

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ResellerMassiveDeliveryContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.script = (ROOT / "static/js/reseller-cart.js").read_text(encoding="utf-8")
        cls.css = (ROOT / "static/css/reseller-cart.css").read_text(encoding="utf-8")
        cls.index = (ROOT / "templates/index.html").read_text(encoding="utf-8")
        cls.dashboard = (ROOT / "templates/resellers/_dashboard_base.html").read_text(encoding="utf-8")

    def test_selector_existe_y_cada_entrega_empieza_detallada(self):
        self.assertIn('data-delivery-format="detailed"', self.script)
        self.assertIn('data-delivery-format="massive"', self.script)
        self.assertIn('deliveryFormat = "detailed"', self.script)
        self.assertIn('role="tablist"', self.script)
        self.assertIn('aria-selected="true"', self.script)

    def test_cambio_es_render_local_sin_post_ni_mutacion(self):
        handler = self.script.split('const format = event.target.closest("[data-delivery-format]")', 1)[1].split("const toggle", 1)[0]
        self.assertIn("renderDelivery()", handler)
        for forbidden in ("fetch(", "purchase()", "saveCart()", "validate()", "localStorage", "sessionStorage"):
            self.assertNotIn(forbidden, handler)

    def test_agrupa_por_producto_plan_y_modalidad(self):
        self.assertIn('`${unit.producto}\\u0000${unit.plan || ""}\\u0000${unit.modalidad}`', self.script)
        self.assertIn("deliveryGroups", self.script)
        self.assertIn("groups.get(key).unidades.push(unit)", self.script)

    def test_cuenta_y_perfil_usan_solo_campos_reales(self):
        for key in ('fieldValue(unit, "correo")', 'fieldValue(unit, "contrasena")', 'fieldValue(unit, "perfil")', 'fieldValue(unit, "pin")'):
            self.assertIn(key, self.script)
        self.assertIn('.filter((value) => value != null && value !== "")', self.script)
        self.assertNotIn('PIN 0000', self.script)

    def test_listado_completo_y_mensaje_unico(self):
        self.assertIn("COPIAR LISTADO COMPLETO", self.script)
        self.assertIn("✓ LISTADO COPIADO", self.script)
        formatter = self.script.split("const formatMassiveDelivery", 1)[1].split("const copyText", 1)[0]
        self.assertEqual(formatter.count("Gracias por tu compra."), 1)
        self.assertIn("Recomendamos utilizar cada cuenta", formatter)
        self.assertIn("Los perfiles deben utilizarse únicamente en 1 dispositivo", formatter)
        self.assertIn('sections.join("\\n\\n\\n")', formatter)

    def test_listado_no_expone_metadatos_internos(self):
        formatter = self.script.split("const formatMassiveDelivery", 1)[1].split("const copyText", 1)[0]
        for forbidden in ("order_id", "purchase_id", "cuenta_id", "perfil_id", "token", "preview"):
            self.assertNotIn(forbidden, formatter)

    def test_escalas_comparten_lista_compacta_sin_limite_artificial(self):
        rendering = self.script.split("const massiveGroupHtml", 1)[1].split("const recommendationsHtml", 1)[0]
        self.assertIn("group.unidades.map", rendering)
        for forbidden in ("slice(0, 1)", "slice(0, 5)", "slice(0, 20)", "slice(0, 50)", "slice(0, 100)"):
            self.assertNotIn(forbidden, rendering)

    def test_scroll_interno_responsive_y_sin_overflow_horizontal(self):
        self.assertIn(".reseller-delivery-list{", self.css)
        self.assertIn("overflow-x:hidden", self.css)
        self.assertIn("overflow-y:auto", self.css)
        self.assertIn(".reseller-delivery-list.is-massive", self.css)
        self.assertIn("grid-template-columns:28px minmax(0,1fr)", self.css)
        self.assertIn("overflow-wrap:anywhere", self.css)

    def test_detallado_permanece_disponible(self):
        for contract in ("delivery.unidades.map(unitHtml)", "data-delivery-copy-field", "data-delivery-copy-unit", "data-delivery-copy-all", "data-delivery-toggle", "1 DISPOSITIVO"):
            self.assertIn(contract, self.script)

    def test_no_persistencia_credenciales_ni_whatsapp(self):
        self.assertNotIn("sessionStorage", self.script)
        self.assertNotIn("WhatsApp", self.script)
        self.assertNotIn("wa.me", self.script)
        self.assertIn('delivery = null; deliveryFormat = "detailed"', self.script)
        storage = self.script.split("const saveCart", 1)[1].split("const savePosition", 1)[0]
        self.assertNotIn("delivery", storage)
        self.assertNotIn("credencial", storage)

    def test_cache_busters_consistentes(self):
        for template in (self.index, self.dashboard):
            self.assertIn("reseller-cart.css') }}?v=4", template)
            self.assertIn("reseller-cart.js') }}?v=6", template)
            self.assertNotIn("reseller-cart.css') }}?v=3", template)
            self.assertNotIn("reseller-cart.js') }}?v=4", template)


if __name__ == "__main__":
    unittest.main()
