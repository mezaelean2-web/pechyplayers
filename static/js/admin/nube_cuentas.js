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

        const tabGestionPerfil =
            document.getElementById("tabGestionPerfil");

        const tabHistorialPerfil =
            document.getElementById("tabHistorialPerfil");

        const vistaHistorialPerfil =
            document.getElementById("vistaHistorialPerfil");

        const contenidoHistorialPerfil =
            document.getElementById("contenidoHistorialPerfil");

        const guardarGestionPerfil =
            formGestionPerfil?.querySelector("button[type='submit']");

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

const grupoLiberacionPerfil = document.getElementById("grupoLiberacionPerfil");
const abrirLiberacionPerfil = document.getElementById("abrirLiberacionPerfil");
const panelLiberacionPerfil = document.getElementById("panelLiberacionPerfil");
const contenidoLiberacionPerfil = document.getElementById("contenidoLiberacionPerfil");
const exitoLiberacionPerfil = document.getElementById("exitoLiberacionPerfil");
const motivoLiberacionPerfil = document.getElementById("motivoLiberacionPerfil");
const cancelarLiberacionPerfil = document.getElementById("cancelarLiberacionPerfil");
const confirmarLiberacionPerfil = document.getElementById("confirmarLiberacionPerfil");
const liberacionCliente = document.getElementById("liberacionCliente");
const liberacionServicio = document.getElementById("liberacionServicio");
const liberacionVencimiento = document.getElementById("liberacionVencimiento");
const liberacionDias = document.getElementById("liberacionDias");
const elegirLiberarPerfil = document.getElementById("elegirLiberarPerfil");
const elegirTrasladarPerfil = document.getElementById("elegirTrasladarPerfil");
const elegirDestinoNuevo = document.getElementById("elegirDestinoNuevo");
const elegirDestinoActivo = document.getElementById("elegirDestinoActivo");
const panelTrasladoPerfil = document.getElementById("panelTrasladoPerfil");
const trasladoDiasDisponibles = document.getElementById("trasladoDiasDisponibles");
const diasTrasladarPerfil = document.getElementById("diasTrasladarPerfil");
const plataformaDestinoPerfil = document.getElementById("plataformaDestinoPerfil");
const campoPlataformaDestino = document.getElementById("campoPlataformaDestino");
const listaDestinosTraslado = document.getElementById("listaDestinosTraslado");
const resumenTrasladoPerfil = document.getElementById("resumenTrasladoPerfil");
const trasladoResumenOrigen = document.getElementById("trasladoResumenOrigen");
const trasladoResumenDestino = document.getElementById("trasladoResumenDestino");
const trasladoResumenCliente = document.getElementById("trasladoResumenCliente");
const trasladoResumenDias = document.getElementById("trasladoResumenDias");
const trasladoResumenVencimiento = document.getElementById("trasladoResumenVencimiento");
const filaVencimientoActual = document.getElementById("filaVencimientoActual");
const trasladoResumenVencimientoActual = document.getElementById("trasladoResumenVencimientoActual");
const advertenciaLiberacionPerfil = document.getElementById("advertenciaLiberacionPerfil");
const grupoRenovacionPerfil = document.querySelector(".nube-renovacion-rapida");

let operacionLiberacionUuid = "";
let accionLiberacionPerfil = "liberar";
let contextoLiberacionPerfil = null;
let perfilDestinoTraslado = null;
let destinoTrasladoTipo = "nuevo";

