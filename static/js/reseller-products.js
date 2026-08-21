document.addEventListener("DOMContentLoaded", () => {
  if (document.body.dataset.catalogContext !== "reseller") return;
  const drawer = document.getElementById("resellerProductDrawer");
  const opener = document.querySelector("[data-reseller-drawer-open]");
  const setOpen = (open) => {
    if (!drawer) return;
    drawer.classList.toggle("is-open", open);
    drawer.setAttribute("aria-hidden", String(!open));
    opener?.setAttribute("aria-expanded", String(open));
    document.body.classList.toggle("reseller-drawer-open", open);
  };
  opener?.addEventListener("click", () => setOpen(true));
  drawer?.querySelectorAll("[data-reseller-drawer-close]").forEach((item) => item.addEventListener("click", () => setOpen(false)));
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && drawer?.classList.contains("is-open")) setOpen(false);
  });

  // mobile.js copia el href público al abrir el modal. Este observador mantiene
  // el CTA reseller estrictamente visual y sin destino financiero/comercial.
  const modalCta = document.getElementById("modalProductoComprar");
  if (modalCta) {
    const preserveDisabledCta = () => {
      modalCta.removeAttribute("href");
      modalCta.setAttribute("disabled", "");
      modalCta.setAttribute("aria-disabled", "true");
    };
    preserveDisabledCta();
    new MutationObserver(preserveDisabledCta).observe(modalCta, { attributes: true, attributeFilter: ["href"] });
  }
});
