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
  const recovery = root.querySelector("[data-customer-order-recovery]");
  const recoveryMessage = root.querySelector("[data-customer-order-recovery-message]");
  const channels = root.querySelector("[data-customer-order-recovery-channels]");
  const otpForm = root.querySelector("[data-customer-order-otp-form]");
  const otpInputs = [...root.querySelectorAll('[name="otp_digit"]')];
  const otpMessage = root.querySelector("[data-customer-order-otp-message]");
  const resendButton = root.querySelector("[data-customer-order-otp-resend]");
  const result = root.querySelector("[data-customer-order-lookup-result]");
  const orderId = root.querySelector("[data-customer-order-lookup-id]");
  const state = root.querySelector("[data-customer-order-lookup-state]");
  const message = root.querySelector("[data-customer-order-lookup-message]");
  const deliveryLink = root.querySelector("[data-customer-order-delivery-link]");
  let previousFocus = null, recoveryId = "", selectedChannel = "", cooldownTimer = null;
  const csrfHeaders = () => ({"Content-Type": "application/json", "X-CSRF-Token": root.dataset.checkoutCsrf || ""});
  const hide = (element) => { element.hidden = true; };
  const show = (element) => { element.hidden = false; };
  const resetFlow = () => {
    recoveryId = ""; selectedChannel = ""; channels.replaceChildren();
    otpInputs.forEach((field) => { field.value = ""; });
    otpMessage.textContent = ""; hide(recovery); hide(otpForm); hide(result);
    deliveryLink.hidden = true; deliveryLink.removeAttribute("href");
    if (cooldownTimer) window.clearInterval(cooldownTimer);
  };
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
  const renderOrder = (order) => {
    hide(recovery); hide(otpForm); show(result);
    orderId.textContent = `Pedido: ${order.public_order_id}`;
    state.textContent = order.payment_status === "paid" ? "Estado del pago: Pagado" : "Estado del pago: Pendiente";
    message.textContent = order.message;
    if (order.delivery_available) { deliveryLink.href = order.delivery_url; deliveryLink.hidden = false; }
    result.dataset.state = order.state;
  };
  const beginCooldown = (seconds) => {
    let remaining = Math.max(1, Number(seconds) || 60);
    resendButton.disabled = true; resendButton.textContent = `Reenviar código en ${remaining} s`;
    if (cooldownTimer) window.clearInterval(cooldownTimer);
    cooldownTimer = window.setInterval(() => {
      remaining -= 1;
      resendButton.textContent = remaining > 0 ? `Reenviar código en ${remaining} s` : "Reenviar código";
      if (remaining <= 0) { window.clearInterval(cooldownTimer); resendButton.disabled = false; }
    }, 1000);
  };
  const requestOtp = async (channel) => {
    selectedChannel = channel; otpMessage.textContent = "Solicitando código…";
    const response = await fetch("/compras/pedidos/recuperacion/otp/solicitar", {
      method: "POST", headers: csrfHeaders(), cache: "no-store",
      body: JSON.stringify({recovery_id: recoveryId, channel}),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error("No pudimos procesar la solicitud. Intenta nuevamente.");
    show(otpForm); otpMessage.textContent = data.message || "Revisa el canal seleccionado.";
    beginCooldown(data.retry_after); otpInputs[0].focus();
  };
  const showRecovery = (data) => {
    recoveryId = data.recovery_id; recoveryMessage.textContent = data.message; channels.replaceChildren();
    (data.channels || []).filter((item) => item.available !== false).forEach((item) => {
      const control = document.createElement("button"); control.type = "button"; control.dataset.channel = item.channel;
      control.textContent = item.channel === "whatsapp" ? `Enviar por WhatsApp · ${item.destination}` : `Enviar por correo · ${item.destination}`;
      control.addEventListener("click", () => requestOtp(item.channel).catch((error) => { otpMessage.textContent = error.message; show(otpForm); }));
      channels.append(control);
    });
    show(recovery);
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
  otpInputs.forEach((field, index) => {
    field.addEventListener("input", () => { field.value = field.value.replace(/\D/g, "").slice(-1); if (field.value && otpInputs[index + 1]) otpInputs[index + 1].focus(); });
    field.addEventListener("keydown", (event) => { if (event.key === "Backspace" && !field.value && otpInputs[index - 1]) otpInputs[index - 1].focus(); });
    field.addEventListener("paste", (event) => {
      const code = event.clipboardData.getData("text").replace(/\D/g, "").slice(0, 6);
      if (code.length !== 6) return;
      event.preventDefault(); otpInputs.forEach((item, position) => { item.value = code[position]; }); otpInputs[5].focus();
    });
  });
  form.addEventListener("submit", async (event) => {
    event.preventDefault(); if (form.dataset.loading === "1") return;
    form.dataset.loading = "1"; resetFlow();
    const originalText = button.textContent; button.disabled = true; button.textContent = "Consultando…";
    try {
      const response = await fetch("/compras/pedidos/consultar", {method: "POST", headers: csrfHeaders(), body: JSON.stringify({public_order_id: input.value.trim()}), cache: "no-store"});
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.message || "No pudimos iniciar la consulta segura.");
      if (data.recovery_required) showRecovery(data);
      else { if (data.order.delivery_available) deliveryLink.href = data.order.delivery_url; renderOrder(data.order); }
    } catch (error) {
      orderId.textContent = "Consulta de pedido"; state.textContent = "No disponible"; message.textContent = error.message; result.dataset.state = "denied"; show(result);
    } finally { form.dataset.loading = "0"; button.disabled = false; button.textContent = originalText; }
  });
  resendButton.addEventListener("click", () => { if (selectedChannel) requestOtp(selectedChannel).catch((error) => { otpMessage.textContent = error.message; }); });
  otpForm.addEventListener("submit", async (event) => {
    event.preventDefault(); const code = otpInputs.map((field) => field.value).join("");
    if (!/^\d{6}$/.test(code)) { otpMessage.textContent = "Ingresa los seis dígitos."; return; }
    const verifyButton = otpForm.querySelector('button[type="submit"]'); verifyButton.disabled = true; otpMessage.textContent = "Verificando…";
    try {
      const response = await fetch("/compras/pedidos/recuperacion/otp/verificar", {method: "POST", headers: csrfHeaders(), cache: "no-store", body: JSON.stringify({recovery_id: recoveryId, code})});
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.message || "El código no es válido.");
      renderOrder(data.order);
    } catch (error) { otpMessage.textContent = error.message; }
    finally { verifyButton.disabled = false; }
  });
})();
