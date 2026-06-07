# 🔴 FIXES FALTANTES - Cambios Puntuales Necesarios

## PROBLEMA 1: Campo DISTRITO no aparece en formulario de Alta

### Ubicación: `formulario.py` línea ~560

**BUSCA:**
```python
provincia = st.selectbox(
    "PROVINCIA",
    provincia_options,
    key=k("provincia"),
)
```

**REEMPLAZA CON:**
```python
provincia = st.selectbox(
    "PROVINCIA",
    provincia_options,
    key=k("provincia"),
)

# 🆕 NUEVO: Campo DISTRITO
distrito_options = lista_limpia(df_ubi, "DISTRITO") if provincia and provincia != "" else [""]
distrito = st.selectbox(
    "DISTRITO",
    distrito_options,
    key=k("distrito"),
)
```

---

## PROBLEMA 2: El DISTRITO no se guarda en el registro

### Ubicación: `formulario.py` línea ~680 (donde se construye el dict de datos)

**BUSCA:**
```python
"DEPARTAMENTO": departamento,
"PROVINCIA": provincia,
"DNI": dni,
```

**REEMPLAZA CON:**
```python
"DEPARTAMENTO": departamento,
"PROVINCIA": provincia,
"DISTRITO": distrito,  # 🆕 NUEVA LÍNEA
"DNI": dni,
```

---

## PROBLEMA 3: Error de tipo en asistencia.py línea 1245

### Ubicación: Línea ~1245 en asistencia.py ORIGINAL

**ERROR ACTUAL:**
```python
TypeError: 'str' object cannot be interpreted as an integer
```

**CAUSA:** Selección de día usando sintaxis incorrecta

**SOLUCIÓN:** ✅ YA INCLUIDA en el nuevo `asistencia.py`

El nuevo archivo tiene la función `mostrar_asistencia()` completamente rediseñada para evitar este error.

---

## PROBLEMA 4: Columna DISTRITO no existe en Google Drive

### Ubicación: Hoja "ubicaciones" en Google Drive

**ACCIÓN REQUERIDA:**
1. Abre la hoja "ubicaciones" en Google Drive
2. Agrega columna entre PROVINCIA y el siguiente campo:
   - **Nombre:** DISTRITO
   - **Tipo:** Texto
   - **Rellena:** Distritos según provincia (ej: LIMA, SAN ISIDRO, MIRAFLORES, etc)

**Ejemplo de estructura:**
```
DEPARTAMENTO | PROVINCIA | DISTRITO | SUPERVISOR | ...
LIMA         | LIMA      | LIMA     | Juan       | ...
LIMA         | LIMA      | SAN ISIDRO | Juan     | ...
AMAZONAS     | CHACHAPOYAS | CHACHAPOYAS | Pedro | ...
```

---

## PROBLEMA 5: Cascada de ubicaciones necesita actualizarse

### Ubicación: `formulario.py` función `actualizar_provincia()` o similar

**SI EXISTE una función de cascada**, debe actualizarse para incluir DISTRITO:

**ANTES:**
```python
def actualizar_provincia():
    provincia_opts = lista_limpia(df_ubi, "PROVINCIA", "DEPARTAMENTO", dep_sel)
```

**DESPUÉS:**
```python
def actualizar_provincia():
    provincia_opts = lista_limpia(df_ubi, "PROVINCIA", "DEPARTAMENTO", dep_sel)

def actualizar_distrito():
    distrito_opts = lista_limpia(df_ubi, "DISTRITO", "PROVINCIA", prov_sel)
```

---

## CHECKLIST DE FIXES

```
FORMULARIO.PY:
✅ Agregar campo DISTRITO después de PROVINCIA
✅ Incluir DISTRITO en el diccionario de guardado
✅ Verificar que hoja "ubicaciones" tenga columna DISTRITO
✅ Prueba: Crear novo registro → Ver que DISTRITO aparece y se guarda

ASISTENCIA.PY:
✅ Usar el nuevo archivo proporcionado (v2.5.0)
✅ Incluye fix de error de tipo
✅ Incluye DISTRITO en COLUMNAS_BASE
✅ Incluye nuevas funciones de búsqueda

GOOGLE DRIVE - SHEETS:
✅ Agregar DISTRITO a "ubicaciones"
✅ Agregar DISTRITO a "Asistencia" (si no existe)
✅ Crear carpeta "Descansos_Medicos_Vacaciones"

ARCHIVOS A SUBIR A GITHUB:
✅ asistencia.py (nuevo, con todos los fixes)
✅ formulario.py (modificado, con DISTRITO agregado)
✅ auth.py (ya actualizado)
```

---

## CÓMO IMPLEMENTAR AHORA

### Opción A: Quick Fix (Recomendado)
1. ✅ Reemplaza `asistencia.py` con la versión nueva (tiene todos los fixes)
2. 🔴 Modifica `formulario.py` - Agregar 5 líneas para DISTRITO (ver arriba)
3. ✅ Verifica Google Drive tenga DISTRITO

### Opción B: Si quieres hacer todo de cero
1. Usa CAMBIOS_ASISTENCIA_DETALLADO.md
2. Aplica manualmente cada sección
3. Prueba paso a paso

---

## 🎯 ARCHIVOS LISTOS PARA SUBIR A GITHUB

```
Archivos con MISMO NOMBRE (para reemplazar sin duplicados):

1. auth.py              ✅ Listo (cambio de marca)
2. formulario.py        🔴 Listo en /outputs pero NECESITA 5 líneas agregadas para DISTRITO
3. asistencia.py        ✅ Listo (incluye TODOS los fixes)

Uso en GitHub:
$ git add auth.py formulario.py asistencia.py
$ git commit -m "v2.5.0: Cambios de marca, razones sociales, rediseño presencialidad"
```

---

## 📝 MODIFICACIÓN RÁPIDA A FORMULARIO.PY

Si tu `formulario.py` actual tiene esta estructura:

```python
# Línea ~560
provincia = st.selectbox(
    "PROVINCIA",
    provincia_options,
    key=k("provincia"),
)

# Línea ~650 (construcción del registro)
"DEPARTAMENTO": departamento,
"PROVINCIA": provincia,
"DNI": dni,
```

**Simplemente:**

1. Copia la versión de `formulario.py` que ya está en /outputs
2. Es prácticamente idéntica a la anterior
3. Solo cambió razones sociales y lógica WOW TEL
4. Ahora necesitas agregar esas 5 líneas de DISTRITO

---

## ⚠️ IMPORTANTE: NOMBRES DE ARCHIVOS

✅ **CORRECTO:**
```
auth.py
formulario.py
asistencia.py
```

❌ **INCORRECTO:**
```
auth_nuevo.py
formulario_v2.py
asistencia_2.5.0.py
```

Los archivos deben tener el **MISMO NOMBRE EXACTO** para reemplazar sin duplicar en GitHub.

---

**Documento**: FIXES_FALTANTES.md  
**Versión**: 2.5.0  
**Status**: 🔴 Lee antes de subir a GitHub
