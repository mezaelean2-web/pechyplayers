# Reporte técnico — Fase 1

**Proyecto:** PechyPlayers  
**Fecha de corte:** 12 de agosto de 2026  
**Fuente del reporte:** inspección del árbol de trabajo y comparación contra el commit `994a4e6` (`checkpoint: estado estable antes del nuevo desktop`).

## 1. Resumen ejecutivo

La Fase 1 incorpora la base técnica para administrar imágenes diferenciadas por dispositivo, con énfasis en promociones y en la configuración visual del hero. El trabajo incluye cambios en backend Flask, persistencia SQLite, panel administrativo, presentación pública, seguridad de cargas, compatibilidad con datos históricos y una suite de pruebas de regresión.

El flujo de promociones está conectado de extremo a extremo: permite cargar una imagen móvil obligatoria y una variante de escritorio opcional, conserva ambas de forma independiente, aplica fallbacks si una variante falta y entrega la imagen adecuada mediante `<picture>` en la vista pública.

El centro de configuración también admite imágenes móvil y escritorio para el hero, con aislamiento por tenant, borrador/publicación/restauración, validación de rutas y vista previa administrativa. Sin embargo, al cierre de este corte la plantilla pública no consume todavía `hero_imagen_mobile_efectiva` ni `hero_imagen_desktop_efectiva`; por tanto, esa parte constituye infraestructura preparada, no integración visual pública terminada.

## 2. Estado del árbol de trabajo

Los cambios de esta fase se encuentran actualmente sin confirmar en Git.

- 10 archivos existentes modificados.
- 1 archivo de pruebas nuevo: `tests/test_imagenes_responsive.py`.
- Balance observado antes de crear este reporte: 385 inserciones y 87 eliminaciones.
- La base de datos local `pechy.db` aparece modificada; contiene estado de ejecución y no debe asumirse como una migración versionada.

Archivos funcionales modificados:

- `app.py`
- `configuracion_centro.py`
- `database.py`
- `static/css/admin/configuracion.css`
- `static/css/admin/promociones.css`
- `static/css/pc-v2.css`
- `static/js/admin/configuracion_centro.js`
- `static/js/admin/promociones.js`
- `templates/admin/promociones.html`
- `templates/index.html`
- `tests/test_imagenes_responsive.py` (nuevo)

## 3. Implementación realizada

### 3.1. Gestión responsiva de promociones

Se amplió el modelo de promociones para almacenar dos variantes:

- `imagen`: variante móvil y valor histórico obligatorio.
- `imagen_desktop`: variante opcional para escritorio.

La consulta `obtener_promociones()` devuelve ahora `(id, imagen, activa, imagen_desktop)` y conserva el orden por `orden ASC, id DESC`.

#### Migración compatible

La inicialización comprueba las columnas reales con `PRAGMA table_info(promociones)` y ejecuta `ALTER TABLE promociones ADD COLUMN imagen_desktop TEXT` únicamente cuando sea necesario. La misma comprobación defensiva existe al consultar promociones, lo que permite abrir bases antiguas sin destruir registros ni obligar a una migración manual previa.

#### Procesamiento y seguridad de imágenes

La función `guardar_imagen_promocion()` implementa el siguiente flujo:

1. Verifica que el archivo pueda abrirse realmente como imagen mediante Pillow.
2. Limita los formatos a PNG, JPEG y WEBP.
3. Rechaza dimensiones superiores a 6000 × 6000 píxeles.
4. Normaliza el modo de color a RGB o RGBA cuando sea necesario.
5. Reduce imágenes de más de 2400 píxeles de ancho conservando la proporción.
6. Convierte el resultado a WEBP con calidad 88 y optimización habilitada.
7. Genera nombres no predecibles con `secrets.token_hex(16)`.

Las peticiones de creación y actualización se rechazan cuando su tamaño declarado supera 16 MiB. El sistema no confía en la extensión ni conserva el nombre suministrado por el usuario.

#### Ciclo de vida y limpieza

La creación exige una imagen móvil y acepta una imagen de escritorio opcional. La edición permite reemplazar cualquiera de las variantes sin alterar la otra. Si una carga falla, se eliminan los archivos nuevos que hayan quedado sin referencia.

La función `eliminar_imagen_promocion_si_huerfana()` consulta ambas columnas antes de borrar un archivo, impidiendo eliminar recursos todavía compartidos por otro registro o variante. También normaliza el nombre con `basename`, comprueba que la ruta permanezca dentro de la carpeta de promociones y solo elimina archivos existentes.

Al actualizar o eliminar una promoción se limpian las variantes anteriores únicamente cuando ya no están referenciadas.

#### Resolución de fallbacks

`resolver_variantes_promociones()` valida la existencia física de los archivos antes de enviar promociones a la plantilla pública:

- Si existen ambas variantes, conserva cada una.
- Si falta la variante de escritorio, utiliza la móvil.
- Si falta la móvil pero existe la de escritorio, usa escritorio también como variante efectiva móvil.
- Si no existe ningún archivo, omite la promoción para evitar referencias rotas.

