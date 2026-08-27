import unittest
from pathlib import Path


class CustomerOrderLookupPhase2C8Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root=Path(__file__).resolve().parents[1]
        cls.index=(root/"templates"/"index.html").read_text(encoding="utf-8")
        cls.template=(root/"templates"/"_customer_order_lookup.html").read_text(encoding="utf-8")
        cls.script=(root/"static"/"js"/"customer-order-lookup.js").read_text(encoding="utf-8")
        css=(root/"static"/"css"/"style.css").read_text(encoding="utf-8")
        cls.css=css[css.index(".customer-order-lookup-floating"):css.index(".customer-payment-result")]

    def test_tarjeta_fija_sale_del_footer_y_componente_se_carga_con_scripts_publicos(self):
        include='{% include "_customer_order_lookup.html" %}'
        self.assertEqual(self.index.count(include),1)
        self.assertGreater(self.index.index(include),self.index.index("</footer>"))
        self.assertIn("customer-order-lookup.js",self.index)
        self.assertIn("{% else %}{% include \"_customer_cart.html\" %}"+include,self.index)

    def test_boton_flotante_chat_es_accesible_y_no_comparte_posicion_del_carrito(self):
        self.assertIn('class="customer-order-lookup-floating"',self.template)
        self.assertIn('aria-label="Consultar mi pedido"',self.template)
        self.assertIn('aria-controls="customerOrderLookupModal"',self.template)
        self.assertIn('aria-expanded="false"',self.template)
        self.assertIn("position:fixed;right:27px;bottom:172px",self.css)
        self.assertIn("bottom:166px;width:50px;height:50px",self.css)
        self.assertNotIn("gradient",self.css)

    def test_modal_semantico_abre_cierra_escape_y_atrapa_foco(self):
        self.assertIn('role="dialog"',self.template);self.assertIn('aria-modal="true"',self.template)
        self.assertGreaterEqual(self.template.count("data-customer-order-lookup-close"),2)
        for marker in ('openButton.addEventListener("click", openModal)','control.addEventListener("click", closeModal)','event.key === "Escape"','event.key !== "Tab"','previousFocus.focus()'):
            self.assertIn(marker,self.script)
        self.assertIn('modal.setAttribute("aria-hidden", "false")',self.script)
        self.assertIn('modal.setAttribute("aria-hidden", "true")',self.script)

    def test_consulta_reutiliza_post_2c7_y_resultados_permanecen_en_modal(self):
        self.assertIn('fetch("/compras/pedidos/consultar"',self.script)
        self.assertIn('method: "POST"',self.script)
        self.assertIn('X-CSRF-Token',self.script)
        self.assertIn('data-customer-order-lookup-result',self.template)
        self.assertIn('data-customer-order-delivery-link',self.template)
        self.assertIn('Ver mi entrega',self.template)
        self.assertIn('deliveryLink.href = data.order.delivery_url',self.script)

    def test_html_inicial_y_almacenamiento_no_contienen_credenciales(self):
        source=self.template+self.script
        for forbidden in ("account_id","profile_id","fulfillment_line_id","guest_session_hash","customer_checkout_guest_token","sessionStorage","localStorage.setItem"):
            self.assertNotIn(forbidden,source)
        self.assertNotIn("password",self.template.lower());self.assertNotIn("contraseña",self.template.lower())

    def test_paleta_nueva_es_oscura_roja_y_verde_solo_para_fulfilled(self):
        for color in ("#eab308","#f5c542","#f4c430","#a855f7","#3b82f6"):
            self.assertNotIn(color,self.css.lower())
        self.assertIn("#11151b",self.css);self.assertIn("#ef2635",self.css)
        self.assertIn("data-state=fulfilled",self.css);self.assertIn("#86efac",self.css)


if __name__=="__main__":unittest.main()
