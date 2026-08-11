document.addEventListener("DOMContentLoaded", () => {
    const app = document.getElementById("cortesApp");
    if (!app) return;

    const lista = document.getElementById("cortesLista");
    const modal = document.getElementById("corteModal");
    const body = document.getElementById("corteModalBody");
    const estado = {
        pendientes: [],
        historial: [],
        tab: "pendientes",
        tipo: "",
        cantidad: "",
        fecha: "",
        busqueda: "",
        expandidas: new Set()
    };

    const el = (tag, clase, texto) => {
        const nodo = document.createElement(tag);
        if (clase) nodo.className = clase;
        if (texto !== undefined) nodo.textContent = texto;
        return nodo;
    };
    const fecha = valor => valor ? new Intl.DateTimeFormat("es-CO", { dateStyle: "medium", timeZone: "UTC" }).format(new Date(String(valor).slice(0, 10) + "T00:00:00Z")) : "Sin fecha";
    const diasVencido = valor => {
        if (!valor) return "-";
        const base = new Date(String(valor).slice(0, 10) + "T00:00:00Z");
        const hoy = new Date(new Date().toISOString().slice(0, 10) + "T00:00:00Z");
        const dias = Math.max(Math.floor((hoy - base) / 86400000), 0);
        return dias === 0 ? "Vence hoy" : `${dias} dia${dias === 1 ? "" : "s"}`;
    };
    const tiempoDesde = valor => {
        if (!valor) return "Sin hora";
        const fechaBase = new Date(String(valor).replace(" ", "T"));
        if (Number.isNaN(fechaBase.getTime())) return fecha(valor);
        const horas = Math.max(Math.floor((Date.now() - fechaBase.getTime()) / 3600000), 0);
        if (horas < 1) return "Hace menos de 1 h";
        if (horas < 24) return `Hace ${horas} h`;
        const dias = Math.floor(horas / 24);
        return `Hace ${dias} dia${dias === 1 ? "" : "s"}`;
    };
    const cerrar = () => {
        modal.classList.remove("abierto");
        modal.setAttribute("aria-hidden", "true");
        document.body.classList.remove("nube-op-modal-abierto");
    };
    const dato = (k, v) => {
        const n = el("div", "nube-op-dato");
        n.append(el("span", "", k), el("strong", "", v || "-"));
        return n;
    };
    const campo = (id, label, value, type = "text") => {
        const wrap = el("label", "nube-op-field");
        const input = el("input");
        input.id = id;
        input.type = type;
        input.value = value || "";
        input.autocomplete = "off";
        wrap.append(el("span", "", label), input);
        return { wrap, input };
    };
    const seccion = (titulo, contenido) => {
        const box = el("section", "nube-op-block");
        box.append(el("h3", "", titulo), contenido);
        return box;
    };
    const servicioTitulo = s => s.servicio_tipo === "perfil" ? (s.nombre_perfil || `Perfil #${s.perfil_id}`) : "Cuenta completa";
    const serviciosTexto = grupo => (grupo.servicios || []).map(servicioTitulo).join(" + ");
    const textoBusqueda = grupo => {
        const cuenta = grupo.cuenta_madre || {};
        const hijos = (grupo.servicios || []).map(s => `${s.nombre_cliente} ${s.telefono} ${s.telefono_normalizado} ${s.nombre_perfil} ${s.pin} ${s.plataforma}`).join(" ");
        return `${cuenta.correo} ${cuenta.plataforma} ${cuenta.tipo} ${grupo.tipo} ${hijos}`.toLowerCase();
    };
    const coincide = item => {
        if (estado.tab === "historial") {
            const texto = `${item.nombre_cliente} ${item.telefono} ${item.telefono_normalizado} ${item.nombre_perfil} ${item.plataforma} ${item.correo} ${item.tipo_notificacion}`.toLowerCase();
            return (!estado.tipo || (item.tipo_notificacion || "individual") === estado.tipo) && (!estado.busqueda || texto.includes(estado.busqueda));
        }
        const pendientes = (item.servicios || []).length;
        const fechaNotificacion = String(item.fecha_notificacion || "").slice(0, 10);
        return (!estado.tipo || (item.servicios || []).some(s => (s.tipo_notificacion || "individual") === estado.tipo))
            && (!estado.cantidad || (estado.cantidad === "uno" ? pendientes === 1 : pendientes > 1))
            && (!estado.fecha || fechaNotificacion === estado.fecha)
            && (!estado.busqueda || textoBusqueda(item).includes(estado.busqueda));
    };

    function pintar() {
        lista.replaceChildren();
        document.querySelectorAll("[data-tab]").forEach(b => b.classList.toggle("activo", b.dataset.tab === estado.tab));
        const origen = estado.tab === "pendientes" ? estado.pendientes : estado.historial;
        const items = origen.filter(coincide);
        if (!items.length) {
            const vacio = el("div", "nube-op-vacio");
            vacio.append(el("strong", "", "Sin registros"), el("p", "", estado.tab === "pendientes" ? "No hay cuentas madre pendientes de corte." : "No hay historial para estos filtros."));
            lista.append(vacio);
            return;
        }
        items.forEach(item => estado.tab === "pendientes" ? pintarMadre(item) : pintarHistorial(item));
        window.lucide?.createIcons();
    }

    function pintarMadre(grupo) {
        const cuenta = grupo.cuenta_madre || {};
        const servicios = grupo.servicios || [];
        const id = String(grupo.cuenta_id || cuenta.id || "");
        const abierta = estado.expandidas.has(id) || servicios.length === 1 && servicios[0].servicio_tipo === "cuenta_completa";
        const card = el("article", `nube-op-card nube-op-madre ${grupo.tipo || ""}`);
        const expandir = el("button", "nube-op-expand", abierta ? "v" : ">");
        expandir.type = "button";
        expandir.title = abierta ? "Contraer" : "Expandir";
        expandir.onclick = () => {
            abierta ? estado.expandidas.delete(id) : estado.expandidas.add(id);
            pintar();
        };
        const icono = el("span", "nube-op-platform", (cuenta.plataforma || "?").slice(0, 1).toUpperCase());
        const info = el("div", "nube-op-card-main");
        info.append(el("h3", "", cuenta.plataforma || "Cuenta madre"));
        info.append(el("p", "", cuenta.correo || "Sin correo"));
        const tags = el("div", "nube-op-tags");
        tags.append(
            el("span", "", `${cuenta.perfiles_totales || servicios.length || 1} perfiles`),
            el("span", "oro", `${servicios.length} pendiente${servicios.length === 1 ? "" : "s"} de corte`),
            el("span", "", `Notificacion mas antigua: ${tiempoDesde(grupo.fecha_notificacion)}`),
            el("span", "", "Estado: PENDIENTE")
        );
        if (grupo.vigentes_count) tags.append(el("span", "", `${grupo.vigentes_count} vigentes / renovados`));
        if (servicios.some(s => s.tipo_notificacion === "combo")) tags.append(el("span", "oro", "Incluye combo"));
        info.append(tags);
        const acciones = el("div", "nube-op-row-actions");
        const ver = el("a", "nube-op-accion", "Ver");
        ver.href = `/admin/nube-cuentas?cuenta=${encodeURIComponent(id)}`;
        const editar = el("button", "nube-op-accion", "Editar");
        editar.type = "button";
        editar.onclick = () => abrir(grupo, "cuenta");
        const cortar = el("button", "nube-op-accion nube-op-danger", servicios.length > 1 ? `Cortar pendientes (${servicios.length})` : "Cortar");
        cortar.type = "button";
        cortar.onclick = () => abrir(grupo, "corte");
        acciones.append(ver, editar, cortar);
        card.append(expandir, icono, info, acciones);
        lista.append(card);
        if (abierta) {
            const hijos = el("div", "nube-op-hijos");
            servicios.forEach(s => hijos.append(filaHijo(s, grupo)));
            lista.append(hijos);
        }
    }

    function filaHijo(s, grupo) {
        const row = el("div", "nube-op-hijo");
        const info = el("div", "nube-op-hijo-main");
        info.append(el("strong", "", servicioTitulo(s)));
        info.append(el("small", "", `${s.nombre_cliente || grupo.cliente || "Cliente"} · ${s.telefono_normalizado || s.telefono || grupo.telefono_normalizado || "Sin telefono"}`));
        const tags = el("div", "nube-op-tags");
        tags.append(
            el("span", "", `Vencio: ${fecha(s.fecha_vencimiento)}`),
            el("span", "", `Notificado: ${tiempoDesde(s.fecha_notificacion || grupo.fecha_notificacion)}`),
            el("span", "", `PIN perfil: ${s.pin || "No aplica"}`),
            el("span", "", (s.tipo_notificacion || "individual").toUpperCase())
        );
        info.append(tags);
        const acciones = el("div", "nube-op-row-actions");
        if (s.servicio_tipo === "perfil") {
            const pin = el("button", "nube-op-accion", "Editar PIN");
            pin.type = "button";
            pin.onclick = () => abrirPinPerfil(s, grupo);
            acciones.append(pin);
        }
        const cortar = el("button", "nube-op-accion nube-op-danger", "Cortar");
        cortar.type = "button";
        cortar.onclick = () => cortarServicios([s]);
        acciones.append(cortar);
        row.append(info, acciones);
        return row;
    }

    function pintarHistorial(item) {
        const card = el("article", `nube-op-card ${item.estado_corte || ""}`);
        const info = el("div", "nube-op-card-main");
        info.append(el("h3", "", item.plataforma || "Servicio"));
        info.append(el("p", "", item.descripcion || (item.servicio_tipo === "perfil" ? `${item.nombre_perfil || "Perfil"} · ${item.nombre_cliente || "Cliente"}` : item.nombre_cliente || "Cuenta completa")));
        const tags = el("div", "nube-op-tags");
        tags.append(
            el("span", "", item.estado_corte || "historial"),
            el("span", "", `Actualizado: ${tiempoDesde(item.fecha_actualizacion)}`),
            el("span", "", item.tipo_notificacion || "individual")
        );
        info.append(tags);
        card.append(info, el("span", "nube-op-status", item.estado_corte || "historial"));
        lista.append(card);
    }

    function bloqueServicios(grupo, seleccionable = false) {
        const wrap = el("div", "nube-op-stack");
        (grupo.servicios || []).forEach(s => {
            const item = el("div", "nube-op-service-card");
            const titulo = el("div", "nube-op-service-title");
            if (seleccionable) {
                const check = el("input");
                check.type = "checkbox";
                check.checked = true;
                check.dataset.servicioTipo = s.servicio_tipo;
                check.dataset.servicioId = s.servicio_id;
                check.dataset.cuentaId = s.cuenta_id;
                check.dataset.perfilId = s.perfil_id || "";
                titulo.append(check);
            }
            titulo.append(el("strong", "", servicioTitulo(s)));
            const grid = el("div", "nube-op-grid nube-op-grid-servicio");
            grid.append(
                dato("Cliente", s.nombre_cliente || grupo.cliente),
                dato("Telefono", s.telefono_normalizado || s.telefono || grupo.telefono_normalizado || grupo.telefono),
                dato("Vencimiento", fecha(s.fecha_vencimiento)),
                dato("Notificacion", tiempoDesde(s.fecha_notificacion || grupo.fecha_notificacion)),
                dato("PIN del perfil", s.servicio_tipo === "perfil" ? (s.pin || "No aplica") : "No aplica"),
                dato("Estado", "Pendiente")
            );
            item.append(titulo, grid);
            wrap.append(item);
        });
        return wrap;
    }

    function abrir(grupo, modo = "cuenta") {
        const servicios = grupo.servicios || [];
        const primero = servicios[0] || {};
        const cuenta = grupo.cuenta_madre || primero.cuenta_madre || {};
        modal.classList.add("abierto");
        modal.setAttribute("aria-hidden", "false");
        document.body.classList.add("nube-op-modal-abierto");
        document.getElementById("corteModalTipo").textContent = `${cuenta.plataforma || primero.plataforma || "Servicio"} · ${servicios.length} pendiente${servicios.length === 1 ? "" : "s"}`;
        document.getElementById("corteModalTitulo").textContent = cuenta.correo || "Cuenta madre";
        body.replaceChildren();

        const cuentaGrid = el("div", "nube-op-form-grid");
        const correo = campo("corteCuentaCorreo", "Correo", cuenta.correo);
        const pass = campo("corteCuentaContrasena", "Contrasena", cuenta.contrasena, "password");
        const pin = campo("corteCuentaPin", "PIN de cuenta", cuenta.pin);
        const passWrap = el("div", "nube-op-password");
        const ojo = el("button", "nube-op-eye", "Ver");
        ojo.type = "button";
        ojo.onclick = () => {
            pass.input.type = pass.input.type === "password" ? "text" : "password";
            ojo.textContent = pass.input.type === "password" ? "Ver" : "Ocultar";
        };
        passWrap.append(pass.wrap, ojo);
        cuentaGrid.append(
            dato("Plataforma", cuenta.plataforma || primero.plataforma),
            dato("Tipo / modalidad", `${cuenta.tipo || "-"} / ${cuenta.modalidad || "-"}`),
            dato("Plan", cuenta.plan || "No aplica"),
            correo.wrap,
            passWrap,
            pin.wrap
        );
        body.append(seccion("Datos de la cuenta", cuentaGrid));
        body.append(seccion("Perfiles pendientes", bloqueServicios(grupo, true)));

        const notifGrid = el("div", "nube-op-grid");
        notifGrid.append(dato("Notificacion mas antigua", grupo.fecha_notificacion ? fecha(String(grupo.fecha_notificacion).slice(0, 10)) : "-"), dato("Tiempo desde notificacion", tiempoDesde(grupo.fecha_notificacion)), dato("Medio", grupo.medio || "manual"));
        body.append(seccion("Notificacion", notifGrid));

        const motivo = el("textarea", "nube-op-motivo");
        motivo.placeholder = "Nota operativa opcional";
        body.append(seccion("Historial operativo / nota", motivo));

        const msg = el("div", "nube-op-msg");
        const acciones = el("div", "nube-op-actions");
        const gestionar = el("a", "nube-op-secondary", "Ver cuenta");
        gestionar.href = `/admin/nube-cuentas?cuenta=${encodeURIComponent(cuenta.id || primero.cuenta_id || "")}`;
        const guardar = el("button", "nube-op-primary", "Guardar cambios de cuenta");
        guardar.type = "button";
        guardar.onclick = () => guardarCuenta(cuenta, grupo, servicios, correo.input, pass.input, pin.input, guardar, msg);
        const seleccionados = el("button", "nube-op-danger", `Cortar seleccionados (${servicios.length})`);
        seleccionados.type = "button";
        seleccionados.onclick = () => {
            const marcados = [...body.querySelectorAll("input[type='checkbox']:checked")].map(input => ({
                servicio_tipo: input.dataset.servicioTipo,
                servicio_id: Number(input.dataset.servicioId),
                cuenta_id: Number(input.dataset.cuentaId),
                perfil_id: input.dataset.perfilId ? Number(input.dataset.perfilId) : null
            }));
            cortarServicios(marcados, motivo.value, seleccionados, msg);
        };
        acciones.append(gestionar, guardar, seleccionados);
        body.append(acciones, msg);
        if (modo === "corte") seleccionados.focus();
        window.lucide?.createIcons();
    }

    async function guardarCuenta(cuenta, grupo, servicios, correo, pass, pin, boton, msg) {
        boton.disabled = true;
        msg.className = "nube-op-msg";
        msg.textContent = "Guardando cuenta madre...";
        try {
            const payload = {
                cuenta_id: cuenta.id || grupo.cuenta_id,
                correo: correo.value.trim(),
                contrasena: pass.value.trim(),
                pin: pin.value.trim()
            };
            const r = await fetch("/admin/nube-cortes/cuenta/credenciales", { method: "POST", headers: { "Content-Type": "application/json", Accept: "application/json" }, body: JSON.stringify(payload) });
            const data = await r.json();
            if (!r.ok || !data.ok) throw new Error(data.mensaje || "No se pudo guardar.");
            Object.assign(cuenta, data.cuenta || payload);
            if (grupo.cuenta_madre) Object.assign(grupo.cuenta_madre, cuenta);
            servicios.forEach(s => { if (s.cuenta_madre) Object.assign(s.cuenta_madre, cuenta); });
            msg.textContent = data.mensaje || "Datos de la cuenta actualizados.";
            pintar();
        } catch (error) {
            msg.className = "nube-op-msg error";
            msg.textContent = error.message;
        } finally {
            boton.disabled = false;
        }
    }

    function abrirPinPerfil(servicio, grupo) {
        abrir(grupo, "cuenta");
        const msg = body.querySelector(".nube-op-msg");
        const bloque = el("section", "nube-op-block");
        const pin = campo("cortePerfilPin", `PIN del perfil ${servicio.nombre_perfil || servicio.perfil_id}`, servicio.pin);
        const guardar = el("button", "nube-op-primary", "Guardar PIN del perfil");
        guardar.type = "button";
        guardar.onclick = async () => {
            guardar.disabled = true;
            msg.className = "nube-op-msg";
            msg.textContent = "Guardando PIN del perfil...";
            try {
                const payload = { cuenta_id: servicio.cuenta_id, perfil_id: servicio.perfil_id, pin: pin.input.value.trim() };
                const r = await fetch("/admin/nube-cortes/perfil/pin", { method: "POST", headers: { "Content-Type": "application/json", Accept: "application/json" }, body: JSON.stringify(payload) });
                const data = await r.json();
                if (!r.ok || !data.ok) throw new Error(data.mensaje || "No se pudo guardar el PIN.");
                servicio.pin = data.perfil?.pin ?? payload.pin;
                msg.textContent = data.mensaje || "PIN del perfil actualizado.";
                pintar();
            } catch (error) {
                msg.className = "nube-op-msg error";
                msg.textContent = error.message;
            } finally {
                guardar.disabled = false;
            }
        };
        bloque.append(el("h3", "", "PIN del perfil"), pin.wrap, guardar);
        body.insertBefore(bloque, body.querySelector(".nube-op-actions"));
    }

    async function cortarServicios(servicios, motivo = "", boton = null, msg = null) {
        if (!servicios.length) {
            if (msg) {
                msg.className = "nube-op-msg error";
                msg.textContent = "Selecciona al menos un pendiente.";
            }
            return;
        }
        if (boton) boton.disabled = true;
        if (msg) {
            msg.className = "nube-op-msg";
            msg.textContent = "Revalidando y cortando...";
        }
        try {
            const r = await fetch("/admin/nube-cortes/cortar", { method: "POST", headers: { "Content-Type": "application/json", Accept: "application/json" }, body: JSON.stringify({ servicios, motivo }) });
            const data = await r.json();
            if (!r.ok || !data.ok) throw new Error(data.mensaje || "No se pudo cortar.");
            cerrar();
            await cargar();
        } catch (error) {
            if (msg) {
                msg.className = "nube-op-msg error";
                msg.textContent = error.message;
            }
            if (boton) boton.disabled = false;
        }
    }

    async function cargar() {
        app.setAttribute("aria-busy", "true");
        const r = await fetch("/admin/nube-cortes/datos", { headers: { Accept: "application/json" } });
        const data = await r.json();
        if (!r.ok || !data.ok) {
            lista.replaceChildren(el("div", "nube-op-error", data.mensaje || "No se pudo cargar."));
            return;
        }
        estado.pendientes = data.pendientes || [];
        estado.historial = data.historial || [];
        document.getElementById("cortesCuentas").textContent = data.resumen?.cuentas_pendientes ?? data.resumen?.pendientes ?? 0;
        document.getElementById("cortesServiciosPendientes").textContent = data.resumen?.servicios_pendientes ?? data.resumen?.servicios_individuales ?? 0;
        document.getElementById("cortesHoy").textContent = data.resumen?.notificados_hoy ?? 0;
        document.getElementById("cortesCombos").textContent = data.resumen?.combos ?? 0;
        document.getElementById("cortesIndividuales").textContent = data.resumen?.individuales ?? 0;
        pintar();
        app.setAttribute("aria-busy", "false");
    }

    document.getElementById("cortesBuscar").addEventListener("input", e => { estado.busqueda = e.target.value.trim().toLowerCase(); pintar(); });
    document.getElementById("cortesTipo").addEventListener("change", e => { estado.tipo = e.target.value; pintar(); });
    document.getElementById("cortesCantidad").addEventListener("change", e => { estado.cantidad = e.target.value; pintar(); });
    document.getElementById("cortesFecha").addEventListener("change", e => { estado.fecha = e.target.value; pintar(); });
    document.querySelectorAll("[data-tab]").forEach(b => b.addEventListener("click", () => { estado.tab = b.dataset.tab; pintar(); }));
    document.getElementById("cortesActualizar").addEventListener("click", cargar);
    document.querySelectorAll("[data-cerrar-modal]").forEach(b => b.addEventListener("click", cerrar));
    document.addEventListener("keydown", e => { if (e.key === "Escape") cerrar(); });
    cargar();
});
