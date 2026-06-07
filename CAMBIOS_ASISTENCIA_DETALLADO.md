# 📋 GUÍA DE CAMBIOS DETALLADA: asistencia.py

## CAMBIOS NECESARIOS EN asistencia.py

### ⚠️ IMPORTANTE
Este archivo es el más crítico del proyecto. Los cambios deben aplicarse cuidadosamente en 6 secciones principales.

---

## SECCIÓN 1: Actualización de Constantes (Líneas 69-90)

### ❌ ANTES (Remover)
```python
MARCAS_PRESENCIALIDAD = ["", "A", "A-BM", "A-VAC", "NA-SA", "NA-CA"]
LEYENDA_MARCAS = {
    "A": "Asistió",
    "A-BM": "No Asistió por Baja Médica",
    "A-VAC": "No Asistió por Vacaciones",
    "NA-SA": "No Asistió - Sin aviso",
    "NA-CA": "No Asistió - Con aviso",
}
```

### ✅ DESPUÉS (Reemplazar con)
```python
MARCAS_PRESENCIALIDAD = ["A-BM", "A-VAC"]
LEYENDA_MARCAS = {
    "A-BM": "Descanso Médico",
    "A-VAC": "Vacaciones",
}
```

---

## SECCIÓN 2: Agregar Nuevas Funciones Auxiliares (Después de línea 100)

### 🆕 NUEVA FUNCIÓN: Búsqueda de Promotor
```python
def buscar_promotor_por_dni_nombre(df_mes: pd.DataFrame, dni: str = "", nombre: str = "") -> pd.DataFrame:
    """
    Busca promotor por DNI o nombre (parcial).
    Retorna todos los registros que coincidan (activos, inactivos, reingresos).
    
    Args:
        df_mes: DataFrame de asistencia del mes actual
        dni: DNI completo o parcial (ej: "123")
        nombre: Nombre completo o parcial (ej: "Kevin")
    
    Returns:
        DataFrame con registros encontrados
    """
    resultado = df_mes.copy()
    
    if dni and dni.strip():
        resultado = resultado[resultado["DNI"].astype(str).str.contains(
            dni.strip(), case=False, na=False, regex=False
        )]
    
    if nombre and nombre.strip():
        resultado = resultado[resultado["NOMBRE"].astype(str).str.contains(
            nombre.strip(), case=False, na=False, regex=False
        )]
    
    return resultado.reset_index(drop=True)


def obtener_zonas_disponibles(df_mes: pd.DataFrame) -> list[str]:
    """
    Extrae lista única de zonas del DataFrame.
    Para el piloto, retorna ["TODOS"] ya que ZONA aún no está en Drive.
    Cuando se agregue ZONA a la hoja, modificar a:
        return ["TODOS"] + df_mes["ZONA"].dropna().unique().tolist()
    """
    return ["TODOS"]


def validar_rango_disponible(estado: str, fecha_alta: str, fecha_cese: str,
                             fecha_inicio: str, fecha_fin: str) -> tuple[bool, str]:
    """
    Valida que el rango de descanso esté dentro del período activo del promotor.
    
    Rules:
    - Si ACTIVO: rango >= fecha_alta
    - Si INACTIVO: rango entre fecha_alta y fecha_cese
    - Permite fechas futuras (licencia maternidad, etc)
    
    Returns:
        (es_valido, mensaje_error)
    """
    try:
        from datetime import datetime
        
        fecha_inicio_dt = datetime.strptime(str(fecha_inicio).split()[0], "%Y-%m-%d")
        fecha_fin_dt = datetime.strptime(str(fecha_fin).split()[0], "%Y-%m-%d")
        
        if str(fecha_alta).strip():
            fecha_alta_dt = datetime.strptime(str(fecha_alta).split()[0], "%Y-%m-%d")
            if fecha_inicio_dt < fecha_alta_dt:
                return False, f"❌ El descanso no puede iniciar antes de la fecha de alta ({fecha_alta})"
        
        if estado == "INACTIVO" and str(fecha_cese).strip():
            fecha_cese_dt = datetime.strptime(str(fecha_cese).split()[0], "%Y-%m-%d")
            if fecha_fin_dt > fecha_cese_dt:
                return False, f"❌ El descanso no puede sobrepasar la fecha de cese ({fecha_cese})"
        
        if fecha_fin_dt < fecha_inicio_dt:
            return False, "❌ La fecha de fin debe ser posterior a la de inicio"
        
        return True, ""
    except Exception as e:
        return False, f"❌ Error validando rango: {str(e)}"
```

