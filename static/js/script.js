const buscador = document.getElementById("buscador");
const productos = document.querySelectorAll(".producto-item");

buscador.addEventListener("input", () => {
    const texto = buscador.value.toLowerCase();

    productos.forEach(producto => {
        const nombre = producto.dataset.nombre;

        if (nombre.includes(texto)) {
            producto.style.display = "block";
        } else {
            producto.style.display = "none";
        }
    });
});
const promoTrack = document.getElementById("promoTrack");
const promoSlides = document.querySelectorAll(".promo-slide");
const promoAnterior = document.getElementById("promoAnterior");
const promoSiguiente = document.getElementById("promoSiguiente");
const promoPuntos = document.querySelectorAll(".promo-punto");
const promoSlider = document.getElementById("promoSlider");

let promoActual = 0;
let promoTemporizador = null;

function mostrarPromocion(posicion) {
  if (!promoTrack || promoSlides.length === 0) return;

  if (posicion >= promoSlides.length) {
    promoActual = 0;
  } else if (posicion < 0) {
    promoActual = promoSlides.length - 1;
  } else {
    promoActual = posicion;
  }

  promoTrack.style.transform = `translateX(-${promoActual * 100}%)`;

  promoPuntos.forEach((punto, index) => {
    punto.classList.toggle("activo", index === promoActual);
  });
}

function iniciarCarruselPromociones() {
  if (promoSlides.length <= 1) return;

  detenerCarruselPromociones();

  promoTemporizador = setInterval(() => {
    mostrarPromocion(promoActual + 1);
  }, 4500);
}

function detenerCarruselPromociones() {
  if (promoTemporizador) {
    clearInterval(promoTemporizador);
    promoTemporizador = null;
  }
}

if (promoTrack && promoSlides.length > 0) {
  promoSiguiente?.addEventListener("click", () => {
    mostrarPromocion(promoActual + 1);
    iniciarCarruselPromociones();
  });

  promoAnterior?.addEventListener("click", () => {
    mostrarPromocion(promoActual - 1);
    iniciarCarruselPromociones();
  });

  promoPuntos.forEach((punto) => {
    punto.addEventListener("click", () => {
      mostrarPromocion(Number(punto.dataset.posicion));
      iniciarCarruselPromociones();
    });
  });

  promoSlider?.addEventListener("mouseenter", detenerCarruselPromociones);
  promoSlider?.addEventListener("mouseleave", iniciarCarruselPromociones);

  mostrarPromocion(0);
  iniciarCarruselPromociones();
}