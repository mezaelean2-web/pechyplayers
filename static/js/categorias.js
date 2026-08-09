document.addEventListener("DOMContentLoaded", function () {
  if (window.innerWidth > 768) return;

  const PLATAFORMAS = {

    netflix:{
        color:"#e50914",
        posicion:"center 14%"
    },

    disney:{
        color:"#1464f4",
        posicion:"center 24%"
    },

    max:{
        color:"#7c3aed",
        posicion:"center 10%"
    },

    prime:{
        color:"#00a8e1",
        posicion:"center 8%"
    },

    paramount:{
        color:"#2563eb",
        posicion:"center 18%"
    },

    spotify:{
        color:"#1db954",
        posicion:"center center"
    },

    youtube:{
        color:"#ff0000",
        posicion:"center center"
    },

    iptv:{
        color:"#ff7a00",
        posicion:"center center"
    },

    plex:{
        color:"#e5a800",
        posicion:"center center"
    },

    vix:{
        color:"#ff6a00",
        posicion:"center 18%"
    },

    crunchyroll:{
        color:"#f47521",
        posicion:"center 18%"
    },

    directv:{
        color:"#00a6ff",
        posicion:"center center"
    },

    dgo:{
        color:"#00a6ff",
        posicion:"center center"
    },

    jellyfin:{
        color:"#aa5cc3",
        posicion:"center center"
    }

};


function obtenerConfiguracion(nombre){

    nombre=(nombre||"").toLowerCase();

    for(const plataforma in PLATAFORMAS){

        if(nombre.includes(plataforma)){

            return PLATAFORMAS[plataforma];

        }

    }

    return{

        color:"#ff2d2d",

        posicion:"center center"

    };

}

  function iniciarCarruselCategoria(
    sliderId,
    contadorId,
    puntosId
  ) {
    const slider = document.getElementById(sliderId);

    if (!slider) return;

    const seccion = slider.closest(".categoria-home");

    const tarjetas = [
      ...slider.querySelectorAll(".producto-item")
    ];

    if (tarjetas.length === 0) return;

    
    tarjetas.forEach(function (tarjeta) {

    const nombre = tarjeta.dataset.nombre || "";

    const config = obtenerConfiguracion(nombre);

    tarjeta.style.setProperty(
        "--color-plataforma",
        config.color
    );

    const imagen =
        tarjeta.querySelector(".cover-img");

    if (imagen) {
        imagen.style.objectPosition =
            config.posicion;
    }

});

    function actualizar() {
      const rectSlider = slider.getBoundingClientRect();

      const centroSlider =
        rectSlider.left + rectSlider.width / 2;

      let indiceActivo = 0;
      let menorDistancia = Infinity;

      tarjetas.forEach(function (tarjeta, index) {
        const rectTarjeta =
          tarjeta.getBoundingClientRect();

        const centroTarjeta =
          rectTarjeta.left + rectTarjeta.width / 2;

        const distancia =
          Math.abs(centroSlider - centroTarjeta);

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

      if (activa && seccion) {
        const color =
          getComputedStyle(activa)
            .getPropertyValue("--color-plataforma")
            .trim() || "#ff2d2d";

        seccion.style.setProperty(
          "--categoria-color",
          color
        );
      }

      const contador =
        document.getElementById(contadorId);

      if (contador) {
        contador.textContent = indiceActivo + 1;
      }

      const puntosContenedor =
        document.getElementById(puntosId);

      const puntos =
        puntosContenedor?.querySelectorAll(
          ".catalogo-punto"
        );

      puntos?.forEach(function (punto, index) {
        punto.classList.toggle(
          "activo",
          index === indiceActivo
        );
      });
    }

    slider.addEventListener(
      "scroll",
      actualizar,
      { passive: true }
    );

    window.addEventListener(
      "resize",
      actualizar
    );

    setTimeout(actualizar, 150);
  }

  document
  .querySelectorAll(".categoria-home")
  .forEach(function (seccion) {

    const slider =
      seccion.querySelector(".categoria-slider");

    const contador =
      seccion.querySelector(
        ".catalogo-contador strong"
      );

    const puntos =
      seccion.querySelector(".catalogo-puntos");

    if (!slider || !contador || !puntos) return;

    iniciarCarruselCategoria(
      slider.id,
      contador.id,
      puntos.id
    );

  });

  /* ==========================================
   ANIMACIÓN AL HACER SCROLL
========================================== */

const seccionesCategorias = [
  ...document.querySelectorAll(".categoria-home")
];

if ("IntersectionObserver" in window) {
  const observadorCategorias =
    new IntersectionObserver(
      function (entradas, observador) {
        entradas.forEach(function (entrada) {
          if (!entrada.isIntersecting) return;

          entrada.target.classList.add(
            "categoria-visible"
          );

          observador.unobserve(entrada.target);
        });
      },
      {
        threshold:0.18,
        rootMargin:"0px 0px -40px 0px"
      }
    );

  seccionesCategorias.forEach(function (seccion) {
    observadorCategorias.observe(seccion);
  });
} else {
  seccionesCategorias.forEach(function (seccion) {
    seccion.classList.add("categoria-visible");
  });
}
/* ==========================================
   MODAL VER TODO POR CATEGORÍA
========================================== */

const categoriasModal =
  document.getElementById("categoriasModal");

const categoriasModalFondo =
  document.getElementById("categoriasModalFondo");

const cerrarCategoriasModal =
  document.getElementById("cerrarCategoriasModal");

const categoriasModalTitulo =
  document.getElementById("categoriasModalTitulo");

const categoriasModalGrid =
  document.getElementById("categoriasModalGrid");


function abrirCategoriasModal(categoria, seccion) {

  if (
    !categoriasModal ||
    !categoriasModalTitulo ||
    !categoriasModalGrid ||
    !seccion
  ) return;

  const tarjetas =
    seccion.querySelectorAll(
      ".categoria-slider .producto-item"
    );

  categoriasModalTitulo.textContent =
    categoria;

  categoriasModalGrid.innerHTML = "";

  tarjetas.forEach(function (tarjeta) {

    const imagen =
      tarjeta.querySelector(".cover-img");

    const nombre =
      tarjeta.querySelector(".cover-overlay h3");

    const planes =
      tarjeta.querySelector(".plans");

    const enlace =
      tarjeta.querySelector(".buy");

    const nombreProducto =
  nombre
    ? nombre.textContent.trim()
    : "Producto";

const config =
obtenerConfiguracion(nombreProducto);

const colorProducto =
config.color;

const posicionImagen =
config.posicion;


const miniTarjeta =
  document.createElement("article");

miniTarjeta.className =
  "categoria-modal-producto";

miniTarjeta.style.setProperty(
  "--color-producto",
  colorProducto
);

miniTarjeta.innerHTML = `

  <div class="categoria-modal-imagen">

    ${
      imagen
        ? `
          <img
            src="${imagen.src}"
            alt="${nombreProducto}"
            style="object-position:${posicionImagen};"
          >
        `
        : ""
    }

    <div class="categoria-modal-imagen-sombra"></div>

  </div>

  <div class="categoria-modal-info">

    <h3>
      ${nombreProducto}
    </h3>

    <div class="categoria-modal-linea"></div>

    <div class="categoria-modal-planes">
      ${planes ? planes.innerHTML : ""}
    </div>

    <a
      class="categoria-modal-comprar"
      href="${enlace ? enlace.href : "#"}"
      target="_blank"
    >
      💬 Comprar
    </a>

  </div>
`;

categoriasModalGrid.appendChild(
  miniTarjeta
);

  });

  categoriasModal.classList.add(
    "modal-activo"
  );

  document.body.classList.add(
    "modal-categorias-abierto"
  );

}


function cerrarModalCategorias() {

  if (!categoriasModal) return;

  categoriasModal.classList.remove(
    "modal-activo"
  );

  document.body.classList.remove(
    "modal-categorias-abierto"
  );

}


document
  .querySelectorAll(".categoria-ver-todo")
  .forEach(function (boton) {

    boton.addEventListener(
      "click",
      function () {

        const categoria =
          boton.dataset.categoria;

        const seccion =
          boton.closest(".categoria-home");

        abrirCategoriasModal(
          categoria,
          seccion
        );

      }
    );

  });


if (cerrarCategoriasModal) {

  cerrarCategoriasModal.addEventListener(
    "click",
    cerrarModalCategorias
  );

}


if (categoriasModalFondo) {

  categoriasModalFondo.addEventListener(
    "click",
    cerrarModalCategorias
  );

}


document.addEventListener(
  "keydown",
  function (evento) {

    if (evento.key === "Escape") {
      cerrarModalCategorias();
    }
  }
);
  });