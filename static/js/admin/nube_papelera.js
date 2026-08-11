function convertirFechaSegura(valor) {
    if (valor === null || valor === undefined) return null;
    const texto = String(valor).trim();
    if (!texto || texto === "—") return null;
    let normalizado = texto;
    if (/^\d{4}-\d{2}-\d{2}$/.test(texto)) normalizado = `${texto}T00:00:00Z`;
    else if (/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(?:\.\d+)?$/.test(texto)) normalizado = `${texto.replace(" ", "T")}Z`;
    const fecha = new Date(normalizado);
    return Number.isNaN(fecha.getTime()) ? null : fecha;
}

function formatearFechaSegura(valor) {
    const fecha = convertirFechaSegura(valor);
    if (!fecha) return "Sin fecha";
    return new Intl.DateTimeFormat("es-CO", { dateStyle: "medium", timeZone: "UTC" }).format(fecha);
}

function esPinVencido(cuenta, hoy = new Date()) {
    if (String(cuenta.tipo_pago || "").toLowerCase() !== "pin") return false;
    const proximoPago = convertirFechaSegura(cuenta.fecha_proximo_pago);
    if (!proximoPago) return false;
    const limite = new Date(Date.UTC(hoy.getUTCFullYear(), hoy.getUTCMonth(), hoy.getUTCDate()));
    return proximoPago < limite;
}

function filtrarCuentasPapelera(cuentas, consulta, plataforma, pinVencido, hoy = new Date()) {
    const busqueda = String(consulta || "").trim().toLowerCase();
    return cuentas.filter(cuenta =>
        (!busqueda || `${cuenta.plataforma || ""} ${cuenta.correo || ""}`.toLowerCase().includes(busqueda)) &&
        (!plataforma || cuenta.plataforma === plataforma) &&
        (!pinVencido || esPinVencido(cuenta, hoy))
    );
}

