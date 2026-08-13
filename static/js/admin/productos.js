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

    if (!buscador) {
        return;
    }

    const productos = Array.from(
        document.querySelectorAll(".admin-producto")
    );
    const resultado = document.getElementById("resultadoBusquedaAdmin");

    buscador.addEventListener("input", function () {
        const consulta = buscador.value.trim().toLocaleLowerCase("es");
        let visibles = 0;

        productos.forEach(function (producto) {
            const nombre = producto.dataset.nombre || "";
            const coincide = nombre.includes(consulta);

            producto.hidden = !coincide;
            if (coincide) {
                visibles += 1;
            }
        });

        if (!resultado) {
            return;
        }

        const sinResultados = consulta !== "" && visibles === 0;
        resultado.hidden = !sinResultados;
        resultado.textContent = sinResultados
            ? "No se encontraron productos con esa búsqueda."
            : "";
    });
});
