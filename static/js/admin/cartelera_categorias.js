document.addEventListener("DOMContentLoaded", () => {
    const lista = document.getElementById("listaCategoriasCartelera");
    if (!lista) return;

    const modal = document.getElementById("modalCategoriaCartelera");
    const formulario = document.getElementById("formCategoriaCartelera");
    const nombreInput = document.getElementById("nombreCategoriaCartelera");
    const tituloModal = document.getElementById("tituloModalCategoria");
    const botonGuardar = document.getElementById("guardarCategoriaCartelera");
    const mensaje = document.getElementById("mensajeCategoriaCartelera");
    let categoriaEditando = null;
    let arrastrada = null;
    let ordenAnterior = [];
    let punteroActivo = null;

    const filas = () => [...lista.querySelectorAll(".categoria-cartelera-fila")];
    const ids = () => filas().map((fila) => Number(fila.dataset.categoriaId));

    const avisar = (texto, error = false) => {
        mensaje.textContent = texto;
        mensaje.classList.toggle("is-error", error);
        mensaje.classList.add("is-visible");
        window.clearTimeout(avisar.timer);
        avisar.timer = window.setTimeout(() => mensaje.classList.remove("is-visible"), 3600);
    };

    const solicitar = async (url, opciones = {}) => {
        const respuesta = await fetch(url, {
            ...opciones,
            headers: { "Content-Type": "application/json", ...(opciones.headers || {}) }
        });
        const resultado = await respuesta.json().catch(() => ({}));
        if (!respuesta.ok || !resultado.ok) {
            throw new Error(resultado.mensaje || "No se pudo completar la operación.");
        }
        return resultado;
    };

    const abrirModal = (fila = null) => {
        categoriaEditando = fila;
        tituloModal.textContent = fila ? "Editar categoría" : "Nueva categoría";
        nombreInput.value = fila?.dataset.categoriaNombre || "";
        modal.classList.add("is-open");
        modal.setAttribute("aria-hidden", "false");
        document.body.style.overflow = "hidden";
        window.setTimeout(() => nombreInput.focus(), 50);
    };

    const cerrarModal = () => {
        modal.classList.remove("is-open");
        modal.setAttribute("aria-hidden", "true");
        document.body.style.overflow = "";
        categoriaEditando = null;
        formulario.reset();
    };

    document.getElementById("nuevaCategoriaCartelera")?.addEventListener("click", () => abrirModal());
    modal.querySelectorAll("[data-cerrar-modal]").forEach((boton) => boton.addEventListener("click", cerrarModal));

    formulario.addEventListener("submit", async (evento) => {
        evento.preventDefault();
        botonGuardar.disabled = true;
        botonGuardar.textContent = "Guardando...";
        const id = categoriaEditando?.dataset.categoriaId;
        try {
            await solicitar(
                id ? `/admin/cartelera/categorias/${id}` : "/admin/cartelera/categorias",
                { method: id ? "PATCH" : "POST", body: JSON.stringify({ nombre: nombreInput.value }) }
            );
            cerrarModal();
            avisar(id ? "Categoría actualizada." : "Categoría creada.");
            window.setTimeout(() => window.location.reload(), 350);
        } catch (error) {
            avisar(error.message, true);
        } finally {
            botonGuardar.disabled = false;
            botonGuardar.textContent = "Guardar";
        }
    });

    lista.addEventListener("click", async (evento) => {
        const fila = evento.target.closest(".categoria-cartelera-fila");
        if (!fila) return;
        if (evento.target.closest(".categoria-editar")) {
            abrirModal(fila);
            return;
        }
        const eliminar = evento.target.closest(".categoria-eliminar");
        if (!eliminar) return;
        const cantidad = Number(eliminar.dataset.cantidad);
        if (cantidad > 0) {
            avisar(`No se puede eliminar: ${cantidad} película${cantidad === 1 ? "" : "s"} dependen de esta categoría.`, true);
            return;
        }
        if (!window.confirm(`¿Eliminar la categoría “${fila.dataset.categoriaNombre}”?`)) return;
        eliminar.disabled = true;
        try {
            await solicitar(`/admin/cartelera/categorias/${fila.dataset.categoriaId}`, { method: "DELETE" });
            fila.remove();
            avisar("Categoría eliminada.");
        } catch (error) {
            eliminar.disabled = false;
            avisar(error.message, true);
        }
    });

    lista.addEventListener("change", async (evento) => {
        const switchEstado = evento.target.closest(".categoria-estado");
        if (!switchEstado) return;
        const fila = switchEstado.closest(".categoria-cartelera-fila");
        const estadoAnterior = !switchEstado.checked;
        switchEstado.disabled = true;
        fila.classList.add("is-saving");
        try {
            await solicitar(`/admin/cartelera/categorias/${fila.dataset.categoriaId}/estado`, {
                method: "PATCH",
                body: JSON.stringify({ activa: switchEstado.checked })
            });
            fila.classList.toggle("is-inactive", !switchEstado.checked);
            fila.querySelector(".categoria-cartelera-switch__label").textContent = switchEstado.checked ? "Activa" : "Inactiva";
            avisar("Estado actualizado.");
        } catch (error) {
            switchEstado.checked = estadoAnterior;
            fila.classList.add("is-error");
            window.setTimeout(() => fila.classList.remove("is-error"), 900);
            avisar(error.message, true);
        } finally {
            switchEstado.disabled = false;
            fila.classList.remove("is-saving");
        }
    });

    const restaurarOrden = (orden) => {
        orden.forEach((id) => {
            const fila = lista.querySelector(`[data-categoria-id="${id}"]`);
            if (fila) lista.appendChild(fila);
        });
    };

    const guardarOrden = async () => {
        const ordenNuevo = ids();
        if (ordenNuevo.join() === ordenAnterior.join()) return;
        lista.classList.add("is-saving");
        try {
            await solicitar("/admin/cartelera/categorias/orden", {
                method: "PUT",
                body: JSON.stringify({ orden: ordenNuevo })
            });
            avisar("Orden guardado.");
        } catch (error) {
            restaurarOrden(ordenAnterior);
            avisar(`${error.message} Recuperando el orden real…`, true);
            window.setTimeout(() => window.location.reload(), 900);
        } finally {
            lista.classList.remove("is-saving");
        }
    };

    const moverSegunPunto = (clienteY) => {
        if (!arrastrada) return;
        const destino = document.elementFromPoint(window.innerWidth / 2, clienteY)?.closest(".categoria-cartelera-fila");
        if (!destino || destino === arrastrada || destino.parentElement !== lista) return;
        const caja = destino.getBoundingClientRect();
        lista.insertBefore(arrastrada, clienteY < caja.top + caja.height / 2 ? destino : destino.nextSibling);
    };

    filas().forEach((fila) => {
        const handle = fila.querySelector(".categoria-cartelera-handle");
        handle.addEventListener("dragstart", (evento) => {
            ordenAnterior = ids();
            arrastrada = fila;
            fila.classList.add("is-dragging");
            evento.dataTransfer.effectAllowed = "move";
        });
        handle.addEventListener("dragend", () => {
            fila.classList.remove("is-dragging");
            arrastrada = null;
            guardarOrden();
        });
        handle.addEventListener("pointerdown", (evento) => {
            if (evento.pointerType === "mouse") return;
            ordenAnterior = ids();
            punteroActivo = evento.pointerId;
            arrastrada = fila;
            handle.setPointerCapture(punteroActivo);
            fila.classList.add("is-dragging");
            evento.preventDefault();
        });
        handle.addEventListener("pointermove", (evento) => {
            if (evento.pointerId !== punteroActivo) return;
            moverSegunPunto(evento.clientY);
            evento.preventDefault();
        });
        const terminarPuntero = (evento) => {
            if (evento.pointerId !== punteroActivo) return;
            fila.classList.remove("is-dragging");
            punteroActivo = null;
            arrastrada = null;
            guardarOrden();
        };
        handle.addEventListener("pointerup", terminarPuntero);
        handle.addEventListener("pointercancel", terminarPuntero);
    });

    lista.addEventListener("dragover", (evento) => {
        evento.preventDefault();
        moverSegunPunto(evento.clientY);
    });
});
