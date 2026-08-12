document.addEventListener("DOMContentLoaded", () => {
    const app = document.getElementById("cortesApp");
    if (!app) return;

    const lista = document.getElementById("cortesLista");
    const botonActualizar = document.getElementById("cortesActualizar");
    let actualizando = false;
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
    const toast = (mensaje, error = false) => {
        document.querySelector(".nube-op-toast")?.remove();
        const aviso = el("div", `nube-op-toast${error ? " error" : ""}`, mensaje);
        aviso.setAttribute("role", error ? "alert" : "status");
        document.body.append(aviso);
        window.setTimeout(() => aviso.remove(), 2800);
    };
    const fecha = valor => valor ? new Intl.DateTimeFormat("es-CO", { dateStyle: "medium", timeZone: "UTC" }).format(new Date(String(valor).slice(0, 10) + "T00:00:00Z")) : "Sin fecha";
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
    const servicioTitulo = s => s.servicio_tipo === "perfil" ? (s.nombre_perfil || `Perfil #${s.perfil_id}`) : "Cuenta completa";
    const clasePlataforma = valor => String(valor || "otra").toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "otra";
    const notificarCambioNube = cuentaId => {
        try {
            localStorage.setItem("pechy:nube-cuenta-actualizada", JSON.stringify({ cuenta_id: Number(cuentaId), fecha: Date.now() }));
        } catch (_) {
            // El dato ya fue persistido; la sincronizacion entre pestañas es auxiliar.
        }
    };
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
        const abierta = estado.expandidas.has(id);
        const card = el("article", `nube-op-card nube-op-madre plataforma-${clasePlataforma(cuenta.plataforma)} ${grupo.tipo || ""}`);
        const expandir = el("button", "nube-op-expand", abierta ? "⌄" : ">");
        expandir.type = "button";
        expandir.title = abierta ? "Contraer cuenta" : "Expandir cuenta";
        expandir.setAttribute("aria-expanded", String(abierta));
        expandir.onclick = () => {
            abierta ? estado.expandidas.delete(id) : estado.expandidas.add(id);
            pintar();
        };
        const icono = el("span", "nube-op-platform", (cuenta.plataforma || "?").slice(0, 1).toUpperCase());
        const info = el("div", "nube-op-card-main");
        info.append(el("h3", "", cuenta.plataforma || "Cuenta madre"));
        info.append(el("p", "nube-op-email", cuenta.correo || "Sin correo"));
        const pendiente = el("strong", "nube-op-pendientes", `${servicios.length} perfil${servicios.length === 1 ? "" : "es"} pendiente${servicios.length === 1 ? "" : "s"}`);
        card.append(expandir, icono, info, pendiente);
        lista.append(card);
        if (abierta) lista.append(panelCuenta(grupo));
    }

    function panelCuenta(grupo) {
        const cuenta = grupo.cuenta_madre || {};
        const servicios = grupo.servicios || [];
        const panel = el("section", "nube-op-cuenta-panel");
        const msg = el("div", "nube-op-msg");

        const credenciales = el("div", "nube-op-credenciales");
        const cabecera = el("div", "nube-op-section-title");
        cabecera.append(el("div", "", "Datos de cuenta"), el("span", "", `${servicios.length} pendiente${servicios.length === 1 ? "" : "s"}`));
        const plataforma = dato("Plataforma", cuenta.plataforma || servicios[0]?.plataforma || "-");
        const correo = campo(`corteCorreo-${cuenta.id}`, "Correo", cuenta.correo);
        const pass = campo(`cortePass-${cuenta.id}`, "Contraseña", cuenta.contrasena, "password");
        const passWrap = el("div", "nube-op-password");
        const ojo = el("button", "nube-op-eye");
        ojo.type = "button";
        ojo.setAttribute("aria-pressed", "false");
        ojo.innerHTML = '<i data-lucide="eye" aria-hidden="true"></i><span>Mostrar</span>';
        ojo.setAttribute("aria-label", "Mostrar contraseña");
        ojo.onclick = () => {
            const oculta = pass.input.type === "password";
            pass.input.type = oculta ? "text" : "password";
            ojo.setAttribute("aria-pressed", String(oculta));
            ojo.innerHTML = `<i data-lucide="${oculta ? "eye-off" : "eye"}" aria-hidden="true"></i><span>${oculta ? "Ocultar" : "Mostrar"}</span>`;
            ojo.setAttribute("aria-label", `${oculta ? "Ocultar" : "Mostrar"} contraseña`);
            window.lucide?.createIcons();
        };
        passWrap.append(pass.wrap, ojo);
        const guardar = el("button", "nube-op-primary", "Guardar cambios");
        guardar.type = "button";
        guardar.onclick = () => guardarCuenta(cuenta, grupo, correo.input, pass.input, guardar, msg);
        const form = el("div", "nube-op-account-form");
        form.append(plataforma, correo.wrap, passWrap, guardar);
        credenciales.append(cabecera, form);

        const perfiles = el("div", "nube-op-perfiles");
        perfiles.append(el("div", "nube-op-section-title", "Perfiles pendientes"));
        const motivo = el("textarea", "nube-op-motivo");
        motivo.placeholder = "Nota operativa opcional";
        const seleccionados = el("button", "nube-op-danger nube-op-seleccionados", "Cortar seleccionados (0)");
        seleccionados.type = "button";
        seleccionados.hidden = true;
        const actualizarSeleccion = () => {
            const total = panel.querySelectorAll(".nube-op-profile-check:checked").length;
            seleccionados.textContent = `Cortar seleccionados (${total})`;
            seleccionados.hidden = total === 0;
        };
        servicios.forEach(s => perfiles.append(filaPerfil(s, grupo, msg, actualizarSeleccion)));
        seleccionados.onclick = () => {
            const marcados = [...panel.querySelectorAll(".nube-op-profile-check:checked")].map(input => ({
                servicio_tipo: input.dataset.servicioTipo,
                servicio_id: Number(input.dataset.servicioId),
                cuenta_id: Number(input.dataset.cuentaId),
                perfil_id: input.dataset.perfilId ? Number(input.dataset.perfilId) : null
            }));
            cortarServicios(marcados, motivo.value, seleccionados, msg);
        };

        const detalles = el("details", "nube-op-details");
        const summary = el("summary", "", "Más detalles");
        const detalleGrid = el("div", "nube-op-details-grid");
        detalleGrid.append(
            dato("Fecha de notificación", grupo.fecha_notificacion ? fecha(grupo.fecha_notificacion) : "-"),
            dato("Tiempo desde notificación", tiempoDesde(grupo.fecha_notificacion)),
            dato("Medio", grupo.medio || "manual")
        );
        const notaWrap = el("label", "nube-op-note");
        notaWrap.append(el("span", "", "Historial operativo / nota para el corte"), motivo);
        detalles.append(summary, detalleGrid, notaWrap);

        const acciones = el("div", "nube-op-selection-actions");
        acciones.append(seleccionados);
        panel.append(credenciales, perfiles, acciones, detalles, msg);
        return panel;
    }

    function filaPerfil(s, grupo, msg, actualizarSeleccion) {
        const row = el("article", "nube-op-profile-row");
        const check = el("input", "nube-op-profile-check");
        check.type = "checkbox";
        check.setAttribute("aria-label", `Seleccionar ${servicioTitulo(s)}`);
        check.dataset.servicioTipo = s.servicio_tipo;
        check.dataset.servicioId = s.servicio_id;
        check.dataset.cuentaId = s.cuenta_id;
        check.dataset.perfilId = s.perfil_id || "";
        check.onchange = actualizarSeleccion;

        const identidad = el("div", "nube-op-profile-identity");
        identidad.append(el("strong", "", servicioTitulo(s)));
        identidad.append(el("small", "", `${s.nombre_cliente || grupo.cliente || "Cliente"} · ${s.telefono_normalizado || s.telefono || grupo.telefono_normalizado || "Sin teléfono"}`));
        identidad.append(el("span", "", `Vence: ${fecha(s.fecha_vencimiento)}`));

        const pinBox = el("div", "nube-op-profile-pin");
        pinBox.append(el("span", "", "PIN del perfil"), el("strong", "", s.servicio_tipo === "perfil" ? (s.pin || "Sin PIN") : "No aplica"));
        const acciones = el("div", "nube-op-row-actions");
        if (s.servicio_tipo === "perfil") {
            const editarPin = el("button", "nube-op-accion", "Editar PIN");
            editarPin.type = "button";
            editarPin.onclick = () => mostrarEditorPin(s, pinBox, editarPin, msg);
            acciones.append(editarPin);
        }
        const cortar = el("button", "nube-op-accion nube-op-danger", "Cortar");
        cortar.type = "button";
        cortar.onclick = () => cortarServicios([s], "", cortar, msg);
        acciones.append(cortar);
        row.append(check, identidad, pinBox, acciones);
        return row;
    }

    function mostrarEditorPin(servicio, pinBox, boton, msg) {
        if (pinBox.querySelector("input")) return;
        const input = el("input", "nube-op-pin-input");
        input.value = servicio.pin || "";
        input.placeholder = "PIN";
        input.autocomplete = "off";
        pinBox.replaceChildren(el("span", "", "PIN del perfil"), input);
        boton.textContent = "Guardar PIN";
        boton.onclick = async () => {
            boton.disabled = true;
            msg.className = "nube-op-msg";
            msg.textContent = "Guardando PIN del perfil...";
            try {
                const payload = { cuenta_id: servicio.cuenta_id, perfil_id: servicio.perfil_id, pin: input.value.trim() };
                const r = await fetch("/admin/nube-cortes/perfil/pin", { method: "POST", headers: { "Content-Type": "application/json", Accept: "application/json" }, body: JSON.stringify(payload) });
                const data = await r.json();
                if (!r.ok || !data.ok) throw new Error(data.mensaje || "No se pudo guardar el PIN.");
                servicio.pin = data.perfil?.pin ?? payload.pin;
                pinBox.replaceChildren(el("span", "", "PIN del perfil"), el("strong", "", servicio.pin || "Sin PIN"));
                boton.textContent = "Editar PIN";
                boton.onclick = () => mostrarEditorPin(servicio, pinBox, boton, msg);
                notificarCambioNube(data.perfil?.cuenta_id || servicio.cuenta_id);
                msg.textContent = data.mensaje || "PIN del perfil actualizado.";
            } catch (error) {
                msg.className = "nube-op-msg error";
                msg.textContent = error.message;
            } finally {
                boton.disabled = false;
            }
        };
        input.focus();
        input.select();
    }

    function pintarHistorial(item) {
        const card = el("article", `nube-op-card ${item.estado_corte || ""}`);
        const info = el("div", "nube-op-card-main");
        info.append(el("h3", "", item.plataforma || "Servicio"));
        info.append(el("p", "", item.descripcion || (item.servicio_tipo === "perfil" ? `${item.nombre_perfil || "Perfil"} · ${item.nombre_cliente || "Cliente"}` : item.nombre_cliente || "Cuenta completa")));
        const tags = el("div", "nube-op-tags");
        tags.append(el("span", "", item.estado_corte || "historial"), el("span", "", `Actualizado: ${tiempoDesde(item.fecha_actualizacion)}`), el("span", "", item.tipo_notificacion || "individual"));
        info.append(tags);
        card.append(info, el("span", "nube-op-status", item.estado_corte || "historial"));
        lista.append(card);
    }

    async function guardarCuenta(cuenta, grupo, correo, pass, boton, msg) {
        boton.disabled = true;
        msg.className = "nube-op-msg";
        msg.textContent = "Guardando cuenta madre...";
        try {
            const payload = { cuenta_id: cuenta.id || grupo.cuenta_id, correo: correo.value.trim(), contrasena: pass.value.trim() };
            const r = await fetch("/admin/nube-cortes/cuenta/credenciales", { method: "POST", headers: { "Content-Type": "application/json", Accept: "application/json" }, body: JSON.stringify(payload) });
            const data = await r.json();
            if (!r.ok || !data.ok) throw new Error(data.mensaje || "No se pudo guardar.");
            const persistida = data.cuenta || {};
            Object.assign(cuenta, persistida);
            correo.value = persistida.correo ?? correo.value;
            pass.value = persistida.contrasena ?? pass.value;
            const panel = boton.closest(".nube-op-cuenta-panel");
            const correoMadre = panel?.previousElementSibling?.querySelector(".nube-op-email");
            if (correoMadre) correoMadre.textContent = cuenta.correo || "Sin correo";
            notificarCambioNube(persistida.id || payload.cuenta_id);
            msg.textContent = data.mensaje || "Datos de la cuenta actualizados.";
        } catch (error) {
            msg.className = "nube-op-msg error";
            msg.textContent = error.message;
        } finally {
            boton.disabled = false;
        }
    }

    async function cortarServicios(servicios, motivo = "", boton = null, msg = null) {
        if (!servicios.length) return;
        if (!window.confirm(`¿Confirmas cortar ${servicios.length} servicio${servicios.length === 1 ? "" : "s"}?`)) return;
        if (boton) boton.disabled = true;
        if (msg) {
            msg.className = "nube-op-msg";
            msg.textContent = "Procesando corte...";
        }
        try {
            const r = await fetch("/admin/nube-cortes/cortar", { method: "POST", headers: { "Content-Type": "application/json", Accept: "application/json" }, body: JSON.stringify({ servicios, motivo }) });
            const data = await r.json();
            if (!r.ok || !data.ok) throw new Error(data.mensaje || "No se pudo completar el corte.");
            const cuentaIds = [...new Set(servicios.map(s => Number(s.cuenta_id)).filter(Boolean))];
            localStorage.setItem("pechy:nube-cuenta-actualizada", JSON.stringify({ cuenta_ids: cuentaIds, fecha: Date.now(), origen: "cortes" }));
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
        try {
            const r = await fetch("/admin/nube-cortes/datos", { headers: { Accept: "application/json" } });
            const data = await r.json();
            if (!r.ok || !data.ok) throw new Error(data.mensaje || "No se pudo cargar.");
            estado.pendientes = data.pendientes || [];
            estado.historial = data.historial || [];
            document.getElementById("cortesCuentas").textContent = data.resumen?.cuentas_pendientes ?? data.resumen?.pendientes ?? 0;
            document.getElementById("cortesServiciosPendientes").textContent = data.resumen?.servicios_pendientes ?? data.resumen?.servicios_individuales ?? 0;
            document.getElementById("cortesHoy").textContent = data.resumen?.notificados_hoy ?? 0;
            document.getElementById("cortesCombos").textContent = data.resumen?.combos ?? 0;
            document.getElementById("cortesIndividuales").textContent = data.resumen?.individuales ?? 0;
            pintar();
        } catch (error) {
            lista.replaceChildren(el("div", "nube-op-error", error.message));
            throw error;
        } finally {
            app.setAttribute("aria-busy", "false");
        }
    }
    async function actualizar() {
        if (actualizando) return;
        actualizando = true; botonActualizar.disabled = true; botonActualizar.classList.add("actualizando");
        botonActualizar.setAttribute("aria-busy", "true"); botonActualizar.querySelector("span").textContent = "Actualizando...";
        try { await cargar(); toast("Información actualizada."); }
        catch (_) { toast("No pudimos actualizar. Intenta nuevamente.", true); }
        finally {
            actualizando = false; botonActualizar.disabled = false; botonActualizar.classList.remove("actualizando");
            botonActualizar.setAttribute("aria-busy", "false"); botonActualizar.querySelector("span").textContent = "Actualizar";
        }
    }

    document.getElementById("cortesBuscar").addEventListener("input", e => { estado.busqueda = e.target.value.trim().toLowerCase(); pintar(); });
    document.getElementById("cortesTipo").addEventListener("change", e => { estado.tipo = e.target.value; pintar(); });
    document.getElementById("cortesCantidad").addEventListener("change", e => { estado.cantidad = e.target.value; pintar(); });
    document.getElementById("cortesFecha").addEventListener("change", e => { estado.fecha = e.target.value; pintar(); });
    document.querySelectorAll("[data-tab]").forEach(b => b.addEventListener("click", () => { estado.tab = b.dataset.tab; pintar(); }));
    botonActualizar.addEventListener("click", actualizar);
    cargar().catch(() => {});
});
