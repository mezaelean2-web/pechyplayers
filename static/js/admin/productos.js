function previewImagen(input, previewId) {
    const preview = document.getElementById(previewId);

    if (!preview) {
        return;
    }

    const archivo = input.files && input.files[0];

    if (!archivo) {
        preview.removeAttribute("src");
        preview.style.display = "none";
        return;
    }

    if (!archivo.type.startsWith("image/")) {
        input.value = "";
        preview.removeAttribute("src");
        preview.style.display = "none";
        window.alert("Selecciona un archivo de imagen válido.");
        return;
    }

    const lector = new FileReader();

    lector.addEventListener("load", function () {
        preview.src = lector.result;
        preview.style.display = "block";
    });

    lector.addEventListener("error", function () {
        preview.removeAttribute("src");
        preview.style.display = "none";
        window.alert("No se pudo mostrar la vista previa de la imagen.");
    });

    lector.readAsDataURL(archivo);
}

document.addEventListener("DOMContentLoaded", function () {
    const buscador = document.getElementById("buscadorAdmin");
    const grid = document.getElementById("productosAdminGrid");

    if (!buscador || !grid) {
        return;
    }

    const productos = Array.from(
        grid.querySelectorAll(".productos-admin-card")
    );
    const resultado = document.getElementById("resultadoBusquedaAdmin");
    const filtroCategoria = document.getElementById("filtroCategoriaAdmin");
    const filtroEstado = document.getElementById("filtroEstadoAdmin");
    const filtroCaracteristica = document.getElementById("filtroCaracteristicaAdmin");
    const contador = document.getElementById("contadorProductosAdmin");
    const estadoOrden = document.getElementById("estadoOrdenProductosAdmin");
    const estadoVacio = document.getElementById("productosAdminEmpty");
    const abrirAgregar = document.getElementById("abrirAgregarProducto");
    const createBackdrop = document.getElementById("productoCreateBackdrop");
    const createModal = createBackdrop?.querySelector(".producto-create-modal");
    const createForm = document.getElementById("productoCreateForm");
    const createError = document.getElementById("productoCreateError");
    const createImage = document.getElementById("nuevaImagen");
    const createPreview = document.getElementById("previewAgregar");
    let productoArrastrado = null;
    let ordenAntesDeArrastrar = [];
    let huboArrastre = false;
    let ultimoDisparadorModal = null;
    let solicitudProducto = null;
    let productoSolicitado = null;
    const modalBackdrop = document.getElementById("productoControlBackdrop");
    const modal = modalBackdrop?.querySelector(".producto-control-modal");
    const modalContent = document.getElementById("productoControlContent");

    function normalizarPrecio(precio) {
        const digitos = String(precio || "").replace(/\D/g, "");
        return digitos ? Number(digitos) : null;
    }

    function etiquetaPrecio(precio) {
        const texto = String(precio || "").trim();
        return texto.startsWith("$") ? texto : `$${texto}`;
    }

    productos.forEach(function (producto) {
        const salida = producto.querySelector(".productos-admin-card__price");
        let precios = [];

        try {
            precios = JSON.parse(producto.dataset.precios || "[]");
        } catch (error) {
            precios = [];
        }

        if (!salida || precios.length === 0) return;

        const preciosOrdenables = precios
            .map(function (texto) {
                return { texto: String(texto), valor: normalizarPrecio(texto) };
            })
            .filter(function (precio) {
                return precio.valor !== null;
            })
            .sort(function (a, b) {
                return a.valor - b.valor;
            });

        if (precios.length === 1) {
            salida.textContent = `Desde ${etiquetaPrecio(precios[0])}`;
        } else if (preciosOrdenables.length === precios.length) {
            salida.textContent = `${etiquetaPrecio(preciosOrdenables[0].texto)} – ${etiquetaPrecio(preciosOrdenables.at(-1).texto)}`;
        } else {
            salida.textContent = `${etiquetaPrecio(precios[0])} – ${etiquetaPrecio(precios.at(-1))}`;
        }
    });

    function hayFiltrosActivos() {
        return Boolean(
            buscador.value.trim() ||
            filtroCategoria?.value ||
            filtroEstado?.value ||
            filtroCaracteristica?.value
        );
    }

    function actualizarEstadoOrden() {
        const bloqueado = hayFiltrosActivos();
        grid.classList.toggle("productos-admin-grid--locked", bloqueado);
        productos.forEach(function (producto) {
            producto.draggable = !bloqueado;
        });
        if (estadoOrden) {
            estadoOrden.textContent = bloqueado
                ? "Limpia búsqueda y filtros para ordenar"
                : "Arrastra las tarjetas para ordenar";
        }
    }

    function aplicarFiltros() {
        const consulta = buscador.value.trim().toLocaleLowerCase("es");
        const categoria = filtroCategoria?.value || "";
        const estado = filtroEstado?.value || "";
        const caracteristica = filtroCaracteristica?.value || "";
        let visibles = 0;

        productos.forEach(function (producto) {
            const coincideNombre = (producto.dataset.nombre || "").includes(consulta);
            const coincideCategoria = !categoria || producto.dataset.categoria === categoria;
            const coincideEstado = !estado || producto.dataset.estado === estado;
            const coincideCaracteristica =
                !caracteristica ||
                (caracteristica === "oferta" && producto.dataset.oferta === "1") ||
                (caracteristica === "destacado" && producto.dataset.destacado === "1") ||
                (caracteristica === "oculto" && producto.dataset.visible !== "1");
            const coincide = coincideNombre && coincideCategoria && coincideEstado && coincideCaracteristica;

            producto.hidden = !coincide;
            if (coincide) visibles += 1;
        });

        if (contador) {
            contador.textContent = `${visibles} ${visibles === 1 ? "producto" : "productos"}`;
        }
        if (estadoVacio) estadoVacio.hidden = visibles !== 0;
        if (resultado) {
            resultado.hidden = visibles !== 0;
            resultado.textContent = visibles === 0
                ? "No se encontraron productos con los criterios seleccionados."
                : "";
        }
        actualizarEstadoOrden();
    }

    [buscador, filtroCategoria, filtroEstado, filtroCaracteristica]
        .filter(Boolean)
        .forEach(function (control) {
            control.addEventListener(control === buscador ? "input" : "change", aplicarFiltros);
        });

    function cerrarCreateModal() {
        if (!createBackdrop || createBackdrop.hidden) return;
        createBackdrop.hidden = true;
        document.body.classList.remove("producto-create-modal-open");
        abrirAgregar?.focus({ preventScroll: true });
    }

    function abrirCreateModal() {
        if (!createBackdrop || !createModal) return;
        createBackdrop.hidden = false;
        document.body.classList.add("producto-create-modal-open");
        createModal.scrollTop = 0;
        createModal.focus({ preventScroll: true });
        document.getElementById("nuevoNombre")?.focus({ preventScroll: true });
    }

    abrirAgregar?.addEventListener("click", abrirCreateModal);
    createBackdrop?.addEventListener("click", function (evento) {
        if (evento.target === createBackdrop || evento.target.closest("[data-close-create-modal]")) cerrarCreateModal();
    });

    createImage?.addEventListener("change", function () {
        const archivo = createImage.files && createImage.files[0];
        if (!archivo || !archivo.type.startsWith("image/")) {
            createPreview?.removeAttribute("src");
            if (createPreview) createPreview.hidden = true;
            return;
        }
        const lector = new FileReader();
        lector.addEventListener("load", function () {
            if (!createPreview) return;
            createPreview.src = lector.result;
            createPreview.hidden = false;
        });
        lector.readAsDataURL(archivo);
    });

    createForm?.querySelectorAll("[data-create-plan]").forEach(function (tarjeta) {
        const activo = tarjeta.querySelector('input[type="checkbox"]');
        const campos = Array.from(tarjeta.querySelectorAll('input[type="text"]'));
        const precio = tarjeta.querySelector('input[name^="precio_"]:not([name^="precio_reseller_"])');
        if (!activo || !precio) return;
        activo.addEventListener("change", function () {
            tarjeta.classList.toggle("is-active", activo.checked);
            campos.forEach(function (campo) { campo.disabled = !activo.checked; });
            precio.required = activo.checked;
            if (createError) createError.hidden = true;
        });
    });

    createForm?.addEventListener("submit", function (evento) {
        const activos = Array.from(createForm.querySelectorAll("[data-create-plan]")).filter(function (tarjeta) {
            return tarjeta.querySelector('input[type="checkbox"]')?.checked;
        });
        const invalidos = activos.filter(function (tarjeta) {
            return !/\d/.test(tarjeta.querySelector('input[name^="precio_"]:not([name^="precio_reseller_"])')?.value || "");
        });
        if (!activos.length || invalidos.length) {
            evento.preventDefault();
            if (createError) {
                createError.textContent = !activos.length
                    ? "Activa al menos un plan para crear el producto."
                    : "Escribe un precio válido para cada plan activo.";
                createError.hidden = false;
            }
            invalidos[0]?.querySelector('input[type="text"]')?.focus();
            return;
        }
        const boton = createForm.querySelector('button[type="submit"]');
        if (boton) {
            boton.disabled = true;
            boton.textContent = "Creando producto…";
        }
    });

    function cerrarModal() {
        if (!modalBackdrop || modalBackdrop.hidden) return;
        solicitudProducto?.abort();
        solicitudProducto = null;
        productoSolicitado = null;
        modalBackdrop.hidden = true;
        document.body.classList.remove("producto-modal-open");
        if (modalContent) modalContent.replaceChildren();
        ultimoDisparadorModal?.focus({ preventScroll: true });
    }

    function mostrarCarga() {
        if (!modalContent) return;
        modal?.removeAttribute("aria-labelledby");
        modalContent.innerHTML = '<div class="producto-control-status" role="status"><span class="producto-control-spinner" aria-hidden="true"></span><strong>Cargando producto…</strong></div>';
    }

    function mostrarError(tarjeta) {
        if (!modalContent) return;
        modalContent.innerHTML = '<div class="producto-control-status producto-control-status--error" role="alert"><strong>No pudimos cargar este producto.</strong><button type="button" data-retry-producto>Reintentar</button></div>';
        modalContent.querySelector("[data-retry-producto]")?.addEventListener("click", function () {
            cargarProducto(tarjeta);
        }, { once: true });
    }

    function inicializarControlDinamico() {
        if (!modalContent) return;
        const titulo = modalContent.querySelector("h2");
        if (titulo?.id) modal?.setAttribute("aria-labelledby", titulo.id);

        modalContent.querySelectorAll("form").forEach(function (formulario) {
            if (formulario.matches("[data-plan-discount-form]")) return;
            formulario.addEventListener("submit", function () {
                const boton = formulario.querySelector('button[type="submit"]');
                if (!boton) return;
                boton.disabled = true;
                boton.dataset.textoOriginal = boton.textContent;
                boton.textContent = "Guardando…";
            });
        });

        modalContent.querySelectorAll("[data-state-control]").forEach(function (tarjeta) {
            const switchEstado = tarjeta.querySelector('input[type="checkbox"]');
            const estado = tarjeta.querySelector(".producto-state-current span");
            const pendiente = tarjeta.querySelector(".producto-state-pending");
            if (!switchEstado || !estado || !pendiente) return;
            const valorInicial = switchEstado.checked;
            switchEstado.addEventListener("change", function () {
                const hayCambio = switchEstado.checked !== valorInicial;
                estado.textContent = switchEstado.checked ? tarjeta.dataset.onLabel : tarjeta.dataset.offLabel;
                tarjeta.classList.toggle("has-pending-change", hayCambio);
                pendiente.hidden = !hayCambio;
            });
        });

        modalContent.querySelectorAll("[data-offer-control]").forEach(function (oferta) {
            const switchOferta = oferta.querySelector('input[name="oferta_activa"]');
            const plan = oferta.closest("[data-plan-card]");
            const badge = plan?.querySelector(".producto-offer-badge");
            if (!switchOferta || !plan || !badge) return;
            switchOferta.addEventListener("change", function () {
                plan.classList.toggle("has-offer", switchOferta.checked);
                badge.hidden = !switchOferta.checked;
            });
        });

        modalContent.querySelectorAll("[data-reseller-price-form]").forEach(function (formulario) {
            formulario.addEventListener("submit", async function (evento) {
                evento.preventDefault();
                const boton = formulario.querySelector('button[type="submit"]');
                const campo = formulario.querySelector('[name="precio_reseller_general"]');
                const feedback = formulario.querySelector("[data-reseller-feedback]");
                const tarjeta = formulario.closest("[data-reseller-price-card]");
                const precio = String(campo?.value || "").replace(/\D/g, "");
                if (!precio) {
                    if (feedback) feedback.textContent = "Escribe un importe valido.";
                    if (boton) { boton.disabled = false; boton.textContent = boton.dataset.textoOriginal || "Guardar precio reseller"; }
                    return;
                }
                try {
                    const respuesta = await fetch(`/admin/revendedores/precios/generales/${encodeURIComponent(formulario.dataset.planId)}`, {
                        method: "PUT",
                        headers: {"Content-Type": "application/json", "X-CSRF-Token": formulario.querySelector('[name="csrf_token"]')?.value || ""},
                        body: JSON.stringify({ precio: precio })
                    });
                    const datos = await respuesta.json().catch(function () { return {}; });
                    if (!respuesta.ok) throw new Error(datos.mensaje || "No fue posible guardar el precio.");
                    tarjeta?.classList.add("is-saved");
                    const estado = tarjeta?.querySelector("[data-reseller-status]");
                    if (estado) estado.textContent = "Precio reseller configurado";
                    if (feedback) feedback.textContent = "Precio reseller guardado.";
                } catch (error) {
                    if (feedback) feedback.textContent = error.message;
                } finally {
                    if (boton) { boton.disabled = false; boton.textContent = boton.dataset.textoOriginal || "Guardar precio reseller"; }
                }
            });
        });
    }

    async function cargarProducto(tarjeta) {
        if (!modalContent || !tarjeta?.dataset.productoId) return;
        solicitudProducto?.abort();
        const controlador = new AbortController();
        solicitudProducto = controlador;
        productoSolicitado = tarjeta.dataset.productoId;
        mostrarCarga();
        try {
            const respuesta = await fetch(`/admin/productos/${encodeURIComponent(productoSolicitado)}/control`, {
                headers: { "X-Requested-With": "XMLHttpRequest" },
                signal: controlador.signal
            });
            if (!respuesta.ok) throw new Error(`HTTP ${respuesta.status}`);
            const html = await respuesta.text();
            if (controlador.signal.aborted || productoSolicitado !== tarjeta.dataset.productoId) return;
            modalContent.innerHTML = html;
            inicializarControlDinamico();
        } catch (error) {
            if (error.name !== "AbortError" && productoSolicitado === tarjeta.dataset.productoId) mostrarError(tarjeta);
        } finally {
            if (solicitudProducto === controlador) solicitudProducto = null;
        }
    }

    function abrirModal(tarjeta) {
        if (!modalBackdrop || !modal || !modalContent || huboArrastre) return;
        ultimoDisparadorModal = tarjeta;
        modalBackdrop.hidden = false;
        document.body.classList.add("producto-modal-open");
        modal.scrollTop = 0;
        modal.focus({ preventScroll: true });
        cargarProducto(tarjeta);
    }

    grid.addEventListener("click", function (evento) {
        const tarjeta = evento.target.closest(".productos-admin-card");
        if (tarjeta && !huboArrastre) abrirModal(tarjeta);
    });

    grid.addEventListener("keydown", function (evento) {
        if ((evento.key === "Enter" || evento.key === " ") && evento.target.matches(".productos-admin-card")) {
            evento.preventDefault();
            abrirModal(evento.target);
        }
    });

    modalBackdrop?.addEventListener("click", function (evento) {
        if (evento.target === modalBackdrop || evento.target.closest("[data-close-producto-modal]")) cerrarModal();
    });

    document.addEventListener("keydown", function (evento) {
        if (evento.key === "Escape" && !createBackdrop?.hidden) {
            cerrarCreateModal();
            return;
        }
        if (evento.key === "Escape" && !modalBackdrop?.hidden) cerrarModal();
        const modalActivo = !createBackdrop?.hidden ? createModal : (!modalBackdrop?.hidden ? modal : null);
        if (evento.key !== "Tab" || !modalActivo) return;
        const enfocables = Array.from(modalActivo.querySelectorAll('button:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex="0"]')).filter(function (item) {
            return !item.closest("[hidden]");
        });
        if (!enfocables.length) return;
        const primero = enfocables[0];
        const ultimo = enfocables.at(-1);
        if (evento.shiftKey && document.activeElement === primero) { evento.preventDefault(); ultimo.focus(); }
        else if (!evento.shiftKey && document.activeElement === ultimo) { evento.preventDefault(); primero.focus(); }
    });

    function obtenerTarjetaDestino(x, y) {
        return document.elementsFromPoint(x, y).find(function (elemento) {
            return elemento.classList?.contains("productos-admin-card") && elemento !== productoArrastrado;
        });
    }

    grid.addEventListener("dragstart", function (evento) {
        if (hayFiltrosActivos()) {
            evento.preventDefault();
            return;
        }
        productoArrastrado = evento.target.closest(".productos-admin-card");
        if (!productoArrastrado || evento.target.closest("button")) {
            evento.preventDefault();
            productoArrastrado = null;
            return;
        }
        ordenAntesDeArrastrar = Array.from(grid.querySelectorAll(".productos-admin-card")).map(function (producto) {
            return producto.dataset.producto;
        });
        huboArrastre = true;
        productoArrastrado.classList.add("productos-admin-card--dragging");
        evento.dataTransfer.effectAllowed = "move";
        evento.dataTransfer.setData("text/plain", productoArrastrado.dataset.producto);
    });

    grid.addEventListener("dragover", function (evento) {
        if (!productoArrastrado) return;
        evento.preventDefault();
        const destino = obtenerTarjetaDestino(evento.clientX, evento.clientY);
        productos.forEach(function (producto) {
            producto.classList.remove("productos-admin-card--drop-before", "productos-admin-card--drop-after");
        });
        if (!destino) return;
        const rect = destino.getBoundingClientRect();
        const despues = evento.clientY > rect.top + rect.height / 2;
        destino.classList.add(despues ? "productos-admin-card--drop-after" : "productos-admin-card--drop-before");
        grid.insertBefore(productoArrastrado, despues ? destino.nextSibling : destino);
    });

    grid.addEventListener("dragend", async function () {
        if (!productoArrastrado) return;
        productoArrastrado.classList.remove("productos-admin-card--dragging");
        productos.forEach(function (producto) {
            producto.classList.remove("productos-admin-card--drop-before", "productos-admin-card--drop-after");
        });
        const ordenNuevo = Array.from(grid.querySelectorAll(".productos-admin-card")).map(function (producto) {
            return producto.dataset.producto;
        });
        productoArrastrado = null;
        window.setTimeout(function () { huboArrastre = false; }, 0);

        if (ordenNuevo.join("\u0000") === ordenAntesDeArrastrar.join("\u0000")) return;
        grid.classList.add("productos-admin-grid--saving");
        if (estadoOrden) estadoOrden.textContent = "Guardando orden…";
        try {
            const respuesta = await fetch("/guardar-orden", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ orden: ordenNuevo })
            });
            if (!respuesta.ok) throw new Error("No fue posible guardar el orden");
            if (estadoOrden) estadoOrden.textContent = "Orden guardado";
        } catch (error) {
            const porNombre = new Map(productos.map(function (producto) {
                return [producto.dataset.producto, producto];
            }));
            ordenAntesDeArrastrar.forEach(function (nombre) {
                const producto = porNombre.get(nombre);
                if (producto) grid.appendChild(producto);
            });
            if (estadoOrden) estadoOrden.textContent = "No se pudo guardar; se restauró el orden anterior";
        } finally {
            grid.classList.remove("productos-admin-grid--saving");
            window.setTimeout(actualizarEstadoOrden, 2200);
        }
    });

    aplicarFiltros();
});