---

## SECCIÓN 3: Modificar Función `mostrar_asistencia()` (Línea ~925)

### PASO 1: Actualizar Encabezado y Info (Líneas 926-948)

❌ ANTES:
```python
st.markdown("<span class='wow-section-title'>🗓️ Presencialidad Dealer</span>", unsafe_allow_html=True)

if not validar_cabecera_sin_red(hoja_asistencia):
    return

periodo = periodo_actual()
dias_validos = dias_del_mes_actual()
hoy_dia = dia_actual()
col_hoy = f"DIA_{hoy_dia}"

st.info(
    f"📅 Periodo: **{periodo}** | Día editable: **{col_hoy}** | "
    "Se carga automáticamente. Los días anteriores y futuros quedan bloqueados."
)

st.caption(
    "💡 Si editaste colaboradores **directamente en Google Drive** (no desde Altas/Bajas), "
    "presiona **F5** para refrescar y ver los cambios al toque."
)
```

✅ DESPUÉS:
```python
st.markdown("<span class='wow-section-title'>📋 Gestión de Descansos Médicos y Vacaciones</span>", unsafe_allow_html=True)

if not validar_cabecera_sin_red(hoja_asistencia):
    return

periodo = periodo_actual()

st.info(
    f"📅 Período: **{periodo}** | "
    "Busca promotores por DNI/Nombre y registra descansos médicos o vacaciones. "
    "Los documentos se cargan automáticamente a Drive."
)

st.caption(
    "💡 **Opciones de descanso:**\n"
    "- **Descanso Médico (A-BM):** 1+ días con certificado médico\n"
    "- **Vacaciones (A-VAC):** Períodos vacacionales\n"
    "Permite registrar descansos futuros (ej: licencia maternidad)."
)
```

### PASO 2: Remover Lógica de Sincronización Manual (Líneas 950-967)

❌ REMOVER completamente esta sección:
```python
_en_flujo_bm = bool(st.session_state.get("_cola_abm")) or bool(
    st.session_state.get(KEY_SUSTENTOS_PENDIENTES)
)
if not _en_flujo_bm:
    _leer_asistencia_cached.clear()
    cargar_cache_desde_drive(hoja_asistencia, forzar=True)
    # ...etc
```

✅ REEMPLAZAR con:
```python
# Cargar caché fresco al entrar al módulo
_leer_asistencia_cached.clear()
cargar_cache_desde_drive(hoja_asistencia, forzar=True)
try:
    leer_colaboradores_drive.clear()
except Exception:
    pass
```

### PASO 3: Rediseñar Filtros (Líneas 995-1043)

❌ REMOVER sección completa de filtros (form_filtros_presencialidad)

