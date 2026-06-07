# 📋 RESUMEN DE CAMBIOS - WAP VENTAS DOOR TO DOOR

## Fecha: Junio 2026
## Módulo: Actualización de Jerarquía + Presencialidad Dealer (Piloto)

---

## 🎯 RESUMEN EJECUTIVO

El proyecto requiere actualizaciones estratégicas en **3 archivos principales** para reflejar el cambio de marca (EMPRESAS → VENTAS DOOR TO DOOR) y rediseñar completamente el módulo de Presencialidad Dealer enfocándose SOLO en gestión de **Bajas Médicas y Vacaciones**, eliminando registros de asistencia.

---

## 📁 ARCHIVOS A MODIFICAR

### 1️⃣ `auth.py` - Cambio de Marca en Hero Login
**Estado:** ✅ SIMPLE

**Líneas a cambiar:** 48-58

**Cambios:**
- Línea 52: Cambiar eyebrow de "✦ Portal de Vendedores" → "✦ VENTAS DOOR TO DOOR"
- Línea 53: Mantener título pero puede refinarse
- Línea 54: Actualizar descripción a: "Actualización de jerarquía: altas, bajas, descansos médicos y vacaciones."
- Líneas 55-59: Simplificar features a solo:
  - Altas y bajas
  - Descansos médicos y vacaciones
  - Jerarquía

**Impacto:** 🟢 Bajo - Solo cambio de textos en UI de bienvenida

---

### 2️⃣ `asistencia.py` - REDISEÑO MAYOR DEL MÓDULO
**Estado:** ⚠️ COMPLEJO - Cambios estructurales importantes

**Cambios principales:**

#### A. Simplificación de constantes (líneas 69-76)
```
ANTES:
MARCAS_PRESENCIALIDAD = ["", "A", "A-BM", "A-VAC", "NA-SA", "NA-CA"]
LEYENDA_MARCAS = { múltiples entradas }

DESPUÉS:
MARCAS_PRESENCIALIDAD = ["A-BM", "A-VAC"]  # Solo BM y VAC
LEYENDA_MARCAS = {
    "A-BM": "Descanso Médico",
    "A-VAC": "Vacaciones",
}
```

#### B. Nueva función: Búsqueda de Promotores (NUEVA)
```python
def buscar_promotor(df_mes, dni: str = "", nombre: str = "") -> pd.DataFrame:
    """
    Busca promotor por DNI o nombre en df_mes
    Retorna todos los coincidentes (activos, inactivos, reingresos)
    """
    # Lógica de búsqueda flexible
```

#### C. Nueva función: Validación de Rango de Fechas (NUEVA)
```python
def validar_rango_disponible(estado: str, fecha_alta: str, fecha_cese: str, 
                             fecha_inicio_rango: str, fecha_fin_rango: str) -> bool:
    """
    Valida que el rango seleccionado esté dentro del período activo del promotor.
    
    Reglas:
    - Si ACTIVO: rango debe ser >= fecha_alta
    - Si INACTIVO: rango debe estar entre fecha_alta y fecha_cese
    - Permite futuros (ej: licencia maternidad de 90 días)
    """
```

#### D. Nueva función: Registro de Baja Médica/Vacaciones (NUEVA)
```python
def registrar_descanso(hoja_asistencia, datos: dict) -> str:
    """
    Registra un descanso médico o vacacional en la hoja de asistencia.
    
    Parámetros:
    - promotor_dni, promotor_nombre, razon_social
    - tipo_descanso: "A-BM" o "A-VAC"
    - fecha_inicio, fecha_fin
    - documentos: lista de archivos subidos a Drive
    
    Retorna: mensaje de éxito/error
    """
```

#### E. Rediseño de `mostrar_asistencia()` (líneas 925+)
**ANTES:**
- Filtros: Razón Social, Supervisor, Coordinador, Departamento, Provincia, Estado
- Vista: Matriz editable con días del mes (DIA_1 a DIA_31)
- Funcionalidad: Marcar asistencia diaria

**DESPUÉS:**
- **Nueva barra de filtros:**
  1. Razón Social (TODOS) - Desplegable
  2. Zona (TODOS) - **NUEVO CAMPO**
  3. Campo de búsqueda por DNI (texto)
  4. Campo de búsqueda por Nombre (texto)
  5. Rango de fechas (fecha_inicio - fecha_fin) **NUEVO**
  6. Botón "🔎 Buscar"

- **Nueva vista de resultados:**
  - Tabla con registros encontrados (DNI, NOMBRE, RAZON SOCIAL, ESTADO, FECHA_ALTA, FECHA_CESE)
  - Click en fila → Expande formulario de descanso médico/vacacional
  - Formulario contiene:
    - Tipo de descanso (desplegable: Descanso Médico / Vacaciones)
    - Fecha de inicio (date picker)
    - Fecha de fin (date picker)
    - Campo para adjuntar documento(s) - **MÚLTIPLE**
    - Botón "Guardar descanso"

- **Eliminación:**
  - Remove matriz de edición diaria
  - Remove botones de sincronización manual
  - Remove todo lo relacionado con "período/día" viejo

#### F. Integración con Google Drive
- Los documentos adjuntos se suben a una carpeta `Descansos_Medicos_Vacaciones/` en Drive
- Se registra en tabla `Sustentos_BM` con:
  - FECHA_DESDE, FECHA_HASTA
  - DNI, NOMBRE, RAZON SOCIAL
  - TIPO_DESCANSO (BM o VAC)
  - LINK_DOCUMENTO
  - FECHA_CARGA, USUARIO_REGISTRO

