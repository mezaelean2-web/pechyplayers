document.addEventListener("DOMContentLoaded", function () {
  const page = document.querySelector(".resellers-page");
  if (!page) return;

  const csrf = page.dataset.csrfToken || "";
  const grid = document.getElementById("resellersGrid");
  const cards = Array.from(grid?.querySelectorAll(".reseller-card") || []);
  const search = document.getElementById("resellerSearch");
  const filters = Array.from(document.querySelectorAll("[data-reseller-filter]"));
  const count = document.getElementById("resellerCount");
  const empty = document.getElementById("resellersEmpty");
  const controlBackdrop = document.getElementById("resellerControlBackdrop");
  const controlModal = controlBackdrop?.querySelector(".reseller-control-modal");
  const controlContent = document.getElementById("resellerControlContent");
  const createBackdrop = document.getElementById("resellerCreateBackdrop");
  const createForm = document.getElementById("resellerCreateForm");
  let currentFilter = "";
  let currentReseller = null;
  let requestControl = null;
  let controlReturnFocus = null;
  let controlScrollPosition = null;

  function message(element, text, success) {
    if (!element) return;
    element.textContent = text;
    element.hidden = false;
    element.classList.toggle("is-success", Boolean(success));
  }

  async function api(url, options = {}) {
    const response = await fetch(url, {
      ...options,
      headers: {"Content-Type": "application/json", "X-CSRF-Token": csrf, ...(options.headers || {})}
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.mensaje || "No se pudo completar la operación.");
    return data;
  }

  function applyFilters() {
    const term = (search?.value || "").trim().toLocaleLowerCase("es");
    let visible = 0;
    cards.forEach(function (card) {
      const show = (!currentFilter || card.dataset.status === currentFilter) && (card.dataset.search || "").includes(term);
      card.hidden = !show;
      if (show) visible += 1;
    });
    if (count) count.textContent = `${visible} ${visible === 1 ? "revendedor" : "revendedores"}`;
    if (empty) empty.hidden = visible !== 0;
  }

  search?.addEventListener("input", applyFilters);
  filters.forEach(function (button) {
    button.addEventListener("click", function () {
      filters.forEach(item => item.classList.remove("is-active"));
      button.classList.add("is-active");
      currentFilter = button.dataset.resellerFilter || "";
      applyFilters();
    });
  });

  function closeControl() {
    requestControl?.abort();
    if (controlBackdrop) controlBackdrop.hidden = true;
    document.body.classList.remove("reseller-modal-open");
    if (controlScrollPosition) window.scrollTo(controlScrollPosition.x, controlScrollPosition.y);
    controlReturnFocus?.focus({preventScroll: true});
    controlReturnFocus = null;
    controlScrollPosition = null;
  }

  async function openControl(id) {
    if (!controlBackdrop || !controlContent) return;
    requestControl?.abort();
    requestControl = new AbortController();
    currentReseller = id;
    if (controlBackdrop.hidden) {
      controlReturnFocus = document.activeElement;
      controlScrollPosition = {x: window.scrollX, y: window.scrollY};
    }
    controlBackdrop.hidden = false;
    document.body.classList.add("reseller-modal-open");
    controlContent.innerHTML = '<div class="resellers-empty"><strong>Cargando Centro de Control…</strong></div>';
    try {
      const response = await fetch(`/admin/revendedores/${id}/control`, {signal: requestControl.signal});
      if (!response.ok) throw new Error(response.status === 404 ? "Revendedor no encontrado." : "No se pudo cargar el Centro de Control.");
      controlContent.innerHTML = await response.text();
      bindControl();
      window.lucide?.createIcons();
      controlModal?.focus({preventScroll: true});
    } catch (error) {
      if (error.name !== "AbortError") controlContent.innerHTML = `<div class="resellers-empty"><strong>${error.message}</strong></div>`;
    }
  }

  cards.forEach(function (card) {
    const open = () => openControl(card.dataset.resellerId);
    card.addEventListener("click", open);
    card.addEventListener("keydown", event => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); open(); } });
  });
  controlBackdrop?.addEventListener("click", event => { if (event.target === controlBackdrop || event.target.closest("[data-reseller-close]")) closeControl(); });

  function updateResellerCard(id, reseller) {
    const card = cards.find(item => item.dataset.resellerId === String(id));
    if (!card || !reseller) return;
    const name = reseller.nombre || "";
    const words = name.trim().split(/\s+/).filter(Boolean);
    const copy = card.querySelector(".reseller-card-copy");
    card.querySelector(".reseller-avatar").textContent = words.slice(0, 2).map(word => word[0].toLocaleUpperCase("es")).join("");
    copy.querySelector("h2").textContent = name;
    copy.querySelector("p").textContent = reseller.negocio || "Revendedor independiente";
    const details = copy.querySelectorAll("small");
    details[0].textContent = reseller.correo;
    details[1].textContent = reseller.telefono || "Sin teléfono registrado";
    card.dataset.search = [name, reseller.negocio, reseller.correo, reseller.telefono].filter(Boolean).join(" ").toLocaleLowerCase("es");
    applyFilters();
  }

  function bindControl() {
    const root = controlContent.querySelector(".reseller-control");
    if (!root) return;
    const id = root.dataset.resellerId;
    const tabs = Array.from(root.querySelectorAll("[data-reseller-tab]"));
    tabs.forEach(function (tab) {
      tab.addEventListener("click", function () {
        tabs.forEach(item => item.classList.toggle("is-active", item === tab));
        root.querySelectorAll("[data-reseller-panel]").forEach(panel => { panel.hidden = panel.dataset.resellerPanel !== tab.dataset.resellerTab; });
      });
    });

    const general = root.querySelector("[data-reseller-general]");
    general?.addEventListener("submit", async function (event) {
      event.preventDefault();
      const output = general.querySelector(".reseller-form-message");
      const form = new FormData(general);
      try {
        const data = await api(`/admin/revendedores/${id}`, {method: "PATCH", body: JSON.stringify(Object.fromEntries(form))});
        updateResellerCard(id, data.revendedor);
        window.setTimeout(closeControl, 450);
        message(output, "Información actualizada.", true);
      } catch (error) { message(output, error.message, false); }
    });

    const priceSearch = root.querySelector("[data-reseller-price-search]");
    const priceCards = Array.from(root.querySelectorAll(".reseller-price-card"));
    const priceSearchEmpty = root.querySelector("[data-reseller-price-search-empty]");
    priceSearch?.addEventListener("input", function () {
      const terms = priceSearch.value.toLocaleLowerCase("es").trim().split(/\s+/).filter(Boolean);
      let visible = 0;
      priceCards.forEach(function (card) {
        const haystack = (card.dataset.priceSearch || "").replace(/\s+/g, " ");
        const show = terms.every(term => haystack.includes(term));
        card.hidden = !show;
        if (show) visible += 1;
      });
      if (priceSearchEmpty) priceSearchEmpty.hidden = visible !== 0 || priceCards.length === 0;
    });

    root.querySelector("[data-reseller-state]")?.addEventListener("click", async function (event) {
      const button = event.currentTarget;
      try {
        await api(`/admin/revendedores/${id}/estado`, {method: "POST", body: JSON.stringify({estado: button.dataset.resellerState})});
        window.location.reload();
      } catch (error) { window.alert(error.message); }
    });

    const password = root.querySelector("[data-reseller-password]");
    password?.addEventListener("submit", async function (event) {
      event.preventDefault();
      const output = password.querySelector(".reseller-form-message");
      try {
        await api(`/admin/revendedores/${id}/password`, {method: "POST", body: JSON.stringify({password: new FormData(password).get("password")})});
        password.reset();
        message(output, "Contraseña restablecida de forma segura.", true);
      } catch (error) { message(output, error.message, false); }
    });

    root.querySelectorAll(".reseller-price-card").forEach(function (card) {
      const planId = card.dataset.planId;
      const output = card.querySelector(".reseller-form-message");
      card.querySelector("[data-save-general]")?.addEventListener("click", async function () {
        try {
          await api(`/admin/revendedores/precios/generales/${planId}`, {method: "PUT", body: JSON.stringify({precio: card.querySelector('[name="precio_general"]').value.replace(/\D/g, "")})});
          message(output, "Precio reseller general guardado.", true);
        } catch (error) { message(output, error.message, false); }
      });
      card.querySelector("[data-save-custom]")?.addEventListener("click", async function () {
        try {
          await api(`/admin/revendedores/${id}/precios/${planId}`, {method: "PUT", body: JSON.stringify({
            precio: card.querySelector('[name="precio_personalizado"]').value.replace(/\D/g, ""),
            oferta_activa: card.querySelector('[name="oferta_activa"]').checked,
            oferta_precio: card.querySelector('[name="oferta_precio"]').value.replace(/\D/g, ""),
            oferta_inicio: card.querySelector('[name="oferta_inicio"]').value,
            oferta_fin: card.querySelector('[name="oferta_fin"]').value
          })});
          await openControl(id);
        } catch (error) { message(output, error.message, false); }
      });
      card.querySelector("[data-reset-custom]")?.addEventListener("click", async function () {
        try { await api(`/admin/revendedores/${id}/precios/${planId}`, {method: "DELETE"}); await openControl(id); }
        catch (error) { message(output, error.message, false); }
      });
    });
  }

  function closeCreate() { if (createBackdrop) createBackdrop.hidden = true; document.body.classList.remove("reseller-modal-open"); }
  document.getElementById("resellerCreateOpen")?.addEventListener("click", function () { if (createBackdrop) createBackdrop.hidden = false; document.body.classList.add("reseller-modal-open"); });
  createBackdrop?.addEventListener("click", event => { if (event.target === createBackdrop || event.target.closest("[data-reseller-create-close]")) closeCreate(); });
  createForm?.addEventListener("submit", async function (event) {
    event.preventDefault();
    const output = createForm.querySelector(".reseller-form-message");
    try {
      await api("/admin/revendedores", {method: "POST", body: JSON.stringify(Object.fromEntries(new FormData(createForm)))});
      window.location.reload();
    } catch (error) { message(output, error.message, false); }
  });
  document.addEventListener("keydown", event => { if (event.key === "Escape") { closeControl(); closeCreate(); } });
});
