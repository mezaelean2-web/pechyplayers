document.addEventListener("DOMContentLoaded", function () {
  const esMovil = window.innerWidth <= 768;

  /* ==========================
     SPLASH
  ========================== */

  if (typeof iniciarSplash === "function") {
  iniciarSplash();
} else {
  const splash = document.getElementById("splashMobile");

  setTimeout(function () {
    splash?.classList.add("oculto");
  }, 1800);

  setTimeout(function () {
    splash?.remove();
  }, 2500);
}

  /* ==========================
     MODAL DE PRODUCTO COMPARTIDO
  ========================== */
  const modal = document.getElementById("productoModal");
  const cerrar = document.getElementById("cerrarProductoModal");
  const fondo = modal?.querySelector(".producto-modal-fondo");
  const contenido = modal?.querySelector(".producto-modal-contenido");

  const modalImagen = document.getElementById("modalProductoImagen");
  const modalImagenFondo = document.getElementById("modalProductoImagenFondo");
  const modalNombre = document.getElementById("modalProductoNombre");
  const modalTopNombre = document.getElementById("modalProductoTopNombre");
  const modalCategoria = document.getElementById("modalProductoCategoria");
  const modalEstado = modal?.querySelector(".modal-topbar > span");
  const modalPlanes = document.getElementById("modalProductoPlanes");
  const modalComprar = document.getElementById("modalProductoComprar");
  const modalCompartir = document.getElementById("modalProductoCompartir");
  const modalFavorito = document.getElementById("modalFavorito");
  const modalRecomendacionesLista =
  document.getElementById("modalRecomendacionesLista");

  let tarjetaActual = null;
  let cambioProductoId = 0;
  const abridoresModal = new Map();
  const tarjetasPorNombre = new Map();

  function productoAgotado(card) {
  return Boolean(
    card?.querySelector(".agotado-ribbon") ||
    card?.querySelector(".buy-agotado")
  );
}

function enviarAgotadoAWhatsApp(card) {
  const enlace =
    card?.querySelector(".buy-agotado")?.getAttribute("href");

  if (enlace) {
    window.location.href = enlace;
  }
}

  if (!modal) return;

  function cerrarModal() {
    cambioProductoId += 1;
    modal.classList.remove("abierto");
    document.body.classList.remove("modal-abierto");
    contenido?.classList.remove("is-switching");

    if (contenido) {
      contenido.style.transform = "";
      contenido.style.transition = "";
    }
  }

  const tarjetasConModal = document.querySelectorAll(".producto-item");

  tarjetasConModal.forEach(function (card) {
    const cover = card.querySelector(".cover");
    const boton = card.querySelector(".buy");

    function abrirModalProducto(opciones = {}) {
      const navegacionInterna = opciones.navegacionInterna === true;

      if (productoAgotado(card) && !navegacionInterna) {
  enviarAgotadoAWhatsApp(card);
  return;
}
      const solicitudActual = ++cambioProductoId;
      const cambiandoProducto = modal.classList.contains("abierto");

      if (cambiandoProducto) {
        contenido?.classList.add("is-switching");
        contenido?.scrollTo({ top: 0, behavior: "auto" });
      }

        tarjetaActual = card;
      const nombre =
        card.querySelector(".cover-overlay h3")?.textContent.trim() || "";

      const imagen =
        card.querySelector(".cover-img")?.getAttribute("src") || "";

      const comprar =
        boton?.getAttribute("href") || "#";

      if (modalNombre) {
        modalNombre.textContent = nombre;
      }

      if (modalTopNombre) {
        modalTopNombre.textContent = nombre;
      }

      if (modalCategoria) {
        modalCategoria.textContent = card.dataset.categoria || "PECHY PLAYERS PREMIUM";
      }

      if (modalEstado) {
        modalEstado.textContent = "â— ACTIVO";
      }

      if (modalFavorito) {
  const recordatorios = obtenerRecordatorios();
  const claveNombre = card.dataset.nombre || nombre.toLowerCase();

  const yaGuardado = recordatorios.some(function (item) {
    return item.nombre === claveNombre;
  });

  modalFavorito.classList.toggle("activo", yaGuardado);

  modalFavorito.textContent = yaGuardado
    ? "✅ Te lo recordaremos cuando vuelvas"
    : "🔔 Recordarme este producto";
}

      if (modalImagen) {
        modalImagen.src = imagen;
        modalImagen.alt = nombre;
      }

      if (modalImagenFondo) {
        modalImagenFondo.src = imagen;
      }

      if (modalComprar) {
        modalComprar.href = comprar;
      }

      if (modalPlanes) {
        modalPlanes.innerHTML = "";

        card.querySelectorAll(".plan").forEach(function (plan) {
          const copia = document.createElement("div");
          copia.className = "modal-plan";
          copia.innerHTML = plan.innerHTML;
          if (plan.dataset.publicPlanId && !plan.dataset.resellerPlanId) {
            const agregar = document.createElement("button");
            agregar.type = "button";
            agregar.className = "modal-plan-cart-add";
            agregar.dataset.publicCartAdd = plan.dataset.publicPlanId;
            agregar.textContent = "Agregar al carrito";
            agregar.setAttribute("aria-label", `Agregar ${nombre} ${plan.querySelector("span")?.textContent.trim() || "plan"} al carrito`);
            copia.appendChild(agregar);
            copia.classList.add("modal-plan--customer-cart");
          }
          if (plan.dataset.resellerPlanId) {
            copia.dataset.resellerPlanId = plan.dataset.resellerPlanId;
            copia.dataset.resellerPriceReady = plan.dataset.resellerPriceReady || "false";
            copia.tabIndex = 0;
            copia.setAttribute("role", "button");
          }
          modalPlanes.appendChild(copia);
        });
      }

      const colorPlataforma =
        getComputedStyle(card).getPropertyValue("--color-plataforma").trim() ||
        getComputedStyle(card).getPropertyValue("--catalogo-color").trim() ||
        "#ff2d2d";

      modal.style.setProperty("--modal-color", colorPlataforma);

      if (modalRecomendacionesLista) {
  modalRecomendacionesLista.innerHTML = "";

  const nombreActual = card.dataset.nombre || nombre.toLowerCase();
  const productosUnicos = new Map();

  document.querySelectorAll(".producto-item").forEach(function (otraCard) {
    const clave = otraCard.dataset.nombre || "";
    if (clave && clave !== nombreActual && !productosUnicos.has(clave)) {
      productosUnicos.set(clave, otraCard);
    }
  });

  const otrasTarjetas = [...productosUnicos.values()];

  otrasTarjetas.slice(0, 6).forEach(function (otraCard) {
  const otroNombre =
    otraCard.querySelector(".cover-overlay h3")
      ?.textContent.trim() || "Plataforma";

  const otraImagen =
    otraCard.querySelector(".cover-img")
      ?.getAttribute("src") || "";

  const estaAgotado =
    productoAgotado(otraCard);

  const recomendacion =
    document.createElement("button");

  recomendacion.type = "button";
  recomendacion.dataset.modalProducto = otraCard.dataset.nombre || "";

  recomendacion.className =
    estaAgotado
      ? "modal-recomendacion recomendacion-agotada"
      : "modal-recomendacion";

  recomendacion.innerHTML = `
    <div class="modal-recomendacion-imagen">
      <img src="${otraImagen}" alt="${otroNombre}">

      ${
        estaAgotado
  ? `
    <div class="recomendacion-ribbon-agotado">
  <span>AGOTADO</span>
</div>
  `
  : ""
      }
    </div>

    <div class="modal-recomendacion-info">
      <strong>${otroNombre}</strong>

      <span>
        ${
          estaAgotado
            ? "Avísame cuando esté disponible →"
            : "Ver planes →"
        }
      </span>
    </div>
  `;

  modalRecomendacionesLista.appendChild(
    recomendacion
  );
});

}

if(typeof actualizarActividadModal==="function"){
    actualizarActividadModal(nombre);
}

if (
  typeof actualizarOfertaInteligente ===
  "function"
) {
  actualizarOfertaInteligente(nombre);
}

      modal.classList.add("abierto");
      document.body.classList.add("modal-abierto");

      const finalizarCambio = function () {
        if (solicitudActual !== cambioProductoId) return;
        contenido?.classList.remove("is-switching");
      };

      if (!cambiandoProducto || modalImagen?.complete) {
        requestAnimationFrame(finalizarCambio);
      } else {
        modalImagen?.addEventListener("load", finalizarCambio, { once: true });
        modalImagen?.addEventListener("error", finalizarCambio, { once: true });
      }
    }

    abridoresModal.set(card, abrirModalProducto);

    const claveProducto = card.dataset.nombre || "";
    if (claveProducto && !tarjetasPorNombre.has(claveProducto)) {
      tarjetasPorNombre.set(claveProducto, card);
    }

    if (esMovil) {
      cover?.addEventListener("click", abrirModalProducto);
    }

    boton?.addEventListener("click", function (e) {
      if (boton.classList.contains("buy-agotado")) return;

      e.preventDefault();
      abrirModalProducto();
    });
  });

  window.abrirProductoModalCompartido = function (card) {
    const clave = card?.dataset.nombre || "";
    const tarjetaRegistrada = tarjetasPorNombre.get(clave) || card;
    const abrir = abridoresModal.get(tarjetaRegistrada);
    abrir?.();
  };

  modal.addEventListener("click", function (evento) {
    const accion = evento.target.closest("[data-modal-producto]");
    if (!accion || !modal.contains(accion)) return;

    evento.preventDefault();
    evento.stopPropagation();

    const claveProducto = accion.dataset.modalProducto || "";
    const tarjeta = tarjetasPorNombre.get(claveProducto);
    const abrir = abridoresModal.get(tarjeta);

    if (!tarjeta || !abrir) {
      console.warn(
        "No se pudo resolver la navegación interna del modal:",
        claveProducto
      );
      return;
    }

    abrir({ navegacionInterna: true });
  });

  cerrar?.addEventListener("click", cerrarModal);
  fondo?.addEventListener("click", cerrarModal);

  if (!esMovil) {
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && modal.classList.contains("abierto")) {
        cerrarModal();
      }
    });
  }

  modalCompartir?.addEventListener("click", async function () {
  if (!tarjetaActual) return;

  const nombre =
    tarjetaActual.querySelector(".cover-overlay h3")
      ?.textContent.trim() || "Plataforma";

  const enlace = window.location.href.split("#")[0];

  const texto =
    `Mira los planes de ${nombre} en PECHY PLAYERS: ${enlace}`;

  try {
    /* En HTTPS abre el menú nativo del teléfono */
    if (navigator.share) {
      await navigator.share({
        title: `PECHY PLAYERS - ${nombre}`,
        text: texto,
        url: enlace
      });

      return;
    }

    /* Si permite copiar, copia el mensaje */
    if (navigator.clipboard) {
      await navigator.clipboard.writeText(texto);

      if (typeof mostrarToast === "function") {
        mostrarToast("Enlace copiado para compartir.");
      }

      return;
    }
  } catch (error) {
    console.log("Compartir nativo no disponible:", error);
  }

  /* Respaldo para pruebas locales: abre WhatsApp */
  const enlaceWhatsApp =
    `https://wa.me/?text=${encodeURIComponent(texto)}`;

  window.open(enlaceWhatsApp, "_blank");
});

  modalFavorito?.addEventListener("click", function () {
  if (!tarjetaActual) return;

  const nombreVisible =
    tarjetaActual.querySelector(".cover-overlay h3")
      ?.textContent.trim() || "Plataforma";

  const claveNombre =
    tarjetaActual.dataset.nombre ||
    nombreVisible.toLowerCase();

  const imagen =
    tarjetaActual.querySelector(".cover-img")
      ?.getAttribute("src") || "";

  const comprar =
    tarjetaActual.querySelector(".buy")
      ?.getAttribute("href") || "#";

  const planes = [];

  tarjetaActual.querySelectorAll(".plan").forEach(function (plan) {
    planes.push(plan.innerHTML);
  });

  const color =
    getComputedStyle(tarjetaActual).getPropertyValue("--color-plataforma").trim() ||
    getComputedStyle(tarjetaActual).getPropertyValue("--catalogo-color").trim() ||
    "#ff2d2d";

  const recordatorios = obtenerRecordatorios();

  const yaExiste = recordatorios.some(function (item) {
    return item.nombre === claveNombre;
  });

  if (!yaExiste) {
    recordatorios.push({
      nombre: claveNombre,
      nombreVisible: nombreVisible,
      imagen: imagen,
      comprar: comprar,
      planes: planes,
      color: color
    });

    guardarRecordatorios(recordatorios);
  }

mostrarToast("¡Perfecto! El Pechy ya lo dejó guardado.");

  modalFavorito.classList.add("activo");
modalFavorito.textContent =
  "✅ Te lo recordaremos cuando vuelvas";

modalFavorito.classList.remove("confirmado");
void modalFavorito.offsetWidth;
modalFavorito.classList.add("confirmado");

  actualizarEstadoRecordatorios();
});

