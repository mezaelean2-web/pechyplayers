document.addEventListener("DOMContentLoaded", () => {
  if (!window.matchMedia("(min-width: 769px)").matches) return;

  const accesosRapidos = [...document.querySelectorAll(".desktop-category-access__links a")];
  const barraCategorias = document.querySelector(".desktop-category-access");
  const carruselCategorias = document.querySelector(".desktop-category-carousel");
  const viewportCategorias = document.querySelector(".desktop-category-carousel__viewport");
  const trackCategorias = document.querySelector(".desktop-category-access__links");
  const flechaCategoriaAnterior = document.querySelector(".desktop-category-carousel__arrow--previous");
  const flechaCategoriaSiguiente = document.querySelector(".desktop-category-carousel__arrow--next");
  const headerPublico = document.querySelector(".nav");
  const placeholderHeader = headerPublico
    ? Object.assign(document.createElement("div"), {
        className: "public-header-placeholder",
        ariaHidden: "true",
      })
    : null;
  const placeholderCategorias = barraCategorias
    ? Object.assign(document.createElement("div"), { className: "desktop-category-access-placeholder" })
    : null;

  if (headerPublico && placeholderHeader) {
    headerPublico.after(placeholderHeader);
  }

  if (barraCategorias && placeholderCategorias) {
    barraCategorias.before(placeholderCategorias);
  }

  let stickyRafCategorias = 0;
  let topNaturalCategorias = 0;

  const paletaCategorias = ["#9b6cff", "#22b8f0", "#ec4899", "#ef4444", "#f59e0b", "#22c55e", "#14b8a6", "#f97316"];
  const acentosConocidos = [
    [/anime/i, "#9b6cff"],
    [/iptv|\btv\b/i, "#22b8f0"],
    [/m[uú]sica|music/i, "#ec4899"],
    [/stream|pel[ií]cula/i, "#ef4444"],
    [/combo/i, "#f59e0b"],
    [/deport/i, "#22c55e"],
  ];

  accesosRapidos.forEach((acceso) => {
    const identidad = `${acceso.textContent} ${acceso.getAttribute("href") || ""}`.trim();
    const conocido = acentosConocidos.find(([patron]) => patron.test(identidad));
    const hash = [...identidad].reduce((total, caracter) => ((total * 31) + caracter.charCodeAt(0)) >>> 0, 0);
    acceso.style.setProperty("--category-hover-accent", conocido?.[1] || paletaCategorias[hash % paletaCategorias.length]);
  });

  accesosRapidos.forEach((acceso, indice) => {
    acceso.dataset.categoryCarouselKey = String(indice);
  });

  let carruselInfinitoActivo = false;
  let inicioOriginales = 0;
  let longitudOriginales = 0;
  let reconstruccionRaf = 0;
  let normalizacionRaf = 0;
  let arrastrandoCategorias = false;
  let arrastreSuperoUmbral = false;
  let cancelarSiguienteClick = false;
  let punteroCategorias = null;
  let inicioPunteroX = 0;
  let inicioScrollCategorias = 0;

  const quitarIdsClonados = (clon) => {
    clon.removeAttribute("id");
    clon.querySelectorAll("[id]").forEach((elemento) => elemento.removeAttribute("id"));
  };

  const crearClonCategoria = (original) => {
    const clon = original.cloneNode(true);
    quitarIdsClonados(clon);
    clon.dataset.categoryCarouselClone = "true";
    clon.dataset.categoryCarouselKey = original.dataset.categoryCarouselKey;
    clon.setAttribute("aria-hidden", "true");
    clon.setAttribute("tabindex", "-1");
    clon.removeAttribute("aria-current");
    return clon;
  };

  const sincronizarActivoCategorias = (claveActiva) => {
    accesosRapidos.forEach((original) => {
      const activo = original.dataset.categoryCarouselKey === claveActiva;
      original.classList.toggle("is-active", activo);
      if (activo) original.setAttribute("aria-current", "page");
      else original.removeAttribute("aria-current");
    });

    trackCategorias?.querySelectorAll("[data-category-carousel-clone]").forEach((clon) => {
      clon.classList.toggle("is-active", clon.dataset.categoryCarouselKey === claveActiva);
    });
  };

  const normalizarCarruselCategorias = () => {
    normalizacionRaf = 0;
    if (!carruselInfinitoActivo || !trackCategorias || longitudOriginales <= 0) return;

    if (trackCategorias.scrollLeft < inicioOriginales - 1) {
      trackCategorias.scrollLeft += longitudOriginales;
    } else if (trackCategorias.scrollLeft >= inicioOriginales + longitudOriginales) {
      trackCategorias.scrollLeft -= longitudOriginales;
    }
  };

  const solicitarNormalizacionCategorias = () => {
    if (normalizacionRaf) return;
    normalizacionRaf = requestAnimationFrame(normalizarCarruselCategorias);
  };

  const centrarCategoria = (elemento, suave = true) => {
    if (!trackCategorias || !elemento) return;
    const destino = elemento.offsetLeft - ((trackCategorias.clientWidth - elemento.offsetWidth) / 2);
    trackCategorias.scrollTo({ left: destino, behavior: suave ? "smooth" : "auto" });
  };

  const reconstruirCarruselCategorias = () => {
    reconstruccionRaf = 0;
    if (!trackCategorias || !viewportCategorias || accesosRapidos.length === 0) return;

    const claveActiva = accesosRapidos.find((acceso) => acceso.classList.contains("is-active"))
      ?.dataset.categoryCarouselKey || "0";

    trackCategorias.querySelectorAll("[data-category-carousel-clone]").forEach((clon) => clon.remove());
    trackCategorias.scrollLeft = 0;
    carruselCategorias?.classList.add("is-static");

    const estilosTrack = getComputedStyle(trackCategorias);
    const gap = parseFloat(estilosTrack.columnGap || estilosTrack.gap) || 0;
    const anchoOriginales = accesosRapidos.reduce(
      (total, acceso) => total + acceso.getBoundingClientRect().width,
      gap * Math.max(0, accesosRapidos.length - 1)
    );
    const debeRepetirse = anchoOriginales > viewportCategorias.clientWidth + 1;

    carruselInfinitoActivo = debeRepetirse;
    carruselCategorias?.classList.toggle("is-static", !debeRepetirse);

    if (!debeRepetirse) {
      inicioOriginales = 0;
      longitudOriginales = 0;
      sincronizarActivoCategorias(claveActiva);
      return;
    }

    const anteriores = document.createDocumentFragment();
    const siguientes = document.createDocumentFragment();
    accesosRapidos.forEach((original) => {
      anteriores.appendChild(crearClonCategoria(original));
      siguientes.appendChild(crearClonCategoria(original));
    });
    trackCategorias.prepend(anteriores);
    trackCategorias.append(siguientes);

    inicioOriginales = accesosRapidos[0].offsetLeft;
    const clones = [...trackCategorias.querySelectorAll("[data-category-carousel-clone]")];
    const primerSiguiente = clones[accesosRapidos.length];
    if (!primerSiguiente) return;
    longitudOriginales = primerSiguiente.offsetLeft - inicioOriginales;
    trackCategorias.scrollLeft = inicioOriginales;
    sincronizarActivoCategorias(claveActiva);
  };

  const solicitarReconstruccionCategorias = () => {
    if (reconstruccionRaf) cancelAnimationFrame(reconstruccionRaf);
    reconstruccionRaf = requestAnimationFrame(reconstruirCarruselCategorias);
  };

  const moverUnaCategoria = (direccion) => {
    if (!trackCategorias || !carruselInfinitoActivo) return;
    const centroViewport = trackCategorias.getBoundingClientRect().left + (trackCategorias.clientWidth / 2);
    const candidatos = [...trackCategorias.querySelectorAll("a")]
      .map((acceso) => {
        const caja = acceso.getBoundingClientRect();
        return { acceso, distancia: caja.left + (caja.width / 2) - centroViewport };
      })
      .filter(({ distancia }) => direccion > 0 ? distancia > 2 : distancia < -2)
      .sort((a, b) => Math.abs(a.distancia) - Math.abs(b.distancia));

    if (candidatos[0]) {
      trackCategorias.scrollBy({ left: candidatos[0].distancia, behavior: "smooth" });
    }
  };

  trackCategorias?.addEventListener("scroll", solicitarNormalizacionCategorias, { passive: true });
  flechaCategoriaAnterior?.addEventListener("click", () => moverUnaCategoria(-1));
  flechaCategoriaSiguiente?.addEventListener("click", () => moverUnaCategoria(1));

  trackCategorias?.addEventListener("click", (evento) => {
    const acceso = evento.target.closest("a[data-category-carousel-key]");
    if (!acceso) return;
    if (cancelarSiguienteClick) {
      evento.preventDefault();
      evento.stopPropagation();
      cancelarSiguienteClick = false;
      return;
    }

    const clave = acceso.dataset.categoryCarouselKey;
    sincronizarActivoCategorias(clave);
    requestAnimationFrame(() => centrarCategoria(acceso));
  });

  trackCategorias?.addEventListener("pointerdown", (evento) => {
    if (evento.pointerType === "touch" || evento.button !== 0 || !carruselInfinitoActivo) return;
    arrastrandoCategorias = true;
    arrastreSuperoUmbral = false;
    cancelarSiguienteClick = false;
    punteroCategorias = evento.pointerId;
    inicioPunteroX = evento.clientX;
    inicioScrollCategorias = trackCategorias.scrollLeft;
  });

  trackCategorias?.addEventListener("pointermove", (evento) => {
    if (!arrastrandoCategorias || evento.pointerId !== punteroCategorias) return;
    const desplazamiento = evento.clientX - inicioPunteroX;
    if (!arrastreSuperoUmbral && Math.abs(desplazamiento) < 7) return;
    if (!arrastreSuperoUmbral) {
      arrastreSuperoUmbral = true;
      trackCategorias.setPointerCapture?.(evento.pointerId);
    }
    evento.preventDefault();
    trackCategorias.classList.add("is-dragging");
    trackCategorias.scrollLeft = inicioScrollCategorias - desplazamiento;
  });

  const terminarArrastreCategorias = (evento) => {
    if (!arrastrandoCategorias || evento.pointerId !== punteroCategorias) return;
    cancelarSiguienteClick = arrastreSuperoUmbral;
    arrastrandoCategorias = false;
    punteroCategorias = null;
    trackCategorias?.classList.remove("is-dragging");
    solicitarNormalizacionCategorias();
    if (cancelarSiguienteClick) setTimeout(() => { cancelarSiguienteClick = false; }, 0);
  };

  trackCategorias?.addEventListener("pointerup", terminarArrastreCategorias);
  trackCategorias?.addEventListener("pointercancel", terminarArrastreCategorias);

  trackCategorias?.addEventListener("wheel", (evento) => {
    if (!carruselInfinitoActivo || Math.abs(evento.deltaX) <= Math.abs(evento.deltaY) || Math.abs(evento.deltaX) < 2) return;
    evento.preventDefault();
    trackCategorias.scrollLeft += evento.deltaX;
  }, { passive: false });

  solicitarReconstruccionCategorias();

  if (window.ResizeObserver && viewportCategorias) {
    const observadorCarruselCategorias = new ResizeObserver(solicitarReconstruccionCategorias);
    observadorCarruselCategorias.observe(viewportCategorias);
  } else {
    window.addEventListener("resize", solicitarReconstruccionCategorias, { passive: true });
  }

  const actualizarMedidasCategorias = () => {
    const altoHeader = Math.ceil(headerPublico?.getBoundingClientRect().height || 72);
    const altoBarra = Math.ceil(barraCategorias?.getBoundingClientRect().height || 92);
    document.documentElement.style.setProperty("--public-header-height", `${altoHeader}px`);
    document.documentElement.style.setProperty("--desktop-category-height", `${altoBarra}px`);
    if (placeholderHeader) placeholderHeader.style.height = `${altoHeader}px`;
    if (barraCategorias && !barraCategorias.classList.contains("is-fixed")) {
      const caja = barraCategorias.getBoundingClientRect();
      topNaturalCategorias = caja.top + window.scrollY;
      barraCategorias.style.removeProperty("left");
      barraCategorias.style.removeProperty("width");
    }
  };

  const actualizarEstadoStickyCategorias = () => {
    stickyRafCategorias = 0;
    if (!barraCategorias) return;
    actualizarMedidasCategorias();
    const topSticky = parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--public-header-height")) || 0;
    const debeFijarse = window.scrollY + topSticky >= topNaturalCategorias;

    if (debeFijarse && !barraCategorias.classList.contains("is-fixed")) {
      const caja = barraCategorias.getBoundingClientRect();
      barraCategorias.style.left = `${caja.left}px`;
      barraCategorias.style.width = `${caja.width}px`;
      placeholderCategorias?.classList.add("is-active");
      barraCategorias.classList.add("is-fixed");
    } else if (!debeFijarse && barraCategorias.classList.contains("is-fixed")) {
      barraCategorias.classList.remove("is-fixed");
      placeholderCategorias?.classList.remove("is-active");
      barraCategorias.style.removeProperty("left");
      barraCategorias.style.removeProperty("width");
      actualizarMedidasCategorias();
    } else if (debeFijarse) {
      const cajaPlaceholder = placeholderCategorias?.getBoundingClientRect();
      if (cajaPlaceholder) {
        barraCategorias.style.left = `${cajaPlaceholder.left}px`;
        barraCategorias.style.width = `${cajaPlaceholder.width}px`;
      }
    }
  };

  const solicitarEstadoStickyCategorias = () => {
    if (stickyRafCategorias) return;
    stickyRafCategorias = requestAnimationFrame(actualizarEstadoStickyCategorias);
  };

  solicitarEstadoStickyCategorias();
  window.addEventListener("scroll", solicitarEstadoStickyCategorias, { passive: true });
  window.addEventListener("resize", solicitarEstadoStickyCategorias, { passive: true });

  if (window.ResizeObserver) {
    const observadorCategorias = new ResizeObserver(solicitarEstadoStickyCategorias);
    if (headerPublico) observadorCategorias.observe(headerPublico);
    if (barraCategorias) observadorCategorias.observe(barraCategorias);
  }

});
