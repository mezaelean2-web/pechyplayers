(() => {
  const modal = document.getElementById('recharge-modal'); if (!modal) return;
  const input = document.getElementById('recharge-amount'); const error = document.getElementById('recharge-error'); const submit = document.getElementById('start-bold');
  const showError = (message) => { error.textContent = message; error.hidden = false; };
  document.getElementById('open-recharge').addEventListener('click', () => { modal.hidden = false; input.focus(); });
  modal.querySelector('.recharge-close').addEventListener('click', () => { modal.hidden = true; });
  modal.addEventListener('click', (event) => { if (event.target === modal) modal.hidden = true; });
  modal.querySelectorAll('[data-amount]').forEach((button) => button.addEventListener('click', () => { input.value = Number(button.dataset.amount).toLocaleString('es-CO'); error.hidden = true; }));
  input.addEventListener('input', () => { const digits = input.value.replace(/\D/g, '').slice(0, 7); input.value = digits ? Number(digits).toLocaleString('es-CO') : ''; });
  const loadBold = () => new Promise((resolve, reject) => { if (window.BoldCheckout) return resolve(); const script = document.createElement('script'); script.src = 'https://checkout.bold.co/library/boldPaymentButton.js'; script.onload = resolve; script.onerror = () => reject(new Error('No fue posible cargar el checkout seguro de Bold.')); document.head.appendChild(script); });
  submit.addEventListener('click', async () => { const monto = input.value.replace(/\D/g, ''); error.hidden = true; submit.disabled = true; try { const response = await fetch('/revendedores/recargas', {method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':window.PECHY_RECHARGE.csrf},body:JSON.stringify({monto})}); const result=await response.json(); if(!response.ok) throw new Error(result.error||'No pudimos iniciar la recarga.'); await loadBold(); new window.BoldCheckout(result.checkout).open(); } catch(requestError){ showError(requestError.message); } finally { submit.disabled=false; } });
})();
