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

const esMovilPromociones = window.innerWidth <= 768;

if (promoTrack && promoSlides.length > 0 && !esMovilPromociones) {
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
const productosGridMovil = document.getElementById("productosGrid");
const tarjetasMovil = document.querySelectorAll(".producto-item");
const contadorActual = document.getElementById("catalogoActual");
const puntosCatalogo = document.querySelectorAll(".catalogo-punto");

function actualizarCarruselMovil() {
  if (window.innerWidth > 768 || !productosGridMovil || tarjetasMovil.length === 0) {
    return;
  }

  const centro = productosGridMovil.scrollLeft + productosGridMovil.clientWidth / 2;

  let indiceActivo = 0;
  let menorDistancia = Infinity;

  tarjetasMovil.forEach((tarjeta, index) => {
    const centroTarjeta = tarjeta.offsetLeft + tarjeta.offsetWidth / 2;
    const distancia = Math.abs(centro - centroTarjeta);

    if (distancia < menorDistancia) {
      menorDistancia = distancia;
      indiceActivo = index;
    }
  });

  tarjetasMovil.forEach((tarjeta, index) => {
    tarjeta.classList.toggle("card-activa", index === indiceActivo);
  });

  if (contadorActual) {
    contadorActual.textContent = indiceActivo + 1;
  }

  puntosCatalogo.forEach((punto, index) => {
    punto.classList.toggle("activo", index === indiceActivo);
  });
}

if (productosGridMovil) {
  productosGridMovil.addEventListener("scroll", actualizarCarruselMovil, {
    passive: true
  });

  window.addEventListener("resize", actualizarCarruselMovil);

  setTimeout(actualizarCarruselMovil, 150);
}
/* ==========================================
   CARRUSEL DE PROMOCIONES EN PC
========================================== */

document.addEventListener("DOMContentLoaded", function () {
  if (window.innerWidth <= 768) return;

  const track = document.getElementById("promoTrack");
  const anterior = document.getElementById("promoPcAnterior");
  const siguiente = document.getElementById("promoPcSiguiente");
  const contador = document.getElementById("promocionActual");

  if (!track || !anterior || !siguiente) return;

  function obtenerTarjetas() {
    return [...track.querySelectorAll(".promo-card")];
  }

  function obtenerIndiceActual() {
    const tarjetas = obtenerTarjetas();

    if (tarjetas.length === 0) return 0;

    let indice = 0;
    let distanciaMenor = Infinity;

    tarjetas.forEach(function (tarjeta, posicion) {
      const distancia =
        Math.abs(tarjeta.offsetLeft - track.scrollLeft);

      if (distancia < distanciaMenor) {
        distanciaMenor = distancia;
        indice = posicion;
      }
    });

    return indice;
  }

  function moverPromocion(direccion) {
    const tarjetas = obtenerTarjetas();

    if (tarjetas.length === 0) return;

    const actual = obtenerIndiceActual();

    let nuevoIndice = actual + direccion;

    if (nuevoIndice < 0) {
      nuevoIndice = tarjetas.length - 1;
    }

    if (nuevoIndice >= tarjetas.length) {
      nuevoIndice = 0;
    }

    track.scrollTo({
      left: tarjetas[nuevoIndice].offsetLeft,
      behavior: "smooth"
    });
  }

  function actualizarEstado() {
    const tarjetas = obtenerTarjetas();
    const indice = obtenerIndiceActual();

    if (contador) {
      contador.textContent = indice + 1;
    }

    document
      .querySelectorAll(".promocion-punto")
      .forEach(function (punto, posicion) {
        punto.classList.toggle(
          "activo",
          posicion === indice
        );
      });
  }

  anterior.addEventListener("click", function () {
    moverPromocion(-1);
  });

  siguiente.addEventListener("click", function () {
    moverPromocion(1);
  });

  track.addEventListener(
    "scroll",
    actualizarEstado,
    { passive:true }
  );

  setTimeout(actualizarEstado, 150);
});