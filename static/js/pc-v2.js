/* ==========================================
   PECHY PLAYERS
   HERO PC CON COLOR DINÁMICO
========================================== */

document.addEventListener("DOMContentLoaded", function () {
  if (window.innerWidth <= 768) return;

  const hero = document.querySelector(".hero-pc-v2");

  const tarjetas = [
    ...document.querySelectorAll(".hero-pc-logo")
  ];

  if (!hero || tarjetas.length === 0) return;

  function cambiarColor(tarjeta) {
    const color =
      tarjeta.dataset.color || "#e50914";

    hero.style.setProperty(
      "--hero-color",
      color
    );

    tarjetas.forEach(function (item) {
      item.classList.toggle(
        "hero-activa",
        item === tarjeta
      );
    });
  }

  tarjetas.forEach(function (tarjeta) {
    tarjeta.addEventListener("mouseenter", function () {
      cambiarColor(tarjeta);
    });

    tarjeta.addEventListener("click", function () {
      cambiarColor(tarjeta);
    });
  });

  cambiarColor(tarjetas[0]);
});
/* ==========================================
   COLORES DEL CATÁLOGO EN PC
========================================== */

document.addEventListener("DOMContentLoaded", function () {
  if (window.innerWidth <= 768) return;

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

  document
    .querySelectorAll("#productosGrid .producto-item")
    .forEach(function (tarjeta) {
      const nombre = tarjeta.dataset.nombre || "";
      const color = obtenerColor(nombre);

      tarjeta.style.setProperty(
        "--catalogo-color",
        color
      );
    });
});