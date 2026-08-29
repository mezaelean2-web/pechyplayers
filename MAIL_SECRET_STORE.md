# Mailbox Secret Store

El Centro de Correo usa `SQLiteEncryptedSecretStore`, detrás de la interfaz
`SecretStore`. SQLite conserva únicamente una referencia opaca, un nonce y
ciphertext autenticado AES-256-GCM. La master key nunca se guarda en SQLite ni
se genera automáticamente durante el arranque.

## Master key

El proceso debe recibir `PECHY_MAIL_SECRET_MASTER_KEY` desde el gestor de
secretos del despliegue. Su formato es base64 URL-safe de exactamente 32 bytes.
En desarrollo puede inyectarse en el entorno del proceso; en un VPS debe
provenir de systemd `EnvironmentFile` con permisos restrictivos, Docker/Kubernetes
Secrets o un secret manager equivalente. No debe escribirse en `.env` versionado,
logs, argumentos CLI ni backups de `pechy.db`.

Si falta la key o es incorrecta, la creación, resolución y rotación de
credenciales fallan cerradas. Las referencias legacy de
`PRIVATE_EMAIL_CREDENTIALS_BUNDLE`, incluido `pechy_pilot`, siguen resolviéndose
sin migración automática.

## Backup y restauración

El backup SQLite contiene ciphertext, nunca la master key. Para restaurar un
buzón administrado se necesitan ambos elementos: backup consistente de SQLite y
la misma master key protegida por separado. Perder la master key hace
irrecuperables los secretos, por diseño.

La rotación de una credencial reemplaza nonce+ciphertext dentro de la misma
transacción que actualiza la configuración. La rotación futura de la master key
debe implementarse como operación administrativa versionada; no se intenta
automáticamente.

## Portabilidad y multiempresa

La abstracción `SecretStore` evita dependencia de Windows Credential Manager y
permite sustituir el backend por Vault, AWS Secrets Manager u otro servicio en
un despliegue multiempresa. Las referencias `ms1_...` son aleatorias y no
codifican IDs de mailbox ni tenant.
