(() => {
  "use strict";
  const root = document.querySelector("[data-customer-order-lookup]");
  if (!root) return;
  const openButton = root.querySelector("[data-customer-order-lookup-open]");
  const modal = root.querySelector("[data-customer-order-lookup-modal]");
  const dialog = modal.querySelector('[role="dialog"]');
  const closeButtons = modal.querySelectorAll("[data-customer-order-lookup-close]");
  const form = root.querySelector("[data-customer-order-lookup-form]");
  const input = form.querySelector('[name="public_order_id"]');
  const button = form.querySelector('button[type="submit"]');
  const result = root.querySelector("[data-customer-order-lookup-result]");
  const orderId = root.querySelector("[data-customer-order-lookup-id]");
  const state = root.querySelector("[data-customer-order-lookup-state]");
  const message = root.querySelector("[data-customer-order-lookup-message]");
  const deliveryLink = root.querySelector("[data-customer-order-delivery-link]");
  let previousFocus = null;

  const openModal = () => {
    previousFocus = document.activeElement;
    modal.hidden = false;
    modal.setAttribute("aria-hidden", "false");
    openButton.setAttribute("aria-expanded", "true");
    document.body.classList.add("customer-order-lookup-modal-open");
    window.requestAnimationFrame(() => input.focus());
  };
  const closeModal = () => {
    modal.hidden = true;
    modal.setAttribute("aria-hidden", "true");
    openButton.setAttribute("aria-expanded", "false");
    document.body.classList.remove("customer-order-lookup-modal-open");
    if (previousFocus && typeof previousFocus.focus === "function") previousFocus.focus();
  };
  openButton.addEventListener("click", openModal);
  closeButtons.forEach((control) => control.addEventListener("click", closeModal));
  modal.addEventListener("keydown", (event) => {
    if (event.key === "Escape") { event.preventDefault(); closeModal(); return; }
    if (event.key !== "Tab") return;
    const focusable = [...dialog.querySelectorAll('button:not([disabled]),input:not([disabled]),a[href]')].filter((element) => !element.hidden);
    if (!focusable.length) return;
    const first = focusable[0], last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (form.dataset.loading === "1") return;
    form.dataset.loading = "1";
    const originalText = button.textContent;
    button.disabled = true;
    button.textContent = "Consultando…";
    result.hidden = true;
    deliveryLink.hidden = true;
    deliveryLink.removeAttribute("href");
    try {
      const response = await fetch("/compras/pedidos/consultar", {
        method: "POST",
        headers: {"Content-Type": "application/json", "X-CSRF-Token": root.dataset.checkoutCsrf || ""},
        body: JSON.stringify({public_order_id: input.value.trim()}),
        cache: "no-store",
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.message || "No encontramos un pedido disponible para esta sesión.");
      orderId.textContent = `Pedido: ${data.order.public_order_id}`;
      state.textContent = data.order.payment_status === "paid" ? "Estado del pago: Pagado" : "Estado del pago: Pendiente";
      message.textContent = data.order.message;
      if (data.order.delivery_available) {
        deliveryLink.href = data.order.delivery_url;
        deliveryLink.hidden = false;
      }
      result.dataset.state = data.order.state;
    } catch (error) {
      orderId.textContent = "Consulta de pedido";
      state.textContent = "No disponible";
      message.textContent = error.message;
      result.dataset.state = "denied";
    } finally {
      result.hidden = false;
      form.dataset.loading = "0";
      button.disabled = false;
      button.textContent = originalText;
    }
  });
})();
