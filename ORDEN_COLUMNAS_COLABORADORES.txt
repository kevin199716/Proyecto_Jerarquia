# Optimización de memoria — Proyecto Jerarquía (Render + Google Sheets)

Objetivo: eliminar los cortes por "exceeded memory limit" en Render (512 MB RAM)
manteniendo EXACTAMENTE la misma lógica de negocio, columnas y flujos.

## Causa raíz detectada
Con solo ~17 000 registros la app no debería caerse nunca. El problema no eran
los datos sino cómo se cargaban:

1. Se leía la hoja COMPLETA con `get_all_records()` (lista de diccionarios, la
   forma más cara en RAM) en cada interacción.
2. La matriz de jerarquía se recargaba en TODAS las pantallas (Alta, Bajas,
   Presencialidad), aunque no se usara.
3. En Presencialidad se guardaban DOS copias completas del DataFrame por sesión
   (`KEY_DF_TOTAL` y `KEY_DF_ORIGINAL`) y luego se volvían a copiar en cada render
   → hasta 4 copias por usuario, multiplicado por cada usuario conectado.
4. Las bajas hacían hasta 6 llamadas `update_cell` separadas → cuelgues/timeouts.
5. `requirements.txt` cargaba librerías pesadas que NO se usan (streamlit-aggrid,
   numpy, oauth2client, openpyxl, etc.), consumiendo RAM al arrancar.

## Cambios aplicados (misma lógica, sin cambiar columnas)

### sheets.py
- Cliente gspread y apertura del libro cacheados (`@st.cache_resource`): el libro
  se abre UNA vez por proceso en vez de buscarse en Drive por nombre en cada lectura.

### registro_mod.py (matriz)
- `_leer_matriz_cached`: ahora usa `get_all_values()` (liviano) y devuelve un
  DataFrame ya limpio y con DNI/celular como texto, UNA sola vez y compartido
  entre sesiones. Antes leía y copiaba en cada render.
- Filtros por referencia: solo se materializa una copia cuando hay un filtro activo.
- La tabla grande se renderiza dentro de un desplegable cerrado (no se dibujan
  17k filas en cada clic).
- Bajas: UNA sola escritura por lotes (`update_cells`) en vez de 6 `update_cell`.
  Refresca la caché de la matriz al instante.

### asistencia.py (la fuga mayor)
- Lectura de Asistencia compartida en caché global (`@st.cache_data`): se hace
  UNA vez para todos los usuarios.
- `cargar_cache_desde_drive`: UNA sola copia de trabajo por sesión. `KEY_DF_ORIGINAL`
  referencia el mismo objeto (el diff de guardado hace su propia copia cuando la
  necesita). Igual tras guardar.
- Render usa una sola copia de trabajo en vez de dos.
- `leer_colaboradores_drive`: `get_all_values()` + caché, en vez de `get_all_records()`.
- La sincronización de mes limpia la caché de colaboradores antes de leer, para
  no perder altas/bajas recientes.

### formulario.py
- `_leer_colaboradores_cached`: `get_all_values()` en vez de `get_all_records()`.

### requirements.txt
- Solo lo que se usa, con versiones fijas:
  streamlit, gspread, google-auth, google-api-python-client, protobuf, pandas,
  pytz, requests. (Se quitaron aggrid, numpy, openpyxl, oauth2client, etc.)

### .streamlit/config.toml (nuevo)
- Configuración de bajo consumo en producción: sin file-watcher, sin telemetría,
  headless, reruns rápidos, mensajes de error ocultos al cliente.

## Validación realizada
- Todos los .py compilan sin errores.
- Todos los módulos importan correctamente.
- Test con datos simulados: la lectura optimizada produce el MISMO contenido que
  `get_all_records()`; los DNI se mantienen como texto con relleno a 8 dígitos.
- Confirmado que `KEY_DF_TOTAL is KEY_DF_ORIGINAL` (una sola copia en RAM).
- Confirmada la escritura por lotes (1 llamada, 0 `update_cell` individuales).

## Notas
- `utils.py` (que importa `pydeck`) NO se importa en la app, así que no consume
  memoria en runtime. Se dejó intacto.
- `usuarios.json` está en `.gitignore`: no se subirá a GitHub. Cambia las claves
  reales antes de usar en producción.
- Próximo paso recomendado (cuando puedas): migrar a PostgreSQL de Render para
  consultar solo lo necesario y dejar de cargar la hoja completa. Eso elimina el
  problema de raíz y escala sin el tope de 10M celdas de Sheets.
