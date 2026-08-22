document.querySelectorAll(".rule-card").forEach((form) => form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const status = form.querySelector("[role=status]");
  const button = form.querySelector("button");
  const data = Object.fromEntries(new FormData(form));
  data.activo = form.elements.activo.checked;
  button.disabled = true; status.textContent = "Guardando…";
  try {
    const response = await fetch(`/admin/reglas-inventario-reseller/${form.dataset.planId}`, {
      method: "POST", headers: {"Content-Type": "application/json", "X-CSRF-Token": document.querySelector(".rules-page").dataset.csrfToken},
      body: JSON.stringify(data)
    });
    const result = await response.json();
    status.textContent = result.ok ? "Configuración guardada." : (result.mensaje || "No fue posible guardar.");
    status.classList.toggle("is-error", !result.ok);
  } catch (_) { status.textContent = "Error de conexión."; status.classList.add("is-error"); }
  finally { button.disabled = false; }
}));
