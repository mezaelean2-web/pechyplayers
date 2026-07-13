document.addEventListener("DOMContentLoaded", function () {
  if (window.innerWidth > 768) return;

  const colores = {
    netflix: "#e50914",
    disney: "#1464f4",
    max: "#7c3aed",
    prime: "#00a8e1",
    paramount: "#2563eb",
    spotify: "#1db954",
    youtube: "#ff0000",
    iptv: "#ff7a00",
    plex: "#e5a800",
    vix: "#8b2cff",
    crunchyroll: "#f47521",
    directv: "#00a6ff",
    jellyfin: "#aa5cc3"
  };

  function obtenerColor(nombre) {
    const texto = (nombre || "").toLowerCase();

    for (const plataforma in colores) {
      if (texto.includes(plataforma)) {
        return colores[plataforma];
      }
    }

    return "#ff2d2d";
  }

  /* ==========================
     CARRUSEL DEL CATÁLOGO
  ========================== */

  const productosGrid = document.getElementById("productosGrid");

  function iniciarCarruselCatalogo() {
    if (!productosGrid) return;

    const tarjetas = [
      ...productosGrid.querySelectorAll(".producto-item")
    ];

    tarjetas.forEach(function (tarjeta) {
      const nombre = tarjeta.dataset.nombre || "";
      const color = obtenerColor(nombre);

      tarjeta.style.setProperty("--color-plataforma", color);
    });

    function actualizarCatalogo() {
      if (tarjetas.length === 0) return;

      const centro =
        productosGrid.scrollLeft +
        productosGrid.clientWidth / 2;

      let indiceActivo = 0;
      let menorDistancia = Infinity;

      tarjetas.forEach(function (tarjeta, index) {
        const centroTarjeta =
          tarjeta.offsetLeft +
          tarjeta.offsetWidth / 2;

        const distancia =
          Math.abs(centro - centroTarjeta);

        if (distancia < menorDistancia) {
          menorDistancia = distancia;
          indiceActivo = index;
        }
      });

      tarjetas.forEach(function (tarjeta, index) {
        tarjeta.classList.toggle(
          "card-activa",
          index === indiceActivo
        );
      });

      const activa = tarjetas[indiceActivo];

      if (activa) {
        const color =
          getComputedStyle(activa)
            .getPropertyValue("--color-plataforma")
            .trim() || "#ff2d2d";

        document.body.style.setProperty(
          "--fondo-plataforma",
          color
        );
      }

      const contador =
        document.getElementById("catalogoActual");

      if (contador) {
        contador.textContent = indiceActivo + 1;
      }

      document
        .querySelectorAll(".catalogo-punto")
        .forEach(function (punto, index) {
          punto.classList.toggle(
            "activo",
            index === indiceActivo
          );
        });
    }

    productosGrid.addEventListener(
      "scroll",
      actualizarCatalogo,
      { passive: true }
    );

    window.addEventListener(
      "resize",
      actualizarCatalogo
    );

    setTimeout(actualizarCatalogo, 150);
  }

  /* Pequeño empujón para indicar que se puede deslizar */
setTimeout(function () {

  if (productosGrid.scrollWidth <= productosGrid.clientWidth) return;

  productosGrid.scrollTo({
    left: 35,
    behavior: "smooth"
  });

  setTimeout(function () {

    productosGrid.scrollTo({
      left: 0,
      behavior: "smooth"
    });

  }, 450);

}, 700);

  iniciarCarruselCatalogo();

  /* ==========================
     CARRUSEL DE RECORDATORIOS
  ========================== */

  const recordatoriosTrack =
    document.getElementById("recordatoriosTrack");

  const recordatoriosScreen =
    document.getElementById("recordatoriosScreen");

  function iniciarCarruselRecordatorios() {
    if (!recordatoriosTrack || !recordatoriosScreen) return;

    const tarjetas = [
      ...recordatoriosTrack.querySelectorAll(".recordatorio-card")
    ];

    if (tarjetas.length === 0) return;

    tarjetas.forEach(function (tarjeta) {
      const nombre =
        tarjeta.querySelector("h3")
          ?.textContent.trim() || "";

      let color =
        getComputedStyle(tarjeta)
          .getPropertyValue("--recordatorio-color")
          .trim();

      if (!color) {
        color = obtenerColor(nombre);

        tarjeta.style.setProperty(
          "--recordatorio-color",
          color
        );
      }
    });

    function actualizarRecordatorios() {
  const tarjetasActuales = [
    ...recordatoriosTrack.querySelectorAll(".recordatorio-card")
  ];

  if (tarjetasActuales.length === 0) return;

  const rectTrack = recordatoriosTrack.getBoundingClientRect();
  const centroTrack = rectTrack.left + rectTrack.width / 2;

  let indiceActivo = 0;
  let menorDistancia = Infinity;

  tarjetasActuales.forEach(function (tarjeta, index) {
    const rectTarjeta = tarjeta.getBoundingClientRect();
    const centroTarjeta =
      rectTarjeta.left + rectTarjeta.width / 2;

    const distancia =
      Math.abs(centroTrack - centroTarjeta);

    if (distancia < menorDistancia) {
      menorDistancia = distancia;
      indiceActivo = index;
    }
  });

      recordatoriosTrack.addEventListener(
        "scroll",
        actualizarRecordatorios,
        { passive: true }
      );

      recordatoriosTrack.dataset.carruselActivo = "true";
    }

    setTimeout(actualizarRecordatorios, 150);
  }

  setTimeout(function () {

  if (recordatoriosTrack.scrollWidth <= recordatoriosTrack.clientWidth) return;

  recordatoriosTrack.scrollTo({
    left:35,
    behavior:"smooth"
  });

  setTimeout(function(){

    recordatoriosTrack.scrollTo({
      left:0,
      behavior:"smooth"
    });

  },450);

},700);

  /* Detecta cuando mobile.js crea las tarjetas */
  if (recordatoriosTrack) {
    const observer = new MutationObserver(function () {
      iniciarCarruselRecordatorios();
    });

    observer.observe(recordatoriosTrack, {
      childList: true
    });

    iniciarCarruselRecordatorios();
  }
  const ayudaCatalogo =
  document.getElementById("ayudaCatalogo");

const ayudaRecordatorios =
  document.getElementById("ayudaRecordatorios");

function ocultarAyudaAlMover(carrusel, ayuda) {
  if (!carrusel || !ayuda) return;

  let ocultada = false;

  carrusel.addEventListener(
    "scroll",
    function () {
      if (ocultada || carrusel.scrollLeft < 8) return;

      ocultada = true;
      ayuda.classList.add("oculta");

      setTimeout(function () {
        ayuda.remove();
      }, 400);
    },
    { passive:true }
  );
}

ocultarAyudaAlMover(productosGrid, ayudaCatalogo);
ocultarAyudaAlMover(
  document.getElementById("recordatoriosTrack"),
  ayudaRecordatorios
);
});