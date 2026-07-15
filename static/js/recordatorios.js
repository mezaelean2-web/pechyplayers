/* ==========================================
   PECHY PLAYERS
   SISTEMA DE RECORDATORIOS
========================================== */

(function () {
  const CLAVE_RECORDATORIOS = "pechyRecordatorios";

  function obtenerRecordatorios() {
    try {
      return JSON.parse(
        localStorage.getItem(CLAVE_RECORDATORIOS)
      ) || [];
    } catch (error) {
      console.error("No se pudieron leer los recordatorios:", error);
      return [];
    }
  }

  function guardarRecordatorios(recordatorios) {
    localStorage.setItem(
      CLAVE_RECORDATORIOS,
      JSON.stringify(recordatorios)
    );
  }

  function actualizarEstadoRecordatorios() {
    const recordatorios = obtenerRecordatorios();

    document
      .querySelectorAll(".producto-item")
      .forEach(function (card) {
        const nombre = card.dataset.nombre || "";

        const guardado = recordatorios.some(function (item) {
          return item.nombre === nombre;
        });

        card.classList.toggle("card-favorita", guardado);
      });
  }

  function mostrarPantallaRecordatorios() {
    const pantalla =
      document.getElementById("recordatoriosScreen");

    const track =
      document.getElementById("recordatoriosTrack");

    if (!pantalla || !track) return;

    const recordatorios = obtenerRecordatorios();

    if (recordatorios.length === 0) {
      pantalla.classList.remove("mostrar");
      return;
    }

    track.innerHTML = "";

    pantalla
      .querySelector(".recordatorios-contador")
      ?.remove();

    pantalla
      .querySelector(".recordatorios-puntos")
      ?.remove();

    recordatorios.forEach(function (item) {
      const tarjeta = document.createElement("article");

      tarjeta.className = "recordatorio-card";

      tarjeta.style.setProperty(
        "--recordatorio-color",
        item.color || "#ff2d2d"
      );

      const planesHTML = (item.planes || [])
        .map(function (plan) {
          return `
            <div class="recordatorio-plan">
              ${plan}
            </div>
          `;
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
        const nuevos = obtenerRecordatorios().filter(
          function (guardado) {
            return guardado.nombre !== item.nombre;
          }
        );

        guardarRecordatorios(nuevos);
        actualizarEstadoRecordatorios();
      }

      botonComprar?.addEventListener("click", function () {
        eliminarRecordatorioActual();
      });

      botonExplorar?.addEventListener("click", function () {
        eliminarRecordatorioActual();

        pantalla.classList.remove("mostrar");

        document.getElementById("catalogo")?.scrollIntoView({
          behavior: "smooth"
        });
      });

      track.appendChild(tarjeta);
    });

    crearContadorYPuntos(
      pantalla,
      track,
      recordatorios.length
    );

    configurarFlecha(pantalla, track);

    pantalla.classList.add("mostrar");
  }

  function crearContadorYPuntos(
    pantalla,
    track,
    totalRecordatorios
  ) {
    const slider =
      pantalla.querySelector(".recordatorios-slider");

    if (!slider) return;

    const contador = document.createElement("div");

    contador.className = "recordatorios-contador";

    contador.innerHTML = `
      <strong id="recordatorioActual">1</strong>
      <span>/</span>
      <span>${totalRecordatorios}</span>
    `;

    const puntos = document.createElement("div");

    puntos.className = "recordatorios-puntos";

    for (let index = 0; index < totalRecordatorios; index++) {
      const punto = document.createElement("span");

      punto.className =
        "recordatorio-punto" +
        (index === 0 ? " activo" : "");

      puntos.appendChild(punto);
    }

    slider.appendChild(contador);
    slider.appendChild(puntos);

    configurarCarrusel(pantalla, track, puntos);
  }

  function configurarCarrusel(pantalla, track, puntos) {
    const tarjetas = [
      ...track.querySelectorAll(".recordatorio-card")
    ];

    const puntosLista = [
      ...puntos.querySelectorAll(".recordatorio-punto")
    ];

    function actualizarCarrusel() {
      if (tarjetas.length === 0) return;

      const rectTrack = track.getBoundingClientRect();
      const centroTrack =
        rectTrack.left + rectTrack.width / 2;

      let indiceActivo = 0;
      let menorDistancia = Infinity;

      tarjetas.forEach(function (tarjeta, index) {
        const rectTarjeta =
          tarjeta.getBoundingClientRect();

        const centroTarjeta =
          rectTarjeta.left + rectTarjeta.width / 2;

        const distancia =
          Math.abs(centroTrack - centroTarjeta);

        if (distancia < menorDistancia) {
          menorDistancia = distancia;
          indiceActivo = index;
        }
      });

      tarjetas.forEach(function (tarjeta, index) {
        tarjeta.classList.toggle(
          "recordatorio-activo",
          index === indiceActivo
        );
      });

      puntosLista.forEach(function (punto, index) {
        punto.classList.toggle(
          "activo",
          index === indiceActivo
        );
      });

      const contadorActual =
        document.getElementById("recordatorioActual");

      if (contadorActual) {
        contadorActual.textContent = indiceActivo + 1;
      }

      const tarjetaActiva = tarjetas[indiceActivo];

      if (tarjetaActiva) {
        const color =
          getComputedStyle(tarjetaActiva)
            .getPropertyValue("--recordatorio-color")
            .trim() || "#ff2d2d";

        pantalla.style.setProperty(
          "--recordatorio-fondo",
          color
        );
      }
    }

    track.addEventListener(
      "scroll",
      actualizarCarrusel,
      { passive: true }
    );

    requestAnimationFrame(function () {
      requestAnimationFrame(actualizarCarrusel);
    });
  }

  function configurarFlecha(pantalla, track) {
    const flecha =
      document.getElementById("flechaRecordatorios");

    if (!flecha) return;

    flecha.classList.remove("oculta");

    function ocultarFlecha() {
      if (track.scrollLeft < 10) return;

      flecha.classList.add("oculta");

      track.removeEventListener(
        "scroll",
        ocultarFlecha
      );
    }

    track.addEventListener(
      "scroll",
      ocultarFlecha,
      { passive: true }
    );
  }

  /* Estas funciones quedan disponibles para mobile.js */
  window.obtenerRecordatorios = obtenerRecordatorios;
  window.guardarRecordatorios = guardarRecordatorios;
  window.actualizarEstadoRecordatorios =
    actualizarEstadoRecordatorios;
  window.mostrarPantallaRecordatorios =
    mostrarPantallaRecordatorios;
})();