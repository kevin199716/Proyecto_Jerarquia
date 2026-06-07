# 🚀 GUÍA DE IMPLEMENTACIÓN - Proyecto WAP VENTAS DOOR TO DOOR

## Fecha: Junio 7, 2026
## Versión: 2.5.0-presencialidad-v2 (Piloto)

---

## 📦 ARCHIVOS ENTREGADOS

```
✅ auth.py                           (LISTO - Cambio de marca)
✅ formulario.py                     (LISTO - Razones sociales simplificadas)
📋 CAMBIOS_ASISTENCIA_DETALLADO.md  (GUÍA - Paso a paso para asistencia.py)
📋 RESUMEN_CAMBIOS_REQUERIDOS.md    (RESUMEN - Visión general)
```

---

## 🎯 FLUJO DE IMPLEMENTACIÓN RECOMENDADO

### FASE 1: Cambios Simples (30 minutos)

#### 1️⃣ Reemplazar `auth.py`
```bash
# En tu repositorio GitHub:
git pull origin develop
cp auth.py tu_repo/auth.py
git add auth.py
git commit -m "feat: cambio de marca a WAP VENTAS DOOR TO DOOR v2.5.0"
```

**Validación:**
- [ ] La página de login muestra "✦ VENTAS DOOR TO DOOR"
- [ ] El texto describe "Actualización de jerarquía: altas, bajas, descansos médicos y vacaciones"
- [ ] Los íconos en features son: 👥 Altas y bajas, 🏥 Descansos médicos, ✈️ Vacaciones

---

#### 2️⃣ Reemplazar `formulario.py`
```bash
cp formulario.py tu_repo/formulario.py
git add formulario.py
git commit -m "feat: actualizar dropdown razones sociales a 4 socios piloto"
```

**Validación:**
- [ ] Dropdown RAZÓN SOCIAL solo muestra:
  - INTERCONEXION 360 SAC
  - MULTIPLE FORCE SAC
  - NOGALES HIGH SAC
  - GRUPO CREED SAC
- [ ] Remover WOW TEL, MALUTECH, 2CONNECT, KONECTA
- [ ] Canal es siempre VENTAS INDIRECTAS
- [ ] No hay lógica especial para ningún socio

---

### FASE 2: Cambio Complejo - asistencia.py (4-6 horas)

#### ⚠️ PASO 0: Crear Rama de Desarrollo
```bash
git checkout -b feature/presencialidad-v2
```

#### PASO 1: Actualizar Constantes (10 minutos)

Abre `asistencia.py` y busca línea ~69:

**ANTES:**
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

**DESPUÉS:**
```python
MARCAS_PRESENCIALIDAD = ["A-BM", "A-VAC"]
LEYENDA_MARCAS = {
    "A-BM": "Descanso Médico",
    "A-VAC": "Vacaciones",
}
```

---

#### PASO 2: Agregar DISTRITO a COLUMNAS_BASE (5 minutos)

Busca línea ~27:

**ANTES:**
```python
COLUMNAS_BASE = [
    "RAZON SOCIAL",
    "SUPERVISOR",
    "COORDINADOR",
    "DEPARTAMENTO",
    "PROVINCIA",
    "DNI",
    ...
]
```

**DESPUÉS:**
```python
COLUMNAS_BASE = [
    "RAZON SOCIAL",
    "SUPERVISOR",
    "COORDINADOR",
    "DEPARTAMENTO",
    "PROVINCIA",
    "DISTRITO",  # 🆕
    "DNI",
    ...
]
```

---

#### PASO 3: Agregar Nuevas Funciones Auxiliares (30 minutos)

Busca línea ~100 (después de `normalizar_columnas()`) e inserta:

