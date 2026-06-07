# ⚡ REFERENCIA RÁPIDA - CAMBIOS POR ARCHIVO

## 📄 auth.py (COMPLETAMENTE REEMPLAZADO)

### Cambios Clave:
```diff
- <div class="wow-login-eyebrow">✦ Portal de Vendedores</div>
+ <div class="wow-login-eyebrow">✦ VENTAS DOOR TO DOOR</div>

- <h1>Gestiona tu fuerza de ventas<br/><span class="accent">con claridad</span>.</h1>
- <p>Altas, bajas, asistencia y jerarquía en un solo lugar. Toda la operación de WOW D2D...

+ <h1>Gestiona tu fuerza de ventas<br/><span class="accent">con claridad</span>.</h1>
+ <p>Actualización de jerarquía: altas, bajas, descansos médicos y vacaciones...

- <div class="feat"><div class="ico">👥</div> Altas y bajas</div>
- <div class="feat"><div class="ico">🗓️</div> Asistencia diaria</div>
- <div class="feat"><div class="ico">📋</div> Jerarquía</div>
+ <div class="feat"><div class="ico">👥</div> Altas y bajas</div>
+ <div class="feat"><div class="ico">🏥</div> Descansos médicos</div>
+ <div class="feat"><div class="ico">✈️</div> Vacaciones</div>

- <div class="footer">© 2026 WOW Perú · v2.4.0</div>
+ <div class="footer">© 2026 WAP Perú · v2.5.0</div>
```

**Status:** ✅ LISTO - Usar archivo completo proporcionado

---

## 📄 formulario.py (CAMBIOS ESPECÍFICOS)

### Cambio 1: Razones Sociales (Línea ~450)

```python
# ❌ ANTES (8 razones):
razones = [
    "MALUTECH S.A.C.",
    "2CONNECT SERVICES S.A.C.",
    "INTERCONEXION 360 SAC",
    "NOGALES HIGH SAC",
    "MULTIPLE FORCE SAC",
    "KONECTA SAC",
    "WOW TEL",
]

# ✅ DESPUÉS (4 razones):
razones = [
    "INTERCONEXION 360 SAC",
    "MULTIPLE FORCE SAC",
    "NOGALES HIGH SAC",
    "GRUPO CREED SAC",
]
```

### Cambio 2: Descripción de Canales (Línea ~485)

```python
# ❌ ANTES:
st.caption("WOW TEL se gestiona como VENTAS DIRECTAS. Los demás socios...")

# ✅ DESPUÉS:
st.caption("Todos los socios se gestionan como VENTAS INDIRECTAS. Se mantiene la lógica original de cargos Dealer.")
```

### Cambio 3: Lógica de Canal/Subcanal (Línea ~507-544)

```python
# ❌ ANTES: Condicional if razon_norm == "WOW TEL": ... elif ...
# ✅ DESPUÉS: Directamente: if razon_norm:

if razon_norm:
    canal = "VENTAS INDIRECTAS"
    st.text_input("CANAL", value=canal, disabled=True, key=k("canal_indirecto_fijo"))
    subcanal = st.selectbox(
        "SUB CANAL",
        ["VENTAS INDIRECTAS", "OUTBOUND"],
        index=0,
        key=k("subcanal_indirecto"),
    )
    tipo_gestion = "CAMPO"
else:
    # ... código para cuando no hay razón seleccionada
```

**Status:** ✅ LISTO - Usar archivo completo proporcionado

---

## 📄 asistencia.py (CAMBIOS COMPLEJOS - 6 SECCIONES)

### 1️⃣ CONSTANTES (Línea ~69-76)

```python
# ❌ ANTES:
MARCAS_PRESENCIALIDAD = ["", "A", "A-BM", "A-VAC", "NA-SA", "NA-CA"]
LEYENDA_MARCAS = {
    "A": "Asistió",
    "A-BM": "No Asistió por Baja Médica",
    "A-VAC": "No Asistió por Vacaciones",
    "NA-SA": "No Asistió - Sin aviso",
    "NA-CA": "No Asistió - Con aviso",
}

# ✅ DESPUÉS:
MARCAS_PRESENCIALIDAD = ["A-BM", "A-VAC"]
LEYENDA_MARCAS = {
    "A-BM": "Descanso Médico",
    "A-VAC": "Vacaciones",
}
```

