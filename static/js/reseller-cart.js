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
  let cart = [], preview = null, validating = false, purchasing = false, delivery = null, deliveryFormat = "detailed", deliveryRequest = 0, lastFocus = null;
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
    if (dialog.classList.contains("is-purchase-success")) { deliveryRequest += 1; delivery = null; deliveryFormat = "detailed"; qs("[data-cart-body]").replaceChildren(); dialog.classList.remove("is-purchase-success"); }
    lastFocus?.focus?.();
  };
  const renderFab = () => {
    const count = totalUnits();
    fab.hidden = count === 0;
    qs("[data-cart-badge]").textContent = count > 99 ? "99+" : String(count);
    fab.setAttribute("aria-label", `Abrir carrito, ${count} ${count === 1 ? "unidad" : "unidades"}`);
    if (!count) close(); else applyPosition();
  };
  const removeButtonHtml = () => `<button type="button" data-cart-remove aria-label="Eliminar producto"><svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M4 7h16M9 7V4h6v3m3 0-1 13H7L6 7m4 4v5m4-5v5"></path></svg><span>Eliminar</span></button>`;
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
    const buy = qs("[data-cart-submit]"); buy.disabled = purchasing || !preview.puede_prepararse; buy.textContent = purchasing ? "Procesando compra…" : `Comprar todo · ${preview.total_cop}`;
    put("[data-cart-feedback]", preview.saldo_suficiente ? "Precio, saldo e inventario se confirmarán al comprar." : "Saldo insuficiente. Ajusta el carrito o recarga saldo.");
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

  const fieldHtml = (field, unitIndex, fieldIndex) => `<div class="reseller-delivery-field"><span>${escapeHtml(field.etiqueta)}</span><div><strong data-delivery-value class="${field.sensible ? "is-secret" : ""}">${field.sensible ? "••••••••" : escapeHtml(field.valor)}</strong>${field.sensible ? `<button type="button" data-delivery-toggle data-unit="${unitIndex}" data-field="${fieldIndex}" aria-label="Mostrar ${escapeHtml(field.etiqueta)}"><i data-lucide="eye"></i></button>` : ""}<button type="button" data-delivery-copy-field data-unit="${unitIndex}" data-field="${fieldIndex}" aria-label="Copiar ${escapeHtml(field.etiqueta)}"><i data-lucide="copy"></i><span>Copiar</span></button></div></div>`;
  const unitHtml = (unit, unitIndex) => `<article class="reseller-delivery-card" data-delivery-unit="${unitIndex}"><header><span>#${unit.numero}</span><div><strong>${escapeHtml(unit.producto)}${unit.plan ? ` · ${escapeHtml(unit.plan)}` : ""}</strong><em class="is-${unit.modalidad}">${escapeHtml(unit.modalidad_etiqueta)}</em></div></header><div class="reseller-delivery-fields">${unit.campos.map((field, fieldIndex) => fieldHtml(field, unitIndex, fieldIndex)).join("")}</div><button type="button" class="reseller-delivery-copy-unit" data-delivery-copy-unit="${unitIndex}"><i data-lucide="copy-check"></i><span>COPIAR TODO</span></button>${unit.modalidad === "perfil" ? `<aside class="reseller-delivery-device-warning"><div><i data-lucide="triangle-alert"></i><span>1 DISPOSITIVO</span></div><strong>IMPORTANTE — USO EN UN SOLO DISPOSITIVO</strong><p>Este perfil debe utilizarse únicamente en 1 dispositivo. Iniciar sesión o utilizarlo simultáneamente en varios dispositivos puede provocar el bloqueo de la cuenta. Evita compartir el acceso entre varios equipos.</p></aside>` : ""}</article>`;
  const normalizedWords = (value) => String(value || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toUpperCase().replace(/[^A-Z0-9]+/g, " ").trim();
  const modalityAlreadyNamed = (name, modality) => modality === "perfil"
    ? /\bPERFIL(?:ES)?\b/.test(normalizedWords(name))
    : /\bCUENTA(?:S)? COMPLETA(?:S)?\b/.test(normalizedWords(name));
  const deliveryTitle = (product, plan, modality, label, separator = " — ") => {
    const base = `${product}${plan ? ` · ${plan}` : ""}`;
    return modalityAlreadyNamed(base, modality) ? base : `${base}${separator}${label}`;
  };
  const profileWarning = "IMPORTANTE:\nEste perfil debe utilizarse únicamente en 1 dispositivo.\nIniciar sesión o utilizarlo en varios dispositivos puede provocar el bloqueo de la cuenta.";
  const formatUnit = (unit, numbered = false) => `${numbered ? `#${unit.numero}\n` : ""}${deliveryTitle(unit.producto, unit.plan, unit.modalidad, unit.modalidad_etiqueta).toUpperCase()}\n\n${unit.campos.map((field) => `${field.etiqueta}: ${field.valor}`).join("\n")}${unit.modalidad === "perfil" ? `\n\n${profileWarning}` : ""}`;
  const fieldValue = (unit, key) => unit.campos.find((field) => field.clave === key)?.valor;
  const deliveryGroups = () => {
    const groups = new Map();
    for (const unit of delivery?.unidades || []) {
      const key = `${unit.producto}\u0000${unit.plan || ""}\u0000${unit.modalidad}`;
      if (!groups.has(key)) groups.set(key, { producto: unit.producto, plan: unit.plan, modalidad: unit.modalidad, modalidadEtiqueta: unit.modalidad_etiqueta, unidades: [] });
      groups.get(key).unidades.push(unit);
    }
    return [...groups.values()];
  };
  const massiveRowHtml = (unit, index, modality) => {
    const values = [fieldValue(unit, "correo"), fieldValue(unit, "contrasena")];
    if (modality === "perfil") values.push(fieldValue(unit, "perfil"), fieldValue(unit, "pin") ? `PIN ${fieldValue(unit, "pin")}` : null);
    return `<div class="reseller-delivery-massive__row"><b>${String(index + 1).padStart(2, "0")}</b>${values.filter((value) => value != null && value !== "").map((value) => `<span>${escapeHtml(value)}</span>`).join("")}</div>`;
  };
  const massiveGroupHtml = (group) => `<section class="reseller-delivery-massive__group"><header><div><strong>${escapeHtml(deliveryTitle(group.producto, group.plan, group.modalidad, group.modalidadEtiqueta, " — "))}</strong><span>${group.unidades.length} ${group.unidades.length === 1 ? "UNIDAD" : "UNIDADES"}</span></div></header><div class="reseller-delivery-massive__rows">${group.unidades.map((unit, index) => massiveRowHtml(unit, index, group.modalidad)).join("")}</div></section>`;
  const recommendationsHtml = (groups) => {
    const hasAccounts = groups.some((group) => group.modalidad === "cuenta"), hasProfiles = groups.some((group) => group.modalidad === "perfil");
    return `<footer class="reseller-delivery-massive__message"><strong>Gracias por tu compra.</strong><span>IMPORTANTE:</span>${hasAccounts ? "<p>Recomendamos utilizar cada cuenta de manera responsable y evitar cambios innecesarios en los datos de acceso para mantener la estabilidad del servicio.</p>" : ""}${hasProfiles ? "<p>Los perfiles deben utilizarse únicamente en 1 dispositivo.<br>El uso simultáneo en varios dispositivos puede provocar el bloqueo de la cuenta.</p>" : ""}</footer>`;
  };
  const formatMassiveDelivery = () => {
    const groups = deliveryGroups(), sections = groups.map((group) => {
      const title = deliveryTitle(group.producto, group.plan, group.modalidad, group.modalidad === "cuenta" ? "CUENTAS COMPLETAS" : group.modalidadEtiqueta).toUpperCase();
      const rows = group.unidades.map((unit, index) => {
        const values = [fieldValue(unit, "correo"), fieldValue(unit, "contrasena")];
        if (group.modalidad === "perfil") values.push(fieldValue(unit, "perfil"), fieldValue(unit, "pin") ? `PIN ${fieldValue(unit, "pin")}` : null);
        return `${String(index + 1).padStart(2, "0")}. ${values.filter((value) => value != null && value !== "").join(" | ")}`;
      });
      return `${title}\n\n${rows.join("\n")}`;
    });
    const hasAccounts = groups.some((group) => group.modalidad === "cuenta"), hasProfiles = groups.some((group) => group.modalidad === "perfil");
    const notes = [hasAccounts ? "Recomendamos utilizar cada cuenta de manera responsable y evitar cambios innecesarios en los datos de acceso para mantener la estabilidad del servicio." : null, hasProfiles ? "Los perfiles deben utilizarse únicamente en 1 dispositivo.\nEl uso simultáneo en varios dispositivos puede provocar el bloqueo de la cuenta." : null].filter(Boolean);
    return `${sections.join("\n\n\n")}\n\n\nGracias por tu compra.\n\nIMPORTANTE:\n${notes.join("\n")}`;
  };
  const copyText = async (value, button, success) => {
    try {
      await navigator.clipboard.writeText(value);
    } catch (_error) {
      const area = document.createElement("textarea"); area.value = value; area.setAttribute("readonly", ""); area.style.position = "fixed"; area.style.opacity = "0"; document.body.appendChild(area); area.select(); document.execCommand("copy"); area.remove();
    }
    const label = button.querySelector("span"); const previous = label?.textContent;
    button.classList.add("is-copied"); if (label) label.textContent = success;
    setTimeout(() => { button.classList.remove("is-copied"); if (label && button.isConnected) label.textContent = previous; }, 1600);
  };
  const renderDelivery = () => {
    const container = qs("[data-delivery-list]"); if (!container || !delivery) return;
    const groups = deliveryGroups();
    container.classList.toggle("is-massive", deliveryFormat === "massive");
    container.innerHTML = delivery.unidades.length ? (deliveryFormat === "massive" ? `<div class="reseller-delivery-massive">${groups.map(massiveGroupHtml).join("")}${recommendationsHtml(groups)}</div>` : delivery.unidades.map(unitHtml).join("")) : `<div class="reseller-delivery-unavailable"><strong>Entrega no disponible</strong><p>No fue posible validar las credenciales asignadas. Consúltalas desde Mis cuentas.</p></div>`;
    put("[data-delivery-count]", `${delivery.unidades.length} ${delivery.unidades.length === 1 ? "acceso disponible" : "accesos disponibles"}`);
    const detailedCopy = qs("[data-delivery-copy-all]"); if (detailedCopy) detailedCopy.hidden = deliveryFormat !== "detailed" || delivery.unidades.length < 2;
    const massiveCopy = qs("[data-delivery-copy-massive]"); if (massiveCopy) massiveCopy.hidden = deliveryFormat !== "massive" || !delivery.unidades.length;
    root.querySelectorAll("[data-delivery-format]").forEach((button) => { const active = button.dataset.deliveryFormat === deliveryFormat; button.classList.toggle("is-active", active); button.setAttribute("aria-selected", String(active)); });
    window.lucide?.createIcons?.();
  };
  const showSuccess = async (order) => {
    const requestId = ++deliveryRequest;
    dialog.classList.add("is-purchase-success");
    deliveryFormat = "detailed";
    qs("[data-cart-body]").innerHTML = `<section class="reseller-purchase-success"><header class="reseller-purchase-success__hero"><button type="button" class="reseller-purchase-success__close" data-cart-close aria-label="Cerrar entrega">×</button><span class="reseller-purchase-success__check"><i data-lucide="check"></i></span><small>COMPRA COMPLETADA</small><h2>Tu pedido fue procesado correctamente.</h2><strong>${escapeHtml(order.identificador_pedido)}</strong><dl><div><dt>Unidades</dt><dd>${order.cantidad_unidades}</dd></div><div><dt>Total pagado</dt><dd>${escapeHtml(order.total_pagado_cop)}</dd></div><div><dt>Saldo restante</dt><dd>${escapeHtml(order.saldo_restante_cop)}</dd></div></dl></header><section class="reseller-delivery"><div class="reseller-delivery-format"><small>FORMATO DE ENTREGA</small><div role="tablist" aria-label="Formato de entrega"><button type="button" class="is-active" data-delivery-format="detailed" role="tab" aria-selected="true"><i data-lucide="layout-grid"></i><span>DETALLADO</span></button><button type="button" data-delivery-format="massive" role="tab" aria-selected="false"><i data-lucide="list"></i><span>MASIVO</span></button></div></div><header><div><small>CUENTAS ENTREGADAS</small><strong data-delivery-count>Preparando entrega segura…</strong></div><button type="button" data-delivery-copy-all hidden><i data-lucide="copy-check"></i><span>COPIAR TODAS</span></button><button type="button" data-delivery-copy-massive hidden><i data-lucide="copy-check"></i><span>COPIAR LISTADO COMPLETO</span></button></header><div class="reseller-delivery-list" data-delivery-list><div class="reseller-delivery-loading"><span></span><p>Validando las unidades asignadas…</p></div></div></section><footer class="reseller-purchase-success__actions"><a href="/revendedores/mis-cuentas">VER MIS CUENTAS</a><button type="button" data-cart-continue>SEGUIR COMPRANDO</button></footer></section>`;
    qs("[data-cart-summary]").hidden = true; window.lucide?.createIcons?.();
    try {
      const response = await fetch(`/revendedores/pedidos/${encodeURIComponent(order.order_id)}/entrega`, { headers: { "Accept": "application/json" } });
      const data = await response.json();
      if (!response.ok || !data.ok) throw new Error(data.mensaje || "No fue posible cargar la entrega.");
      if (requestId !== deliveryRequest) return;
      delivery = data; renderDelivery();
    } catch (error) {
      if (requestId !== deliveryRequest) return;
      delivery = null; const list = qs("[data-delivery-list]"); if (list) list.innerHTML = `<div class="reseller-delivery-unavailable"><strong>Compra confirmada</strong><p>${escapeHtml(error.message)} Puedes consultar tus accesos en Mis cuentas.</p></div>`;
      put("[data-delivery-count]", "Entrega segura no disponible");
    }
  };
  const purchase = async () => {
    if (purchasing || !preview?.puede_prepararse || !cart.length) return;
    purchasing = true; render(); put("[data-cart-status]", "Procesando compra…");
    try {
      const response = await fetch("/revendedores/productos/carrito/comprar", { method: "POST", headers: { "Content-Type": "application/json", "X-CSRF-Token": config.csrf_token }, body: JSON.stringify({ items: cart, cart_intent_id: intentId, preview_token: preview.preview_token }) });
      const data = await response.json();
      if (!response.ok || !data.ok) {
        const error = new Error(data.mensaje || "No fue posible completar el pedido."); error.code = data.codigo; error.data = data; throw error;
      }
      cart = []; preview = null; saveCart(); fab.hidden = true; await showSuccess(data.pedido);
    } catch (error) {
      const suffix = error.code === "saldo_insuficiente" ? " Puedes ir a Billetera para recargar." : error.code === "inventario_agotado" ? " Revalida el carrito e inténtalo nuevamente." : " Tu carrito sigue intacto.";
      if (error.code === "price_changed") {
        preview = null;
        qs("[data-price-changed]")?.remove();
        qs("[data-cart-lines]").insertAdjacentHTML("beforebegin", `<div class="reseller-cart-status" data-price-changed><strong>El precio de tu pedido cambi&oacute;</strong><p>Revisamos nuevamente las tarifas antes de cobrarte.</p><p>Antes: ${escapeHtml(error.data.total_anterior_cop)}<br>Ahora: ${escapeHtml(error.data.total_actual_cop)}</p><p>Ning&uacute;n cobro fue realizado.</p><button type="button" data-review-new-total>REVISAR NUEVO TOTAL</button></div>`);
        put("[data-cart-status]", "");
        return;
      }
      if (error.code === "cart_changed") {
        preview = null;
        qs("[data-price-changed]")?.remove();
        qs("[data-cart-lines]").insertAdjacentHTML("beforebegin", `<div class="reseller-cart-status" data-price-changed><strong>Las condiciones de tu pedido cambiaron</strong><p>Revalida el carrito para revisar el detalle actualizado.</p><p>Ning&uacute;n cobro fue realizado.</p><button type="button" data-review-new-total>REVISAR CARRITO</button></div>`);
        put("[data-cart-status]", "");
        return;
      }
      await validate();
      put("[data-cart-status]", `${error.message}${suffix}`);
    } finally { purchasing = false; if (cart.length) render(); }
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
    if (event.target.closest("[data-cart-submit]")) purchase();
    const format = event.target.closest("[data-delivery-format]");
    if (format && delivery) { deliveryFormat = format.dataset.deliveryFormat; renderDelivery(); }
    const toggle = event.target.closest("[data-delivery-toggle]");
    if (toggle && delivery) {
      const unit = delivery.unidades[Number(toggle.dataset.unit)], field = unit?.campos[Number(toggle.dataset.field)], value = toggle.closest(".reseller-delivery-field")?.querySelector("[data-delivery-value]");
      if (field && value) { const hidden = value.classList.toggle("is-secret"); value.textContent = hidden ? "••••••••" : field.valor; toggle.innerHTML = `<i data-lucide="${hidden ? "eye" : "eye-off"}"></i>`; toggle.setAttribute("aria-label", `${hidden ? "Mostrar" : "Ocultar"} ${field.etiqueta}`); window.lucide?.createIcons?.(); }
    }
    const copyField = event.target.closest("[data-delivery-copy-field]");
    if (copyField && delivery) { const field = delivery.unidades[Number(copyField.dataset.unit)]?.campos[Number(copyField.dataset.field)]; if (field) copyText(field.valor, copyField, "✓ COPIADO"); }
    const copyUnit = event.target.closest("[data-delivery-copy-unit]");
    if (copyUnit && delivery) { const unit = delivery.unidades[Number(copyUnit.dataset.deliveryCopyUnit)]; if (unit) copyText(formatUnit(unit), copyUnit, "✓ Datos copiados"); }
    const copyAll = event.target.closest("[data-delivery-copy-all]");
    if (copyAll && delivery) copyText(delivery.unidades.map((unit) => formatUnit(unit, true)).join("\n\n──────────\n\n"), copyAll, "✓ Todas las cuentas copiadas");
    const copyMassive = event.target.closest("[data-delivery-copy-massive]");
    if (copyMassive && delivery) copyText(formatMassiveDelivery(), copyMassive, "✓ LISTADO COPIADO");
    if (event.target.closest("[data-cart-continue]")) { delivery = null; deliveryFormat = "detailed"; window.location.href = "/revendedores/productos"; }
    if (event.target.closest("[data-review-new-total]")) {
      qs("[data-price-changed]")?.remove();
      intentId = window.crypto?.randomUUID?.() || `cart-${Date.now()}`;
      saveCart(); validate();
    }
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
