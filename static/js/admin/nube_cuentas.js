document.addEventListener(
    "DOMContentLoaded",
    () => {
        const duracionesInventarioManual = [30, 60, 90, 120, 150, 180];
        const requiereDuracionInventario = plataforma => {
            const tokens = String(plataforma || "")
                .normalize("NFD").replace(/[\u0300-\u036f]/g, "")
                .toLowerCase().match(/[a-z0-9]+/g) || [];
            return tokens.includes("youtube") || tokens.includes("spotify");
        };
        const etiquetaDuracionInventario = dias => Number(dias) % 30 === 0
            ? `${Number(dias) / 30} ${Number(dias) === 30 ? "mes" : "meses"}`
            : `${dias} dias`;
        const aplicarPoliticaDuracionInventario = (plataforma, modalidad, select) => {
            if (!select) return;
            const requiere = requiereDuracionInventario(plataforma);
            select.value = "";
            select.replaceChildren(new Option("Seleccionar duración", ""));
            duracionesInventarioManual.forEach(dias =>
                select.add(new Option(etiquetaDuracionInventario(dias), String(dias)))
            );
            select.required = requiere;
            select.disabled = !requiere;
            select.closest("label").hidden = !requiere;
        };
        const plataformaNueva = document.getElementById("nubeNuevaPlataforma");
        const duracionNueva = document.getElementById("nubeNuevaDuracion");
        const tipoNueva = document.getElementById("nubeTipoCuenta");
        const refrescarDuracionNueva = () => aplicarPoliticaDuracionInventario(
            plataformaNueva?.value,
            tipoNueva?.value === "perfil" ? "perfiles" : "cuenta_completa",
            duracionNueva
        );
        plataformaNueva?.addEventListener("input", refrescarDuracionNueva);
        tipoNueva?.addEventListener("change", refrescarDuracionNueva);

        const paginaNubeAdmin = document.querySelector(".nube-page");
        const csrfNubeAdmin = paginaNubeAdmin?.dataset.csrfToken || "";
        const modalRenombrarPlataforma = document.getElementById("modalRenombrarPlataforma");
        const formRenombrarPlataforma = document.getElementById("formRenombrarPlataforma");
        const plataformaNombreActual = document.getElementById("plataformaNombreActual");
        const plataformaNombreActualVisible = document.getElementById("plataformaNombreActualVisible");
        const plataformaNombreNuevo = document.getElementById("plataformaNombreNuevo");
        const mensajeRenombrarPlataforma = document.getElementById("mensajeRenombrarPlataforma");
        const modalEditarCuenta = document.getElementById("modalEditarCuenta");
        const formEditarCuenta = document.getElementById("formEditarCuenta");
        const editarCuentaId = document.getElementById("editarCuentaId");
        const editarPlataforma = document.getElementById("editarPlataforma");
        const editarCorreo = document.getElementById("editarCorreo");
        const editarContrasena = document.getElementById("editarContrasena");
        const editarPin = document.getElementById("editarPin");
        const editarModalidad = document.getElementById("editarModalidad");
        const editarDuracion = document.getElementById("editarDuracion");
        const editarCantidadPerfiles = document.getElementById("editarCantidadPerfiles");
        const editarPerfilesGrupo = document.getElementById("editarPerfilesGrupo");
        const editarImpactoModalidad = document.getElementById("editarImpactoModalidad");
        const editarCuentaMensaje = document.getElementById("editarCuentaMensaje");
        let contextoEditarCuenta = null;

        const mostrarMensajeRenombre = (texto, error = true) => {
            if (!mensajeRenombrarPlataforma) return;
            mensajeRenombrarPlataforma.hidden = !texto;
            mensajeRenombrarPlataforma.textContent = texto || "";
            mensajeRenombrarPlataforma.classList.toggle("error", error);
        };
        const abrirRenombrePlataforma = nombre => {
            if (!modalRenombrarPlataforma || !nombre) return;
            plataformaNombreActual.value = nombre;
            plataformaNombreActualVisible.value = nombre;
            plataformaNombreNuevo.value = nombre;
            mostrarMensajeRenombre("");
            modalRenombrarPlataforma.classList.add("abierto");
            modalRenombrarPlataforma.setAttribute("aria-hidden", "false");
            document.body.classList.add("nube-modal-abierto");
            requestAnimationFrame(() => {
                plataformaNombreNuevo.focus();
                plataformaNombreNuevo.select();
            });
        };
        const cerrarRenombrePlataforma = () => {
            modalRenombrarPlataforma?.classList.remove("abierto");
            modalRenombrarPlataforma?.setAttribute("aria-hidden", "true");
            document.body.classList.remove("nube-modal-abierto");
            formRenombrarPlataforma?.reset();
            mostrarMensajeRenombre("");
        };
        modalRenombrarPlataforma?.querySelectorAll("[data-cerrar-renombrar-plataforma]").forEach(
            control => control.addEventListener("click", cerrarRenombrePlataforma)
        );
        formRenombrarPlataforma?.addEventListener("submit", async evento => {
            evento.preventDefault();
            mostrarMensajeRenombre("");
            const actual = String(plataformaNombreActual.value || "").replace(/\s+/g, " ").trim();
            const nuevo = String(plataformaNombreNuevo.value || "").replace(/\s+/g, " ").trim();
            if (!nuevo) {
                mostrarMensajeRenombre("Escribe un nombre nuevo para la plataforma.");
                return;
            }
            const clave = valor => valor.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
            if (clave(actual) === clave(nuevo)) {
                mostrarMensajeRenombre("El nuevo nombre equivale al nombre actual.");
                return;
            }
            if (!window.confirm(`Renombrar plataforma\n\n${actual}\n→\n${nuevo}\n\nSe actualizarán las cuentas y reglas reseller operativas asociadas.`)) return;
            const boton = formRenombrarPlataforma.querySelector("button[type='submit']");
            boton.disabled = true;
            try {
                const respuesta = await fetch("/admin/nube-cuentas/plataformas/renombrar", {
                    method: "POST",
                    headers: {"Content-Type":"application/json", Accept:"application/json", "X-CSRF-Token":csrfNubeAdmin},
                    body: JSON.stringify({nombre_actual:actual, nombre_nuevo:nuevo})
                });
                const resultado = await respuesta.json();
                if (!respuesta.ok || !resultado.ok) throw new Error(resultado.mensaje || "No se pudo renombrar la plataforma.");
                cerrarRenombrePlataforma();
                window.location.reload();
            } catch (error) {
                mostrarMensajeRenombre(error.message || "No se pudo renombrar la plataforma.");
            } finally {
                boton.disabled = false;
            }
        });

        const mensajeEdicion = (texto, error = true) => {
            if (!editarCuentaMensaje) return;
            editarCuentaMensaje.hidden = !texto;
            editarCuentaMensaje.textContent = texto || "";
            editarCuentaMensaje.classList.toggle("error", error);
        };
        const refrescarCamposEdicion = () => {
            const perfiles = editarModalidad?.value === "perfiles";
            if (editarPerfilesGrupo) editarPerfilesGrupo.hidden = !perfiles;
            if (editarCantidadPerfiles) editarCantidadPerfiles.required = perfiles;
            const anterior = contextoEditarCuenta?.cuenta?.modalidad || "cuenta_completa";
            const cambia = anterior !== editarModalidad?.value;
            if (editarImpactoModalidad) {
                editarImpactoModalidad.hidden = !cambia;
                editarImpactoModalidad.textContent = cambia
                    ? (perfiles
                        ? `Se crearán ${editarCantidadPerfiles?.value || 0} perfiles vacíos. No se modificará ninguna asignación.`
                        : `Se retirarán ${contextoEditarCuenta?.perfiles?.length || 0} perfiles únicamente si están completamente vacíos.`)
                    : "";
            }
        };
        async function abrirEdicionCuenta(cuentaId) {
            mensajeEdicion("");
            const respuesta = await fetch(`/admin/nube-cuentas/${encodeURIComponent(cuentaId)}/edicion`, {headers:{Accept:"application/json"}});
            const resultado = await respuesta.json();
            if (!respuesta.ok || !resultado.ok) throw new Error(resultado.mensaje || "No se pudo cargar la cuenta.");
            contextoEditarCuenta = resultado;
            const cuenta = resultado.cuenta;
            editarCuentaId.value = cuenta.id;
            editarPlataforma.value = cuenta.plataforma || "";
            editarCorreo.value = cuenta.correo || "";
            editarContrasena.value = cuenta.contrasena || "";
            editarPin.value = cuenta.pin || "";
            editarModalidad.value = cuenta.modalidad || "cuenta_completa";
            editarCantidadPerfiles.value = cuenta.cantidad_perfiles || resultado.perfiles.length || 1;
            aplicarPoliticaDuracionInventario(cuenta.plataforma, cuenta.modalidad, editarDuracion);
            editarDuracion.value = cuenta.duracion_unidad_dias == null ? "" : String(cuenta.duracion_unidad_dias);
            refrescarCamposEdicion();
            modalEditarCuenta.classList.add("abierto"); modalEditarCuenta.setAttribute("aria-hidden", "false");
            document.body.classList.add("nube-modal-abierto");
        }
        function cerrarEdicionCuenta() {
            modalEditarCuenta?.classList.remove("abierto"); modalEditarCuenta?.setAttribute("aria-hidden", "true");
            document.body.classList.remove("nube-modal-abierto"); contextoEditarCuenta = null;
        }
        async function solicitarEliminacionCuenta(cuentaId) {
            const llamar = async confirmacion => {
                const respuesta = await fetch(`/admin/nube-cuentas/${encodeURIComponent(cuentaId)}/eliminar`, {
                    method:"POST", headers:{"Content-Type":"application/json",Accept:"application/json","X-CSRF-Token":csrfNubeAdmin},
                    body:JSON.stringify({confirmacion})
                });
                const resultado = await respuesta.json(); return {respuesta, resultado};
            };
            let {respuesta, resultado} = await llamar(false);
            if (resultado.codigo !== "confirmacion_requerida") throw new Error(resultado.mensaje || "La cuenta no se puede eliminar.");
            const cuenta = resultado.cuenta || {};
            if (!window.confirm(`Eliminar definitivamente la cuenta #${cuenta.id}\n${cuenta.plataforma || ""} · ${cuenta.correo || ""}\n\nEsta acción solo continuará si sigue completamente descartable.`)) return;
            ({respuesta, resultado} = await llamar(true));
            if (!respuesta.ok || !resultado.ok) throw new Error(resultado.mensaje || "No se pudo eliminar la cuenta.");
            window.location.reload();
        }
        editarPlataforma?.addEventListener("input", () => {
            const valor = editarDuracion?.value;
            aplicarPoliticaDuracionInventario(editarPlataforma.value, editarModalidad?.value, editarDuracion);
            if ([...editarDuracion.options].some(opcion => opcion.value === valor)) editarDuracion.value = valor;
        });
        editarModalidad?.addEventListener("change", refrescarCamposEdicion);
        editarCantidadPerfiles?.addEventListener("input", refrescarCamposEdicion);
        modalEditarCuenta?.querySelectorAll("[data-cerrar-edicion]").forEach(control => control.addEventListener("click", cerrarEdicionCuenta));
        formEditarCuenta?.addEventListener("submit", async evento => {
            evento.preventDefault(); mensajeEdicion("");
            const cambiaModalidad = contextoEditarCuenta?.cuenta?.modalidad !== editarModalidad.value;
            const cambiaPerfiles = editarModalidad.value === "perfiles" &&
                Number(contextoEditarCuenta?.cuenta?.cantidad_perfiles || contextoEditarCuenta?.perfiles?.length || 0) !== Number(editarCantidadPerfiles.value || 0);
            const requiereConfirmacion = cambiaModalidad || cambiaPerfiles;
            const detalleConfirmacion = cambiaModalidad ? editarImpactoModalidad?.textContent :
                `La configuración cambiará de ${contextoEditarCuenta?.perfiles?.length || 0} a ${editarCantidadPerfiles.value || 0} perfiles.`;
            const confirmar = !requiereConfirmacion || window.confirm(`${detalleConfirmacion || "Cambiar configuración"}\n\n¿Confirmas este cambio estructural?`);
            if (!confirmar) return;
            const boton = formEditarCuenta.querySelector("button[type='submit']"); boton.disabled = true;
            try {
                const payload = {plataforma:editarPlataforma.value,correo:editarCorreo.value,contrasena:editarContrasena.value,
                    pin:editarPin.value,modalidad:editarModalidad.value,duracion_unidad_dias:editarDuracion.disabled ? null : editarDuracion.value,
                    cantidad_perfiles:Number(editarCantidadPerfiles.value || 0),confirmar_cambio_modalidad:requiereConfirmacion};
                const respuesta = await fetch(`/admin/nube-cuentas/${encodeURIComponent(editarCuentaId.value)}/edicion`, {
                    method:"POST",headers:{"Content-Type":"application/json",Accept:"application/json","X-CSRF-Token":csrfNubeAdmin},body:JSON.stringify(payload)});
                const resultado = await respuesta.json();
                if (!respuesta.ok || !resultado.ok) throw new Error(resultado.mensaje || "No se pudo guardar la cuenta.");
                cerrarEdicionCuenta(); await refreshCuentaNube(editarCuentaId.value);
            } catch(error) { mensajeEdicion(error.message, true); } finally { boton.disabled = false; }
        });
        refrescarDuracionNueva();
        // CENTRO DE INVENTARIO: búsqueda y filtros locales combinables.
        const inventario = {
            busqueda: "", plataforma: "", tipo: "", estado: "", asignacion: "",
            pago: "", tipoAvanzado: ""
        };
        const normalizarInventario = valor => String(valor ?? "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
        const claveInventario = valor => normalizarInventario(valor).replace(/\s+/g, "_");
        const colorAutomaticoPlataformaNube = valor => {
            const nombre = normalizarInventario(valor);
            if (!nombre) return "";
            let hash = 2166136261;
            for (const caracter of nombre){
                hash ^= caracter.codePointAt(0);
                hash = Math.imul(hash, 16777619);
            }
            return `hsl(${(hash >>> 0) % 360} 68% 48%)`;
        };
        const normalizarTipoInventario = valor => {
            const clave = claveInventario(valor);
            if (["cuenta_completa", "cuenta_completas", "completa", "completas"].includes(clave)) return "cuenta_completa";
            if (["perfil", "perfiles"].includes(clave)) return "perfiles";
            if (["perfil_extra", "miembro_extra"].includes(clave)) return "perfil_extra";
            if (clave === "plan_estandar") return "plan_estandar";
            return clave;
        };
        const etiquetaTipoInventario = valor => ({
            cuenta_completa: "Cuenta completa",
            perfiles: "Perfiles",
            perfil_extra: "Perfil Extra",
            plan_estandar: "Plan estándar"
        })[normalizarTipoInventario(valor)] || String(valor || "Otros").replaceAll("_", " ").replace(/\b\w/g, letra => letra.toUpperCase());
        const normalizarTelefonoNubeUi = telefono => {
            let numero = String(telefono ?? "").replace(/\D/g, "");
            if (/^3\d{9}$/.test(numero)) numero = `57${numero}`;
            return /^\d{10,15}$/.test(numero) ? numero : "";
        };
        let madresInventario = [...document.querySelectorAll(".nube-cuenta-madre")];
        const crearRegistroInventario = fila => {
            const id = fila.dataset.cuentaId;
            const hijos = [...document.querySelectorAll(`.nube-perfil-row[data-parent-id="${CSS.escape(id)}"]`)];
            const controles = [fila, ...hijos].flatMap(nodo => [...nodo.querySelectorAll("[data-id]")]);
            const secretos = controles.flatMap(control => Object.values(control.dataset));
            return { hijos, texto: normalizarInventario([fila.textContent, ...hijos.map(h => h.textContent), ...secretos, id].join(" ")) };
        };
        const indiceInventario = new Map(madresInventario.map(fila => [fila, crearRegistroInventario(fila)]));
        const resultadoInventario = document.createElement("div");
        resultadoInventario.className = "nube-resultado-filtros";
        resultadoInventario.setAttribute("aria-live", "polite");
        document.querySelector(".nube-tabla-card")?.prepend(resultadoInventario);
        const selectPlataformaInventario = document.getElementById("nubeFiltroPlataforma");
        const selectTipoAvanzadoInventario = document.getElementById("nubeFiltroTipoAvanzado");

        function estaAsignadoInventario(nodo){
            return nodo?.dataset?.asignado === "1";
        }

        function coincideEstadoInventario(nodo, filtro){
            if (!filtro) return true;
            if (filtro === "vendida") return estaAsignadoInventario(nodo);
            if (filtro === "vencida") return nodo?.dataset?.estadoReal === "vencida";
            return nodo?.dataset?.estado === filtro;
        }

        function estaVendibleInventario(nodo){
            return !["caida", "papelera", "reemplazada"].includes(String(nodo?.dataset?.estado || ""));
        }

        function esCuentaCompletaDisponibleInventario(fila){
            return fila.dataset.modalidad !== "perfiles" &&
                fila.dataset.estado === "disponible" &&
                !estaAsignadoInventario(fila);
        }

        function sincronizarPlataformaInventario(plataforma){
            inventario.plataforma = plataforma || "";
            const normal = normalizarInventario(inventario.plataforma);
            document.querySelectorAll(".nube-hoja").forEach(boton => {
                const activo = normalizarInventario(boton.dataset.plataforma) === normal;
                boton.classList.toggle("activo", activo);
                boton.setAttribute("aria-pressed", String(activo));
            });
            if (selectPlataformaInventario) selectPlataformaInventario.value = inventario.plataforma;
        }

        function escribirStatInventario(nombre, valor){
            const nodo = document.querySelector(`[data-stat-value="${nombre}"]`);
            if (nodo) nodo.textContent = valor;
        }

        function escribirDetalleStatInventario(nombre, valor){
            const nodo = document.querySelector(`[data-stat-detail="${nombre}"]`);
            if (nodo) nodo.textContent = valor;
        }

        function recalcularMetricasInventario(){
            const cuentas = madresInventario.filter(fila =>
                !inventario.plataforma ||
                normalizarInventario(fila.dataset.plataforma) === normalizarInventario(inventario.plataforma)
            );
            const resumen = {
                total: 0,
                vendidas: 0,
                por_vencer: 0,
                vencidas: 0,
                notificadas: 0,
                caidas: 0,
                perfiles: 0,
                madres: 0,
                completas: 0
            };

            cuentas.forEach(fila => {
                const hijos = indiceInventario.get(fila)?.hijos || [];
                const servicios = fila.dataset.modalidad === "perfiles" ? hijos : [fila];
                resumen.total += servicios.length;
                if (fila.dataset.estadoReal === "caida" || fila.dataset.estado === "caida") resumen.caidas += 1;
                servicios.forEach(servicio => {
                    if (estaAsignadoInventario(servicio)) resumen.vendidas += 1;
                    if (servicio.dataset.estadoReal === "por_vencer" && estaAsignadoInventario(servicio)) resumen.por_vencer += 1;
                    if (servicio.dataset.estadoReal === "vencida" && estaAsignadoInventario(servicio)) resumen.vencidas += 1;
                    if (servicio.dataset.estado === "notificada" && estaAsignadoInventario(servicio)) resumen.notificadas += 1;
                });

                if (fila.dataset.modalidad === "perfiles" && estaVendibleInventario(fila)){
                    const disponibles = hijos.filter(hijo =>
                        hijo.dataset.estado === "disponible" &&
                        !estaAsignadoInventario(hijo)
                    ).length;
                    resumen.perfiles += disponibles;
                    if (disponibles > 0) resumen.madres += 1;
                } else if (esCuentaCompletaDisponibleInventario(fila)){
                    resumen.completas += 1;
                }
            });

            escribirStatInventario("total", resumen.total);
            escribirDetalleStatInventario("total", inventario.plataforma ? "Servicios de la plataforma" : "Capacidad del inventario");
            escribirStatInventario("vendidas", resumen.vendidas);
            escribirStatInventario("por_vencer", resumen.por_vencer);
            escribirStatInventario("vencidas", resumen.vencidas);
            escribirStatInventario("notificadas", resumen.notificadas);
            escribirStatInventario("caidas", resumen.caidas);
            escribirStatInventario("disponibles", resumen.perfiles + resumen.completas);
            escribirDetalleStatInventario("disponibles", `${resumen.madres} madres · ${resumen.perfiles} perfiles · ${resumen.completas} completas`);
        }

        function aplicarIdentidadVisualFilaNube(fila){
            const identidad = identidadVisualNube(fila.dataset.plataforma, fila.dataset.tipo);
            fila.classList.add(`plataforma-${identidad.clase}`);
            if (identidad.colorAutomatico) fila.style.setProperty("--plataforma", identidad.colorAutomatico);
            const icono = fila.querySelector(".nube-plataforma-icono");
            if (icono) icono.textContent = identidad.icono;
            const etiqueta = fila.querySelector(".nube-plataforma-info span");
            if (etiqueta) etiqueta.textContent = identidad.label;
        }

        async function refreshAlertasCompactas(){
            const atajo = document.getElementById("nubeAlertasAtajo");
            if (!atajo) return;
            const respuesta = await fetch("/admin/nube-cuentas/alertas", {headers:{Accept:"application/json"}});
            const datos = await respuesta.json();
            if (!respuesta.ok || !datos.ok) throw new Error("No se pudieron actualizar las alertas.");
            const resumen = datos.resumen || {};
            document.getElementById("nubeAlertasAtajoTitulo").textContent = resumen.total
                ? `${resumen.total} alerta${resumen.total === 1 ? "" : "s"} requieren atención`
                : "Todo está al día";
            document.getElementById("nubeAlertasAtajoResumen").textContent =
                `${resumen.criticas || 0} críticas · ${resumen.hoy || 0} hoy · ${resumen.proximas || 0} próximas`;
        }

        async function refreshCuentaNube(cuentaId){
            const id = String(cuentaId || "");
            const madreAnterior = document.querySelector(`.nube-cuenta-madre[data-cuenta-id="${CSS.escape(id)}"]`);
            if (!madreAnterior) throw new Error("No se encontró la cuenta que se debe actualizar.");
            const estabaExpandida = madreAnterior.querySelector(".nube-expandir-cuenta")?.classList.contains("activo") ||
                [...document.querySelectorAll(`.nube-perfil-row[data-parent-id="${CSS.escape(id)}"]`)].some(fila => !fila.hidden);
            const respuesta = await fetch(`/admin/nube-cuentas/${encodeURIComponent(id)}/resumen`, {headers:{Accept:"application/json"}});
            const resultado = await respuesta.json();
            if (!respuesta.ok || !resultado.ok) throw new Error(resultado.mensaje || "No se pudo actualizar la cuenta.");
            const tablaTemporal = document.createElement("table");
            tablaTemporal.innerHTML = `<tbody>${resultado.html}</tbody>`;
            const filasNuevas = [...tablaTemporal.tBodies[0].rows];
            const registroAnterior = indiceInventario.get(madreAnterior);
            registroAnterior?.hijos.forEach(fila => fila.remove());
            madreAnterior.replaceWith(...filasNuevas);
            indiceInventario.delete(madreAnterior);
            const madreNueva = filasNuevas.find(fila => fila.classList.contains("nube-cuenta-madre"));
            madresInventario = madresInventario.map(fila => fila === madreAnterior ? madreNueva : fila);
            indiceInventario.set(madreNueva, crearRegistroInventario(madreNueva));
            aplicarIdentidadVisualFilaNube(madreNueva);
            if (estabaExpandida) madreNueva.querySelector(".nube-expandir-cuenta")?.click();
            aplicarFiltrosInventario();
            window.lucide?.createIcons();
            refreshAlertasCompactas().catch(() => {});
            return madreNueva;
        }

        function cuentaIdDePerfilNube(perfilId){
            return document.querySelector(`.nube-gestionar-perfil[data-id="${CSS.escape(String(perfilId || ""))}"]`)?.closest(".nube-perfil-row")?.dataset.parentId || "";
        }

        async function refreshPerfilNube(perfilId){
            const cuentaId = cuentaIdDePerfilNube(perfilId);
            if (!cuentaId) throw new Error("No se pudo identificar la cuenta del perfil.");
            return refreshCuentaNube(cuentaId);
        }

        function reportarFalloRefrescoNube(error){
            const recargar = window.confirm(`${error.message || error}\n\n¿Deseas recargar manualmente la página?`);
            if (recargar) window.location.reload();
        }

        let marcaCuentaCortesProcesada = localStorage.getItem("pechy:nube-cuenta-actualizada") || "";
        async function sincronizarCuentaEditadaEnCortes(valor){
            const marca = valor || localStorage.getItem("pechy:nube-cuenta-actualizada") || "";
            if (!marca || marca === marcaCuentaCortesProcesada) return;
            marcaCuentaCortesProcesada = marca;
            let cambio;
            try { cambio = JSON.parse(marca); } catch (_) { return; }
            const ids = [...new Set([cambio?.cuenta_id, ...(cambio?.cuenta_ids || [])].filter(Boolean).map(String))];
            for (const id of ids) {
                if (document.querySelector(`.nube-cuenta-madre[data-cuenta-id="${CSS.escape(id)}"]`)) await refreshCuentaNube(id);
            }
        }
        window.addEventListener("storage", evento => {
            if (evento.key === "pechy:nube-cuenta-actualizada") {
                sincronizarCuentaEditadaEnCortes(evento.newValue).catch(reportarFalloRefrescoNube);
            }
        });
        window.addEventListener("focus", () => {
            sincronizarCuentaEditadaEnCortes().catch(reportarFalloRefrescoNube);
        });

        function poblarTiposAvanzadosInventario(){
            if (!selectTipoAvanzadoInventario) return;
            const tipos = new Map();
            madresInventario.forEach(fila => {
                const tipoMadre = fila.dataset.modalidad === "perfiles" ? "perfiles" : fila.dataset.tipo;
                tipos.set(normalizarTipoInventario(tipoMadre), etiquetaTipoInventario(tipoMadre));
                indiceInventario.get(fila)?.hijos.forEach(hijo =>
                    tipos.set(normalizarTipoInventario(hijo.dataset.tipo), etiquetaTipoInventario(hijo.dataset.tipo))
                );
            });
            [...tipos.entries()].sort((a, b) => a[1].localeCompare(b[1], "es")).forEach(([valor, etiqueta]) => {
                const option = document.createElement("option");
                option.value = valor;
                option.textContent = etiqueta;
                selectTipoAvanzadoInventario.append(option);
            });
        }

        function aplicarFiltrosInventario(){
            let visibles = 0;
            madresInventario.forEach(fila => {
                const registro = indiceInventario.get(fila);
                const coincideBusqueda = !inventario.busqueda || registro.texto.includes(normalizarInventario(inventario.busqueda));
                const coincidePlataforma = !inventario.plataforma || normalizarInventario(fila.dataset.plataforma) === normalizarInventario(inventario.plataforma);
                const tipoFila = normalizarTipoInventario(fila.dataset.modalidad === "perfiles" ? "perfiles" : fila.dataset.tipo);
                const coincideTipo = !inventario.tipo || tipoFila === normalizarTipoInventario(inventario.tipo);
                const filtroCaidas = inventario.estado === "caida";
                const hijosEstado = registro.hijos.filter(hijo => coincideEstadoInventario(hijo, inventario.estado));
                const coincideEstado = !inventario.estado || (filtroCaidas
                    ? fila.dataset.estadoReal === "caida" || fila.dataset.estado === "caida"
                    : coincideEstadoInventario(fila, inventario.estado) || hijosEstado.length > 0);
                const tieneCliente = estaAsignadoInventario(fila) || registro.hijos.some(estaAsignadoInventario);
                const tieneCapacidad = (
                    fila.dataset.modalidad === "perfiles" &&
                    estaVendibleInventario(fila) &&
                    registro.hijos.some(h => h.dataset.estado === "disponible" && !estaAsignadoInventario(h))
                ) || esCuentaCompletaDisponibleInventario(fila);
                const coincideAsignacion = !inventario.asignacion || (inventario.asignacion === "con_cliente" && tieneCliente) || (inventario.asignacion === "sin_cliente" && !tieneCliente) || (inventario.asignacion === "con_capacidad" && tieneCapacidad);
                const coincidePago = !inventario.pago || fila.dataset.tipoPago === inventario.pago;
                const coincideTipoAvanzado = !inventario.tipoAvanzado || tipoFila === inventario.tipoAvanzado || registro.hijos.some(h => normalizarTipoInventario(h.dataset.tipo) === inventario.tipoAvanzado);
                const mostrar = coincideBusqueda && coincidePlataforma && coincideTipo && coincideEstado && coincideAsignacion && coincidePago && coincideTipoAvanzado;
                fila.hidden = !mostrar;
                registro.hijos.forEach(hijo => {
                    if (!mostrar) hijo.hidden = true;
                    else if (inventario.estado) hijo.hidden = filtroCaidas || !coincideEstadoInventario(hijo, inventario.estado);
                });
                if (mostrar) visibles += 1;
            });
            resultadoInventario.textContent = visibles ? `${visibles} cuenta${visibles === 1 ? "" : "s"} en esta vista` : "No hay resultados para los filtros seleccionados.";
            recalcularMetricasInventario();
        }
        let debounceInventario;
        document.getElementById("nubeBuscar")?.addEventListener("input", evento => { clearTimeout(debounceInventario); debounceInventario = setTimeout(() => { inventario.busqueda = evento.target.value; aplicarFiltrosInventario(); }, 180); });
        const hojasPlataformaNube = document.getElementById("nubeHojas");
        hojasPlataformaNube?.addEventListener("click", evento => { const boton = evento.target.closest("[data-plataforma]"); if (!boton) return; sincronizarPlataformaInventario(boton.dataset.plataforma); aplicarFiltrosInventario(); });
        hojasPlataformaNube?.addEventListener("dblclick", evento => {
            const boton = evento.target.closest("[data-plataforma]");
            if (boton?.dataset.plataforma) abrirRenombrePlataforma(boton.dataset.plataforma);
        });
        hojasPlataformaNube?.addEventListener("contextmenu", evento => {
            const boton = evento.target.closest("[data-plataforma]");
            if (!boton?.dataset.plataforma) return;
            evento.preventDefault();
            abrirRenombrePlataforma(boton.dataset.plataforma);
        });
        selectPlataformaInventario?.addEventListener("change", evento => { sincronizarPlataformaInventario(evento.target.value); aplicarFiltrosInventario(); });
        document.getElementById("nubeTipos")?.addEventListener("click", evento => { const boton = evento.target.closest("[data-tipo]"); if (!boton) return; inventario.tipo = boton.dataset.tipo; document.querySelectorAll("#nubeTipos [data-tipo]").forEach(b => { const activo = b === boton; b.classList.toggle("activo", activo); b.setAttribute("aria-pressed", String(activo)); }); aplicarFiltrosInventario(); });
        const abrirFiltrosInventario = document.getElementById("nubeAbrirFiltros"), panelFiltrosInventario = document.getElementById("nubeFiltrosPanel");
        abrirFiltrosInventario?.addEventListener("click", () => { const abrir = panelFiltrosInventario.hidden; panelFiltrosInventario.hidden = !abrir; abrirFiltrosInventario.setAttribute("aria-expanded", String(abrir)); requestAnimationFrame(actualizarAlturaStickyNube); });
        document.getElementById("nubeFiltroEstado")?.addEventListener("change", evento => { inventario.estado = evento.target.value; aplicarFiltrosInventario(); });
        document.getElementById("nubeFiltroAsignacion")?.addEventListener("change", evento => { inventario.asignacion = evento.target.value; aplicarFiltrosInventario(); });
        document.getElementById("nubeFiltroPago")?.addEventListener("change", evento => { inventario.pago = evento.target.value; aplicarFiltrosInventario(); });
        selectTipoAvanzadoInventario?.addEventListener("change", evento => { inventario.tipoAvanzado = evento.target.value; aplicarFiltrosInventario(); });
        document.getElementById("nubeLimpiarFiltros")?.addEventListener("click", () => { Object.keys(inventario).forEach(k => inventario[k] = ""); document.getElementById("nubeBuscar").value = ""; document.getElementById("nubeFiltroEstado").value = ""; document.getElementById("nubeFiltroAsignacion").value = ""; document.getElementById("nubeFiltroPago").value = ""; if (selectTipoAvanzadoInventario) selectTipoAvanzadoInventario.value = ""; sincronizarPlataformaInventario(""); document.querySelector("#nubeTipos [data-tipo='']")?.click(); aplicarFiltrosInventario(); });
        document.querySelector(".nube-resumen")?.addEventListener("click", evento => { const tarjeta = evento.target.closest("[data-inventario-estado]"); if (!tarjeta) return; inventario.estado = tarjeta.dataset.inventarioEstado; document.getElementById("nubeFiltroEstado").value = inventario.estado; document.querySelectorAll("[data-inventario-estado]").forEach(t => t.classList.toggle("activo", t === tarjeta)); aplicarFiltrosInventario(); });
        const registryVisualNube = [
            { prueba: v => v.includes("perfil_extra") || v.includes("miembro_extra"), clase: "netflix", label: "Perfil Extra", icono: "N" },
            { prueba: v => v.includes("netflix"), clase: "netflix", label: "Netflix", icono: "N" },
            { prueba: v => v.includes("disney_premium"), clase: "disney-premium", label: "Disney Premium", icono: "D+" },
            { prueba: v => v.includes("disney"), clase: "disney", label: "Disney+", icono: "D+" },
            { prueba: v => v.includes("max_basica"), clase: "max-basica", label: "Max Básica", icono: "M" },
            { prueba: v => v.includes("max_premium"), clase: "max-premium", label: "Max Premium", icono: "M" },
            { prueba: v => v.includes("max") || v.includes("hbo"), clase: "max", label: "Max", icono: "M" },
            { prueba: v => v.includes("prime") || v.includes("amazon"), clase: "prime", label: "Prime Video", icono: "P" },
            { prueba: v => v.includes("paramount"), clase: "paramount", label: "Paramount+", icono: "P+" },
            { prueba: v => v.includes("vix"), clase: "vix", label: "Vix", icono: "V" },
            { prueba: v => v === "dgo" || v.includes("directv") || v.includes("directv_go"), clase: "directv-go", label: "DIRECTV GO", icono: "DG" }
        ];
        const identidadVisualNube = (plataforma, tipo = "") => {
            const clave = claveInventario(`${plataforma || ""} ${tipo || ""}`);
            return registryVisualNube.find(item => item.prueba(clave)) ||
                { clase: "otra", label: String(plataforma || "Otra"), icono: String(plataforma || "O").slice(0, 1).toUpperCase(),
                    colorAutomatico: colorAutomaticoPlataformaNube(plataforma) };
        };
        document.querySelectorAll("[data-plataforma],.nube-cuenta-madre").forEach(nodo => {
            const identidad = identidadVisualNube(nodo.dataset.plataforma, nodo.dataset.tipo);
            nodo.classList.add(`plataforma-${identidad.clase}`);
            if (identidad.colorAutomatico) nodo.style.setProperty("--plataforma", identidad.colorAutomatico);
            const icono = nodo.matches(".nube-hoja") ? nodo.querySelector("span") : nodo.querySelector(".nube-plataforma-icono");
            if (icono) icono.textContent = identidad.icono;
            if (nodo.matches(".nube-hoja") && nodo.dataset.plataforma){
                [...nodo.childNodes].filter(n => n.nodeType === Node.TEXT_NODE).forEach(n => { n.textContent = identidad.label; });
            }
            const etiqueta = nodo.querySelector?.(".nube-plataforma-info span");
            if (etiqueta) etiqueta.textContent = identidad.label;
        });
        document.querySelector(".nube-tabla")?.addEventListener("click", evento => {
            const fila = evento.target.closest(".nube-cuenta-madre,.nube-perfil-row"); if (!fila) return;
            const madre = fila.matches(".nube-cuenta-madre") ? fila : document.querySelector(`.nube-cuenta-madre[data-cuenta-id="${CSS.escape(fila.dataset.parentId || "")}"]`);
            const ver = evento.target.closest(".nube-ver-cuenta,.nube-ver-perfil");
            if (ver) { abrirDrawer(ver); return; }
            const editarCuenta = evento.target.closest(".nube-editar-cuenta");
            if (editarCuenta) {
                abrirEdicionCuenta(editarCuenta.dataset.id).catch(error => window.alert(error.message));
                return;
            }
            const eliminarCuenta = evento.target.closest(".nube-eliminar-cuenta");
            if (eliminarCuenta) {
                solicitarEliminacionCuenta(eliminarCuenta.dataset.id).catch(error => window.alert(error.message));
                return;
            }
            const gestionarPerfil = evento.target.closest(".nube-gestionar-perfil");
            if (gestionarPerfil) { abrirGestionPerfil(gestionarPerfil); return; }
            const gestionar = evento.target.closest(".nube-gestionar-cuenta");
            if (gestionar) {
                if (gestionar.dataset.modalidad !== "perfiles" && gestionar.dataset.estado === "disponible"){
                    abrirModalAsignarCuenta(gestionar);
                } else {
                    const perfiles = indiceInventario.get(madre)?.hijos.map(h => h.querySelector(".nube-gestionar-perfil")).filter(Boolean) || [];
                    if (perfiles.length === 1) perfiles[0].click();
                    else madre?.querySelector(".nube-expandir-cuenta")?.click();
                }
                return;
            }
            const recordatorio = evento.target.closest(".nube-recordatorio-cuenta");
            if (recordatorio) {
                const control = fila.querySelector(".nube-ver-cuenta,.nube-ver-perfil,.nube-gestionar-cuenta,.nube-gestionar-perfil");
                abrirModalRecordatorioCuenta(control, fila);
                return;
            }
            const whatsapp = evento.target.closest(".nube-accion-whatsapp");
            if (whatsapp) {
                const control = fila.querySelector(".nube-ver-cuenta,.nube-ver-perfil,.nube-gestionar-perfil");
                if (fila.matches(".nube-cuenta-madre") && fila.dataset.modalidad === "perfiles"){
                    abrirSelectorWhatsappFila(whatsapp, fila);
                } else {
                    const numero = normalizarTelefonoNubeUi(control?.dataset.telefono || fila.dataset.telefono);
                    if (numero) window.open(`https://wa.me/${numero}`, "_blank", "noopener,noreferrer");
                }
                return;
            }
            const mas = evento.target.closest(".nube-mas-acciones");
            if (mas) { evento.stopPropagation(); abrirMenuAccionesNube(mas, fila); return; }
        });
        poblarTiposAvanzadosInventario();
        sincronizarPlataformaInventario("");
        aplicarFiltrosInventario();

        // Sticky coordinado: toolbar + encabezado real de tabla.
        const paginaNube = document.querySelector(".nube-page");
        const toolbarInventario = document.querySelector(".nube-toolbar-premium");
        const tablaInventario = document.querySelector(".nube-tabla");
        const wrapperInventario = document.querySelector(".nube-tabla-wrapper");
        const tarjetaInventario = document.querySelector(".nube-tabla-card");
        const cabeceraInventario = tablaInventario?.querySelector("thead");
        let stickyRafNube = null;
        let stickyTablaNube = null;
        let stickyTablaClonNube = null;

        function crearStickyTablaNube(){
            if (!wrapperInventario || !tarjetaInventario || !tablaInventario || !cabeceraInventario) return;
            stickyTablaNube = document.createElement("div");
            stickyTablaNube.className = "nube-tabla-sticky-shell";
            stickyTablaNube.hidden = true;
            stickyTablaNube.setAttribute("aria-hidden", "true");
            const viewport = document.createElement("div");
            viewport.className = "nube-tabla-sticky-viewport";
            stickyTablaClonNube = document.createElement("table");
            stickyTablaClonNube.className = "nube-tabla nube-tabla-sticky-clone";
            stickyTablaClonNube.append(cabeceraInventario.cloneNode(true));
            viewport.append(stickyTablaClonNube);
            stickyTablaNube.append(viewport);
            tarjetaInventario.insertBefore(stickyTablaNube, wrapperInventario);
        }

        function sincronizarStickyTablaNube(){
            if (!stickyTablaNube || !stickyTablaClonNube || !cabeceraInventario || !wrapperInventario) return;
            const originales = Array.from(cabeceraInventario.querySelectorAll("th"));
            const copias = Array.from(stickyTablaClonNube.querySelectorAll("th"));
            const alto = Math.ceil(cabeceraInventario.getBoundingClientRect().height);
            stickyTablaNube.style.setProperty("--nube-table-head-height", `${alto}px`);
            stickyTablaClonNube.style.width = `${tablaInventario.getBoundingClientRect().width}px`;
            originales.forEach((celda, indice) => {
                const ancho = `${celda.getBoundingClientRect().width}px`;
                if (!copias[indice]) return;
                copias[indice].style.width = ancho;
                copias[indice].style.minWidth = ancho;
                copias[indice].style.maxWidth = ancho;
            });
            stickyTablaClonNube.style.transform = `translateX(${-wrapperInventario.scrollLeft}px)`;
        }

        function leerTopStickyNube(){
            if (!paginaNube) return 0;
            return parseFloat(getComputedStyle(paginaNube).getPropertyValue("--nube-sticky-top")) || 0;
        }

        function actualizarAlturaStickyNube(){
            if (!paginaNube || !toolbarInventario) return;
            const alto = Math.ceil(toolbarInventario.getBoundingClientRect().height);
            paginaNube.style.setProperty("--nube-toolbar-sticky-height", `${alto}px`);
        }

        function actualizarEstadoStickyNube(){
            stickyRafNube = null;
            if (!paginaNube || !toolbarInventario || !tablaInventario) return;
            actualizarAlturaStickyNube();
            const topSticky = leerTopStickyNube();
            const altoToolbar = Math.ceil(toolbarInventario.getBoundingClientRect().height);
            const topCabecera = topSticky + altoToolbar;
            const rectTabla = tablaInventario.getBoundingClientRect();
            const altoCabecera = cabeceraInventario?.getBoundingClientRect().height || 0;
            const toolbarActivo = toolbarInventario.getBoundingClientRect().top <= topSticky + 1;
            const tablaEnTop = rectTabla.top <= topCabecera + 1;
            const tablaEnRecorrido = tablaEnTop && rectTabla.bottom > topCabecera + altoCabecera;
            toolbarInventario.classList.toggle("nube-toolbar-sticky-activo", toolbarActivo);
            paginaNube.classList.toggle("nube-inventario-sticky", tablaEnRecorrido);
            if (stickyTablaNube) stickyTablaNube.hidden = !tablaEnRecorrido;
            if (tablaEnRecorrido) sincronizarStickyTablaNube();
        }

        function pedirEstadoStickyNube(){
            if (stickyRafNube !== null) return;
            stickyRafNube = window.requestAnimationFrame(actualizarEstadoStickyNube);
        }

        crearStickyTablaNube();
        actualizarAlturaStickyNube();
        sincronizarStickyTablaNube();
        pedirEstadoStickyNube();
        window.addEventListener("scroll", pedirEstadoStickyNube, { passive: true });
        window.addEventListener("resize", pedirEstadoStickyNube, { passive: true });
        wrapperInventario?.addEventListener("scroll", sincronizarStickyTablaNube, { passive: true });

        if (window.ResizeObserver && toolbarInventario){
            new ResizeObserver(pedirEstadoStickyNube).observe(toolbarInventario);
        }
        if (window.ResizeObserver && tablaInventario){
            new ResizeObserver(sincronizarStickyTablaNube).observe(tablaInventario);
        }

        // ==========================================
        // CENTRO DE ALERTAS OPERATIVAS
        // ==========================================

        const centroAlertas = document.getElementById("nubeAlertasCentro");
        const listaAlertas = document.getElementById("nubeAlertasLista");
        const filtroTipoAlertas = document.getElementById("nubeAlertasFiltroTipo");
        const filtrosPrincipalesAlertas = document.getElementById("nubeAlertasFiltrosPrincipales");
        const botonActualizarAlertas = document.getElementById("nubeAlertasActualizar");
        const estadoAlertas = { alertas: [], filtro: "todas", tipo: "todos", cargando: false };

        const gruposTipoAlerta = {
            perfiles: ["perfil_vencido", "perfil_vence_hoy", "perfil_por_vencer"],
            cuentas: ["cuenta_vencida", "cuenta_vence_hoy", "cuenta_por_vencer"],
            pagos_pin: ["pago_pin_pendiente", "pago_pin_vence_hoy", "pago_pin_proximo"],
            caidas: ["cuenta_caida"]
        };

        function crearElementoAlerta(etiqueta, clase, texto){
            const elemento = document.createElement(etiqueta);
            if (clase) elemento.className = clase;
            if (texto !== undefined) elemento.textContent = texto;
            return elemento;
        }

        function coincideFiltroAlerta(alerta){
            const coincidePrincipal = estadoAlertas.filtro === "todas" ||
                (estadoAlertas.filtro === "criticas" && alerta.prioridad === "critica") ||
                (estadoAlertas.filtro === "hoy" && alerta.dias_restantes === 0) ||
                (estadoAlertas.filtro === "proximas" && alerta.dias_restantes >= 1 && alerta.dias_restantes <= 3);
            const tipos = gruposTipoAlerta[estadoAlertas.tipo];
            return coincidePrincipal && (!tipos || tipos.includes(alerta.tipo));
        }

        function textoFechaAlerta(alerta){
            if (!alerta.fecha_objetivo) return "Sin fecha objetivo";
            if (alerta.dias_restantes === 0) return `${alerta.fecha_objetivo} · Hoy`;
            if (alerta.dias_restantes === 1) return `${alerta.fecha_objetivo} · Falta 1 día`;
            if (alerta.dias_restantes > 1) return `${alerta.fecha_objetivo} · Faltan ${alerta.dias_restantes} días`;
            if (alerta.dias_restantes === -1) return `${alerta.fecha_objetivo} · Hace 1 día`;
            if (alerta.dias_restantes < -1) return `${alerta.fecha_objetivo} · Hace ${Math.abs(alerta.dias_restantes)} días`;
            return alerta.fecha_objetivo;
        }

        function ejecutarAccionAlerta(alerta){
            let selector;
            if (alerta.accion === "gestionar_perfil" && alerta.perfil_id){
                selector = `.nube-gestionar-perfil[data-id="${CSS.escape(String(alerta.perfil_id))}"]`;
            } else if (alerta.cuenta_id){
                selector = `.nube-ver-cuenta[data-id="${CSS.escape(String(alerta.cuenta_id))}"]`;
            }
            const control = selector ? document.querySelector(selector) : null;
            if (control){
                control.click();
                return;
            }
            const fila = alerta.cuenta_id
                ? document.querySelector(`.nube-cuenta-madre .nube-ver-cuenta[data-id="${CSS.escape(String(alerta.cuenta_id))}"]`)?.closest("tr")
                : null;
            fila?.scrollIntoView({ behavior: "smooth", block: "center" });
        }

        function renderizarAlertas(){
            if (!listaAlertas) return;
            listaAlertas.replaceChildren();
            const visibles = estadoAlertas.alertas.filter(coincideFiltroAlerta);

            if (!visibles.length){
                const vacio = crearElementoAlerta("div", "nube-alertas-vacio");
                vacio.append(
                    crearElementoAlerta("strong", "", estadoAlertas.alertas.length ? "Sin coincidencias" : "Todo al día"),
                    crearElementoAlerta("span", "", estadoAlertas.alertas.length
                        ? "No hay alertas para los filtros seleccionados."
                        : "No hay alertas operativas pendientes.")
                );
                listaAlertas.append(vacio);
                return;
            }

            visibles.forEach(alerta => {
                const tarjeta = crearElementoAlerta("article", `nube-alerta-item nube-alerta-${alerta.prioridad}`);
                const cabecera = crearElementoAlerta("div", "nube-alerta-item-cabecera");
                cabecera.append(
                    crearElementoAlerta("span", "nube-alerta-prioridad", alerta.prioridad.toUpperCase()),
                    crearElementoAlerta("span", "nube-alerta-tipo", alerta.tipo.replaceAll("_", " "))
                );
                const contenido = crearElementoAlerta("div", "nube-alerta-contenido");
                contenido.append(
                    crearElementoAlerta("h3", "", alerta.titulo),
                    crearElementoAlerta("p", "", alerta.descripcion)
                );
                const meta = crearElementoAlerta("div", "nube-alerta-meta");
                [
                    alerta.plataforma,
                    alerta.cliente ? `Cliente: ${alerta.cliente}` : "",
                    alerta.perfil_id ? `Perfil #${alerta.perfil_id}` : `Cuenta #${alerta.cuenta_id}`,
                    textoFechaAlerta(alerta)
                ].filter(Boolean).forEach(texto => meta.append(crearElementoAlerta("span", "", texto)));
                contenido.append(meta);
                const accion = crearElementoAlerta("button", "nube-alerta-accion",
                    alerta.accion === "gestionar_perfil" ? "Gestionar perfil" :
                    alerta.accion === "actualizar_pago_pin" ? "Ver control PIN" : "Ver cuenta");
                accion.type = "button";
                accion.addEventListener("click", () => ejecutarAccionAlerta(alerta));
                tarjeta.append(cabecera, contenido, accion);
                listaAlertas.append(tarjeta);
            });
        }

        function cambiarFiltroAlertas(filtro){
            estadoAlertas.filtro = filtro;
            document.querySelectorAll("[data-alerta-filtro]").forEach(boton => {
                const activo = boton.dataset.alertaFiltro === filtro;
                boton.classList.toggle("activo", activo);
                boton.setAttribute("aria-pressed", String(activo));
            });
            renderizarAlertas();
        }

        function crearFiltrosPrincipales(){
            if (!filtrosPrincipalesAlertas) return;
            [
                ["todas", "Todas"], ["criticas", "Críticas"],
                ["hoy", "Hoy"], ["proximas", "Próximas"]
            ].forEach(([valor, etiqueta]) => {
                const boton = crearElementoAlerta("button", "nube-alertas-chip", etiqueta);
                boton.type = "button";
                boton.dataset.alertaFiltro = valor;
                boton.setAttribute("aria-pressed", String(valor === "todas"));
                boton.classList.toggle("activo", valor === "todas");
                boton.addEventListener("click", () => cambiarFiltroAlertas(valor));
                filtrosPrincipalesAlertas.append(boton);
            });
        }

        async function refreshAlertasNube(){
            if (!centroAlertas || estadoAlertas.cargando) return;
            estadoAlertas.cargando = true;
            centroAlertas.setAttribute("aria-busy", "true");
            botonActualizarAlertas?.setAttribute("disabled", "");
            try {
                const respuesta = await fetch("/admin/nube-cuentas/alertas", {
                    headers: { "Accept": "application/json", "X-Requested-With": "XMLHttpRequest" }
                });
                const resultado = await respuesta.json();
                if (!respuesta.ok || !resultado.ok) throw new Error(resultado.mensaje || "No se pudieron cargar las alertas.");
                estadoAlertas.alertas = Array.isArray(resultado.alertas) ? resultado.alertas : [];
                const resumen = resultado.resumen || {};
                document.getElementById("nubeAlertasTotal").textContent = resumen.total ?? 0;
                document.getElementById("nubeAlertasCriticas").textContent = resumen.criticas ?? 0;
                document.getElementById("nubeAlertasHoy").textContent = resumen.hoy ?? 0;
                document.getElementById("nubeAlertasProximas").textContent = resumen.proximas ?? 0;
                renderizarAlertas();
            } catch (error) {
                listaAlertas?.replaceChildren();
                const estadoError = crearElementoAlerta("div", "nube-alertas-error");
                estadoError.append(
                    crearElementoAlerta("strong", "", "No pudimos cargar las alertas"),
                    crearElementoAlerta("span", "", error.message)
                );
                const reintentar = crearElementoAlerta("button", "nube-alerta-accion", "Reintentar");
                reintentar.type = "button";
                reintentar.addEventListener("click", refreshAlertasNube);
                estadoError.append(reintentar);
                listaAlertas?.append(estadoError);
            } finally {
                estadoAlertas.cargando = false;
                centroAlertas.setAttribute("aria-busy", "false");
                botonActualizarAlertas?.removeAttribute("disabled");
            }
        }

        crearFiltrosPrincipales();
        document.querySelectorAll(".nube-alerta-stat").forEach(boton =>
            boton.addEventListener("click", () => cambiarFiltroAlertas(boton.dataset.alertaFiltro))
        );
        filtroTipoAlertas?.addEventListener("change", () => {
            estadoAlertas.tipo = filtroTipoAlertas.value;
            renderizarAlertas();
        });
        botonActualizarAlertas?.addEventListener("click", refreshAlertasNube);
        window.refreshAlertasNube = refreshAlertasNube;
        refreshAlertasNube();

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

        const botonPapeleraDrawer = document.getElementById("drawerPapelera");
        const drawerRenovar = document.getElementById("drawerRenovar");
        const drawerReemplazar = document.getElementById("drawerReemplazar");
        const drawerCaida = document.getElementById("drawerCaida");
        const drawerCopiar = document.getElementById("drawerCopiar");
        const drawerWhatsapp = document.getElementById("drawerWhatsapp");
        const drawerEditar = document.getElementById("drawerEditar");
        const drawerClienteCard = document.getElementById("drawerClienteCard");
        const drawerPerfilesCard = document.getElementById("drawerPerfilesCard");
        const drawerPerfilesResumen = document.getElementById("drawerPerfilesResumen");
        const drawerHistorialLista = document.getElementById("drawerHistorialLista");
        const drawerGarantiasResumen = document.getElementById("drawerGarantiasResumen");
        const drawerGarantiasLista = document.getElementById("drawerGarantiasLista");
        const drawerNotasTexto = document.getElementById("drawerNotasTexto");
        const drawerGuardarNotas = document.getElementById("drawerGuardarNotas");
        const modalRecordatorioCuenta = document.getElementById("modalRecordatorioCuenta");
        const formRecordatorioCuenta = document.getElementById("formRecordatorioCuenta");
        const recordatorioCuentaId = document.getElementById("recordatorioCuentaId");
        const recordatorioPlataforma = document.getElementById("recordatorioPlataforma");
        const recordatorioCorreo = document.getElementById("recordatorioCorreo");
        const recordatorioNotas = document.getElementById("recordatorioNotas");
        const modalWhatsappDrawer = document.getElementById("modalWhatsappDrawer");
        const whatsappDrawerClientes = document.getElementById("whatsappDrawerClientes");
        let cuentaActualDrawerId = null;
        let datosActualesDrawer = null;
        let detalleActualDrawer = null;


        let passwordActual = "";

        let passwordVisible = false;

        function normalizarTelefonoDrawer(valor){
            return normalizarTelefonoNubeUi(valor);
        }

        function notificarDrawer(mensaje, error = false){
            const aviso = document.createElement("div");
            aviso.className = `nube-drawer-toast${error ? " error" : ""}`;
            aviso.textContent = mensaje;
            document.body.append(aviso);
            setTimeout(() => aviso.remove(), 2600);
        }

        function escaparHtmlNube(valor){
            return String(valor ?? "")
                .replaceAll("&", "&amp;")
                .replaceAll("<", "&lt;")
                .replaceAll(">", "&gt;")
                .replaceAll('"', "&quot;")
                .replaceAll("'", "&#039;");
        }

        function cuentaIdDesdeFila(control, fila){
            return control?.dataset.cuentaId || control?.dataset.id || fila?.dataset.cuentaId || fila?.dataset.parentId || "";
        }

        function madreDesdeCuentaId(cuentaId){
            return cuentaId ? document.querySelector(`.nube-cuenta-madre[data-cuenta-id="${CSS.escape(String(cuentaId))}"]`) : null;
        }

        function datosMadreParaCuenta(cuentaId, control, fila){
            const madre = madreDesdeCuentaId(cuentaId);
            const controlMadre = madre?.querySelector(".nube-ver-cuenta,.nube-gestionar-cuenta");
            return controlMadre?.dataset || control?.dataset || fila?.dataset || {};
        }

        function actualizarNotasLocalesCuenta(cuentaId, notas){
            if (!cuentaId) return;
            const selectorCuenta = CSS.escape(String(cuentaId));
            document.querySelectorAll(`.nube-cuenta-madre [data-id="${selectorCuenta}"]`).forEach(nodo => {
                if (nodo.dataset) nodo.dataset.notas = notas;
            });
            const madre = madreDesdeCuentaId(cuentaId);
            madre?.querySelectorAll("[data-notas]").forEach(nodo => {
                nodo.dataset.notas = notas;
            });
            if (String(cuentaActualDrawerId || "") === String(cuentaId) && drawerNotasTexto) {
                drawerNotasTexto.value = notas;
            }
            if (detalleActualDrawer?.cuenta && String(detalleActualDrawer.cuenta.id || "") === String(cuentaId)) {
                detalleActualDrawer.cuenta.notas = notas;
            }
            if (datosActualesDrawer && String(cuentaActualDrawerId || "") === String(cuentaId)) {
                datosActualesDrawer.notas = notas;
            }
        }

        function abrirModalRecordatorioCuenta(control, fila){
            if (!modalRecordatorioCuenta || !recordatorioCuentaId || !recordatorioNotas) return;
            const cuentaId = cuentaIdDesdeFila(control, fila);
            const datos = datosMadreParaCuenta(cuentaId, control, fila);
            recordatorioCuentaId.value = cuentaId;
            recordatorioPlataforma.textContent = datos.plataforma || "Cuenta";
            recordatorioCorreo.textContent = datos.correo || datos.identificador || "Sin identificador";
            recordatorioNotas.value = datos.notas || "";
            modalRecordatorioCuenta.classList.add("abierto");
            modalRecordatorioCuenta.setAttribute("aria-hidden", "false");
            document.body.classList.add("nube-modal-abierto");
            setTimeout(() => recordatorioNotas.focus(), 60);
        }

        function cerrarModalRecordatorioCuenta(){
            modalRecordatorioCuenta?.classList.remove("abierto");
            modalRecordatorioCuenta?.setAttribute("aria-hidden", "true");
            document.body.classList.remove("nube-modal-abierto");
        }

        function abrirModalWhatsappDrawer(clientes){
            if (!modalWhatsappDrawer || !whatsappDrawerClientes) return;
            whatsappDrawerClientes.innerHTML = "";
            clientes.forEach(cliente => {
                const boton = document.createElement("button");
                boton.type = "button";
                boton.className = "nube-whatsapp-cliente";
                boton.innerHTML = `
                    <strong>${escaparHtmlNube(cliente.nombre || "Cliente")}</strong>
                    <span>${escaparHtmlNube(cliente.perfil || "Perfil")} · ${escaparHtmlNube(cliente.telefonoOriginal || cliente.telefono)}</span>
                `;
                boton.addEventListener("click", () => {
                    const numero = normalizarTelefonoDrawer(cliente.telefono);
                    if (!numero) return;
                    cerrarModalWhatsappDrawer();
                    window.open(`https://wa.me/${numero}`, "_blank", "noopener,noreferrer");
                });
                whatsappDrawerClientes.append(boton);
            });
            modalWhatsappDrawer.classList.add("abierto");
            modalWhatsappDrawer.setAttribute("aria-hidden", "false");
            document.body.classList.add("nube-modal-abierto");
            lucide?.createIcons?.();
        }

        function cerrarModalWhatsappDrawer(){
            modalWhatsappDrawer?.classList.remove("abierto");
            modalWhatsappDrawer?.setAttribute("aria-hidden", "true");
            document.body.classList.remove("nube-modal-abierto");
        }

        async function copiarTextoDrawer(texto){
            if (navigator.clipboard?.writeText) return navigator.clipboard.writeText(texto);
            const auxiliar = document.createElement("textarea");
            auxiliar.value = texto;
            auxiliar.setAttribute("readonly", "");
            auxiliar.style.position = "fixed";
            auxiliar.style.opacity = "0";
            document.body.append(auxiliar);
            auxiliar.select();
            const ok = document.execCommand("copy");
            auxiliar.remove();
            if (!ok) throw new Error("No se pudo copiar");
        }

        function abrirPrimerPerfilDrawer(accion){
            const perfiles = [...document.querySelectorAll(`.nube-perfil-row[data-parent-id="${CSS.escape(String(cuentaActualDrawerId))}"] .nube-gestionar-perfil`)];
            const elegibles = accion === "reemplazar"
                ? perfiles.filter(b => b.dataset.estado === "caida")
                : accion === "caida"
                    ? perfiles.filter(b => !["caida","papelera","reemplazada"].includes(b.dataset.estado))
                    : perfiles.filter(b => String(b.dataset.cliente || "").trim());
            if (elegibles.length === 1) {
                cerrarPanelCuenta();
                elegibles[0].click();
                return;
            }
            cerrarPanelCuenta();
            document.querySelector(`.nube-expandir-cuenta[data-cuenta-id="${CSS.escape(String(cuentaActualDrawerId))}"]`)?.click();
            notificarDrawer(elegibles.length ? "Selecciona el perfil que deseas gestionar." : "No hay perfiles elegibles para esta acción.", !elegibles.length);
        }

        async function validarPapeleraDrawer(){
            const idValidado = cuentaActualDrawerId;
            try {
                const respuesta = await fetch(`/admin/nube-cuentas/alertas/detalle?cuenta_id=${encodeURIComponent(idValidado)}`, { headers:{Accept:"application/json"} });
                const detalle = await respuesta.json();
                if (!respuesta.ok || !detalle.ok) throw new Error(detalle.mensaje || "No se pudo validar la cuenta.");
                if (idValidado !== cuentaActualDrawerId) return;
                const pendientes = Number(detalle.cuenta.servicios_vigentes_pendientes || 0);
                botonPapeleraDrawer.disabled = !detalle.cuenta.lista_para_papelera;
                botonPapeleraDrawer.title = detalle.cuenta.lista_para_papelera ? "Mover cuenta a Papelera" : (pendientes === 1 ? "Falta 1 servicio vigente por resolver." : `Faltan ${pendientes} servicios vigentes por resolver.`);
            } catch(error) {
                if (idValidado === cuentaActualDrawerId) {
                    botonPapeleraDrawer.disabled = true;
                    botonPapeleraDrawer.title = error.message;
                }
            }
        }

        function cambiarTabDrawer(tab){
            document.querySelectorAll("[data-drawer-tab]").forEach(boton => {
                const activo = boton.dataset.drawerTab === tab;
                boton.classList.toggle("activo", activo);
                boton.setAttribute("aria-selected", String(activo));
            });
            document.querySelectorAll("[data-drawer-panel]").forEach(panel => {
                const activo = panel.dataset.drawerPanel === tab;
                panel.hidden = !activo;
                panel.classList.toggle("activo", activo);
            });
        }

        function renderizarPerfilesDrawer(perfiles = []){
            if (!drawerPerfilesResumen) return;
            drawerPerfilesResumen.replaceChildren();
            const fragmento = document.createDocumentFragment();
            perfiles.forEach(perfil => {
                const item = document.createElement("div");
                const asignado = Boolean(perfil.asignado || String(perfil.nombre_cliente || "").trim());
                item.className = `nube-drawer-perfil-item${asignado ? "" : " disponible"}`;
                const restante = asignado
                    ? `${Number(perfil.dias_restantes || 0)} días restantes`
                    : "Disponible";
                item.innerHTML = `
                    <strong>${escaparHtmlNube(perfil.nombre_perfil || `Perfil ${perfil.orden || ""}`)}</strong>
                    <span>${escaparHtmlNube(asignado ? (perfil.nombre_cliente || "Cliente") : "Disponible")}</span>
                    <small>${escaparHtmlNube(restante)}</small>
                `;
                fragmento.append(item);
            });
            if (!perfiles.length){
                const vacio = document.createElement("div");
                vacio.className = "nube-drawer-vacio";
                vacio.textContent = "Sin perfiles registrados.";
                fragmento.append(vacio);
            }
            drawerPerfilesResumen.append(fragmento);
        }

        function eventoDrawer(titulo, descripcion, fecha, icono = "circle"){
            const item = document.createElement("article");
            item.className = "nube-drawer-evento";
            item.innerHTML = `
                <i data-lucide="${icono}"></i>
                <div>
                    <strong>${escaparHtmlNube(titulo)}</strong>
                    <span>${escaparHtmlNube(descripcion || "")}</span>
                    <small>${escaparHtmlNube(fecha || "")}</small>
                </div>
            `;
            return item;
        }

        function renderizarHistorialDrawer(detalle){
            if (!drawerHistorialLista) return;
            drawerHistorialLista.replaceChildren();
            const fragmento = document.createDocumentFragment();
            const historial = detalle?.historial || {};
            (historial.movimientos || []).forEach(mov => {
                fragmento.append(eventoDrawer(
                    String(mov.tipo || "Movimiento").replaceAll("_", " "),
                    [mov.descripcion, mov.cliente_nombre ? `Cliente: ${mov.cliente_nombre}` : ""].filter(Boolean).join(" · "),
                    mov.fecha,
                    mov.tipo === "creacion" ? "cloud" : "activity"
                ));
            });
            (historial.pagos_pin || []).forEach(pago => {
                fragmento.append(eventoDrawer(
                    "Pago PIN",
                    `${pago.plan || "Plan"} · $${pago.valor_pin || 0} · ${pago.dias_estimados || 0} días`,
                    pago.fecha_aplicacion || pago.fecha_estimada_fin,
                    "credit-card"
                ));
            });
            (historial.reemplazos || []).forEach(rep => {
                fragmento.append(eventoDrawer(
                    "Reemplazo",
                    `${rep.perfil_anterior || "Perfil"} → ${rep.plataforma_nueva || ""} ${rep.perfil_nuevo || ""}`.trim(),
                    rep.fecha,
                    "repeat-2"
                ));
            });
            (historial.snapshots || []).forEach(snapshot => {
                const datos = snapshot.datos || {};
                fragmento.append(eventoDrawer(
                    snapshot.tipo_origen === "cuenta_completa" ? "Snapshot cuenta completa" : "Snapshot asignación",
                    [datos.nombre_perfil, datos.nombre_cliente || datos.cliente, datos.fecha_vencimiento].filter(Boolean).join(" · "),
                    snapshot.fecha,
                    "archive"
                ));
            });
            if (!fragmento.childNodes.length){
                fragmento.append(eventoDrawer("Sin historial registrado", "No hay movimientos reales para mostrar.", "", "info"));
            }
            drawerHistorialLista.append(fragmento);
            lucide?.createIcons?.();
        }

        function renderizarGarantiasDrawer(detalle){
            if (!drawerGarantiasResumen || !drawerGarantiasLista) return;
            const garantias = detalle?.garantias || {};
            drawerGarantiasResumen.innerHTML = `
                <span>${Number(garantias.total_perfiles || 0)} perfiles</span>
                <span>${Number(garantias.perfiles_afectados || 0)} afectados</span>
                <span>${Number(garantias.reemplazados || 0)} reemplazos</span>
                <span>${Number(garantias.pendientes || 0)} pendientes</span>
            `;
            drawerGarantiasLista.replaceChildren();
            const fragmento = document.createDocumentFragment();
            (garantias.items || []).forEach(item => {
                fragmento.append(eventoDrawer(
                    item.perfil || "Perfil",
                    [
                        item.cliente ? `Cliente: ${item.cliente}` : "",
                        item.estado ? `Estado: ${item.estado}` : "",
                        item.destino ? `Destino: ${item.destino}` : "",
                        item.motivo ? `Motivo: ${item.motivo}` : ""
                    ].filter(Boolean).join(" · "),
                    item.fecha,
                    item.tipo === "reemplazo" ? "repeat-2" : "shield-check"
                ));
            });
            if (!fragmento.childNodes.length){
                fragmento.append(eventoDrawer("Sin garantías registradas", "No hay reemplazos ni garantías reales para esta cuenta.", "", "shield"));
            }
            drawerGarantiasLista.append(fragmento);
            lucide?.createIcons?.();
        }

        async function cargarDetalleDrawer(cuentaId){
            if (!cuentaId) return;
            try {
                const respuesta = await fetch(`/admin/nube-cuentas/${encodeURIComponent(cuentaId)}/drawer`, {
                    headers: {Accept: "application/json"}
                });
                const detalle = await respuesta.json();
                if (!respuesta.ok || !detalle.ok) throw new Error(detalle.mensaje || "No se pudo cargar el detalle.");
                detalleActualDrawer = detalle;
                if (drawerNotasTexto) drawerNotasTexto.value = detalle.cuenta?.notas || "";
                const esMadre = (detalle.cuenta?.modalidad || "") === "perfiles";
                if (drawerClienteCard) drawerClienteCard.hidden = esMadre;
                if (drawerPerfilesCard) drawerPerfilesCard.hidden = !esMadre;
                renderizarPerfilesDrawer(detalle.perfiles || []);
                renderizarHistorialDrawer(detalle);
                renderizarGarantiasDrawer(detalle);
                actualizarWhatsappDrawer();
            } catch(error) {
                notificarDrawer(error.message, true);
            }
        }

        function clientesWhatsappDrawer(){
            const telefonoCuenta = normalizarTelefonoDrawer(datosActualesDrawer?.telefono);
            if ((detalleActualDrawer?.cuenta?.modalidad || datosActualesDrawer?.modalidad) !== "perfiles"){
                return telefonoCuenta ? [{
                    nombre: datosActualesDrawer?.cliente || "Cliente",
                    perfil: "Cuenta completa",
                    telefono: telefonoCuenta,
                    telefonoOriginal: datosActualesDrawer?.telefono || telefonoCuenta
                }] : [];
            }
            return (detalleActualDrawer?.perfiles || [])
                .map(perfil => ({
                    etiqueta: `${perfil.nombre_perfil || "Perfil"} · ${perfil.nombre_cliente || "Cliente"} · ${perfil.telefono || ""}`,
                    nombre: perfil.nombre_cliente || "Cliente",
                    perfil: perfil.nombre_perfil || `Perfil ${perfil.orden || ""}`.trim(),
                    telefono: normalizarTelefonoDrawer(perfil.telefono),
                    telefonoOriginal: perfil.telefono || ""
                }))
                .filter(item => item.telefono);
        }

        function actualizarWhatsappDrawer(){
            if (!drawerWhatsapp) return;
            const clientes = clientesWhatsappDrawer();
            drawerWhatsapp.disabled = clientes.length === 0;
            drawerWhatsapp.title = clientes.length
                ? "Abrir WhatsApp"
                : "Sin teléfono registrado";
        }

        function abrirSelectorWhatsappDrawer(origen){
            const clientes = clientesWhatsappDrawer();
            if (!clientes.length) return;
            if (clientes.length === 1){
                window.open(`https://wa.me/${clientes[0].telefono}`, "_blank", "noopener,noreferrer");
                return;
            }
            abrirModalWhatsappDrawer(clientes);
        }

        function abrirDrawer(
            boton
        ){

            if (!drawer) return;

            const datos =
                boton.dataset;

            cuentaActualDrawerId = datos.cuentaId || datos.id || null;
            datosActualesDrawer = { ...datos };
            detalleActualDrawer = null;
            cambiarTabDrawer("informacion");


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

            if (drawerNotasTexto){
                drawerNotasTexto.value = datos.notas || "";
            }


            const estado =
                datos.estado ||
                "disponible";

            const esPerfiles = datos.modalidad === "perfiles" || datos.modalidad === "perfil";
            const esMadrePerfiles = datos.modalidad === "perfiles";
            if (drawerClienteCard) drawerClienteCard.hidden = esMadrePerfiles;
            if (drawerPerfilesCard) drawerPerfilesCard.hidden = !esMadrePerfiles;
            if (drawerPerfilesResumen) drawerPerfilesResumen.innerHTML = `<div class="nube-drawer-vacio">Cargando perfiles...</div>`;
            [drawerRenovar, drawerReemplazar, drawerCaida].forEach(control => {
                if (control) {
                    control.disabled = !esPerfiles;
                    control.hidden = !esPerfiles;
                    control.title = esPerfiles ? "Seleccionar el perfil sobre el que se realizará la acción" : "Esta acción solo existe para perfiles individuales";
                }
            });
            if (drawerRenovar) drawerRenovar.textContent = esMadrePerfiles ? "Gestionar perfiles" : "Renovar / Extender";
            if (drawerEditar) { drawerEditar.hidden = true; drawerEditar.disabled = true; }
            if (drawerWhatsapp) { drawerWhatsapp.disabled = true; drawerWhatsapp.title = "Validando teléfonos..."; }
            if (botonPapeleraDrawer) { botonPapeleraDrawer.hidden = estado !== "caida"; botonPapeleraDrawer.disabled = true; botonPapeleraDrawer.title = estado === "caida" ? "Validando elegibilidad…" : "Solo una cuenta caída puede archivarse"; }


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

            if (estado === "caida") validarPapeleraDrawer();
            cargarDetalleDrawer(cuentaActualDrawerId);

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

        document.querySelector(".nube-drawer-tabs")?.addEventListener("click", evento => {
            const boton = evento.target.closest("[data-drawer-tab]");
            if (!boton) return;
            cambiarTabDrawer(boton.dataset.drawerTab);
        });


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

        drawerRenovar?.addEventListener("click", () => abrirPrimerPerfilDrawer("renovar"));
        drawerReemplazar?.addEventListener("click", () => abrirPrimerPerfilDrawer("reemplazar"));
        drawerCaida?.addEventListener("click", () => abrirPrimerPerfilDrawer("caida"));
        drawerCopiar?.addEventListener("click", async () => {
            if (!datosActualesDrawer) return;
            const lineas = [
                ["Plataforma", datosActualesDrawer.plataforma],
                ["Correo", datosActualesDrawer.correo],
                ["Contraseña", passwordActual],
                ["PIN", datosActualesDrawer.pin]
            ].filter(([, valor]) => String(valor || "").trim()).map(([clave, valor]) => `${clave}: ${valor}`);
            try {
                await copiarTextoDrawer(lineas.join("\n"));
                notificarDrawer("Datos copiados correctamente.");
            } catch(error) {
                notificarDrawer(error.message, true);
            }
        });
        drawerWhatsapp?.addEventListener("click", evento => {
            abrirSelectorWhatsappDrawer(evento.currentTarget);
        });
        document.getElementById("cerrarRecordatorioCuenta")?.addEventListener("click", cerrarModalRecordatorioCuenta);
        document.getElementById("cancelarRecordatorioCuenta")?.addEventListener("click", cerrarModalRecordatorioCuenta);
        document.getElementById("cerrarRecordatorioBackdrop")?.addEventListener("click", cerrarModalRecordatorioCuenta);
        document.getElementById("cerrarWhatsappDrawer")?.addEventListener("click", cerrarModalWhatsappDrawer);
        document.getElementById("cerrarWhatsappDrawerBackdrop")?.addEventListener("click", cerrarModalWhatsappDrawer);
        formRecordatorioCuenta?.addEventListener("submit", async evento => {
            evento.preventDefault();
            const cuentaId = recordatorioCuentaId?.value || "";
            if (!cuentaId) return;
            const submit = formRecordatorioCuenta.querySelector("button[type='submit']");
            submit.disabled = true;
            try {
                const notas = recordatorioNotas?.value || "";
                const respuesta = await fetch(`/admin/nube-cuentas/${encodeURIComponent(cuentaId)}/notas`, {
                    method: "POST",
                    headers: {"Content-Type": "application/json", Accept: "application/json"},
                    body: JSON.stringify({notas})
                });
                const resultado = await respuesta.json();
                if (!respuesta.ok || !resultado.ok) throw new Error(resultado.mensaje || "No se pudo guardar el recordatorio.");
                actualizarNotasLocalesCuenta(cuentaId, notas);
                cerrarModalRecordatorioCuenta();
                notificarDrawer("Recordatorio guardado");
            } catch(error) {
                notificarDrawer(error.message, true);
            } finally {
                submit.disabled = false;
            }
        });
        drawerGuardarNotas?.addEventListener("click", async () => {
            if (!cuentaActualDrawerId) return;
            drawerGuardarNotas.disabled = true;
            try {
                const respuesta = await fetch(`/admin/nube-cuentas/${encodeURIComponent(cuentaActualDrawerId)}/notas`, {
                    method: "POST",
                    headers: {"Content-Type": "application/json", Accept: "application/json"},
                    body: JSON.stringify({notas: drawerNotasTexto?.value || ""})
                });
                const resultado = await respuesta.json();
                if (!respuesta.ok || !resultado.ok) throw new Error(resultado.mensaje || "No se pudo guardar la nota.");
                if (datosActualesDrawer) datosActualesDrawer.notas = drawerNotasTexto?.value || "";
                actualizarNotasLocalesCuenta(cuentaActualDrawerId, drawerNotasTexto?.value || "");
                notificarDrawer("Nota guardada.");
            } catch(error) {
                notificarDrawer(error.message, true);
            } finally {
                drawerGuardarNotas.disabled = false;
            }
        });
        botonPapeleraDrawer?.addEventListener("click", async () => {
            if (!cuentaActualDrawerId || botonPapeleraDrawer.disabled) return;
            if (!confirm("Mover cuenta a Papelera\n\nLa cuenta saldrá del inventario operativo y del Centro de Alertas. Los datos operativos restantes serán limpiados, pero todo el historial se conservará.")) return;
            botonPapeleraDrawer.disabled = true;
            try {
                const respuesta = await fetch(`/admin/nube-cuentas/${cuentaActualDrawerId}/papelera`, {
                    method:"POST",
                    headers:{"Content-Type":"application/json",Accept:"application/json"},
                    body:JSON.stringify({motivo:"Archivada desde Nube"})
                });
                const resultado = await respuesta.json();
                if (!respuesta.ok || !resultado.ok) throw new Error(resultado.mensaje || "No se pudo mover la cuenta a Papelera.");
                cerrarPanelCuenta();
                window.location.reload();
            } catch(error) {
                notificarDrawer(error.message,true);
                await validarPapeleraDrawer();
            }
        });

        // ==========================================
        // CUENTA COMPLETA DISPONIBLE - ASIGNAR
        // ==========================================

        const modalAsignarCuenta = document.getElementById("modalAsignarCuentaCompleta");
        const formAsignarCuenta = document.getElementById("formAsignarCuentaCompleta");
        const asignarCuentaId = document.getElementById("asignarCuentaId");
        const asignarCuentaCliente = document.getElementById("asignarCuentaCliente");
        const asignarCuentaTelefono = document.getElementById("asignarCuentaTelefono");
        const asignarCuentaEntrega = document.getElementById("asignarCuentaEntrega");
        const asignarCuentaDias = document.getElementById("asignarCuentaDias");
        const asignarCuentaVencimiento = document.getElementById("asignarCuentaVencimiento");
        const asignarCuentaNotas = document.getElementById("asignarCuentaNotas");
        const tituloAsignarCuenta = document.getElementById("tituloAsignarCuentaCompleta");
        const mensajeAsignarCuenta = document.getElementById("mensajeAsignarCuenta");
        const mensajeAsignarCuentaTexto = document.getElementById("mensajeAsignarCuentaTexto");

        function calcularVencimientoUi(fecha, dias){
            if (!fecha || Number(dias || 0) <= 0) return "";
            const base = new Date(`${fecha}T12:00:00`);
            if (Number.isNaN(base.getTime())) return "";
            base.setDate(base.getDate() + Number(dias));
            return base.toISOString().slice(0, 10);
        }

        function abrirModalAsignarCuenta(control){
            if (!modalAsignarCuenta) return;
            const datos = control.dataset;
            asignarCuentaId.value = datos.id || "";
            asignarCuentaCliente.value = datos.cliente || "";
            asignarCuentaTelefono.value = datos.telefono || "";
            asignarCuentaEntrega.value = datos.entrega || new Date().toISOString().slice(0, 10);
            asignarCuentaDias.value = datos.dias && Number(datos.dias) > 0 ? datos.dias : "30";
            asignarCuentaNotas.value = datos.notas || "";
            tituloAsignarCuenta.textContent = `Asignar ${datos.plataforma || "cuenta"}`;
            asignarCuentaVencimiento.value = calcularVencimientoUi(asignarCuentaEntrega.value, asignarCuentaDias.value);
            if (mensajeAsignarCuenta) mensajeAsignarCuenta.hidden = true;
            modalAsignarCuenta.classList.add("abierto");
            modalAsignarCuenta.setAttribute("aria-hidden", "false");
            document.body.classList.add("nube-modal-abierto");
        }

        function cerrarModalAsignarCuenta(){
            modalAsignarCuenta?.classList.remove("abierto");
            modalAsignarCuenta?.setAttribute("aria-hidden", "true");
            document.body.classList.remove("nube-modal-abierto");
        }

        [asignarCuentaEntrega, asignarCuentaDias].forEach(campo =>
            campo?.addEventListener("input", () => {
                asignarCuentaVencimiento.value = calcularVencimientoUi(asignarCuentaEntrega.value, asignarCuentaDias.value);
            })
        );
        document.getElementById("cerrarAsignarCuentaCompleta")?.addEventListener("click", cerrarModalAsignarCuenta);
        document.getElementById("cancelarAsignarCuentaCompleta")?.addEventListener("click", cerrarModalAsignarCuenta);
        document.getElementById("cerrarAsignarCuentaBackdrop")?.addEventListener("click", cerrarModalAsignarCuenta);

        formAsignarCuenta?.addEventListener("submit", async evento => {
            evento.preventDefault();
            const submit = formAsignarCuenta.querySelector("button[type='submit']");
            submit.disabled = true;
            try {
                const respuesta = await fetch("/admin/nube-cuentas/asignar-cuenta", {
                    method: "POST",
                    headers: {"Content-Type": "application/json", "Accept": "application/json"},
                    body: JSON.stringify({
                        cuenta_id: asignarCuentaId.value,
                        nombre_cliente: asignarCuentaCliente.value,
                        telefono: asignarCuentaTelefono.value,
                        fecha_entrega: asignarCuentaEntrega.value,
                        dias_cuenta: asignarCuentaDias.value,
                        notas: asignarCuentaNotas.value
                    })
                });
                const resultado = await respuesta.json();
                if (!respuesta.ok || !resultado.ok) throw new Error(resultado.mensaje || "No se pudo asignar la cuenta.");
                mensajeAsignarCuentaTexto.textContent = "Cuenta asignada correctamente.";
                mensajeAsignarCuenta.classList.remove("error");
                mensajeAsignarCuenta.hidden = false;
                await refreshCuentaNube(asignarCuentaId.value);
                window.setTimeout(cerrarModalAsignarCuenta, 700);
            } catch(error) {
                mensajeAsignarCuentaTexto.textContent = error.message;
                mensajeAsignarCuenta.classList.add("error");
                mensajeAsignarCuenta.hidden = false;
            } finally {
                submit.disabled = false;
            }
        });

        // ==========================================
        // MÁS ACCIONES - MENÚ CONTEXTUAL
        // ==========================================

        let menuAccionesNube = null;
        function cerrarMenuAccionesNube(){
            menuAccionesNube?.remove();
            menuAccionesNube = null;
        }

        function crearBotonMenuAccion(etiqueta, icono, accion){
            const boton = document.createElement("button");
            boton.type = "button";
            boton.dataset.accion = accion;
            boton.innerHTML = `<i data-lucide="${icono}"></i><span>${etiqueta}</span>`;
            return boton;
        }

        function abrirSelectorWhatsappFila(origen, fila){
            const perfiles = indiceInventario.get(fila)?.hijos || [];
            const clientes = perfiles.map(perfil => {
                const control = perfil.querySelector(".nube-gestionar-perfil,.nube-ver-perfil");
                const telefono = normalizarTelefonoNubeUi(control?.dataset.telefono || perfil.dataset.telefono);
                return {
                    telefono,
                    etiqueta: `${control?.dataset.nombre || perfil.querySelector("strong")?.textContent?.trim() || "Perfil"} · ${control?.dataset.cliente || "Cliente"} · ${control?.dataset.telefono || ""}`
                };
            }).filter(item => item.telefono);

            if (!clientes.length) return;
            if (clientes.length === 1){
                window.open(`https://wa.me/${clientes[0].telefono}`, "_blank", "noopener,noreferrer");
                return;
            }

            cerrarMenuAccionesNube();
            menuAccionesNube = document.createElement("div");
            menuAccionesNube.className = "nube-menu-acciones nube-menu-whatsapp";
            const titulo = document.createElement("strong");
            titulo.textContent = "Selecciona el cliente";
            menuAccionesNube.append(titulo);
            clientes.forEach(cliente => {
                const boton = document.createElement("button");
                boton.type = "button";
                boton.innerHTML = `<i data-lucide="message-circle"></i><span>${escaparHtmlNube(cliente.etiqueta)}</span>`;
                boton.addEventListener("click", () => {
                    cerrarMenuAccionesNube();
                    window.open(`https://wa.me/${cliente.telefono}`, "_blank", "noopener,noreferrer");
                });
                menuAccionesNube.append(boton);
            });
            document.body.append(menuAccionesNube);
            lucide?.createIcons?.();
            const rect = origen.getBoundingClientRect();
            menuAccionesNube.style.left = `${Math.min(window.innerWidth - 260, Math.max(12, rect.right - 260))}px`;
            menuAccionesNube.style.top = `${Math.min(window.innerHeight - menuAccionesNube.offsetHeight - 12, rect.bottom + 8)}px`;
        }

        function abrirMenuAccionesNube(origen, fila){
            cerrarMenuAccionesNube();
            const control = fila.querySelector(".nube-ver-cuenta,.nube-ver-perfil,.nube-gestionar-cuenta,.nube-gestionar-perfil");
            if (!control) return;
            const estado = control.dataset.estado || fila.dataset.estado || "";
            const esPerfil = fila.matches(".nube-perfil-row");
            const esCuentaCompleta = !esPerfil && control.dataset.modalidad !== "perfiles";
            const acciones = [
                crearBotonMenuAccion("Ver", "eye", "ver"),
                crearBotonMenuAccion("Copiar datos", "copy", "copiar")
            ];
            if (esPerfil) acciones.splice(1, 0, crearBotonMenuAccion("Gestionar", "user-round-cog", "gestionar"));
            if (esCuentaCompleta && estado === "disponible") acciones.splice(1, 0, crearBotonMenuAccion("Asignar", "user-plus", "asignar"));
            if (esPerfil && !["disponible", "papelera", "reemplazada"].includes(estado)) acciones.push(crearBotonMenuAccion("Renovar", "refresh-cw", "gestionar"));
            if (esPerfil && !["caida", "papelera", "reemplazada"].includes(estado)) acciones.push(crearBotonMenuAccion("Marcar caída", "triangle-alert", "gestionar"));
            if (!esPerfil && estado === "caida") acciones.push(crearBotonMenuAccion("Mover a Papelera", "trash-2", "papelera"));

            menuAccionesNube = document.createElement("div");
            menuAccionesNube.className = "nube-menu-acciones";
            acciones.forEach(boton => menuAccionesNube.append(boton));
            document.body.append(menuAccionesNube);
            lucide?.createIcons?.();
            const rect = origen.getBoundingClientRect();
            const ancho = 190;
            menuAccionesNube.style.left = `${Math.min(window.innerWidth - ancho - 12, Math.max(12, rect.right - ancho))}px`;
            menuAccionesNube.style.top = `${Math.min(window.innerHeight - menuAccionesNube.offsetHeight - 12, rect.bottom + 8)}px`;
            menuAccionesNube.addEventListener("click", async evento => {
                const boton = evento.target.closest("[data-accion]");
                if (!boton) return;
                const accion = boton.dataset.accion;
                cerrarMenuAccionesNube();
                if (accion === "ver") control.click();
                if (accion === "gestionar") fila.querySelector(".nube-gestionar-perfil")?.click();
                if (accion === "asignar") abrirModalAsignarCuenta(control);
                if (accion === "copiar") {
                    const lineas = [["Plataforma", control.dataset.plataforma], ["Correo", control.dataset.correo], ["Contraseña", control.dataset.contrasena], ["PIN", control.dataset.pin], ["Cliente", control.dataset.cliente], ["Teléfono", control.dataset.telefono]].filter(([,v]) => String(v || "").trim()).map(([k,v]) => `${k}: ${v}`);
                    try { await copiarTextoDrawer(lineas.join("\n")); notificarDrawer("Datos copiados correctamente."); } catch(error) { notificarDrawer(error.message, true); }
                }
                if (accion === "papelera") { control.click(); setTimeout(() => botonPapeleraDrawer?.click(), 120); }
            });
        }

        document.addEventListener("click", evento => {
            if (menuAccionesNube && !evento.target.closest(".nube-menu-acciones,.nube-mas-acciones")) cerrarMenuAccionesNube();
        });

        // ==========================================
        // CARGA RÁPIDA
        // ==========================================

        const modalCargaRapida = document.getElementById("modalCargaRapida");
        const formCargaRapida = document.getElementById("formCargaRapida");
        const plataformaCargaRapida = document.getElementById("cargaRapidaPlataforma");
        const modalidadCargaRapida = document.getElementById("cargaRapidaModalidad");
        const duracionCargaRapida = document.getElementById("cargaRapidaDuracion");
        const refrescarDuracionCargaRapida = () => aplicarPoliticaDuracionInventario(
            plataformaCargaRapida?.value, modalidadCargaRapida?.value, duracionCargaRapida
        );
        plataformaCargaRapida?.addEventListener("change", refrescarDuracionCargaRapida);
        modalidadCargaRapida?.addEventListener("change", refrescarDuracionCargaRapida);
        refrescarDuracionCargaRapida();
        const previaCargaRapida = document.getElementById("cargaRapidaPrevia");
        const confirmarCargaRapida = document.getElementById("confirmarCargaRapida");
        const credencialesCargaRapida = document.getElementById("cargaRapidaCredenciales");
        let credencialesValidasCargaRapida = [];
        let filasCargaRapida = [];
        let filtroCargaRapida = "todas";
        let filaEditandoCargaRapida = null;

        function abrirModalCargaRapida(){
            modalCargaRapida?.classList.add("abierto");
            modalCargaRapida?.setAttribute("aria-hidden", "false");
            document.body.classList.add("nube-modal-abierto");
            analizarCargaRapida();
        }

        function cerrarModalCargaRapida(){
            modalCargaRapida?.classList.remove("abierto");
            modalCargaRapida?.setAttribute("aria-hidden", "true");
            document.body.classList.remove("nube-modal-abierto");
        }

        function correosExistentesNube(){
            return new Set(madresInventario.map(fila => String(fila.querySelector(".nube-correo")?.textContent || "").trim().toLowerCase()).filter(Boolean));
        }

        function clasificarLineaCargaRapida(texto, indice, existentes, vistos){
            const valor = String(texto || "").trim();
            if (!valor) return null;
            const partes = valor.split(":");
            const correo = (partes[0] || "").trim().toLowerCase();
            const contrasena = (partes[1] || "").trim();
            const pin = partes.slice(2).join(":").trim();
            const base = {indice, texto: valor, correo, contrasena, pin, razon: "", estado: "valida"};
            if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(correo)){
                return {...base, estado: "invalida", razon: "correo inválido"};
            }
            if (!contrasena){
                return {...base, estado: "invalida", razon: "falta contraseña"};
            }
            if (existentes.has(correo)){
                return {...base, estado: "duplicada", razon: "Correo ya existe en inventario."};
            }
            if (vistos.has(correo)){
                return {...base, estado: "duplicada", razon: "Duplicada dentro del lote."};
            }
            vistos.add(correo);
            return base;
        }

        function reconstruirTextareaCargaRapida(){
            if (!credencialesCargaRapida) return;
            credencialesCargaRapida.value = filasCargaRapida.map(fila => fila.texto).join("\n");
        }

        function renderizarCargaRapida(){
            if (!previaCargaRapida) return;
            const conteos = {
                todas: filasCargaRapida.length,
                valida: filasCargaRapida.filter(f => f.estado === "valida").length,
                duplicada: filasCargaRapida.filter(f => f.estado === "duplicada").length,
                invalida: filasCargaRapida.filter(f => f.estado === "invalida").length
            };
            credencialesValidasCargaRapida = filasCargaRapida
                .filter(fila => fila.estado === "valida")
                .map(({correo, contrasena, pin}) => ({correo, contrasena, pin}));
            confirmarCargaRapida.disabled = credencialesValidasCargaRapida.length === 0;
            confirmarCargaRapida.innerHTML = `<i data-lucide="cloud-upload"></i>Agregar ${credencialesValidasCargaRapida.length} cuenta${credencialesValidasCargaRapida.length === 1 ? "" : "s"}`;

            const visibles = filasCargaRapida.filter(fila =>
                filtroCargaRapida === "todas" || fila.estado === filtroCargaRapida
            );
            const fragmento = document.createDocumentFragment();
            const contadores = document.createElement("div");
            contadores.className = "nube-carga-contadores";
            [
                ["todas", conteos.todas, "Todas"],
                ["valida", conteos.valida, "Válidas"],
                ["duplicada", conteos.duplicada, "Duplicadas"],
                ["invalida", conteos.invalida, "Inválidas"]
            ].forEach(([estado, total, etiqueta]) => {
                const boton = document.createElement("button");
                boton.type = "button";
                boton.dataset.cargaFiltro = estado;
                boton.className = filtroCargaRapida === estado ? "activo" : "";
                boton.textContent = `${total} ${etiqueta}`;
                contadores.append(boton);
            });
            fragmento.append(contadores);

            const lista = document.createElement("div");
            lista.className = "nube-carga-lista";
            visibles.slice(0, 500).forEach(fila => {
                const item = document.createElement("button");
                item.type = "button";
                item.className = `nube-carga-linea ${fila.estado}`;
                item.dataset.lineaIndice = String(fila.indice);
                item.innerHTML = `
                    <strong>${fila.estado === "valida" ? "✓" : fila.estado === "duplicada" ? "⚠" : "×"} ${escaparHtmlNube(fila.correo || `Línea ${fila.indice + 1}`)}</strong>
                    <span>${escaparHtmlNube(fila.estado)}${fila.razon ? ` · ${escaparHtmlNube(fila.razon)}` : ""}</span>
                `;
                lista.append(item);
            });
            fragmento.append(lista);

            const editor = document.createElement("div");
            editor.className = "nube-carga-editor";
            const filaEditando = filasCargaRapida.find(f => f.indice === filaEditandoCargaRapida);
            if (filaEditando){
                editor.innerHTML = `
                    <label>
                        <span>Editando línea ${filaEditando.indice + 1}</span>
                        <input type="text" id="cargaRapidaEditorLinea" value="${escaparHtmlNube(filaEditando.texto)}">
                    </label>
                    <small>${escaparHtmlNube(filaEditando.razon || "Corrige y se revalidará automáticamente.")}</small>
                `;
            }
            fragmento.append(editor);
            previaCargaRapida.replaceChildren(fragmento);
            lucide?.createIcons?.();
        }

        function analizarCargaRapida(){
            const existentes = correosExistentesNube();
            const vistos = new Set();
            filasCargaRapida = String(credencialesCargaRapida?.value || "")
                .split(/\r?\n/)
                .map((linea, indice) => clasificarLineaCargaRapida(linea, indice, existentes, vistos))
                .filter(Boolean);
            renderizarCargaRapida();
        }

        document.getElementById("abrirCargaRapida")?.addEventListener("click", abrirModalCargaRapida);
        document.getElementById("cerrarCargaRapida")?.addEventListener("click", cerrarModalCargaRapida);
        document.getElementById("cancelarCargaRapida")?.addEventListener("click", cerrarModalCargaRapida);
        document.getElementById("cerrarCargaRapidaBackdrop")?.addEventListener("click", cerrarModalCargaRapida);
        formCargaRapida?.addEventListener("input", analizarCargaRapida);
        previaCargaRapida?.addEventListener("click", evento => {
            const filtro = evento.target.closest("[data-carga-filtro]");
            if (filtro){
                filtroCargaRapida = filtro.dataset.cargaFiltro;
                renderizarCargaRapida();
                return;
            }
            const linea = evento.target.closest("[data-linea-indice]");
            if (linea){
                filaEditandoCargaRapida = Number(linea.dataset.lineaIndice);
                renderizarCargaRapida();
            }
        });
        previaCargaRapida?.addEventListener("input", evento => {
            if (evento.target.id !== "cargaRapidaEditorLinea") return;
            evento.stopPropagation();
            const fila = filasCargaRapida.find(item => item.indice === filaEditandoCargaRapida);
            if (!fila) return;
            fila.texto = evento.target.value;
            reconstruirTextareaCargaRapida();
            analizarCargaRapida();
            filaEditandoCargaRapida = Math.min(filaEditandoCargaRapida, filasCargaRapida.at(-1)?.indice ?? 0);
            renderizarCargaRapida();
            const editor = document.getElementById("cargaRapidaEditorLinea");
            editor?.focus();
        });
        formCargaRapida?.addEventListener("submit", async evento => {
            evento.preventDefault();
            analizarCargaRapida();
            if (!credencialesValidasCargaRapida.length) return;
            confirmarCargaRapida.disabled = true;
            try {
                const respuesta = await fetch("/admin/nube-cuentas/carga-rapida", {
                    method: "POST",
                    headers: {"Content-Type": "application/json", "Accept": "application/json"},
                    body: JSON.stringify({
                        plataforma: document.getElementById("cargaRapidaPlataforma").value,
                        modalidad: document.getElementById("cargaRapidaModalidad").value,
                        duracion_unidad_dias: duracionCargaRapida.required ? duracionCargaRapida.value : null,
                        tipo_pago: document.getElementById("cargaRapidaTipoPago").value,
                        cantidad_perfiles: document.getElementById("cargaRapidaCantidadPerfiles").value,
                        plan_pago: document.getElementById("cargaRapidaPlan").value,
                        valor_pin: document.getElementById("cargaRapidaValorPin").value,
                        precio_plan_referencia: document.getElementById("cargaRapidaPrecioPlan").value,
                        fecha_aplicacion_pin: document.getElementById("cargaRapidaFechaPin").value,
                        credenciales: credencialesValidasCargaRapida
                    })
                });
                const resultado = await respuesta.json();
                if (!respuesta.ok || !resultado.ok) throw new Error(resultado.mensaje || "No se pudo completar la carga rápida.");
                window.location.reload();
            } catch(error) {
                previaCargaRapida.innerHTML = `<strong>No se pudo cargar</strong><span>${error.message}</span>`;
                confirmarCargaRapida.disabled = false;
            }
        });



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

                                perfil.hidden = abierto || (
                                    Boolean(inventario.estado) &&
                                    !coincideEstadoInventario(perfil, inventario.estado)
                                );

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
const grupoNoRenovoPerfil = document.getElementById("grupoNoRenovoPerfil");
const abrirNoRenovoPerfil = document.getElementById("abrirNoRenovoPerfil");
const panelNoRenovoPerfil = document.getElementById("panelNoRenovoPerfil");
const contenidoNoRenovoPerfil = document.getElementById("contenidoNoRenovoPerfil");
const exitoNoRenovoPerfil = document.getElementById("exitoNoRenovoPerfil");
const cancelarNoRenovoPerfil = document.getElementById("cancelarNoRenovoPerfil");
const confirmarNoRenovoPerfil = document.getElementById("confirmarNoRenovoPerfil");

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

document.addEventListener("DOMContentLoaded", async () => {
    const atajo = document.getElementById("nubeAlertasAtajo");
    if (atajo) {
        try {
            const respuesta = await fetch("/admin/nube-cuentas/alertas", { headers: { Accept: "application/json" } });
            const datos = await respuesta.json();
            if (!respuesta.ok || !datos.ok) throw new Error();
            const resumen = datos.resumen || {};
            document.getElementById("nubeAlertasAtajoTitulo").textContent = resumen.total ? `${resumen.total} alerta${resumen.total === 1 ? "" : "s"} requieren atención` : "Todo está al día";
            document.getElementById("nubeAlertasAtajoResumen").textContent = `${resumen.criticas || 0} críticas · ${resumen.hoy || 0} hoy · ${resumen.proximas || 0} próximas`;
        } catch (_) {
            document.getElementById("nubeAlertasAtajoTitulo").textContent = "Centro de alertas";
            document.getElementById("nubeAlertasAtajoResumen").textContent = "No se pudo actualizar el conteo · Abrir centro";
        }
    }
    const params = new URLSearchParams(window.location.search);
    const perfil = params.get("perfil");
    const cuenta = params.get("cuenta");
    const escape = window.CSS?.escape || (valor => String(valor).replace(/[^a-zA-Z0-9_-]/g, ""));
    const selector = perfil ? `.nube-gestionar-perfil[data-id="${escape(perfil)}"]` : cuenta ? `.nube-ver-cuenta[data-id="${escape(cuenta)}"]` : "";
    if (selector) window.setTimeout(() => document.querySelector(selector)?.click(), 120);
});
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
            const estadoNoRenovo = String(datos.estado || "").trim().toLowerCase();
            const estadoPermiteNoRenovo = ![
                "disponible", "reemplazada", "papelera", "garantia", "caida"
            ].includes(estadoNoRenovo);
            if (grupoNoRenovoPerfil){
                grupoNoRenovoPerfil.hidden = !(perfilRealmenteAsignado && estadoPermiteNoRenovo);
            }
            if (panelNoRenovoPerfil) panelNoRenovoPerfil.hidden = true;
            if (contenidoNoRenovoPerfil) contenidoNoRenovoPerfil.hidden = false;
            if (exitoNoRenovoPerfil) exitoNoRenovoPerfil.hidden = true;
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

            refreshAlertasNube();

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

                const perfilId = perfilGestionId?.value || "";
                cerrarModalPerfil();
                refreshPerfilNube(perfilId).catch(reportarFalloRefrescoNube);
            }
        );


        formGestionPerfil?.addEventListener(
            "submit",
            event => {
                event.preventDefault();

                if (operacionCompletada){
                    const perfilId = perfilGestionId?.value || "";
                    cerrarModalPerfil();
                    refreshPerfilNube(perfilId).catch(reportarFalloRefrescoNube);
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
                    await refreshPerfilNube(perfilId);
                    confirmarLiberacionPerfil.disabled = false;
                }
            } catch (error) {
                mostrarMensajePerfil(error.message, "error");
                confirmarLiberacionPerfil.disabled = false;
            }
        });

        abrirNoRenovoPerfil?.addEventListener("click", () => {
            panelNoRenovoPerfil.hidden = false;
            contenidoNoRenovoPerfil.hidden = false;
            exitoNoRenovoPerfil.hidden = true;
        });

        cancelarNoRenovoPerfil?.addEventListener("click", () => {
            panelNoRenovoPerfil.hidden = true;
        });

        confirmarNoRenovoPerfil?.addEventListener("click", async () => {
            const perfilId = perfilGestionId?.value || "";
            if (!perfilId || operacionCompletada) return;
            confirmarNoRenovoPerfil.disabled = true;
            try {
                const respuesta = await fetch("/admin/nube-cuentas/perfil/no-renovo", {
                    method: "POST",
                    headers: {"Content-Type": "application/json"},
                    body: JSON.stringify({
                        perfil_id: perfilId,
                        operacion_uuid: crearOperacionUuid().replace("liberar-", "no-renovo-")
                    })
                });
                const resultado = await respuesta.json();
                if (!respuesta.ok || !resultado.ok){
                    throw new Error(resultado.mensaje || "No se pudo registrar la no renovación.");
                }
                contenidoNoRenovoPerfil.hidden = true;
                exitoNoRenovoPerfil.hidden = false;
                if (grupoLiberacionPerfil) grupoLiberacionPerfil.hidden = true;
                if (grupoRenovacionPerfil) grupoRenovacionPerfil.hidden = true;
                if (abrirCaidaPerfil) abrirCaidaPerfil.hidden = true;
                if (grupoReemplazoPerfil) grupoReemplazoPerfil.hidden = true;
                perfilGestionCliente.value = "";
                perfilGestionTelefono.value = "";
                perfilGestionEntrega.value = "";
                perfilGestionDias.value = "";
                perfilGestionVencimiento.value = "Sin vencimiento";
                subtituloGestionPerfil.textContent = "Perfil · disponible";
                mostrarMensajePerfil(resultado.mensaje);
                establecerOperacionCompletada(true);
                window.lucide?.createIcons();
                await refreshPerfilNube(perfilId);
            } catch (error) {
                mostrarMensajePerfil(error.message, "error");
                confirmarNoRenovoPerfil.disabled = false;
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

establecerOperacionCompletada(true);


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

                cerrarMenuAccionesNube();

                if (
                    modalAsignarCuenta?.classList.contains(
                        "abierto"
                    )
                ){

                    cerrarModalAsignarCuenta();

                }

                if (
                    modalCargaRapida?.classList.contains(
                        "abierto"
                    )
                ){

                    cerrarModalCargaRapida();

                }

                if (
                    modalRecordatorioCuenta?.classList.contains(
                        "abierto"
                    )
                ){

                    cerrarModalRecordatorioCuenta();

                }

                if (
                    modalWhatsappDrawer?.classList.contains(
                        "abierto"
                    )
                ){

                    cerrarModalWhatsappDrawer();

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