### 2️⃣ COLUMNAS_BASE (Línea ~27-41)

```python
# ❌ ANTES:
COLUMNAS_BASE = [
    "RAZON SOCIAL",
    "SUPERVISOR",
    "COORDINADOR",
    "DEPARTAMENTO",
    "PROVINCIA",
    "DNI",
    # ...rest
]

# ✅ DESPUÉS:
COLUMNAS_BASE = [
    "RAZON SOCIAL",
    "SUPERVISOR",
    "COORDINADOR",
    "DEPARTAMENTO",
    "PROVINCIA",
    "DISTRITO",  # 🆕 NUEVA
    "DNI",
    # ...rest
]
```

### 3️⃣ NUEVAS FUNCIONES AUXILIARES (Después de línea ~100)

**Agregar 3 funciones nuevas:**
1. `buscar_promotor_por_dni_nombre()` - Búsqueda flexible
2. `obtener_zonas_disponibles()` - Lista de zonas
3. `validar_rango_disponible()` - Validación de fechas

*(Ver CAMBIOS_ASISTENCIA_DETALLADO.md, SECCIÓN 2 para código completo)*

### 4️⃣ ENCABEZADO mostrar_asistencia() (Línea ~926-948)

```python
# ❌ ANTES:
st.markdown("<span class='wow-section-title'>🗓️ Presencialidad Dealer</span>", ...)
# ...info sobre "Día editable: DIA_X"
# ...caption sobre editar en Google Drive

# ✅ DESPUÉS:
st.markdown("<span class='wow-section-title'>📋 Gestión de Descansos Médicos y Vacaciones</span>", ...)
# ...info sobre "Busca promotores..."
# ...caption sobre opciones de descanso
```

### 5️⃣ CARGAR CACHÉ (Línea ~950-967)

```python
# ❌ ANTES: Lógica compleja de _en_flujo_bm y sincronización condicional

# ✅ DESPUÉS: Simple y directo
_leer_asistencia_cached.clear()
cargar_cache_desde_drive(hoja_asistencia, forzar=True)
try:
    leer_colaboradores_drive.clear()
except Exception:
    pass
```

### 6️⃣ FILTROS → BÚSQUEDA (Línea ~995-1043)

```python
# ❌ ANTES: 6 selectboxes (Razón Social, Supervisor, Coordinador, Departamento, Provincia, Estado)
with st.form("form_filtros_presencialidad"):
    f1, f2, f3, f4, f5, f6 = st.columns(6)
    # ...selectboxes...

# ✅ DESPUÉS: Nueva UI de búsqueda
st.markdown("### 🔍 Búsqueda de Promotor")
col1, col2, col3, col4, col5 = st.columns([1.5, 1.5, 1, 1, 1])

with col1:
    buscar_dni = st.text_input("Buscar por DNI", ...)
with col2:
    buscar_nombre = st.text_input("Buscar por Nombre", ...)
with col3:
    fecha_desde = st.date_input("Desde", ...)
with col4:
    fecha_hasta = st.date_input("Hasta", ...)
with col5:
    zona_selected = st.selectbox("Zona", obtener_zonas_disponibles(df_mes))

buscar_btn = st.button("🔎 Buscar Promotor", ...)

# ... Mostrar resultados con tabla seleccionable
# ... Formulario de registro de descanso con file_uploader
```

### 7️⃣ ELIMINAR (Remover completamente)

```python
# ❌ REMOVER:
- Función: puede_editar_hoy()
- Función: marcar_presencia()
- Sección: "Editor de Presencialidad" (matriz de días)
- Toda lógica de validación "solo hoy"
- Botones de sincronización manual
```

### 8️⃣ MANTENER

```python
# ✅ MANTENER INTACTOS:
- Todas las funciones de caché (leer_asistencia_drive, etc)
- Todas las funciones de normalización
- Sección de Sustentos (adaptar solo si es necesario)
- Funciones de utilidad (normalizar_dni, etc)
```

**Status:** ⚠️ MANUAL - Ver CAMBIOS_ASISTENCIA_DETALLADO.md para código completo

