(() => {
  "use strict";
  const root = document.querySelector("[data-reseller-global-cart]");
  if (!root) return;
  const qs = (selector, scope = root) => scope?.querySelector(selector);
  const fab = qs("[data-cart-open]");
  const shell = qs("[data-cart-shell]");
  const dialog = qs(".reseller-cart", shell);
  const config = JSON.parse(document.getElementById("resellerCartConfig")?.textContent || "{}");
  const CART_KEY = "pechy-reseller-cart-v1";
  const POSITION_KEY = "pechy-reseller-cart-position-v1";
  const SAFE = () => parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--reseller-cart-safe")) || 14;
  const money = (value) => value == null ? "Precio por configurar" : `$${Number(value).toLocaleString("es-CO")} COP`;
  const escapeHtml = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char]);
  const put = (selector, value) => { const node = qs(selector); if (node) node.textContent = value; };
  let cart = [], preview = null, validating = false, lastFocus = null;
  let intentId = window.crypto?.randomUUID?.() || `cart-${Date.now()}`;
  let position = { edge: "right", yRatio: .76 };

  const normalizeCart = (lines) => {
    const combined = new Map();
    for (const line of Array.isArray(lines) ? lines : []) {
      const normalized = { plan_id: Number(line.plan_id), cantidad_unidades: Number(line.cantidad_unidades), cantidad_periodos: Number(line.cantidad_periodos) };
      if (!Number.isInteger(normalized.plan_id) || !Number.isInteger(normalized.cantidad_unidades) || normalized.cantidad_unidades < 1 || !Number.isInteger(normalized.cantidad_periodos) || normalized.cantidad_periodos < 1) continue;
      const key = `${normalized.plan_id}:${normalized.cantidad_periodos}`;
      const current = combined.get(key);
      if (current) current.cantidad_unidades += normalized.cantidad_unidades; else combined.set(key, normalized);
    }
    return [...combined.values()];
  };

  const load = () => {
    try {
      const saved = JSON.parse(localStorage.getItem(CART_KEY) || "{}");
      if (Array.isArray(saved.lineas)) cart = normalizeCart(saved.lineas);
      if (saved.cart_intent_id) intentId = saved.cart_intent_id;
    } catch (_error) {}
    try { position = { ...position, ...JSON.parse(localStorage.getItem(POSITION_KEY) || "{}") }; } catch (_error) {}
  };
  const saveCart = () => { try { if (cart.length) localStorage.setItem(CART_KEY, JSON.stringify({ cart_intent_id: intentId, lineas: cart })); else { localStorage.removeItem(CART_KEY); intentId = window.crypto?.randomUUID?.() || `cart-${Date.now()}`; } } catch (_error) {} };
  const savePosition = () => { try { localStorage.setItem(POSITION_KEY, JSON.stringify(position)); } catch (_error) {} };
  const totalUnits = () => cart.reduce((sum, line) => sum + line.cantidad_unidades, 0);
  const bounds = () => ({ maxX: Math.max(SAFE(), innerWidth - fab.offsetWidth - SAFE()), maxY: Math.max(SAFE(), innerHeight - fab.offsetHeight - SAFE()) });
  const applyPosition = (animate = false) => {
    if (fab.hidden) return;
    const { maxX, maxY } = bounds();
    const x = position.edge === "left" ? SAFE() : maxX;
    const y = Math.max(SAFE(), Math.min(maxY, SAFE() + (maxY - SAFE()) * Math.max(0, Math.min(1, Number(position.yRatio) || 0))));
    fab.style.transition = animate ? "left .22s ease,top .22s ease,transform .16s" : "none";
    fab.style.left = `${x}px`; fab.style.top = `${y}px`;
    if (!animate) requestAnimationFrame(() => { fab.style.transition = ""; });
  };
  const close = () => {
    if (shell.hidden) return;
    shell.hidden = true; shell.setAttribute("aria-hidden", "true"); document.body.classList.remove("reseller-cart-open");
    lastFocus?.focus?.();
  };
  const renderFab = () => {
    const count = totalUnits();
    fab.hidden = count === 0;
    qs("[data-cart-badge]").textContent = count > 99 ? "99+" : String(count);
    fab.setAttribute("aria-label", `Abrir carrito, ${count} ${count === 1 ? "unidad" : "unidades"}`);
    if (!count) close(); else applyPosition();
  };
  const removeButtonHtml = () => `<button type="button" data-cart-remove><svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M4 7h16M9 7V4h6v3m3 0-1 13H7L6 7m4 4v5m4-5v5"></path></svg><span>Eliminar</span></button>`;
  const lineHtml = (line) => `<article class="reseller-cart-line" data-cart-plan="${line.plan_id}" data-cart-periods="${line.cantidad_periodos}"><header><div><span>${escapeHtml(line.producto)}</span><h3>${escapeHtml(line.plan)}</h3></div><em>${escapeHtml(line.tipo_unidad_etiqueta)}</em></header><p>Precio: ${money(line.precio_unitario)} / período<br>${money(line.precio_unitario)} × ${line.cantidad_unidades} × ${line.cantidad_periodos}</p><div class="reseller-cart-line-controls"><label>Unidades<span><button type="button" data-cart-change="units" data-delta="-1" aria-label="Restar unidad">−</button><b>${line.cantidad_unidades}</b><button type="button" data-cart-change="units" data-delta="1" aria-label="Sumar unidad" ${line.cantidad_unidades >= line.disponibilidad_unidades ? "disabled" : ""}>+</button></span></label><label>Períodos por unidad<span><button type="button" data-cart-change="periods" data-delta="-1" aria-label="Restar período">−</button><b>${line.cantidad_periodos}</b><button type="button" data-cart-change="periods" data-delta="1" aria-label="Sumar período" ${line.cantidad_periodos >= 12 ? "disabled" : ""}>+</button></span></label></div><footer><span>Subtotal<strong>${money(line.precio_total)}</strong></span>${removeButtonHtml()}</footer></article>`;
  const fallbackLineHtml = (line) => `<article class="reseller-cart-line is-unavailable" data-cart-plan="${line.plan_id}" data-cart-periods="${line.cantidad_periodos}"><header><div><span>Selección guardada</span><h3>Plan #${line.plan_id}</h3></div><em>Revalidación requerida</em></header><p>El precio y la disponibilidad no pudieron confirmarse. Reduce o elimina esta selección.</p><div class="reseller-cart-line-controls"><label>Unidades<span><button type="button" data-cart-change="units" data-delta="-1" aria-label="Restar unidad">−</button><b>${line.cantidad_unidades}</b><button type="button" disabled aria-label="Sumar unidad">+</button></span></label><label>Períodos por unidad<span><button type="button" data-cart-change="periods" data-delta="-1" aria-label="Restar período">−</button><b>${line.cantidad_periodos}</b><button type="button" disabled aria-label="Sumar período">+</button></span></label></div><footer>${removeButtonHtml()}</footer></article>`;
  const render = () => {
    renderFab();
    put("[data-cart-heading-count]", `${totalUnits()} unidades · ${cart.length} productos`);
    qs("[data-cart-lines]").innerHTML = preview?.lineas?.map(lineHtml).join("") || cart.map(fallbackLineHtml).join("");
    qs("[data-cart-summary]").hidden = !preview;
    if (!preview) return;
    put("[data-cart-heading-count]", `${preview.total_unidades} unidades · ${preview.total_productos} productos`);
    put("[data-cart-summary-count]", `${preview.total_unidades} unidades · ${preview.total_productos} productos`);
    put("[data-cart-summary-total]", preview.total_cop); put("[data-cart-balance]", preview.saldo_cop); put("[data-cart-after]", preview.saldo_estimado_cop);
    qs("[data-cart-recharge]").hidden = preview.saldo_suficiente;
    const buy = qs("[data-cart-submit]"); buy.disabled = true; buy.textContent = `Comprar todo · ${preview.total_cop}`;
    put("[data-cart-feedback]", preview.saldo_suficiente ? "Compra protegida: disponible en una fase posterior." : "Saldo insuficiente. Ajusta el carrito o recarga saldo.");
    window.lucide?.createIcons?.();
  };
  const validate = async () => {
    if (!cart.length) { preview = null; validating = false; put("[data-cart-status]", ""); render(); return; }
    validating = true; put("[data-cart-status]", "Revalidando precio, saldo e inventario actuales…");
    try {
      const response = await fetch("/revendedores/productos/carrito/preview", { method: "POST", headers: { "Content-Type": "application/json", "X-CSRF-Token": config.csrf_token }, body: JSON.stringify({ lineas: cart, cart_intent_id: intentId }) });
      const data = await response.json();
      if (!response.ok || !data.ok) throw new Error(data.mensaje || "No fue posible revalidar el carrito.");
      preview = data.preview; put("[data-cart-status]", "");
    } catch (error) { preview = null; put("[data-cart-status]", `${error.message} Ajusta o elimina la selección para continuar.`); }
    finally { validating = false; render(); }
  };
  const open = async () => {
    if (!cart.length) return;
    window.dispatchEvent(new CustomEvent("pechy:cart:opening"));
    lastFocus = document.activeElement; shell.hidden = false; shell.setAttribute("aria-hidden", "false"); document.body.classList.add("reseller-cart-open");
    dialog.focus(); if (!validating) await validate();
  };
  const add = (line, maxUnits = Infinity) => {
    const normalized = { plan_id: Number(line.plan_id), cantidad_unidades: Number(line.cantidad_unidades), cantidad_periodos: Number(line.cantidad_periodos) };
    const existing = cart.find((item) => item.plan_id === normalized.plan_id && item.cantidad_periodos === normalized.cantidad_periodos);
    if (existing) existing.cantidad_unidades = Math.min(maxUnits, existing.cantidad_unidades + normalized.cantidad_unidades); else { normalized.cantidad_unidades = Math.min(maxUnits, normalized.cantidad_unidades); cart.push(normalized); }
    preview = null; saveCart(); render(); validate();
  };
  const remove = (id, periods) => { cart = cart.filter((line) => !(line.plan_id === id && line.cantidad_periodos === periods)); preview = null; saveCart(); render(); if (cart.length) validate(); };
  const change = (node, field, delta) => {
    const id = Number(node.dataset.cartPlan), oldPeriods = Number(node.dataset.cartPeriods);
    const line = cart.find((item) => item.plan_id === id && item.cantidad_periodos === oldPeriods); if (!line) return;
    const key = field === "units" ? "cantidad_unidades" : "cantidad_periodos";
    const authoritative = preview?.lineas.find((item) => item.plan_id === id && item.cantidad_periodos === oldPeriods);
    const max = field === "units" ? authoritative?.disponibilidad_unidades || line[key] : 12;
    line[key] = Math.max(1, Math.min(max, line[key] + delta)); cart = normalizeCart(cart); saveCart(); preview = null; render(); validate();
  };

  let drag = null, suppressClick = false;
  fab.addEventListener("pointerdown", (event) => {
    if (event.button !== undefined && event.button !== 0) return;
    drag = { id: event.pointerId, startX: event.clientX, startY: event.clientY, left: fab.offsetLeft, top: fab.offsetTop, moved: false };
    fab.setPointerCapture(event.pointerId);
  });
  fab.addEventListener("pointermove", (event) => {
    if (!drag || event.pointerId !== drag.id) return;
    const dx = event.clientX - drag.startX, dy = event.clientY - drag.startY;
    if (!drag.moved && Math.hypot(dx, dy) < 7) return;
    drag.moved = true; fab.classList.add("is-dragging");
    const { maxX, maxY } = bounds(); fab.style.left = `${Math.max(SAFE(), Math.min(maxX, drag.left + dx))}px`; fab.style.top = `${Math.max(SAFE(), Math.min(maxY, drag.top + dy))}px`;
  });
  const endDrag = (event) => {
    if (!drag || event.pointerId !== drag.id) return;
    if (drag.moved) {
      suppressClick = true; fab.classList.remove("is-dragging");
      const { maxY } = bounds(); position = { edge: fab.offsetLeft + fab.offsetWidth / 2 < innerWidth / 2 ? "left" : "right", yRatio: (fab.offsetTop - SAFE()) / Math.max(1, maxY - SAFE()) };
      savePosition(); applyPosition(true); setTimeout(() => { suppressClick = false; }, 0);
    }
    drag = null;
  };
  fab.addEventListener("pointerup", endDrag); fab.addEventListener("pointercancel", endDrag);
  fab.addEventListener("click", (event) => { if (suppressClick) { event.preventDefault(); return; } open(); });
  shell.addEventListener("click", (event) => {
    if (event.target.closest("[data-cart-close]")) return close();
    const node = event.target.closest("[data-cart-plan]");
    if (event.target.closest("[data-cart-remove]") && node) return remove(Number(node.dataset.cartPlan), Number(node.dataset.cartPeriods));
    const control = event.target.closest("[data-cart-change]"); if (control && node) change(node, control.dataset.cartChange, Number(control.dataset.delta));
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !shell.hidden) close();
    if (event.key === "Tab" && !shell.hidden) { const focusable = [...shell.querySelectorAll("button:not([disabled]),a[href]")]; if (!focusable.length) return; const first = focusable[0], last = focusable[focusable.length - 1]; if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); } else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); } }
  });
  window.addEventListener("resize", () => applyPosition());
  window.addEventListener("storage", (event) => { if (event.key === CART_KEY) { cart = []; load(); preview = null; render(); } });
  window.PechyResellerCart = { add, open, close, validate, storageKey: CART_KEY, positionKey: POSITION_KEY };
  load(); renderFab(); if (cart.length) validate();
})();
