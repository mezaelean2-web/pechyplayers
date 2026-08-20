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
    const crearProducto = document.getElementById("agregar");
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

    abrirAgregar?.addEventListener("click", function () {
        crearProducto.open = true;
        crearProducto.scrollIntoView({ behavior: "smooth", block: "start" });
        document.getElementById("nuevoNombre")?.focus({ preventScroll: true });
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
        if (evento.key === "Escape" && !modalBackdrop?.hidden) cerrarModal();
        if (evento.key !== "Tab" || modalBackdrop?.hidden || !modal) return;
        const enfocables = Array.from(modal.querySelectorAll('button:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex="0"]')).filter(function (item) {
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
