/* ==========================================
   PECHY PLAYERS
   SPLASH
========================================== */

(function(){

function iniciarSplash(){

if(window.innerWidth>768) return;

const splash=document.getElementById("splashMobile");

if(!splash) return;

setTimeout(function(){

splash.classList.add("oculto");

},1800);

setTimeout(function(){

splash.remove();

if(typeof mostrarPantallaRecordatorios==="function"){

mostrarPantallaRecordatorios();

}

},2500);

}

window.iniciarSplash=iniciarSplash;

})();