---

## 📄 sheets.py (VERIFICAR, NO CAMBIAR)

### ✅ NO REQUIERE CAMBIOS

Solo verificar que exista la función `subir_archivo_drive()` para carga de documentos.

---

## 📄 app_maestra_vendedores.py (OPCIONAL)

### Cambio Opcional (Línea ~34)

```python
# ❌ ANTES:
page_title="WOW D2D | Portal Vendedores"

# ✅ DESPUÉS:
page_title="WAP VENTAS D2D | Portal"
```

**Status:** ✅ OPCIONAL - Cambio cosmético

---

## 🗂️ ARCHIVOS GOOGLE SHEETS (VERIFICAR)

### Hoja: "colaboradores"
- [ ] Tiene todas las columnas esperadas
- [ ] DNI, NOMBRE, RAZON SOCIAL, DEPARTAMENTO, PROVINCIA presentes

### Hoja: "ubicaciones"
- [ ] DEPARTAMENTO
- [ ] PROVINCIA
- [ ] DISTRITO (verificar que existe)
- [ ] SUPERVISOR A CARGO FINAL
- [ ] COORDINADOR FINAL

### Hoja: "Asistencia"
- [ ] Columnas base: RAZON SOCIAL, SUPERVISOR, COORDINADOR, DEPARTAMENTO, PROVINCIA, **DISTRITO**, DNI, NOMBRE, ESTADO, FECHA_ALTA, FECHA_CESE, MES, PERIODO
- [ ] Columnas de días: DIA_1 a DIA_31
- [ ] ✅ Crear columna DISTRITO si no existe

### Nueva Carpeta Drive (crear si no existe)
- [ ] `Descansos_Medicos_Vacaciones/` - Para almacenar documentos cargados

---

## 📋 CHECKLIST DE CAMBIOS

### auth.py
- [ ] ✅ Reemplazar archivo completo (proporcionado)

### formulario.py
- [ ] ✅ Reemplazar archivo completo (proporcionado)
- [ ] ✅ Verificar razones sociales en dropdown
- [ ] ✅ Verificar lógica canal = VENTAS INDIRECTAS

### asistencia.py
- [ ] Actualizar MARCAS_PRESENCIALIDAD
- [ ] Actualizar COLUMNAS_BASE (agregar DISTRITO)
- [ ] Agregar 3 nuevas funciones auxiliares
- [ ] Actualizar encabezado mostrar_asistencia()
- [ ] Simplificar carga de caché
- [ ] Rediseñar sección de filtros → búsqueda
- [ ] Remover matriz editable de días
- [ ] Remover lógica antigua de "solo hoy"
- [ ] Agregar formulario de registro de descanso
- [ ] Agregar validación de rango de fechas

### sheets.py
- [ ] ✅ Verificar función subir_archivo_drive()

### app_maestra_vendedores.py
- [ ] 🟡 Opcional: Cambiar page_title

### Google Drive
- [ ] Agregar columna DISTRITO a "ubicaciones"
- [ ] Agregar columna DISTRITO a "Asistencia"
- [ ] Crear carpeta "Descansos_Medicos_Vacaciones"

---

## 🚀 ORDEN DE IMPLEMENTACIÓN RECOMENDADO

```
1. auth.py         ✅ (5 min)   - Cambio de marca
2. formulario.py   ✅ (5 min)   - Razones sociales
3. sheets.py       🟡 (15 min)  - Verificar, agregar DISTRITO
4. asistencia.py   ⚠️ (180 min) - Cambios complejos
5. Testing         🧪 (60 min)  - Validar todo
6. Merge & Deploy  📦 (15 min)  - Subir a producción
```

**Tiempo Total Estimado: ~280 minutos (4.5-5 horas)**

---

## 🔗 REFERENCIAS RÁPIDAS

- **GUIA_IMPLEMENTACION_COMPLETA.md** - Paso a paso detallado
- **CAMBIOS_ASISTENCIA_DETALLADO.md** - Código completo para asistencia.py
- **RESUMEN_CAMBIOS_REQUERIDOS.md** - Visión general del proyecto

---

*Última actualización: 7 de Junio de 2026*