**Impacto:** 🔴 ALTO - Rediseño completo de lógica y UI

---

### 3️⃣ `formulario.py` - Actualización de Dropdown Razón Social
**Estado:** ✅ SIMPLE

**Cambio:**
- Actualizar la lista de razones sociales a SOLO las que proporcionaste:
  ```
  - INTERCONEXION 360 SAC
  - MULTIPLE FORCE SAC
  - NOGALES HIGH SAC
  - GRUPO CREED SAC
  ```
- Remover cualquier otra razón social que estuviera en el dropdown

**Ubicación:** Buscar en `formulario.py` dónde se define la lista de razones sociales (probablemente en un desplegable `st.selectbox`)

**Impacto:** 🟢 Bajo - Solo cambio de opciones estáticas

---

### 4️⃣ `sheets.py` - Soporte para Columna DISTRITO
**Estado:** 🟡 MEDIO

**Cambio:**
- Asegurar que la función de cascada de ubicaciones (Departamento → Provincia → **Distrito**) funcione correctamente
- Actualizar `COLUMNAS_BASE` si aplica en asistencia.py para incluir DISTRITO
- La lógica actual (lectura desde Drive) debería funcionar automáticamente SI:
  1. La hoja "ubicaciones" en el Drive tiene las columnas: DEPARTAMENTO, PROVINCIA, DISTRITO
  2. La función de cascada en `formulario.py` está configurada para leer la tercera columna

**Impacto:** 🟡 Medio - Validar existencia, poco cambio de código

---

### 5️⃣ `app_maestra_vendedores.py` - CAMBIO MENOR
**Estado:** ✅ SIMPLE

**Cambio (opcional pero recomendado):**
- Línea 34: Cambiar `page_title="WOW D2D | Portal Vendedores"` → `"WAP VENTAS D2D | Portal"`
- Línea 52: El eyebrow ya se actualiza en `auth.py`

**Impacto:** 🟢 Bajo

---

## 🔄 FLUJO PROPUESTO PARA PRESENCIALIDAD DEALER

### Escenario 1: Registrar Descanso Médico
```
1. Usuario entra a "Presencialidad Dealer"
2. Completar búsqueda:
   - Ingresa DNI de Kevin → O bien nombre "Kevin"
   - Selecciona rango: 01/03/2026 - 30/04/2026
   - Presiona "🔎 Buscar"
3. Resultados:
   - Muestra Kevin (ACTIVO, DNI 12345678, RAZON SOCIAL: NOGALES HIGH SAC)
4. Click en Kevin → Se expande formulario:
   - Tipo: "Descanso Médico"
   - Fecha inicio: 01/03/2026
   - Fecha fin: 05/03/2026 (rango seleccionable)
   - Adjunta documento (certificado médico)
   - Guardar → Se carga en Asistencia y Sustentos_BM
```

### Escenario 2: Licencia Maternidad (Futuro)
```
1. Misma búsqueda
2. Formula descanso:
   - Tipo: "Descanso Médico"
   - Fecha inicio: 15/07/2026 (futura)
   - Fecha fin: 18/10/2026 (90 días aprox)
   - Adjunta documentos (certificado, autorización)
   - El sistema permite porque la promotora está ACTIVA desde antes de esa fecha
```

### Escenario 3: Administrador ve Todo
```
- El admin (backoffice) ve TODOS los registros de descansos
- El dealer solo ve sus propios descansos (según razón social)
- Filtro "Zona" disponible para admin (en desarrollo futuro)
```

---

## 📊 TABLA DE CAMBIOS RESUMIDA

| Archivo | Tipo | Complejidad | Líneas | Estado |
|---------|------|------------|--------|--------|
| `auth.py` | Textos | Simple | 48-58 | ✅ Listo |
| `asistencia.py` | Lógica + UI | Complejo | 400+ | ⚠️ En desarrollo |
| `formulario.py` | Datos | Simple | ~50 | ✅ Listo |
| `sheets.py` | Validación | Medio | 10-20 | 🟡 Verificar |
| `app_maestra_vendedores.py` | Metadatos | Simple | 2 | ✅ Opcional |

---

## 🧪 VALIDACIONES CRÍTICAS

Antes de deploy, verificar:

- [ ] Columnas de "ubicaciones" en Drive: DEPARTAMENTO, PROVINCIA, DISTRITO
- [ ] Columnas de "Asistencia" en Drive incluyen: DISTRITO (nueva)
- [ ] Las 4 razones sociales aparecen en desplegable de formulario
- [ ] Búsqueda de promotor funciona con DNI, nombre, y reingresos
- [ ] Rango de fechas respeta fecha_alta y fecha_cese
- [ ] Documentos se suben a Drive correctamente
- [ ] Tabla Sustentos_BM se crea/actualiza sin errores

---

## 📝 PRÓXIMOS PASOS

1. ✅ Implementar cambios en los 5 archivos
2. ✅ Subir archivos a GitHub en rama `feature/presencialidad-v2`
3. 🧪 Testing local: Alta, búsqueda, carga de descanso médico
4. 🔄 Ciclo de feedback con usuario
5. 📦 Merge a `main` tras validación

---

**Documento generado:** 7/Junio/2026  
**Versión:** 2.5.0-presencialidad-v2  
**Responsable:** System Update