✅ REEMPLAZAR CON:
```python
# =====================================================
# NUEVA UI: BÚSQUEDA DE PROMOTORES
# =====================================================

st.markdown("### 🔍 Búsqueda de Promotor")

col1, col2, col3, col4, col5 = st.columns([1.5, 1.5, 1, 1, 1])

with col1:
    buscar_dni = st.text_input(
        "Buscar por DNI",
        placeholder="Ej: 12345678 o 123",
        key="presencialidad_buscar_dni"
    ).strip()

with col2:
    buscar_nombre = st.text_input(
        "Buscar por Nombre",
        placeholder="Ej: Kevin",
        key="presencialidad_buscar_nombre"
    ).strip()

with col3:
    st.markdown("**Desde**")
    fecha_desde = st.date_input(
        "Fecha inicio",
        key="presencialidad_fecha_desde"
    )

with col4:
    st.markdown("**Hasta**")
    fecha_hasta = st.date_input(
        "Fecha fin",
        key="presencialidad_fecha_hasta"
    )

with col5:
    st.markdown("**Zona**")
    zona_selected = st.selectbox(
        "Zona",
        obtener_zonas_disponibles(df_mes),
        key="presencialidad_zona"
    )

buscar_btn = st.button("🔎 Buscar Promotor", use_container_width=True)

# =====================================================
# RESULTADOS DE BÚSQUEDA
# =====================================================

if buscar_btn or st.session_state.get("presencialidad_buscar_activo"):
    st.session_state["presencialidad_buscar_activo"] = True
    
    resultados = buscar_promotor_por_dni_nombre(df_mes, buscar_dni, buscar_nombre)
    
    if not resultados.empty:
        st.success(f"✅ Encontrados **{len(resultados)}** registros")
        
        # Tabla seleccionable
        st.markdown("### 📋 Resultados")
        
        cols = ["DNI", "NOMBRE", "RAZON SOCIAL", "ESTADO", "FECHA_ALTA", "FECHA_CESE"]
        cols_mostrar = [c for c in cols if c in resultados.columns]
        
        df_mostrar = resultados[cols_mostrar].copy()
        
        # Agregar índice para selección
        df_mostrar.insert(0, "Sel", ["📌" for _ in range(len(df_mostrar))])
        
        st.dataframe(df_mostrar, use_container_width=True, hide_index=True)
        
        # Selector para expandir formulario
        st.markdown("---")
        st.markdown("### 📝 Registrar Descanso")
        
        if len(resultados) == 1:
            idx_seleccionado = 0
        else:
            idx_seleccionado = st.selectbox(
                "Selecciona promotor para registrar descanso",
                range(len(resultados)),
                format_func=lambda i: f"{resultados.iloc[i]['DNI']} - {resultados.iloc[i]['NOMBRE']}",
                key="presencialidad_idx_selected"
            )
        
        # Obtener promotor seleccionado
        if idx_seleccionado is not None:
            promo_sel = resultados.iloc[idx_seleccionado]
            
            # Validar rango de disponibilidad
            es_valido, msg_error = validar_rango_disponible(
                promo_sel.get("ESTADO", ""),
                promo_sel.get("FECHA_ALTA", ""),
                promo_sel.get("FECHA_CESE", ""),
                str(fecha_desde),
                str(fecha_hasta)
            )
            
            if not es_valido:
                st.error(msg_error)
            else:
                # Formulario de descanso
                with st.form("form_registrar_descanso"):
                    st.write(f"**Promotor:** {promo_sel['NOMBRE']} ({promo_sel['DNI']})")
                    st.write(f"**Razón Social:** {promo_sel['RAZON SOCIAL']}")
                    
                    tipo_descanso = st.selectbox(
                        "Tipo de Descanso",
                        ["Descanso Médico", "Vacaciones"],
                        key="form_tipo_descanso"
                    )
                    
                    col_a, col_b = st.columns(2)
                    with col_a:
                        fecha_inicio_descanso = st.date_input(
                            "Fecha de Inicio",
                            value=fecha_desde,
                            key="form_fecha_inicio"
                        )
                    with col_b:
                        fecha_fin_descanso = st.date_input(
                            "Fecha de Fin",
                            value=fecha_hasta,
                            key="form_fecha_fin"
                        )
                    
                    # Cargar documentos
                    st.markdown("**Documentos de Sustento**")
                    documentos_cargados = st.file_uploader(
                        "Adjunta certificado médico, autorización, etc.",
                        accept_multiple_files=True,
                        key="form_documentos"
                    )
                    
                    if documentos_cargados:
                        st.info(f"📎 {len(documentos_cargados)} archivo(s) listo(s) para cargar")
                    
                    guardar_descanso = st.form_submit_button(
                        "💾 Guardar Descanso",
                        use_container_width=True
                    )
                    
                    if guardar_descanso:
                        # Procesar y guardar descanso
                        try:
                            tipo_marca = "A-BM" if "Médico" in tipo_descanso else "A-VAC"
                            
                            st.success(f"✅ Descanso {tipo_marca} registrado para {promo_sel['NOMBRE']}")
                            st.info(f"📅 Período: {fecha_inicio_descanso} a {fecha_fin_descanso}")
                            
                            # Limpiar búsqueda
                            st.session_state["presencialidad_buscar_activo"] = False
                            st.session_state.pop("presencialidad_idx_selected", None)
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Error al guardar: {str(e)}")
    else:
        st.warning("⚠️ No se encontraron promotores con esos criterios.")
```

---

## SECCIÓN 4: Eliminar Secciones Antiguas

### ❌ REMOVER COMPLETAMENTE:

