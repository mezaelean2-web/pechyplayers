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
    const legacy = document.getElementById("productosAdminLegacy");
    let productoArrastrado = null;
    let ordenAntesDeArrastrar = [];
    let huboArrastre = false;
    let ultimoDisparadorModal = null;
    const modalBackdrop = document.getElementById("productoControlBackdrop");
    const modal = modalBackdrop?.querySelector(".producto-control-modal");
    const controlesModal = Array.from(modalBackdrop?.querySelectorAll("[data-modal-producto]") || []);

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
        const precio = tarjeta.querySelector('input[type="text"]');
        if (!activo || !precio) return;
        activo.addEventListener("change", function () {
            tarjeta.classList.toggle("is-active", activo.checked);
            precio.disabled = !activo.checked;
            precio.required = activo.checked;
            if (createError) createError.hidden = true;
        });
    });

    createForm?.addEventListener("submit", function (evento) {
        const activos = Array.from(createForm.querySelectorAll("[data-create-plan]")).filter(function (tarjeta) {
            return tarjeta.querySelector('input[type="checkbox"]')?.checked;
        });
        const invalidos = activos.filter(function (tarjeta) {
            return !/\d/.test(tarjeta.querySelector('input[type="text"]')?.value || "");
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
        modalBackdrop.hidden = true;
        document.body.classList.remove("producto-modal-open");
        controlesModal.forEach(function (control) { control.hidden = true; });
        ultimoDisparadorModal?.focus({ preventScroll: true });
    }

    function abrirModal(tarjeta) {
        if (!modalBackdrop || !modal || huboArrastre) return;
        const control = controlesModal.find(function (item) {
            return item.dataset.modalProducto === tarjeta.dataset.producto;
        });
        if (!control) return;
        controlesModal.forEach(function (item) { item.hidden = item !== control; });
        const titulo = control.querySelector("h2");
        modal.setAttribute("aria-labelledby", titulo.id);
        ultimoDisparadorModal = tarjeta;
        modalBackdrop.hidden = false;
        document.body.classList.add("producto-modal-open");
        modal.scrollTop = 0;
        modal.focus({ preventScroll: true });
    }

    grid.addEventListener("click", function (evento) {
        const boton = evento.target.closest("[data-legacy-producto]");
        if (!boton) {
            const tarjeta = evento.target.closest(".productos-admin-card");
            if (tarjeta && !huboArrastre) abrirModal(tarjeta);
            return;
        }
        if (!legacy) return;
        evento.stopPropagation();

        const nombre = boton.dataset.legacyProducto.toLocaleLowerCase("es");
        const editor = Array.from(legacy.querySelectorAll(".admin-producto")).find(function (item) {
            return (item.dataset.nombre || "").toLocaleLowerCase("es") === nombre;
        });
        if (!editor) return;

        legacy.hidden = false;
        legacy.querySelectorAll(".admin-producto").forEach(function (item) {
            item.hidden = item !== editor;
            item.open = item === editor;
        });
        editor.scrollIntoView({ behavior: "smooth", block: "start" });
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

    modalBackdrop?.querySelectorAll("form").forEach(function (formulario) {
        formulario.addEventListener("submit", function () {
            const boton = formulario.querySelector('button[type="submit"]');
            if (!boton) return;
            boton.disabled = true;
            boton.dataset.textoOriginal = boton.textContent;
            boton.textContent = "Guardando…";
        });
    });

    modalBackdrop?.querySelectorAll("[data-state-control]").forEach(function (tarjeta) {
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

    modalBackdrop?.querySelectorAll("[data-offer-control]").forEach(function (oferta) {
        const switchOferta = oferta.querySelector('input[name="oferta_activa"]');
        const plan = oferta.closest("[data-plan-card]");
        const badge = plan?.querySelector(".producto-offer-badge");
        if (!switchOferta || !plan || !badge) return;

        switchOferta.addEventListener("change", function () {
            plan.classList.toggle("has-offer", switchOferta.checked);
            badge.hidden = !switchOferta.checked;
        });
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
