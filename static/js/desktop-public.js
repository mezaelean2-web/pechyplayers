document.addEventListener("DOMContentLoaded", () => {
  if (!window.matchMedia("(min-width: 769px)").matches) return;

  const accesosRapidos = [...document.querySelectorAll(".desktop-category-access__links a")];
  accesosRapidos.forEach((acceso) => {
    acceso.addEventListener("click", () => {
      accesosRapidos.forEach((item) => {
        const activo = item === acceso;
        item.classList.toggle("is-active", activo);
        if (activo) item.setAttribute("aria-current", "page");
        else item.removeAttribute("aria-current");
      });
    });
  });

  const cartelera = document.getElementById("carteleraLista");
  if (!cartelera) return;

  let framePendiente = 0;

  const actualizarProtagonista = () => {
    framePendiente = 0;
    const centro = cartelera.getBoundingClientRect().left + (cartelera.clientWidth / 2);
    const tarjetas = [...cartelera.querySelectorAll(".cartelera-card")]
      .filter((tarjeta) => getComputedStyle(tarjeta).display !== "none");
    let protagonista = null;
    let distanciaMinima = Infinity;

    tarjetas.forEach((tarjeta) => {
      const caja = tarjeta.getBoundingClientRect();
      const distancia = Math.abs((caja.left + (caja.width / 2)) - centro);
      if (distancia < distanciaMinima) {
        protagonista = tarjeta;
        distanciaMinima = distancia;
      }
    });

    tarjetas.forEach((tarjeta) => {
      tarjeta.classList.toggle("is-featured", tarjeta === protagonista);
    });
  };

  const solicitarActualizacion = () => {
    if (framePendiente) return;
    framePendiente = requestAnimationFrame(actualizarProtagonista);
  };

  cartelera.addEventListener("scroll", solicitarActualizacion, { passive: true });
  window.addEventListener("resize", solicitarActualizacion, { passive: true });
  solicitarActualizacion();

  document.querySelectorAll("[data-cartelera-direccion]").forEach((boton) => {
    boton.addEventListener("click", () => {
      const direccion = boton.dataset.carteleraDireccion === "anterior" ? -1 : 1;
      const tarjeta = cartelera.querySelector(".cartelera-card");
      const estilos = getComputedStyle(cartelera);
      const distancia = (tarjeta?.getBoundingClientRect().width || 240)
        + (parseFloat(estilos.columnGap || estilos.gap) || 20);

      cartelera.scrollBy({ left: direccion * distancia * 2, behavior: "smooth" });
    });
  });

  document.querySelectorAll(".categoria-btn").forEach((boton) => {
    boton.addEventListener("click", () => requestAnimationFrame(actualizarProtagonista));
  });
});
