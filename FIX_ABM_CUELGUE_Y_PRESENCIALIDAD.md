# Problema: A-BM se cuelga + Presencialidad con datos viejos

Revisé tu caso en las imágenes:
- **Jerarquía:** 2 registros KONECTA (correcto)
- **Presencialidad:** 9 registros KONECTA (viejos, deberían ser 2)
- **A-BM:** Se cuelga cuando intentas cargar múltiples a la vez

## Causa 1: Presencialidad con datos viejos

Cuando ves en Presencialidad **9 registros KONECTA pero en Jerarquía solo hay 2**, significa:

```
Eliminaste 7 filas en Google Drive (colaboradores)
↓
Presencialidad aún tiene esos 7 en caché/memoria (porque los leyó antes de eliminarlos)
↓
"Datos desincronizados"
```

### Por qué pasa
- Presencialidad carga los datos **UNA sola vez** cuando entras al módulo.
- Si luego EDITAS colaboradores **directamente en Drive** (sin usar Altas/Bajas), Presencialidad no se entera.
- El caché de colaboradores tiene TTL de 30 segundos, pero eso es entre reruns, no dentro de la misma sesión.

### Solución
**Opción A (rápida):** Presiona **F5** en el navegador después de editar colaboradores en Drive.
```
Esto fuerza que Streamlit recargue y lea datos frescos de Drive.
```

**Opción B (automática):** Agregué un aviso en Presencialidad que te recuerda:
```
💡 Si editaste colaboradores DIRECTAMENTE en Google Drive (no desde Altas/Bajas), 
   presiona F5 para refrescar y ver los cambios al toque.
```

---

## Causa 2: A-BM se cuelga cuando cargas múltiples

El flujo de múltiples A-BM funciona así:

```
1. Marcas 3 A-BM y das "Guardar"
2. La app abre un diálogo → "Adjunta sustento para persona 1"
3. Validas → st.rerun()
4. Se abre diálogo 2 → "Adjunta sustento para persona 2"
5. Validas → st.rerun()
6. Se abre diálogo 3 → "Adjunta sustento para persona 3"
7. Validas → guardar todo en Drive
```

**El problema:** si hay un error en medio (ej: error al crear el diálogo, error en Drive), la cola **queda en estado inconsistente** y la app se congela esperando indefinidamente.

### Solución aplicada

Agregué **guardias de seguridad** en el código:

1. **Contador de seguridad:** Si la cola tiene más de 100 items (error anormal), se limpia automáticamente.
```python
if len(_cola_abm) > 100:
    st.error("❌ Error: cola de A-BM con más de 100 items. Se limpió la cola.")
    # Limpia y rerun
```

2. **Contador visible:** Ahora ves progreso mientras cargas:
```
📋 Cargando sustento A-BM: 1 de 3
```

3. **Mejor manejo de errores:** Si algo falla en el diálogo, muestra un error claro:
```
❌ Error en el diálogo A-BM: [...]. Intenta de nuevo.
```

4. **Auto-limpieza:** Si hay un error, se limpia la cola automáticamente (en lugar de quedarse indefinida).

### Cómo usar después del fix

Cuando cargues múltiples A-BM:

```
1. Marca 2 o 3 A-BM (no hagas 10+ a la vez; probablemente habrá timeout)
2. Dale "Guardar Presencialidad"
3. Verás: "📋 Cargando sustento A-BM: 1 de 3"
4. Adjunta PDF/imagen en la ventana
5. Dale "Validar sustento"
6. Automáticamente abre ventana 2
7. Repite
8. Al terminar, verás: "✅ Se registraron 3 A-BM con su sustento..."
```

**Si se cuelga:**
- Presiona **F5** (refrescar navegador)
- O, si la cola quedó basura, recarga la pestaña y vuelve a intentar (solo 2-3 A-BM esta vez)

---

## Cambios en esta versión (`asistencia_v3.py`)

### ✅ Guardias contra cuelgue
- Contador de seguridad: si cola > 100 items → se limpia
- Manejo de excepciones en el diálogo
- Mensaje de progreso: "X de Y" mientras cargas

### ✅ Aviso sobre datos frescos
- Se agregó nota clara: "Si editaste colaboradores en Drive, presiona F5"
- Evita confusión cuando eliminas filas y sigue viéndolas en Presencialidad

### ✅ Mejor recuperación de errores
- Si el diálogo falla, la cola se limpia (no queda colgada)
- Mensaje de error claro en lugar de silencio

---

## Pasos a seguir

### Ahora mismo
1. Reemplaza `asistencia.py` por `asistencia_v3.py`
2. Presiona F5 en Presencialidad para refrescar datos
3. Verifica que jerarquía y presencialidad tengan el mismo conteo

### Prueba A-BM
1. Marca **2 o 3** A-BM en Presencialidad
2. Dale "Guardar Presencialidad"
3. Deberías ver: "📋 Cargando sustento A-BM: 1 de 3"
4. Adjunta documentos (no se cuelgue esta vez)
5. Si todo OK, intenta con 4-5

### Si sigue colgándose
El problema podría ser:
- **Conexión lenta a Google Drive:** los archivos tardan en subir
- **Demasiados A-BM de una vez:** intenta con menos (máx 3-5)
- **Error silencioso en Drive:** revisa la consola (F12 → Console tab)

---

## Código de las guardias (para referencia)

```python
if _cola_abm:
    _procesados = set(_pendientes.keys())
    _sin_sustento = [item for item in _cola_abm if item["clave"] not in _procesados]
    
    # Seguridad: si la cola tiene más de 100 items, algo anormal pasó
    if len(_cola_abm) > 100:
        st.error("❌ Error: cola de A-BM con más de 100 items. Se limpió la cola.")
        st.session_state["_cola_abm"] = []
        st.session_state[KEY_SUSTENTOS_PENDIENTES] = {}
        st.rerun()
    
    if _sin_sustento:
        # Mostrar progreso
        _indice_actual = len(_cola_abm) - len(_sin_sustento)
        _total_cola = len(_cola_abm)
        st.info(f"📋 Cargando sustento A-BM: {_indice_actual + 1} de {_total_cola}")
        
        try:
            _next = _sin_sustento[0]
            dialogo_sustento_bm(...)
            st.stop()
        except Exception as _e_dialog:
            # Si falla, limpiar y avisar
            st.error(f"❌ Error en el diálogo A-BM: {_e_dialog}.")
            st.session_state["_cola_abm"] = []
            st.session_state[KEY_SUSTENTOS_PENDIENTES] = {}
```

---

## Preguntas frecuentes

**P: ¿Presencia sigue mostrando 9 cuando jerarquía solo tiene 2?**
R: Presiona **F5**. La app cargó los datos antes de que eliminaras las filas. F5 recarga todo.

**P: ¿Puedo cargar 10 A-BM de una vez?**
R: Mejor no. Intenta máximo 5. Más de eso puede causar timeout en Drive.

**P: ¿Qué hago si dice "Error: cola de A-BM con más de 100 items"?**
R: Se limpió la cola automáticamente. Presiona F5 y vuelve a intentar con menos items.

**P: ¿Por qué aparece "Cargando sustento A-BM: 1 de 3" dos veces?**
R: Eso es normal — aparece una vez por cada rerun del diálogo. Es solo para que veas progreso.