### 3.2. Panel administrativo de promociones

La interfaz administrativa fue ampliada para mostrar y editar ambas variantes de forma independiente:

- Vista previa separada para móvil y escritorio.
- Mensaje explícito cuando escritorio utilizará el fallback móvil.
- Botones independientes para cambiar cada imagen.
- Inputs restringidos a PNG, JPEG y WEBP.
- Previsualización local con `FileReader` antes de publicar.
- Envío de `imagen` e `imagen_desktop` mediante `DataTransfer` al formulario existente.
- Indicador en cada tarjeta: “Móvil + Escritorio” o “Desktop usa fallback”.

La lógica conserva el modo de edición y habilita los controles de publicación al seleccionar una nueva variante. La imagen móvil continúa siendo requerida para una promoción nueva.

El CSS incorpora una cuadrícula de previsualización con proporciones diferenciadas, estilos compartidos para ambas imágenes, etiqueta de variantes y adaptación a la estructura visual ya existente.

### 3.3. Renderizado público de promociones

La promoción destacada y las tarjetas secundarias usan ahora el elemento semántico `<picture>`:

- El `<img>` base carga la variante móvil.
- Un `<source media="(min-width: 769px)">` entrega la variante de escritorio.
- Cuando no existe una variante específica de escritorio, se usa la móvil como fallback.

`static/css/pc-v2.css` asegura que los nuevos contenedores `<picture>` ocupen el ancho y alto disponibles sin alterar el layout previo.

Nota: existe otra referencia a la primera promoción en `templates/index.html` alrededor de la línea 713, utilizada como `background-image`; esa referencia sigue usando la variante móvil. Conviene revisarla en la siguiente fase si ese bloque también debe cambiar según el viewport.

### 3.4. Variantes del hero en el centro de configuración

El módulo `inicio` incorpora tres campos de activos:

- `hero_imagen`: campo histórico conservado como fallback.
- `hero_imagen_mobile`: nueva variante móvil.
- `hero_imagen_desktop`: nueva variante de escritorio.

`configuracion_efectiva()` calcula valores derivados sin romper configuraciones anteriores:

- Móvil efectivo: móvil → histórico → escritorio.
- Escritorio efectivo: escritorio → móvil → histórico.

Los valores se exponen tanto en `modulos.inicio` como en el nivel plano de configuración bajo `hero_imagen_mobile_efectiva` y `hero_imagen_desktop_efectiva`.

El panel administrativo asigna etiquetas comprensibles, identifica el campo histórico como fallback y muestra una miniatura del recurso actual o recién cargado.

#### Estado de integración

La configuración, los fallbacks y la administración del hero están implementados, pero `templates/index.html` no referencia todavía los valores efectivos del hero. Por ello, cargar y publicar esas imágenes no cambia aún el hero visible en el sitio público. Esta integración debe tratarse como pendiente y no como funcionalidad terminada.

### 3.5. Aislamiento por tenant

Se añadió `_tenant_configuracion()` para obtener el tenant desde `session["tenant_id"]`, usando `default` como valor de respaldo. El identificador se limita a 80 caracteres y solo acepta letras, números, guion y guion bajo.

El tenant se propaga en las operaciones administrativas de configuración:

- lectura de estado y módulos;
- guardado de borradores;
- restauración de módulo o de toda la configuración;
- publicación;
- auditoría;
- preview;
- carga de archivos.

Los recursos se guardan en `static/uploads/configuracion/<tenant>/`, evitando que distintos clientes compartan por accidente la misma carpeta lógica.

Observación: la ruta pública `/` llama actualmente a `configuracion_efectiva()` sin indicar tenant, por lo que usa `default`. El aislamiento está aplicado al flujo administrativo, pero una experiencia pública white-label por tenant requerirá definir cómo se resuelve el tenant en solicitudes públicas.

### 3.6. Validación de rutas de activos

La validación anterior fue reemplazada por una expresión regular anclada que solo admite rutas con esta forma:

```text
/static/uploads/configuracion/<tenant>/<archivo>
```

El patrón impide subdirectorios inesperados y secuencias como `../`, reduciendo el riesgo de traversal o de apuntar a archivos fuera del espacio permitido.

## 4. Pruebas añadidas

`tests/test_imagenes_responsive.py` contiene 10 casos con base SQLite y carpeta de activos temporales:

1. Migración no destructiva de una tabla histórica de promociones.
2. Fallback de promociones entre móvil, escritorio y archivos ausentes.
3. Persistencia y actualización independiente de ambas variantes.
4. Variantes del hero y conservación de configuración white-label.
5. Fallback móvil/escritorio y compatibilidad con el campo histórico del hero.
6. Ciclo de borrador, publicación y restauración.
7. Aislamiento de variantes del hero entre tenants.
8. Rechazo de traversal en rutas de activos.
9. Rechazo de un archivo falso y ausencia de registros residuales.
10. Respuesta correcta de inicio con una promoción legacy.

Las pruebas restauran las referencias globales de base de datos y carpeta de promociones en `tearDown`, y eliminan los recursos temporales después de cada caso.