if (typeof document !== "undefined") document.addEventListener("DOMContentLoaded", () => {
    const app = document.getElementById("papeleraApp");
    if (!app) return;
    const lista = document.getElementById("papeleraLista");
    const modal = document.getElementById("papeleraModal");
    const body = document.getElementById("papeleraDetalle");
    const conteo = document.getElementById("papeleraConteo");
    let cuentas = [];
    const el = (tag, clase, texto) => { const nodo = document.createElement(tag); if (clase) nodo.className = clase; if (texto !== undefined) nodo.textContent = texto; return nodo; };
    const fecha = formatearFechaSegura;
    const dinero = valor => new Intl.NumberFormat("es-CO", { style: "currency", currency: "COP", maximumFractionDigits: 0 }).format(Number(valor || 0));
    const dato = (clave, valor) => { const nodo = el("div", "papelera-dato"); nodo.append(el("span", "", clave), el("strong", "", valor || "—")); return nodo; };
    const seccion = titulo => { const nodo = el("section", "papelera-seccion"); nodo.append(el("h3", "", titulo)); return nodo; };
    const nombreMovimiento = valor => String(valor || "Sin actividad").replaceAll("_", " ");
    const iniciales = valor => String(valor || "?").trim().split(/\s+/).slice(0, 2).map(parte => parte[0]).join("").toUpperCase();

    function render() {
        const consulta = document.getElementById("papeleraBuscar").value.trim().toLowerCase();
        const plataforma = document.getElementById("papeleraPlataforma").value;
        const pinVencido = document.getElementById("papeleraPinVencido").checked;
        const items = filtrarCuentasPapelera(cuentas, consulta, plataforma, pinVencido);
        conteo.textContent = `${items.length} de ${cuentas.length}`;
        lista.replaceChildren();
        if (!items.length) { lista.append(el("div", "papelera-vacio", "No hay cuentas archivadas para estos filtros.")); return; }
        const fragmento = document.createDocumentFragment();
        items.forEach(cuenta => {
            const fila = el("button", "papelera-fila"); fila.type = "button"; fila.dataset.cuentaId = cuenta.id;
            const identidad = el("span", "papelera-cuenta"), avatar = el("span", "papelera-avatar", iniciales(cuenta.plataforma)), textos = el("span", "papelera-identidad");
            const plataformaCuenta = el("span", "papelera-plataforma", cuenta.plataforma || "Sin plataforma"); plataformaCuenta.append(el("span", "papelera-estado", "PAPELERA"));
            textos.append(plataformaCuenta, el("span", "papelera-correo", cuenta.correo || "Sin identificador")); identidad.append(avatar, textos);
            const archivo = el("span", "papelera-archivo"); archivo.append(el("span", "papelera-linea", `${cuenta.perfiles_totales || 0} perfiles · Archivada ${fecha(cuenta.fecha_archivada)}`));
            if (String(cuenta.tipo_pago || "").toLowerCase() === "pin") archivo.append(el("span", "papelera-sublinea papelera-pin", `Próximo PIN · ${fecha(cuenta.fecha_proximo_pago)}`));
            else archivo.append(el("span", "papelera-sublinea", cuenta.modalidad || "Sin modalidad"));
            const actividad = el("span", "papelera-actividad"); actividad.append(el("span", "papelera-linea", "Último movimiento"), el("span", "papelera-sublinea", nombreMovimiento(cuenta.ultimo_movimiento)));
            fila.append(identidad, archivo, actividad, el("span", "papelera-ver", "Ver")); fragmento.append(fila);
        });
        lista.append(fragmento);
    }

    async function cargar() {
        const respuesta = await fetch(`/admin/nube-papelera/cuentas?_=${Date.now()}`, { cache: "no-store", headers: { Accept: "application/json" } }); const datos = await respuesta.json();
        if (!respuesta.ok) throw Error(datos.mensaje); cuentas = datos.cuentas || [];
        const selector = document.getElementById("papeleraPlataforma"), actual = selector.value;
        selector.replaceChildren(new Option("Todas las plataformas", ""));
        [...new Set(cuentas.map(c => c.plataforma))].sort().forEach(x => selector.add(new Option(x, x))); selector.value = actual; render();
    }

    async function abrir(id) {
        modal.classList.add("abierto"); modal.setAttribute("aria-hidden", "false"); body.textContent = "Cargando…";
        document.body.classList.add("papelera-modal-abierto");
        try {
            const respuesta = await fetch(`/admin/nube-papelera/${id}`), datos = await respuesta.json();
            if (!respuesta.ok) throw Error(datos.mensaje || "No fue posible cargar el detalle.");
            document.getElementById("papeleraModalPlataforma").textContent = datos.cuenta.plataforma || "CUENTA ARCHIVADA";
            document.getElementById("papeleraTitulo").textContent = datos.cuenta.correo || "Detalle"; pintarDetalle(datos);
        } catch (error) {
            console.error("No fue posible cargar el detalle de Papelera:", error);
            const estado = el("div", "papelera-vacio");
            estado.append(el("p", "", "No pudimos cargar Papelera."));
            const reintentar = el("button", "papelera-btn", "Reintentar");
            reintentar.type = "button";
            reintentar.onclick = () => abrir(id);
            estado.append(reintentar);
            body.replaceChildren(estado);
        }
    }

    function pintarDetalle(datos) {
        body.replaceChildren(); const cuenta = datos.cuenta;
        const tabs = el("nav", "papelera-tabs"); tabs.setAttribute("aria-label", "Secciones de la cuenta");
        const paneles = {};
        const crearPanel = (id, etiqueta) => { const boton = el("button", `papelera-tab${id === "resumen" ? " activo" : ""}`, etiqueta); boton.type = "button"; boton.dataset.panel = id; boton.setAttribute("aria-selected", String(id === "resumen")); tabs.append(boton); const panel = el("div", "papelera-panel-modal"); panel.dataset.panelContenido = id; panel.hidden = id !== "resumen"; paneles[id] = panel; return panel; };
        const resumenPanel = crearPanel("resumen", "Resumen"), perfilesPanel = crearPanel("perfiles", `Perfiles (${datos.perfiles.length})`), historialPanel = crearPanel("historial", `Historial (${datos.movimientos.length})`), pagosPanel = crearPanel("pagos", cuenta.tipo_pago === "pin" ? `Pagos (${datos.historial_pin.length})` : "Acción");
        const resumen = seccion("Resumen de archivo"), grid = el("div", "papelera-datos");
        grid.append(dato("Estado", "Papelera"), dato("Fecha archivada", fecha(cuenta.fecha_archivada)), dato("Perfiles", String(datos.perfiles.length)), dato("Tipo / modalidad", `${cuenta.tipo_pago || "Sin PIN"} · ${cuenta.modalidad || "Sin modalidad"}`), dato("Próximo pago PIN", cuenta.tipo_pago === "pin" ? fecha(cuenta.fecha_proximo_pago) : "No aplica"), dato("Último movimiento", nombreMovimiento(datos.movimientos[0]?.tipo))); resumen.append(grid); resumenPanel.append(resumen);
        const perfiles = seccion("Perfiles preservados"), listaPerfiles = el("div", "papelera-lista");
        datos.perfiles.forEach(p => { const item = el("div", "papelera-item"); item.append(el("strong", "", p.nombre_perfil || `Perfil #${p.id}`), el("small", "", "Sin cliente operativo"), el("span", "papelera-estado", "ARCHIVADO")); listaPerfiles.append(item); });
        if (!datos.perfiles.length) listaPerfiles.append(el("div", "papelera-vacio", "No hay perfiles asociados.")); perfiles.append(listaPerfiles); perfilesPanel.append(perfiles);
        const movimientos = seccion("Historial y movimientos"), listaMovimientos = el("div", "papelera-lista");
        datos.movimientos.forEach(m => { const item = el("div", "papelera-item"); item.append(el("strong", "", nombreMovimiento(m.tipo)), el("small", "", m.descripcion || "Sin descripción"), el("time", "", fecha(m.fecha))); listaMovimientos.append(item); });
        if (!datos.movimientos.length) listaMovimientos.append(el("div", "papelera-vacio", "No hay movimientos registrados.")); movimientos.append(listaMovimientos); historialPanel.append(movimientos);
        const pagos = seccion("Historial de pagos PIN"), listaPagos = el("div", "papelera-lista");
        datos.historial_pin.forEach(p => { const item = el("div", "papelera-item"); item.append(el("strong", "", p.plan || "Pago PIN"), el("small", "", dinero(p.valor_pin)), el("time", "", fecha(p.fecha_aplicacion))); listaPagos.append(item); });
        if (!datos.historial_pin.length) listaPagos.append(el("div", "papelera-vacio", "No hay pagos PIN registrados.")); pagos.append(listaPagos); pagosPanel.append(pagos);
        const acciones = seccion(cuenta.tipo_pago === "pin" ? "Actualizar pago y restaurar" : "Acciones disponibles"); pagosPanel.append(acciones);
        body.append(tabs, resumenPanel, perfilesPanel, historialPanel, pagosPanel);
        tabs.onclick = evento => { const boton = evento.target.closest("[data-panel]"); if (!boton) return; tabs.querySelectorAll(".papelera-tab").forEach(tab => { const activo = tab === boton; tab.classList.toggle("activo", activo); tab.setAttribute("aria-selected", String(activo)); }); Object.entries(paneles).forEach(([id, panel]) => { panel.hidden = id !== boton.dataset.panel; }); };
        if (cuenta.tipo_pago === "pin") pintarPin(datos, acciones); else pintarRestauracionManual(datos, acciones);
    }

    function pintarPin(datos, seccionPin = seccion("Actualizar pago PIN y restaurar")) {
        const formulario = el("form", "papelera-form");
        [["Plan", "plan", "text", datos.cuenta.plan_pago], ["Valor PIN", "valor_pin", "number", datos.cuenta.valor_pin], ["Precio mensual de referencia", "precio_plan_referencia", "number", datos.cuenta.precio_plan_referencia], ["Fecha", "fecha_aplicacion", "date", new Date().toISOString().slice(0, 10)]].forEach(([label, nombre, tipo, valor]) => { const campo = el("label"); campo.append(el("span", "", label)); const input = el("input"); input.name = nombre; input.type = tipo; input.value = valor || ""; input.required = true; campo.append(input); formulario.append(campo); });
        const mensaje = el("div", "papelera-mensaje"), boton = el("button", "papelera-btn principal", "Actualizar pago"); boton.type = "submit"; formulario.append(mensaje, boton);
        formulario.onsubmit = async evento => { evento.preventDefault(); boton.disabled = true; const payload = Object.fromEntries(new FormData(formulario)); payload.cuenta_id = datos.cuenta.id; try { const respuesta = await fetch("/admin/nube-cuentas/pagos-pin", { method: "POST", headers: { "Content-Type": "application/json", Accept: "application/json" }, body: JSON.stringify(payload) }); const resultado = await respuesta.json(); if (!respuesta.ok || !resultado.ok) throw new Error(resultado.mensaje || "No se pudo actualizar el pago."); if (!resultado.cuenta_restaurada && !resultado.pago?.cuenta_restaurada) throw new Error("El pago se procesó, pero la cuenta no pudo restaurarse."); seccionPin.replaceChildren(el("div", "papelera-exito", resultado.pago_registrado ? "✓ Pago registrado correctamente" : "✓ Pago verificado correctamente"), el("div", "papelera-exito", "✓ Cuenta restaurada al inventario"), dato("Correo", datos.cuenta.correo), dato("Plan", resultado.pago.plan), dato("Valor", dinero(resultado.pago.valor_pin)), dato("Fecha registrada", fecha(resultado.pago.fecha_aplicacion)), dato("Próximo pago", fecha(resultado.pago.proximo_pago))); const listo = el("button", "papelera-btn principal", "Listo"); listo.type = "button"; listo.onclick = async () => { cerrarModal(); await cargar(); }; seccionPin.append(listo); } catch (error) { mensaje.textContent = error.message; boton.disabled = false; } };
        seccionPin.append(formulario);
    }

    function pintarRestauracionManual(datos, acciones = seccion("Acciones disponibles")) {
        const boton = el("button", "papelera-btn principal", "Mover al inventario");
        boton.onclick = async () => { if (!confirm("Esta cuenta volverá al inventario operativo. Los clientes anteriores NO serán restaurados.")) return; boton.disabled = true; const respuesta = await fetch(`/admin/nube-papelera/${datos.cuenta.id}/restaurar`, { method: "POST", headers: { Accept: "application/json" } }); const resultado = await respuesta.json(); if (!respuesta.ok) { alert(resultado.mensaje); boton.disabled = false; return; } cerrarModal(); await cargar(); };
        acciones.append(boton);
    }

    document.getElementById("papeleraBuscar").value = "";
    document.getElementById("papeleraPlataforma").value = "";
    document.getElementById("papeleraPinVencido").checked = false;
    function cerrarModal() { modal.classList.remove("abierto"); modal.setAttribute("aria-hidden", "true"); document.body.classList.remove("papelera-modal-abierto"); }
    document.querySelectorAll("[data-cerrar]").forEach(x => x.onclick = cerrarModal);
    lista.addEventListener("click", evento => { const fila = evento.target.closest("[data-cuenta-id]"); if (fila) abrir(fila.dataset.cuentaId); });
    document.addEventListener("keydown", evento => { if (evento.key === "Escape" && modal.classList.contains("abierto")) cerrarModal(); });
    ["papeleraBuscar", "papeleraPlataforma", "papeleraPinVencido"].forEach(id => document.getElementById(id).addEventListener(id === "papeleraBuscar" ? "input" : "change", render));
    document.getElementById("papeleraActualizar").onclick = cargar;
    function mostrarErrorCarga(error) {
        console.error("No fue posible cargar Papelera:", error);
        const estado = el("div", "papelera-vacio");
        estado.append(el("p", "", "No pudimos cargar Papelera."));
        const reintentar = el("button", "papelera-btn", "Reintentar");
        reintentar.type = "button";
        reintentar.onclick = () => cargar().catch(mostrarErrorCarga);
        estado.append(reintentar);
        lista.replaceChildren(estado);
    }

    cargar().catch(mostrarErrorCarga);
});

if (typeof module !== "undefined" && module.exports) {
    module.exports = { convertirFechaSegura, formatearFechaSegura, esPinVencido, filtrarCuentasPapelera };
}
