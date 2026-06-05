# SOLUCIÓN FINAL: A-BM, Presencialidad y Límites de Fecha

## Los 3 problemas que resolvimos

### 1️⃣ A-BM SE CUELGA Y PIDE VARIAS VECES

**El problema:** Cuando intentas cargar múltiples A-BM, la ventana se queda abierta indefinidamente o pide varias veces sin avanzar.

**Causa:** El diálogo no se cerraba correctamente entre iteraciones, causando un loop.

**Solución aplicada:**
- ✅ Agregué botón **"⏭️ Saltar (sin sustento)"** para pasar al siguiente A-BM sin adjuntar
- ✅ Agregué botón **"❌ Cancelar todo"** para salir del flujo si se cuelga
- ✅ Mejoré la lógica de queue para limpiar el estado correctamente
- ✅ Removí el `time.sleep()` que causaba delays innecesarios

**Flujo mejorado:**
```
Usuario marca 2 A-BM → Guardar
↓
[Diálogo 1] Adjunta sustento → ✅ Validar sustento
↓ (automáticamente abre el siguiente)
[Diálogo 2] Adjunta sustento → ✅ Validar sustento
↓
Se guarda todo y muestra: "✅ Se registraron 2 A-BM..."
```

Si algo falla o el usuario quiere saltar un A-BM:
```
[Diálogo 1] Sin sustento → ⏭️ Saltar
↓
[Diálogo 2] Adjunta → ✅ Validar
↓
Guarda solo el que tiene sustento
```

---

### 2️⃣ PRESENCIALIDAD MUESTRA CASOS ELIMINADOS HACE HORAS

**El problema:** Eliminas filas en la hoja colaboradores de Drive, pero Presencialidad sigue mostrándolas (9 registros cuando solo hay 2 en jerarquía).

**Causa:** El caché de colaboradores está viejo. Presencialidad leyó los datos ANTES de que los eliminaras.

**Soluciones:**

#### A) Inmediata (user action)
```
Presiona F5 en el navegador
(Esto fuerza a Streamlit a releer colaboradores desde Drive)
```

#### B) Automática (app)
Agregué un aviso claro en Presencialidad:
```
💡 Si editaste colaboradores DIRECTAMENTE en Google Drive (no desde Altas/Bajas), 
   presiona F5 para refrescar y ver los cambios al toque.
```

**Por qué no se refleja automáticamente:**
- Los cambios en Drive se cachean 30 segundos
- Presencialidad carga datos cuando ENTRAS al módulo
- Si cierras/abres la pestaña sin F5, sigue usando datos viejos en memoria

**Recomendación:** Siempre usa **Altas/Bajas** en la app en lugar de editar Drive manualmente. Así los cambios se reflejan al toque.

---

### 3️⃣ SIN LÍMITES DE FECHA PARA MARCAR ASISTENCIA

**El problema:** Podías marcar asistencia para una persona el 2026-06-05 aunque fue dada de baja el 2026-06-04 (FECHA_CESE).

**Causa:** El editor retroactivo (A-BM de días anteriores) no validaba FECHA_ALTA ni FECHA_CESE.

**Solución aplicada:**
- ✅ Agregué validación de fechas: solo permite marcar A-BM si `FECHA_ALTA ≤ fecha_seleccionada ≤ FECHA_CESE`
- ✅ Aviso claro: "X registro(s) están fuera del rango válido (entre su FECHA_ALTA y FECHA_CESE)"
- ✅ Automáticamente salta las filas inválidas al guardar

**Ejemplo:**
```
Fernando Merzenich García:
  - FECHA_ALTA: 2026-06-04
  - FECHA_CESE: (vacío = nunca fue de baja)
  - ✅ Puede marcar asistencia 2026-06-04, 05, 06, etc.

Otro colaborador:
  - FECHA_ALTA: 2026-06-03
  - FECHA_CESE: 2026-06-04
  - ✅ Puede marcar asistencia solo 2026-06-03 y 2026-06-04
  - ❌ NO puede marcar 2026-06-05 (ya está de baja)
```

---

## Cómo usar la versión mejorada

### Cargar múltiples A-BM sin que se cuelgue:

