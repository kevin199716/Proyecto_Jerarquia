# 👥 DUPLICADOS vs REINGRESOS - Cómo Saber la Diferencia

## 🔍 TU CASO: Andrea Jeniffer Flores Carhuas (DNI: 47722887)

Aparece 2 veces en los resultados. ¿Por qué?

### OPCIÓN 1: Es un Reingreso (CORRECTO - Mantener ambos)

```
Registro 1:
- DNI: 47722887
- NOMBRE: Andrea Jeniffer Flores Carhuas
- FECHA_ALTA: 2025-03-01
- FECHA_CESE: 2026-05-31
- ESTADO: INACTIVO

Registro 2:
- DNI: 47722887
- NOMBRE: Andrea Jeniffer Flores Carhuas
- FECHA_ALTA: 2026-06-01  ← FECHA DIFERENTE
- FECHA_CESE: [vacío]
- ESTADO: ACTIVO

✅ CORRECTO: Se dio de baja el 31/05, volvió a ingresar 01/06
✅ MANTENER AMBOS: El sistema necesita ambos registros
```

### OPCIÓN 2: Es un Duplicado (INCORRECTO - Eliminar uno)

```
Registro 1:
- DNI: 47722887
- NOMBRE: Andrea Jeniffer Flores Carhuas
- FECHA_ALTA: 2026-06-07
- FECHA_CESE: [vacío]
- ESTADO: ACTIVO

Registro 2:
- DNI: 47722887
- NOMBRE: Andrea Jeniffer Flores Carhuas
- FECHA_ALTA: 2026-06-07  ← FECHA IGUAL
- FECHA_CESE: [vacío]
- ESTADO: ACTIVO

❌ INCORRECTO: Son idénticos
❌ ELIMINAR UNO: Mantener solo uno de los dos
```

---

## 🔧 CÓMO IDENTIFICAR EN GOOGLE DRIVE

### EN HOJA "colaboradores":

1. **Abre** la hoja "colaboradores"
2. **Busca** por DNI 47722887
3. **Verifica:**

```
Columnas a revisar:
- FECHA DE CREACION USUARIO (FECHA_ALTA)
- FECHA DE CESE
- ESTADO
```

### Tabla de decisión:

| FECHA_ALTA | FECHA_CESE | ESTADO | ¿Qué hacer? |
|-----------|-----------|--------|------------|
| 2025-03-01 | 2026-05-31 | INACTIVO | ✅ Mantener |
| 2026-06-01 | [vacío] | ACTIVO | ✅ Mantener |
| 2026-06-07 | [vacío] | ACTIVO | ✅ Mantener |
| 2026-06-07 | [vacío] | ACTIVO | ❌ Eliminar (es copia) |

---

## ✅ EN TU CASO (Probablemente Reingreso)

Basándome en lo que viste (2 registros con ACTIVO y sin FECHA_CESE):

```
Probablemente:
- Registro 1: Reingreso reciente (FECHA_ALTA: 2026-06-XX)
- Registro 2: Otro reingreso o cambio de datos

Verificar en Drive:
[ ] FECHA_ALTA diferente en cada uno?
[ ] Si son diferentes → ✅ MANTENER AMBOS
[ ] Si son iguales → ❌ ELIMINAR UNO
```

---

## 🛠️ CÓMO ELIMINAR DUPLICADO (SI NECESARIO)

### En Google Sheets:

1. **Click derecho** en la fila duplicada
2. **Selecciona:** "Eliminar fila"
3. **Confirma:** "Sí"

### ⚠️ ADVERTENCIA:

No elimines sin verificar primero que realmente sea un duplicado.

---

## 💡 CÓMO EVITAR DUPLICADOS EN FUTURO

### Regla:
```
CLAVE = DNI + FECHA_ALTA

Si (DNI + FECHA_ALTA) es igual → Duplicado
Si (DNI + FECHA_ALTA) es diferente → Reingreso (mantener)
```

### Ejemplo:

```
Duplicado:
- 47722887 + 2026-06-07 = Duplicado A
- 47722887 + 2026-06-07 = Duplicado B
❌ Eliminar uno

Reingreso:
- 47722887 + 2025-03-01 = Antiguo (se dio de baja)
- 47722887 + 2026-06-01 = Nuevo reingreso
✅ Mantener ambos
```

---

## 📍 CÓMO VER EN LA APLICACIÓN

Cuando aparecen 2 registros en la búsqueda:

```
🔍 Búsqueda de Promotor
  Buscar DNI: 47722887
  [🔎 Buscar]

✅ Encontrados 2 registros

📋 Resultados
┌─────────────────────────────────────────────────────┐
│ DNI      │ NOMBRE                    │ FECHA_ALTA   │
├─────────────────────────────────────────────────────┤
│ 47722887 │ Andrea Jeniffer F.C.      │ 2025-03-01   │
│ 47722887 │ Andrea Jeniffer F.C.      │ 2026-06-01   │
└─────────────────────────────────────────────────────┘

SI FECHA_ALTA es diferente → ✅ Reingreso (ambos correctos)
SI FECHA_ALTA es igual → ❌ Duplicado (eliminar uno)
```

---

## 🔐 REGLA DE ORO

```
ÚNICA FORMA de saber si es duplicado o reingreso:

Verificar FECHA_ALTA en Google Drive "colaboradores"

Si son diferentes → ✅ MANTENER AMBOS (son reingresos)
Si son iguales → ❌ ELIMINAR UNO (es duplicado)
```

---

## 📞 TU PRÓXIMO PASO

1. **Abre** Google Drive → Hoja "colaboradores"
2. **Busca** DNI 47722887 (usar Ctrl+F)
3. **Compara** FECHA_ALTA en cada registro
4. **Decide:**
   - Si diferentes → ✅ Listo
   - Si iguales → Elimina uno

---

**Documento**: DUPLICADOS_REINGRESOS_EXPLICACION.md  
**Tiempo acción**: 2 minutos  
**Criticidad**: Media