### Resultado de verificación en este corte

Se intentó ejecutar:

```powershell
.\venv\Scripts\python.exe -m unittest tests.test_imagenes_responsive -v
```

La suite no llegó a iniciar porque el ejecutable del entorno virtual apunta a `C:\Users\pechy\AppData\Local\Programs\Python\Python313\python.exe` y el sistema respondió “Acceso denegado”. Por tanto, los casos están implementados pero **no hay una ejecución satisfactoria verificable en este entorno**.

También se comprobó estáticamente que las referencias de promociones usan el nuevo cuarto elemento y que no existen referencias públicas a las variantes efectivas del hero.

## 5. Compatibilidad y decisiones técnicas

- Se conserva `imagen` como columna móvil obligatoria para no romper registros y plantillas históricas.
- `imagen_desktop` es nullable y opcional.
- Se mantienen fallbacks bidireccionales para tolerar datos parciales o archivos eliminados.
- La migración es aditiva y no recrea la tabla.
- Los nombres aleatorios evitan colisiones y exposición del nombre original.
- La conversión uniforme a WEBP reduce peso y simplifica el formato almacenado.
- El uso de `<picture>` delega al navegador la selección por media query.
- El corte de escritorio se fijó en 769 px, consistente con el enfoque mobile-first aplicado.
- Los cambios administrativos respetan el esquema existente de autenticación por `session["admin"]`.

## 6. Riesgos y pendientes detectados

### Prioridad alta

1. Conectar `hero_imagen_mobile_efectiva` y `hero_imagen_desktop_efectiva` con el hero de `templates/index.html`.
2. Reparar o recrear el entorno virtual y ejecutar la suite completa.
3. Definir la resolución de tenant en la ruta pública si se requiere white-label real fuera del panel.

### Prioridad media

1. Revisar el `background-image` de promoción que aún usa solo `promociones[0][1]`.
2. Añadir pruebas HTTP de límites de tamaño, dimensiones máximas y formatos JPEG/WEBP válidos.
3. Añadir prueba de limpieza de archivos huérfanos al actualizar y eliminar.
4. Validar visualmente el panel en viewports estrechos; la nueva cuadrícula de variantes no incluye en este cambio una media query específica.
5. Evitar que `obtener_promociones()` realice DDL en una ruta de lectura; una vez estabilizada la migración, conviene centralizarla exclusivamente en la inicialización.

### Consideraciones operativas

- El límite de 16 MiB se aplica al cuerpo completo de la petición y no equivale a 16 MiB por imagen.
- La conversión de imágenes grandes puede consumir memoria antes del redimensionado; el límite dimensional mitiga, pero no elimina, el riesgo de imágenes especialmente comprimidas.
- La eliminación segura depende de referencias registradas en la base actual; archivos históricos que nunca estén registrados no son limpiados automáticamente.
- `pechy.db` contiene cambios locales y debe revisarse antes de incluirse en un commit o despliegue.

## 7. Criterios de aceptación alcanzados

- La base antigua puede incorporar `imagen_desktop` sin perder promociones.
- Una promoción puede conservar imágenes móvil y escritorio distintas.
- Es posible cambiar una variante sin sobrescribir la otra.
- Una promoción sin variante de escritorio sigue funcionando mediante fallback.
- Los archivos inválidos no crean registros.
- Los archivos sustituidos o eliminados se limpian solo cuando quedan huérfanos.
- El frontend público usa recursos responsivos para los bloques principales de promociones.
- El centro de configuración separa variantes del hero y conserva el campo legacy.
- Las configuraciones administrativas quedan aisladas por tenant.
- Las rutas de activos rechazan traversal.

## 8. Criterios todavía no alcanzados

- El hero público aún no cambia de imagen según el dispositivo.
- No se confirmó la ejecución exitosa de las pruebas automatizadas por el problema del intérprete.
- No se realizó en este corte una validación visual manual en navegador.
- La selección pública de configuración por tenant continúa usando el tenant predeterminado.

## 9. Recomendación para cierre de fase

Antes de declarar la Fase 1 completamente cerrada se recomienda:

1. Integrar las variantes efectivas del hero con `<picture>` o con variables CSS responsivas.
2. Corregir el entorno de Python y obtener una corrida verde de los 10 casos nuevos más la suite general.
3. Ejecutar una prueba manual de creación, edición, fallback y eliminación de promociones en móvil y escritorio.
4. Confirmar si la experiencia pública será mono-tenant (`default`) o resolver el tenant por dominio, subdominio o sesión.
5. Separar en el commit los cambios de código, las pruebas y cualquier modificación intencional de datos.

## 10. Conclusión

La fase deja una implementación sólida y retrocompatible para promociones responsivas, con controles de seguridad, limpieza de archivos y administración independiente de variantes. También deja preparada la capa de configuración responsiva del hero y mejora el aislamiento multi-tenant del panel. Los principales puntos para el cierre definitivo son conectar el hero a la vista pública, validar el comportamiento visual y recuperar una ejecución automatizada exitosa.
