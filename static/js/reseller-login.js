(() => {
  "use strict";
  const toggle = document.querySelector("[data-password-toggle]");
  const password = document.querySelector("#reseller-password");
  if (!toggle || !password) return;
  toggle.addEventListener("click", () => {
    const visible = password.type === "password";
    password.type = visible ? "text" : "password";
    toggle.setAttribute("aria-pressed", String(visible));
    toggle.setAttribute("aria-label", visible ? "Ocultar contraseña" : "Mostrar contraseña");
    password.focus({preventScroll: true});
  });
})();
