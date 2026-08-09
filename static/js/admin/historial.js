document.addEventListener("DOMContentLoaded", () => {

    const buscador =
        document.getElementById("historialBuscador");

    const botonesFiltro = [
        ...document.querySelectorAll(
            ".historial-filtro"
        )
    ];

    const registros = [
        ...document.querySelectorAll(
            ".historial-item"
        )
    ];

    const botonesFecha = [
    ...document.querySelectorAll(
        ".historial-fecha"
    )
];

let filtroFechaActivo = "hoy";

    let filtroActivo = "todos";


    function obtenerCategoria(accion) {

    const texto =
        (accion || "")
            .toLowerCase();


    if (
        texto.includes("promoción") ||
        texto.includes("promocion") ||
        texto.includes("promo")
    ) {
        return "promociones";
    }


    if (
        texto.includes("categoría") ||
        texto.includes("categoria")
    ) {
        return "categorias";
    }


    if (
        texto.includes("cartelera") ||
        texto.includes("película") ||
        texto.includes("pelicula") ||
        texto.includes("serie") ||
        texto.includes("estreno") ||
        texto.includes("tendencia")
    ) {
        return "cartelera";
    }


    if (
        texto.includes("configuración") ||
        texto.includes("configuracion") ||
        texto.includes("whatsapp") ||
        texto.includes("ajuste") ||
        texto.includes("sistema")
    ) {
        return "configuracion";
    }


    if (
        texto.includes("producto") ||
        texto.includes("precio") ||
        texto.includes("oferta") ||
        texto.includes("disponible") ||
        texto.includes("agotado") ||
        texto.includes("visible") ||
        texto.includes("oculto") ||
        texto.includes("plan") ||
        texto.includes("netflix") ||
        texto.includes("max") ||
        texto.includes("paramount") ||
        texto.includes("apple tv") ||
        texto.includes("prime") ||
        texto.includes("disney") ||
        texto.includes("spotify") ||
        texto.includes("youtube") ||
        texto.includes("jellyfin") ||
        texto.includes("plex") ||
        texto.includes("iptv") ||
        texto.includes("vix") ||
        texto.includes("dgo")
    ) {
        return "productos";
    }


    return "sistema";

}


    registros.forEach(registro => {

        const accion =
            registro.dataset.accion || "";

        const categoria =
            obtenerCategoria(accion);

            const iconos = {
    productos: "✓",
    promociones: "🏷",
    categorias: "📁",
    cartelera: "🎬",
    configuracion: "⚙",
    sistema: "●"
};

        registro.dataset.categoria =
            categoria;


        const badge =
            registro.querySelector(
                ".historial-badge"
            );

        if (badge) {

            const nombres = {
                productos: "Productos",
                promociones: "Promociones",
                categorias: "Categorías",
                cartelera: "Cartelera",
                configuracion: "Configuración",
                sistema: "Sistema"
            };

            badge.textContent =
                nombres[categoria] || "Sistema";

            badge.classList.add(
                `categoria-${categoria}`
            );

        }

        const icono =
    registro.querySelector(
        ".historial-icono"
    );

if (icono) {

    icono.textContent =
        iconos[categoria] || "●";

    icono.classList.add(
        `icono-${categoria}`
    );

}

    });


    function aplicarFiltros() {

        const busqueda =
            (buscador?.value || "")
                .trim()
                .toLowerCase();

        let visibles = 0;


        registros.forEach(registro => {

            const accion =
                registro.dataset.accion || "";

            const fecha =
                (registro.dataset.fecha || "")
                    .toLowerCase();

            const categoria =
                registro.dataset.categoria ||
                "sistema";

                const fechaTexto =
    registro.dataset.fecha || "";

const fechaRegistro =
    new Date(
        fechaTexto.replace(" ", "T")
    );

const ahora =
    new Date();

let coincideFecha = true;


if (filtroFechaActivo === "hoy") {

    coincideFecha =
        fechaRegistro.getFullYear() ===
            ahora.getFullYear() &&

        fechaRegistro.getMonth() ===
            ahora.getMonth() &&

        fechaRegistro.getDate() ===
            ahora.getDate();

}


if (
    filtroFechaActivo === "7" ||
    filtroFechaActivo === "30"
) {

    const dias =
        Number(filtroFechaActivo);

    const limite =
        new Date();

    limite.setDate(
        limite.getDate() - dias
    );

    coincideFecha =
        fechaRegistro >= limite;

}

            const coincideBusqueda =
                accion.includes(busqueda) ||
                fecha.includes(busqueda);

            const coincideFiltro =
                filtroActivo === "todos" ||
                categoria === filtroActivo;

            const mostrar =
    coincideBusqueda &&
    coincideFiltro &&
    coincideFecha;

            registro.style.display =
                mostrar
                    ? "grid"
                    : "none";

            if (mostrar) {
                visibles++;
            }

        });


        let mensajeVacio =
            document.getElementById(
                "historialSinResultados"
            );


        if (visibles === 0) {

            if (!mensajeVacio) {

                mensajeVacio =
                    document.createElement("div");

                mensajeVacio.id =
                    "historialSinResultados";

                mensajeVacio.className =
                    "historial-vacio";

                mensajeVacio.innerHTML = `
                    <div class="historial-vacio-icono">
                        🔎
                    </div>

                    <h2>
                        No encontramos movimientos
                    </h2>

                    <p>
                        Prueba con otra palabra
                        o cambia el filtro seleccionado.
                    </p>
                `;

                const lista =
                    document.getElementById(
                        "historialLista"
                    );

                lista?.appendChild(
                    mensajeVacio
                );

            }

            mensajeVacio.style.display =
                "flex";

        } else if (mensajeVacio) {

            mensajeVacio.style.display =
                "none";

        }

    }


    if (buscador) {

        buscador.addEventListener(
            "input",
            aplicarFiltros
        );

    }


    botonesFiltro.forEach(boton => {

        boton.addEventListener(
            "click",
            () => {

                botonesFiltro.forEach(
                    otroBoton => {

                        otroBoton.classList.remove(
                            "activo"
                        );

                    }
                );

                boton.classList.add(
                    "activo"
                );

                filtroActivo =
                    boton.dataset.filtro ||
                    "todos";

                aplicarFiltros();

            }
        );

    });


    aplicarFiltros();


    /* ==========================================
   CARGAR MÁS MOVIMIENTOS
========================================== */

const botonCargarMas =
    document.getElementById(
        "btnCargarMasHistorial"
    );

const listaHistorial =
    document.getElementById(
        "historialLista"
    );


function crearRegistroHistorial(registro) {

    const categoria =
        obtenerCategoria(
            registro.accion
        );

    const nombres = {
        productos: "Productos",
        promociones: "Promociones",
        categorias: "Categorías",
        cartelera: "Cartelera",
        configuracion: "Configuración",
        sistema: "Sistema"
    };

    const iconos = {
    productos: "✓",
    promociones: "🏷",
    categorias: "📁",
    cartelera: "🎬",
    configuracion: "⚙",
    sistema: "●"
};

    const articulo =
        document.createElement("article");

    articulo.className =
        "historial-item";

    articulo.dataset.accion =
        registro.accion.toLowerCase();

    articulo.dataset.fecha =
        registro.fecha;

    articulo.dataset.categoria =
        categoria;

    articulo.innerHTML = `

        <div class="historial-item-actividad">

            <div class="historial-icono">
                ✓
            </div>

            <div>

                <strong>
                    ${registro.accion}
                </strong>

                <small>
                    Movimiento registrado en el sistema
                </small>

            </div>

        </div>


        <div class="historial-item-categoria">

            <span
                class="
                    historial-badge
                    categoria-${categoria}
                ">

                ${nombres[categoria] || "Sistema"}

            </span>

        </div>


        <div class="historial-item-fecha">

            <strong>
                ${registro.fecha}
            </strong>

            <small>
                Registro guardado
            </small>

        </div>
    `;

    return articulo;

}


if (
    botonCargarMas &&
    listaHistorial
) {

    botonCargarMas.addEventListener(
        "click",
        async () => {

            const offset =
                Number(
                    botonCargarMas.dataset.offset || 0
                );

            botonCargarMas.disabled = true;

            botonCargarMas.innerHTML =
                "Cargando movimientos...";


            try {

                const respuesta =
                    await fetch(
                        `/admin/historial/cargar-mas?offset=${offset}`
                    );

                const datos =
                    await respuesta.json();


                if (
                    !respuesta.ok ||
                    !datos.ok
                ) {

                    throw new Error(
                        datos.mensaje ||
                        "No se pudieron cargar los movimientos."
                    );

                }


                datos.registros.forEach(
                    registro => {

                        const articulo =
                            crearRegistroHistorial(
                                registro
                            );

                        listaHistorial.appendChild(
                            articulo
                        );

                        registros.push(
                            articulo
                        );

                    }
                );


                const nuevoOffset =
                    offset +
                    datos.registros.length;

                botonCargarMas.dataset.offset =
                    nuevoOffset;


                if (
                    datos.registros.length < 15
                ) {

                    botonCargarMas.textContent =
                        "No hay más movimientos";

                    botonCargarMas.disabled = true;

                } else {

                    botonCargarMas.innerHTML = `
                        Cargar más movimientos
                        <span>⌄</span>
                    `;

                    botonCargarMas.disabled = false;

                }


                aplicarFiltros();

            } catch (error) {

                console.error(error);

                botonCargarMas.innerHTML = `
                    Reintentar
                    <span>⌄</span>
                `;

                botonCargarMas.disabled = false;

                alert(
                    "No se pudieron cargar más movimientos."
                );

            }

        }
    );

}

botonesFecha.forEach(boton => {

    boton.addEventListener(
        "click",
        () => {

            botonesFecha.forEach(
                otroBoton => {

                    otroBoton.classList.remove(
                        "activo"
                    );

                }
            );

            boton.classList.add(
                "activo"
            );

            filtroFechaActivo =
                boton.dataset.fecha ||
                "todos";

            aplicarFiltros();

        }
    );

});

/* ==========================================
   RESUMEN DINÁMICO DEL HISTORIAL
========================================== */

const contadorCriticos =
    document.getElementById(
        "historialCambiosCriticos"
    );

const ultimaActividadElemento =
    document.getElementById(
        "historialUltimaActividad"
    );


function contarCambiosCriticos() {

    const palabrasCriticas = [
        "agotado",
        "eliminado",
        "eliminada",
        "oculto",
        "oculta",
        "desactivado",
        "desactivada",
        "error",
        "fallo"
    ];

    const totalCriticos =
        registros.filter(registro => {

            const accion =
                registro.dataset.accion || "";

            return palabrasCriticas.some(
                palabra =>
                    accion.includes(palabra)
            );

        }).length;

    if (contadorCriticos) {

        contadorCriticos.textContent =
            totalCriticos;

    }

}


function obtenerTiempoRelativo(fechaTexto) {

    if (!fechaTexto) {
        return "Sin actividad";
    }

    const fecha =
        new Date(
            fechaTexto.replace(" ", "T")
        );

    if (Number.isNaN(fecha.getTime())) {
        return fechaTexto;
    }

    const ahora =
        new Date();

    const diferencia =
        ahora - fecha;

    const minutos =
        Math.floor(
            diferencia / 60000
        );

    if (minutos < 1) {
        return "Ahora mismo";
    }

    if (minutos < 60) {
        return `Hace ${minutos} min`;
    }

    const horas =
        Math.floor(
            minutos / 60
        );

    if (horas < 24) {
        return `Hace ${horas} h`;
    }

    const dias =
        Math.floor(
            horas / 24
        );

    if (dias === 1) {
        return "Ayer";
    }

    if (dias < 30) {
        return `Hace ${dias} días`;
    }

    return fechaTexto;

}


function actualizarUltimaActividad() {

    if (!ultimaActividadElemento) {
        return;
    }

    const fechaTexto =
        ultimaActividadElemento.dataset.fecha || "";

    ultimaActividadElemento.textContent =
        obtenerTiempoRelativo(
            fechaTexto
        );

}


contarCambiosCriticos();
actualizarUltimaActividad();

setInterval(
    actualizarUltimaActividad,
    60000
);


/* ==========================================
   VER TODO EL HISTORIAL
========================================== */

const botonVerTodo =
    document.getElementById(
        "btnVerTodoHistorial"
    );

if (botonVerTodo) {

    botonVerTodo.addEventListener(
        "click",
        () => {

            filtroFechaActivo = "todos";
            filtroActivo = "todos";

            if (buscador) {
                buscador.value = "";
            }

            botonesFiltro.forEach(
                boton => {

                    boton.classList.toggle(
                        "activo",
                        boton.dataset.filtro === "todos"
                    );

                }
            );

            botonesFecha.forEach(
                boton => {

                    boton.classList.toggle(
                        "activo",
                        boton.dataset.fecha === "todos"
                    );

                }
            );

            aplicarFiltros();

            document
                .querySelector(".historial-tabla-card")
                ?.scrollIntoView({
                    behavior: "smooth",
                    block: "start"
                });

        }
    );

}

const contenedorFiltros =
    document.querySelector(
        ".historial-filtros"
    );

if (contenedorFiltros) {

    contenedorFiltros.scrollLeft = 0;

}

});