document.addEventListener("DOMContentLoaded", () => {
    const centro = document.getElementById("alertasCentro");
    if (!centro) return;
    const lista = document.getElementById("alertasLista");
    const modal = document.getElementById("alertaModal");
    const modalBody = document.getElementById("alertaModalBody");
    const estado = { alertas: [], filtro: "todas", tipo: "todos", cargando: false, activa: null };
    const grupos = {
        perfiles: ["perfil_vencido", "perfil_vence_hoy", "perfil_por_vencer"],
        cuentas: ["cuenta_vencida", "cuenta_vence_hoy", "cuenta_por_vencer"],
        pagos_pin: ["pago_pin_pendiente", "pago_pin_vence_hoy", "pago_pin_proximo"],
        caidas: ["cuenta_caida"]
    };
    const el = (tag, clase, texto) => {
        const nodo = document.createElement(tag);
        if (clase) nodo.className = clase;
        if (texto !== undefined) nodo.textContent = texto;
        return nodo;
    };
    const dinero = valor => new Intl.NumberFormat("es-CO", { style: "currency", currency: "COP", maximumFractionDigits: 0 }).format(Number(valor || 0));
    const fechaTexto = valor => valor ? new Intl.DateTimeFormat("es-CO", { dateStyle: "medium", timeZone: "UTC" }).format(new Date(`${valor}T00:00:00Z`)) : "Sin fecha";
    const coincide = alerta => {
        const principal = estado.filtro === "todas" ||
            (estado.filtro === "criticas" && alerta.prioridad === "critica") ||
            (estado.filtro === "hoy" && alerta.dias_restantes === 0) ||
            (estado.filtro === "proximas" && alerta.dias_restantes >= 1 && alerta.dias_restantes <= 3);
        return principal && (!grupos[estado.tipo] || grupos[estado.tipo].includes(alerta.tipo));
    };
    const diasTexto = alerta => {
        if (alerta.dias_restantes === null || alerta.dias_restantes === undefined) return "Sin fecha objetivo";
        if (alerta.dias_restantes === 0) return "Vence hoy";
        return alerta.dias_restantes > 0 ? `Faltan ${alerta.dias_restantes} día(s)` : `Vencida hace ${Math.abs(alerta.dias_restantes)} día(s)`;
    };
    function filaDato(etiqueta, valor) {
        const fila = el("div", "alerta-dato");
        fila.append(el("span", "", etiqueta), el("strong", "", valor || "—"));
        return fila;
    }
    function cerrarModal() {
        modal.classList.remove("abierto");
        modal.setAttribute("aria-hidden", "true");
        document.body.classList.remove("alerta-modal-abierto");
    }
    async function abrirModal(alerta) {
        estado.activa = alerta;
        modal.classList.add("abierto");
        modal.setAttribute("aria-hidden", "false");
        document.body.classList.add("alerta-modal-abierto");
        document.getElementById("alertaModalTitulo").textContent = alerta.titulo;
        const badge = document.getElementById("alertaModalPrioridad");
        badge.textContent = alerta.prioridad.toUpperCase();
        badge.className = `alerta-badge ${alerta.prioridad}`;
        modalBody.replaceChildren(el("div", "alertas-cargando-modal", "Cargando contexto operativo…"));
        try {
            const params = new URLSearchParams({ cuenta_id: alerta.cuenta_id });
            if (alerta.perfil_id) params.set("perfil_id", alerta.perfil_id);
            const respuesta = await fetch(`/admin/nube-cuentas/alertas/detalle?${params}`, { headers: { Accept: "application/json" } });
            const datos = await respuesta.json();
            if (!respuesta.ok || !datos.ok) throw new Error(datos.mensaje || "No se pudo cargar el detalle.");
            renderModal(alerta, datos);
        } catch (error) {
            modalBody.replaceChildren(el("div", "alertas-error", error.message));
        }
    }
    function renderModal(alerta, datos) {
        modalBody.replaceChildren();
        if (alerta.tipo === "cuenta_caida") { renderCuentaCaidaPremium(datos); return; }
        const resumen = el("section", "alerta-resumen");
        resumen.append(el("p", "alerta-descripcion", alerta.descripcion));
        const grid = el("div", "alerta-datos-grid");
        grid.append(filaDato("Tipo", alerta.tipo.replaceAll("_", " ")), filaDato("Plataforma", datos.cuenta.plataforma), filaDato(alerta.perfil_id ? "Perfil" : "Cuenta", datos.perfil?.nombre_perfil || `#${alerta.cuenta_id}`), filaDato("Cliente", datos.perfil?.nombre_cliente || alerta.cliente || "Sin asignar"), filaDato("Fecha objetivo", fechaTexto(alerta.fecha_objetivo)), filaDato("Estado", datos.perfil?.estado || datos.cuenta.estado), filaDato("Plazo", diasTexto(alerta)));
        resumen.append(grid);
        modalBody.append(resumen);
        if (alerta.accion === "actualizar_pago_pin") renderPin(datos);
        else if (alerta.tipo === "cuenta_caida") renderCuentaCaida(datos);
        else renderAccionGestion(alerta);
    }
    function renderCuentaCaidaPremium(datos) {
        const c = datos.cuenta;
        const total = Number(c.perfiles_totales || 0), resueltos = Number(c.perfiles_resueltos || 0), vencidos = Number(c.perfiles_vencidos || 0), pendientesVigentes = Number(c.servicios_vigentes_pendientes || 0);
        const porcentaje = total ? Math.round((resueltos + vencidos) * 100 / total) : 100;
        const bloque = el("section", "alerta-caida-premium");
        const identidad = el("div", "alerta-caida-identidad");
        identidad.append(el("span", "alerta-caida-plataforma", c.plataforma), el("strong", "", c.correo));
        bloque.append(identidad, el("h3", "", "Estado de garantÃ­as"));
        const metricas = el("div", "alerta-caida-metricas");
        metricas.append(filaDato("Total perfiles", String(total)), filaDato("Resueltos", String(resueltos)), filaDato("Vencidos", String(vencidos)), filaDato("Pendientes", String(pendientesVigentes)));
        bloque.append(metricas);
        const progresoCabecera = el("div", "alerta-progreso-cabecera");
        progresoCabecera.append(el("span", "", "ResoluciÃ³n de garantÃ­as"), el("strong", "", `${porcentaje}%`));
        const progreso = el("div", "alerta-progreso"), barra = el("span"); barra.style.width = `${porcentaje}%`; progreso.append(barra);
        bloque.append(progresoCabecera, progreso);
        if (datos.perfiles_pendientes?.length) {
            bloque.append(el("h3", "alerta-pendientes-titulo", "Perfiles pendientes"));
            const pendientes = el("div", "alerta-pendientes");
            datos.perfiles_pendientes.forEach(perfil => {
                const fila = el("div", "alerta-pendiente-fila"), persona = el("div");
                persona.append(el("strong", "", perfil.nombre_perfil || `Perfil #${perfil.id}`), el("span", "", perfil.nombre_cliente || "Cliente asignado"));
                fila.append(persona, el("span", "alerta-pendiente-estado", "Pendiente")); pendientes.append(fila);
            });
            bloque.append(pendientes);
        } else bloque.append(el("p", "alerta-form-mensaje exito", "âœ“ Lista para archivar"));
        const acciones = el("div", "alerta-acciones-botones");
        const gestionar = el("a", "alerta-btn alerta-btn-principal", "Gestionar cuenta"); gestionar.href = `/admin/nube-cuentas?cuenta=${c.id}`; acciones.append(gestionar);
        if ((c.tipo_pago || "").toLowerCase() === "pin") { const pin = el("button", "alerta-btn alerta-btn-pin", "Registrar / actualizar pago PIN"); pin.type = "button"; pin.onclick = () => { modalBody.replaceChildren(); renderPin(datos); }; acciones.append(pin); }
        const archivar = el("button", "alerta-btn alerta-btn-archivo", "Mover a Papelera"); archivar.type = "button"; archivar.disabled = !c.lista_para_papelera;
        archivar.onclick = async () => { if (!confirm("Esta cuenta saldrÃ¡ del inventario operativo, pero conservarÃ¡ sus datos e historial.")) return; archivar.disabled = true; const respuesta = await fetch(`/admin/nube-cuentas/${c.id}/papelera`, { method: "POST", headers: { "Content-Type": "application/json", Accept: "application/json" }, body: JSON.stringify({ motivo: "GarantÃ­as completadas" }) }); const resultado = await respuesta.json(); if (!respuesta.ok) { alert(resultado.mensaje); archivar.disabled = false; return; } cerrarModal(); await cargarAlertas(); };
        acciones.append(archivar); bloque.append(acciones);
        if (!c.lista_para_papelera) bloque.append(el("p", "alerta-bloqueo", pendientesVigentes === 1 ? "Falta 1 servicio vigente por resolver." : `Faltan ${pendientesVigentes} servicios vigentes por resolver.`));
        modalBody.append(bloque);
    }
    function renderCuentaCaida(datos) {
        const c = datos.cuenta, total = Number(c.perfiles_totales || 0), resueltos = Number(c.perfiles_resueltos || 0), vencidos = Number(c.perfiles_vencidos || 0), pendientesVigentes = Number(c.servicios_vigentes_pendientes || 0), porcentaje = total ? Math.round((resueltos + vencidos) * 100 / total) : 100;
        const bloque = el("section", "alerta-acciones"); bloque.append(el("h3", "", "Garantías"), el("strong", "", `${resueltos} / ${total} perfiles resueltos`));
        const resumen = el("div", "alerta-detalle-grid"); resumen.append(filaDato("Plataforma", c.plataforma), filaDato("Cuenta", c.correo), filaDato("Estado", c.estado), filaDato("Total de perfiles", String(total)), filaDato("Reemplazados / resueltos", String(resueltos)), filaDato("Vencidos", String(vencidos)), filaDato("Servicios vigentes pendientes", String(pendientesVigentes))); bloque.append(resumen);
        const progreso = el("div", "alerta-progreso"), barra = el("span"); barra.style.width = `${porcentaje}%`; progreso.append(barra); bloque.append(progreso, el("p", "", `${porcentaje}% completado`));
        if (datos.perfiles_pendientes?.length) { const pendientes = el("div", "alerta-pendientes"); datos.perfiles_pendientes.forEach(p => pendientes.append(el("span", "", `${p.nombre_perfil || `Perfil #${p.id}`} · ${p.nombre_cliente || "Cliente asignado"}`))); bloque.append(pendientes); }
        else bloque.append(el("p", "alerta-form-mensaje exito", "✓ Garantías completadas · Lista para archivar"));
        const acciones = el("div", "alerta-acciones-botones"), gestionar = el("a", "alerta-btn alerta-btn-principal", "Gestionar cuenta"); gestionar.href = `/admin/nube-cuentas?cuenta=${c.id}`; acciones.append(gestionar);
        if ((c.tipo_pago || "").toLowerCase() === "pin") { const pin = el("button", "alerta-btn", "Registrar pago / PIN"); pin.type = "button"; pin.onclick = () => { modalBody.replaceChildren(); renderPin(datos); }; acciones.append(pin); }
        const archivar = el("button", "alerta-btn", "Mover a papelera"); archivar.type = "button"; archivar.disabled = !c.lista_para_papelera; archivar.onclick = async () => { if (!confirm("Esta cuenta saldrá del inventario operativo, pero conservará sus datos e historial.")) return; archivar.disabled = true; const respuesta = await fetch(`/admin/nube-cuentas/${c.id}/papelera`, { method: "POST", headers: { "Content-Type": "application/json", Accept: "application/json" }, body: JSON.stringify({ motivo: "Garantías completadas" }) }); const resultado = await respuesta.json(); if (!respuesta.ok) { alert(resultado.mensaje); archivar.disabled = false; return; } cerrarModal(); await cargarAlertas(); }; acciones.append(archivar); bloque.append(acciones);
        if (!c.lista_para_papelera) bloque.append(el("p", "alerta-form-ayuda", pendientesVigentes === 1 ? "Falta 1 servicio vigente por resolver." : `Faltan ${pendientesVigentes} servicios vigentes por resolver.`)); modalBody.append(bloque);
    }
    function renderAccionGestion(alerta) {
        const bloque = el("section", "alerta-acciones");
        bloque.append(el("h3", "", "Acción disponible"), el("p", "", "Continúa en el flujo existente de Nube para administrar este registro."));
        const enlace = el("a", "alerta-btn alerta-btn-principal", alerta.accion === "gestionar_perfil" ? "Gestionar perfil" : "Gestionar cuenta");
        enlace.href = `/admin/nube-cuentas?cuenta=${encodeURIComponent(alerta.cuenta_id)}${alerta.perfil_id ? `&perfil=${encodeURIComponent(alerta.perfil_id)}` : ""}`;
        bloque.append(enlace); modalBody.append(bloque);
    }
    function renderPin(datos) {
        const cuenta = datos.cuenta;
        const actual = el("section", "alerta-seccion-pin");
        actual.append(el("h3", "", "Pago actual / anterior"));
        const grid = el("div", "alerta-datos-grid");
        grid.append(filaDato("Plataforma", cuenta.plataforma), filaDato("Cuenta", `#${cuenta.id}`), filaDato("Correo de la cuenta", cuenta.correo), filaDato("Plan", cuenta.plan_pago), filaDato("Valor PIN", dinero(cuenta.valor_pin)), filaDato("Último pago", fechaTexto(cuenta.fecha_aplicacion_pin)), filaDato("Fecha estimada", fechaTexto(cuenta.fecha_proximo_pago)), filaDato("Estado", estado.activa.titulo));
        actual.append(grid); modalBody.append(actual);

        const registro = el("section", "alerta-seccion-pin");
        registro.append(el("h3", "", "Registrar nuevo pago"));
        const form = el("form", "alerta-form-pin");
        const campos = [
            ["Plan", "plan", "text", cuenta.plan_pago || ""],
            ["Valor PIN", "valor_pin", "number", cuenta.valor_pin || ""],
            ["Precio mensual de referencia", "precio_plan_referencia", "number", cuenta.precio_plan_referencia || ""],
            ["Fecha de pago / activación", "fecha_aplicacion", "date", new Date().toISOString().slice(0, 10)]
        ];
        campos.forEach(([label, name, type, value]) => { const wrap = el("label", ""); wrap.append(el("span", "", label)); const input = el("input"); input.name = name; input.type = type; input.value = value; input.required = true; if (type === "number") input.min = "1"; wrap.append(input); form.append(wrap); });
        const ayuda = el("p", "alerta-form-ayuda", "La duración se calcula con la regla vigente: valor PIN ÷ precio mensual × 30 días.");
        const mensaje = el("div", "alerta-form-mensaje");
        const boton = el("button", "alerta-btn alerta-btn-principal", "Registrar pago"); boton.type = "submit";
        form.append(ayuda, mensaje, boton);
        form.addEventListener("submit", async evento => {
            evento.preventDefault(); boton.disabled = true; mensaje.textContent = "Registrando…";
            const formData = new FormData(form);
            const payload = Object.fromEntries(formData.entries()); payload.cuenta_id = cuenta.id;
            try {
                const respuesta = await fetch("/admin/nube-cuentas/pagos-pin", { method: "POST", headers: { "Content-Type": "application/json", Accept: "application/json", "X-Requested-With": "XMLHttpRequest" }, body: JSON.stringify(payload) });
                const resultado = await respuesta.json();
                if (!respuesta.ok || !resultado.ok) throw new Error(resultado.mensaje || "No se pudo registrar el pago.");
                await cargarAlertas();
                registro.replaceChildren(); const fin = el("div", "alerta-finalizado"); fin.append(el("strong", "", "✓ Pago registrado correctamente")); if (resultado.pago.cuenta_reactivada) fin.append(el("strong", "", "✓ Cuenta reactivada"), el("p", "", "La cuenta ya está disponible nuevamente en Nube.")); fin.append(el("p", "", `Plan: ${resultado.pago.plan}`), el("p", "", `Valor: ${dinero(resultado.pago.valor_pin)}`), el("p", "", `Fecha registrada: ${fechaTexto(resultado.pago.fecha_aplicacion)}`), el("p", "", `Próximo pago: ${fechaTexto(resultado.pago.proximo_pago)}`)); const listo = el("button", "alerta-btn alerta-btn-principal", "Listo"); listo.type = "button"; listo.onclick = cerrarModal; fin.append(listo); registro.append(fin);
            } catch (error) { mensaje.className = "alerta-form-mensaje error"; mensaje.textContent = error.message; }
            finally { boton.disabled = false; }
        });
        registro.append(form); modalBody.append(registro);
        const historial = el("section", "alerta-seccion-pin"); historial.append(el("h3", "", "Historial de pagos"));
        const items = el("div", "alerta-historial");
        if (!datos.historial_pin.length) items.append(el("p", "", "Aún no hay pagos en el historial."));
        datos.historial_pin.forEach(pago => items.append(el("div", "alerta-historial-item", `${fechaTexto(pago.fecha_aplicacion)} · ${pago.plan || "Sin plan"} · ${dinero(pago.valor_pin)} · ${pago.dias_estimados} días`)));
        historial.append(items); modalBody.append(historial);
    }
    function renderLista() {
        lista.replaceChildren(); const visibles = estado.alertas.filter(coincide);
        if (!visibles.length) { const vacio = el("div", "alertas-vacio"); vacio.append(el("strong", "", estado.alertas.length ? "Sin coincidencias" : "Todo al día"), el("p", "", estado.alertas.length ? "Prueba con otro filtro." : "No hay alertas operativas pendientes.")); lista.append(vacio); return; }
        visibles.forEach(alerta => {
            const tarjeta = el("button", `alerta-card prioridad-${alerta.prioridad}`); tarjeta.type = "button"; tarjeta.setAttribute("aria-label", `Abrir alerta: ${alerta.titulo}`);
            const icono = el("span", "alerta-card-icono"); const i = el("i"); i.dataset.lucide = alerta.accion === "actualizar_pago_pin" ? "key-round" : alerta.accion === "gestionar_perfil" ? "user-round" : "cloud"; icono.append(i);
            const contenido = el("span", "alerta-card-contenido"); const superior = el("span", "alerta-card-superior"); superior.append(el("span", "alerta-card-prioridad", alerta.prioridad), el("span", "alerta-card-tipo", alerta.tipo.replaceAll("_", " "))); contenido.append(superior, el("strong", "alerta-card-titulo", alerta.titulo), el("span", "alerta-card-desc", alerta.descripcion));
            const meta = el("span", "alerta-card-meta"); [alerta.plataforma, alerta.cliente, `Cuenta #${alerta.cuenta_id}`, fechaTexto(alerta.fecha_objetivo), diasTexto(alerta)].filter(Boolean).forEach(texto => meta.append(el("span", "", texto))); contenido.append(meta);
            tarjeta.append(icono, contenido, el("span", "alerta-card-flecha", "→")); tarjeta.addEventListener("click", () => abrirModal(alerta)); lista.append(tarjeta);
        });
        window.lucide?.createIcons();
    }
    function cambiarFiltro(filtro) { estado.filtro = filtro; document.querySelectorAll("[data-filtro]").forEach(b => { const activo = b.dataset.filtro === filtro; b.classList.toggle("activo", activo); b.setAttribute("aria-pressed", String(activo)); }); renderLista(); }
    async function cargarAlertas() {
        if (estado.cargando) return; estado.cargando = true; centro.setAttribute("aria-busy", "true"); document.getElementById("alertasActualizar").disabled = true;
        try { const respuesta = await fetch("/admin/nube-cuentas/alertas", { headers: { Accept: "application/json" } }); const datos = await respuesta.json(); if (!respuesta.ok || !datos.ok) throw new Error(datos.mensaje || "No se pudieron cargar las alertas."); estado.alertas = datos.alertas || []; [["alertasTotal", "total"], ["alertasCriticas", "criticas"], ["alertasHoy", "hoy"], ["alertasProximas", "proximas"]].forEach(([id, key]) => document.getElementById(id).textContent = datos.resumen?.[key] ?? 0); renderLista(); }
        catch (error) { const bloque = el("div", "alertas-error"); bloque.append(el("strong", "", "No pudimos cargar las alertas"), el("p", "", error.message)); const reintentar = el("button", "alerta-btn", "Reintentar"); reintentar.addEventListener("click", cargarAlertas); bloque.append(reintentar); lista.replaceChildren(bloque); }
        finally { estado.cargando = false; centro.setAttribute("aria-busy", "false"); document.getElementById("alertasActualizar").disabled = false; }
    }
    [["todas", "Todas"], ["criticas", "Críticas"], ["hoy", "Hoy"], ["proximas", "Próximas"]].forEach(([valor, texto]) => { const b = el("button", `alertas-chip${valor === "todas" ? " activo" : ""}`, texto); b.type = "button"; b.dataset.filtro = valor; b.setAttribute("aria-pressed", String(valor === "todas")); b.addEventListener("click", () => cambiarFiltro(valor)); document.getElementById("alertasChips").append(b); });
    document.querySelectorAll(".alertas-stat").forEach(b => b.addEventListener("click", () => cambiarFiltro(b.dataset.filtro)));
    document.getElementById("alertasTipo").addEventListener("change", e => { estado.tipo = e.target.value; renderLista(); });
    document.getElementById("alertasActualizar").addEventListener("click", cargarAlertas);
    document.querySelectorAll("[data-cerrar-modal]").forEach(b => b.addEventListener("click", cerrarModal));
    document.addEventListener("keydown", e => { if (e.key === "Escape" && modal.classList.contains("abierto")) cerrarModal(); });
    cargarAlertas();
});
