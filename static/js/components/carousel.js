/*
class InfiniteCarousel {

    constructor(config) {

        this.lista =
            document.querySelector(config.lista);

        this.itemSelector =
            config.item;

        this.items = [];

    }

    init() {

        if (!this.lista) {

            console.log("No se encontró la lista.");

            return;

        }

        this.items = [
            ...this.lista.querySelectorAll(
                this.itemSelector
            )
        ];

        alert(
    "Películas originales: " +
    this.items.length
);

        this.crearBloques();

        setTimeout(() => {

    this.posicionarCentro();

}, 50);

    }

    crearBloques() {

        

        this.lista.innerHTML = "";

        for (let i = 0; i < 3; i++) {

            this.items.forEach((item) => {

                const copia =
                    item.cloneNode(true);

                copia.dataset.bloque = i;

                this.lista.appendChild(copia);

            });

        }

        alert(
    "Total tarjetas: " +
    this.lista.querySelectorAll(
        this.itemSelector
    ).length

);

    }

    posicionarCentro() {

    alert(
        "clientWidth: " +
        this.lista.clientWidth
    );

    alert(
        "scrollWidth: " +
        this.lista.scrollWidth
    );

    alert(
        "scrollLeft inicial: " +
        this.lista.scrollLeft
    );

    this.lista.scrollLeft = 500;

    alert(
        "scrollLeft final: " +
        this.lista.scrollLeft
    );

}

}

window.InfiniteCarousel = InfiniteCarousel;
*/