function crearOperacionUuid(){
    if (window.crypto?.randomUUID) return window.crypto.randomUUID();
    return `liberar-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function esFechaOperativaValida(valor){
    if (!/^\d{4}-\d{2}-\d{2}$/.test(valor || "")) return false;
    const fecha = new Date(`${valor}T00:00:00Z`);
    return !Number.isNaN(fecha.getTime()) &&
        fecha.toISOString().slice(0, 10) === valor;
}


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
let operacionCompletada = false;

function establecerOperacionCompletada(completada){
    operacionCompletada = Boolean(completada);

    if (guardarGestionPerfil){
        guardarGestionPerfil.type = operacionCompletada
            ? "button"
            : "submit";
    }
}

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

    if (tipo === "cambio_servicio"){
        return `🔄 CAMBIO DE SERVICIO
PECHY PLAYERS

Hola ${cliente} 👋

Tu servicio fue cambiado correctamente.

Servicio anterior:
${datoEntrega(datos.plataforma_origen)}

Nuevo servicio:
${datoEntrega(datos.plataforma_destino)}

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

✅ Se trasladaron ${datoEntrega(datos.dias_trasladados)} días.

⚠️ Desde ahora utiliza únicamente estos nuevos datos.

Si tienes alguna duda o inconveniente, escríbenos y con gusto te ayudamos.

PECHY PLAYERS 🔥`;
    }

    if (tipo === "dias_trasladados"){
        return `♻️ DÍAS TRASLADADOS
PECHY PLAYERS

Hola ${cliente} 👋

Los días restantes de tu servicio anterior fueron trasladados correctamente.

Servicio anterior:
${datoEntrega(datos.plataforma_origen)}

Servicio que recibió los días:
${datoEntrega(datos.plataforma_destino)}

📧 Correo:
${correo}

🔐 Contraseña:
${contrasena}

👤 Perfil:
${perfil}

🔢 PIN:
${pin}

✅ Días agregados:
${datoEntrega(datos.dias_trasladados)}

📅 Nuevo vencimiento:
${datoEntrega(datos.nuevo_vencimiento || datos.fecha_vencimiento)}

Tu servicio continúa activo con normalidad.

PECHY PLAYERS 🔥`;
    }

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
    establecerOperacionCompletada(true);
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


function fechaTrasladoCalculada(dias){
    const fecha = new Date();
    fecha.setHours(12, 0, 0, 0);
    fecha.setDate(fecha.getDate() + Number(dias || 0));
    const ano = fecha.getFullYear();
    const mes = String(fecha.getMonth() + 1).padStart(2, "0");
    const dia = String(fecha.getDate()).padStart(2, "0");
    return `${ano}-${mes}-${dia}`;
}

function fechaExtensionCalculada(fechaActual, dias){
    if (!esFechaOperativaValida(fechaActual)) return "—";
    const fecha = new Date(`${fechaActual}T12:00:00`);
    fecha.setDate(fecha.getDate() + Number(dias || 0));
    return fecha.toISOString().slice(0, 10);
}

function escaparHtmlTraslado(valor){
    return String(valor ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}

function actualizarResumenTraslado(){
    if (!resumenTrasladoPerfil) return;
    const dias = Number(diasTrasladarPerfil?.value || 0);
    const maximo = Number(contextoLiberacionPerfil?.dias_restantes || 0);
    const valido = perfilDestinoTraslado && dias >= 1 && dias <= maximo;
    resumenTrasladoPerfil.hidden = !valido;
    if (!valido) return;

    trasladoResumenOrigen.textContent =
        `${contextoLiberacionPerfil.plataforma} · ${contextoLiberacionPerfil.perfil}`;
    trasladoResumenDestino.textContent =
        `${perfilDestinoTraslado.plataforma} · ${perfilDestinoTraslado.nombre_perfil}`;
    trasladoResumenCliente.textContent = contextoLiberacionPerfil.cliente || "—";
    trasladoResumenDias.textContent = String(dias);
    const activo = destinoTrasladoTipo === "activo";
    if (filaVencimientoActual) filaVencimientoActual.hidden = !activo;
    if (trasladoResumenVencimientoActual){
        trasladoResumenVencimientoActual.textContent = activo
            ? perfilDestinoTraslado.fecha_vencimiento
            : "—";
    }
    trasladoResumenVencimiento.textContent = activo
        ? fechaExtensionCalculada(perfilDestinoTraslado.fecha_vencimiento, dias)
        : fechaTrasladoCalculada(dias);
}

function renderizarDestinosTraslado(){
    if (!listaDestinosTraslado) return;
    const plataforma = plataformaDestinoPerfil?.value || "";
    const perfilSeleccionadoId = perfilDestinoTraslado?.perfil_id;
    perfilDestinoTraslado = null;
    actualizarResumenTraslado();
    listaDestinosTraslado.innerHTML = "";
    const activos = destinoTrasladoTipo === "activo";
    if (!activos && !plataforma) return;
    const candidatos = activos
        ? (contextoLiberacionPerfil?.servicios_activos_cliente || [])
        : (contextoLiberacionPerfil?.perfiles_destino || [])
            .filter(perfil => perfil.plataforma === plataforma);
    if (!candidatos.length){
        listaDestinosTraslado.innerHTML =
            `<div class="nube-reemplazo-vacio">${activos
                ? "No hay servicios activos seguros para este cliente."
                : "No hay perfiles disponibles."}</div>`;
        return;
    }

    candidatos.forEach((perfil, indice) => {
        const diferencia = perfil.diferencia_dias == null
            ? "Cuenta nueva"
            : `${perfil.diferencia_dias} días de diferencia`;
        const ciclo = perfil.fecha_referencia_cuenta || "Sin ciclo activo";
        const item = document.createElement("button");
        item.type = "button";
        item.className = "nube-reemplazo-item";
        item.innerHTML = `
            <div class="nube-reemplazo-item-principal">
                <strong>${escaparHtmlTraslado(activos ? perfil.plataforma : perfil.correo)}</strong>
                ${!activos && indice === 0 ? '<span class="nube-reemplazo-mejor">MEJOR OPCIÓN</span>' : ""}
                ${activos ? `<span>${escaparHtmlTraslado(perfil.correo)}</span>` : ""}
                <span>${escaparHtmlTraslado(perfil.nombre_perfil)} · PIN ${escaparHtmlTraslado(perfil.pin || "—")}</span>
            </div>
            <div class="nube-reemplazo-item-meta">
                ${activos ? `<span>Vence actualmente: ${escaparHtmlTraslado(perfil.fecha_vencimiento)}</span>
                    <span>+ ${escaparHtmlTraslado(diasTrasladarPerfil?.value || 0)} días</span>
                    <span>Nuevo vencimiento: ${escaparHtmlTraslado(fechaExtensionCalculada(perfil.fecha_vencimiento, diasTrasladarPerfil?.value))}</span>`
                    : `<span>Ciclo ${escaparHtmlTraslado(ciclo)}</span><span>${escaparHtmlTraslado(diferencia)}</span>`}
                ${!activos ? `<span class="nube-reemplazo-nivel nube-reemplazo-nivel-${escaparHtmlTraslado(perfil.nivel_recomendacion)}">
                    ${escaparHtmlTraslado(String(perfil.nivel_recomendacion || "").replaceAll("_", " "))}
                </span>` : ""}
            </div>`;
        item.addEventListener("click", () => {
            listaDestinosTraslado
                .querySelectorAll(".nube-reemplazo-item")
                .forEach(elemento => elemento.classList.remove("seleccionado"));
            item.classList.add("seleccionado");
            perfilDestinoTraslado = perfil;
            actualizarResumenTraslado();
        });
        if (perfil.perfil_id === perfilSeleccionadoId){
            item.classList.add("seleccionado");
            perfilDestinoTraslado = perfil;
        }
        listaDestinosTraslado.appendChild(item);
    });
    actualizarResumenTraslado();
}

function seleccionarTipoDestinoTraslado(tipo){
    destinoTrasladoTipo = tipo;
    elegirDestinoNuevo?.classList.toggle("seleccionado", tipo === "nuevo");
    elegirDestinoActivo?.classList.toggle("seleccionado", tipo === "activo");
    if (campoPlataformaDestino) campoPlataformaDestino.hidden = tipo === "activo";
    accionLiberacionPerfil = tipo === "activo" ? "sumar_activo" : "trasladar_nuevo";
    renderizarDestinosTraslado();
    if (advertenciaLiberacionPerfil){
        advertenciaLiberacionPerfil.textContent = tipo === "activo"
            ? "El servicio origen volverá a disponible y los días se sumarán al servicio seleccionado."
            : "El perfil origen volverá a disponible y el cliente pasará al nuevo servicio.";
    }
}

function seleccionarAccionLiberacion(accion){
    accionLiberacionPerfil = accion;
    const trasladar = accion !== "liberar";
    elegirLiberarPerfil?.classList.toggle("seleccionado", !trasladar);
    elegirTrasladarPerfil?.classList.toggle("seleccionado", trasladar);
    if (panelTrasladoPerfil) panelTrasladoPerfil.hidden = !trasladar;
    if (advertenciaLiberacionPerfil){
        advertenciaLiberacionPerfil.innerHTML = trasladar
            ? "El perfil origen volverá a disponible y el cliente pasará al nuevo servicio."
            : "Este perfil volverá a disponible.<br>La venta anterior quedará guardada en el historial.<br>No se trasladarán días a otro servicio.";
    }
    if (trasladar) seleccionarTipoDestinoTraslado(destinoTrasladoTipo);
}

function resetearTrasladoPerfil(){
    contextoLiberacionPerfil = null;
    perfilDestinoTraslado = null;
    destinoTrasladoTipo = "nuevo";
    seleccionarAccionLiberacion("liberar");
    if (diasTrasladarPerfil) diasTrasladarPerfil.value = "";
    if (trasladoDiasDisponibles) trasladoDiasDisponibles.textContent = "0";
    if (plataformaDestinoPerfil){
        plataformaDestinoPerfil.innerHTML =
            '<option value="">Selecciona una plataforma</option>';
    }
    if (listaDestinosTraslado) listaDestinosTraslado.innerHTML = "";
    if (resumenTrasladoPerfil) resumenTrasladoPerfil.hidden = true;
}

elegirLiberarPerfil?.addEventListener(
    "click",
    () => seleccionarAccionLiberacion("liberar")
);
elegirTrasladarPerfil?.addEventListener(
    "click",
    () => seleccionarAccionLiberacion("trasladar_nuevo")
);
elegirDestinoNuevo?.addEventListener("click", () => seleccionarTipoDestinoTraslado("nuevo"));
elegirDestinoActivo?.addEventListener("click", () => seleccionarTipoDestinoTraslado("activo"));
plataformaDestinoPerfil?.addEventListener("change", renderizarDestinosTraslado);
diasTrasladarPerfil?.addEventListener("input", () => {
    if (destinoTrasladoTipo === "activo") renderizarDestinosTraslado();
    else actualizarResumenTraslado();
});


const configuracionEventosHistorial = {
    venta: {
        clase: "venta",
        icono: "user-check"
    },
    renovacion: {
        clase: "renovacion",
        icono: "refresh-cw"
    },
    caida: {
        clase: "caida",
        icono: "triangle-alert"
    },
    reemplazo: {
        clase: "reemplazo",
        icono: "repeat-2"
    },
    liberacion: {
        clase: "liberacion",
        icono: "unlock"
    },
    traslado_nuevo_servicio: {
        clase: "traslado",
        icono: "arrow-right-left"
    },
    traslado_servicio_activo: {
        clase: "traslado-activo",
        icono: "calendar-plus"
    },
    creacion_cuenta: {
        clase: "neutral",
        icono: "cloud"
    }
};

let historialPerfilCargadoId = "";
let historialPerfilAbortController = null;

function textoHistorial(valor, alternativo = "—"){
    if (valor === 0) return "0";
    const texto = String(valor ?? "").trim();
    return texto || alternativo;
}

function formatearFechaHistorial(valor){
    const texto = String(valor ?? "").trim();
    if (!texto) return "Fecha no disponible";

    const normalizado = texto.includes("T")
        ? texto
        : texto.includes(" ")
            ? texto.replace(" ", "T")
            : `${texto}T12:00:00`;
    const fecha = new Date(normalizado);
    if (Number.isNaN(fecha.getTime())) return texto;

    return new Intl.DateTimeFormat("es-CO", {
        dateStyle: "medium",
        timeStyle: texto.length > 10 ? "short" : undefined
    }).format(fecha);
}

function etiquetaServicioHistorial(datos){
    if (!datos || typeof datos !== "object") return "—";
    return [datos.plataforma, datos.nombre_perfil]
        .map(valor => String(valor ?? "").trim())
        .filter(Boolean)
        .join(" · ") || "—";
}

function detallesEventoHistorial(evento){
    const datos = evento?.datos || {};
    const origen = datos.origen || {};
    const antes = datos.destino_antes || {};
    const despues = datos.destino_despues || {};

    switch (evento?.tipo){
        case "venta":
            return [
                ["Cliente", datos.cliente],
                ["Días", datos.dias],
                ["Vence", datos.fecha_vencimiento]
            ];
        case "renovacion":
            return [
                ["Días agregados", datos.dias_agregados ?? datos.dias],
                ["Vencimiento anterior", datos.vencimiento_anterior],
                ["Nuevo vencimiento", datos.nuevo_vencimiento]
            ];
        case "caida":
            return [
                ["Cliente", datos.cliente],
                ["Estado anterior", datos.estado_anterior],
                ["Estado nuevo", datos.estado_nuevo]
            ];
        case "reemplazo":
            return [
                ["Origen", `${textoHistorial(datos.plataforma_origen, "")} · ${textoHistorial(datos.perfil_origen, "")}`],
                ["Destino", `${textoHistorial(datos.plataforma_destino, "")} · ${textoHistorial(datos.perfil_destino, "")}`],
                ["Cliente", datos.cliente],
                ["Vencimiento preservado", datos.vencimiento_preservado],
                ["Motivo", datos.motivo]
            ];
        case "liberacion":
            return [
                ["Cliente anterior", origen.cliente],
                ["Días restantes", datos.dias_disponibles ?? origen.dias_restantes],
                ["Motivo", datos.motivo]
            ];
        case "traslado_nuevo_servicio":
            return [
                ["Origen", etiquetaServicioHistorial(origen)],
                ["Destino", etiquetaServicioHistorial(despues)],
                ["Días trasladados", datos.dias_trasladados],
                ["Nuevo vencimiento", despues.fecha_vencimiento],
                ["Motivo", datos.motivo]
            ];
        case "traslado_servicio_activo":
            return [
                ["Origen", etiquetaServicioHistorial(origen)],
                ["Destino", etiquetaServicioHistorial(despues)],
                ["Días agregados", datos.dias_trasladados],
                ["Vencimiento anterior", antes.fecha_vencimiento],
                ["Nuevo vencimiento", despues.fecha_vencimiento],
                ["Motivo", datos.motivo]
            ];
        default:
            return [];
    }
}

function esTrasladoHistorial(evento){
    return evento?.tipo === "traslado_nuevo_servicio" ||
        evento?.tipo === "traslado_servicio_activo";
}

function crearRutaTrasladoHistorial(evento){
    const datos = evento?.datos || {};
    const perfilEsOrigen = datos.rol_perfil === "origen";
    const perfilEsDestino = datos.rol_perfil === "destino";
    if (!perfilEsOrigen && !perfilEsDestino) return null;

    const bloque = document.createElement("section");
    bloque.className = "nube-historial-traslado";

    const contexto = document.createElement("strong");
    contexto.className = "nube-historial-traslado-contexto";
    contexto.textContent = perfilEsOrigen
        ? "Servicio trasladado desde este perfil"
        : "Este perfil recibió un traslado";

    const ruta = document.createElement("div");
    ruta.className = "nube-historial-traslado-ruta";
    [
        ["ORIGEN", perfilEsOrigen, etiquetaServicioHistorial(datos.origen)],
        ["DESTINO", perfilEsDestino, etiquetaServicioHistorial(datos.destino_despues)]
    ].forEach(([rol, esActual, servicio]) => {
        const extremo = document.createElement("div");
        extremo.className = `nube-historial-traslado-extremo${esActual ? " es-actual" : ""}`;

        const etiquetas = document.createElement("div");
        const etiquetaRol = document.createElement("span");
        etiquetaRol.className = "nube-historial-traslado-badge";
        etiquetaRol.textContent = rol;
        etiquetas.appendChild(etiquetaRol);
        if (esActual){
            const etiquetaActual = document.createElement("span");
            etiquetaActual.className = "nube-historial-traslado-badge es-perfil";
            etiquetaActual.textContent = "ESTE PERFIL";
            etiquetas.appendChild(etiquetaActual);
        }

        const valor = document.createElement("strong");
        valor.textContent = esActual ? "Este perfil" : servicio;
        extremo.append(etiquetas, valor);
        ruta.appendChild(extremo);
    });

    bloque.append(contexto, ruta);
    return bloque;
}

function crearEstadoHistorial(icono, titulo, descripcion, clase = ""){
    const estado = document.createElement("div");
    estado.className = `nube-historial-estado ${clase}`.trim();

    const elementoIcono = document.createElement("i");
    elementoIcono.setAttribute("data-lucide", icono);
    const fuerte = document.createElement("strong");
    fuerte.textContent = titulo;
    const texto = document.createElement("span");
    texto.textContent = descripcion;

    estado.append(elementoIcono, fuerte, texto);
    return estado;
}

function mostrarCargaHistorial(){
    if (!contenidoHistorialPerfil) return;
    const carga = document.createElement("div");
    carga.className = "nube-historial-skeleton";
    carga.setAttribute("aria-label", "Cargando historial");

    for (let indice = 0; indice < 3; indice += 1){
        const fila = document.createElement("div");
        const punto = document.createElement("span");
        const lineas = document.createElement("div");
        lineas.append(document.createElement("i"), document.createElement("i"));
        fila.append(punto, lineas);
        carga.appendChild(fila);
    }
    contenidoHistorialPerfil.replaceChildren(carga);
}

function renderizarHistorialPerfil(resultado){
    if (!contenidoHistorialPerfil) return;
    const fragmento = document.createDocumentFragment();
    const perfil = resultado?.perfil || {};
    const eventos = Array.isArray(resultado?.eventos) ? resultado.eventos : [];

    const resumen = document.createElement("header");
    resumen.className = "nube-historial-resumen";
    const etiqueta = document.createElement("span");
    etiqueta.textContent = "HISTORIAL DEL PERFIL";
    const titulo = document.createElement("h3");
    titulo.textContent = [perfil.plataforma, perfil.nombre_perfil]
        .map(valor => String(valor ?? "").trim())
        .filter(Boolean)
        .join(" · ") || "Perfil";
    const meta = document.createElement("div");

    [
        ["Estado actual", perfil.estado],
        ["Cuenta madre", perfil.cuenta_madre],
        ["Eventos", eventos.length]
    ].forEach(([nombre, valor]) => {
        const elemento = document.createElement("span");
        const nombreElemento = document.createElement("small");
        nombreElemento.textContent = nombre;
        const valorElemento = document.createElement("strong");
        valorElemento.textContent = textoHistorial(valor);
        elemento.append(nombreElemento, valorElemento);
        meta.appendChild(elemento);
    });
    resumen.append(etiqueta, titulo, meta);
    fragmento.appendChild(resumen);

    if (!eventos.length){
        fragmento.appendChild(crearEstadoHistorial(
            "history",
            "Sin movimientos registrados",
            "No hay movimientos históricos registrados para este perfil."
        ));
        contenidoHistorialPerfil.replaceChildren(fragmento);
        if (window.lucide) window.lucide.createIcons();
        return;
    }

    const linea = document.createElement("div");
    linea.className = "nube-historial-linea";

    eventos.forEach(evento => {
        const configuracion = configuracionEventosHistorial[evento?.tipo] || {
            clase: "neutral",
            icono: "activity"
        };
        const articulo = document.createElement("article");
        articulo.className = `nube-historial-evento nube-historial-evento--${configuracion.clase}`;

        const marcador = document.createElement("div");
        marcador.className = "nube-historial-marcador";
        const icono = document.createElement("i");
        icono.setAttribute("data-lucide", configuracion.icono);
        marcador.appendChild(icono);

        const tarjeta = document.createElement("div");
        tarjeta.className = "nube-historial-tarjeta";
        const cabecera = document.createElement("div");
        cabecera.className = "nube-historial-evento-header";
        const tituloEvento = document.createElement("strong");
        tituloEvento.textContent = textoHistorial(evento?.titulo, "Movimiento del perfil");
        const fecha = document.createElement("time");
        fecha.dateTime = String(evento?.fecha ?? "");
        fecha.textContent = formatearFechaHistorial(evento?.fecha);
        cabecera.append(tituloEvento, fecha);

        const descripcion = document.createElement("p");
        descripcion.textContent = textoHistorial(evento?.descripcion, "Sin descripción adicional.");
        tarjeta.append(cabecera, descripcion);

        const rutaTraslado = crearRutaTrasladoHistorial(evento);
        if (rutaTraslado) tarjeta.appendChild(rutaTraslado);

        const detalles = detallesEventoHistorial(evento)
            .filter(([nombre]) => !rutaTraslado || !["Origen", "Destino"].includes(nombre))
            .filter(([, valor]) => String(valor ?? "").trim());
        if (detalles.length){
            const lista = document.createElement("dl");
            detalles.forEach(([nombre, valor]) => {
                const fila = document.createElement("div");
                const termino = document.createElement("dt");
                termino.textContent = nombre;
                const dato = document.createElement("dd");
                dato.textContent = textoHistorial(valor);
                fila.append(termino, dato);
                lista.appendChild(fila);
            });
            tarjeta.appendChild(lista);
        }
        articulo.append(marcador, tarjeta);
        linea.appendChild(articulo);
    });

    fragmento.appendChild(linea);
    contenidoHistorialPerfil.replaceChildren(fragmento);
    if (window.lucide) window.lucide.createIcons();
}

async function cargarHistorialPerfil(forzar = false){
    const perfilId = String(perfilGestionId?.value || "").trim();
    if (!perfilId || !contenidoHistorialPerfil) return;
    if (!forzar && historialPerfilCargadoId === perfilId) return;

    historialPerfilAbortController?.abort();
    historialPerfilAbortController = new AbortController();
    mostrarCargaHistorial();

    try {
        const respuesta = await fetch(
            `/admin/nube-cuentas/perfil/${encodeURIComponent(perfilId)}/historial`,
            {signal: historialPerfilAbortController.signal}
        );
        const resultado = await respuesta.json();
        if (!respuesta.ok || !resultado.ok){
            throw new Error(resultado.mensaje || "No se pudo cargar el historial.");
        }
        historialPerfilCargadoId = perfilId;
        renderizarHistorialPerfil(resultado);
    } catch (error) {
        if (error.name === "AbortError") return;
        const estado = crearEstadoHistorial(
            "circle-alert",
            "No pudimos cargar el historial",
            error.message || "Intenta nuevamente en unos segundos.",
            "error"
        );
        const reintentar = document.createElement("button");
        reintentar.type = "button";
        reintentar.textContent = "Reintentar";
        reintentar.addEventListener("click", () => cargarHistorialPerfil(true));
        estado.appendChild(reintentar);
        contenidoHistorialPerfil.replaceChildren(estado);
        if (window.lucide) window.lucide.createIcons();
    }
}

function cambiarVistaPerfil(vista){
    const mostrarHistorial = vista === "historial";
    if (formGestionPerfil){
        formGestionPerfil.hidden = mostrarHistorial;
        formGestionPerfil.setAttribute("aria-hidden", String(mostrarHistorial));
    }
    if (vistaHistorialPerfil){
        vistaHistorialPerfil.hidden = !mostrarHistorial;
        vistaHistorialPerfil.setAttribute("aria-hidden", String(!mostrarHistorial));
    }
    tabGestionPerfil?.classList.toggle("activo", !mostrarHistorial);
    tabHistorialPerfil?.classList.toggle("activo", mostrarHistorial);
    tabGestionPerfil?.setAttribute("aria-selected", String(!mostrarHistorial));
    tabHistorialPerfil?.setAttribute("aria-selected", String(mostrarHistorial));

    if (mostrarHistorial) cargarHistorialPerfil();
}

function resetearHistorialPerfil(){
    historialPerfilAbortController?.abort();
    historialPerfilAbortController = null;
    historialPerfilCargadoId = "";
    contenidoHistorialPerfil?.replaceChildren();
    cambiarVistaPerfil("gestion");
}

tabGestionPerfil?.addEventListener("click", () => cambiarVistaPerfil("gestion"));
tabHistorialPerfil?.addEventListener("click", () => cambiarVistaPerfil("historial"));


        function abrirGestionPerfil(
            boton
        ){

            if (!modalPerfil) return;

            establecerOperacionCompletada(false);
            resetearHistorialPerfil();


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

            const perfilRealmenteAsignado =
                Boolean(String(datos.cliente || "").trim()) &&
                esFechaOperativaValida(datos.entrega) &&
                Number(datos.dias || 0) > 0 &&
                esFechaOperativaValida(datos.vencimiento);

            if (grupoLiberacionPerfil){
                grupoLiberacionPerfil.hidden = !perfilRealmenteAsignado;
            }
            if (panelLiberacionPerfil) panelLiberacionPerfil.hidden = true;
            if (contenidoLiberacionPerfil) contenidoLiberacionPerfil.hidden = false;
            if (exitoLiberacionPerfil) exitoLiberacionPerfil.hidden = true;
            if (exitoLiberacionPerfil){
                exitoLiberacionPerfil.querySelector("strong").textContent =
                    "Perfil liberado";
                exitoLiberacionPerfil.querySelector("span").textContent =
                    "La venta quedó protegida en el historial y no se trasladaron días.";
            }
            if (motivoLiberacionPerfil) motivoLiberacionPerfil.value = "";
            if (abrirLiberacionPerfil) abrirLiberacionPerfil.hidden = false;
            if (grupoRenovacionPerfil) grupoRenovacionPerfil.hidden = false;
            operacionLiberacionUuid = "";
            resetearTrasladoPerfil();


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

            establecerOperacionCompletada(false);
            resetearHistorialPerfil();
            operacionLiberacionUuid = "";
            resetearTrasladoPerfil();


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


        guardarGestionPerfil?.addEventListener(
            "click",
            event => {
                if (!operacionCompletada) return;

                event.preventDefault();
                event.stopPropagation();

                cerrarModalPerfil();
                window.location.reload();
            }
        );


        formGestionPerfil?.addEventListener(
            "submit",
            event => {
                event.preventDefault();

                if (operacionCompletada){
                    cerrarModalPerfil();
                    window.location.reload();
                    return;
                }

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


        abrirLiberacionPerfil?.addEventListener("click", async () => {
            const perfilId = perfilGestionId?.value || "";
            if (!perfilId) return;

            abrirLiberacionPerfil.disabled = true;
            try {
                const respuesta = await fetch(
                    `/admin/nube-cuentas/perfil/${perfilId}/liberacion`
                );
                const resultado = await respuesta.json();
                if (!respuesta.ok || !resultado.ok){
                    throw new Error(
                        resultado.mensaje || "No se pudo preparar la liberación."
                    );
                }

                liberacionCliente.textContent = resultado.cliente || "—";
                liberacionServicio.textContent =
                    `${resultado.plataforma || "—"} · ${resultado.perfil || "—"}`;
                liberacionVencimiento.textContent = resultado.vencimiento || "—";
                liberacionDias.textContent = String(resultado.dias_restantes ?? 0);
                contextoLiberacionPerfil = resultado;
                perfilDestinoTraslado = null;
                seleccionarAccionLiberacion("liberar");
                trasladoDiasDisponibles.textContent = String(
                    resultado.dias_restantes ?? 0
                );
                diasTrasladarPerfil.value = String(resultado.dias_restantes ?? 0);
                diasTrasladarPerfil.max = String(resultado.dias_restantes ?? 0);
                plataformaDestinoPerfil.innerHTML =
                    '<option value="">Selecciona una plataforma</option>';
                (resultado.plataformas_destino || []).forEach(plataforma => {
                    const opcion = document.createElement("option");
                    opcion.value = plataforma;
                    opcion.textContent = plataforma;
                    plataformaDestinoPerfil.appendChild(opcion);
                });
                listaDestinosTraslado.innerHTML = "";
                resumenTrasladoPerfil.hidden = true;
                operacionLiberacionUuid = crearOperacionUuid();
                panelLiberacionPerfil.hidden = false;
                contenidoLiberacionPerfil.hidden = false;
                exitoLiberacionPerfil.hidden = true;
            } catch (error) {
                mostrarMensajePerfil(error.message, "error");
            } finally {
                abrirLiberacionPerfil.disabled = false;
            }
        });


        cancelarLiberacionPerfil?.addEventListener("click", () => {
            panelLiberacionPerfil.hidden = true;
            motivoLiberacionPerfil.value = "";
            operacionLiberacionUuid = "";
            resetearTrasladoPerfil();
        });


        confirmarLiberacionPerfil?.addEventListener("click", async () => {
            const perfilId = perfilGestionId?.value || "";
            if (!perfilId || !operacionLiberacionUuid) return;

            const diasTrasladar = Number(diasTrasladarPerfil?.value || 0);
            const diasDisponibles = Number(
                contextoLiberacionPerfil?.dias_restantes || 0
            );
            if (accionLiberacionPerfil !== "liberar"){
                if (!perfilDestinoTraslado){
                    mostrarMensajePerfil(
                        "Selecciona un perfil disponible de destino.",
                        "error"
                    );
                    return;
                }
                if (
                    !Number.isInteger(diasTrasladar) ||
                    diasTrasladar < 1 ||
                    diasTrasladar > diasDisponibles
                ){
                    mostrarMensajePerfil(
                        `Los días a trasladar deben estar entre 1 y ${diasDisponibles}.`,
                        "error"
                    );
                    return;
                }
            }

            confirmarLiberacionPerfil.disabled = true;
            try {
                const respuesta = await fetch(
                    "/admin/nube-cuentas/perfil/liberar-trasladar",
                    {
                        method: "POST",
                        headers: {"Content-Type": "application/json"},
                        body: JSON.stringify({
                            perfil_origen_id: perfilId,
                            accion: accionLiberacionPerfil,
                            destino_tipo: accionLiberacionPerfil === "sumar_activo"
                                ? "perfil"
                                : "nuevo_perfil",
                            destino_id: perfilDestinoTraslado?.perfil_id,
                            perfil_destino_id: perfilDestinoTraslado?.perfil_id,
                            dias_trasladar: diasTrasladar,
                            motivo: motivoLiberacionPerfil?.value || "",
                            operacion_uuid: operacionLiberacionUuid
                        })
                    }
                );
                const resultado = await respuesta.json();
                if (!respuesta.ok || !resultado.ok){
                    throw new Error(
                        resultado.mensaje || "No se pudo liberar el perfil."
                    );
                }

                contenidoLiberacionPerfil.hidden = true;
                exitoLiberacionPerfil.hidden = false;
                abrirLiberacionPerfil.hidden = true;
                if (abrirCaidaPerfil) abrirCaidaPerfil.hidden = true;
                if (grupoReemplazoPerfil) grupoReemplazoPerfil.hidden = true;
                if (grupoRenovacionPerfil) grupoRenovacionPerfil.hidden = true;
                perfilGestionCliente.value = "";
                perfilGestionTelefono.value = "";
                perfilGestionEntrega.value = "";
                perfilGestionDias.value = "";
                perfilGestionVencimiento.value = "Sin vencimiento";
                subtituloGestionPerfil.textContent = "Perfil · disponible";
                mostrarMensajePerfil(resultado.mensaje);
                establecerOperacionCompletada(true);
                if (window.lucide) window.lucide.createIcons();

                if (
                    accionLiberacionPerfil !== "liberar" &&
                    resultado.datos_entrega
                ){
                    exitoLiberacionPerfil.querySelector("strong").textContent =
                        accionLiberacionPerfil === "sumar_activo"
                            ? "Días trasladados"
                            : "Servicio cambiado";
                    exitoLiberacionPerfil.querySelector("span").textContent =
                        accionLiberacionPerfil === "sumar_activo"
                            ? "El servicio activo seleccionado recibió los días."
                            : "El cliente quedó asignado al nuevo perfil.";
                    mostrarPanelMensajeCliente(
                        accionLiberacionPerfil === "sumar_activo"
                            ? "dias_trasladados"
                            : "cambio_servicio",
                        resultado.datos_entrega
                    );
                    confirmarLiberacionPerfil.disabled = false;
                } else {
                    if (panelMensajeCliente) panelMensajeCliente.hidden = true;
                    window.setTimeout(() => window.location.reload(), 2200);
                }
            } catch (error) {
                mostrarMensajePerfil(error.message, "error");
                confirmarLiberacionPerfil.disabled = false;
            }
        });


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

