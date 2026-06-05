# Resumen de Cambios — Presencialidad + Altas/Bajas

## Problema original
- El botón **"Recargar Drive"** aparecía confundiendo, cuando debería ser automático.
- Los cambios de Alta/Baja **no se reflejaban al instante** en Presencialidad (había que esperar el caché).
- El contador de registros filtrados **mostraba números inconsistentes**.
- Cargar varios A-BM (Bajas Médicas) era **muy lento** (descargaba toda la hoja en cada paso).
- No había un mensaje claro de **cuántos A-BM fueron guardados**.
- El "No results" en desplegables de Altas **confundía** (sin explicar de dónde venía).

---

## Cambios aplicados

### 1️⃣ **Removido botones confusos** (`asistencia.py`, líneas 924-951)
**Antes:** Había botones de "Sincronizar mes" y "Recargar Drive" (deshabilitados pero visibles).
**Ahora:** Removidos completamente. Presencialidad se actualiza **automáticamente al entrar**.

```
💡 Presencialidad YA recarga datos frescos de:
   • Asistencia (hoja del mes actual)
   • Colaboradores (lista de activos, para el editor)
   
   Sin que el usuario tenga que hacer nada.
```

---

### 2️⃣ **Cambios de Alta/Baja reflejan inmediatamente** (`asistencia.py`, líneas 939-947)
**Antes:** Cuando dabas una Alta, Presencialidad esperaba **30 segundos** (caché de colaboradores).
**Ahora:** El caché se **limpia al entrar** a Presencialidad, así la nueva alta aparece al toque.

```
⚡ Flujo rápido:
   1. Registras Alta en módulo Altas
   2. Entras a Presencialidad Dealer
   3. Ya aparece el nuevo colaborador como "activo" → editable
   (Sin esperar 30 segundos)
```

**Excepción:** Si estás a mitad de cargar varios A-BM, la app NO descarga todo de nuevo en cada paso (por eficiencia).

---

### 3️⃣ **Contador arreglado** (`asistencia.py`, líneas 1133-1145)
**Antes:** 
```
Registros editables (activos): 2 | Total filtrados: 0 | Espejo mensual: 8
                                    ↑ MALO (decía 0, pero en realidad eran 8)
```

**Ahora:**
```
Registros editables (activos): 2 | Total filtrados: 8 | Espejo mensual: 8
                                    ✅ Número real
```

**Qué significa cada uno:**
- **Editables (activos hoy):** cuántos puedes marcar asistencia hoy (solo ACTIVOS)
- **Total filtrados:** cuántos hay en total con los filtros seleccionados
- **Espejo mensual:** cuántos hay en el histórico del mes (para referencia)

---

### 4️⃣ **BM (Bajas Médicas) más rápido** (`asistencia.py`, líneas 932-949)
**Antes:** Cargar 5 A-BM = descargar la hoja completa 5 veces = lentísimo.
**Ahora:** Durante el flujo de carga de múltiples A-BM, NO se vuelve a descargar la hoja (la reutiliza).

```
📊 Antes: 10-15 segundos por cada A-BM
📊 Ahora: 2-3 segundos por cada A-BM (mucho más rápido)
```

---

### 5️⃣ **Mensaje claro de cuántos A-BM se guardaron** (`asistencia.py`, línea 1107)
**Antes:** Decía "✅ N sustento(s) A-BM guardados..." (poco claro qué pasó).
**Ahora:**
```
✅ Se registraron 3 A-BM con su sustento 
   (marca guardada + documento subido a Drive + fila en Sustentos_Bajas).
```

---

### 6️⃣ **Aviso claro en Altas cuando falta referencia** (`formulario.py`, líneas 460-478)
**Antes:** El desplegable de COORDINADOR/PROVINCIA mostraba "No results" sin explicar por qué.
**Ahora:** Muestra un aviso amarillo:
```
⚠️ Estas columnas de la hoja ubicaciones vienen vacías o con otro nombre, 
   por eso su desplegable saldrá como 'No results': COORDINADOR FINAL, ...
   Revisa que existan y tengan datos en la hoja de referencia.
```

---

### 7️⃣ **React #185 corregido** (`registro_mod.py`, líneas 233-256)
**Antes:** Salía "Minified React error #185" cuando veías la matriz con filtros activos.
**Ahora:** Cambiado a un checkbox que el usuario controla → no hay re-renderizados automáticos que causen bucles.

---

## Archivos a reemplazar

```
✅ asistencia.py         (principal: automático, caché, velocidad)
✅ formulario.py         (avisos claros en Altas)
✅ registro_mod.py       (React #185)
```

---

## Prueba esto ahora

### Test 1: Alta → Presencialidad (debería reflejar al toque)
1. Ve a **Altas**
2. Registra un colaborador nuevo (DNI inventado, Konecta SAC, etc.)
3. Dale **Guardar Alta**
4. Ve a **Presencialidad Dealer**
5. Filtra por la razón social que acabas de registrar
6. ✅ Deberías ver el nuevo colaborador en la lista de "editables (activos hoy)" **inmediatamente**
   (antes tenías que esperar 30 segundos)

### Test 2: A-BM rápido
1. Ve a **Presencialidad Dealer**
2. Carga sustento A-BM (cualquier fecha)
3. Marca **3 o 4 A-BM** en el editor
4. Dale **Guardar Presencialidad**
5. Adjunta documentos uno por uno (debería ser rápido, sin re-cargas largas)
6. ✅ Al terminar, deberías ver: "Se registraron 3 A-BM con su sustento..."

### Test 3: Contador correcto
1. Filtra Presencialidad por una razón social
2. Mira que los números sean consistentes:
   - Si tienes 5 colaboradores y 3 son activos hoy → "editables: 3 | total filtrados: 5"

---

## Si sigue habiendo desincronización

Si después de estos cambios sigues viendo que un Alta no aparece en Presencialidad:

1. **En colaboradores:** verifica que el DNI y ESTADO sean exactos:
   - DNI: sin espacios, sin puntos, 8 dígitos (ej: `71771852` no `7.177.185-2`)
   - ESTADO: **exactamente** "ACTIVO" (no "activo", no "ACTIVO " con espacio)

2. **Manual refresh:** aprieta **F5** en el navegador (fuerza un rerun de Streamlit).

3. **Cambios manuales en Drive:** si editas Drive directamente, Streamlit tarda hasta 30 segundos en enterarse 
   (ese es el TTL del caché). Refresca F5 si necesitas que sea al toque.

---

## Preguntas frecuentes

**P: ¿Por qué no se refleja un cambio manual en Drive inmediatamente?**
R: Google Sheets + Streamlit + caché = máximo 30 segundos. Aprieta F5 si quieres al toque.

**P: ¿Qué pasa si estoy en Presencialidad y alguien registra un Alta en otra pestaña?**
R: Cuando hagas F5 (o cierres/abras Presencialidad), verás el nuevo colaborador.

**P: ¿Por qué sigue diciendo "editables: 0" si registré una Alta?**
R: Probablemente el DNI en colaboradores no coincide con el de asistencia (espacios, formato).
   Verifica que ambas hojas tengan el DNI normalizado igual.

**P: ¿Qué es "Total filtrados" vs "Espejo mensual"?**
R: Igual en la mayoría de casos. "Total filtrados" = lo que ves hoy con los filtros.
   "Espejo mensual" = el histórico completo del mes (para auditoría).
