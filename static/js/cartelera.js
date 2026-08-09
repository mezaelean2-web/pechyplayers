document.addEventListener("DOMContentLoaded", () => {

    if (window.innerWidth > 768) return;

    const lista = document.getElementById("carteleraLista");

    if (!lista) return;

    const tarjetas = [...lista.querySelectorAll(".cartelera-card")];
    const botones = [...document.querySelectorAll(".categoria-btn")];


    const barraCategorias = document.querySelector(
    ".cartelera-categorias-scroll"
);

let timerCategorias;

    const mapa = {};

    tarjetas.forEach(card => {

        const categoria = (card.dataset.categoria || "")
            .trim()
            .toLowerCase();

        if (!categoria) return;

        if (!mapa[categoria]) {
            mapa[categoria] = card;
        }

    });

    function activarBoton(categoria){

    botones.forEach(btn=>{

        const activa =
            btn.dataset.categoria===categoria;

        btn.classList.toggle(
            "activa",
            activa
        );

        if(activa){

            btn.scrollIntoView({

                behavior:"smooth",

                inline:"center",

                block:"nearest"

            });

        }

    });

}

    botones.forEach(btn=>{

        btn.addEventListener("click",()=>{

            const categoria = btn.dataset.categoria;

            const card = mapa[categoria];

            if(!card){

                console.log("Sin contenido:",categoria);

                return;

            }

            lista.scrollTo({

                left:
                    card.offsetLeft -
                    (lista.clientWidth-card.offsetWidth)/2,

                behavior:"smooth"

            });


            setTimeout(() => {

    detectarCategoria();

}, 350);

        

        });

    });

    function detectarCategoria(){

        const centro =
            lista.scrollLeft +
            lista.clientWidth/2;

        let activa=null;
        let menor=Infinity;

        tarjetas.forEach(card=>{

            const cardCentro =
                card.offsetLeft +
                card.offsetWidth/2;

            const distancia =
                Math.abs(cardCentro-centro);

            if(distancia<menor){

                menor=distancia;

                activa=card.dataset.categoria;

            }

        });

        if(activa){

            activarBoton(activa);

        }

    }

    lista.addEventListener(
        "scroll",
        detectarCategoria,
        {passive:true}
    );

    detectarCategoria();

    barraCategorias.addEventListener(
    "scroll",
    () => {

        clearTimeout(timerCategorias);

        timerCategorias = setTimeout(() => {

            const centro =
                barraCategorias.scrollLeft +
                barraCategorias.clientWidth / 2;

            let botonActivo = null;
            let menor = Infinity;

            botones.forEach(btn => {

                const x =
                    btn.offsetLeft +
                    btn.offsetWidth / 2;

                const d =
                    Math.abs(centro - x);

                if (d < menor) {

                    menor = d;
                    botonActivo = btn;

                }

            });

            if (!botonActivo) return;

            const categoria =
                botonActivo.dataset.categoria;

            const card = mapa[categoria];

            if (!card) return;

            lista.scrollTo({

                left:
                    card.offsetLeft -
                    (lista.clientWidth - card.offsetWidth) / 2,

                behavior: "smooth"

            });

        }, 120);

    },
    { passive: true }
);

/* ==========================================
   MODAL CARTELERA
========================================== */

const carteleraModal =
    document.getElementById("carteleraModal");

const cerrarCarteleraModal =
    document.getElementById("cerrarCarteleraModal");

const fondoCarteleraModal =
    document.getElementById("carteleraModalFondo");

const banner =
    document.getElementById("carteleraModalBanner");

const titulo =
    document.getElementById("carteleraModalTitulo");

const detalles =
    document.getElementById("carteleraModalDetalles");

const descripcion =
    document.getElementById("carteleraModalDescripcion");

const plataformas =
    document.getElementById("carteleraModalPlataformas");

const badges =
    document.getElementById("carteleraModalBadges");

const botonVerAhora =
    document.getElementById("carteleraModalVerAhora");

document.querySelectorAll(".cartelera-ver").forEach(btn=>{

    btn.addEventListener("click",()=>{

        banner.src = btn.dataset.banner;

        titulo.textContent =
            btn.dataset.titulo;

        detalles.textContent =
    `${btn.dataset.anio} • ${btn.dataset.genero}`;

        descripcion.textContent =
    btn.dataset.descripcion ||
    "Próximamente tendremos una descripción completa de esta película.";

        plataformas.innerHTML="";

        badges.innerHTML="";

        btn.dataset.plataformas
            .split(",")

            .forEach(plataforma=>{

                const span =
                    document.createElement("span");

                span.className =
                    "cartelera-plataforma";

                span.textContent =
                    plataforma.trim();

                plataformas.appendChild(span);

            });

            if(btn.dataset.tendencia=="1"){

    badges.innerHTML += `
        <span class="cartelera-modal-badge tendencia">
            🔥 Tendencia
        </span>
    `;

}

const url = btn.dataset.url || "";


if (url) {

    botonVerAhora.href = url;
    botonVerAhora.style.display = "flex";

} else {

    botonVerAhora.removeAttribute("href");
    botonVerAhora.style.display = "none";

}

if(btn.dataset.destacado=="1"){

    badges.innerHTML += `
        <span class="cartelera-modal-badge destacado">
            ⭐ Destacada
        </span>
    `;

}

        carteleraModal.classList.add(
            "activo"
        );

        document.body.style.overflow =
            "hidden";

    });

});

function cerrarModalCartelera(){

    carteleraModal.classList.remove(
        "activo"
    );

    document.body.style.overflow =
        "";

}

cerrarCarteleraModal.addEventListener(
    "click",
    cerrarModalCartelera
);

fondoCarteleraModal.addEventListener(
    "click",
    cerrarModalCartelera
);

});





const carrusel = new InfiniteCarousel({

    lista: "#carteleraLista",

    item: ".cartelera-card"

});

carrusel.init();