document.addEventListener("submit", async function (evento) {
    const planForm = evento.target.closest("[data-plan-discount-form]");
    if (!planForm) return;
    evento.preventDefault();
    const button = planForm.querySelector('button[type="submit"]');
    const feedback = planForm.querySelector("[data-plan-discount-feedback]");
    if (planForm.dataset.saving === "1") return;
    planForm.dataset.saving = "1";
    const originalText = button.textContent;
    button.disabled = true;
    button.textContent = "Guardando…";
    try {
        const response = await fetch(`/admin/productos/${encodeURIComponent(planForm.dataset.planId)}/descuento-carrito`, {
            method: "PATCH",
            headers: {"Content-Type": "application/json", "X-CSRF-Token": planForm.querySelector('[name="csrf_token"]').value},
            body: JSON.stringify({eligible: planForm.querySelector('[name="eligible"]').checked, discount_bps: Math.round(Number(planForm.querySelector('[name="percent"]').value) * 100)})
        });
        const data = await response.json().catch(function () { return {}; });
        if (!response.ok) throw new Error(data.mensaje || "No fue posible guardar.");
        feedback.textContent = "Participación guardada.";
    } catch (error) { feedback.textContent = error.message; }
    finally {
        planForm.dataset.saving = "0";
        button.disabled = false;
        button.textContent = originalText;
    }
});

