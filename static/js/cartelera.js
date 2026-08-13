document.addEventListener("DOMContentLoaded", () => {
    const lista = document.getElementById("carteleraLista");
    if (!lista) return;

    const botones = [...document.querySelectorAll(".categoria-btn:not([data-categoria-clone])")];
    const barraCategorias = document.querySelector(".cartelera-categorias-scroll");
    const contenedorCategorias = barraCategorias?.closest(".cartelera-categorias");
    const mediaDesktop = window.matchMedia("(min-width: 769px)");

    const normalizarCategoria = (valor = "") => valor
        .normalize("NFD")
        .replace(/[\u0300-\u036f]/g, "")
        .trim()
        .toLowerCase();

    let centrarCategoriaActiva = (boton, suave = true) => {
        if (!barraCategorias || !boton) return;
        barraCategorias.scrollTo({
            left: boton.offsetLeft - (barraCategorias.clientWidth - boton.offsetWidth) / 2,
            behavior: suave ? "smooth" : "auto"
        });
    };
    let seleccionarCategoria = () => {};
    let sincronizarIndiceExploracion = () => {};
    let claveCategoriaActiva = normalizarCategoria(
        botones.find((boton) => boton.classList.contains("activa"))?.dataset.categoria || ""
    );

    const activarCategoria = (categoria, suave = true, forzarCentrado = false) => {
        const clave = normalizarCategoria(categoria);
        const cambioLogico = clave !== claveCategoriaActiva;
        let activo = null;

        [...document.querySelectorAll(".categoria-btn")].forEach((boton) => {
            const coincide = normalizarCategoria(boton.dataset.categoria) === clave;
            boton.classList.toggle("activa", coincide);
            if (coincide && !boton.dataset.categoriaClone) activo = boton;
        });

        claveCategoriaActiva = clave;
        sincronizarIndiceExploracion(clave);
        if (cambioLogico || forzarCentrado) centrarCategoriaActiva(activo, suave);
    };

    const iniciarCarruselCategorias = () => {
        if (!barraCategorias || !contenedorCategorias || !botones.length) return;

        botones.forEach((boton, indice) => {
            boton.dataset.categoriaKey = normalizarCategoria(boton.dataset.categoria) || String(indice);
        });

        let longitudOriginales = 0;
        let inicioOriginales = 0;
        let finOriginales = 0;
        let esEstatico = true;
        let normalizando = false;
        let reconstruyendo = false;
        let ignorarScrollInterno = false;
        let navegacionProgramatica = false;
        let timerNavegacion = 0;
        let anchoObservado = 0;
        let indiceExploracion = Math.max(0, botones.findIndex((boton) => boton.classList.contains("activa")));
        let frameScroll = 0;
        let frameResize = 0;
        let arrastrando = false;
        let arrastreReal = false;
        let cancelarClick = false;
        let punteroId = null;
        let origenX = 0;
        let scrollOrigen = 0;
        const representaciones = () => [...barraCategorias.querySelectorAll(".categoria-btn")];
        const centro = () => barraCategorias.getBoundingClientRect().left + barraCategorias.clientWidth / 2;
        const masCercana = (clave) => {
            let candidata = null;
            let distanciaMenor = Infinity;
            representaciones().forEach((boton) => {
                if (clave && boton.dataset.categoriaKey !== clave) return;
                const rect = boton.getBoundingClientRect();
                const distancia = Math.abs(rect.left + rect.width / 2 - centro());
                if (distancia < distanciaMenor) {
                    distanciaMenor = distancia;
                    candidata = boton;
                }
            });
            return candidata;
        };

        const limpiarClon = (clon) => {
            clon.dataset.categoriaClone = "true";
            clon.setAttribute("aria-hidden", "true");
            clon.setAttribute("tabindex", "-1");
            clon.removeAttribute("id");
            clon.querySelectorAll("[id]").forEach((elemento) => elemento.removeAttribute("id"));
            return clon;
        };

        const moverA = (boton, suave = true) => {
            if (!boton || esEstatico) return;
            const rect = boton.getBoundingClientRect();
            barraCategorias.scrollBy({
                left: rect.left + rect.width / 2 - centro(),
                behavior: suave ? "smooth" : "auto"
            });
        };

        sincronizarIndiceExploracion = (categoria) => {
            const clave = normalizarCategoria(categoria);
            const indice = botones.findIndex((boton) => boton.dataset.categoriaKey === clave);
            if (indice >= 0) indiceExploracion = indice;
        };

        const representacionEnDireccion = (clave, direccion) => {
            const centroViewport = centro();
            const candidatas = representaciones().filter((boton) => {
                if (boton.dataset.categoriaKey !== clave) return false;
                const rect = boton.getBoundingClientRect();
                const centroBoton = rect.left + rect.width / 2;
                return direccion > 0
                    ? centroBoton > centroViewport + 1
                    : centroBoton < centroViewport - 1;
            });
            return candidatas.reduce((mejor, boton) => {
                if (!mejor) return boton;
                const rect = boton.getBoundingClientRect();
                const rectMejor = mejor.getBoundingClientRect();
                const distancia = Math.abs(rect.left + rect.width / 2 - centroViewport);
                const distanciaMejor = Math.abs(rectMejor.left + rectMejor.width / 2 - centroViewport);
                return distancia < distanciaMejor ? boton : mejor;
            }, null) || masCercana(clave);
        };

        const terminarNavegacion = () => {
            clearTimeout(timerNavegacion);
            timerNavegacion = window.setTimeout(() => {
                navegacionProgramatica = false;
                normalizar();
            }, 140);
        };

        centrarCategoriaActiva = (boton, suave = true) => {
            if (!boton || esEstatico) return;
            moverA(masCercana(boton.dataset.categoriaKey), suave);
        };

        const normalizar = () => {
            const centroContenido = barraCategorias.scrollLeft + barraCategorias.clientWidth / 2;
            if (esEstatico || reconstruyendo || ignorarScrollInterno
                || navegacionProgramatica || normalizando || longitudOriginales <= 0) return;
            let destino = barraCategorias.scrollLeft;
            if (centroContenido < inicioOriginales) destino += longitudOriginales;
            else if (centroContenido >= finOriginales) destino -= longitudOriginales;
            else return;
            normalizando = true;
            ignorarScrollInterno = true;
            const comportamiento = barraCategorias.style.scrollBehavior;
            barraCategorias.style.scrollBehavior = "auto";
            barraCategorias.scrollLeft = destino;
            barraCategorias.style.scrollBehavior = comportamiento;
            normalizando = false;
            requestAnimationFrame(() => {
                requestAnimationFrame(() => { ignorarScrollInterno = false; });
            });
        };

        const reconstruir = () => {
            if (reconstruyendo) return;
            reconstruyendo = true;
            ignorarScrollInterno = true;
            const activa = botones.find((boton) => boton.classList.contains("activa")) || botones[0];
            barraCategorias.querySelectorAll("[data-categoria-clone]").forEach((clon) => clon.remove());
            barraCategorias.scrollLeft = 0;

            const estilo = getComputedStyle(barraCategorias);
            const gap = parseFloat(estilo.columnGap || estilo.gap) || 0;
            const padding = (parseFloat(estilo.paddingLeft) || 0) + (parseFloat(estilo.paddingRight) || 0);
            const anchoOriginales = botones.reduce((total, boton) => total + boton.getBoundingClientRect().width, 0)
                + gap * Math.max(0, botones.length - 1);
            const anchoDisponibleEstatico = contenedorCategorias.clientWidth - padding;
            esEstatico = anchoOriginales <= anchoDisponibleEstatico + 1;
            contenedorCategorias.classList.toggle("is-static", esEstatico);
            if (esEstatico) {
                requestAnimationFrame(() => {
                    requestAnimationFrame(() => {
                        reconstruyendo = false;
                        ignorarScrollInterno = false;
                    });
                });
                return;
            }

            const anterior = document.createDocumentFragment();
            const siguiente = document.createDocumentFragment();
            botones.forEach((boton) => anterior.appendChild(limpiarClon(boton.cloneNode(true))));
            botones.forEach((boton) => siguiente.appendChild(limpiarClon(boton.cloneNode(true))));
            barraCategorias.prepend(anterior);
            barraCategorias.append(siguiente);

            const primerOriginal = botones[0];
            const primerSiguiente = barraCategorias.querySelectorAll("[data-categoria-clone]")[botones.length];
            inicioOriginales = primerOriginal.offsetLeft;
            longitudOriginales = primerSiguiente.offsetLeft - primerOriginal.offsetLeft;
            finOriginales = inicioOriginales + longitudOriginales;
            barraCategorias.scrollLeft = inicioOriginales - (barraCategorias.clientWidth - primerOriginal.offsetWidth) / 2;
            moverA(masCercana(activa.dataset.categoriaKey), false);
            requestAnimationFrame(() => {
                requestAnimationFrame(() => {
                    reconstruyendo = false;
                    ignorarScrollInterno = false;
                });
            });
        };

        barraCategorias.addEventListener("scroll", () => {
            if (reconstruyendo || ignorarScrollInterno) return;
            if (navegacionProgramatica) {
                terminarNavegacion();
                return;
            }
            cancelAnimationFrame(frameScroll);
            frameScroll = requestAnimationFrame(normalizar);
        }, { passive: true });

        contenedorCategorias.addEventListener("click", (evento) => {
            const flecha = evento.target.closest("[data-categoria-direccion]");
            if (flecha && !esEstatico) {
                const direccion = flecha.dataset.categoriaDireccion === "siguiente" ? 1 : -1;
                normalizar();
                indiceExploracion = (indiceExploracion + direccion + botones.length) % botones.length;
                const claveObjetivo = botones[indiceExploracion].dataset.categoriaKey;
                const objetivo = representacionEnDireccion(claveObjetivo, direccion);
                if (objetivo) {
                    navegacionProgramatica = true;
                    moverA(objetivo, true);
                    terminarNavegacion();
                }
                return;
            }
            const boton = evento.target.closest(".categoria-btn");
            if (!boton || cancelarClick) return;
            activarCategoria(boton.dataset.categoria, true, true);
            seleccionarCategoria(boton.dataset.categoria);
        });

        barraCategorias.addEventListener("pointerdown", (evento) => {
            if (evento.pointerType === "touch" || evento.button !== 0 || esEstatico) return;
            arrastrando = true;
            arrastreReal = false;
            punteroId = evento.pointerId;
            origenX = evento.clientX;
            scrollOrigen = barraCategorias.scrollLeft;
        });
        barraCategorias.addEventListener("pointermove", (evento) => {
            if (!arrastrando || evento.pointerId !== punteroId) return;
            const desplazamiento = evento.clientX - origenX;
            if (!arrastreReal && Math.abs(desplazamiento) < 7) return;
            if (!arrastreReal) {
                arrastreReal = true;
                barraCategorias.setPointerCapture(punteroId);
                barraCategorias.classList.add("is-dragging");
            }
            barraCategorias.scrollLeft = scrollOrigen - desplazamiento;
            evento.preventDefault();
        });
        const terminarArrastre = (evento) => {
            if (!arrastrando || (evento && evento.pointerId !== punteroId)) return;
            cancelarClick = arrastreReal;
            arrastrando = false;
            arrastreReal = false;
            barraCategorias.classList.remove("is-dragging");
            if (punteroId !== null && barraCategorias.hasPointerCapture(punteroId)) barraCategorias.releasePointerCapture(punteroId);
            punteroId = null;
            if (cancelarClick) requestAnimationFrame(() => { cancelarClick = false; });
        };
        barraCategorias.addEventListener("pointerup", terminarArrastre);
        barraCategorias.addEventListener("pointercancel", terminarArrastre);

        const solicitarReconstruccion = () => {
            cancelAnimationFrame(frameResize);
            frameResize = requestAnimationFrame(reconstruir);
        };
        if (window.ResizeObserver) {
            const raizCartelera = contenedorCategorias.closest(".cartelera-home");
            anchoObservado = raizCartelera?.getBoundingClientRect().width || contenedorCategorias.clientWidth;
            new ResizeObserver((entradas) => {
                const anchoNuevo = entradas[0]?.contentRect.width || 0;
                if (Math.abs(anchoNuevo - anchoObservado) < 1) return;
                anchoObservado = anchoNuevo;
                solicitarReconstruccion();
            }).observe(raizCartelera || contenedorCategorias);
        }
        else window.addEventListener("resize", solicitarReconstruccion, { passive: true });
        reconstruir();
    };

    if (mediaDesktop.matches) iniciarCarruselCategorias();

    /* El modal es compartido por móvil, Desktop, originales y clones. */
    const modal = document.getElementById("carteleraModal");
    const fondoModal = document.getElementById("carteleraModalFondo");
    const cerrarModal = document.getElementById("cerrarCarteleraModal");
    const banner = document.getElementById("carteleraModalBanner");
    const titulo = document.getElementById("carteleraModalTitulo");
    const detalles = document.getElementById("carteleraModalDetalles");
    const descripcion = document.getElementById("carteleraModalDescripcion");
    const plataformas = document.getElementById("carteleraModalPlataformas");
    const badges = document.getElementById("carteleraModalBadges");
    const botonVerAhora = document.getElementById("carteleraModalVerAhora");

    const ocultarModal = () => {
        if (!modal) return;
        modal.classList.remove("activo");
        document.body.style.overflow = "";
    };

    lista.addEventListener("click", (evento) => {
        const boton = evento.target.closest(".cartelera-ver");
        if (!boton || !modal) return;

        if (banner) {
            banner.src = boton.dataset.banner || "";
            banner.alt = boton.dataset.titulo || "";
        }
        if (titulo) titulo.textContent = boton.dataset.titulo || "";
        if (detalles) {
            detalles.textContent = [boton.dataset.anio, boton.dataset.genero]
                .filter(Boolean)
                .join(" • ");
        }
        if (descripcion) {
            descripcion.textContent = boton.dataset.descripcion
                || "Próximamente tendremos una descripción completa de esta película.";
        }

        if (plataformas) {
            plataformas.replaceChildren();
            (boton.dataset.plataformas || "")
                .split(",")
                .map((plataforma) => plataforma.trim())
                .filter(Boolean)
                .forEach((plataforma) => {
                    const etiqueta = document.createElement("span");
                    etiqueta.className = "cartelera-plataforma";
                    etiqueta.textContent = plataforma;
                    plataformas.appendChild(etiqueta);
                });
        }

        if (badges) {
            badges.replaceChildren();
            if (boton.dataset.tendencia === "1") {
                const tendencia = document.createElement("span");
                tendencia.className = "cartelera-modal-badge tendencia";
                tendencia.textContent = "🔥 Tendencia";
                badges.appendChild(tendencia);
            }
            if (boton.dataset.destacado === "1") {
                const destacado = document.createElement("span");
                destacado.className = "cartelera-modal-badge destacado";
                destacado.textContent = "⭐ Destacada";
                badges.appendChild(destacado);
            }
        }

        const url = boton.dataset.url || "";
        if (botonVerAhora) {
            if (url) {
                botonVerAhora.href = url;
                botonVerAhora.style.display = "flex";
            } else {
                botonVerAhora.removeAttribute("href");
                botonVerAhora.style.display = "none";
            }
        }

        modal.classList.add("activo");
        document.body.style.overflow = "hidden";
    });

    cerrarModal?.addEventListener("click", ocultarModal);
    fondoModal?.addEventListener("click", ocultarModal);
    document.addEventListener("keydown", (evento) => {
        if (evento.key === "Escape" && modal?.classList.contains("activo")) ocultarModal();
    });

    const iniciarMovil = () => {
        const tarjetas = [...lista.querySelectorAll(".cartelera-card")];
        const mapa = new Map();
        tarjetas.forEach((tarjeta) => {
            const categoria = normalizarCategoria(tarjeta.dataset.categoria);
            if (categoria && !mapa.has(categoria)) mapa.set(categoria, tarjeta);
        });

        const detectarCategoria = () => {
            const centro = lista.scrollLeft + lista.clientWidth / 2;
            let activa = null;
            let distanciaMenor = Infinity;
            tarjetas.forEach((tarjeta) => {
                const distancia = Math.abs(tarjeta.offsetLeft + tarjeta.offsetWidth / 2 - centro);
                if (distancia < distanciaMenor) {
                    distanciaMenor = distancia;
                    activa = tarjeta.dataset.categoria;
                }
            });
            if (activa) activarCategoria(activa);
        };

        seleccionarCategoria = (categoria) => {
            const tarjeta = mapa.get(normalizarCategoria(categoria));
            if (!tarjeta) return;
            activarCategoria(categoria);
            lista.scrollTo({
                left: tarjeta.offsetLeft - (lista.clientWidth - tarjeta.offsetWidth) / 2,
                behavior: "smooth"
            });
            window.setTimeout(detectarCategoria, 350);
        };
        botones.forEach((boton) => {
            boton.addEventListener("click", () => seleccionarCategoria(boton.dataset.categoria));
        });

        let frame = 0;
        lista.addEventListener("scroll", () => {
            cancelAnimationFrame(frame);
            frame = requestAnimationFrame(detectarCategoria);
        }, { passive: true });
        detectarCategoria();
    };

    const iniciarDesktop = () => {
        const contenedor = lista.closest(".cartelera-carousel-shell");
        if (!contenedor) return;

        const originales = [...lista.querySelectorAll(".cartelera-card:not([data-cartelera-clone])")];
        if (!originales.length) return;
        const contadorActual = document.getElementById("carteleraActual");
        const contadorTotal = document.getElementById("carteleraTotal");

        originales.forEach((tarjeta, indice) => {
            tarjeta.dataset.carteleraKey = tarjeta.dataset.id || `pelicula-${indice}`;
        });

        let longitudOriginales = 0;
        let limiteIzquierdo = 0;
        let limiteDerecho = 0;
        let esEstatico = false;
        let normalizando = false;
        let navegacionProgramatica = false;
        let claveDestinoProgramatico = null;
        let timerNavegacion = 0;
        let frameScroll = 0;
        let frameResize = 0;
        let claveActiva = originales[0].dataset.carteleraKey;
        let arrastrando = false;
        let arrastreReal = false;
        let cancelarClick = false;
        let punteroId = null;
        let origenX = 0;
        let scrollOrigen = 0;

        const tarjetasVisuales = () => [...lista.querySelectorAll(".cartelera-card")];

        const limpiarClon = (clon) => {
            clon.dataset.carteleraClone = "true";
            clon.setAttribute("aria-hidden", "true");
            clon.removeAttribute("id");
            clon.querySelectorAll("[id]").forEach((elemento) => elemento.removeAttribute("id"));
            clon.querySelectorAll("a, button, input, select, textarea, [tabindex]")
                .forEach((elemento) => elemento.setAttribute("tabindex", "-1"));
            return clon;
        };

        const centroViewport = () => {
            const rect = lista.getBoundingClientRect();
            return rect.left + rect.width / 2;
        };

        const tarjetaMasCercana = (filtro = () => true) => {
            const centro = centroViewport();
            let candidata = null;
            let distanciaMenor = Infinity;
            tarjetasVisuales().filter(filtro).forEach((tarjeta) => {
                const rect = tarjeta.getBoundingClientRect();
                const distancia = Math.abs(rect.left + rect.width / 2 - centro);
                if (distancia < distanciaMenor) {
                    distanciaMenor = distancia;
                    candidata = tarjeta;
                }
            });
            return candidata;
        };

        const establecerActiva = (tarjeta, sincronizarFiltro = true, forzarSincronizacion = false) => {
            if (!tarjeta) return;
            const cambioLogico = tarjeta.dataset.carteleraKey !== claveActiva;
            claveActiva = tarjeta.dataset.carteleraKey;
            tarjetasVisuales().forEach((item) => item.classList.toggle("is-featured", item === tarjeta));
            originales.forEach((item) => {
                if (item.dataset.carteleraKey === claveActiva) item.setAttribute("aria-current", "true");
                else item.removeAttribute("aria-current");
            });
            const indiceLogico = originales.findIndex((item) => item.dataset.carteleraKey === claveActiva);
            if (contadorActual && indiceLogico >= 0) contadorActual.textContent = String(indiceLogico + 1);
            if (contadorTotal) contadorTotal.textContent = String(originales.length);
            if (sincronizarFiltro && (cambioLogico || forzarSincronizacion)) activarCategoria(tarjeta.dataset.categoria);
        };

        const centrarTarjeta = (tarjeta, suave = true) => {
            if (!tarjeta) return;
            const rectLista = lista.getBoundingClientRect();
            const rectTarjeta = tarjeta.getBoundingClientRect();
            lista.scrollBy({
                left: rectTarjeta.left + rectTarjeta.width / 2 - (rectLista.left + rectLista.width / 2),
                behavior: suave ? "smooth" : "auto"
            });
            establecerActiva(tarjeta);
        };

        const terminarNavegacionProgramatica = () => {
            clearTimeout(timerNavegacion);
            timerNavegacion = window.setTimeout(() => {
                navegacionProgramatica = false;
                normalizarLoop();
                const destino = claveDestinoProgramatico
                    ? tarjetaMasCercana((tarjeta) => tarjeta.dataset.carteleraKey === claveDestinoProgramatico)
                    : tarjetaMasCercana();
                claveDestinoProgramatico = null;
                establecerActiva(destino, true, true);
            }, 140);
        };

        const iniciarNavegacionProgramatica = (objetivo) => {
            if (!objetivo) return;
            claveDestinoProgramatico = objetivo.dataset.carteleraKey;
            navegacionProgramatica = true;
            establecerActiva(objetivo, false);
            const rectLista = lista.getBoundingClientRect();
            const rectObjetivo = objetivo.getBoundingClientRect();
            lista.scrollBy({
                left: rectObjetivo.left + rectObjetivo.width / 2 - (rectLista.left + rectLista.width / 2),
                behavior: "smooth"
            });
            terminarNavegacionProgramatica();
        };

        const normalizarLoop = () => {
            if (esEstatico || normalizando || navegacionProgramatica || longitudOriginales <= 0) return;
            const centroContenido = lista.scrollLeft + lista.clientWidth / 2;
            let destino = lista.scrollLeft;
            if (centroContenido < limiteIzquierdo) destino += longitudOriginales;
            else if (centroContenido >= limiteDerecho) destino -= longitudOriginales;
            else return;

            normalizando = true;
            const comportamiento = lista.style.scrollBehavior;
            lista.style.scrollBehavior = "auto";
            lista.scrollLeft = destino;
            lista.style.scrollBehavior = comportamiento;
            normalizando = false;
        };

        const actualizarCentro = () => {
            normalizarLoop();
            establecerActiva(tarjetaMasCercana());
        };

        const reconstruir = () => {
            const clavePrevia = claveActiva;
            lista.querySelectorAll("[data-cartelera-clone]").forEach((clon) => clon.remove());
            lista.classList.remove("is-static");
            contenedor.classList.remove("is-static");

            const estilo = getComputedStyle(lista);
            const gap = parseFloat(estilo.columnGap || estilo.gap) || 0;
            const anchoDisponible = lista.clientWidth
                - (parseFloat(estilo.paddingLeft) || 0)
                - (parseFloat(estilo.paddingRight) || 0);
            const anchoOriginales = originales.reduce((total, tarjeta) => total + tarjeta.getBoundingClientRect().width, 0)
                + gap * Math.max(0, originales.length - 1);
            esEstatico = anchoOriginales <= anchoDisponible + 1;

            if (esEstatico) {
                lista.classList.add("is-static");
                contenedor.classList.add("is-static");
                lista.scrollLeft = 0;
                const activa = originales.find((tarjeta) => tarjeta.dataset.carteleraKey === clavePrevia)
                    || tarjetaMasCercana((tarjeta) => !tarjeta.dataset.carteleraClone);
                establecerActiva(activa);
                return;
            }

            const copiasPorLado = Math.max(1, Math.ceil(lista.clientWidth / anchoOriginales));
            const fragmentoAnterior = document.createDocumentFragment();
            const fragmentoSiguiente = document.createDocumentFragment();
            for (let copia = 0; copia < copiasPorLado; copia += 1) {
                originales.forEach((tarjeta) => fragmentoAnterior.appendChild(limpiarClon(tarjeta.cloneNode(true))));
                originales.forEach((tarjeta) => fragmentoSiguiente.appendChild(limpiarClon(tarjeta.cloneNode(true))));
            }
            lista.prepend(fragmentoAnterior);
            lista.append(fragmentoSiguiente);

            const clones = [...lista.querySelectorAll("[data-cartelera-clone]")];
            const primerOriginal = originales[0];
            const cantidadAnteriores = copiasPorLado * originales.length;
            const ultimoAnterior = clones[cantidadAnteriores - 1];
            const primerSiguiente = clones[cantidadAnteriores];
            longitudOriginales = primerSiguiente
                ? primerSiguiente.offsetLeft - primerOriginal.offsetLeft
                : anchoOriginales + gap;
            const centroPrimero = primerOriginal.offsetLeft + primerOriginal.offsetWidth / 2;
            const centroUltimoAnterior = ultimoAnterior.offsetLeft + ultimoAnterior.offsetWidth / 2;
            limiteIzquierdo = (centroUltimoAnterior + centroPrimero) / 2;
            limiteDerecho = limiteIzquierdo + longitudOriginales;

            const objetivo = originales.find((tarjeta) => tarjeta.dataset.carteleraKey === clavePrevia) || primerOriginal;
            centrarTarjeta(objetivo, false);
        };

        seleccionarCategoria = (categoria) => {
            const claveCategoria = normalizarCategoria(categoria);
            const objetivo = esEstatico
                ? originales.find((tarjeta) => normalizarCategoria(tarjeta.dataset.categoria) === claveCategoria)
                : tarjetaMasCercana((tarjeta) => normalizarCategoria(tarjeta.dataset.categoria) === claveCategoria);
            if (objetivo) iniciarNavegacionProgramatica(objetivo);
        };

        contenedor.querySelectorAll("[data-cartelera-direccion]").forEach((boton) => {
            boton.addEventListener("click", () => {
                normalizarLoop();
                const actual = tarjetaMasCercana();
                const avance = boton.dataset.carteleraDireccion === "siguiente" ? 1 : -1;
                const indiceLogico = originales.findIndex(
                    (tarjeta) => tarjeta.dataset.carteleraKey === actual?.dataset.carteleraKey
                );
                const indiceObjetivo = (indiceLogico + avance + originales.length) % originales.length;
                const claveObjetivo = originales[indiceObjetivo].dataset.carteleraKey;
                const centroActual = centroViewport();
                const candidatas = tarjetasVisuales().filter((tarjeta) => {
                    if (tarjeta.dataset.carteleraKey !== claveObjetivo) return false;
                    const rect = tarjeta.getBoundingClientRect();
                    const centroTarjeta = rect.left + rect.width / 2;
                    return avance > 0 ? centroTarjeta > centroActual + 1 : centroTarjeta < centroActual - 1;
                });
                const objetivo = candidatas.reduce((mejor, tarjeta) => {
                    if (!mejor) return tarjeta;
                    const distancia = Math.abs(tarjeta.getBoundingClientRect().left + tarjeta.offsetWidth / 2 - centroActual);
                    const distanciaMejor = Math.abs(mejor.getBoundingClientRect().left + mejor.offsetWidth / 2 - centroActual);
                    return distancia < distanciaMejor ? tarjeta : mejor;
                }, null) || tarjetaMasCercana((tarjeta) => tarjeta.dataset.carteleraKey === claveObjetivo);
                if (objetivo) iniciarNavegacionProgramatica(objetivo);
            });
        });

        lista.addEventListener("scroll", () => {
            if (navegacionProgramatica) {
                terminarNavegacionProgramatica();
                return;
            }
            cancelAnimationFrame(frameScroll);
            frameScroll = requestAnimationFrame(actualizarCentro);
        }, { passive: true });

        lista.addEventListener("pointerdown", (evento) => {
            if (evento.pointerType === "touch" || evento.button !== 0) return;
            arrastrando = true;
            arrastreReal = false;
            punteroId = evento.pointerId;
            origenX = evento.clientX;
            scrollOrigen = lista.scrollLeft;
        });

        lista.addEventListener("pointermove", (evento) => {
            if (!arrastrando || evento.pointerId !== punteroId) return;
            const desplazamiento = evento.clientX - origenX;
            if (!arrastreReal && Math.abs(desplazamiento) < 7) return;
            if (!arrastreReal) {
                arrastreReal = true;
                lista.setPointerCapture(punteroId);
                lista.classList.add("is-dragging");
            }
            lista.scrollLeft = scrollOrigen - desplazamiento;
            evento.preventDefault();
        });

        const terminarArrastre = (evento) => {
            if (!arrastrando || (evento && evento.pointerId !== punteroId)) return;
            cancelarClick = arrastreReal;
            arrastrando = false;
            arrastreReal = false;
            lista.classList.remove("is-dragging");
            if (punteroId !== null && lista.hasPointerCapture(punteroId)) lista.releasePointerCapture(punteroId);
            punteroId = null;
            if (cancelarClick) requestAnimationFrame(() => { cancelarClick = false; });
        };

        lista.addEventListener("pointerup", terminarArrastre);
        lista.addEventListener("pointercancel", terminarArrastre);
        lista.addEventListener("click", (evento) => {
            if (!cancelarClick) return;
            evento.preventDefault();
            evento.stopImmediatePropagation();
        }, true);

        const solicitarReconstruccion = () => {
            cancelAnimationFrame(frameResize);
            frameResize = requestAnimationFrame(reconstruir);
        };

        if (window.ResizeObserver) {
            const observador = new ResizeObserver(solicitarReconstruccion);
            observador.observe(lista);
            observador.observe(contenedor);
            originales.forEach((tarjeta) => observador.observe(tarjeta));
        } else {
            window.addEventListener("resize", solicitarReconstruccion, { passive: true });
        }

        reconstruir();
    };

    if (mediaDesktop.matches) iniciarDesktop();
    else iniciarMovil();
});
