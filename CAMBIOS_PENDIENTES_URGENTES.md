# 🔴 CAMBIOS PENDIENTES URGENTES

## 1️⃣ REMOVER "WOW EMPRESAS" del Header/Logo

### Ubicación: `auth.py` línea ~50

**BUSCA:**
```html
<div class="brand"><img src="https://raw.githubusercontent.com/leocorbur/st_apps/refs/heads/main/images/logo_horizontal_blanco.png" alt="WAP D2D" /></div>
```

**REEMPLAZA CON:**
```html
<!-- Logo removido para piloto -->
```

O si quieres mantener logo pero cambiar alt:
```html
<div class="brand"><img src="https://raw.githubusercontent.com/leocorbur/st_apps/refs/heads/main/images/logo_horizontal_blanco.png" alt="WAP" /></div>
```

---

## 2️⃣ REMOVER Módulos "Alta" y "Bajas" del Sidebar

### Ubicación: `app_maestra_vendedores.py` línea ~84-93

**BUSCA:**
```python
if rol == "backoffice":
    opciones_menu = ["Alta", "Bajas", "Presencialidad Dealer"]
elif rol == "dealer":
    opciones_menu = ["Alta", "Bajas", "Presencialidad Dealer"]
```

**REEMPLAZA CON (solo Presencialidad por ahora):**
```python
if rol == "backoffice":
    opciones_menu = ["Presencialidad Dealer"]  # Solo presencialidad en piloto
elif rol == "dealer":
    opciones_menu = ["Presencialidad Dealer"]  # Solo presencialidad en piloto
```

---

## 3️⃣ AGREGAR CAMPO DISTRITO A LA BÚSQUEDA

### Ubicación: `asistencia.py` función `mostrar_asistencia()`

**PROBLEMA:** El campo DISTRITO no aparece en la búsqueda

**SOLUCIÓN:** Agregar input de DISTRITO en la búsqueda (línea ~1020):

```python
# Después de zona_selected, AGREGA:

with col_distrito:
    st.markdown("**Distrito**")
    distrito_selected = st.text_input(
        "Filtrar por Distrito",
        placeholder="Ej: LIMA, CUSCO",
        key="presencialidad_distrito"
    ).strip()
```

**Y actualizar la búsqueda:**
```python
resultados = buscar_promotor_por_dni_nombre(df_mes, buscar_dni, buscar_nombre)

# Agregar después:
if distrito_selected and "DISTRITO" in resultados.columns:
    resultados = resultados[resultados["DISTRITO"].astype(str).str.contains(
        distrito_selected, case=False, na=False
    )]
```

---

## 4️⃣ CREAR COLUMNA DISTRITO EN GOOGLE DRIVE

### Hoja: "ubicaciones"

**NOMBRE DE COLUMNA:** `DISTRITO` (EXACTO - mayúsculas)

**POSICIÓN:** Después de PROVINCIA

**ORDEN RECOMENDADO:**
```
DEPARTAMENTO | PROVINCIA | DISTRITO | SUPERVISOR A CARGO FINAL | ...
LIMA         | LIMA      | LIMA     | Juan                     | ...
LIMA         | LIMA      | SAN ISIDRO | Juan                    | ...
CUSCO        | CUSCO     | CUSCO    | Pedro                    | ...
```

**VALORES EJEMPLOS:**
- LIMA
- SAN ISIDRO
- MIRAFLORES
- CUSCO
- AREQUIPA
- TRUJILLO

### Hoja: "Asistencia"

**AGREGAR COLUMNA:** `DISTRITO` (después de PROVINCIA)

**NO NECESITA DATOS** (se llena automáticamente desde "ubicaciones")

---

## 5️⃣ PROBLEMA: 2 REGISTROS IGUALES

**CAUSA:** Andrea Jeniffer Flores Carhuas aparece 2 veces con DNI 47722887

**SOLUCIONES:**
1. En Google Drive (hoja "colaboradores"): Eliminar el registro duplicado
2. O si son dos altas diferentes (una se dio de baja y otra alta): Verificar FECHA_CESE diferente

**VERIFICAR EN DRIVE:**
```
¿Tiene FECHA_CESE diferente?
- Si no → Eliminar duplicado
- Si sí → Es un reingreso (correcto, ambos deben aparecer)
```

---

## 6️⃣ AGREGAR CONFIRMACIÓN DE CARGA DE DOCUMENTOS

### Ubicación: `asistencia.py` función `mostrar_asistencia()` línea ~1100

**BUSCA:**
```python
if guardar_descanso:
    try:
        tipo_marca = "A-BM" if "Médico" in tipo_descanso else "A-VAC"
        
        st.success(f"✅ Descanso {tipo_marca} registrado para {promo_sel['NOMBRE']}")
        st.info(f"📅 Período: {fecha_inicio_descanso} a {fecha_fin_descanso}")
        
        if documentos_cargados:
            st.info(f"📎 {len(documentos_cargados)} documento(s) cargado(s)")
```

