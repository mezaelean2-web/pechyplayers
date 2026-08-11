document.addEventListener("DOMContentLoaded", () => {
    const app = document.getElementById("notificacionesApp");
    if (!app) return;
    const lista = document.getElementById("notificacionesLista");
    const modal = document.getElementById("notificacionModal");
    const body = document.getElementById("notificacionModalBody");
    const estado = { pendientes: [], notificados: [], tab: "pendientes", tipo: "", busqueda: "", activa: null };
    const el = (tag, clase, texto) => { const nodo = document.createElement(tag); if (clase) nodo.className = clase; if (texto !== undefined) nodo.textContent = texto; return nodo; };
    const fecha = valor => valor ? new Intl.DateTimeFormat("es-CO", { dateStyle: "medium", timeZone: "UTC" }).format(new Date(`${valor}T00:00:00Z`)) : "Sin fecha";
    const textoServicios = unidad => (unidad.servicios || []).map(s => s.plataforma || "Servicio").join(" + ");
    const cerrar = () => { modal.classList.remove("abierto"); modal.setAttribute("aria-hidden", "true"); document.body.classList.remove("nube-op-modal-abierto"); };
    const dato = (k, v) => { const n = el("div", "nube-op-dato"); n.append(el("span", "", k), el("strong", "", v || "-")); return n; };
    const coincide = unidad => {
        const texto = `${unidad.cliente} ${unidad.telefono} ${unidad.telefono_normalizado} ${textoServicios(unidad)}`.toLowerCase();
        return (!estado.tipo || unidad.tipo === estado.tipo) && (!estado.busqueda || texto.includes(estado.busqueda));
    };
    function pintar() {
        lista.replaceChildren();
        const origen = estado.tab === "pendientes" ? estado.pendientes : estado.notificados;
        const items = origen.filter(coincide);
        document.querySelectorAll("[data-tab]").forEach(b => b.classList.toggle("activo", b.dataset.tab === estado.tab));
        if (!items.length) {
            const vacio = el("div", "nube-op-vacio");
            vacio.append(el("strong", "", "Sin registros"), el("p", "", estado.tab === "pendientes" ? "No hay vencimientos pendientes de notificacion." : "No hay notificaciones para estos filtros."));
            lista.append(vacio); return;
        }
        items.forEach(unidad => {
            const card = el("article", `nube-op-card ${unidad.tipo}`);
            const info = el("div");
            info.append(el("h3", "", unidad.cliente || "Cliente"));
            info.append(el("p", "", `${unidad.tipo === "combo" ? "COMBO - " : ""}${textoServicios(unidad)}`));
            const tags = el("div", "nube-op-tags");
            tags.append(el("span", "oro", unidad.tipo.toUpperCase()), el("span", "", `Vence: ${fecha(unidad.fecha_vencimiento)}`), el("span", "", unidad.telefono_normalizado || "Sin telefono"));
            if (unidad.fecha_entrega) tags.append(el("span", "", `Entrega: ${fecha(unidad.fecha_entrega)}`));
            info.append(tags);
            const accion = el("button", "nube-op-accion", estado.tab === "pendientes" ? "Notificar" : "Ver");
            accion.type = "button"; accion.addEventListener("click", () => abrir(unidad));
            card.append(info, accion); lista.append(card);
        });
        window.lucide?.createIcons();
    }
    function serviciosDetalle(unidad) {
        const wrap = el("div", "nube-op-servicios");
        (unidad.servicios || []).forEach(s => {
            const item = el("div", "nube-op-servicio");
            item.append(el("strong", "", s.plataforma || "Servicio"), el("small", "", `${s.servicio_tipo === "perfil" ? (s.nombre_perfil || `Perfil #${s.perfil_id}`) : "Cuenta completa"} - vence ${fecha(s.fecha_vencimiento)}`));
            wrap.append(item);
        });
        return wrap;
    }
    function abrir(unidad) {
        estado.activa = unidad;
        modal.classList.add("abierto"); modal.setAttribute("aria-hidden", "false"); document.body.classList.add("nube-op-modal-abierto");
        document.getElementById("notificacionModalTipo").textContent = unidad.tipo.toUpperCase();
        document.getElementById("notificacionModalTitulo").textContent = estado.tab === "pendientes" ? "Preparar notificacion" : "Notificacion registrada";
        body.replaceChildren();
        const grid = el("div", "nube-op-grid");
        grid.append(dato("Cliente", unidad.cliente), dato("Telefono", unidad.telefono_normalizado || unidad.telefono), dato("Vencimiento", fecha(unidad.fecha_vencimiento)));
        body.append(grid, serviciosDetalle(unidad));
        const mensaje = el("textarea", "nube-op-textarea"); mensaje.value = unidad.mensaje || ""; mensaje.readOnly = estado.tab !== "pendientes"; body.append(mensaje);
        const msg = el("div", "nube-op-msg");
        const acciones = el("div", "nube-op-actions");
        const copiar = el("button", "", "Copiar mensaje"); copiar.type = "button"; copiar.onclick = async () => { await navigator.clipboard.writeText(mensaje.value); msg.textContent = "Mensaje copiado. Marca como notificado solo cuando confirmes el envio."; };
        const wa = el("a", "", "Enviar por WhatsApp"); wa.href = unidad.whatsapp_url || "#"; wa.target = "_blank"; wa.rel = "noopener"; wa.onclick = () => { msg.textContent = "WhatsApp abierto. Confirma manualmente si el mensaje fue enviado."; };
        acciones.append(copiar, wa);
        if (estado.tab === "pendientes") {
            const confirmar = el("button", "nube-op-primary", "Marcar como notificado"); confirmar.type = "button";
            confirmar.onclick = async () => {
                confirmar.disabled = true; msg.textContent = "Registrando...";
                try {
                    const r = await fetch("/admin/nube-notificaciones/notificar", { method: "POST", headers: { "Content-Type": "application/json", Accept: "application/json" }, body: JSON.stringify({ servicios: unidad.servicios, mensaje: mensaje.value, medio: "manual" }) });
                    const data = await r.json(); if (!r.ok || !data.ok) throw new Error(data.mensaje || "No se pudo registrar.");
                    cerrar(); await cargar();
                } catch (error) { msg.className = "nube-op-msg error"; msg.textContent = error.message; confirmar.disabled = false; }
            };
            acciones.append(confirmar);
        }
        body.append(acciones, msg);
    }
    async function cargar() {
        app.setAttribute("aria-busy", "true");
        const r = await fetch("/admin/nube-notificaciones/datos", { headers: { Accept: "application/json" } });
        const data = await r.json();
        if (!r.ok || !data.ok) { lista.replaceChildren(el("div", "nube-op-error", data.mensaje || "No se pudo cargar.")); return; }
        estado.pendientes = data.pendientes || []; estado.notificados = data.notificados || [];
        document.getElementById("notifPendientes").textContent = data.resumen?.pendientes ?? 0;
        document.getElementById("notifHoy").textContent = data.resumen?.individuales ?? 0;
        document.getElementById("notifNotificadosHoy").textContent = data.resumen?.notificados_hoy ?? 0;
        document.getElementById("notifCombos").textContent = data.resumen?.combos ?? 0;
        pintar(); app.setAttribute("aria-busy", "false");
    }
    document.getElementById("notificacionesBuscar").addEventListener("input", e => { estado.busqueda = e.target.value.trim().toLowerCase(); pintar(); });
    document.getElementById("notificacionesTipo").addEventListener("change", e => { estado.tipo = e.target.value; pintar(); });
    document.querySelectorAll("[data-tab]").forEach(b => b.addEventListener("click", () => { estado.tab = b.dataset.tab; pintar(); }));
    document.querySelectorAll("[data-filtro]").forEach(b => b.addEventListener("click", () => { estado.tipo = b.dataset.filtro === "combo" ? "combo" : ""; pintar(); }));
    document.getElementById("notificacionesActualizar").addEventListener("click", cargar);
    document.querySelectorAll("[data-cerrar-modal]").forEach(b => b.addEventListener("click", cerrar));
    document.addEventListener("keydown", e => { if (e.key === "Escape") cerrar(); });
    cargar();
});
