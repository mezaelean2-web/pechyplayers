(() => {
  "use strict";
  const root = document.querySelector("[data-mailbox-root]");
  if (!root) return;
  const form = root.querySelector("[data-mailbox-search]");
  const input = form.querySelector("input[name='email']");
  const submit = form.querySelector("button[type='submit']");
  const status = root.querySelector("[data-mailbox-status]");
  const history = root.querySelector("[data-mailbox-history]");
  const viewer = root.querySelector("[data-mailbox-message]");
  const csrf = root.dataset.csrfToken || "";
  let timer = null;
  let activeRequest = null;

  const icons = () => { if (window.lucide) window.lucide.createIcons(); };
  const element = (tag, className, text) => {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  };
  const safeJson = async response => {
    try { return await response.json(); } catch (_) { return {status: "unavailable"}; }
  };
  const request = async (url, options = {}) => {
    const response = await fetch(url, {credentials: "same-origin", cache: "no-store", ...options});
    return {response, data: await safeJson(response)};
  };
  const stopPolling = () => { if (timer) window.clearTimeout(timer); timer = null; activeRequest = null; };
  const statusView = (mode, title, detail, icon) => {
    status.className = `mailbox-status${mode ? ` is-${mode}` : ""}`;
    status.replaceChildren();
    const iconWrap = element("span", "mailbox-status-icon");
    const iconNode = document.createElement("i"); iconNode.dataset.lucide = icon; iconWrap.append(iconNode);
    const copy = element("div"); copy.append(element("strong", "", title), element("p", "", detail));
    status.append(iconWrap, copy); icons();
  };
  const emptyViewer = message => {
    viewer.replaceChildren();
    const empty = element("div", "mailbox-empty");
    const icon = document.createElement("i"); icon.dataset.lucide = "mail-open";
    empty.append(icon, element("strong", "", "Sin contenido disponible"), element("p", "", message));
    viewer.append(empty); icons();
  };
  const formattedValue = message => {
    if (message.kind === "numeric_code") return String(message.value || "").replace(/(.{3})/g, "$1 ").trim();
    return String(message.value || "");
  };
  const showMessage = message => {
    viewer.replaceChildren();
    const card = element("article", "mailbox-message-card");
    const badge = element("span", "mailbox-message-badge");
    const badgeIcon = document.createElement("i"); badgeIcon.dataset.lucide = "shield-check";
    badge.append(badgeIcon, document.createTextNode(message.kind_label || "Mensaje autorizado"));
    card.append(badge, element("h4", "", message.service || "Servicio digital"),
      element("p", "", "Contenido recibido después de tu solicitud y autorizado por PECHY."));
    if (["numeric_code", "alphanumeric_code"].includes(message.kind)) {
      card.append(element("output", "mailbox-code", formattedValue(message)));
      const copy = element("button", "mailbox-copy"); copy.type = "button";
      copy.setAttribute("aria-label", "Copiar código autorizado");
      const copyIcon = document.createElement("i"); copyIcon.dataset.lucide = "copy";
      copy.append(copyIcon, document.createTextNode("COPIAR CÓDIGO"));
      copy.addEventListener("click", async () => {
        try {
          await navigator.clipboard.writeText(String(message.value || ""));
          copy.lastChild.textContent = " CÓDIGO COPIADO";
        } catch (_) { copy.lastChild.textContent = " NO SE PUDO COPIAR"; }
      });
      card.append(copy);
    } else {
      card.append(element("div", "mailbox-instruction", String(message.value || "Mensaje disponible.")));
    }
    viewer.append(card); icons();
  };
  const formatDate = value => {
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? "" : new Intl.DateTimeFormat("es-CO", {
      day: "2-digit", month: "short", hour: "numeric", minute: "2-digit"
    }).format(date);
  };
  const loadDelivery = async id => {
    const {data} = await request(`/revendedores/buzon/mensajes/${encodeURIComponent(id)}`);
    if (data.status === "found" && data.message) showMessage(data.message);
    else emptyViewer("No hay mensajes disponibles para esta cuenta.");
  };
  const renderHistory = items => {
    history.replaceChildren();
    if (!Array.isArray(items) || !items.length) {
      const empty = element("div", "mailbox-empty");
      const icon = document.createElement("i"); icon.dataset.lucide = "inbox";
      empty.append(icon, element("strong", "", "Aún no hay mensajes"),
        element("p", "", "Los mensajes que PECHY autorice y entregue aparecerán aquí."));
      history.append(empty); icons(); return;
    }
    items.forEach((item, index) => {
      const button = element("button", `mailbox-history-item${index === 0 ? " is-active" : ""}`);
      button.type = "button";
      const iconWrap = element("span", "mailbox-history-icon");
      const icon = document.createElement("i"); icon.dataset.lucide = "mail"; iconWrap.append(icon);
      const copy = element("span", "mailbox-history-copy");
      copy.append(element("strong", "", item.service || "Servicio digital"),
        element("span", "", item.kind_label || "Mensaje autorizado"));
      const time = element("time", "", formatDate(item.received_at)); time.dateTime = item.received_at || "";
      button.append(iconWrap, copy, time);
      button.addEventListener("click", () => loadDelivery(item.id));
      history.append(button);
    });
    icons();
  };
  const poll = async () => {
    if (!activeRequest) return;
    try {
      const {data} = await request(`/revendedores/buzon/solicitudes/${encodeURIComponent(activeRequest)}`);
      if (data.status === "waiting") {
        statusView("waiting", "Esperando nuevo mensaje…",
          "Buscamos el primer mensaje válido recibido después de tu solicitud.", "loader-circle");
        timer = window.setTimeout(poll, Math.max(1000, Number(data.retry_after || 1) * 1000));
      } else if (data.status === "found" && data.message) {
        stopPolling(); statusView("found", "Mensaje nuevo autorizado",
          "PECHY revalidó la asignación antes de mostrar el contenido.", "badge-check");
        renderHistory(data.history); showMessage(data.message); submit.disabled = false;
      } else {
        stopPolling(); statusView("", "No hay mensajes disponibles",
          "No podemos mostrar contenido para esta búsqueda.", "mail-x");
        emptyViewer("No hay mensajes disponibles para esta cuenta."); submit.disabled = false;
      }
    } catch (_) {
      stopPolling(); statusView("", "No hay mensajes disponibles",
        "Intenta nuevamente más tarde.", "wifi-off"); submit.disabled = false;
    }
  };
  form.addEventListener("submit", async event => {
    event.preventDefault(); stopPolling(); submit.disabled = true;
    statusView("waiting", "Validando la solicitud…",
      "Comprobamos la adquisición y la asignación actual sin usar el correo como autorización.", "loader-circle");
    try {
      const {data} = await request("/revendedores/buzon/solicitudes", {
        method: "POST",
        headers: {"Content-Type": "application/json", "X-CSRF-Token": csrf},
        body: JSON.stringify({email: input.value})
      });
      if (data.status === "waiting" && data.request_id) {
        activeRequest = data.request_id;
        if (Array.isArray(data.history)) renderHistory(data.history);
        statusView("waiting", "Esperando nuevo mensaje…",
          "Sólo aceptaremos el primer mensaje válido posterior al inicio de esta solicitud.", "loader-circle");
        timer = window.setTimeout(poll, Math.max(1000, Number(data.retry_after || 1) * 1000));
      } else {
        submit.disabled = false;
        statusView("", "No hay mensajes disponibles",
          "Verifica la dirección completa o intenta más tarde.", "mail-x");
        emptyViewer("No hay mensajes disponibles para esta cuenta.");
      }
    } catch (_) {
      submit.disabled = false;
      statusView("", "No hay mensajes disponibles", "Intenta nuevamente más tarde.", "wifi-off");
    }
  });
})();
