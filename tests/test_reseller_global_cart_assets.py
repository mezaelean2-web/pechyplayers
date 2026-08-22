import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class ResellerGlobalCartAssetsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.script = (ROOT / "static/js/reseller-cart.js").read_text(encoding="utf-8")
        cls.products = (ROOT / "static/js/reseller-products.js").read_text(encoding="utf-8")
        cls.partial = (ROOT / "templates/resellers/_global_cart.html").read_text(encoding="utf-8")
        cls.shell = (ROOT / "templates/resellers/_dashboard_base.html").read_text(encoding="utf-8")
        cls.index = (ROOT / "templates/index.html").read_text(encoding="utf-8")
        cls.cart_css = (ROOT / "static/css/reseller-cart.css").read_text(encoding="utf-8")

    def test_una_fuente_persistente_y_posicion_separada(self):
        self.assertIn('pechy-reseller-cart-v1', self.script)
        self.assertIn('pechy-reseller-cart-position-v1', self.script)
        self.assertIn('localStorage.removeItem(CART_KEY)', self.script)
        self.assertNotEqual(
            self.script.index('pechy-reseller-cart-v1'),
            self.script.index('pechy-reseller-cart-position-v1'),
        )

    def test_fab_oculto_badge_unidades_y_vaciado_cierra(self):
        self.assertIn('data-cart-open hidden', self.partial)
        self.assertIn('const totalUnits = () => cart.reduce', self.script)
        self.assertIn('fab.hidden = count === 0', self.script)
        self.assertIn('if (!count) close()', self.script)

    def test_drag_pointer_umbral_snap_clamp_y_resize(self):
        for contract in (
            'pointerdown', 'pointermove', 'pointerup', 'Math.hypot(dx, dy) < 7',
            'position.edge === "left"', 'Math.max(SAFE(), Math.min(maxY',
            'window.addEventListener("resize"', 'suppressClick',
        ):
            self.assertIn(contract, self.script)

    def test_modal_revalida_es_accesible_y_no_compra(self):
        self.assertIn('role="dialog" aria-modal="true"', self.partial)
        self.assertIn('aria-haspopup="dialog"', self.partial)
        self.assertIn('event.key === "Escape"', self.script)
        self.assertIn('event.key === "Tab"', self.script)
        self.assertIn('await validate()', self.script)
        self.assertIn('/revendedores/productos/carrito/preview', self.script)
        self.assertIn('data-cart-submit disabled', self.partial)
        self.assertNotIn('/comprar', self.script)

    def test_shell_privado_y_catalogo_reseller_comparten_parcial(self):
        include = '{% include "resellers/_global_cart.html" %}'
        self.assertIn(include, self.shell)
        self.assertIn(include, self.index)
        self.assertIn('{% if es_catalogo_reseller %}', self.index)
        self.assertNotIn('data-cart-open', self.products)
        self.assertIn('window.PechyResellerCart?.add', self.products)
        self.assertIn('pechy:cart:opening', self.products)

    def test_productos_usa_fab_global_aislado_y_sobre_modal(self):
        self.assertIn('reseller-global-cart__fab', self.partial)
        self.assertEqual(self.index.count('data-cart-open'), 0)
        self.assertIn('--reseller-layer-fab:100100', self.cart_css)
        self.assertIn('--reseller-layer-cart:100200', self.cart_css)
        self.assertIn('min-width:0', self.cart_css)

    def test_modal_tiene_header_body_scrolleable_y_footer_fijos(self):
        for contract in (
            'class="reseller-cart-header"', 'class="reseller-cart-body"',
            'data-cart-body', 'class="reseller-cart-footer"',
        ):
            self.assertIn(contract, self.partial)
        self.assertIn('.reseller-cart-body{', self.cart_css)
        self.assertIn('overflow-y:auto', self.cart_css)
        self.assertIn('.reseller-cart-footer{', self.cart_css)
        self.assertIn('flex:0 0 auto', self.cart_css)
        cart_rule = self.cart_css.split('.reseller-cart{', 1)[1].split('}', 1)[0]
        self.assertIn('padding:0', cart_rule)
        self.assertIn('overflow:hidden', cart_rule)
        self.assertNotIn('overflow-y:auto', cart_rule)

    def test_fab_incluye_svg_autonomo_visible(self):
        self.assertIn('<svg class="reseller-cart-fab__icon"', self.partial)
        self.assertIn('<path d="M3 3h2', self.partial)
        self.assertIn('fill:none', self.cart_css)
        self.assertIn('stroke:currentColor', self.cart_css)
        self.assertNotIn('data-lucide="shopping-cart"', self.partial)

    def test_configuradores_independientes_en_cada_plan(self):
        self.assertIn('const planStates = new WeakMap()', self.products)
        self.assertIn('node.insertAdjacentHTML("beforeend", configuratorHtml())', self.products)
        self.assertIn('data-plan-step="units"', self.products)
        self.assertIn('data-plan-step="periods"', self.products)
        self.assertIn('data-plan-submit', self.products)
        self.assertNotIn('selectedPlan', self.products)
        self.assertNotIn('resellerPurchaseBackdrop', self.index)

    def test_identidad_linea_plan_y_periodos_y_render_todas(self):
        self.assertIn('const key = `${normalized.plan_id}:${normalized.cantidad_periodos}`', self.script)
        self.assertIn('preview?.lineas?.map(lineHtml).join("")', self.script)
        self.assertIn('cart.map(fallbackLineHtml).join("")', self.script)
        self.assertIn('cart = normalizeCart(cart)', self.script)

    def test_lineas_compactas_y_resumen_centrado(self):
        self.assertIn('const removeButtonHtml', self.script)
        self.assertIn('<svg viewBox="0 0 24 24"', self.script)
        self.assertIn('<span>Subtotal<strong>${money(line.precio_total)}</strong></span>', self.script)
        self.assertNotIn('data-cart-remove>Eliminar', self.script)
        for contract in (
            '.reseller-global-cart .reseller-cart-line footer{',
            'align-items:center;margin-top:9px',
            'white-space:nowrap',
            '.reseller-global-cart .reseller-cart-summary{display:block;width:100%;box-sizing:border-box;margin:0;text-align:center}',
            '.reseller-global-cart .reseller-cart-summary__inner{display:block;width:min(440px,100%);box-sizing:border-box;margin:0 auto;padding:0;border:0}',
            'grid-template-columns:minmax(0,1fr) auto',
            'width:min(400px,100%)',
            '@media(max-width:360px)',
        ):
            self.assertIn(contract, self.cart_css)
        self.assertIn('class="reseller-cart-summary__inner"', self.partial)


if __name__ == "__main__":
    unittest.main()
