(() => {
  "use strict";
  const root = document.querySelector("[data-mail-center]");
  if (!root) return;
  const csrf = root.dataset.csrf || "";
  const api = async (url, method, payload) => {
    const response = await fetch(url, {method, credentials:"same-origin", cache:"no-store",
      headers:{"Content-Type":"application/json", "X-CSRF-Token":csrf},
      body:payload ? JSON.stringify(payload) : undefined});
    try { return await response.json(); } catch (_) { return {ok:false}; }
  };
  root.querySelectorAll("[data-mail-tab]").forEach(button => button.addEventListener("click", () => {
    root.querySelectorAll("[data-mail-tab]").forEach(item => item.classList.toggle("is-active", item === button));
    root.querySelectorAll("[data-mail-panel]").forEach(panel => panel.hidden = panel.dataset.mailPanel !== button.dataset.mailTab);
  }));
  const mailboxForm = root.querySelector("[data-mailbox-form]");
  const actionForm = root.querySelector("[data-action-form]");
  const credentialForm = root.querySelector("[data-credential-form]");
  const openNew = form => { form.reset(); if(form.elements.entity_id)form.elements.entity_id.value=""; form.hidden=false; };
  root.querySelector("[data-open-mailbox]").addEventListener("click", () => {
    openNew(mailboxForm); mailboxForm.querySelector("[data-new-credential]").hidden=false;
    mailboxForm.querySelector("[data-test-unsaved]").hidden=false;
    mailboxForm.elements.username.required=true; mailboxForm.elements.password.required=true;
  });
  root.querySelector("[data-open-action]").addEventListener("click", () => openNew(actionForm));
  root.querySelectorAll("[data-close-form]").forEach(button => button.addEventListener("click", () => button.closest("form").hidden=true));
  root.querySelectorAll("[data-edit-mailbox]").forEach(button => button.addEventListener("click", () => {
    const item=JSON.parse(button.dataset.editMailbox); openNew(mailboxForm);
    for (const name of ["display_name","provider","host","port","tls_mode","folder_key"])
      mailboxForm.elements[name].value=item[name];
    mailboxForm.elements.entity_id.value=item.id; mailboxForm.elements.enabled.checked=Boolean(item.enabled);
    mailboxForm.querySelector("[data-new-credential]").hidden=true;
    mailboxForm.querySelector("[data-test-unsaved]").hidden=true;
    mailboxForm.elements.username.required=false; mailboxForm.elements.password.required=false;
  }));
  root.querySelectorAll("[data-edit-action]").forEach(button => button.addEventListener("click", () => {
    const item=JSON.parse(button.dataset.editAction), config=item.extractor_config; openNew(actionForm);
    for (const name of ["platform","internal_key","display_name","subject_policy","extractor_type"])
      actionForm.elements[name].value=item[name];
    actionForm.elements.entity_id.value=item.id;
    actionForm.elements.allowed_hosts.value=config.allowed_link_hosts.map(row=>row.hostname).join(", ");
    actionForm.elements.sender_domains.value=config.sender_domains.join(", ");
    actionForm.elements.require_dkim_spf.checked=Boolean(config.require_dkim_spf);
    actionForm.elements.enabled.checked=Boolean(item.enabled);
  }));
  mailboxForm.addEventListener("submit", async event => {
    event.preventDefault(); const f=new FormData(mailboxForm), id=f.get("entity_id"), status=mailboxForm.querySelector("[role=status]");
    const payload={display_name:f.get("display_name"),provider:f.get("provider"),host:f.get("host"),
      port:Number(f.get("port")),tls_mode:f.get("tls_mode"),folder_key:f.get("folder_key"),enabled:f.has("enabled")};
    if(!id){payload.username=f.get("username");payload.password=f.get("password");}
    const data=await api(id?`/admin/centro-correo/api/buzones/${id}`:"/admin/centro-correo/api/buzones",id?"PUT":"POST",payload);
    status.textContent=data.ok?"Guardado. Recargando…":
      (data.error==="secret_store_unavailable"?"Almacenamiento seguro no disponible. Reinicia Flask desde una sesión con la master key.":"Configuración rechazada.");
    if(data.ok) location.reload();
  });
  root.querySelector("[data-test-unsaved]").addEventListener("click",async()=>{
    const f=new FormData(mailboxForm),status=mailboxForm.querySelector("[role=status]");
    const payload={display_name:f.get("display_name"),provider:f.get("provider"),host:f.get("host"),port:Number(f.get("port")),
      tls_mode:f.get("tls_mode"),folder_key:f.get("folder_key"),enabled:f.has("enabled"),username:f.get("username"),password:f.get("password")};
    const data=await api("/admin/centro-correo/api/buzones/probar-credencial","POST",payload);
    status.textContent=data.ok?"Conectado correctamente":"No se pudo conectar: "+String(data.status||"connection_failed");
  });
  root.querySelectorAll("[data-rotate-mailbox]").forEach(button=>button.addEventListener("click",()=>{
    credentialForm.reset();credentialForm.elements.mailbox_id.value=button.dataset.rotateMailbox;credentialForm.hidden=false;
  }));
  credentialForm.addEventListener("submit",async event=>{
    event.preventDefault();const f=new FormData(credentialForm),status=credentialForm.querySelector("[role=status]");
    const data=await api(`/admin/centro-correo/api/buzones/${f.get("mailbox_id")}/credencial`,"POST",
      {username:f.get("username"),password:f.get("password")});
    status.textContent=data.ok?"Credencial cambiada. Recargando…":"No se pudo cambiar la credencial.";if(data.ok)location.reload();
  });
  actionForm.addEventListener("submit", async event => {
    event.preventDefault(); const f=new FormData(actionForm), id=f.get("entity_id"), status=actionForm.querySelector("[role=status]");
    const split=name=>String(f.get(name)||"").split(",").map(value=>value.trim()).filter(Boolean);
    const payload={platform:f.get("platform"),internal_key:f.get("internal_key"),display_name:f.get("display_name"),
      subject_policy:f.get("subject_policy"),extractor_type:f.get("extractor_type"),enabled:f.has("enabled"),
      extractor_config:{allowed_link_hosts:split("allowed_hosts").map(hostname=>({hostname,allow_subdomains:false})),
        sender_domains:split("sender_domains"),require_dkim_spf:f.has("require_dkim_spf")}};
    const data=await api(id?`/admin/centro-correo/api/acciones/${id}`:"/admin/centro-correo/api/acciones",id?"PUT":"POST",payload);
    status.textContent=data.ok?"Guardada. Recargando…":"Acción rechazada."; if(data.ok) location.reload();
  });
  root.querySelectorAll("[data-test-mailbox]").forEach(button => button.addEventListener("click", async () => {
    button.disabled=true; button.textContent="Probando…";
    const data=await api(`/admin/centro-correo/api/buzones/${button.dataset.testMailbox}/probar`,"POST");
    button.textContent=data.ok?"Conectado correctamente":String(data.status||"connection_failed"); button.disabled=false;
  }));
})();
