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

(() => {
  const input = document.getElementById("rulesSearch");
  const clear = document.getElementById("rulesSearchClear");
  const empty = document.getElementById("rulesNoResults");
  const cards = Array.from(document.querySelectorAll(".rule-card"));
  if (!input || !clear || !empty) return;

  const normalize = (value) => String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLocaleLowerCase("es")
    .trim();

  const searchableText = (card) => {
    const unit = card.elements.tipo_unidad?.selectedOptions?.[0]?.textContent || "";
    const platform = card.elements.plataforma?.selectedOptions?.[0]?.textContent || "";
    const id = card.dataset.planId || "";
    return normalize([
      card.dataset.producto,
      card.dataset.plan,
      platform,
      unit,
      id,
      `#${id}`
    ].join(" "));
  };

  const filter = () => {
    const query = normalize(input.value);
    let visible = 0;
    cards.forEach((card) => {
      const matches = !query || searchableText(card).includes(query);
      card.hidden = !matches;
      if (matches) visible += 1;
    });
    clear.hidden = !input.value;
    empty.hidden = visible > 0 || !query;
  };

  input.addEventListener("input", filter);
  clear.addEventListener("click", () => {
    input.value = "";
    filter();
    input.focus();
  });
})();
