document.addEventListener("DOMContentLoaded", () => {

    const boton =
        document.getElementById("btnNuevaPromo");

    const botonSuperior =
        document.getElementById("btnNuevaPromoSuperior");

    const input =
        document.getElementById("promoInput");

    const preview =
        document.getElementById("promoPreviewGrande");

    const placeholder =
        document.getElementById("promoPlaceholder");


    /* PANEL DERECHO */

    const tituloSeleccionada =
        document.getElementById("promoSeleccionadaTitulo");

    const estadoSeleccionada =
        document.getElementById("promoSeleccionadaEstado");

    const botonCambiarEstado =
    document.getElementById("btnCambiarEstadoPromo");

let estadoPendiente = true;

    const botonEditarImagen =
        document.getElementById("btnEditarImagen");

    const botonPublicarSuperior =
        document.getElementById("btnPublicarPromo");

    const botonPublicarLateral =
        document.getElementById("btnPublicarLateral");

        const promoForm =
    document.getElementById("promoForm");

const promoFormId =
    document.getElementById("promoFormId");

    const promoFormActiva =
    document.getElementById("promoFormActiva");

    const botonEliminarPanel =
    document.getElementById("btnEliminarPromo");

const promoEliminarForm =
    document.getElementById("promoEliminarForm");

const promoEliminarId =
    document.getElementById("promoEliminarId");

let promocionSeleccionadaId = null;
let modoEdicion = false;


/* ==========================================
       SELECCIONAR PROMOCIÓN GUARDADA
========================================== */

    document
        .querySelectorAll(".promo-card")
        .forEach(card => {

            card.addEventListener("click", () => {

                const ruta =
                    card.dataset.imagen;

                const id =
                    card.dataset.id;

                    promocionSeleccionadaId = id;
modoEdicion = false;

                const activa =
                    card.dataset.activa === "1";

                    estadoPendiente = activa;


                /* Mostrar imagen */

                preview.src = ruta;

                preview.style.display = "block";

                placeholder.style.display = "none";


                /* Marcar tarjeta seleccionada */

                document
                    .querySelectorAll(".promo-card")
                    .forEach(otraTarjeta => {

                        otraTarjeta.classList.remove(
                            "seleccionada"
                        );

                    });

                card.classList.add("seleccionada");


                /* Actualizar panel derecho */

                if (tituloSeleccionada) {

                    tituloSeleccionada.textContent =
                        `Promoción ${id}`;

                }

                if (estadoSeleccionada) {

                    estadoSeleccionada.textContent =
                        activa
                            ? "● Visible"
                            : "● Oculta";

                    estadoSeleccionada.classList.toggle(
                        "visible",
                        activa
                    );

                    estadoSeleccionada.classList.toggle(
                        "oculta",
                        !activa
                    );

                }

                if (botonCambiarEstado) {

    botonCambiarEstado.disabled = false;

    botonCambiarEstado.textContent =
        activa
            ? "Visible"
            : "Oculta";

    botonCambiarEstado.classList.toggle(
        "oculta",
        !activa
    );

}

                if (botonPublicarSuperior) {
    botonPublicarSuperior.disabled = true;
}

if (botonPublicarLateral) {
    botonPublicarLateral.disabled = true;
}

            });

        });

/* ==========================================
   CAMBIAR ESTADO VISUAL
========================================== */

if (botonCambiarEstado) {

    botonCambiarEstado.addEventListener("click", () => {

        if (!promocionSeleccionadaId) return;

        estadoPendiente = !estadoPendiente;

        botonCambiarEstado.textContent =
            estadoPendiente
                ? "Visible"
                : "Oculta";

        botonCambiarEstado.classList.toggle(
            "oculta",
            !estadoPendiente
        );

        if (estadoSeleccionada) {

            estadoSeleccionada.textContent =
                estadoPendiente
                    ? "● Visible"
                    : "● Oculta";

            estadoSeleccionada.classList.toggle(
                "visible",
                estadoPendiente
            );

            estadoSeleccionada.classList.toggle(
                "oculta",
                !estadoPendiente
            );

        }

        if (botonPublicarSuperior) {
            botonPublicarSuperior.disabled = false;
        }

        if (botonPublicarLateral) {
            botonPublicarLateral.disabled = false;
        }

    });

}


/* ==========================================
   EDITAR IMAGEN SELECCIONADA
========================================== */

if (botonEditarImagen && input) {

    botonEditarImagen.addEventListener("click", () => {

        if (!promocionSeleccionadaId) {

            alert("Primero selecciona una promoción.");

            return;

        }

        modoEdicion = true;

        input.click();

    });

}


    /* ==========================================
       SELECCIONAR IMAGEN NUEVA
    ========================================== */

    if (boton && input) {

        boton.addEventListener("click", () => {

            input.click();

        });

    }

    if (botonSuperior && input) {

        botonSuperior.addEventListener("click", () => {

            input.click();

        });

    }

    if (input && preview && placeholder) {

        input.addEventListener("change", () => {

            const archivo =
                input.files[0];

            if (!archivo) return;

            const reader =
                new FileReader();

            reader.onload = evento => {

    preview.src =
        evento.target.result;

    preview.style.display =
        "block";

    placeholder.style.display =
        "none";


    if (botonPublicarSuperior) {

        botonPublicarSuperior.disabled = false;

    }

    if (botonPublicarLateral) {

        botonPublicarLateral.disabled = false;

    }


    if (modoEdicion && tituloSeleccionada) {

        tituloSeleccionada.textContent =
            `Editando promoción ${promocionSeleccionadaId}`;

    } else if (tituloSeleccionada) {

        tituloSeleccionada.textContent =
            "Nueva promoción";

    }

};

            reader.readAsDataURL(archivo);

        });

    }



/* ==========================================
   ELIMINAR PROMOCIÓN
========================================== */

function eliminarPromocion(id) {

    if (!id || !promoEliminarForm || !promoEliminarId) {
        return;
    }

    const confirmar = window.confirm(
        "¿Seguro que quieres eliminar esta promoción?"
    );

    if (!confirmar) {
        return;
    }

    promoEliminarId.value = id;

    promoEliminarForm.submit();

}


if (botonEliminarPanel) {

    botonEliminarPanel.addEventListener("click", () => {

        if (!promocionSeleccionadaId) {

            alert("Primero selecciona una promoción.");

            return;

        }

        eliminarPromocion(
            promocionSeleccionadaId
        );

    });

}


document
    .querySelectorAll(".btn-eliminar-tarjeta")
    .forEach(boton => {

        boton.addEventListener("click", evento => {

            evento.stopPropagation();

            eliminarPromocion(
                boton.dataset.id
            );

        });

    });




/* ==========================================
   ORDENAR PROMOCIONES
========================================== */

const promoGrid =
    document.querySelector(".promo-grid");

let tarjetaArrastrada = null;


function guardarOrdenPromociones() {

    if (!promoGrid) return;

    const orden = [
        ...promoGrid.querySelectorAll(
            ".promo-card"
        )
    ].map(card => card.dataset.id);

    fetch("/guardar-orden-promociones", {

        method: "POST",

        headers: {
            "Content-Type": "application/json"
        },

        body: JSON.stringify({
            orden: orden
        })

    })
    .then(respuesta => {

        if (!respuesta.ok) {
            throw new Error(
                "No se pudo guardar el orden"
            );
        }

        return respuesta.json();

    })
    .then(datos => {

        if (!datos.ok) {
            throw new Error(
                datos.mensaje ||
                "No se pudo guardar el orden"
            );
        }

        console.log(
            "ORDEN GUARDADO",
            orden
        );

    })
    .catch(error => {

        console.error(error);

        alert(
            "No se pudo guardar el nuevo orden."
        );

    });

}


document
    .querySelectorAll(".promo-card")
    .forEach(card => {

        card.addEventListener(
            "dragstart",
            evento => {

                tarjetaArrastrada = card;

                card.classList.add(
                    "arrastrando"
                );

                evento.dataTransfer.effectAllowed =
                    "move";

                evento.dataTransfer.setData(
                    "text/plain",
                    card.dataset.id
                );

            }
        );


        card.addEventListener(
            "dragend",
            () => {

                card.classList.remove(
                    "arrastrando"
                );

                tarjetaArrastrada = null;

                guardarOrdenPromociones();

            }
        );


        card.addEventListener(
            "dragover",
            evento => {

                evento.preventDefault();

                if (
                    !tarjetaArrastrada ||
                    tarjetaArrastrada === card
                ) {
                    return;
                }

                const rect =
                    card.getBoundingClientRect();

                const mitadHorizontal =
                    rect.left +
                    rect.width / 2;

                const mitadVertical =
                    rect.top +
                    rect.height / 2;

                const columnasIguales =
                    Math.abs(
                        tarjetaArrastrada.offsetTop -
                        card.offsetTop
                    ) < card.offsetHeight / 2;


                if (columnasIguales) {

                    if (
                        evento.clientX <
                        mitadHorizontal
                    ) {

                        promoGrid.insertBefore(
                            tarjetaArrastrada,
                            card
                        );

                    } else {

                        promoGrid.insertBefore(
                            tarjetaArrastrada,
                            card.nextSibling
                        );

                    }

                } else {

                    if (
                        evento.clientY <
                        mitadVertical
                    ) {

                        promoGrid.insertBefore(
                            tarjetaArrastrada,
                            card
                        );

                    } else {

                        promoGrid.insertBefore(
                            tarjetaArrastrada,
                            card.nextSibling
                        );

                    }

                }

            }
        );

    });

    
/* ==========================================
   PUBLICAR PROMOCIÓN
========================================== */

function publicarPromocion() {

    console.log("PUBLICAR EJECUTADO");

    const archivo =
        input.files[0];

    if (!promoForm) return;


    /* NUEVA PROMOCIÓN:
       exige imagen únicamente cuando
       no hay una promoción seleccionada */

    if (!promocionSeleccionadaId && !archivo) {

        alert(
            "Selecciona una imagen antes de publicar."
        );

        return;

    }


    /* DECIDIR SI CREA O ACTUALIZA */

    if (promocionSeleccionadaId) {

        promoForm.action =
            "/actualizar-promocion";

        promoFormId.value =
            promocionSeleccionadaId;

    } else {

        promoForm.action =
            "/agregar-promocion";

        promoFormId.value = "";

    }


    /* ESTADO VISIBLE U OCULTA */

    if (promoFormActiva) {

        promoFormActiva.disabled =
            !estadoPendiente;

    }


    /* QUITAR IMAGEN ANTERIOR DEL FORMULARIO */

    const imagenAnterior =
        promoForm.querySelector(
            'input[name="imagen"]'
        );

    if (imagenAnterior) {

        imagenAnterior.remove();

    }


    /* AGREGAR IMAGEN SOLO SI HAY UNA NUEVA */

    if (archivo) {

        const inputImagen =
            document.createElement("input");

        inputImagen.type = "file";
        inputImagen.name = "imagen";

        const transferencia =
            new DataTransfer();

        transferencia.items.add(archivo);

        inputImagen.files =
            transferencia.files;

        promoForm.appendChild(
            inputImagen
        );

    }


    if (botonPublicarSuperior) {

        botonPublicarSuperior.disabled =
            true;

    }

    if (botonPublicarLateral) {

        botonPublicarLateral.disabled =
            true;

    }


    promoForm.submit();

}


/* ==========================================
   CONECTAR BOTONES PUBLICAR
========================================== */

if (botonPublicarSuperior) {

    botonPublicarSuperior.addEventListener(
        "click",
        publicarPromocion
    );

}

if (botonPublicarLateral) {

    botonPublicarLateral.addEventListener(
        "click",
        publicarPromocion
    );

}

});