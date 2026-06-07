# 📍 GUÍA EXACTA: CÓMO AGREGAR DISTRITO EN GOOGLE DRIVE

## 🎯 PREGUNTA RESPONDIDA

**"¿Qué nombre le coloco? ¿En cualquier orden? ¿Dónde coloco?"**

**RESPUESTA:**
- **Nombre:** `DISTRITO` (exacto, mayúsculas)
- **Orden:** Después de PROVINCIA (como tu preferencia)
- **Dónde:** En ambas hojas (ubicaciones + Asistencia)

---

## 📋 PASO 1: Hoja "ubicaciones"

### Ubicación exacta:

```
Columnas actuales:
1. DEPARTAMENTO
2. PROVINCIA
3. [NUEVO] DISTRITO  ← Aquí
4. SUPERVISOR A CARGO FINAL
5. ...resto
```

### Cómo agregar en Google Sheets:

1. **Abre** la hoja "ubicaciones"
2. **Click derecho** en columna C (después de PROVINCIA)
3. **Selecciona:** "Insertar 1 a la derecha"
4. **En la celda C1** escribe: `DISTRITO`
5. **Rellena** los valores:

### Valores para cada DEPARTAMENTO:

**LIMA:**
- LIMA → LIMA
- LIMA → SAN ISIDRO
- LIMA → MIRAFLORES
- LIMA → BREÑA
- etc.

**AMAZONAS:**
- CHACHAPOYAS → CHACHAPOYAS
- CHACHAPOYAS → MARISCAL CASTILLA
- etc.

**CUSCO:**
- CUSCO → CUSCO
- CUSCO → SAN JERÓNIMO
- etc.

**EJEMPLO FINAL:**
```
| DEPARTAMENTO | PROVINCIA      | DISTRITO              | SUPERVISOR          |
|--------------|----------------|----------------------|----------------------|
| LIMA         | LIMA           | LIMA                 | Juan García         |
| LIMA         | LIMA           | SAN ISIDRO           | Juan García         |
| LIMA         | LIMA           | MIRAFLORES           | Juan García         |
| AMAZONAS     | CHACHAPOYAS    | CHACHAPOYAS          | Pedro Rodríguez     |
| CUSCO        | CUSCO          | CUSCO                | María López         |
```

---

## 📋 PASO 2: Hoja "Asistencia"

### Ubicación exacta:

```
Columnas de base:
1. RAZON SOCIAL
2. SUPERVISOR
3. COORDINADOR
4. DEPARTAMENTO
5. PROVINCIA
6. [NUEVO] DISTRITO  ← Aquí
7. DNI
8. NOMBRE
9. ...resto
```

### Cómo agregar:

1. **Abre** la hoja "Asistencia"
2. **Click derecho** en columna F (después de PROVINCIA)
3. **Selecciona:** "Insertar 1 a la derecha"
4. **En la celda F1** escribe: `DISTRITO`
5. **NO necesita rellenar** (se llena automáticamente cuando se registra un promotor)

---

## ✅ VERIFICACIÓN FINAL

Después de agregar, verifica:

```
Google Drive:
✅ "ubicaciones" tiene columna DISTRITO (después de PROVINCIA)
✅ "Asistencia" tiene columna DISTRITO (después de PROVINCIA)
✅ "ubicaciones" tiene valores (LIMA, SAN ISIDRO, etc.)
✅ "Asistencia" columna vacía (se llena al registrar)

Aplicación:
✅ Búsqueda muestra campo DISTRITO
✅ Formulario muestra campo DISTRITO
✅ Al guardar, se refleja en Drive
```

---

## 🚨 PUNTOS IMPORTANTES

### NO hagas esto:
```
❌ DISTRITRO (con typo)
❌ Distrito (minúsculas)
❌ distrito (minúsculas)
❌ DISTRIT0 (cero en lugar de O)
```

### Sí haz esto:
```
✅ DISTRITO (exacto)
✅ Después de PROVINCIA
✅ Mismo nombre en ambas hojas
```

---

## 🔗 RELACIÓN CON asistencia.py

Cuando el código en `asistencia.py` ve:

```python
COLUMNAS_BASE = [
    "RAZON SOCIAL",
    "SUPERVISOR",
    "COORDINADOR",
    "DEPARTAMENTO",
    "PROVINCIA",
    "DISTRITO",  # ← Busca esta columna en Drive
    "DNI",
    ...
]
```

Automáticamente:
1. Lee DISTRITO de Drive
2. Lo muestra en la búsqueda
3. Lo guarda en nuevos registros

---

## 📞 SI ALGO SALE MAL

### Error: "Columna DISTRITO no encontrada"
→ Verificar nombre exacto en Drive: `DISTRITO` (mayúsculas)

### Error: "DISTRITO aparece dos veces"
→ Eliminar una de las columnas duplicadas

### DISTRITO no se llena automáticamente
→ Verificar que esté en la misma posición en ambas hojas

---

## 📸 ASPECTO FINAL EN DRIVE

```
HOJA "ubicaciones":
┌─────────────┬──────────────┬──────────────┬────────────────┐
│ DEPARTAMENTO│ PROVINCIA    │ DISTRITO     │ SUPERVISOR...  │
├─────────────┼──────────────┼──────────────┼────────────────┤
│ LIMA        │ LIMA         │ LIMA         │ Juan García    │
│ LIMA        │ LIMA         │ SAN ISIDRO   │ Juan García    │
│ AMAZONAS    │ CHACHAPOYAS  │ CHACHAPOYAS  │ Pedro Rodríguez│
└─────────────┴──────────────┴──────────────┴────────────────┘

HOJA "Asistencia":
┌─────────────┬────────────┬───────────┬──────────┬──────────┬──────────┐
│ RAZON SOCIAL│ SUPERVISOR │ COORDINADOR│ DEPART.  │ PROVINCIA│ DISTRITO │
├─────────────┼────────────┼───────────┼──────────┼──────────┼──────────┤
│ INTERCON... │ Juan       │ Ana       │ LIMA     │ LIMA     │ LIMA     │
│ NOGALES...  │ Pedro      │ Carlos    │ AMAZONAS │ CHACHAP..│ CHACHAP..│
└─────────────┴────────────┴───────────┴──────────┴──────────┴──────────┘
```

---

**Documento**: DISTRITO_EN_DRIVE_GUIA_EXACTA.md  
**Estado**: ✅ PASO A PASO DETALLADO  
**Tiempo**: 5 minutos para agregar
