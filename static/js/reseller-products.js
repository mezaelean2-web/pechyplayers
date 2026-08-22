document.addEventListener("DOMContentLoaded", () => {
  "use strict";
  if (document.body.dataset.catalogContext !== "reseller") return;
  const qs = (selector, root = document) => root?.querySelector(selector);
  const money = (value) => value == null ? "Precio por configurar" : `$${Number(value).toLocaleString("es-CO")} COP`;
  const drawer = document.getElementById("resellerProductDrawer");
  const plans = document.getElementById("modalProductoPlanes");
  const legacyCta = document.getElementById("modalProductoComprar");
  const planStates = new WeakMap();

  const menuOpen = (open) => {
    drawer?.classList.toggle("is-open", open);
    drawer?.setAttribute("aria-hidden", String(!open));
    document.body.classList.toggle("reseller-drawer-open", open);
  };
  qs("[data-reseller-drawer-open]")?.addEventListener("click", () => menuOpen(true));
  drawer?.querySelectorAll("[data-reseller-drawer-close]").forEach((item) => item.addEventListener("click", () => menuOpen(false)));
  if (legacyCta) {
    legacyCta.removeAttribute("href"); legacyCta.disabled = true;
    legacyCta.setAttribute("aria-disabled", "true"); legacyCta.classList.add("reseller-buy-disabled");
    legacyCta.textContent = "Configura un plan arriba";
    new MutationObserver(() => legacyCta.removeAttribute("href")).observe(legacyCta, { attributes: true, attributeFilter: ["href"] });
  }

  const fetchPlan = async (id, units = 1, periods = 1) => {
    const query = new URLSearchParams({ cantidad_unidades: units, cantidad_periodos: periods });
    const response = await fetch(`/revendedores/productos/planes/${encodeURIComponent(id)}/compra?${query}`, { headers: { Accept: "application/json" } });
    const data = await response.json();
    if (!response.ok || !data.ok) throw new Error(data.mensaje || "No fue posible validar el plan.");
    return data.preview;
  };
  const configuratorHtml = () => `<div class="reseller-plan-config" data-plan-config>
    <p class="reseller-plan-config__status" data-plan-status>Validando precio e inventario actuales…</p>
    <div data-plan-content hidden><header><span data-plan-type></span><strong data-plan-unit-price></strong></header>
    <div class="reseller-plan-config__controls">
      <label>Unidades <span><button type="button" data-plan-step="units" data-delta="-1" aria-label="Restar unidad">−</button><b data-plan-units>1</b><button type="button" data-plan-step="units" data-delta="1" aria-label="Sumar unidad">+</button></span></label>
      <label>Períodos <span><button type="button" data-plan-step="periods" data-delta="-1" aria-label="Restar período">−</button><b data-plan-periods>1</b><button type="button" data-plan-step="periods" data-delta="1" aria-label="Sumar período">+</button></span></label>
    </div><div class="reseller-plan-config__total"><span>Duración <b data-plan-duration></b></span><span>Subtotal <strong data-plan-total></strong></span></div>
    <button class="reseller-plan-config__submit" type="button" data-plan-submit>Agregar al carrito</button>
    <p class="reseller-plan-config__feedback" data-plan-feedback aria-live="polite"></p></div></div>`;

  const renderConfig = (node) => {
    const state = planStates.get(node); if (!state?.preview) return;
    const config = qs("[data-plan-config]", node);
    qs("[data-plan-status]", config).hidden = true; qs("[data-plan-content]", config).hidden = false;
    qs("[data-plan-type]", config).textContent = state.preview.tipo_unidad_etiqueta;
    qs("[data-plan-unit-price]", config).textContent = `${money(state.preview.precio_unitario)} / período`;
    qs("[data-plan-units]", config).textContent = state.units; qs("[data-plan-periods]", config).textContent = state.periods;
    qs("[data-plan-duration]", config).textContent = `${state.preview.duracion_base_dias * state.periods} días`;
    qs("[data-plan-total]", config).textContent = money(state.preview.precio_unitario * state.units * state.periods);
    qs('[data-plan-step="units"][data-delta="-1"]', config).disabled = state.units <= 1;
    qs('[data-plan-step="units"][data-delta="1"]', config).disabled = state.units >= state.preview.disponibilidad_unidades;
    qs('[data-plan-step="periods"][data-delta="-1"]', config).disabled = state.periods <= 1;
    qs('[data-plan-step="periods"][data-delta="1"]', config).disabled = state.periods >= 12;
  };
  const openPlan = async (node) => {
    if (qs("[data-plan-config]", node)) return;
    node.insertAdjacentHTML("beforeend", configuratorHtml()); node.classList.add("is-configuring"); node.setAttribute("aria-expanded", "true");
    const state = { units: 1, periods: 1, preview: null }; planStates.set(node, state);
    if (node.dataset.resellerPriceReady !== "true") { node.classList.add("is-unavailable"); qs("[data-plan-status]", node).textContent = "Precio por configurar"; return; }
    node.classList.add("is-checking");
    try {
      state.preview = await fetchPlan(node.dataset.resellerPlanId);
      if (!state.preview.tarifa_configurada || state.preview.estado_disponibilidad !== "disponible") throw new Error(state.preview.disponibilidad);
      renderConfig(node);
    } catch (error) { node.classList.add("is-unavailable"); qs("[data-plan-status]", node).textContent = error.message; }
    finally { node.classList.remove("is-checking"); }
  };

  plans?.addEventListener("click", (event) => {
    const node = event.target.closest("[data-reseller-plan-id]"); if (!node) return;
    const state = planStates.get(node); const step = event.target.closest("[data-plan-step]");
    if (step && state?.preview) {
      event.stopPropagation(); const delta = Number(step.dataset.delta);
      if (step.dataset.planStep === "units") state.units = Math.max(1, Math.min(state.preview.disponibilidad_unidades, state.units + delta));
      else state.periods = Math.max(1, Math.min(12, state.periods + delta));
      qs("[data-plan-feedback]", node).textContent = ""; renderConfig(node); return;
    }
    if (event.target.closest("[data-plan-submit]") && state?.preview) {
      event.stopPropagation(); window.PechyResellerCart?.add({ plan_id: Number(node.dataset.resellerPlanId), cantidad_unidades: state.units, cantidad_periodos: state.periods }, state.preview.disponibilidad_unidades);
      node.classList.add("is-added"); qs("[data-plan-feedback]", node).textContent = "✓ Agregado. Puedes configurar otro plan.";
      setTimeout(() => node.classList.remove("is-added"), 650); return;
    }
    if (!event.target.closest("[data-plan-config]")) openPlan(node);
  });
  plans?.addEventListener("keydown", (event) => {
    if (!["Enter", " "].includes(event.key) || event.target.closest("button")) return;
    const node = event.target.closest("[data-reseller-plan-id]"); if (node) { event.preventDefault(); openPlan(node); }
  });
  window.addEventListener("pechy:cart:opening", () => menuOpen(false));
  document.addEventListener("keydown", (event) => { if (event.key === "Escape") menuOpen(false); });
});
