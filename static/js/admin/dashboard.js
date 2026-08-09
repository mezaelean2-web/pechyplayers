document.addEventListener("DOMContentLoaded", function () {

    const horaActual = document.getElementById("horaActual");

    function actualizarHora() {
        if (!horaActual) return;

        const ahora = new Date();

        const formato = new Intl.DateTimeFormat("es-CO", {
            weekday: "long",
            day: "numeric",
            month: "long",
            year: "numeric",
            hour: "2-digit",
            minute: "2-digit"
        });

        horaActual.textContent = formato.format(ahora);
    }

    actualizarHora();
    setInterval(actualizarHora, 60000);

    const elementos = document.querySelectorAll(
        ".admin-header, .dashboard-card, .activity-panel, .quick-panel"
    );

    elementos.forEach(function (elemento, indice) {
        elemento.style.opacity = "0";
        elemento.style.transform = "translateY(18px)";

        setTimeout(function () {
            elemento.style.transition =
                "opacity .55s ease, transform .55s ease";

            elemento.style.opacity = "1";
            elemento.style.transform = "translateY(0)";
        }, 80 * indice);
    });

});