(() => {
  const modal = document.querySelector('#accountModal');
  if (!modal) return;
  const body = modal.querySelector('#accountDetailBody');
  const renewalModal = document.querySelector('#renewalModal');
  const renewalBody = renewalModal && renewalModal.querySelector('#renewalBody');
  const recoveryModal = document.querySelector('#recoveryModal');
  const recoveryBody = recoveryModal && recoveryModal.querySelector('#recoveryBody');
  const csrf = document.querySelector('.accounts-heading')?.dataset.csrfToken || '';
  const filters = document.querySelector('.accounts-filters');
  try {
    const products = JSON.parse(document.getElementById('accountProductsData')?.textContent || '[]');
    const select = document.createElement('select'); select.name = 'producto'; select.setAttribute('aria-label', 'Producto o plataforma');
    select.append(new Option('Todos los productos', ''));
    products.forEach(product => select.append(new Option(product, product, false, product === new URLSearchParams(location.search).get('producto'))));
    filters?.querySelector('button[type="submit"]')?.before(select);
  } catch (_error) { /* El filtro base sigue operativo si el JSON no puede leerse. */ }
  const escapeHtml = value => String(value ?? '').replace(/[&<>'"]/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[char]));
  const date = value => value ? escapeHtml(String(value).slice(0, 10)) : '—';
  const close = () => { modal.hidden = true; body.innerHTML = ''; document.body.classList.remove('account-modal-open'); };
  const closeRenewal = () => { if (renewalModal) renewalModal.hidden = true; if (renewalBody) renewalBody.innerHTML = ''; document.body.classList.remove('account-modal-open'); };
  const closeRecovery = () => { if (recoveryModal) recoveryModal.hidden = true; if (recoveryBody) recoveryBody.innerHTML = ''; document.body.classList.remove('account-modal-open'); };
  modal.querySelectorAll('[data-close]').forEach(button => button.addEventListener('click', close));
  renewalModal?.querySelectorAll('[data-renew-close]').forEach(button => button.addEventListener('click', closeRenewal));
  recoveryModal?.querySelectorAll('[data-recovery-close]').forEach(button => button.addEventListener('click', closeRecovery));
  document.addEventListener('keydown', event => { if (event.key === 'Escape') close(); });
  async function credentials(id, container) {
    container.innerHTML = '<p class="credentials-loading">Verificando acceso…</p>';
    const response = await fetch(`/revendedores/mis-cuentas/${id}/credenciales`, {headers: {'Accept':'application/json'}});
    const data = await response.json();
    if (!response.ok || !data.autorizadas) { container.innerHTML = `<div class="credentials-empty"><strong>Credenciales no disponibles</strong><span>${escapeHtml(data.motivo || data.error || 'No fue posible autorizar el acceso.')}</span></div>`; return; }
    container.innerHTML = data.campos.map((field, index) => `<div class="credential-row"><span>${escapeHtml(field.etiqueta)}</span><code data-value="${escapeHtml(field.valor)}" data-hidden="${field.sensible ? 'true' : 'false'}">${field.sensible ? '••••••••' : escapeHtml(field.valor || '—')}</code><div>${field.sensible ? `<button type="button" data-show="${index}">Mostrar</button>` : ''}<button type="button" data-copy="${index}">Copiar</button></div></div>`).join('');
    container.querySelectorAll('[data-show]').forEach(button => button.addEventListener('click', () => { const code = container.querySelectorAll('code')[Number(button.dataset.show)]; const hidden = code.dataset.hidden === 'true'; code.textContent = hidden ? code.dataset.value : '••••••••'; code.dataset.hidden = String(!hidden); button.textContent = hidden ? 'Ocultar' : 'Mostrar'; }));
    container.querySelectorAll('[data-copy]').forEach(button => button.addEventListener('click', async () => { const code = container.querySelectorAll('code')[Number(button.dataset.copy)]; await navigator.clipboard.writeText(code.dataset.value); button.textContent = 'Copiado'; setTimeout(() => { button.textContent = 'Copiar'; }, 1200); }));
  }
  const post = async (url, payload = {}) => {
    const controller = new AbortController(), timeout = setTimeout(() => controller.abort(), 30000);
    try {
      const response = await fetch(url, {method:'POST', signal:controller.signal, headers:{'Accept':'application/json','Content-Type':'application/json','X-CSRF-Token':csrf}, body:JSON.stringify(payload)});
      const text = await response.text();
      let data = {};
      try { data = text ? JSON.parse(text) : {}; } catch (_error) { throw new Error('Respuesta del servidor no válida.'); }
      if (!response.ok) throw new Error(data.error || data.mensaje || 'No fue posible completar la operación.');
      return data;
    } catch (error) {
      if (error.name === 'AbortError') throw new Error('La operación tardó demasiado. Puedes reintentar con seguridad.');
      throw error;
    } finally { clearTimeout(timeout); }
  };
  async function openRenewal(id, cantidad = 1) {
    close(); renewalModal.hidden = false; document.body.classList.add('account-modal-open');
    renewalBody.innerHTML = '<p class="credentials-loading">Calculando renovación…</p>';
    try {
      const response = await fetch(`/revendedores/mis-cuentas/${id}/renovacion?cantidad_periodos=${cantidad}`, {headers:{'Accept':'application/json'}});
      const data = await response.json(); if (!response.ok) throw new Error(data.error);
      const options = Array.from({length:data.max_periodos}, (_, index) => `<option value="${index + 1}" ${index + 1 === cantidad ? 'selected' : ''}>${index + 1} período${index ? 's' : ''}</option>`).join('');
      renewalModal.querySelector('#renewalTitle').textContent = `${data.producto} · ${data.plan}`;
      const renewalKey = crypto.randomUUID();
      renewalBody.innerHTML = `<div class="renewal-summary"><p><span>Vencimiento actual</span><strong>${date(data.fecha_vencimiento)}</strong></p><p><span>Precio por período</span><strong>${escapeHtml(data.precio_unitario_cop)}</strong></p><p><span>Duración total</span><strong>${data.duracion_total_dias} días</strong></p><p><span>Nuevo vencimiento estimado</span><strong>${date(data.nuevo_vencimiento_estimado)}</strong></p><p><span>Total a pagar</span><strong>${escapeHtml(data.precio_total_cop)}</strong></p><p><span>Saldo disponible</span><strong>${escapeHtml(data.saldo_cop)}</strong></p></div><label class="renewal-controls">Períodos<select id="renewalPeriods">${options}</select></label><div class="renewal-message">El backend verificará nuevamente precio, saldo, vigencia y asignación al confirmar.</div><button class="renewal-confirm" type="button">Confirmar renovación</button>`;
      renewalBody.querySelector('#renewalPeriods').addEventListener('change', event => openRenewal(id, Number(event.target.value)));
      renewalBody.querySelector('.renewal-confirm').addEventListener('click', async event => {
        event.currentTarget.disabled = true;
        try {
          const result = await post(`/revendedores/mis-cuentas/${id}/renovar`, {cantidad_periodos:cantidad, idempotency_key:renewalKey});
          renewalBody.innerHTML = `<div class="renewal-message"><strong>${escapeHtml(result.mensaje)}</strong><br>${cantidad} período${cantidad === 1 ? '' : 's'} · ${escapeHtml(result.precio_total_cop || '')}<br>Nuevo vencimiento: ${date(result.fecha_vencimiento)}</div>`;
          setTimeout(() => window.location.reload(), 1400);
        } catch (error) {
          renewalBody.querySelector('.renewal-message').classList.add('is-error');
          renewalBody.querySelector('.renewal-message').innerHTML = `${escapeHtml(error.message)} <a href="/revendedores/billetera#recargar">Ir a Billetera / Recargar saldo</a>`;
        } finally { if (event.currentTarget.isConnected) event.currentTarget.disabled = false; }
      });
    } catch (error) { renewalBody.innerHTML = `<div class="renewal-message is-error">${escapeHtml(error.message)}</div>`; }
  }
  async function openRecovery(id, cantidad = 1) {
    close(); recoveryModal.hidden = false; document.body.classList.add('account-modal-open');
    recoveryBody.innerHTML = '<p class="credentials-loading">Revalidando la unidad original…</p>';
    try {
      const response = await fetch(`/revendedores/mis-cuentas/${id}/recuperacion?cantidad_periodos=${cantidad}`, {headers:{Accept:'application/json'}});
      const data = await response.json(); if (!response.ok) throw new Error(data.error);
      const options = Array.from({length:data.max_periodos}, (_, index) => `<option value="${index + 1}" ${index + 1 === cantidad ? 'selected' : ''}>${index + 1} período${index ? 's' : ''}</option>`).join('');
      recoveryModal.querySelector('#recoveryTitle').textContent = `${data.producto} · ${data.plan}`;
      recoveryBody.innerHTML = `<div class="renewal-summary"><p><span>Estado</span><strong>Disponible nuevamente</strong></p><p><span>Tipo</span><strong>${data.tipo_unidad === 'perfil' ? 'Perfil' : 'Cuenta completa'}</strong></p><p><span>Precio por período</span><strong>${escapeHtml(data.precio_unitario_cop)}</strong></p><p><span>Duración por período</span><strong>${data.duracion_base_dias} días</strong></p><p><span>Saldo disponible</span><strong>${escapeHtml(data.saldo_cop)}</strong></p><p><span>Total</span><strong>${escapeHtml(data.precio_total_cop)}</strong></p><p><span>Nueva vigencia estimada</span><strong>${date(data.nueva_vigencia_estimada)}</strong></p></div><label class="renewal-controls">Períodos<select id="recoveryPeriods">${options}</select></label><div class="renewal-message">Antes de confirmar volveremos a comprobar que esta ${data.tipo_unidad === 'perfil' ? 'perfil' : 'cuenta'} siga disponible.</div><button class="renewal-confirm" type="button">Recuperar ${data.tipo_unidad === 'perfil' ? 'perfil' : 'cuenta'}</button>`;
      recoveryBody.querySelector('#recoveryPeriods').addEventListener('change', event => openRecovery(id, Number(event.target.value)));
      recoveryBody.querySelector('.renewal-confirm').addEventListener('click', async event => {
        event.currentTarget.disabled = true;
        try {
          const result = await post(`/revendedores/mis-cuentas/${id}/recuperar`, {cantidad_periodos:cantidad, idempotency_key:crypto.randomUUID()});
          recoveryBody.innerHTML = `<div class="renewal-message"><strong>${escapeHtml(result.mensaje)}</strong><br>${cantidad} período${cantidad === 1 ? '' : 's'} · ${escapeHtml(result.precio_total_cop)}<br>Nuevo vencimiento: ${date(result.fecha_vencimiento)}</div>`;
          setTimeout(() => window.location.reload(), 1400);
        } catch (error) {
          event.currentTarget.disabled = false;
          recoveryBody.querySelector('.renewal-message').classList.add('is-error');
          recoveryBody.querySelector('.renewal-message').innerHTML = `${escapeHtml(error.message)} <a href="/revendedores/billetera#recargar">Ir a Billetera</a>`;
        }
      });
    } catch (error) { recoveryBody.innerHTML = `<div class="renewal-message is-error">${escapeHtml(error.message)}</div>`; }
  }
  document.querySelectorAll('[data-account-id]').forEach(button => button.addEventListener('click', async () => {
    modal.hidden = false; document.body.classList.add('account-modal-open'); body.innerHTML = '<p class="credentials-loading">Cargando detalle…</p>';
    try {
      const response = await fetch(`/revendedores/mis-cuentas/${button.dataset.accountId}`, {headers: {'Accept':'application/json'}}); const data = await response.json(); if (!response.ok) throw new Error(data.error);
      const d = data.detalle; modal.querySelector('#accountModalTitle').textContent = d.producto;
      body.innerHTML = `<div class="account-detail-grid"><p><span>Plan</span><strong>${escapeHtml(d.plan_nombre)}</strong></p><p><span>Tipo</span><strong>${escapeHtml(d.tipo_etiqueta)}</strong></p><p><span>Compra</span><strong>${date(d.fecha_compra)}</strong></p><p><span>Activación</span><strong>${date(d.fecha_activacion)}</strong></p><p><span>Vencimiento</span><strong>${date(d.fecha_vencimiento)}</strong></p><p><span>Estado</span><strong>${escapeHtml(d.estado_etiqueta)}</strong></p><p><span>Períodos</span><strong>${d.cantidad_periodos ?? '—'}</strong></p><p><span>Duración total</span><strong>${escapeHtml(d.dias_contratados)} días</strong></p><p><span>Precio pagado</span><strong>${escapeHtml(d.precio_pagado_cop)}</strong></p><p><span>Identificador</span><strong>${escapeHtml(d.identificador)}</strong></p></div><div class="account-actions"><button class="is-primary" id="renewAccount" type="button">Renovar</button><button id="toggleNoRenew" type="button">${d.no_renovar ? 'Seguir renovando' : 'No renovar'}</button></div><section class="credentials-panel"><header><div><small>DATOS DE ACCESO</small><h3>Credenciales actuales</h3></div><button type="button" id="loadCredentials"><i data-lucide="shield-check"></i>Solicitar acceso</button></header><div id="credentialsBody"><p>Se consultarán de forma segura sólo cuando las solicites.</p></div></section>`;
      if (!d.no_renovar && d.estado_visual !== 'VENCIDA') body.querySelector('#toggleNoRenew')?.remove();
      if (d.recuperada_de) {
        body.querySelector('.account-detail-grid').insertAdjacentHTML('beforeend', `<p><span>Nuevo ciclo</span><strong>Recuperada de ${escapeHtml(d.recuperada_de)}</strong></p>`);
      }
      if (d.cortada_at) {
        body.querySelector('.account-detail-grid').insertAdjacentHTML('beforeend', `<p><span>Fecha de corte</span><strong>${date(d.cortada_at)}</strong></p>`);
        body.querySelector('.account-actions').innerHTML = '<button class="is-primary" id="checkAvailability" type="button">Consultar disponibilidad</button>';
        body.querySelector('.credentials-panel').innerHTML = '<header><div><small>ESTADO DE LA UNIDAD ORIGINAL</small><h3>Disponibilidad para recuperación</h3></div></header><div id="availabilityBody"><p>La consulta revisará el inventario en tiempo real y no reservará la unidad.</p></div>';
        body.querySelector('#checkAvailability').addEventListener('click', async event => {
          event.currentTarget.disabled = true;
          const target = body.querySelector('#availabilityBody'); target.innerHTML = '<p class="credentials-loading">Consultando inventario…</p>';
          try {
            const response = await fetch(`/revendedores/mis-cuentas/${d.id}/disponibilidad`, {headers:{Accept:'application/json'}});
            const result = await response.json();
            target.innerHTML = `<div class="availability-result is-${escapeHtml(result.code || 'UNAVAILABLE').toLowerCase()}"><strong>${escapeHtml(result.code === 'AVAILABLE' ? 'DISPONIBLE' : result.code)}</strong><span>${escapeHtml(result.message || result.error)}</span>${result.recoverable ? `<button class="renewal-confirm" id="recoverAccount" type="button">Recuperar ${result.tipo_unidad === 'perfil' ? 'perfil' : 'cuenta'}</button>` : ''}</div>`;
            target.querySelector('#recoverAccount')?.addEventListener('click', () => openRecovery(d.id));
          } catch (error) { target.innerHTML = `<div class="credentials-empty"><span>${escapeHtml(error.message)}</span></div>`; }
          finally { event.currentTarget.disabled = false; }
        });
      } else {
        body.querySelector('#loadCredentials').addEventListener('click', event => { event.currentTarget.disabled = true; credentials(d.id, body.querySelector('#credentialsBody')); });
        body.querySelector('#renewAccount').addEventListener('click', () => openRenewal(d.id));
        body.querySelector('#toggleNoRenew')?.addEventListener('click', async event => { event.currentTarget.disabled = true; try { await post(`/revendedores/mis-cuentas/${d.id}/${d.no_renovar ? 'seguir-renovando' : 'no-renovar'}`); window.location.reload(); } catch (error) { event.currentTarget.disabled = false; alert(error.message); } });
      }
      if (window.lucide) window.lucide.createIcons();
    } catch (error) { body.innerHTML = `<div class="credentials-empty"><strong>No fue posible cargar el detalle</strong><span>${escapeHtml(error.message)}</span></div>`; }
  }));
})();
