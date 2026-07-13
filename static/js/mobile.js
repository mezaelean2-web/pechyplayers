document.addEventListener("DOMContentLoaded", function () {
  const esMovil = window.innerWidth <= 768;

  /* ==========================
     SPLASH
  ========================== */
  const splash = document.getElementById("splashMobile");

  if (splash && esMovil) {
    setTimeout(function () {
      splash.classList.add("oculto");
    }, 1800);

    setTimeout(function () {
  splash.remove();
  mostrarPantallaRecordatorios();
}, 2500);
  }

  if (!esMovil) return;

  const pantallaRecordatorios =
  document.getElementById("recordatoriosScreen");

const trackRecordatorios =
  document.getElementById("recordatoriosTrack");

  function mostrarPantallaRecordatorios() {
  if (!pantallaRecordatorios || !trackRecordatorios) return;

  const recordatorios = obtenerRecordatorios();

  if (recordatorios.length === 0) {
    pantallaRecordatorios.classList.remove("mostrar");
    return;
  }

  trackRecordatorios.innerHTML = "";

  pantallaRecordatorios
  .querySelector(".recordatorios-contador")
  ?.remove();

pantallaRecordatorios
  .querySelector(".recordatorios-puntos")
  ?.remove();

  recordatorios.forEach(function (item) {
    const tarjeta = document.createElement("article");
    tarjeta.className = "recordatorio-card";
    tarjeta.style.setProperty(
      "--recordatorio-color",
      item.color || "#ff2d2d"
    );

    const planesHTML = item.planes
      .map(function (plan) {
        return `<div class="recordatorio-plan">${plan}</div>`;
      })
      .join("");

    tarjeta.innerHTML = `
      <img
        src="${item.imagen}"
        alt="${item.nombreVisible}"
        class="recordatorio-imagen"
      >

      <div class="recordatorio-contenido">
        <small>TE LO RECORDAMOS ❤️</small>

        <h3>${item.nombreVisible}</h3>

        <div class="recordatorio-planes">
          ${planesHTML}
        </div>

        <a
          href="${item.comprar}"
          target="_blank"
          class="recordatorio-comprar">
          💬 Comprar ahora
        </a>

        <button
          type="button"
          class="recordatorio-explorar">
          Explorar catálogo
        </button>
      </div>
    `;

    const botonComprar =
      tarjeta.querySelector(".recordatorio-comprar");

    const botonExplorar =
      tarjeta.querySelector(".recordatorio-explorar");

    function eliminarRecordatorioActual() {
      const nuevos = obtenerRecordatorios().filter(function (guardado) {
        return guardado.nombre !== item.nombre;
      });

      guardarRecordatorios(nuevos);
      actualizarEstadoRecordatorios();
    }

    botonComprar?.addEventListener("click", function () {
      eliminarRecordatorioActual();
    });

    botonExplorar?.addEventListener("click", function () {
      eliminarRecordatorioActual();

      pantallaRecordatorios.classList.remove("mostrar");

      document.getElementById("catalogo")?.scrollIntoView({
        behavior: "smooth"
      });
    });

    trackRecordatorios.appendChild(tarjeta);
  });

  const contador = document.createElement("div");
contador.className = "recordatorios-contador";
contador.innerHTML = `
  <strong id="recordatorioActual">1</strong>
  <span>/</span>
  <span>${recordatorios.length}</span>
`;

const puntos = document.createElement("div");
puntos.className = "recordatorios-puntos";

recordatorios.forEach(function (_, index) {
  const punto = document.createElement("span");
  punto.className =
    "recordatorio-punto" + (index === 0 ? " activo" : "");
  puntos.appendChild(punto);
});

pantallaRecordatorios
  .querySelector(".recordatorios-slider")
  ?.appendChild(contador);

pantallaRecordatorios
  .querySelector(".recordatorios-slider")
  ?.appendChild(puntos);

const tarjetasRecordatorio = [
  ...trackRecordatorios.querySelectorAll(".recordatorio-card")
];

const puntosRecordatorio = [
  ...puntos.querySelectorAll(".recordatorio-punto")
];

function actualizarCarruselRecordatorios() {
  const centro =
    trackRecordatorios.scrollLeft +
    trackRecordatorios.clientWidth / 2;

  let indiceActivo = 0;
  let menorDistancia = Infinity;

  tarjetasRecordatorio.forEach(function (tarjeta, index) {
    const centroTarjeta =
      tarjeta.offsetLeft + tarjeta.offsetWidth / 2;

    const distancia = Math.abs(centro - centroTarjeta);

    if (distancia < menorDistancia) {
      menorDistancia = distancia;
      indiceActivo = index;
    }
  });

  tarjetasRecordatorio.forEach(function (tarjeta, index) {
    tarjeta.classList.toggle(
      "recordatorio-activo",
      index === indiceActivo
    );
  });

  puntosRecordatorio.forEach(function (punto, index) {
    punto.classList.toggle(
      "activo",
      index === indiceActivo
    );
  });

  const actual =
    document.getElementById("recordatorioActual");

  if (actual) {
    actual.textContent = indiceActivo + 1;
  }

  const activa = tarjetasRecordatorio[indiceActivo];

  if (activa) {
    const color =
      getComputedStyle(activa)
        .getPropertyValue("--recordatorio-color")
        .trim() || "#ff2d2d";

    pantallaRecordatorios.style.setProperty(
      "--recordatorio-fondo",
      color
    );
  }
}

trackRecordatorios.addEventListener(
  "scroll",
  actualizarCarruselRecordatorios,
  { passive:true }
);

setTimeout(
  actualizarCarruselRecordatorios,
  120
);

const ayuda = document.getElementById("ayudaRecordatorios");

if (ayuda) {
  ayuda.classList.remove("oculta");
}

  pantallaRecordatorios.classList.add("mostrar");
}

setTimeout(function () {

  const ayuda = document.getElementById("ayudaRecordatorios");

  if (!ayuda) return;

  const track = document.getElementById("recordatoriosTrack");

  function ocultar() {

    ayuda.classList.add("oculta");

    track.removeEventListener("scroll", ocultar);

  }

  track.addEventListener("scroll", ocultar, { passive:true });

},200);

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
  const modalFavorito = document.getElementById("modalFavorito");
  const modalRecomendacionesLista =
  document.getElementById("modalRecomendacionesLista");

  let tarjetaActual = null;

function obtenerRecordatorios() {
  try {
    return JSON.parse(
      localStorage.getItem("pechyRecordatorios")
    ) || [];
  } catch {
    return [];
  }
}

function guardarRecordatorios(recordatorios) {
  localStorage.setItem(
    "pechyRecordatorios",
    JSON.stringify(recordatorios)
  );
}

function actualizarEstadoRecordatorios() {
  const recordatorios = obtenerRecordatorios();

  document.querySelectorAll(".producto-item").forEach(function (card) {
    const nombre = card.dataset.nombre || "";

    const guardado = recordatorios.some(function (item) {
      return item.nombre === nombre;
    });

    card.classList.toggle("card-favorita", guardado);
  });
}

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

  const toast =
document.getElementById("pechyToast");

if(toast){

toast.classList.add("mostrar");

setTimeout(function(){

toast.classList.remove("mostrar");

},2200);

}

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
  ========================== */
  if (contenido) {
    let inicioY = 0;
    let movimientoY = 0;
    let arrastrando = false;

    contenido.addEventListener(
      "touchstart",
      function (e) {
        if (!modal.classList.contains("abierto")) return;

        inicioY = e.touches[0].clientY;
        movimientoY = 0;
        arrastrando = true;

        contenido.style.transition = "none";
      },
      { passive: true }
    );

    contenido.addEventListener(
      "touchmove",
      function (e) {
        if (!arrastrando) return;

        movimientoY = e.touches[0].clientY - inicioY;

        if (movimientoY > 0) {
          contenido.style.transform = `translateY(${movimientoY}px)`;
        }
      },
      { passive: true }
    );

    contenido.addEventListener("touchend", function () {
      if (!arrastrando) return;

      arrastrando = false;

      contenido.style.transition =
        "transform .4s cubic-bezier(.22,.61,.36,1)";

      if (movimientoY > 120) {
        cerrarModal();
      } else {
        contenido.style.transform = "translateY(0)";
      }
    });
  }
});