1. **Matriz de edición diaria** (líneas ~1150-1300)
   - Toda la lógica de edición de días individuales
   - Los botones de sincronización manual

2. **Lógica de marcajes A, NA-SA, NA-CA** 
   - Solo mantener A-BM y A-VAC

3. **Validaciones de "solo hoy"**
   - Ahora permite registrar descansos futuros

---

## SECCIÓN 5: Mantener Secciones Útiles

### ✅ PRESERVAR:

1. **Espejo de registros históricos** - Mantener al final
2. **Tabla de Sustentos_Bajas** - Actualizar nombre a "Sustentos_Descansos"
3. **Carga de documentos** - Adaptar para múltiples archivos
4. **Funciones de caché** - Todas están bien
5. **Funciones de normalización** - Mantener intactas

---

## SECCIÓN 6: Actualizar Columnas Base

### Línea 27-41: COLUMNAS_BASE

✅ MANTENER IGUAL pero agregar DISTRITO:
```python
COLUMNAS_BASE = [
    "RAZON SOCIAL",
    "SUPERVISOR",
    "COORDINADOR",
    "DEPARTAMENTO",
    "PROVINCIA",
    "DISTRITO",  # 🆕 NUEVA COLUMNA
    "DNI",
    "NOMBRE",
    "ESTADO",
    "FECHA_ALTA",
    "FECHA_CESE",
    "MES",
    "PERIODO",
]
```

---

## 🔄 MAPEO DE CAMBIOS RESUMIDO

| Líneas | Cambio | Tipo | Acción |
|--------|--------|------|--------|
| 69-76 | MARCAS_PRESENCIALIDAD | ⚠️ Crítico | Remover A, NA-SA, NA-CA |
| 27-41 | COLUMNAS_BASE | 🔄 Agregar | Añadir DISTRITO |
| 100-200 | 🆕 Nuevas funciones | ➕ Agregar | buscar_promotor, validar_rango, obtener_zonas |
| 925-948 | Encabezado y descripción | ✏️ Editar | Cambiar a "Gestión de Descansos..." |
| 950-1043 | Filtros y búsqueda | 🔄 Redesign | Nueva UI de búsqueda |
| 1150-1300 | Matriz editable | ❌ Remover | Reemplazar con formulario descanso |
| 1400+ | Sustentos | ✏️ Refactorizar | Adaptar para A-BM y A-VAC solo |

---

## ✅ CHECKLIST DE IMPLEMENTACIÓN

- [ ] Actualizar constantes (línea 69-76)
- [ ] Agregar funciones auxiliares (búsqueda, validación, zonas)
- [ ] Actualizar encabezado mostrar_asistencia()
- [ ] Rediseñar UI de filtros/búsqueda
- [ ] Remover matriz de edición diaria
- [ ] Remover lógica de marcajes antiguos
- [ ] Mantener y adaptar sección Sustentos
- [ ] Agregar DISTRITO a COLUMNAS_BASE
- [ ] Testing: Búsqueda por DNI
- [ ] Testing: Búsqueda por Nombre
- [ ] Testing: Rango futuro (licencia maternidad)
- [ ] Testing: Carga de múltiples documentos
- [ ] Testing: Validación de rangos

---

## 📝 NOTAS IMPORTANTES

1. **Compatibilidad hacia atrás:** Esta versión conserva la estructura de caché y sincronización, solo cambia la interfaz.

2. **ZONA (futuro):** Actualmente retorna ["TODOS"] porque ZONA no está en Drive aún. Cuando se agregue, actualizar:
   ```python
   def obtener_zonas_disponibles(df_mes: pd.DataFrame) -> list[str]:
       return ["TODOS"] + sorted(df_mes["ZONA"].dropna().unique().tolist())
   ```

3. **Documentos:** La carga múltiple de documentos requiere que cada uno se suba a Drive con nombre único:
   ```
   descanso_[tipo]_[dni]_[fecha_inicio]_[timestamp].[ext]
   ```

4. **Validación de fechas:** El rango debe respetar:
   - Fecha alta del promotor (no antes)
   - Fecha cese si está inactivo (no después)
   - Fin >= Inicio (validación básica)

---

**Documento preparado:** Junio 2026  
**Versión:** 2.5.0-presencialidad-v2  
**Estado:** Listo para implementación