```
1. Marca 3-5 A-BM en el editor (no más de 5 a la vez)
2. Dale "Guardar Presencialidad"
3. Verás: "📋 Cargando sustento A-BM: 1 de 3"
4. Adjunta PDF/imagen → "✅ Validar sustento"
5. Automáticamente abre la ventana del siguiente
6. Repite paso 4-5
7. Al terminar, muestra: "✅ Se registraron 3 A-BM..."
```

**Si quieres saltar uno sin sustento:**
```
[Ventana A-BM] Sin sustento → "⏭️ Saltar (sin sustento)"
→ Automáticamente abre el siguiente
```

**Si se cuelga o necesitas salir:**
```
[Ventana A-BM] → "❌ Cancelar todo"
→ Se limpia la cola y cierras todo
```

---

### Si presencialidad sigue con datos viejos:

```
Opción 1 (rápido): Presiona F5 en el navegador
Opción 2 (completo): Cierra la pestaña y re-abre presencialidad
Opción 3 (ideal): Usa Altas/Bajas en lugar de editar Drive manualmente
```

---

### Marcar A-BM respetando fechas de alta/cese:

```
1. Selecciona período 2026-06 y día 5
2. Verás lista de personas
3. Si alguien está fuera del rango, aviso: 
   "⚠️ X registros están fuera del rango válido"
4. Esas filas no se pueden editar (aunque aparezcan)
5. Solo marca A-BM para personas en rango válido
6. Guarda
```

---

## Cambios técnicos en esta versión (`asistencia_FINAL.py`)

| Problema | Fix | Línea |
|----------|-----|-------|
| A-BM cuelga | Mejor error handling, botón Saltar/Cancelar | 746-795 |
| A-BM pide varias veces | Limpiar flag de diálogo, mejorar queue handler | 1048-1076 |
| Presencialidad datos viejos | Aviso claro sobre refrescar después de cambios Drive | 930-938 |
| Sin límites de fecha | Validar FECHA_ALTA/FECHA_CESE en editor | 1240-1278 |

---

## Archivos a reemplazar

```
Reemplaza tu asistencia.py por asistencia_FINAL.py
```

Mantén también los otros archivos ya actualizados:
- `formulario.py` (para avisos de ubicaciones vacías)
- `registro_mod.py` (para el React #185)

---

## Pruebas rápidas para verificar que todo funciona

### Test A-BM mejorado
```
1. Marca 3 A-BM en presencialidad
2. Guardar → debería mostrar "📋 Cargando sustento A-BM: 1 de 3"
3. Adjunta doc → ✅ Validar
4. Automáticamente abre siguiente (no se cuelga)
5. Repite 3-4 dos veces más
6. Debería terminar sin colgarse
```

### Test presencialidad fresca
```
1. En Google Drive colaboradores, elimina una fila
2. Abre Presencialidad en Streamlit
3. Verás esa persona aún (caché viejo)
4. Presiona F5
5. Ahora NO debería estar (datos frescos)
```

### Test límites de fecha
```
1. Carga sustento A-BM, período 2026-06, día 3
2. Si alguien fue dado de alta el 2026-06-05, está fuera de rango
3. Deberías ver aviso: "X registros están fuera del rango válido"
4. Esa persona NO debe aparecer editable (aunque esté en la lista)
```

---

## Si sigue habiendo problemas

**A-BM cuelga igual:**
- Intenta con menos items (máx 3)
- Presiona F5 para limpiar session
- Si sigue, reporta el navegador (Chrome, Firefox, etc)

**Presencialidad sigue vieja:**
- Presiona F5 (es obligatorio si editaste Drive manualmente)
- O cierra/abre la pestaña de presencialidad

**Faltan avisos de fechas límite:**
- Verifica que FECHA_ALTA y FECHA_CESE estén en el editor
- Si no ves esas columnas, revisa los headers

---

## Recomendación final

**Para evitar futuros problemas:**

1. **Usa Altas/Bajas** para cambios en colaboradores (no edites Drive directamente)
   - Los cambios se reflejan al toque
   - El caché se limpia automáticamente

2. **Presiona F5** después de cambios manuales en Drive
   - Recarga datos frescos

3. **Carga máx 3-5 A-BM por lote**
   - Evita cuelgues por timeout

4. **Verifica fechas** antes de marcar A-BM retroactivo
   - Respeta FECHA_ALTA (no puedes marcar antes del alta)
   - Respeta FECHA_CESE (no puedes marcar después de baja)

---

**¿Listo para probar? Descarga `asistencia_FINAL.py` y reemplaza.**