document.addEventListener("change", function (evento) {
    const eligible = evento.target.closest('[data-plan-discount-form] [name="eligible"]');
    if (!eligible) return;
    eligible.form.querySelector('[name="percent"]').disabled = !eligible.checked;
});

document.addEventListener("DOMContentLoaded", function () {
    const panel = document.querySelector("[data-cart-discount-admin]");
    if (!panel) return;
    const feedback = panel.querySelector("[data-discount-feedback]");
    panel.querySelectorAll("[data-discount-rule]").forEach(function (form) {
        const active = form.querySelector('[name="active"]');
        active.addEventListener("change", function () { active.nextElementSibling.textContent = active.checked ? "Sí" : "No"; });
        form.addEventListener("submit", async function (event) {
            event.preventDefault();
            const minimum = Number(form.querySelector('[name="minimum"]').value);
            const percent = Number(form.querySelector('[name="percent"]').value);
            if (!Number.isInteger(minimum) || !Number.isFinite(percent) || Math.round(percent * 100) !== percent * 100) {
                feedback.textContent = "Usa un mínimo entero y un porcentaje con máximo dos decimales."; return;
            }
            const id = form.dataset.ruleId;
            try {
                const response = await fetch(id ? `/admin/productos/descuentos-carrito/${id}` : "/admin/productos/descuentos-carrito", {
                    method: id ? "PUT" : "POST",
                    headers: {"Content-Type": "application/json", "X-CSRF-Token": panel.dataset.csrfToken},
                    body: JSON.stringify({minimum_eligible_services: minimum, discount_bps: Math.round(percent * 100), active: active.checked})
                });
                const data = await response.json().catch(function () { return {}; });
                if (!response.ok) throw new Error(data.mensaje || "No fue posible guardar la regla.");
                window.location.reload();
            } catch (error) { feedback.textContent = error.message; }
        });
        form.querySelector("[data-delete-rule]")?.addEventListener("click", async function () {
            if (!window.confirm("¿Eliminar este nivel de descuento?")) return;
            const response = await fetch(`/admin/productos/descuentos-carrito/${form.dataset.ruleId}`, {method: "DELETE", headers: {"X-CSRF-Token": panel.dataset.csrfToken}});
            const data = await response.json().catch(function () { return {}; });
            if (!response.ok) { feedback.textContent = data.mensaje || "No fue posible eliminar."; return; }
            form.remove(); feedback.textContent = "Nivel eliminado.";
        });
    });
});
