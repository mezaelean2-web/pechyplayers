document.addEventListener("DOMContentLoaded", () => {

    const boton =
        document.getElementById("btnNuevaPromo");

    const botonSuperior =
        document.getElementById("btnNuevaPromoSuperior");

    const input =
        document.getElementById("promoInput");

    const inputDesktop =
        document.getElementById("promoInputDesktop");

    const preview =
        document.getElementById("promoPreviewGrande");

    const previewDesktop =
        document.getElementById("promoPreviewDesktop");

    const desktopFallback =
        document.getElementById("promoDesktopFallback");

    const botonEliminarImagenMobile =
        document.getElementById("btnEliminarImagenMobile");

    const botonEliminarImagenDesktop =
        document.getElementById("btnEliminarImagenDesktop");

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

    const botonEditarImagenDesktop =
        document.getElementById("btnEditarImagenDesktop");

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

const promoFormEliminarImagen =
    document.getElementById("promoFormEliminarImagen");

const promoFormEliminarImagenDesktop =
    document.getElementById("promoFormEliminarImagenDesktop");

    const botonEliminarPanel =
    document.getElementById("btnEliminarPromo");

const promoEliminarForm =
    document.getElementById("promoEliminarForm");

const promoEliminarId =
    document.getElementById("promoEliminarId");

let promocionSeleccionadaId = null;
let modoEdicion = false;
let imagenMobileGuardada = "";
let imagenDesktopGuardada = "";
let eliminarImagenMobile = false;
let eliminarImagenDesktop = false;

function habilitarPublicacion() {
    if (botonPublicarSuperior) botonPublicarSuperior.disabled = false;
    if (botonPublicarLateral) botonPublicarLateral.disabled = false;
}


/* ==========================================
       SELECCIONAR PROMOCIÓN GUARDADA
========================================== */

    document
        .querySelectorAll(".promo-card")
        .forEach(card => {

            card.addEventListener("click", () => {

                const ruta =
                    card.dataset.imagen;

                const rutaDesktop =
                    card.dataset.imagenDesktop;

                const id =
                    card.dataset.id;

                promocionSeleccionadaId = id;
                modoEdicion = false;
                input.value = "";
                if (inputDesktop) inputDesktop.value = "";
                imagenMobileGuardada = ruta;
                imagenDesktopGuardada = rutaDesktop;
                eliminarImagenMobile = false;
                eliminarImagenDesktop = false;

                const activa =
                    card.dataset.activa === "1";

                    estadoPendiente = activa;


                /* Mostrar imagen */

                preview.src = ruta || "";

                preview.style.display = ruta ? "block" : "none";

                if (previewDesktop) {
                    previewDesktop.src = rutaDesktop || ruta || "";
                    previewDesktop.style.display = (rutaDesktop || ruta) ? "block" : "none";
                }

                if (desktopFallback) {
                    desktopFallback.hidden = Boolean(card.dataset.imagenDesktop);
                }

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

if (botonEditarImagenDesktop && inputDesktop) {
    botonEditarImagenDesktop.addEventListener("click", () => {
        if (!promocionSeleccionadaId && !input?.files[0]) {
            alert("Selecciona primero la imagen móvil de la nueva promoción.");
            return;
        }
        modoEdicion = Boolean(promocionSeleccionadaId);
        inputDesktop.click();
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

    eliminarImagenMobile = false;

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

    if (inputDesktop && previewDesktop && placeholder) {
        inputDesktop.addEventListener("change", () => {
            const archivo = inputDesktop.files[0];
            if (!archivo) return;

            const reader = new FileReader();
            reader.onload = evento => {
                previewDesktop.src = evento.target.result;
                previewDesktop.style.display = "block";
                eliminarImagenDesktop = false;
                if (desktopFallback) desktopFallback.hidden = true;
                placeholder.style.display = "none";

                if (botonPublicarSuperior) botonPublicarSuperior.disabled = false;
                if (botonPublicarLateral) botonPublicarLateral.disabled = false;

                if (tituloSeleccionada) {
                    tituloSeleccionada.textContent = promocionSeleccionadaId
                        ? `Editando promoción ${promocionSeleccionadaId}`
                        : "Nueva promoción";
                }
            };
            reader.readAsDataURL(archivo);
        });
    }

    if (botonEliminarImagenMobile) {
        botonEliminarImagenMobile.addEventListener("click", () => {
            if (input?.files[0]) {
                input.value = "";
                preview.src = imagenMobileGuardada || "";
                preview.style.display = imagenMobileGuardada ? "block" : "none";
                eliminarImagenMobile = false;
                habilitarPublicacion();
                return;
            }

            if (!promocionSeleccionadaId || !imagenMobileGuardada) return;
            eliminarImagenMobile = true;
            preview.removeAttribute("src");
            preview.style.display = "none";
            habilitarPublicacion();
        });
    }

    if (botonEliminarImagenDesktop) {
        botonEliminarImagenDesktop.addEventListener("click", () => {
            if (inputDesktop?.files[0]) {
                inputDesktop.value = "";
                previewDesktop.src = imagenDesktopGuardada || imagenMobileGuardada || "";
                previewDesktop.style.display = (imagenDesktopGuardada || imagenMobileGuardada) ? "block" : "none";
                if (desktopFallback) desktopFallback.hidden = Boolean(imagenDesktopGuardada);
                eliminarImagenDesktop = false;
                habilitarPublicacion();
                return;
            }

            if (!promocionSeleccionadaId || !imagenDesktopGuardada) return;
            eliminarImagenDesktop = true;
            previewDesktop.src = imagenMobileGuardada || "";
            previewDesktop.style.display = imagenMobileGuardada ? "block" : "none";
            if (desktopFallback) desktopFallback.hidden = false;
            habilitarPublicacion();
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

    const archivoDesktop =
        inputDesktop?.files[0];

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

    if (promoFormEliminarImagen) {
        promoFormEliminarImagen.value = eliminarImagenMobile ? "1" : "";
    }

    if (promoFormEliminarImagenDesktop) {
        promoFormEliminarImagenDesktop.value = eliminarImagenDesktop ? "1" : "";
    }


    /* QUITAR IMAGEN ANTERIOR DEL FORMULARIO */

    promoForm.querySelectorAll('input[name="imagen"], input[name="imagen_desktop"]')
        .forEach(imagenAnterior => imagenAnterior.remove());


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

    if (archivoDesktop) {
        const inputImagenDesktop = document.createElement("input");
        inputImagenDesktop.type = "file";
        inputImagenDesktop.name = "imagen_desktop";
        const transferenciaDesktop = new DataTransfer();
        transferenciaDesktop.items.add(archivoDesktop);
        inputImagenDesktop.files = transferenciaDesktop.files;
        promoForm.appendChild(inputImagenDesktop);
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
