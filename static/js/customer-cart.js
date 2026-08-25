(function () {
    "use strict";
    const STORAGE_KEY = "pechy.customerCart.v1";
    const FAB_POSITION_KEY = "customer_cart_fab_position";
    const DRAG_THRESHOLD = 6;
    const modal = document.querySelector("[data-customer-cart-modal]");
    const dialog = document.querySelector("[data-customer-cart]");
    if (!modal || !dialog) return;
    const lines = dialog.querySelector("[data-customer-cart-lines]");
    const errorBox = dialog.querySelector("[data-customer-cart-error]");
    const empty = dialog.querySelector("[data-customer-cart-empty]");
    const summary = dialog.querySelector("[data-customer-cart-summary]");
    const discountBanner = dialog.querySelector("[data-cart-discount-banner]");
    const floatingAccess = document.querySelector("[data-customer-cart-floating]");
    const cartStage = dialog.querySelector('[data-customer-cart-stage="cart"]');
    const customerStage = dialog.querySelector('[data-customer-cart-stage="customer"]');
    const readyStage = dialog.querySelector('[data-customer-cart-stage="ready"]');
    const checkoutForm = dialog.querySelector("[data-customer-checkout-form]");
    const checkoutNext = dialog.querySelector("[data-customer-checkout-next]");
    const payBold = dialog.querySelector("[data-customer-pay-bold]");
    const announcer = document.querySelector("[data-customer-cart-announcer]");
    let cart = load();
    let requestNumber = 0;
    let focusBeforeOpen = null;
    let scrollBeforeOpen = {left:0, top:0};
    let checkoutKey = null;
    let checkoutFingerprint = null;
    let cancellationRequest = Promise.resolve();
    let preparedOrderId = null;

    function load() {
        try {
            const value = JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]");
            if (!Array.isArray(value)) return [];
            return value.filter(x => Number.isInteger(x.plan_id) && Number.isInteger(x.quantity) && x.plan_id > 0 && x.quantity > 0).map(x => ({plan_id:x.plan_id, quantity:x.quantity}));
        } catch (_) { return []; }
    }
    function persist() { localStorage.setItem(STORAGE_KEY, JSON.stringify(cart)); }
    function money(value) { return new Intl.NumberFormat("es-CO", {style:"currency", currency:"COP", maximumFractionDigits:0}).format(value); }
    function totalQuantity() { return cart.reduce((sum,item)=>sum+item.quantity,0); }
    function updateCount() {
        const total=totalQuantity();
        document.querySelectorAll("[data-customer-cart-count]").forEach(node=>node.textContent=total);
        document.querySelectorAll("[data-customer-cart-open]").forEach(button=>button.setAttribute("aria-label",`Abrir carrito, ${total} ${total===1?"servicio":"servicios"}`));
        if(checkoutNext)checkoutNext.disabled=total===0;
    }
    function pulseAccess() {
        document.querySelectorAll("[data-customer-cart-open]").forEach(button=>{button.classList.remove("is-updated");requestAnimationFrame(()=>button.classList.add("is-updated"));});
    }
    function setupFloatingAccess() {
        if (!floatingAccess) return;
        const safeMargin=16;
        let drag=null;
        let suppressClick=false;
        function bounds() {
            return {maxX:Math.max(safeMargin,window.innerWidth-floatingAccess.offsetWidth-safeMargin),maxY:Math.max(safeMargin,window.innerHeight-floatingAccess.offsetHeight-safeMargin)};
        }
        function clamp(value,min,max) { return Math.min(Math.max(value,min),max); }
        function place(x,y,animate=false) {
            const limit=bounds();
            floatingAccess.classList.toggle("is-snapping",animate);
            floatingAccess.style.left=`${clamp(x,safeMargin,limit.maxX)}px`;
            floatingAccess.style.top=`${clamp(y,safeMargin,limit.maxY)}px`;
        }
        function savePosition() {
            const rect=floatingAccess.getBoundingClientRect();
            const limit=bounds();
            const side=rect.left+rect.width/2<window.innerWidth/2?"left":"right";
            const usable=Math.max(1,limit.maxY-safeMargin);
            localStorage.setItem(FAB_POSITION_KEY,JSON.stringify({side,y:clamp((rect.top-safeMargin)/usable,0,1)}));
        }
        function restorePosition() {
            const limit=bounds();
            let saved=null;
            try { saved=JSON.parse(localStorage.getItem(FAB_POSITION_KEY)||"null"); } catch (_) { saved=null; }
            const side=saved?.side==="left"?"left":"right";
            const normalized=Number.isFinite(saved?.y)?clamp(saved.y,0,1):null;
            const defaultY=Math.max(safeMargin,limit.maxY-84);
            place(side==="left"?safeMargin:limit.maxX,normalized===null?defaultY:safeMargin+normalized*Math.max(1,limit.maxY-safeMargin));
        }
        function finishDrag(event) {
            if (!drag||event.pointerId!==drag.pointerId) return;
            if (floatingAccess.hasPointerCapture(event.pointerId)) floatingAccess.releasePointerCapture(event.pointerId);
            floatingAccess.classList.remove("is-dragging");
            if (drag.moved) {
                const rect=floatingAccess.getBoundingClientRect();
                const limit=bounds();
                const x=rect.left+rect.width/2<window.innerWidth/2?safeMargin:limit.maxX;
                place(x,rect.top,true); savePosition(); suppressClick=true;
                window.setTimeout(()=>{suppressClick=false;},0);
            }
            drag=null;
        }
        floatingAccess.addEventListener("pointerdown",event=>{
            if (event.button!==undefined&&event.button!==0) return;
            const rect=floatingAccess.getBoundingClientRect();
            drag={pointerId:event.pointerId,startX:event.clientX,startY:event.clientY,offsetX:event.clientX-rect.left,offsetY:event.clientY-rect.top,moved:false};
            floatingAccess.setPointerCapture(event.pointerId);
        });
        floatingAccess.addEventListener("pointermove",event=>{
            if (!drag||event.pointerId!==drag.pointerId) return;
            if (!drag.moved&&Math.hypot(event.clientX-drag.startX,event.clientY-drag.startY)<DRAG_THRESHOLD) return;
            drag.moved=true; floatingAccess.classList.add("is-dragging");
            place(event.clientX-drag.offsetX,event.clientY-drag.offsetY);
            event.preventDefault();
        });
        floatingAccess.addEventListener("pointerup",finishDrag);
        floatingAccess.addEventListener("pointercancel",finishDrag);
        floatingAccess.addEventListener("click",event=>{
            if (suppressClick) { event.preventDefault(); event.stopImmediatePropagation(); suppressClick=false; return; }
            event.preventDefault(); openCustomerCart();
        });
        const keepInside=()=>{const rect=floatingAccess.getBoundingClientRect();place(rect.left,rect.top);savePosition();};
        window.addEventListener("resize",keepInside,{passive:true});
        window.addEventListener("orientationchange",keepInside,{passive:true});
        restorePosition();
    }
    function openCustomerCart() {
        if (!modal.hidden) return;
        const productModal=document.getElementById("productoModal");
        if (productModal?.classList.contains("abierto")) document.getElementById("cerrarProductoModal")?.click();
        focusBeforeOpen=document.activeElement;
        scrollBeforeOpen={left:window.scrollX,top:window.scrollY};
        modal.hidden=false; modal.setAttribute("aria-hidden","false");
        document.body.classList.add("customer-cart-modal-open");
        document.querySelectorAll("[data-customer-cart-open]").forEach(button=>button.setAttribute("aria-expanded","true"));
        dialog.focus({preventScroll:true});
    }
    function closeCustomerCart() {
        if (modal.hidden) return;
        modal.hidden=true; modal.setAttribute("aria-hidden","true");
        document.body.classList.remove("customer-cart-modal-open");
        window.scrollTo({left:scrollBeforeOpen.left,top:scrollBeforeOpen.top,behavior:"auto"});
        document.querySelectorAll("[data-customer-cart-open]").forEach(button=>button.setAttribute("aria-expanded","false"));
        if (focusBeforeOpen instanceof HTMLElement) focusBeforeOpen.focus({preventScroll:true});
    }
    function showStage(stage) {
        cartStage.hidden=stage!=="cart";
        customerStage.hidden=stage!=="customer";
        readyStage.hidden=stage!=="ready";
        if(stage==="customer")checkoutForm.querySelector("input")?.focus({preventScroll:true});
        if(stage==="ready")readyStage.focus({preventScroll:true});
    }
    function newCheckoutKey() {
        if(crypto.randomUUID)return crypto.randomUUID();
        const bytes=crypto.getRandomValues(new Uint8Array(24));
        return Array.from(bytes,value=>value.toString(16).padStart(2,"0")).join("");
    }
    async function loadCheckoutCustomer() {
        try{
            const response=await fetch("/compras/checkout-profile",{headers:{"X-CSRF-Token":dialog.dataset.checkoutCsrf||""},cache:"no-store"});
            const data=await response.json();
            if(!response.ok||!data.customer)return;
            const mapping={first_name:data.customer.first_name,last_name:data.customer.last_name,whatsapp:data.customer.whatsapp};
            Object.entries(mapping).forEach(([name,value])=>{const input=checkoutForm.elements.namedItem(name);if(input&&!input.value)input.value=value;});
        }catch(_){/* El formulario continúa disponible sin precarga. */}
    }
    function invalidatePreparedOrder() {
        checkoutKey=null;checkoutFingerprint=null;showStage("cart");
        cancellationRequest=cancellationRequest.then(async()=>{
            const response=await fetch("/compras/pedidos/cancelar-actual",{method:"POST",headers:{"Content-Type":"application/json","X-CSRF-Token":dialog.dataset.checkoutCsrf||""},body:"{}"});
            if(!response.ok){const data=await response.json();throw new Error(data.message||"No pudimos actualizar el pedido preparado.");}
        }).catch(error=>{errorBox.textContent=error.message;errorBox.hidden=false;});
    }
    function feedbackAdded(button) {
        if(button.dataset.feedbackActive==="true")return;
        const original=button.textContent;
        const product=document.getElementById("modalProductoNombre")?.textContent.trim()||"Producto";
        const plan=button.closest(".modal-plan")?.querySelector("span")?.textContent.trim()||"plan";
        button.dataset.feedbackActive="true";button.disabled=true;button.textContent="✓ Agregado al carrito";button.classList.add("is-added");
        announcer.textContent=`${product} ${plan} agregado al carrito`;
        window.setTimeout(()=>{button.disabled=false;button.textContent=original;button.classList.remove("is-added");delete button.dataset.feedbackActive;},1100);
    }
    async function submitCheckout() {
        if(!checkoutForm.reportValidity())return;
        await cancellationRequest;
        const fields=new FormData(checkoutForm);
        const customer={first_name:String(fields.get("first_name")||""),last_name:String(fields.get("last_name")||""),whatsapp:String(fields.get("whatsapp")||""),country_code:String(fields.get("country_code")||"")};
        const fingerprint=JSON.stringify({customer,items:cart});
        if(!checkoutKey||checkoutFingerprint!==fingerprint){checkoutKey=newCheckoutKey();checkoutFingerprint=fingerprint;}
        const submit=checkoutForm.querySelector("[data-customer-checkout-submit]");
        submit.disabled=true;submit.textContent="Preparando pedido…";errorBox.hidden=true;
        try{
            const response=await fetch("/compras/pedidos",{method:"POST",headers:{"Content-Type":"application/json","X-CSRF-Token":dialog.dataset.checkoutCsrf||""},body:JSON.stringify({customer,items:cart,idempotency_key:checkoutKey})});
            const data=await response.json();
            if(!response.ok)throw new Error(data.message||"No pudimos preparar el pedido.");
            readyStage.querySelector("[data-customer-order-id]").textContent=data.order.id;
            readyStage.querySelector("[data-customer-order-total]").textContent=money(data.order.total);
            preparedOrderId=data.order.id;
            showStage("ready");
        }catch(error){errorBox.textContent=error.message;errorBox.hidden=false;}
        finally{submit.disabled=false;submit.textContent="Continuar";}
    }
    document.querySelectorAll("[data-customer-cart-open]:not([data-customer-cart-floating])").forEach(button=>button.addEventListener("click",event=>{event.preventDefault();openCustomerCart();}));
    setupFloatingAccess();
    checkoutNext?.addEventListener("click",async()=>{if(cart.length){errorBox.hidden=true;await loadCheckoutCustomer();showStage("customer");}});
    dialog.querySelector("[data-customer-checkout-back]")?.addEventListener("click",()=>{checkoutKey=null;checkoutFingerprint=null;errorBox.hidden=true;showStage("cart");});
    checkoutForm?.addEventListener("submit",event=>{event.preventDefault();submitCheckout();});
    payBold?.addEventListener("click",async()=>{
        if(!preparedOrderId||payBold.disabled)return;
        payBold.disabled=true;payBold.textContent="Abriendo pago seguro…";errorBox.hidden=true;
        try{
            const response=await fetch(`/compras/pedidos/${encodeURIComponent(preparedOrderId)}/pago/bold`,{
                method:"POST",headers:{"Content-Type":"application/json","X-CSRF-Token":dialog.dataset.checkoutCsrf||""},body:"{}"});
            const data=await response.json();
            if(!response.ok)throw new Error(data.message||"No pudimos iniciar el pago.");
            if(!window.BoldCheckout){await new Promise((resolve,reject)=>{const script=document.createElement("script");script.src="https://checkout.bold.co/library/boldPaymentButton.js";script.onload=resolve;script.onerror=()=>reject(new Error("No fue posible cargar el checkout seguro de Bold."));document.head.appendChild(script);});}
            new window.BoldCheckout(data.checkout).open();
        }catch(error){errorBox.textContent=error.message;errorBox.hidden=false;payBold.disabled=false;payBold.textContent="Pagar con Bold";}
    });
    async function refresh() {
        persist(); updateCount(); errorBox.hidden=true;
        if (!cart.length) { lines.replaceChildren(); empty.hidden=false; summary.hidden=true; discountBanner.hidden=true; cartStage.classList.add("is-empty"); return; }
        const current=++requestNumber;
        try {
            const response=await fetch("/compras/carrito/preview", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({items:cart})});
            const data=await response.json(); if(current!==requestNumber)return;
            if(!response.ok)throw new Error(data.message||"No pudimos calcular el carrito.");
            render(data.preview);
        } catch(error) {
            if(current!==requestNumber)return;
            lines.replaceChildren(); empty.hidden=true; summary.hidden=true; discountBanner.hidden=true;
            errorBox.textContent=`${error.message} Conservamos tus productos para que puedas reintentar.`; errorBox.hidden=false;
        }
    }
    function render(preview) {
        const grouped=new Map();
        preview.items.forEach(item=>{const group=grouped.get(item.plan_id)||{item,quantity:0,total:0,discount:0};group.quantity++;group.total+=item.line_total_final;group.discount+=item.discount_amount;grouped.set(item.plan_id,group);});
        lines.replaceChildren(...Array.from(grouped.values()).map(group=>{
            const row=document.createElement("article"); row.className="customer-cart-line"; row.dataset.planId=group.item.plan_id;
            row.innerHTML='<span class="customer-cart-line__icon" aria-hidden="true">◆</span><div class="customer-cart-line__identity"><strong></strong><span></span><small class="customer-cart-line__unit"></small><small class="customer-cart-line__eligibility"></small></div><div class="customer-cart-quantity"><button type="button" data-cart-minus aria-label="Restar una unidad">−</button><b></b><button type="button" data-cart-plus aria-label="Sumar una unidad">+</button></div><strong class="customer-cart-line-total"></strong><button type="button" data-cart-remove aria-label="Eliminar del carrito">×</button>';
            row.querySelector(".customer-cart-line__identity strong").textContent=group.item.producto;
            row.querySelector(".customer-cart-line__identity>span").textContent=group.item.plan;
            row.querySelector(".customer-cart-line__unit").textContent=`Precio unitario: ${money(group.item.precio_efectivo)}`;
            row.querySelector(".customer-cart-line__eligibility").textContent=group.item.discount_eligible?(group.discount?`Descuento aplicado: ${money(group.discount)}`:"Participa en descuentos"):"No participa en descuentos";
            row.querySelector("b").textContent=group.quantity; row.querySelector(".customer-cart-line-total").textContent=money(group.total); return row;
        }));
        const hasItems=preview.items.length>0;
        empty.hidden=hasItems; summary.hidden=!hasItems; cartStage.classList.toggle("is-empty",!hasItems); discountBanner.hidden=!hasItems||preview.discount_total<=0;
        summary.querySelector("[data-cart-subtotal]").textContent=money(preview.subtotal_bruto);
        summary.querySelector("[data-cart-discount]").textContent=`− ${money(preview.discount_total)}`;
        summary.querySelector("[data-cart-total]").textContent=money(preview.total_final);
    }
    function change(planId,delta) {
        const item=cart.find(x=>x.plan_id===planId);
        if(!item&&delta>0)cart.push({plan_id:planId,quantity:1}); else if(item){item.quantity+=delta;if(item.quantity<=0)cart=cart.filter(x=>x!==item);}
        if(totalQuantity()>5){if(item)item.quantity-=delta;else cart=cart.filter(x=>x.plan_id!==planId);errorBox.textContent="El carrito admite máximo 5 servicios.";errorBox.hidden=false;return false;}
        refresh();invalidatePreparedOrder();return true;
    }
    document.addEventListener("click",event=>{
        const add=event.target.closest("[data-public-cart-add]");
        if(add){event.preventDefault();event.stopPropagation();if(add.dataset.feedbackActive==="true")return;if(change(Number(add.dataset.publicCartAdd),1)){pulseAccess();feedbackAdded(add);}return;}
        if(event.target.closest("[data-customer-cart-open]"))return;
        if(event.target.closest("[data-customer-cart-close]")){closeCustomerCart();return;}
        if(event.target.closest("[data-customer-cart-explore]")){closeCustomerCart();return;}
        const row=event.target.closest("[data-plan-id]");
        if(row&&row.closest("[data-customer-cart]")){const id=Number(row.dataset.planId);if(event.target.closest("[data-cart-plus]"))change(id,1);if(event.target.closest("[data-cart-minus]"))change(id,-1);if(event.target.closest("[data-cart-remove]")){cart=cart.filter(x=>x.plan_id!==id);refresh();invalidatePreparedOrder();}}
        if(event.target.closest("[data-customer-cart-clear]")){cart=[];refresh();invalidatePreparedOrder();}
    });
    document.addEventListener("keydown",event=>{
        if(modal.hidden)return;
        if(event.key==="Escape"){event.preventDefault();closeCustomerCart();return;}
        if(event.key!=="Tab")return;
        const focusable=Array.from(dialog.querySelectorAll('button:not([disabled]),a[href],[tabindex]:not([tabindex="-1"])'));
        if(!focusable.length){event.preventDefault();dialog.focus();return;}
        const first=focusable[0],last=focusable[focusable.length-1];
        if(event.shiftKey&&document.activeElement===first){event.preventDefault();last.focus();}else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first.focus();}
    });
    updateCount(); refresh();
}());