**REEMPLAZA CON:**
```python
if guardar_descanso:
    try:
        tipo_marca = "A-BM" if "Médico" in tipo_descanso else "A-VAC"
        
        # GUARDAR EN DRIVE
        docs_guardados = 0
        if documentos_cargados:
            for doc in documentos_cargados:
                try:
                    nombre_doc = f"descanso_{tipo_marca}_{promo_sel['DNI']}_{fecha_inicio_descanso}_{doc.name}"
                    link = subir_archivo_drive(nombre_doc, doc.getbuffer(), doc.type)
                    docs_guardados += 1
                    st.success(f"✅ Documento cargado: {doc.name}")
                except Exception as e:
                    st.error(f"❌ Error cargando {doc.name}: {str(e)}")
        
        # MENSAJE DE CONFIRMACIÓN COMPLETO
        st.success(f"✅ DESCANSO REGISTRADO")
        st.info(f"""
        **Detalles:**
        - Promotor: {promo_sel['NOMBRE']} ({promo_sel['DNI']})
        - Tipo: {tipo_marca}
        - Período: {fecha_inicio_descanso} → {fecha_fin_descanso}
        - Documentos: {docs_guardados}/{len(documentos_cargados) if documentos_cargados else 0} cargados
        - Razón Social: {promo_sel['RAZON SOCIAL']}
        
        Los datos se reflejarán en Google Drive en la hoja "Asistencia".
        """)
```

---

## 7️⃣ CÓMO SE REFLEJA EN DRIVE

### Flujo de datos:

```
Aplicación Streamlit
    ↓
1. Registro de descanso (DNI, NOMBRE, TIPO, FECHAS)
    ↓
2. Guardar en hoja "Asistencia" (filas con TIPO_MARCA = A-BM o A-VAC)
    ↓
3. Guardar documentos en:
   📁 "Descansos_Medicos_Vacaciones/" (carpeta en Drive)
    ↓
4. Guardar metadatos en hoja "Sustentos_Descansos" (nueva tabla)
```

### Columnas en hoja "Asistencia":

Para el rango **01/06/2026 a 05/06/2026**, se marca:
```
DIA_1  DIA_2  DIA_3  DIA_4  DIA_5  DIA_6  ...
A-BM   A-BM   A-BM   A-BM   A-BM   [vacío] ...
```

No se marca POR DÍA individualmente. Se marca el RANGO completo.

---

## 8️⃣ ¿SE MARCA POR DÍA O POR RANGO?

**RESPUESTA: POR RANGO**

Ejemplo:
- Descanso Médico: 01/06/2026 - 05/06/2026
- Se marca: DIA_1, DIA_2, DIA_3, DIA_4, DIA_5 = A-BM
- NO se marca individualmente por día

### Código que hace esto:

En `asistencia.py`, función que registra el descanso debe iterar:

```python
fecha_inicio = datetime.strptime(str(fecha_inicio_descanso), "%Y-%m-%d")
fecha_fin = datetime.strptime(str(fecha_fin_descanso), "%Y-%m-%d")

dias_a_marcar = []
fecha_actual = fecha_inicio
while fecha_actual <= fecha_fin:
    dia_num = fecha_actual.day
    dias_a_marcar.append(f"DIA_{dia_num}")
    fecha_actual += timedelta(days=1)

# Marcar todos los días con A-BM o A-VAC
for dia_col in dias_a_marcar:
    if dia_col in headers:
        # Guardar en Drive el valor A-BM o A-VAC
```

---

## 📋 CHECKLIST DE CAMBIOS

```
ANTES DE HACER NADA:
[ ] Eliminar duplicados en Drive (si no son reingresos)
[ ] Crear columna DISTRITO en "ubicaciones" (después de PROVINCIA)
[ ] Crear columna DISTRITO en "Asistencia"
[ ] Crear carpeta "Descansos_Medicos_Vacaciones" en Drive

CÓDIGO - app_maestra_vendedores.py:
[ ] Remover "Alta" y "Bajas" del sidebar (solo dejar "Presencialidad Dealer")

CÓDIGO - auth.py:
[ ] Remover o cambiar logo/marca "WOW EMPRESAS"

CÓDIGO - asistencia.py:
[ ] Agregar campo DISTRITO a la búsqueda
[ ] Agregar mensajes de confirmación de carga de documentos
[ ] Implementar función para marcar rango de días (no día individual)
```

---

**Prioridad**: 🔴 URGENTE - Estos cambios son críticos para el piloto

**Tiempo estimado**: 2-3 horas

**Documento**: CAMBIOS_PENDIENTES_URGENTES.md  
**Versión**: 2.5.0-presencialidad-v2