actualizarEstadoRecordatorios();

/* ==========================
   DESLIZAR MODAL HACIA ABAJO
   Solo cierra estando arriba
========================== */

if (esMovil && contenido) {
  let inicioY = 0;
  let movimientoY = 0;
  let arrastrando = false;
  let puedeCerrar = false;

  contenido.addEventListener(
    "touchstart",
    function (e) {
      if (!modal.classList.contains("abierto")) return;

      inicioY = e.touches[0].clientY;
      movimientoY = 0;

      /*
       Solo permite arrastrar el modal cuando
       el contenido ya está completamente arriba.
      */
      puedeCerrar = contenido.scrollTop <= 2;
      arrastrando = puedeCerrar;

      if (puedeCerrar) {
        contenido.style.transition = "none";
      }
    },
    { passive: true }
  );

  contenido.addEventListener(
    "touchmove",
    function (e) {
      if (!arrastrando || !puedeCerrar) return;

      movimientoY = e.touches[0].clientY - inicioY;

      /*
       Solo mueve el modal si el dedo baja.
       Si el dedo sube, deja funcionar el scroll normal.
      */
      if (movimientoY > 0) {
        contenido.style.transform =
          `translateY(${movimientoY}px)`;
      }
    },
    { passive: true }
  );

  contenido.addEventListener("touchend", function () {
    if (!arrastrando || !puedeCerrar) return;

    arrastrando = false;
    puedeCerrar = false;

    contenido.style.transition =
      "transform .4s cubic-bezier(.22,.61,.36,1)";

    if (movimientoY > 140) {
      cerrarModal();
    } else {
      contenido.style.transform = "translateY(0)";
    }

    movimientoY = 0;
  });

    contenido.addEventListener("touchcancel", function () {
    arrastrando = false;
    puedeCerrar = false;
    movimientoY = 0;

    contenido.style.transform = "translateY(0)";
    contenido.style.transition =
      "transform .4s cubic-bezier(.22,.61,.36,1)";
  });
}

/* Cierra DOMContentLoaded */
});
