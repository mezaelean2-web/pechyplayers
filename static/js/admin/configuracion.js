document.addEventListener("DOMContentLoaded", () => {

    const tarjetasModulo = [
        ...document.querySelectorAll(
            ".configuracion-modulo-card"
        )
    ];

    const tituloPreview =
        document.getElementById(
            "configuracionModuloTitulo"
        );

    const descripcionPreview =
        document.getElementById(
            "configuracionModuloDescripcion"
        );

    const iconoPreview =
        document.getElementById(
            "configuracionModuloIcono"
        );


    const informacionModulos = {

        identidad: {
            titulo: "Identidad del negocio",
            descripcion:
                "Edita el nombre, logo, eslogan y datos principales de la marca.",
            icono: "🛡"
        },

        apariencia: {
            titulo: "Colores y apariencia",
            descripcion:
                "Personaliza colores, estilos, tipografía y tema visual.",
            icono: "🎨"
        },

        contacto: {
            titulo: "WhatsApp y contacto",
            descripcion:
                "Configura números, redes sociales y mensajes de contacto.",
            icono: "☎"
        },

        comercial: {
            titulo: "Información comercial",
            descripcion:
                "Administra moneda, garantía, políticas y métodos de pago.",
            icono: "ℹ"
        },

        inicio: {
            titulo: "Página de inicio",
            descripcion:
                "Controla banners, textos y secciones visibles del inicio.",
            icono: "🏠"
        },

        catalogo: {
            titulo: "Catálogo",
            descripcion:
                "Define el comportamiento general de productos y precios.",
            icono: "📦"
        },

        promociones: {
            titulo: "Promociones",
            descripcion:
                "Configura visibilidad, cantidad y reglas de promociones.",
            icono: "🔥"
        },

        cartelera: {
            titulo: "Cartelera",
            descripcion:
                "Controla tendencias, destacados y datos visibles.",
            icono: "🎬"
        },

        mensajes: {
            titulo: "Mensajes automáticos",
            descripcion:
                "Edita textos de compra, soporte, garantía y renovación.",
            icono: "💬"
        },

        sistema: {
            titulo: "Estado del sistema",
            descripcion:
                "Administra tienda abierta, mantenimiento y avisos generales.",
            icono: "〽"
        },

        accesos: {
            titulo: "Accesos rápidos",
            descripcion:
                "Entra rápidamente a los módulos principales del panel.",
            icono: "⚡"
        },

        cliente: {
            titulo: "Modo cliente / White label",
            descripcion:
                "Prepara la plataforma para personalizarla y venderla.",
            icono: "👤"
        },

        seguridad: {
            titulo: "Seguridad",
            descripcion:
                "Gestiona contraseña, sesiones y confirmaciones importantes.",
            icono: "🛡"
        },

        respaldo: {
            titulo: "Respaldo y mantenimiento",
            descripcion:
                "Crea copias, restaura datos y realiza mantenimiento.",
            icono: "☁"
        },

        auditoria: {
            titulo: "Auditoría",
            descripcion:
                "Consulta cambios, accesos y actividad importante.",
            icono: "📋"
        }

    };


    tarjetasModulo.forEach(tarjeta => {

        tarjeta.addEventListener(
            "click",
            () => {

                tarjetasModulo.forEach(
                    otraTarjeta => {

                        otraTarjeta.classList.remove(
                            "activo"
                        );

                    }
                );

                tarjeta.classList.add(
                    "activo"
                );


                const modulo =
                    tarjeta.dataset.modulo;

                const informacion =
                    informacionModulos[modulo];

                if (!informacion) {
                    return;
                }


                if (tituloPreview) {

                    tituloPreview.textContent =
                        informacion.titulo;

                }


                if (descripcionPreview) {

                    descripcionPreview.textContent =
                        informacion.descripcion;

                }


                if (iconoPreview) {

                    iconoPreview.textContent =
                        informacion.icono;

                }

            }
        );

    });


    /* ==========================================
   MODAL IDENTIDAD DEL NEGOCIO
========================================== */

const modalIdentidad =
    document.getElementById(
        "modalIdentidad"
    );

const botonCerrarModalIdentidad =
    document.getElementById(
        "btnCerrarModalIdentidad"
    );

const botonCancelarModalIdentidad =
    document.getElementById(
        "btnCancelarModalIdentidad"
    );

const tarjetaIdentidad =
    document.querySelector(
        '.configuracion-modulo-card[data-modulo="identidad"]'
    );

const formularioIdentidad =
    document.getElementById(
        "formIdentidad"
    );


const campoNombreNegocio =
    document.getElementById(
        "nombreNegocio"
    );

const campoNombreCorto =
    document.getElementById(
        "nombreCorto"
    );

const campoEslogan =
    document.getElementById(
        "esloganNegocio"
    );

const campoDescripcion =
    document.getElementById(
        "descripcionNegocio"
    );

const campoTituloNavegador =
    document.getElementById(
        "tituloNavegador"
    );

const campoTextoFooter =
    document.getElementById(
        "textoFooter"
    );


const previewNombre =
    document.getElementById(
        "previewModalNombre"
    );

const previewEslogan =
    document.getElementById(
        "previewModalEslogan"
    );

const previewDescripcion =
    document.getElementById(
        "previewModalDescripcion"
    );

const previewTitulo =
    document.getElementById(
        "previewModalTitulo"
    );

const previewFooter =
    document.getElementById(
        "previewModalFooter"
    );


let valoresInicialesIdentidad = {};


/* ==========================================
   GUARDAR VALORES INICIALES
========================================== */

function guardarValoresInicialesIdentidad() {

    valoresInicialesIdentidad = {
        nombreNegocio:
            campoNombreNegocio?.value || "",

        nombreCorto:
            campoNombreCorto?.value || "",

        eslogan:
            campoEslogan?.value || "",

        descripcion:
            campoDescripcion?.value || "",

        tituloNavegador:
            campoTituloNavegador?.value || "",

        textoFooter:
            campoTextoFooter?.value || ""
    };

}


/* ==========================================
   ACTUALIZAR VISTA PREVIA
========================================== */

function actualizarPreviewIdentidad() {

    if (previewNombre) {

        previewNombre.textContent =
            campoNombreNegocio?.value.trim() ||
            "Nombre del negocio";

    }


    if (previewEslogan) {

        previewEslogan.textContent =
            campoEslogan?.value.trim() ||
            "Eslogan del negocio";

    }


    if (previewDescripcion) {

        previewDescripcion.textContent =
            campoDescripcion?.value.trim() ||
            "Descripción del negocio.";

    }


    if (previewTitulo) {

        previewTitulo.textContent =
            campoTituloNavegador?.value.trim() ||
            "Título del navegador";

    }


    if (previewFooter) {

        previewFooter.textContent =
            campoTextoFooter?.value.trim() ||
            "Texto del footer";

    }

}


/* ==========================================
   ABRIR MODAL
========================================== */

function abrirModalIdentidad() {

    if (!modalIdentidad) return;

    guardarValoresInicialesIdentidad();

    actualizarPreviewIdentidad();

    modalIdentidad.classList.add(
        "abierto"
    );

    modalIdentidad.setAttribute(
        "aria-hidden",
        "false"
    );

    document.body.classList.add(
        "configuracion-modal-abierto"
    );

    setTimeout(
        () => {

            campoNombreNegocio?.focus();

        },
        120
    );

}


/* ==========================================
   RESTAURAR VALORES SIN GUARDAR
========================================== */

function restaurarValoresIdentidad() {

    if (campoNombreNegocio) {
        campoNombreNegocio.value =
            valoresInicialesIdentidad.nombreNegocio || "";
    }

    if (campoNombreCorto) {
        campoNombreCorto.value =
            valoresInicialesIdentidad.nombreCorto || "";
    }

    if (campoEslogan) {
        campoEslogan.value =
            valoresInicialesIdentidad.eslogan || "";
    }

    if (campoDescripcion) {
        campoDescripcion.value =
            valoresInicialesIdentidad.descripcion || "";
    }

    if (campoTituloNavegador) {
        campoTituloNavegador.value =
            valoresInicialesIdentidad.tituloNavegador || "";
    }

    if (campoTextoFooter) {
        campoTextoFooter.value =
            valoresInicialesIdentidad.textoFooter || "";
    }

    actualizarPreviewIdentidad();

}


/* ==========================================
   CERRAR MODAL
========================================== */

function cerrarModalIdentidad(
    restaurar = true
) {

    if (!modalIdentidad) return;

    if (restaurar) {
        restaurarValoresIdentidad();
    }

    modalIdentidad.classList.remove(
        "abierto"
    );

    modalIdentidad.setAttribute(
        "aria-hidden",
        "true"
    );

    document.body.classList.remove(
        "configuracion-modal-abierto"
    );

}


/* ==========================================
   EVENTOS DE APERTURA Y CIERRE
========================================== */

if (tarjetaIdentidad) {

    tarjetaIdentidad.addEventListener(
        "click",
        abrirModalIdentidad
    );

}


if (botonCerrarModalIdentidad) {

    botonCerrarModalIdentidad.addEventListener(
        "click",
        () => cerrarModalIdentidad(true)
    );

}


if (botonCancelarModalIdentidad) {

    botonCancelarModalIdentidad.addEventListener(
        "click",
        () => cerrarModalIdentidad(true)
    );

}


document
    .querySelectorAll(
        '[data-cerrar-modal="identidad"]'
    )
    .forEach(elemento => {

        elemento.addEventListener(
            "click",
            () => cerrarModalIdentidad(true)
        );

    });


document.addEventListener(
    "keydown",
    evento => {

        if (
            evento.key === "Escape" &&
            modalIdentidad?.classList.contains(
                "abierto"
            )
        ) {

            cerrarModalIdentidad(true);

        }

    }
);


/* ==========================================
   VISTA PREVIA EN VIVO
========================================== */

[
    campoNombreNegocio,
    campoNombreCorto,
    campoEslogan,
    campoDescripcion,
    campoTituloNavegador,
    campoTextoFooter
]
.filter(Boolean)
.forEach(campo => {

    campo.addEventListener(
        "input",
        actualizarPreviewIdentidad
    );

});


/* ==========================================
   ENVÍO DEL FORMULARIO
========================================== */

if (formularioIdentidad) {

    formularioIdentidad.addEventListener(
        "submit",
        () => {

            document.body.classList.remove(
                "configuracion-modal-abierto"
            );

        }
    );

}


/* ==========================================
   MODAL CONTACTO Y WHATSAPP
========================================== */

const modalContacto =
    document.getElementById(
        "modalContacto"
    );

const tarjetaContacto =
    document.querySelector(
        '.configuracion-modulo-card[data-modulo="contacto"]'
    );

const botonCerrarModalContacto =
    document.getElementById(
        "btnCerrarModalContacto"
    );

const botonCancelarModalContacto =
    document.getElementById(
        "btnCancelarModalContacto"
    );

const formularioContacto =
    document.getElementById(
        "formContacto"
    );

const campoWhatsappPrincipal =
    document.getElementById(
        "whatsappPrincipal"
    );

const previewContactoNumero =
    document.getElementById(
        "previewContactoNumero"
    );

const previewContactoEnlace =
    document.getElementById(
        "previewContactoEnlace"
    );

const previewContactoUrlCompleta =
    document.getElementById(
        "previewContactoUrlCompleta"
    );

let valorInicialWhatsapp = "";


/* ==========================================
   LIMPIAR NÚMERO
========================================== */

function limpiarNumeroWhatsapp(valor) {

    return valor.replace(/\D/g, "");

}


/* ==========================================
   ACTUALIZAR VISTA PREVIA
========================================== */

function actualizarPreviewContacto() {

    if (!campoWhatsappPrincipal) return;

    const numeroLimpio =
        limpiarNumeroWhatsapp(
            campoWhatsappPrincipal.value
        );

    campoWhatsappPrincipal.value =
        numeroLimpio;

    const numeroMostrado =
        numeroLimpio ||
        "573147735950";

    if (previewContactoNumero) {

        previewContactoNumero.textContent =
            `+${numeroMostrado}`;

    }

    if (previewContactoEnlace) {

        previewContactoEnlace.textContent =
            `wa.me/${numeroMostrado}`;

    }

    if (previewContactoUrlCompleta) {

        previewContactoUrlCompleta.textContent =
            `https://wa.me/${numeroMostrado}`;

    }

}


/* ==========================================
   ABRIR MODAL
========================================== */

function abrirModalContacto() {

    if (
        !modalContacto ||
        !campoWhatsappPrincipal
    ) {
        return;
    }

    valorInicialWhatsapp =
        campoWhatsappPrincipal.value;

    actualizarPreviewContacto();

    modalContacto.classList.add(
        "abierto"
    );

    modalContacto.setAttribute(
        "aria-hidden",
        "false"
    );

    document.body.classList.add(
        "configuracion-modal-abierto"
    );

    setTimeout(
        () => {

            campoWhatsappPrincipal.focus();

            campoWhatsappPrincipal.select();

        },
        120
    );

}


/* ==========================================
   RESTAURAR Y CERRAR
========================================== */

function cerrarModalContacto(
    restaurar = true
) {

    if (!modalContacto) return;

    if (
        restaurar &&
        campoWhatsappPrincipal
    ) {

        campoWhatsappPrincipal.value =
            valorInicialWhatsapp;

        actualizarPreviewContacto();

    }

    modalContacto.classList.remove(
        "abierto"
    );

    modalContacto.setAttribute(
        "aria-hidden",
        "true"
    );

    document.body.classList.remove(
        "configuracion-modal-abierto"
    );

}


/* ==========================================
   EVENTOS
========================================== */

if (tarjetaContacto) {

    tarjetaContacto.addEventListener(
        "click",
        abrirModalContacto
    );

}

if (botonCerrarModalContacto) {

    botonCerrarModalContacto.addEventListener(
        "click",
        () => cerrarModalContacto(true)
    );

}

if (botonCancelarModalContacto) {

    botonCancelarModalContacto.addEventListener(
        "click",
        () => cerrarModalContacto(true)
    );

}

document
    .querySelectorAll(
        '[data-cerrar-modal="contacto"]'
    )
    .forEach(elemento => {

        elemento.addEventListener(
            "click",
            () => cerrarModalContacto(true)
        );

    });

if (campoWhatsappPrincipal) {

    campoWhatsappPrincipal.addEventListener(
        "input",
        actualizarPreviewContacto
    );

}

document.addEventListener(
    "keydown",
    evento => {

        if (
            evento.key === "Escape" &&
            modalContacto?.classList.contains(
                "abierto"
            )
        ) {

            cerrarModalContacto(true);

        }

    }
);


/* ==========================================
   VALIDAR ANTES DE GUARDAR
========================================== */

if (formularioContacto) {

    formularioContacto.addEventListener(
        "submit",
        evento => {

            const numero =
                limpiarNumeroWhatsapp(
                    campoWhatsappPrincipal?.value || ""
                );

            if (
                numero.length < 10 ||
                numero.length > 15
            ) {

                evento.preventDefault();

                alert(
                    "Ingresa un número válido con indicativo del país. Ejemplo: 573147735950."
                );

                campoWhatsappPrincipal?.focus();

                return;

            }

            campoWhatsappPrincipal.value =
                numero;

            document.body.classList.remove(
                "configuracion-modal-abierto"
            );

        }
    );

}


/* ==========================================
   MODAL COLORES Y APARIENCIA
========================================== */

const modalApariencia =
    document.getElementById(
        "modalApariencia"
    );

const tarjetaApariencia =
    document.querySelector(
        '.configuracion-modulo-card[data-modulo="apariencia"]'
    );

const botonCerrarModalApariencia =
    document.getElementById(
        "btnCerrarModalApariencia"
    );

const botonCancelarModalApariencia =
    document.getElementById(
        "btnCancelarModalApariencia"
    );

const botonRestaurarApariencia =
    document.getElementById(
        "btnRestaurarApariencia"
    );

const formularioApariencia =
    document.getElementById(
        "formApariencia"
    );


/* ==========================================
   CAMPOS DE COLOR
========================================== */

const colorPrincipal =
    document.getElementById(
        "colorPrincipal"
    );

const colorPrincipalTexto =
    document.getElementById(
        "colorPrincipalTexto"
    );

const colorSecundario =
    document.getElementById(
        "colorSecundario"
    );

const colorSecundarioTexto =
    document.getElementById(
        "colorSecundarioTexto"
    );

const colorAcento =
    document.getElementById(
        "colorAcento"
    );

const colorAcentoTexto =
    document.getElementById(
        "colorAcentoTexto"
    );

const intensidadFondo =
    document.getElementById(
        "intensidadFondo"
    );

const intensidadFondoValor =
    document.getElementById(
        "intensidadFondoValor"
    );


/* ==========================================
   ELEMENTOS DE VISTA PREVIA
========================================== */

const previewApariencia =
    document.getElementById(
        "previewApariencia"
    );

const previewValorPrincipal =
    document.getElementById(
        "previewValorPrincipal"
    );

const previewValorSecundario =
    document.getElementById(
        "previewValorSecundario"
    );

const previewValorAcento =
    document.getElementById(
        "previewValorAcento"
    );


let valoresInicialesApariencia = {};


/* ==========================================
   VALIDAR COLOR HEXADECIMAL
========================================== */

function colorHexValido(valor) {

    return /^#[0-9A-Fa-f]{6}$/.test(
        valor
    );

}


/* ==========================================
   NORMALIZAR COLOR
========================================== */

function normalizarColor(valor) {

    let color =
        valor
            .trim()
            .toUpperCase();

    if (
        color &&
        !color.startsWith("#")
    ) {

        color = `#${color}`;

    }

    return color;

}


/* ==========================================
   ACTUALIZAR VISTA PREVIA
========================================== */

function actualizarPreviewApariencia() {

    if (!previewApariencia) return;

    const principal =
        colorPrincipal?.value ||
        "#e50914";

    const secundario =
        colorSecundario?.value ||
        "#18191d";

    const acento =
        colorAcento?.value ||
        "#d4af37";

    const intensidad =
        Number(
            intensidadFondo?.value ||
            100
        );


    previewApariencia.style.setProperty(
        "--preview-principal",
        principal
    );

    previewApariencia.style.setProperty(
        "--preview-secundario",
        secundario
    );

    previewApariencia.style.setProperty(
        "--preview-acento",
        acento
    );


    /*
       60  = fondo más suave
       100 = fondo completamente oscuro
    */

    const oscuridad =
        Math.min(
            1,
            Math.max(
                .60,
                intensidad / 100
            )
        );

    previewApariencia.style.setProperty(
        "--preview-oscuridad",
        oscuridad
    );

    previewApariencia.style.filter =
        `brightness(${1.35 - oscuridad * .35})`;


    if (previewValorPrincipal) {

        previewValorPrincipal.textContent =
            principal.toUpperCase();

    }

    if (previewValorSecundario) {

        previewValorSecundario.textContent =
            secundario.toUpperCase();

    }

    if (previewValorAcento) {

        previewValorAcento.textContent =
            acento.toUpperCase();

    }

    if (intensidadFondoValor) {

        intensidadFondoValor.textContent =
            `${intensidad}%`;

    }

}


/* ==========================================
   SINCRONIZAR SELECTOR Y TEXTO
========================================== */

function conectarSelectorColor(
    selector,
    campoTexto
) {

    if (
        !selector ||
        !campoTexto
    ) {
        return;
    }


    selector.addEventListener(
        "input",
        () => {

            campoTexto.value =
                selector.value.toUpperCase();

            actualizarPreviewApariencia();

        }
    );


    campoTexto.addEventListener(
        "input",
        () => {

            const color =
                normalizarColor(
                    campoTexto.value
                );

            campoTexto.value = color;

            if (colorHexValido(color)) {

                selector.value = color;

                actualizarPreviewApariencia();

            }

        }
    );


    campoTexto.addEventListener(
        "blur",
        () => {

            const color =
                normalizarColor(
                    campoTexto.value
                );

            if (colorHexValido(color)) {

                campoTexto.value = color;

                selector.value = color;

            } else {

                campoTexto.value =
                    selector.value.toUpperCase();

            }

            actualizarPreviewApariencia();

        }
    );

}


/* ==========================================
   GUARDAR VALORES INICIALES
========================================== */

function guardarValoresInicialesApariencia() {

    valoresInicialesApariencia = {

        principal:
            colorPrincipal?.value ||
            "#e50914",

        secundario:
            colorSecundario?.value ||
            "#18191d",

        acento:
            colorAcento?.value ||
            "#d4af37",

        intensidad:
            intensidadFondo?.value ||
            "100"

    };

}


/* ==========================================
   APLICAR VALORES AL FORMULARIO
========================================== */

function aplicarValoresApariencia(
    valores
) {

    if (colorPrincipal) {

        colorPrincipal.value =
            valores.principal;

    }

    if (colorPrincipalTexto) {

        colorPrincipalTexto.value =
            valores.principal.toUpperCase();

    }

    if (colorSecundario) {

        colorSecundario.value =
            valores.secundario;

    }

    if (colorSecundarioTexto) {

        colorSecundarioTexto.value =
            valores.secundario.toUpperCase();

    }

    if (colorAcento) {

        colorAcento.value =
            valores.acento;

    }

    if (colorAcentoTexto) {

        colorAcentoTexto.value =
            valores.acento.toUpperCase();

    }

    if (intensidadFondo) {

        intensidadFondo.value =
            valores.intensidad;

    }

    actualizarPreviewApariencia();

}


/* ==========================================
   ABRIR MODAL
========================================== */

function abrirModalApariencia() {

    if (!modalApariencia) return;

    guardarValoresInicialesApariencia();

    actualizarPreviewApariencia();

    modalApariencia.classList.add(
        "abierto"
    );

    modalApariencia.setAttribute(
        "aria-hidden",
        "false"
    );

    document.body.classList.add(
        "configuracion-modal-abierto"
    );

}


/* ==========================================
   CERRAR MODAL
========================================== */

function cerrarModalApariencia(
    restaurar = true
) {

    if (!modalApariencia) return;

    if (restaurar) {

        aplicarValoresApariencia(
            valoresInicialesApariencia
        );

    }

    modalApariencia.classList.remove(
        "abierto"
    );

    modalApariencia.setAttribute(
        "aria-hidden",
        "true"
    );

    document.body.classList.remove(
        "configuracion-modal-abierto"
    );

}


/* ==========================================
   CONECTAR SELECTORES
========================================== */

conectarSelectorColor(
    colorPrincipal,
    colorPrincipalTexto
);

conectarSelectorColor(
    colorSecundario,
    colorSecundarioTexto
);

conectarSelectorColor(
    colorAcento,
    colorAcentoTexto
);


if (intensidadFondo) {

    intensidadFondo.addEventListener(
        "input",
        actualizarPreviewApariencia
    );

}


/* ==========================================
   EVENTOS DEL MODAL
========================================== */

if (tarjetaApariencia) {

    tarjetaApariencia.addEventListener(
        "click",
        abrirModalApariencia
    );

}


if (botonCerrarModalApariencia) {

    botonCerrarModalApariencia.addEventListener(
        "click",
        () => cerrarModalApariencia(true)
    );

}


if (botonCancelarModalApariencia) {

    botonCancelarModalApariencia.addEventListener(
        "click",
        () => cerrarModalApariencia(true)
    );

}


document
    .querySelectorAll(
        '[data-cerrar-modal="apariencia"]'
    )
    .forEach(elemento => {

        elemento.addEventListener(
            "click",
            () => cerrarModalApariencia(true)
        );

    });


document.addEventListener(
    "keydown",
    evento => {

        if (
            evento.key === "Escape" &&
            modalApariencia?.classList.contains(
                "abierto"
            )
        ) {

            cerrarModalApariencia(true);

        }

    }
);


/* ==========================================
   RESTAURAR COLORES PREDETERMINADOS
========================================== */

if (botonRestaurarApariencia) {

    botonRestaurarApariencia.addEventListener(
        "click",
        () => {

            aplicarValoresApariencia({

                principal:
                    "#e50914",

                secundario:
                    "#18191d",

                acento:
                    "#d4af37",

                intensidad:
                    "100"

            });

        }
    );

}


/* ==========================================
   VALIDAR Y GUARDAR APARIENCIA
========================================== */

if (formularioApariencia) {

    formularioApariencia.addEventListener(
        "submit",
        evento => {

            const principal =
                normalizarColor(
                    colorPrincipalTexto?.value || ""
                );

            const secundario =
                normalizarColor(
                    colorSecundarioTexto?.value || ""
                );

            const acento =
                normalizarColor(
                    colorAcentoTexto?.value || ""
                );


            if (
                !colorHexValido(principal) ||
                !colorHexValido(secundario) ||
                !colorHexValido(acento)
            ) {

                evento.preventDefault();

                alert(
                    "Revisa los colores. Deben tener un formato como #E50914."
                );

                return;

            }


            colorPrincipal.value =
                principal;

            colorSecundario.value =
                secundario;

            colorAcento.value =
                acento;


            document.body.classList.remove(
                "configuracion-modal-abierto"
            );

        }
    );

}

/* ==========================================
   MODAL CONFIGURACIÓN COMERCIAL
========================================== */

const modalComercial =
    document.getElementById("modalComercial");

const tarjetaComercial =
    document.querySelector(
        '.configuracion-modulo-card[data-modulo="comercial"]'
    );

const btnCerrarModalComercial =
    document.getElementById(
        "btnCerrarModalComercial"
    );

const btnCancelarModalComercial =
    document.getElementById(
        "btnCancelarModalComercial"
    );

const formComercial =
    document.getElementById("formComercial");


const monedaNombre =
    document.getElementById("monedaNombre");

const monedaSimbolo =
    document.getElementById("monedaSimbolo");

const separadorMiles =
    document.getElementById("separadorMiles");

const diasGarantia =
    document.getElementById("diasGarantia");

const textoEntrega =
    document.getElementById("textoEntrega");

const textoDisponibilidad =
    document.getElementById(
        "textoDisponibilidad"
    );

const mensajeComercial =
    document.getElementById(
        "mensajeComercial"
    );


const previewComercialDisponibilidad =
    document.getElementById(
        "previewComercialDisponibilidad"
    );

const previewComercialPrecio =
    document.getElementById(
        "previewComercialPrecio"
    );

const previewComercialMensaje =
    document.getElementById(
        "previewComercialMensaje"
    );

const previewComercialEntrega =
    document.getElementById(
        "previewComercialEntrega"
    );

const previewComercialGarantia =
    document.getElementById(
        "previewComercialGarantia"
    );

const previewComercialMoneda =
    document.getElementById(
        "previewComercialMoneda"
    );

const previewComercialFormato =
    document.getElementById(
        "previewComercialFormato"
    );


let valoresComercialesOriginales = null;


/* ==========================================
   FORMATO DE PRECIO DE EJEMPLO
========================================== */

function obtenerPrecioComercialEjemplo(){

    const simbolo =
        monedaSimbolo?.value.trim() || "$";

    const separador =
        separadorMiles?.value ?? ".";

    return `${simbolo}20${separador}000`;

}


/* ==========================================
   ACTUALIZAR PREVISUALIZACIÓN
========================================== */

function actualizarPreviewComercial(){

    const precioEjemplo =
        obtenerPrecioComercialEjemplo();


    if (previewComercialDisponibilidad) {

        previewComercialDisponibilidad.textContent =
            textoDisponibilidad?.value.trim() ||
            "Disponible";

    }


    if (previewComercialPrecio) {

        previewComercialPrecio.textContent =
            precioEjemplo;

    }


    if (previewComercialMensaje) {

        previewComercialMensaje.textContent =
            mensajeComercial?.value.trim() ||
            "Plataformas premium al mejor precio, entrega inmediata y soporte rápido.";

    }


    if (previewComercialEntrega) {

        previewComercialEntrega.textContent =
            textoEntrega?.value.trim() ||
            "Entrega inmediata";

    }


    if (previewComercialGarantia) {

        previewComercialGarantia.textContent =
            diasGarantia?.value || "30";

    }


    if (previewComercialMoneda) {

        previewComercialMoneda.textContent =
            monedaNombre?.value.trim() ||
            "Peso colombiano";

    }


    if (previewComercialFormato) {

        previewComercialFormato.textContent =
            precioEjemplo;

    }

}


/* ==========================================
   GUARDAR ESTADO ORIGINAL
========================================== */

function guardarEstadoComercial(){

    valoresComercialesOriginales = {

        monedaNombre:
            monedaNombre?.value || "",

        monedaSimbolo:
            monedaSimbolo?.value || "",

        separadorMiles:
            separadorMiles?.value || ".",

        diasGarantia:
            diasGarantia?.value || "30",

        textoEntrega:
            textoEntrega?.value || "",

        textoDisponibilidad:
            textoDisponibilidad?.value || "",

        mensajeComercial:
            mensajeComercial?.value || ""

    };

}


/* ==========================================
   RESTAURAR ESTADO ORIGINAL
========================================== */

function restaurarEstadoComercial(){

    if (!valoresComercialesOriginales) {
        return;
    }


    if (monedaNombre) {
        monedaNombre.value =
            valoresComercialesOriginales
                .monedaNombre;
    }


    if (monedaSimbolo) {
        monedaSimbolo.value =
            valoresComercialesOriginales
                .monedaSimbolo;
    }


    if (separadorMiles) {
        separadorMiles.value =
            valoresComercialesOriginales
                .separadorMiles;
    }


    if (diasGarantia) {
        diasGarantia.value =
            valoresComercialesOriginales
                .diasGarantia;
    }


    if (textoEntrega) {
        textoEntrega.value =
            valoresComercialesOriginales
                .textoEntrega;
    }


    if (textoDisponibilidad) {
        textoDisponibilidad.value =
            valoresComercialesOriginales
                .textoDisponibilidad;
    }


    if (mensajeComercial) {
        mensajeComercial.value =
            valoresComercialesOriginales
                .mensajeComercial;
    }


    actualizarPreviewComercial();

}


/* ==========================================
   ABRIR Y CERRAR MODAL
========================================== */

function abrirModalComercial(){

    if (!modalComercial) {
        return;
    }


    guardarEstadoComercial();
    actualizarPreviewComercial();


    modalComercial.classList.add(
    "abierto"
);

    modalComercial.setAttribute(
        "aria-hidden",
        "false"
    );

    document.body.classList.add(
        "configuracion-modal-abierto"
    );

}


function cerrarModalComercial(
    restaurar = false
){

    if (!modalComercial) {
        return;
    }


    if (restaurar) {
        restaurarEstadoComercial();
    }


    modalComercial.classList.remove(
    "abierto"
);

    modalComercial.setAttribute(
        "aria-hidden",
        "true"
    );

    document.body.classList.remove(
        "configuracion-modal-abierto"
    );

}


/* ==========================================
   EVENTOS DEL MODAL
========================================== */

if (tarjetaComercial) {

    tarjetaComercial.addEventListener(
        "click",
        abrirModalComercial
    );

}


if (btnCerrarModalComercial) {

    btnCerrarModalComercial.addEventListener(
        "click",
        () => cerrarModalComercial(true)
    );

}


if (btnCancelarModalComercial) {

    btnCancelarModalComercial.addEventListener(
        "click",
        () => cerrarModalComercial(true)
    );

}


document.querySelectorAll(
    '[data-cerrar-modal="comercial"]'
).forEach(elemento => {

    elemento.addEventListener(
        "click",
        () => cerrarModalComercial(true)
    );

});


[
    monedaNombre,
    monedaSimbolo,
    separadorMiles,
    diasGarantia,
    textoEntrega,
    textoDisponibilidad,
    mensajeComercial
].forEach(campo => {

    if (!campo) {
        return;
    }


    campo.addEventListener(
        "input",
        actualizarPreviewComercial
    );

    campo.addEventListener(
        "change",
        actualizarPreviewComercial
    );

});


document.addEventListener(
    "keydown",
    evento => {

        if (
            evento.key === "Escape" &&
            modalComercial?.classList.contains(
    "abierto"
)
        ) {

            cerrarModalComercial(true);

        }

    }
);


/* ==========================================
   VALIDAR Y GUARDAR CONFIGURACIÓN COMERCIAL
========================================== */

if (formComercial) {

    formComercial.addEventListener(
        "submit",
        evento => {

            const nombreMoneda =
                monedaNombre?.value.trim() || "";

            const simbolo =
                monedaSimbolo?.value.trim() || "";

            const garantia =
                Number(
                    diasGarantia?.value || 0
                );

            const entrega =
                textoEntrega?.value.trim() || "";

            const disponibilidad =
                textoDisponibilidad?.value.trim() || "";

            const mensaje =
                mensajeComercial?.value.trim() || "";


            if (!nombreMoneda) {

                evento.preventDefault();

                alert(
                    "Ingresa el nombre de la moneda."
                );

                monedaNombre?.focus();

                return;

            }


            if (!simbolo) {

                evento.preventDefault();

                alert(
                    "Ingresa el símbolo de la moneda."
                );

                monedaSimbolo?.focus();

                return;

            }


            if (
                !Number.isInteger(garantia) ||
                garantia < 0 ||
                garantia > 365
            ) {

                evento.preventDefault();

                alert(
                    "La garantía debe estar entre 0 y 365 días."
                );

                diasGarantia?.focus();

                return;

            }


            if (!entrega) {

                evento.preventDefault();

                alert(
                    "Ingresa el texto de entrega."
                );

                textoEntrega?.focus();

                return;

            }


            if (!disponibilidad) {

                evento.preventDefault();

                alert(
                    "Ingresa el texto de disponibilidad."
                );

                textoDisponibilidad?.focus();

                return;

            }


            if (
                !mensaje ||
                mensaje.length > 220
            ) {

                evento.preventDefault();

                alert(
                    "El mensaje comercial debe contener entre 1 y 220 caracteres."
                );

                mensajeComercial?.focus();

                return;

            }


            document.body.classList.remove(
                "configuracion-modal-abierto"
            );

        }
    );

}

/* ==========================================
   MODAL PÁGINA DE INICIO
========================================== */

const modalInicio =
    document.getElementById(
        "modalInicio"
    );

const tarjetaInicio =
    document.querySelector(
        '.configuracion-modulo-card[data-modulo="inicio"]'
    );

const btnCerrarModalInicio =
    document.getElementById(
        "btnCerrarModalInicio"
    );

const btnCancelarModalInicio =
    document.getElementById(
        "btnCancelarModalInicio"
    );

const formInicio =
    document.getElementById(
        "formInicio"
    );


/* ==========================================
   CAMPOS
========================================== */

const inicioHeroActivo =
    document.getElementById(
        "inicioHeroActivo"
    );

const inicioBadge =
    document.getElementById(
        "inicioBadge"
    );

const inicioTituloSuperior =
    document.getElementById(
        "inicioTituloSuperior"
    );

const inicioTituloDestacado =
    document.getElementById(
        "inicioTituloDestacado"
    );

const inicioTituloInferior =
    document.getElementById(
        "inicioTituloInferior"
    );

const inicioBotonCatalogo =
    document.getElementById(
        "inicioBotonCatalogo"
    );

const inicioBotonWhatsapp =
    document.getElementById(
        "inicioBotonWhatsapp"
    );


/* ==========================================
   VISTA PREVIA
========================================== */

const previewInicioHero =
    document.getElementById(
        "previewInicioHero"
    );

const previewInicioBadge =
    document.getElementById(
        "previewInicioBadge"
    );

const previewInicioTituloSuperior =
    document.getElementById(
        "previewInicioTituloSuperior"
    );

const previewInicioTituloDestacado =
    document.getElementById(
        "previewInicioTituloDestacado"
    );

const previewInicioTituloInferior =
    document.getElementById(
        "previewInicioTituloInferior"
    );

const previewInicioBotonCatalogo =
    document.getElementById(
        "previewInicioBotonCatalogo"
    );

const previewInicioBotonWhatsapp =
    document.getElementById(
        "previewInicioBotonWhatsapp"
    );

const previewInicioEstado =
    document.getElementById(
        "previewInicioEstado"
    );


let valoresInicialesInicio = null;


/* ==========================================
   GUARDAR ESTADO ORIGINAL
========================================== */

function guardarEstadoInicio(){

    valoresInicialesInicio = {

        heroActivo:
            inicioHeroActivo?.checked || false,

        badge:
            inicioBadge?.value || "",

        tituloSuperior:
            inicioTituloSuperior?.value || "",

        tituloDestacado:
            inicioTituloDestacado?.value || "",

        tituloInferior:
            inicioTituloInferior?.value || "",

        botonCatalogo:
            inicioBotonCatalogo?.value || "",

        botonWhatsapp:
            inicioBotonWhatsapp?.value || ""

    };

}


/* ==========================================
   ACTUALIZAR VISTA PREVIA
========================================== */

function actualizarPreviewInicio(){

    const heroActivo =
        inicioHeroActivo?.checked ?? true;


    if (previewInicioBadge) {

        previewInicioBadge.textContent =
            inicioBadge?.value.trim() ||
            "🛡️ COMPRA SEGURA Y PROTEGIDA";

    }


    if (previewInicioTituloSuperior) {

        previewInicioTituloSuperior.textContent =
            inicioTituloSuperior?.value.trim() ||
            "EL MEJOR";

    }


    if (previewInicioTituloDestacado) {

        previewInicioTituloDestacado.textContent =
            inicioTituloDestacado?.value.trim() ||
            "ENTRETENIMIENTO";

    }


    if (previewInicioTituloInferior) {

        previewInicioTituloInferior.textContent =
            inicioTituloInferior?.value.trim() ||
            "EN TUS MANOS";

    }


    if (previewInicioBotonCatalogo) {

        previewInicioBotonCatalogo.textContent =
            inicioBotonCatalogo?.value.trim() ||
            "Explorar catálogo →";

    }


    if (previewInicioBotonWhatsapp) {

        previewInicioBotonWhatsapp.textContent =
            inicioBotonWhatsapp?.value.trim() ||
            "💬 Comprar por WhatsApp";

    }


    if (previewInicioEstado) {

        previewInicioEstado.textContent =
            heroActivo
                ? "ACTIVO"
                : "OCULTO";

        previewInicioEstado.classList.toggle(
            "inactivo",
            !heroActivo
        );

    }


    if (previewInicioHero) {

        previewInicioHero.classList.toggle(
            "inicio-preview-hero-oculto",
            !heroActivo
        );

    }

}


/* ==========================================
   RESTAURAR VALORES
========================================== */

function restaurarEstadoInicio(){

    if (!valoresInicialesInicio) {
        return;
    }


    if (inicioHeroActivo) {

        inicioHeroActivo.checked =
            valoresInicialesInicio.heroActivo;

    }


    if (inicioBadge) {

        inicioBadge.value =
            valoresInicialesInicio.badge;

    }


    if (inicioTituloSuperior) {

        inicioTituloSuperior.value =
            valoresInicialesInicio.tituloSuperior;

    }


    if (inicioTituloDestacado) {

        inicioTituloDestacado.value =
            valoresInicialesInicio.tituloDestacado;

    }


    if (inicioTituloInferior) {

        inicioTituloInferior.value =
            valoresInicialesInicio.tituloInferior;

    }


    if (inicioBotonCatalogo) {

        inicioBotonCatalogo.value =
            valoresInicialesInicio.botonCatalogo;

    }


    if (inicioBotonWhatsapp) {

        inicioBotonWhatsapp.value =
            valoresInicialesInicio.botonWhatsapp;

    }


    actualizarPreviewInicio();

}


/* ==========================================
   ABRIR MODAL
========================================== */

function abrirModalInicio(){

    if (!modalInicio) {
        return;
    }


    guardarEstadoInicio();

    actualizarPreviewInicio();


    modalInicio.classList.add(
        "abierto"
    );

    modalInicio.setAttribute(
        "aria-hidden",
        "false"
    );

    document.body.classList.add(
        "configuracion-modal-abierto"
    );


    setTimeout(
        () => {

            inicioBadge?.focus();

        },
        120
    );

}


/* ==========================================
   CERRAR MODAL
========================================== */

function cerrarModalInicio(
    restaurar = true
){

    if (!modalInicio) {
        return;
    }


    if (restaurar) {

        restaurarEstadoInicio();

    }


    modalInicio.classList.remove(
        "abierto"
    );

    modalInicio.setAttribute(
        "aria-hidden",
        "true"
    );

    document.body.classList.remove(
        "configuracion-modal-abierto"
    );

}


/* ==========================================
   EVENTOS DE APERTURA Y CIERRE
========================================== */

if (tarjetaInicio) {

    tarjetaInicio.addEventListener(
        "click",
        abrirModalInicio
    );

}


if (btnCerrarModalInicio) {

    btnCerrarModalInicio.addEventListener(
        "click",
        () => cerrarModalInicio(true)
    );

}


if (btnCancelarModalInicio) {

    btnCancelarModalInicio.addEventListener(
        "click",
        () => cerrarModalInicio(true)
    );

}


document
    .querySelectorAll(
        '[data-cerrar-modal="inicio"]'
    )
    .forEach(elemento => {

        elemento.addEventListener(
            "click",
            () => cerrarModalInicio(true)
        );

    });


document.addEventListener(
    "keydown",
    evento => {

        if (
            evento.key === "Escape" &&
            modalInicio?.classList.contains(
                "abierto"
            )
        ) {

            cerrarModalInicio(true);

        }

    }
);


/* ==========================================
   VISTA PREVIA EN VIVO
========================================== */

[
    inicioBadge,
    inicioTituloSuperior,
    inicioTituloDestacado,
    inicioTituloInferior,
    inicioBotonCatalogo,
    inicioBotonWhatsapp
]
.filter(Boolean)
.forEach(campo => {

    campo.addEventListener(
        "input",
        actualizarPreviewInicio
    );

});


if (inicioHeroActivo) {

    inicioHeroActivo.addEventListener(
        "change",
        actualizarPreviewInicio
    );

}


/* ==========================================
   GUARDAR CONFIGURACIÓN DE INICIO
========================================== */

if (formInicio) {

    formInicio.addEventListener(
        "submit",
        evento => {

            const badge =
                inicioBadge?.value.trim() || "";

            const tituloSuperior =
                inicioTituloSuperior?.value.trim() || "";

            const tituloDestacado =
                inicioTituloDestacado?.value.trim() || "";

            const tituloInferior =
                inicioTituloInferior?.value.trim() || "";

            const botonCatalogo =
                inicioBotonCatalogo?.value.trim() || "";

            const botonWhatsapp =
                inicioBotonWhatsapp?.value.trim() || "";


            if (
                !badge ||
                !tituloSuperior ||
                !tituloDestacado ||
                !tituloInferior ||
                !botonCatalogo ||
                !botonWhatsapp
            ) {

                evento.preventDefault();

                alert(
                    "Completa todos los campos de la página de inicio."
                );

                return;

            }


            document.body.classList.remove(
                "configuracion-modal-abierto"
            );

        }
    );

}

});