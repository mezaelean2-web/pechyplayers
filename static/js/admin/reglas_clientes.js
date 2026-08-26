const page = document.querySelector(".rules-page");
document.querySelectorAll(".rule-card").forEach((form) => {
  const status = form.querySelector("[role=status]");
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const data = Object.fromEntries(new FormData(form)); data.activo = form.elements.activo.checked;
    const response = await fetch(`/admin/reglas-fulfillment-clientes/${form.dataset.planId}`, {method:"POST",headers:{"Content-Type":"application/json","X-CSRF-Token":page.dataset.csrfToken},body:JSON.stringify(data)});
    const result = await response.json(); status.textContent=result.ok?"Configuración guardada.":(result.mensaje||"No fue posible guardar."); status.classList.toggle("is-error",!result.ok);
  });
  form.querySelector(".copy-reseller")?.addEventListener("click", async (event) => {
    const button=event.currentTarget, detail=`${button.dataset.platform} · ${button.dataset.unit} · ${button.dataset.days} días`;
    if(!window.confirm(`Se copiará ${detail}. La regla cliente quedará inactiva. ¿Continuar?`))return;
    const response=await fetch(`/admin/reglas-fulfillment-clientes/${form.dataset.planId}/copiar-reseller`,{method:"POST",headers:{"Content-Type":"application/json","X-CSRF-Token":page.dataset.csrfToken},body:"{}"});
    const result=await response.json(); if(result.ok)window.location.reload();else{status.textContent=result.mensaje||"No fue posible copiar.";status.classList.add("is-error");}
  });
});
(() => {const input=document.getElementById("rulesSearch"),clear=document.getElementById("rulesSearchClear"),empty=document.getElementById("rulesNoResults"),cards=Array.from(document.querySelectorAll(".rule-card"));if(!input||!clear||!empty)return;const normalize=(v)=>String(v||"").normalize("NFD").replace(/[\u0300-\u036f]/g,"").toLocaleLowerCase("es").trim();const filter=()=>{const q=normalize(input.value);let visible=0;cards.forEach(card=>{const match=!q||normalize(`${card.dataset.planId} ${card.dataset.producto} ${card.dataset.plan}`).includes(q);card.hidden=!match;if(match)visible+=1;});clear.hidden=!input.value;empty.hidden=visible>0||!q;};input.addEventListener("input",filter);clear.addEventListener("click",()=>{input.value="";filter();input.focus();});})();
