document.addEventListener("DOMContentLoaded", function () {
  const esMovil = window.innerWidth <= 768;

  /* ==========================
     SPLASH
  ========================== */

  iniciarSplash();

  if (!esMovil) return;

  /* ==========================
     MODAL DE PRODUCTO
  ========================== */
  const modal = document.getElementById("productoModal");
  const cerrar = document.getElementById("cerrarProductoModal");
  const fondo = modal?.querySelector(".producto-modal-fondo");
  const contenido = modal?.querySelector(".producto-modal-contenido");

  const modalImagen = document.getElementById("modalProductoImagen");
  const modalNombre = document.getElementById("modalProductoNombre");
  const modalTopNombre = document.getElementById("modalProductoTopNombre");
  const modalPlanes = document.getElementById("modalProductoPlanes");
  const modalComprar = document.getElementById("modalProductoComprar");
  const modalCompartir = document.getElementById("modalProductoCompartir");
  const modalFavorito = document.getElementById("modalFavorito");
  const modalRecomendacionesLista =
  document.getElementById("modalRecomendacionesLista");

  let tarjetaActual = null;

  if (!modal) return;

  function cerrarModal() {
    modal.classList.remove("abierto");
    document.body.classList.remove("modal-abierto");

    if (contenido) {
      contenido.style.transform = "";
      contenido.style.transition = "";
    }
  }

  document.querySelectorAll(".producto-item").forEach(function (card) {
    const cover = card.querySelector(".cover");
    const boton = card.querySelector(".buy");

    function abrirModalProducto() {
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
          modalPlanes.appendChild(copia);
        });
      }

      const colorPlataforma =
        getComputedStyle(card)
          .getPropertyValue("--color-plataforma")
          .trim() || "#ff2d2d";

      modal.style.setProperty("--modal-color", colorPlataforma);

      if (modalRecomendacionesLista) {
  modalRecomendacionesLista.innerHTML = "";

  const otrasTarjetas = [
    ...document.querySelectorAll(".producto-item")
  ].filter(function (otraCard) {
    return otraCard !== card;
  });

  otrasTarjetas.slice(0, 6).forEach(function (otraCard) {
    const otroNombre =
      otraCard.querySelector(".cover-overlay h3")
        ?.textContent.trim() || "Plataforma";

    const otraImagen =
      otraCard.querySelector(".cover-img")
        ?.getAttribute("src") || "";

    const recomendacion = document.createElement("button");

    recomendacion.type = "button";
    recomendacion.className = "modal-recomendacion";

    recomendacion.innerHTML = `
      <img src="${otraImagen}" alt="${otroNombre}">
      <div class="modal-recomendacion-info">
        <strong>${otroNombre}</strong>
        <span>Ver planes →</span>
      </div>
    `;

    recomendacion.addEventListener("click", function () {
      const otraPortada = otraCard.querySelector(".cover");

      contenido?.scrollTo({
        top: 0,
        behavior: "smooth"
      });

      otraPortada?.click();
    });

    modalRecomendacionesLista.appendChild(recomendacion);
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
    }

    cover?.addEventListener("click", abrirModalProducto);

    boton?.addEventListener("click", function (e) {
      e.preventDefault();
      abrirModalProducto();
    });
  });

  cerrar?.addEventListener("click", cerrarModal);
  fondo?.addEventListener("click", cerrarModal);

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
    getComputedStyle(tarjetaActual)
      .getPropertyValue("--color-plataforma")
      .trim() || "#ff2d2d";

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

if (contenido) {
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