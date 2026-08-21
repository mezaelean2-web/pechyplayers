document.addEventListener("DOMContentLoaded", function () {
  const page = document.querySelector(".wallet-page");
  if (!page) return;
  const csrf = page.dataset.csrfToken || "";
  const cards = Array.from(page.querySelectorAll(".wallet-card"));
  const search = document.getElementById("walletSearch");
  const filters = Array.from(page.querySelectorAll("[data-wallet-filter]"));
  const empty = document.getElementById("walletEmpty");
  const count = document.getElementById("walletCount");
  const backdrop = document.getElementById("walletBackdrop");
  const modal = backdrop?.querySelector(".wallet-modal");
  const content = document.getElementById("walletControl");
  let filter = "all";
  let request = null;
  let returnFocus = null;
  let scrollPosition = null;

  const cop = value => `$${Number(value || 0).toLocaleString("es-CO")} COP`;
  function applyFilters() {
    const term = (search?.value || "").trim().toLocaleLowerCase("es");
    let visible = 0;
    cards.forEach(card => {
      const balance = Number(card.dataset.balance || 0);
      const matchesFilter = filter === "all" || (filter === "with" && balance > 0) || (filter === "without" && balance === 0) || card.dataset.status === filter;
      const show = matchesFilter && (card.dataset.search || "").includes(term);
      card.hidden = !show;
      if (show) visible += 1;
    });
    if (count) count.textContent = `${visible} ${visible === 1 ? "revendedor" : "revendedores"}`;
    if (empty) empty.hidden = visible !== 0;
  }
  search?.addEventListener("input", applyFilters);
  filters.forEach(button => button.addEventListener("click", () => {
    filters.forEach(item => item.classList.toggle("is-active", item === button));
    filter = button.dataset.walletFilter;
    applyFilters();
  }));

  function closeControl() {
    request?.abort();
    if (backdrop) backdrop.hidden = true;
    document.body.classList.remove("wallet-modal-open");
    if (scrollPosition) window.scrollTo(scrollPosition.x, scrollPosition.y);
    returnFocus?.focus({preventScroll: true});
    returnFocus = null;
    scrollPosition = null;
  }
  async function openControl(id) {
    if (!backdrop || !content) return;
    request?.abort();
    request = new AbortController();
    if (backdrop.hidden) { returnFocus = document.activeElement; scrollPosition = {x: window.scrollX, y: window.scrollY}; }
    backdrop.hidden = false;
    document.body.classList.add("wallet-modal-open");
    content.innerHTML = '<div class="wallet-loading">Cargando Centro de Control…</div>';
    try {
      const response = await fetch(`/admin/saldos/${id}/control`, {signal: request.signal});
      if (!response.ok) throw new Error(response.status === 404 ? "Revendedor no encontrado." : "No se pudo cargar el saldo.");
      content.innerHTML = await response.text();
      bindControl();
      window.lucide?.createIcons();
      modal?.focus({preventScroll: true});
    } catch (error) { if (error.name !== "AbortError") content.innerHTML = `<div class="wallet-loading">${error.message}</div>`; }
  }
  cards.forEach(card => {
    const open = () => openControl(card.dataset.resellerId);
    card.addEventListener("click", open);
    card.addEventListener("keydown", event => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); open(); } });
  });
  backdrop?.addEventListener("click", event => { if (event.target === backdrop || event.target.closest("[data-wallet-close]")) closeControl(); });
  document.addEventListener("keydown", event => { if (event.key === "Escape" && !backdrop?.hidden) closeControl(); });

  async function api(url, body) {
    const response = await fetch(url, {method: "POST", headers: {"Content-Type": "application/json", "X-CSRF-Token": csrf}, body: JSON.stringify(body)});
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.mensaje || "No se pudo completar la operación.");
    return data;
  }
  function updateDashboard(id, movement) {
    const card = cards.find(item => item.dataset.resellerId === String(id));
    const oldBalance = Number(card?.dataset.balance || 0);
    if (card) {
      card.dataset.balance = movement.saldo_posterior;
      card.querySelector("[data-card-balance]").textContent = cop(movement.saldo_posterior);
      card.querySelector("[data-card-updated]").textContent = "Actualizado ahora";
    }
    const total = page.querySelector('[data-wallet-stat="total"]');
    const countStat = page.querySelector('[data-wallet-stat="count"]');
    const kind = movement.tipo === "manual_credit" ? "credits" : "debits";
    const today = page.querySelector(`[data-wallet-stat="${kind}"]`);
    total.dataset.value = Number(total.dataset.value) + movement.saldo_posterior - oldBalance;
    total.textContent = cop(total.dataset.value);
    if (oldBalance === 0 && movement.saldo_posterior > 0) { countStat.dataset.value = Number(countStat.dataset.value) + 1; countStat.textContent = countStat.dataset.value; }
    if (oldBalance > 0 && movement.saldo_posterior === 0) { countStat.dataset.value = Number(countStat.dataset.value) - 1; countStat.textContent = countStat.dataset.value; }
    today.dataset.value = Number(today.dataset.value) + movement.monto;
    today.textContent = cop(today.dataset.value);
    applyFilters();
  }
  function bindControl() {
    const root = content.querySelector(".wallet-control");
    if (!root) return;
    const id = root.dataset.resellerId;
    const name = root.dataset.resellerName;
    const confirmation = root.querySelector("[data-wallet-confirm]");
    const confirmButton = root.querySelector("[data-wallet-confirm-submit]");
    const confirmMessage = root.querySelector("[data-wallet-confirm-message]");
    let pending = null;
    root.querySelectorAll("[data-wallet-action]").forEach(form => form.addEventListener("submit", event => {
      event.preventDefault();
      const data = new FormData(form);
      const amount = String(data.get("monto") || "").trim();
      const reason = String(data.get("motivo") || "").trim();
      const action = form.dataset.walletAction;
      const message = form.querySelector(".wallet-message");
      if (!/^\d+$/.test(amount) || Number(amount) <= 0 || !reason) { message.textContent = "Ingresa un monto entero mayor que cero y un motivo."; message.hidden = false; return; }
      message.hidden = true;
      pending = {action, amount, reason};
      root.querySelector("[data-wallet-confirm-copy]").textContent = `${action === "credito" ? "Agregar" : "Descontar"} ${cop(amount)} ${action === "credito" ? "al saldo de" : "del saldo de"} ${name}`;
      root.querySelector("[data-wallet-confirm-reason]").textContent = reason;
      confirmation.hidden = false;
      confirmButton.focus();
    }));
    root.querySelector("[data-wallet-confirm-cancel]")?.addEventListener("click", () => { pending = null; confirmation.hidden = true; });
    confirmButton?.addEventListener("click", async () => {
      if (!pending || confirmButton.disabled) return;
      confirmButton.disabled = true;
      confirmMessage.hidden = true;
      try {
        const data = await api(`/admin/saldos/${id}/${pending.action}`, {monto: pending.amount, motivo: pending.reason});
        updateDashboard(id, data.movimiento);
        await openControl(id);
      } catch (error) { confirmMessage.textContent = error.message; confirmMessage.hidden = false; confirmButton.disabled = false; }
    });
  }
});
