/* ==========================================
   PECHY PLAYERS
   TOAST
========================================== */

(function(){

function mostrarToast(texto){

const toast=document.getElementById("pechyToast");

if(!toast) return;

const mensaje=toast.querySelector("strong");

if(mensaje){
mensaje.textContent=texto;
}

toast.classList.add("mostrar");

clearTimeout(toast._timer);

toast._timer=setTimeout(function(){

toast.classList.remove("mostrar");

},2200);

}

window.mostrarToast=mostrarToast;

})();