/* ==========================================
   PECHY PLAYERS
   MODAL PREMIUM
========================================== */

(function () {
  const recomendaciones = {
    netflix: {
      titulo: "Completa tu entretenimiento",
      texto: "Combina Netflix con Disney Premium y disfruta todavía más contenido.",
      buscar: "disney"
    },

    disney: {
      titulo: "También te puede gustar",
      texto: "MAX Premium es una excelente opción para complementar Disney.",
      buscar: "max"
    },

    max: {
      titulo: "Sigue ampliando tu catálogo",
      texto: "Prime Video combina muy bien con MAX para películas y series.",
      buscar: "prime"
    },

    prime: {
      titulo: "Una opción recomendada",
      texto: "Paramount+ puede complementar tu suscripción de Prime Video.",
      buscar: "paramount"
    },

    iptv: {
      titulo: "Más entretenimiento y deportes",
      texto: "Disney Premium es una buena alternativa para acompañar tu IPTV.",
      buscar: "disney"
    },

    directv: {
      titulo: "Complementa tus deportes",
      texto: "Disney Premium puede darte más opciones de entretenimiento.",
      buscar: "disney"
    },

    paramount: {
      titulo: "Completa tu experiencia",
      texto: "Prime Video es una excelente opción para acompañar Paramount+.",
      buscar: "prime"
    },

    spotify: {
      titulo: "También puede interesarte",
      texto: "YouTube Premium es una gran opción para música y videos sin anuncios.",
      buscar: "youtube"
    },

    youtube: {
      titulo: "Más música y entretenimiento",
      texto: "Spotify Premium puede complementar tu experiencia.",
      buscar: "spotify"
    },

    default: {
      titulo: "Descubre otra plataforma",
      texto: "Explora una opción adicional y encuentra más contenido para disfrutar.",
      buscar: "netflix"
    }
  };

  function obtenerRecomendacion(nombreProducto) {
    const nombre = (nombreProducto || "").toLowerCase();

    for (const plataforma in recomendaciones) {
      if (
        plataforma !== "default" &&
        nombre.includes(plataforma)
      ) {
        return recomendaciones[plataforma];
      }
    }

    return recomendaciones.default;
  }

  function actualizarOfertaInteligente(nombreProducto) {
    const titulo =
      document.getElementById("ofertaInteligenteTitulo");

    const texto =
      document.getElementById("ofertaInteligenteTexto");

    const boton =
      document.getElementById("ofertaInteligenteBoton");

    const seccion =
      document.getElementById("modalOfertaInteligente");

    if (!titulo || !texto || !boton || !seccion) return;

    const recomendacion =
      obtenerRecomendacion(nombreProducto);

    titulo.textContent = recomendacion.titulo;
    texto.textContent = recomendacion.texto;

    const tarjetas = [
      ...document.querySelectorAll(".producto-item")
    ];

    const tarjetaRecomendada = tarjetas.find(function (card) {
      const nombre = card.dataset.nombre || "";
      return nombre.includes(recomendacion.buscar);
    });

    if (!tarjetaRecomendada) {
      seccion.style.display = "none";
      return;
    }

    seccion.style.display = "";

    const nombreRecomendado =
      tarjetaRecomendada.querySelector(".cover-overlay h3")
        ?.textContent.trim() || "Ver recomendación";

    boton.textContent =
      `Ver ${nombreRecomendado} →`;

    boton.onclick = function () {
      const portada =
        tarjetaRecomendada.querySelector(".cover");

      const contenidoModal =
        document.querySelector(".producto-modal-contenido");

      contenidoModal?.scrollTo({
        top: 0,
        behavior: "smooth"
      });

      portada?.click();
    };
  }

  window.actualizarOfertaInteligente =
    actualizarOfertaInteligente;
})();