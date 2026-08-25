try:
    from tests._bootstrap import TEST_DB
except ModuleNotFoundError:
    from _bootstrap import TEST_DB

import os
import random
import sqlite3
import tempfile
import unittest
from pathlib import Path

import database
import customer_cart
from app import app


class CustomerCartPhase1Test(unittest.TestCase):
    def setUp(self):
        descriptor, path = tempfile.mkstemp(suffix=".db")
        os.close(descriptor)
        self.path = path
        self.previous_db = database.DB
        database.DB = path
        conn = sqlite3.connect(path)
        conn.execute("""CREATE TABLE productos(
            id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT NOT NULL,
            imagen TEXT NOT NULL DEFAULT '', plan TEXT NOT NULL, precio TEXT NOT NULL,
            oferta_precio TEXT DEFAULT '', oferta_activa INTEGER DEFAULT 0,
            destacado INTEGER DEFAULT 0, visible INTEGER DEFAULT 1,
            orden INTEGER DEFAULT 999, categoria TEXT DEFAULT 'Streaming',
            orden_categoria INTEGER DEFAULT 999, estado TEXT DEFAULT 'disponible')""")
        conn.executemany(
            "INSERT INTO productos(id,nombre,plan,precio,oferta_precio,oferta_activa,visible,estado) VALUES(?,?,?,?,?,?,?,?)",
            [
                (1,"Netflix","Perfil","15.000","12.000",1,1,"disponible"),
                (2,"Disney","Perfil","10.000","",0,1,"disponible"),
                (3,"Excluido","Cuenta completa","20.000","18.000",1,1,"disponible"),
                (4,"Oculto","Perfil","9.000","",0,0,"disponible"),
                (5,"Agotado","Perfil","9.000","",0,1,"agotado"),
                (6,"Precio malo","Perfil","10.0000","",0,1,"disponible"),
            ],
        )
        conn.commit(); conn.close()
        customer_cart.initialize_schema()
        conn = sqlite3.connect(path)
        conn.execute("UPDATE productos SET participa_descuento_carrito=1 WHERE id IN (1,2)")
        conn.executemany(
            "INSERT INTO customer_cart_discount_rules(minimum_eligible_services,discount_bps,active) VALUES(?,?,?)",
            [(2,500,1),(3,1000,1),(4,1200,0)],
        )
        conn.commit(); conn.close()
        app.config.update(TESTING=True)
        self.client = app.test_client()

    def tearDown(self):
        database.DB = self.previous_db
        for suffix in ("", "-wal", "-shm"):
            try: os.remove(self.path + suffix)
            except FileNotFoundError: pass

    def calc(self, items):
        return customer_cart.calculate_cart({"items": items})

    def test_parser_cop_formatos_reales_y_fail_closed(self):
        for value, expected in (("$15.000",15000),("15.000",15000),("15000",15000),(0,0),(999999999999,999999999999)):
            with self.subTest(value=value): self.assertEqual(customer_cart.parse_cop(value), expected)
        for value in (None,"",-1,"-1","10.0000","1,000","1.00","NaN","inf",1.5,True,"10 MIL","$1,000"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError): customer_cart.parse_cop(value)

    def test_oferta_descuento_exclusion_y_totales(self):
        result = self.calc([{"plan_id":1,"quantity":1},{"plan_id":2,"quantity":1},{"plan_id":3,"quantity":1}])
        self.assertEqual(result["subtotal_lista"],45000)
        self.assertEqual(result["subtotal_bruto"],40000)
        self.assertEqual(result["subtotal_elegible"],22000)
        self.assertEqual(result["subtotal_excluido"],18000)
        self.assertEqual(result["discount_total"],1100)
        self.assertEqual(result["total_final"],38900)
        self.assertEqual(result["eligible_item_count"],2)
        self.assertEqual(result["discount_bps"],500)
        self.assertEqual(result["items"][2]["discount_amount"],0)

    def test_umbrales_desactivados_sin_reglas_y_solo_excluidos(self):
        self.assertEqual(self.calc([])["discount_bps"],0)
        self.assertEqual(self.calc([{"plan_id":1,"quantity":1}])["discount_total"],0)
        self.assertEqual(self.calc([{"plan_id":3,"quantity":3}])["eligible_item_count"],0)
        between = self.calc([{"plan_id":1,"quantity":2},{"plan_id":2,"quantity":2}])
        self.assertEqual(between["discount_bps"],1000)
        conn=sqlite3.connect(self.path); conn.execute("UPDATE customer_cart_discount_rules SET active=0"); conn.commit(); conn.close()
        self.assertEqual(self.calc([{"plan_id":1,"quantity":2}])["discount_total"],0)

    def test_quantity_expansion_limit_and_payload_security(self):
        result=self.calc([{"plan_id":1,"quantity":2}])
        self.assertEqual([x["line_number"] for x in result["items"]],[1,2])
        self.assertEqual(result["eligible_item_count"],2)
        self.calc([{"plan_id":1,"quantity":5}])
        invalid = [
            {"items":[{"plan_id":1,"quantity":0}]}, {"items":[{"plan_id":1,"quantity":-1}]},
            {"items":[{"plan_id":1,"quantity":1.5}]}, {"items":[{"plan_id":1,"quantity":"2"}]},
            {"items":[{"plan_id":1,"quantity":6}]}, {"items":[{"plan_id":1,"quantity":1,"price":1}]},
            {"items":[],"total":1}, {"items":"bad"}, [],
        ]
        for payload in invalid:
            with self.subTest(payload=payload):
                with self.assertRaises(customer_cart.CartValidationError): customer_cart.calculate_cart(payload)

    def test_planes_inexistentes_no_visibles_agotados_y_precio_invalido(self):
        for plan_id, code in ((99,"plan_not_found"),(4,"plan_unavailable"),(5,"plan_unavailable"),(6,"invalid_plan_price")):
            with self.subTest(plan_id=plan_id):
                with self.assertRaises(customer_cart.CartValidationError) as caught: self.calc([{"plan_id":plan_id,"quantity":1}])
                self.assertEqual(caught.exception.code,code)

    def test_redondeo_half_up_mayor_resto_y_empate_estable(self):
        conn=sqlite3.connect(self.path)
        conn.execute("UPDATE productos SET precio='5', oferta_activa=0 WHERE id=1")
        conn.execute("UPDATE productos SET precio='5' WHERE id=2")
        conn.execute("UPDATE customer_cart_discount_rules SET discount_bps=1000 WHERE minimum_eligible_services=2")
        conn.commit(); conn.close()
        result=self.calc([{"plan_id":1,"quantity":1},{"plan_id":2,"quantity":1}])
        self.assertEqual(result["discount_total"],1)
        self.assertEqual([x["discount_amount"] for x in result["items"]],[1,0])
        self.assertEqual(sum(x["line_total_final"] for x in result["items"]),result["total_final"])

    def test_propiedades_en_carritos_deterministas(self):
        rng=random.Random(20260825)
        for _ in range(150):
            quantities=[]; remaining=5
            for plan_id in (1,2,3):
                q=rng.randint(0,remaining); remaining-=q
                if q: quantities.append({"plan_id":plan_id,"quantity":q})
            result=self.calc(quantities)
            self.assertEqual(result["subtotal_bruto"],result["subtotal_elegible"]+result["subtotal_excluido"])
            self.assertLessEqual(result["discount_total"],result["subtotal_elegible"])
            self.assertEqual(result["total_final"],result["subtotal_bruto"]-result["discount_total"])
            self.assertEqual(sum(x["discount_amount"] for x in result["items"]),result["discount_total"])
            self.assertEqual(sum(x["line_total_final"] for x in result["items"]),result["total_final"])
            self.assertTrue(all(isinstance(v,int) and v>=0 for x in result["items"] for v in (x["discount_amount"],x["line_total_final"])))

    def test_migracion_idempotente_default_constraints_y_preserva_productos(self):
        customer_cart.initialize_schema(); customer_cart.initialize_schema()
        conn=sqlite3.connect(self.path)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM productos").fetchone()[0],6)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM productos WHERE participa_descuento_carrito NOT IN (0,1)").fetchone()[0],0)
        with self.assertRaises(sqlite3.IntegrityError): conn.execute("INSERT INTO customer_cart_discount_rules(minimum_eligible_services,discount_bps,active) VALUES(1,500,1)")
        with self.assertRaises(sqlite3.IntegrityError): conn.execute("INSERT INTO customer_cart_discount_rules(minimum_eligible_services,discount_bps,active) VALUES(9,10001,1)")
        self.assertEqual(conn.execute("PRAGMA foreign_key_check").fetchall(), [])
        conn.close()

    def test_preview_recalcula_y_no_acepta_autoridad_financiera(self):
        ok=self.client.post("/compras/carrito/preview",json={"items":[{"plan_id":1,"quantity":2}]})
        self.assertEqual(ok.status_code,200); self.assertEqual(ok.get_json()["preview"]["total_final"],22800)
        for extra in ("price","total","discount_bps","eligible"):
            response=self.client.post("/compras/carrito/preview",json={"items":[{"plan_id":1,"quantity":1,extra:1}]})
            self.assertEqual(response.status_code,400)
        self.assertEqual(self.client.post("/compras/carrito/preview",data="bad",content_type="application/json").status_code,400)

    def test_admin_auth_csrf_crud_y_flag(self):
        self.assertEqual(self.client.post("/admin/productos/descuentos-carrito",json={}).status_code,401)
        with self.client.session_transaction() as session:
            session["admin"]=True; session["csrf_revendedores"]="token"
        payload={"minimum_eligible_services":5,"discount_bps":1500,"active":True}
        self.assertEqual(self.client.post("/admin/productos/descuentos-carrito",json=payload).status_code,403)
        created=self.client.post("/admin/productos/descuentos-carrito",json=payload,headers={"X-CSRF-Token":"token"})
        self.assertEqual(created.status_code,201); rule_id=created.get_json()["id"]
        self.assertEqual(self.client.post("/admin/productos/descuentos-carrito",json=payload,headers={"X-CSRF-Token":"token"}).status_code,409)
        payload["discount_bps"]=1600; payload["active"]=False
        self.assertEqual(self.client.put(f"/admin/productos/descuentos-carrito/{rule_id}",json=payload,headers={"X-CSRF-Token":"token"}).status_code,200)
        self.assertEqual(self.client.patch("/admin/productos/3/descuento-carrito",json={"eligible":True},headers={"X-CSRF-Token":"token"}).status_code,200)
        conn=sqlite3.connect(self.path); self.assertEqual(conn.execute("SELECT participa_descuento_carrito FROM productos WHERE id=3").fetchone()[0],1); conn.close()
        self.assertEqual(self.client.delete(f"/admin/productos/descuentos-carrito/{rule_id}",headers={"X-CSRF-Token":"token"}).status_code,200)

    def test_preview_no_crea_tablas_de_fases_posteriores(self):
        conn=sqlite3.connect(self.path)
        before=conn.execute("SELECT group_concat(name,'|') FROM sqlite_master WHERE type='table'").fetchone()[0]
        conn.close()
        self.calc([{"plan_id":1,"quantity":1}])
        conn=sqlite3.connect(self.path); after=conn.execute("SELECT group_concat(name,'|') FROM sqlite_master WHERE type='table'").fetchone()[0]
        self.assertEqual(before,after)
        for name in ("customer_orders","customer_order_lines","customer_inventory_reservations","customer_order_payment_intents","customer_order_events","bold_payment_claims"):
            self.assertIsNone(conn.execute("SELECT 1 FROM sqlite_master WHERE name=?",(name,)).fetchone())
        conn.close()


class CustomerCartFrontendUxTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parents[1]
        cls.index = (root / "templates" / "index.html").read_text(encoding="utf-8")
        cls.cart_template = (root / "templates" / "_customer_cart.html").read_text(encoding="utf-8")
        cls.cart_js = (root / "static" / "js" / "customer-cart.js").read_text(encoding="utf-8")
        cls.mobile_js = (root / "static" / "js" / "mobile.js").read_text(encoding="utf-8")
        cls.css = (root / "static" / "css" / "style.css").read_text(encoding="utf-8")
        cls.modal_css = (root / "static" / "css" / "modal.css").read_text(encoding="utf-8")

    def test_tarjetas_no_agregan_directamente_y_ver_planes_permanece(self):
        self.assertNotIn('class="public-cart-add"', self.index)
        self.assertIn("✨ Ver planes", self.index)
        self.assertIn('data-public-plan-id="{{ plan.id }}"', self.index)

    def test_modal_crea_cta_con_plan_id_real_solo_para_publico(self):
        self.assertIn('agregar.textContent = "Agregar al carrito"', self.mobile_js)
        self.assertIn("agregar.dataset.publicCartAdd = plan.dataset.publicPlanId", self.mobile_js)
        self.assertIn("!plan.dataset.resellerPlanId", self.mobile_js)

    def test_carrito_es_modal_centrado_sin_drawer_o_seccion_permanente(self):
        self.assertIn('class="customer-cart-modal"', self.cart_template)
        self.assertIn("customer-cart-backdrop", self.cart_template)
        self.assertIn('role="dialog" aria-modal="true"', self.cart_template)
        self.assertNotIn("COMPRA DIRECTA", self.cart_template)
        self.assertIn("place-items:center", self.css)
        self.assertNotIn("scrollIntoView", self.cart_js)
        self.assertNotIn("translateX", self.css[self.css.index(".customer-cart-modal"):])

    def test_navegacion_publica_tiene_acceso_persistente_y_reseller_no_lo_usa(self):
        self.assertIn('class="public-nav-cart"', self.index)
        self.assertIn('data-customer-cart-open', self.index)
        self.assertIn('{% if not es_catalogo_reseller %}', self.index)
        self.assertIn('aria-haspopup="dialog"', self.index)

    def test_existe_un_solo_flotante_y_un_solo_modal_publico(self):
        self.assertEqual(self.cart_template.count("data-customer-cart-floating"), 1)
        self.assertEqual(self.cart_template.count("data-customer-cart-modal"), 1)
        self.assertEqual(self.cart_template.count('role="dialog"'), 1)
        self.assertEqual(self.index.count('class="public-nav-cart"'), 1)

    def test_flotante_siempre_disponible_sin_depender_del_header(self):
        floating = self.cart_template.split("data-customer-cart-floating", 1)[0]
        self.assertNotIn(" hidden", floating)
        self.assertNotIn("IntersectionObserver", self.cart_js)
        self.assertNotIn("headerAccess", self.cart_js)
        self.assertNotIn("setFloatingVisible", self.cart_js)

    def test_flotante_usa_pointer_events_umbral_y_capture(self):
        self.assertIn('const DRAG_THRESHOLD = 6', self.cart_js)
        self.assertIn('addEventListener("pointerdown"', self.cart_js)
        self.assertIn('addEventListener("pointermove"', self.cart_js)
        self.assertIn('addEventListener("pointerup",finishDrag)', self.cart_js)
        self.assertIn('addEventListener("pointercancel",finishDrag)', self.cart_js)
        self.assertIn('setPointerCapture(event.pointerId)', self.cart_js)
        self.assertIn('releasePointerCapture(event.pointerId)', self.cart_js)
        self.assertIn('Math.hypot(event.clientX-drag.startX,event.clientY-drag.startY)<DRAG_THRESHOLD', self.cart_js)
        self.assertIn('event.stopImmediatePropagation()', self.cart_js)

    def test_flotante_hace_snap_limita_y_restaura_posicion(self):
        self.assertIn('const FAB_POSITION_KEY = "customer_cart_fab_position"', self.cart_js)
        self.assertIn('window.innerWidth-floatingAccess.offsetWidth-safeMargin', self.cart_js)
        self.assertIn('window.innerHeight-floatingAccess.offsetHeight-safeMargin', self.cart_js)
        self.assertIn('rect.left+rect.width/2<window.innerWidth/2?"left":"right"', self.cart_js)
        self.assertIn('localStorage.setItem(FAB_POSITION_KEY', self.cart_js)
        self.assertIn('localStorage.getItem(FAB_POSITION_KEY)', self.cart_js)
        self.assertIn('window.addEventListener("resize",keepInside', self.cart_js)
        self.assertIn('window.addEventListener("orientationchange",keepInside', self.cart_js)

    def test_header_y_flotante_comparten_apertura_y_badge(self):
        self.assertIn('document.querySelectorAll("[data-customer-cart-open]")', self.cart_js)
        self.assertIn('document.querySelectorAll("[data-customer-cart-count]")', self.cart_js)
        self.assertIn('openCustomerCart()', self.cart_js)
        self.assertEqual(self.cart_template.count("data-customer-cart-count"), 1)

    def test_fab_supera_modal_producto_pero_no_modal_carrito(self):
        self.assertIn(".producto-modal{", self.modal_css)
        self.assertIn("z-index:99990", self.modal_css)
        self.assertIn(".customer-cart-floating{", self.css)
        self.assertIn("z-index:100000", self.css)
        self.assertIn(".customer-cart-modal{", self.css)
        self.assertIn("z-index:100010", self.css)

    def test_abrir_carrito_cierra_modal_producto_por_su_control_oficial(self):
        open_branch = self.cart_js.split("function openCustomerCart()", 1)[1].split("function closeCustomerCart()", 1)[0]
        self.assertIn('document.getElementById("productoModal")', open_branch)
        self.assertIn('document.getElementById("cerrarProductoModal")?.click()', open_branch)
        self.assertLess(open_branch.index('cerrarProductoModal'), open_branch.index('focusBeforeOpen=document.activeElement'))

    def test_agregar_desde_producto_no_cierra_modal_ni_abre_carrito(self):
        add_branch = self.cart_js.split('if(add){', 1)[1].split('return;}', 1)[0]
        self.assertNotIn("cerrarProductoModal", add_branch)
        self.assertNotIn("openCustomerCart()", add_branch)
        self.assertIn("pulseAccess()", add_branch)

    def test_modal_cierra_y_gestiona_focus_sin_cambiar_scroll(self):
        self.assertIn('event.key==="Escape"', self.cart_js)
        self.assertIn('data-customer-cart-close', self.cart_js)
        self.assertIn('focusBeforeOpen=document.activeElement', self.cart_js)
        self.assertIn('scrollBeforeOpen={left:window.scrollX,top:window.scrollY}', self.cart_js)
        self.assertIn('window.scrollTo({left:scrollBeforeOpen.left,top:scrollBeforeOpen.top,behavior:"auto"})', self.cart_js)
        self.assertIn('dialog.focus({preventScroll:true})', self.cart_js)
        self.assertIn('event.key!=="Tab"', self.cart_js)

    def test_apertura_centralizada_y_asset_con_cache_invalidada(self):
        self.assertIn('[data-customer-cart-open]:not([data-customer-cart-floating])', self.cart_js)
        self.assertIn('floatingAccess.addEventListener("click"', self.cart_js)
        self.assertIn("function openCustomerCart()", self.cart_js)
        self.assertIn("function closeCustomerCart()", self.cart_js)
        self.assertIn("if (!modal.hidden) return", self.cart_js)
        self.assertIn("customer-cart.js') }}?v=7", self.index)
        self.assertIn("css/style.css') }}?v=6", self.index)

    def test_estado_persistido_y_preview_siguen_siendo_minimos(self):
        self.assertIn('map(x => ({plan_id:x.plan_id, quantity:x.quantity}))', self.cart_js)
        self.assertIn('JSON.stringify({items:cart})', self.cart_js)
        self.assertIn('fetch("/compras/carrito/preview"', self.cart_js)
        self.assertNotIn("localStorage.setItem(STORAGE_KEY, JSON.stringify(preview", self.cart_js)

    def test_controles_contador_vaciar_y_fab_condicionales(self):
        for marker in ("data-cart-plus", "data-cart-minus", "data-cart-remove", "data-customer-cart-clear"):
            self.assertIn(marker, self.cart_js)
        self.assertIn("reduce((sum,item)=>sum+item.quantity,0)", self.cart_js)

    def test_agregar_actualiza_preview_pero_no_abre_carrito(self):
        add_branch = self.cart_js.split('if(add){', 1)[1].split('return;}', 1)[0]
        self.assertIn("change(Number(add.dataset.publicCartAdd),1)", add_branch)
        self.assertIn("pulseAccess()", add_branch)
        self.assertNotIn("openCustomerCart()", add_branch)

    def test_whatsapp_y_reseller_permanecen_en_el_template(self):
        self.assertIn("https://wa.me/", self.index)
        self.assertIn('include "resellers/_global_cart.html"', self.index)
        self.assertIn('js/reseller-cart.js', self.index)
        self.assertIn("defaultY=Math.max(safeMargin,limit.maxY-84)", self.cart_js)
        self.assertIn("position:fixed", self.css)
        self.assertIn("touch-action:none", self.css)
        self.assertIn("@media(prefers-reduced-motion:reduce)", self.css)


if __name__ == "__main__":
    unittest.main()