```python
# =====================================================
# BÚSQUEDA Y VALIDACIÓN - v2.5.0
# =====================================================

def buscar_promotor_por_dni_nombre(df_mes: pd.DataFrame, dni: str = "", nombre: str = "") -> pd.DataFrame:
    """
    Busca promotor por DNI o nombre (búsqueda parcial).
    Retorna todos los registros que coincidan.
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
    Retorna lista de zonas. Para piloto retorna ["TODOS"].
    Cuando ZONA se agregue a Drive, cambiar a:
        return ["TODOS"] + sorted(df_mes["ZONA"].dropna().unique().tolist())
    """
    return ["TODOS"]


def validar_rango_disponible(estado: str, fecha_alta: str, fecha_cese: str,
                             fecha_inicio: str, fecha_fin: str) -> tuple[bool, str]:
    """
    Valida que el rango de descanso esté dentro del período activo del promotor.
    
    Reglas:
    - Si ACTIVO: rango >= fecha_alta
    - Si INACTIVO: rango entre fecha_alta y fecha_cese
    - Permite fechas futuras (licencia maternidad 90 días, etc)
    
    Retorna: (es_valido, mensaje_error)
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

#### PASO 4: Rediseñar función `mostrar_asistencia()` (2-3 horas)

Busca línea ~925. Esta es la función principal. Cambios:

**4.1 - Encabezado (línea ~926-948):**

Reemplazar:
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

Con:
```python
st.markdown("<span class='wow-section-title'>📋 Gestión de Descansos Médicos y Vacaciones</span>", unsafe_allow_html=True)

if not validar_cabecera_sin_red(hoja_asistencia):
    return

periodo = periodo_actual()

st.info(
    f"📅 Período: **{periodo}** | "
    "Busca promotores y registra descansos médicos o vacaciones. "
    "Los documentos se cargan automáticamente a Drive."
)

st.caption(
    "💡 **Opciones de descanso:**\n"
    "- **Descanso Médico (A-BM):** Con certificado médico\n"
    "- **Vacaciones (A-VAC):** Períodos vacacionales\n"
    "Permite registrar descansos futuros (ej: licencia maternidad)."
)
```

**4.2 - Cargar caché (línea ~950-967):**

Remover toda esta sección de sincronización compleja y reemplazar con:
```python
# Cargar caché fresco al entrar al módulo
_leer_asistencia_cached.clear()
cargar_cache_desde_drive(hoja_asistencia, forzar=True)
try:
    leer_colaboradores_drive.clear()
except Exception:
    pass
```

**4.3 - UI de Búsqueda (línea ~995 en adelante):**

Remover completamente el `with st.form("form_filtros_presencialidad"):` con todos sus filtros antiguos.

Reemplazar con la nueva UI de búsqueda (ver CAMBIOS_ASISTENCIA_DETALLADO.md, SECCIÓN 3, PASO 2).

---

#### PASO 5: Remover Secciones Antiguas (1 hora)

**Buscar y remover:**

1. **Matriz editable de días** - Toda la sección que tenga:
   ```python
   st.subheader("Editor de Presencialidad")
   # ...editor...
   ```

2. **Lógica de validación de "solo hoy"** - Remover funciones como:
   ```python
   def puede_editar_hoy(...)
   def marcar_presencia(...)
   ```

3. **Botones de sincronización manual** - Si existen, remover

**Mantener:**
- Funciones de caché (leer_asistencia_drive, cargar_cache_desde_drive, etc)
- Funciones de normalización
- Sección de Sustentos al final

---

### FASE 3: Testing (1 hora)

#### Test 1: Búsqueda por DNI
1. Entrar a Presencialidad Dealer
2. Ingresar DNI de promotor (ej: "47799536")
3. Presionar "🔎 Buscar Promotor"
4. ✅ Debe mostrar 1+ resultado

#### Test 2: Búsqueda por Nombre
1. Ingresar nombre parcial (ej: "Kevin")
2. Presionar "🔎 Buscar Promotor"
3. ✅ Debe mostrar promotores con ese nombre

#### Test 3: Rango Futuro
1. Buscar un promotor ACTIVO
2. Seleccionar rango futuro (ej: 01/07/2026 a 30/09/2026)
3. ✅ Debe permitir registrar (licencia maternidad)

#### Test 4: Rango Inválido (Inactivo)
1. Buscar un promotor INACTIVO con fecha_cese en mayo
2. Intentar registrar descanso en junio
3. ✅ Debe mostrar error: "no puede sobrepasar la fecha de cese"

#### Test 5: Carga de Documentos
1. Registrar descanso médico
2. Adjuntar 2+ documentos
3. Presionar "💾 Guardar Descanso"
4. ✅ Documentos deben aparecer en Drive

---

### FASE 4: Merge a Main (30 minutos)

```bash
git add asistencia.py
git commit -m "feat: rediseño módulo presencialidad para descansos médicos/vacaciones v2.5.0"
git push origin feature/presencialidad-v2

