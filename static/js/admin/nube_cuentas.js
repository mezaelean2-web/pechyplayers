document.addEventListener(
    "DOMContentLoaded",
    () => {

        // ==========================================
        // MODAL — NUEVA CUENTA
        // ==========================================

        const modal =
            document.getElementById(
                "modalNuevaCuenta"
            );

        const abrir =
            document.getElementById(
                "abrirNuevaCuenta"
            );

        const cerrar =
            document.getElementById(
                "cerrarNuevaCuenta"
            );

        const cancelar =
            document.getElementById(
                "cancelarNuevaCuenta"
            );

        const backdrop =
            document.getElementById(
                "cerrarNuevaCuentaBackdrop"
            );


        function abrirModal(){

            if (!modal) return;

            modal.classList.add(
                "abierto"
            );

            modal.setAttribute(
                "aria-hidden",
                "false"
            );

            document.body.classList.add(
                "nube-modal-abierto"
            );

        }


        function cerrarModal(){

            if (!modal) return;

            modal.classList.remove(
                "abierto"
            );

            modal.setAttribute(
                "aria-hidden",
                "true"
            );

            document.body.classList.remove(
                "nube-modal-abierto"
            );

        }


        abrir?.addEventListener(
            "click",
            abrirModal
        );


        cerrar?.addEventListener(
            "click",
            cerrarModal
        );


        cancelar?.addEventListener(
            "click",
            cerrarModal
        );


        backdrop?.addEventListener(
            "click",
            cerrarModal
        );



        // ==========================================
        // DRAWER — DETALLE DE CUENTA
        // ==========================================

        const drawer =
            document.getElementById(
                "nubeDrawer"
            );

        const drawerBackdrop =
            document.getElementById(
                "nubeDrawerBackdrop"
            );

        const cerrarDrawer =
            document.getElementById(
                "cerrarDrawer"
            );

        const botonesVer =
            document.querySelectorAll(
                ".nube-ver-cuenta"
            );

        const drawerTitulo =
            document.getElementById(
                "drawerTitulo"
            );

        const drawerId =
            document.getElementById(
                "drawerId"
            );

        const drawerEstado =
            document.getElementById(
                "drawerEstado"
            );

        const drawerLogo =
            document.getElementById(
                "drawerLogo"
            );

        const drawerCorreo =
            document.getElementById(
                "drawerCorreo"
            );

        const drawerContrasena =
            document.getElementById(
                "drawerContrasena"
            );

        const drawerPin =
            document.getElementById(
                "drawerPin"
            );

        const drawerTipo =
            document.getElementById(
                "drawerTipo"
            );

        const drawerPlataforma =
            document.getElementById(
                "drawerPlataforma"
            );

        const drawerCliente =
            document.getElementById(
                "drawerCliente"
            );

        const drawerTelefono =
            document.getElementById(
                "drawerTelefono"
            );

        const drawerEntrega =
            document.getElementById(
                "drawerEntrega"
            );

        const drawerDias =
            document.getElementById(
                "drawerDias"
            );

        const drawerVencimiento =
            document.getElementById(
                "drawerVencimiento"
            );

        const drawerRestantes =
            document.getElementById(
                "drawerRestantes"
            );

        const togglePassword =
            document.getElementById(
                "toggleDrawerPassword"
            );


        let passwordActual = "";

        let passwordVisible = false;


        function abrirDrawer(
            boton
        ){

            if (!drawer) return;

            const datos =
                boton.dataset;


            const plataforma =
                datos.plataforma ||
                "Cuenta";


            if (drawerTitulo){

                drawerTitulo.textContent =
                    `${plataforma} - ${datos.tipo || "Cuenta"}`;

            }


            if (drawerId){

                drawerId.textContent =
                    `ID: ${datos.id || "—"}`;

            }


            if (drawerLogo){

                drawerLogo.textContent =
                    plataforma
                        .slice(0,1)
                        .toUpperCase();

            }


            if (drawerCorreo){

                drawerCorreo.textContent =
                    datos.correo || "—";

            }


            if (drawerPin){

                drawerPin.textContent =
                    datos.pin || "—";

            }


            if (drawerTipo){

                drawerTipo.textContent =
                    datos.tipo || "—";

            }


            if (drawerPlataforma){

                drawerPlataforma.textContent =
                    plataforma;

            }


            if (drawerCliente){

                drawerCliente.textContent =
                    datos.cliente ||
                    "Sin asignar";

            }


            if (drawerTelefono){

                drawerTelefono.textContent =
                    datos.telefono || "—";

            }


            if (drawerEntrega){

                drawerEntrega.textContent =
                    datos.entrega || "—";

            }


            if (drawerDias){

                drawerDias.textContent =
                    datos.dias
                        ? `${datos.dias} días`
                        : "—";

            }


            if (drawerVencimiento){

                drawerVencimiento.textContent =
                    datos.vencimiento || "—";

            }


            if (drawerRestantes){

                drawerRestantes.textContent =
                    datos.restantes
                        ? `${datos.restantes} días`
                        : "0 días";

            }


            passwordActual =
                datos.contrasena || "";

            passwordVisible = false;


            if (drawerContrasena){

                drawerContrasena.textContent =
                    passwordActual
                        ? "••••••••"
                        : "—";

            }


            const estado =
                datos.estado ||
                "disponible";


            if (drawerEstado){

                drawerEstado.className =
                    `nube-estado nube-estado-${estado}`;

                drawerEstado.textContent =
                    estado
                        .replace(
                            "_",
                            " "
                        );

            }


            drawer.classList.add(
                "abierto"
            );

            drawer.setAttribute(
                "aria-hidden",
                "false"
            );

            document.body.classList.add(
                "nube-modal-abierto"
            );

        }


        function cerrarPanelCuenta(){

            if (!drawer) return;

            drawer.classList.remove(
                "abierto"
            );

            drawer.setAttribute(
                "aria-hidden",
                "true"
            );

            document.body.classList.remove(
                "nube-modal-abierto"
            );

        }


        botonesVer.forEach(
            boton => {

                boton.addEventListener(
                    "click",
                    () => {

                        abrirDrawer(
                            boton
                        );

                    }
                );

            }
        );


        cerrarDrawer?.addEventListener(
            "click",
            cerrarPanelCuenta
        );


        drawerBackdrop?.addEventListener(
            "click",
            cerrarPanelCuenta
        );


        togglePassword?.addEventListener(
            "click",
            () => {

                if (!passwordActual){
                    return;
                }


                passwordVisible =
                    !passwordVisible;


                if (drawerContrasena){

                    drawerContrasena.textContent =
                        passwordVisible
                            ? passwordActual
                            : "••••••••";

                }

            }
        );



        // ==========================================
        // TIPO DE CUENTA / PERFILES
        // ==========================================

        const nubeTipoCuenta =
            document.getElementById(
                "nubeTipoCuenta"
            );

        const grupoCantidadPerfiles =
            document.getElementById(
                "grupoCantidadPerfiles"
            );

        const cantidadPerfiles =
            document.getElementById(
                "cantidadPerfiles"
            );

        const grupoPinesPerfiles =
    document.getElementById(
        "grupoPinesPerfiles"
    );

const listaPinesPerfiles =
    document.getElementById(
        "listaPinesPerfiles"
    );


    function actualizarPinesPerfiles(){

    if (
        !grupoPinesPerfiles ||
        !listaPinesPerfiles
    ){
        return;
    }


    const tipo =
    nubeTipoCuenta?.value || "";


    const cantidad =
        Number(
            cantidadPerfiles?.value || 0
        );


    if (
        tipo !== "perfil" ||
        cantidad < 1
    ){

        grupoPinesPerfiles.hidden = true;

        listaPinesPerfiles.innerHTML = "";

        return;
    }


    grupoPinesPerfiles.hidden = false;


    const valoresActuales = {};


    listaPinesPerfiles
        .querySelectorAll("input")
        .forEach(input => {

            valoresActuales[
                input.name
            ] = input.value;

        });


    listaPinesPerfiles.innerHTML = "";


    for (
        let numero = 1;
        numero <= cantidad;
        numero++
    ){

        const fila =
            document.createElement(
                "label"
            );


        fila.className =
            "nube-pin-perfil-item";


        fila.innerHTML = `
            <span>
                Perfil ${numero}
            </span>

            <input
                type="text"
                name="pin_perfil_${numero}"
                inputmode="numeric"
                autocomplete="off"
                placeholder="Ej: 1507"
                value="${valoresActuales[`pin_perfil_${numero}`] || ""}"
            >
        `;


        listaPinesPerfiles.appendChild(
            fila
        );

    }

}


        function actualizarTipoCuenta(){

            const esPerfil =
                nubeTipoCuenta?.value ===
                "perfil";


            if (grupoCantidadPerfiles){

                grupoCantidadPerfiles.hidden =
                    !esPerfil;

            }


            if (cantidadPerfiles){

                cantidadPerfiles.required =
                    esPerfil;


                if (!esPerfil){

                    cantidadPerfiles.value =
                        "";

                }

            }

        }


        nubeTipoCuenta?.addEventListener(
    "change",
    () => {

        actualizarTipoCuenta();

        actualizarPinesPerfiles();

    }
);


actualizarTipoCuenta();
actualizarPinesPerfiles();

    cantidadPerfiles?.addEventListener(
    "input",
    () => {

        actualizarPinesPerfiles();

    }
);

        // ==========================================
        // CONTROL DE PAGO
        // ==========================================

        const nubeTipoPago =
            document.getElementById(
                "nubeTipoPago"
            );

        const grupoConfiguracionPin =
            document.getElementById(
                "grupoConfiguracionPin"
            );

        const selectorValorPin =
            document.getElementById(
                "nubeValorPinSelector"
            );

        const grupoValorPinOtro =
            document.getElementById(
                "grupoValorPinOtro"
            );

        const valorPinOtro =
            document.getElementById(
                "nubeValorPinOtro"
            );

        const valorPinFinal =
            document.getElementById(
                "nubeValorPin"
            );

        const planPago =
            document.getElementById(
                "nubePlanPago"
            );

        const precioPlan =
            document.getElementById(
                "nubePrecioPlan"
            );

        const fechaAplicacionPin =
            document.getElementById(
                "nubeFechaAplicacionPin"
            );

        const previewDiasPin =
            document.getElementById(
                "previewDiasPin"
            );

        const previewFechaPin =
            document.getElementById(
                "previewFechaPin"
            );


        function obtenerValorPin(){

    if (
        selectorValorPin?.value ===
        "otro"
    ){

        const texto =
            String(
                valorPinOtro?.value || ""
            );

        return Number(
            texto.replace(
                /\D/g,
                ""
            )
        );

    }


    return Number(
        selectorValorPin?.value || 0
    );

}



        function calcularPreviewPin(){

            if (
                nubeTipoPago?.value !==
                "pin"
            ){

                return;

            }


            const valorPin =
                obtenerValorPin();

            const precioTexto =
    String(
        precioPlan?.value || ""
    );

const precio =
    Number(
        precioTexto.replace(
            /\D/g,
            ""
        )
    );


            if (valorPinFinal){

                valorPinFinal.value =
                    valorPin;

            }


            if (
                valorPin <= 0 ||
                precio <= 0
            ){

                if (previewDiasPin){

                    previewDiasPin.textContent =
                        "—";

                }


                if (previewFechaPin){

                    previewFechaPin.textContent =
                        "—";

                }


                return;

            }


            const dias =
                Math.max(
                    Math.floor(
                        (
                            valorPin /
                            precio
                        ) * 30
                    ),
                    1
                );


            if (previewDiasPin){

                previewDiasPin.textContent =
                    `${dias} días aprox.`;

            }


            if (
                fechaAplicacionPin?.value
            ){

                const fecha =
                    new Date(
                        `${fechaAplicacionPin.value}T12:00:00`
                    );


                fecha.setDate(
                    fecha.getDate() +
                    dias
                );


                const fechaFormateada =
                    fecha.toLocaleDateString(
                        "es-CO",
                        {
                            day: "2-digit",
                            month: "2-digit",
                            year: "numeric"
                        }
                    );


                if (previewFechaPin){

                    previewFechaPin.textContent =
                        fechaFormateada;

                }

            }else{

                if (previewFechaPin){

                    previewFechaPin.textContent =
                        "—";

                }

            }

        }



        function actualizarValorPin(){

            const esOtro =
                selectorValorPin?.value ===
                "otro";


            if (grupoValorPinOtro){

                grupoValorPinOtro.hidden =
                    !esOtro;

            }


            if (valorPinOtro){

                valorPinOtro.required =
                    esOtro;


                if (!esOtro){

                    valorPinOtro.value =
                        "";

                }

            }


            if (valorPinFinal){

                valorPinFinal.value =
                    obtenerValorPin();

            }


            calcularPreviewPin();

        }



        function actualizarTipoPago(){

            const esPin =
                nubeTipoPago?.value ===
                "pin";


            if (grupoConfiguracionPin){

                grupoConfiguracionPin.hidden =
                    !esPin;

            }


            if (planPago){

                planPago.required =
                    esPin;

            }


            if (precioPlan){

                precioPlan.required =
                    esPin;

            }


            if (fechaAplicacionPin){

                fechaAplicacionPin.required =
                    esPin;

            }


            if (selectorValorPin){

                selectorValorPin.required =
                    esPin;

            }


            if (!esPin){

                if (selectorValorPin){

                    selectorValorPin.value =
                        "";

                }


                if (valorPinOtro){

                    valorPinOtro.value =
                        "";

                    valorPinOtro.required =
                        false;

                }


                if (valorPinFinal){

                    valorPinFinal.value =
                        "0";

                }


                if (planPago){

                    planPago.value =
                        "";

                }


                if (precioPlan){

                    precioPlan.value =
                        "";

                }


                if (fechaAplicacionPin){

                    fechaAplicacionPin.value =
                        "";

                }


                if (grupoValorPinOtro){

                    grupoValorPinOtro.hidden =
                        true;

                }


                if (previewDiasPin){

                    previewDiasPin.textContent =
                        "—";

                }


                if (previewFechaPin){

                    previewFechaPin.textContent =
                        "—";

                }

            }else{

                actualizarValorPin();

            }

        }


        nubeTipoPago?.addEventListener(
            "change",
            actualizarTipoPago
        );


        selectorValorPin?.addEventListener(
            "change",
            actualizarValorPin
        );


        valorPinOtro?.addEventListener(
            "input",
            actualizarValorPin
        );


        precioPlan?.addEventListener(
            "input",
            calcularPreviewPin
        );


        fechaAplicacionPin?.addEventListener(
            "change",
            calcularPreviewPin
        );


        planPago?.addEventListener(
            "change",
            calcularPreviewPin
        );


        actualizarTipoPago();
        actualizarValorPin();


                // ==========================================
        // CUENTAS DESPLEGABLES / PERFILES
        // ==========================================

        const botonesExpandir =
            document.querySelectorAll(
                ".nube-expandir-cuenta"
            );


        botonesExpandir.forEach(
            boton => {

                boton.addEventListener(
                    "click",
                    () => {

                        const cuentaId =
                            boton.dataset.cuentaId;


                        const perfiles =
                            document.querySelectorAll(
                                `.nube-perfil-row[data-parent-id="${cuentaId}"]`
                            );


                        const abierto =
                            boton.classList.contains(
                                "abierto"
                            );


                        perfiles.forEach(
                            perfil => {

                                perfil.hidden =
                                    abierto;

                            }
                        );


                        boton.classList.toggle(
                            "abierto",
                            !abierto
                        );


                        boton.title =
                            abierto
                                ? "Mostrar perfiles"
                                : "Ocultar perfiles";

                    }
                );

            }
        );


        // ==========================================
        // GESTIONAR PERFIL
        // ==========================================

        const modalPerfil =
            document.getElementById(
                "modalGestionarPerfil"
            );

        const formGestionPerfil =
            document.getElementById("formGestionPerfil");

        const botonesGestionPerfil =
            document.querySelectorAll(
                ".nube-gestionar-perfil"
            );

        const cerrarGestionPerfil =
            document.getElementById(
                "cerrarGestionPerfil"
            );

        const cancelarGestionPerfil =
            document.getElementById(
                "cancelarGestionPerfil"
            );

        const cerrarPerfilBackdrop =
            document.getElementById(
                "cerrarPerfilBackdrop"
            );

        const tituloGestionPerfil =
            document.getElementById(
                "tituloGestionPerfil"
            );

        const subtituloGestionPerfil =
            document.getElementById(
                "subtituloGestionPerfil"
            );

        const perfilGestionId =
            document.getElementById(
                "perfilGestionId"
            );

        const perfilGestionCliente =
            document.getElementById(
                "perfilGestionCliente"
            );

        const perfilGestionTelefono =
            document.getElementById(
                "perfilGestionTelefono"
            );

        const perfilGestionPin =
            document.getElementById(
                "perfilGestionPin"
            );

        const perfilGestionEntrega =
            document.getElementById(
                "perfilGestionEntrega"
            );

        const perfilGestionDias =
            document.getElementById(
                "perfilGestionDias"
            );

        const perfilGestionVencimiento =
            document.getElementById(
                "perfilGestionVencimiento"
            );

        const perfilGestionNotas =
            document.getElementById(
                "perfilGestionNotas"
            );

        const mensajeGestionPerfil =
            document.getElementById(
        "mensajeGestionPerfil"
    );

        const mensajeGestionPerfilTexto =
            document.getElementById(
        "mensajeGestionPerfilTexto"
    );



        const abrirCaidaPerfil =
    document.getElementById(
        "abrirCaidaPerfil"
    );

const panelCaidaPerfil =
    document.getElementById(
        "panelCaidaPerfil"
    );

const motivoCaidaPerfil =
    document.getElementById(
        "motivoCaidaPerfil"
    );

const cancelarCaidaPerfil =
    document.getElementById(
        "cancelarCaidaPerfil"
    );

const confirmarCaidaPerfil =
    document.getElementById(
        "confirmarCaidaPerfil"
    );


const grupoReemplazoPerfil =
    document.getElementById(
        "grupoReemplazoPerfil"
    );

const abrirReemplazoPerfil =
    document.getElementById(
        "abrirReemplazoPerfil"
    );

const panelReemplazoPerfil =
    document.getElementById(
        "panelReemplazoPerfil"
    );

const listaReemplazosPerfil =
    document.getElementById(
        "listaReemplazosPerfil"
    );

const cancelarReemplazoPerfil =
    document.getElementById(
        "cancelarReemplazoPerfil"
    );

const confirmarReemplazoPerfil =
    document.getElementById(
        "confirmarReemplazoPerfil"
    );


let perfilReemplazoSeleccionado = null;

const panelMensajeCliente =
    document.getElementById("panelMensajeCliente");
const vistaPreviaMensajeCliente =
    document.getElementById("vistaPreviaMensajeCliente");
const copiarMensajeCliente =
    document.getElementById("copiarMensajeCliente");
const abrirWhatsappCliente =
    document.getElementById("abrirWhatsappCliente");

let mensajeClienteActual = "";
let telefonoClienteActual = "";

function datoEntrega(valor){
    const texto = String(valor ?? "").trim();
    return texto || "—";
}

function construirMensajeCliente(tipo, datos = {}){
    const cliente = datoEntrega(datos.cliente);
    const plataforma = datoEntrega(datos.plataforma);
    const correo = datoEntrega(datos.correo);
    const contrasena = datoEntrega(datos.contrasena);
    const perfil = datoEntrega(datos.nombre_perfil);
    const pin = datoEntrega(datos.pin);
    const vencimiento = datoEntrega(datos.fecha_vencimiento);

    if (tipo === "reemplazo"){
        return `🛡️ GARANTÍA REALIZADA
PECHY PLAYERS

Hola ${cliente} 👋

Tu perfil anterior presentó un inconveniente y realizamos el reemplazo.

✅ No perdiste tus días de servicio.

🎬 ${plataforma}

📧 Nuevo correo:
${correo}

🔐 Nueva contraseña:
${contrasena}

👤 Nuevo perfil:
${perfil}

🔢 Nuevo PIN:
${pin}

📅 Tu servicio continúa hasta:
${vencimiento}

⚠️ Desde ahora utiliza únicamente estos nuevos datos.

Si tienes alguna duda o inconveniente, escríbenos y con gusto te ayudamos.

PECHY PLAYERS 🔥`;
    }

    if (tipo === "renovacion"){
        return `♻️ RENOVACIÓN CONFIRMADA
PECHY PLAYERS

Hola ${cliente} 👋

Tu servicio de ${plataforma} fue renovado correctamente.

📧 Correo:
${correo}

🔐 Contraseña:
${contrasena}

👤 Perfil:
${perfil}

🔢 PIN:
${pin}

📅 Nuevo vencimiento:
${vencimiento}

✅ Tu servicio continúa activo.

⚠️ Recuerda:
No cambies el correo, contraseña ni PIN del perfil.

Si tienes alguna duda o inconveniente, escríbenos y con gusto te ayudamos.

Gracias por seguir confiando en PECHY PLAYERS 🔥`;
    }

    return `🔥 PECHY PLAYERS

Hola ${cliente} 👋
Tu servicio ya está listo.

🎬 ${plataforma}

📧 Correo:
${correo}

🔐 Contraseña:
${contrasena}

👤 Perfil:
${perfil}

🔢 PIN:
${pin}

📅 Vencimiento:
${vencimiento}

📱 Uso permitido:
1 dispositivo

⚠️ IMPORTANTE
No cambies el correo, contraseña ni PIN del perfil.

Si tienes alguna duda o inconveniente, escríbenos y estaremos atentos para ayudarte.

Gracias por confiar en PECHY PLAYERS 🔥
Agréganos a tus contactos para que puedas ver nuestras promociones y novedades.`;
}

function normalizarTelefonoWhatsapp(telefono){
    let numero = String(telefono ?? "").replace(/\D/g, "");
    if (/^3\d{9}$/.test(numero)) numero = `57${numero}`;
    return numero;
}

function mostrarPanelMensajeCliente(tipo, datos){
    if (!panelMensajeCliente || !vistaPreviaMensajeCliente) return;
    mensajeClienteActual = construirMensajeCliente(tipo, datos);
    telefonoClienteActual = normalizarTelefonoWhatsapp(datos?.telefono);
    vistaPreviaMensajeCliente.textContent = mensajeClienteActual;
    abrirWhatsappCliente.disabled = !telefonoClienteActual;
    panelMensajeCliente.hidden = false;
}

copiarMensajeCliente?.addEventListener("click", async () => {
    try {
        if (navigator.clipboard?.writeText){
            await navigator.clipboard.writeText(mensajeClienteActual);
        } else {
            const auxiliar = document.createElement("textarea");
            auxiliar.value = mensajeClienteActual;
            auxiliar.setAttribute("readonly", "");
            auxiliar.style.position = "fixed";
            auxiliar.style.opacity = "0";
            document.body.appendChild(auxiliar);
            auxiliar.select();
            const copiado = document.execCommand("copy");
            auxiliar.remove();
            if (!copiado) throw new Error("Copia no disponible");
        }
        mostrarMensajePerfil("Mensaje copiado al portapapeles.");
    } catch (error) {
        console.error(error);
        mostrarMensajePerfil("No se pudo copiar el mensaje.", "error");
    }
});

abrirWhatsappCliente?.addEventListener("click", () => {
    if (!telefonoClienteActual || !mensajeClienteActual) return;
    const url = `https://wa.me/${telefonoClienteActual}?text=${encodeURIComponent(mensajeClienteActual)}`;
    window.open(url, "_blank", "noopener,noreferrer");
});


function mostrarMensajePerfil(
    mensaje,
    tipo = "ok"
){

    if (
        !mensajeGestionPerfil ||
        !mensajeGestionPerfilTexto
    ){
        return;
    }


    mensajeGestionPerfilTexto.textContent =
        mensaje;


    mensajeGestionPerfil.classList.toggle(
        "error",
        tipo === "error"
    );


    mensajeGestionPerfil.hidden = false;

}




        const diasRenovacionPerfil =
    document.getElementById(
        "diasRenovacionPerfil"
    );

const renovarPerfil =
    document.getElementById(
        "renovarPerfil"
    );


        function abrirGestionPerfil(
            boton
        ){

            if (!modalPerfil) return;


            const datos =
                boton.dataset;


            perfilGestionId.value =
                datos.id || "";

            perfilGestionCliente.value =
                datos.cliente || "";

            perfilGestionTelefono.value =
                datos.telefono || "";

            perfilGestionPin.value =
                datos.pin || "";

            perfilGestionEntrega.value =
                datos.entrega || "";

            perfilGestionDias.value =
                datos.dias || "";

            perfilGestionVencimiento.value =
                datos.vencimiento || "Sin vencimiento";

            perfilGestionNotas.value =
                datos.notas || "";


            tituloGestionPerfil.textContent =
                datos.nombre ||
                "Gestionar perfil";

            subtituloGestionPerfil.textContent =
                `${datos.plataforma || "Cuenta"} · ${datos.estado || "disponible"}`;



if (
    grupoReemplazoPerfil
){

    grupoReemplazoPerfil.hidden =
        datos.estado !== "caida";

}


if (
    panelReemplazoPerfil
){

    panelReemplazoPerfil.hidden =
        true;

}


if (
    listaReemplazosPerfil
){

    listaReemplazosPerfil.innerHTML =
        "";

}


perfilReemplazoSeleccionado =
    null;


if (
    confirmarReemplazoPerfil
){

    confirmarReemplazoPerfil.disabled =
        true;

}



if (
    mensajeGestionPerfil
){

    mensajeGestionPerfil.hidden = true;

    mensajeGestionPerfil.classList.remove(
        "error"
    );

}

if (panelMensajeCliente){
    panelMensajeCliente.hidden = true;
    mensajeClienteActual = "";
    telefonoClienteActual = "";
}


if (panelCaidaPerfil){
    panelCaidaPerfil.hidden = true;
}

if (abrirCaidaPerfil){
    abrirCaidaPerfil.hidden = false;
}

if (motivoCaidaPerfil){
    motivoCaidaPerfil.value = "";
}

            modalPerfil.classList.add(
                "abierto"
            );

            modalPerfil.setAttribute(
                "aria-hidden",
                "false"
            );

            document.body.classList.add(
                "nube-modal-abierto"
            );

        }


        function cerrarModalPerfil(){

            if (!modalPerfil) return;


            modalPerfil.classList.remove(
                "abierto"
            );

            modalPerfil.setAttribute(
                "aria-hidden",
                "true"
            );

            document.body.classList.remove(
                "nube-modal-abierto"
            );

        }


        botonesGestionPerfil.forEach(
            boton => {

                boton.addEventListener(
                    "click",
                    () => {

                        abrirGestionPerfil(
                            boton
                        );

                    }
                );

            }
        );





        cerrarGestionPerfil?.addEventListener(
            "click",
            cerrarModalPerfil
        );


        cancelarGestionPerfil?.addEventListener(
            "click",
            cerrarModalPerfil
        );


        cerrarPerfilBackdrop?.addEventListener(
            "click",
            cerrarModalPerfil
        );


        formGestionPerfil?.addEventListener(
            "submit",
            event => {
                event.preventDefault();

                const botonGuardar =
                    formGestionPerfil.querySelector("button[type='submit']");

                if (botonGuardar) botonGuardar.disabled = true;

                fetch(formGestionPerfil.action, {
                    method: "POST",
                    headers: {
                        "X-Requested-With": "XMLHttpRequest"
                    },
                    body: new FormData(formGestionPerfil)
                })
                .then(async respuesta => {
                    const resultado = await respuesta.json();
                    if (!respuesta.ok || !resultado.ok){
                        throw new Error(
                            resultado.mensaje ||
                            "No se pudo guardar el perfil."
                        );
                    }
                    return resultado;
                })
                .then(resultado => {
                    if (perfilGestionVencimiento){
                        perfilGestionVencimiento.value =
                            resultado.fecha_vencimiento || "Sin vencimiento";
                    }

                    mostrarMensajePerfil(resultado.mensaje);

                    if (resultado.datos_entrega){
                        mostrarPanelMensajeCliente(
                            "venta",
                            resultado.datos_entrega
                        );
                    }
                })
                .catch(error => {
                    mostrarMensajePerfil(error.message, "error");
                })
                .finally(() => {
                    if (botonGuardar) botonGuardar.disabled = false;
                });
            }
        );


        // ==========================================
        // PREPARAR RENOVACIÓN DE PERFIL
        // ==========================================

        renovarPerfil?.addEventListener(
            "click",
            () => {

                const perfilId =
                    perfilGestionId?.value || "";

                const dias =
                    Number(
                        diasRenovacionPerfil?.value || 0
                    );


                if (!perfilId){

                    alert(
                        "No se pudo identificar el perfil."
                    );

                    return;
                }


                if (dias <= 0){

                    alert(
                        "Indica cuántos días deseas renovar."
                    );

                    return;
                }


                const confirmar =
                    window.confirm(
                        `¿Renovar este perfil por ${dias} días?`
                    );


                if (!confirmar){

                    return;
                }


                // Por ahora comprobamos únicamente
                // que el botón y los datos funcionan.

                                fetch(
                    "/admin/nube-cuentas/perfil/renovar",
                    {
                        method: "POST",

                        headers: {
                            "Content-Type":
                                "application/json"
                        },

                        body: JSON.stringify({
                            perfil_id:
                                perfilId,

                            dias:
                                dias
                        })
                    }
                )
                .then(
                    respuesta =>
                        respuesta.json()
                )
                .then(
                    resultado => {

                       if (
    !resultado.ok
){

    mostrarMensajePerfil(
        resultado.mensaje ||
        "No se pudo renovar el perfil.",
        "error"
    );

    return;
}


// ==========================================
// ACTUALIZAR MODAL INMEDIATAMENTE
// ==========================================

if (
    perfilGestionVencimiento &&
    resultado.fecha_vencimiento
){

    perfilGestionVencimiento.value =
        resultado.fecha_vencimiento;

}


if (
    subtituloGestionPerfil &&
    resultado.estado
){

    const plataformaActual =
        subtituloGestionPerfil.textContent
            .split("·")[0]
            .trim();


    subtituloGestionPerfil.textContent =
        `${plataformaActual} · ${resultado.estado}`;

}


// ==========================================
// MENSAJE DE ÉXITO
// ==========================================

mostrarMensajePerfil(
    resultado.mensaje
);

if (resultado.datos_entrega){
    mostrarPanelMensajeCliente(
        "renovacion",
        resultado.datos_entrega
    );
}


// ==========================================
// RECARGAR DESPUÉS
// ==========================================


                    }
                )
                .catch(
                    error => {

                        console.error(
                            error
                        );

                        mostrarMensajePerfil(
    "Ocurrió un error al renovar el perfil.",
    "error"
);

                    }
                );

            }
        );



// ==========================================
// MARCAR PERFIL COMO CAÍDO
// ==========================================

abrirCaidaPerfil?.addEventListener(
    "click",
    () => {

        if (!panelCaidaPerfil){
            return;
        }

        panelCaidaPerfil.hidden = false;

        abrirCaidaPerfil.hidden = true;

    }
);


cancelarCaidaPerfil?.addEventListener(
    "click",
    () => {

        if (panelCaidaPerfil){
            panelCaidaPerfil.hidden = true;
        }

        if (abrirCaidaPerfil){
            abrirCaidaPerfil.hidden = false;
        }

        if (motivoCaidaPerfil){
            motivoCaidaPerfil.value = "";
        }

    }
);


confirmarCaidaPerfil?.addEventListener(
    "click",
    () => {

        const perfilId =
            perfilGestionId?.value || "";

        const motivo =
            motivoCaidaPerfil?.value.trim() || "";


        if (!perfilId){

            mostrarMensajePerfil(
                "No se pudo identificar el perfil.",
                "error"
            );

            return;
        }


        const confirmar =
            window.confirm(
                "¿Seguro que deseas marcar este perfil como caído?"
            );


        if (!confirmar){

            return;
        }


        fetch(
            "/admin/nube-cuentas/perfil/caido",
            {
                method: "POST",

                headers: {
                    "Content-Type":
                        "application/json"
                },

                body: JSON.stringify({
                    perfil_id:
                        perfilId,

                    motivo:
                        motivo
                })
            }
        )
        .then(
            respuesta =>
                respuesta.json()
        )
        .then(
            resultado => {

                if (!resultado.ok){

                    mostrarMensajePerfil(
                        resultado.mensaje ||
                        "No se pudo marcar el perfil como caído.",
                        "error"
                    );

                    return;
                }


                // ==========================================
                // ACTUALIZAR MODAL
                // ==========================================

                const plataformaActual =
                    subtituloGestionPerfil
                        ?.textContent
                        .split("·")[0]
                        .trim() || "Cuenta";


                if (
                    subtituloGestionPerfil
                ){

                    subtituloGestionPerfil.textContent =
                        `${plataformaActual} · caida`;

                }


                mostrarMensajePerfil(
    resultado.mensaje
);


// ==========================================
// CERRAR PANEL DE CAÍDA
// ==========================================

if (
    panelCaidaPerfil
){

    panelCaidaPerfil.hidden =
        true;

}


if (
    abrirCaidaPerfil
){

    abrirCaidaPerfil.hidden =
        true;

}


// ==========================================
// MOSTRAR REEMPLAZO INMEDIATAMENTE
// ==========================================

if (
    grupoReemplazoPerfil
){

    grupoReemplazoPerfil.hidden =
        false;

}


if (
    panelReemplazoPerfil
){

    panelReemplazoPerfil.hidden =
        true;

}


if (
    listaReemplazosPerfil
){

    listaReemplazosPerfil.innerHTML =
        "";

}


perfilReemplazoSeleccionado =
    null;


if (
    confirmarReemplazoPerfil
){

    confirmarReemplazoPerfil.disabled =
        true;

}

            }
        )
        .catch(
            error => {

                console.error(
                    error
                );


                mostrarMensajePerfil(
                    "Ocurrió un error al marcar el perfil como caído.",
                    "error"
                );

            }
        );

    }
);


// ==========================================
// ABRIR REEMPLAZO DE PERFIL
// ==========================================

abrirReemplazoPerfil?.addEventListener(
    "click",
    () => {

        const perfilId =
            perfilGestionId?.value || "";


        if (!perfilId){

            mostrarMensajePerfil(
                "No se pudo identificar el perfil.",
                "error"
            );

            return;
        }


        panelReemplazoPerfil.hidden =
            false;


        listaReemplazosPerfil.innerHTML =
            `
                <div class="nube-reemplazo-cargando">
                    Buscando perfiles disponibles...
                </div>
            `;


        fetch(
            `/admin/nube-cuentas/perfil/${perfilId}/reemplazos`
        )
        .then(
            respuesta =>
                respuesta.json()
        )
        .then(
            resultado => {

                if (!resultado.ok){

                    throw new Error(
                        resultado.mensaje ||
                        "No se pudieron cargar los reemplazos."
                    );

                }


                listaReemplazosPerfil.innerHTML =
                    "";


                if (
                    !resultado.perfiles ||
                    resultado.perfiles.length === 0
                ){

                    listaReemplazosPerfil.innerHTML =
                        `
                            <div class="nube-reemplazo-vacio">
                                No hay perfiles disponibles
                                de esta plataforma.
                            </div>
                        `;

                    return;
                }


                const etiquetasNivel = {
                    excelente: "Excelente",
                    muy_buena: "Muy buena",
                    buena: "Buena",
                    aceptable: "Aceptable",
                    lejana: "Lejana",
                    cuenta_nueva: "Cuenta nueva"
                };


                const escaparHtml = valor =>
                    String(valor ?? "")
                        .replaceAll("&", "&amp;")
                        .replaceAll("<", "&lt;")
                        .replaceAll(">", "&gt;")
                        .replaceAll('"', "&quot;")
                        .replaceAll("'", "&#039;");


                resultado.perfiles.forEach(
                    (perfil, indice) => {

                        const item =
                            document.createElement(
                                "button"
                            );


                        item.type =
                            "button";


                        item.className =
                            "nube-reemplazo-item";


                        item.dataset.perfilId =
                            perfil.perfil_id;


                        const diferenciaTexto =
                            perfil.diferencia_dias === null
                                ? "Sin ciclo previo"
                                : `${perfil.diferencia_dias} días de diferencia`;


                        const referenciaTexto =
                            perfil.fecha_referencia_cuenta ||
                            "Cuenta sin ventas activas";


                        const nivelTexto =
                            etiquetasNivel[
                                perfil.nivel_recomendacion
                            ] || perfil.nivel_recomendacion;


                        item.innerHTML =
                            `
                                <div class="nube-reemplazo-item-principal">

                                    ${indice === 0 ? `
                                        <span class="nube-reemplazo-mejor">
                                            MEJOR OPCIÓN
                                        </span>
                                    ` : ""}

                                    <strong>
                                        ${escaparHtml(perfil.correo)}
                                    </strong>

                                    <span>
                                        ${escaparHtml(perfil.nombre_perfil)} ·
                                        PIN ${escaparHtml(perfil.pin || "—")}
                                    </span>

                                    <small>
                                        Ciclo ${escaparHtml(referenciaTexto)} ·
                                        ${perfil.cantidad_perfiles_ocupados} ocupados ·
                                        ${perfil.cantidad_perfiles_disponibles} disponibles
                                    </small>

                                </div>


                                <div class="nube-reemplazo-item-meta">

                                    <span class="nube-reemplazo-nivel nube-reemplazo-nivel-${escaparHtml(perfil.nivel_recomendacion)}">
                                        ${escaparHtml(nivelTexto)}
                                    </span>

                                    <span>
                                        ${escaparHtml(diferenciaTexto)}
                                    </span>

                                </div>
                            `;


                        item.addEventListener(
                            "click",
                            () => {

                                document
                                    .querySelectorAll(
                                        ".nube-reemplazo-item"
                                    )
                                    .forEach(
                                        otro =>
                                            otro.classList.remove(
                                                "seleccionado"
                                            )
                                    );


                                item.classList.add(
                                    "seleccionado"
                                );


                                perfilReemplazoSeleccionado =
                                    Number(
                                        perfil.perfil_id
                                    );


                                confirmarReemplazoPerfil.disabled =
                                    false;

                            }
                        );


                        listaReemplazosPerfil.appendChild(
                            item
                        );

                    }
                );

            }
        )
        .catch(
            error => {

                console.error(
                    error
                );


                listaReemplazosPerfil.innerHTML =
                    `
                        <div class="nube-reemplazo-vacio">
                            No se pudieron cargar
                            los perfiles disponibles.
                        </div>
                    `;

            }
        );

    }
);


cancelarReemplazoPerfil?.addEventListener(
    "click",
    () => {

        panelReemplazoPerfil.hidden =
            true;


        perfilReemplazoSeleccionado =
            null;


        if (
            confirmarReemplazoPerfil
        ){

            confirmarReemplazoPerfil.disabled =
                true;

        }

    }
);



// ==========================================
// CONFIRMAR REEMPLAZO REAL
// ==========================================

confirmarReemplazoPerfil?.addEventListener(
    "click",
    () => {

        const perfilAnteriorId =
            perfilGestionId?.value || "";

        const perfilNuevoId =
            perfilReemplazoSeleccionado;


        if (
            !perfilAnteriorId ||
            !perfilNuevoId
        ){

            mostrarMensajePerfil(
                "Selecciona un perfil de reemplazo.",
                "error"
            );

            return;
        }


        const confirmar =
            window.confirm(
                "¿Confirmas el reemplazo de este perfil?"
            );


        if (!confirmar){

            return;
        }


        fetch(
            "/admin/nube-cuentas/perfil/reemplazar",
            {
                method: "POST",

                headers: {
                    "Content-Type":
                        "application/json"
                },

                body: JSON.stringify({

                    perfil_anterior_id:
                        perfilAnteriorId,

                    perfil_nuevo_id:
                        perfilNuevoId,

                    motivo:
                        motivoCaidaPerfil?.value.trim() || ""

                })
            }
        )
        .then(
            respuesta =>
                respuesta.json()
        )
        .then(
            resultado => {

                if (!resultado.ok){

                    mostrarMensajePerfil(
                        resultado.mensaje ||
                        "No se pudo realizar el reemplazo.",
                        "error"
                    );

                    return;
                }


                // ==========================================
                // ACTUALIZAR EL MODAL
                // ==========================================

                if (
                    subtituloGestionPerfil
                ){

                    const plataformaActual =
                        subtituloGestionPerfil
                            .textContent
                            .split("·")[0]
                            .trim();


                    subtituloGestionPerfil.textContent =
                        `${plataformaActual} · reemplazada`;

                }


                if (
                    panelReemplazoPerfil
                ){

                    panelReemplazoPerfil.hidden =
                        true;

                }


                if (
                    grupoReemplazoPerfil
                ){

                    grupoReemplazoPerfil.hidden =
                        true;

                }


                if (
                    abrirCaidaPerfil
                ){

                    abrirCaidaPerfil.hidden =
                        true;

                }


                mostrarMensajePerfil(
                    `${resultado.mensaje} El cliente conserva ${resultado.dias_restantes} días.`
                );

                if (resultado.datos_entrega){
                    mostrarPanelMensajeCliente(
                        "reemplazo",
                        resultado.datos_entrega
                    );
                }


                // ==========================================
                // RECARGAR LA NUBE
                // ==========================================

            }
        )
        .catch(
            error => {

                console.error(
                    error
                );


                mostrarMensajePerfil(
                    "Ocurrió un error al reemplazar el perfil.",
                    "error"
                );

            }
        );

    }
);



 // ==========================================
 // // ESCAPE — MODAL / DRAWER
 // ==========================================

        document.addEventListener(
            "keydown",
            event => {

                if (
                    event.key !==
                    "Escape"
                ){

                    return;

                }


                if (
                    modal?.classList.contains(
                        "abierto"
                    )
                ){

                    cerrarModal();

                }


                if (
                    drawer?.classList.contains(
                        "abierto"
                    )
                ){

                    cerrarPanelCuenta();

                }

                                if (
                    modalPerfil?.classList.contains(
                        "abierto"
                    )
                ){

                    cerrarModalPerfil();

                }

            }
        );

    }

    
);