# En GitHub: crear Pull Request, review, merge
git checkout main
git pull origin main
```

---

## 🔍 VALIDACIÓN FINAL CHECKLIST

**Antes de Producción:**

### Página de Login
- [ ] Logo/Marca visible
- [ ] "✦ VENTAS DOOR TO DOOR" mostrado
- [ ] Texto de descripción actualizado
- [ ] Botones de login funcionales

### Módulo Alta (Formulario)
- [ ] RAZÓN SOCIAL dropdown solo muestra 4 socios
- [ ] WOW TEL/MALUTECH/2CONNECT removidos
- [ ] Canal siempre "VENTAS INDIRECTAS"

### Módulo Presencialidad Dealer
- [ ] Título es "📋 Gestión de Descansos Médicos y Vacaciones"
- [ ] Búsqueda por DNI funciona
- [ ] Búsqueda por Nombre funciona
- [ ] Rango de fechas valida correctamente
- [ ] Desplegable ZONA existe (aunque sea ["TODOS"])
- [ ] Formulario de descanso aparece al seleccionar promotor
- [ ] Carga de múltiples documentos funciona
- [ ] Guardado de descanso registra en Sheet

### Google Drive
- [ ] Hoja "Asistencia" tiene columna DISTRITO
- [ ] Hoja "ubicaciones" tiene DEPARTAMENTO, PROVINCIA, DISTRITO
- [ ] Documentos cargados aparecen en carpeta "Descansos_Medicos_Vacaciones"

### Base de Datos / Sheet
- [ ] Tabla "Sustentos_BM" (o "Sustentos_Descansos") registra correctamente
- [ ] Campos: TIPO_DESCANSO, FECHA_DESDE, FECHA_HASTA, DNI, NOMBRE, etc

---

## 📞 SOPORTE Y TROUBLESHOOTING

### Problema: "El desplegable ZONA no muestra zonas"
**Solución:** Es normal en el piloto. La columna ZONA se agregará a Drive en la v2.5.1.

### Problema: "Documentos no se cargan a Drive"
**Solución:** Verificar permisos de la API de Google Drive en `sheets.py` - función `subir_archivo_drive()`

### Problema: "La búsqueda no encuentra promotores"
**Solución:** 
1. Verificar que haya registros en la hoja Asistencia
2. Ejecutar "Sincronizar mes" desde módulo Altas
3. Refrescar (F5) la página

### Problema: "Error validando rango de fechas"
**Solución:** Verificar que FECHA_ALTA y FECHA_CESE estén en formato YYYY-MM-DD en Drive

---

## 📊 ESTIMACIÓN DE TIEMPO

| Tarea | Tiempo | Complejidad |
|-------|--------|-------------|
| Reemplazar auth.py | 5 min | 🟢 Trivial |
| Reemplazar formulario.py | 5 min | 🟢 Trivial |
| Actualizar constantes asistencia.py | 10 min | 🟢 Fácil |
| Agregar nuevas funciones | 30 min | 🟡 Medio |
| Rediseñar mostrar_asistencia() | 120 min | 🔴 Complejo |
| Remover secciones antiguas | 60 min | 🔴 Complejo |
| Testing | 60 min | 🟡 Medio |
| **TOTAL** | **290 min** | **~5 horas** |

---

## 🎯 NEXT STEPS DESPUÉS DEL PILOTO

1. **v2.5.1:** Agregar columna ZONA a Drive y funcionalidad completa
2. **v2.5.2:** Dashboard de reportes de descansos por socio/zona
3. **v2.5.3:** Notificaciones automáticas a supervisores
4. **v3.0:** Integración con nómina para descantos automatizados

---

## ✉️ CONTACTO Y PREGUNTAS

Para dudas o issues durante la implementación:
- Email: ksa@wowperu.pe
- Repository: GitHub [URL_REPO]
- Rama: `feature/presencialidad-v2`

---

**Documento Preparado:** 7 de Junio de 2026  
**Versión:** 2.5.0-presencialidad-v2  
**Estado:** ✅ Listo para Implementación
