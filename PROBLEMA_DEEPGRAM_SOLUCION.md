# 🚫 PROBLEMA: USO DE DEEPGRAM - SOLUCIÓN

## 🔴 ¿POR QUÉ NO USAR DEEPGRAM?

Cuando pasas archivos .py por Deepgram:

```
Archivo original:
def buscar_promotor_por_dni_nombre(df_mes: pd.DataFrame, dni: str = "", nombre: str = ""):

Después de Deepgram:
def buscar_promotor_por_dni_nombre(df_mes: pd.DataFrome, dni: str = "", nombre: str = ""):
                                                         ↑
                                                    ERROR: DataFrome vs DataFrame
```

**Problemas causados:**
- ❌ Cambios de nombres de variables
- ❌ Errores de sintaxis
- ❌ Duplicación de código
- ❌ Caracteres especiales mal interpretados
- ❌ Indentación rota

---

## ✅ SOLUCIÓN: DESCARGAR DIRECTO

### Opción 1: Descargar desde Claude (RECOMENDADO)

```
1. Click en el archivo .py (auth.py, formulario.py, asistencia.py)
2. Descarga el archivo
3. Cópialo a tu repo
4. Listo
```

**Sin pasos intermedios. Sin Deepgram. Sin errores.**

### Opción 2: Copiar desde GitHub

```bash
# Si ya está en GitHub:
git pull origin feature/presencialidad-v2
git checkout feature/presencialidad-v2

# Los archivos se actualizan automáticamente
```

---

## 🔧 PASOS PARA ARREGLAR AHORA

### PASO 1: Borra caché de Streamlit

```bash
# En PowerShell (Windows):
Remove-Item -Path ".\.streamlit\cache_data\*" -Force -Recurse

# En Terminal (Mac/Linux):
rm -rf .streamlit/cache_data/*
```

### PASO 2: Descarga archivos DIRECTO (SIN Deepgram)

✅ Descarga:
- auth.py
- formulario.py
- asistencia.py

### PASO 3: Reemplaza en tu repo

```bash
cp auth.py ~/tu_repo/auth.py
cp formulario.py ~/tu_repo/formulario.py
cp asistencia.py ~/tu_repo/asistencia.py
```

### PASO 4: Verifica en Git

```bash
cd tu_repo
git status

# Debe mostrar:
# modified: auth.py
# modified: formulario.py
# modified: asistencia.py
```

### PASO 5: Reinicia Streamlit

```bash
# Ctrl+C para detener
# Luego:
streamlit run app_maestra_vendedores.py
```

### PASO 6: Verifica DISTRITO aparece

```
En la aplicación:
Presencialidad Dealer → Búsqueda
    ☐ DNI
    ☐ Nombre
    ☐ Desde
    ☐ Hasta
    ☐ Zona
    ☐ DISTRITO  ← Debe aparecer aquí
```

Si NO aparece:
```bash
# Borra caché de nuevo
rm -rf .streamlit/cache_data/*
# Reinicia
streamlit run app_maestra_vendedores.py
```

---

## 🎯 CAMBIO A "VENTA DOOR TO DOOR"

En `auth.py` línea ~52:

**ANTES:**
```python
"✦ VENTAS DOOR TO DOOR"
```

**DESPUÉS:**
```python
"✦ VENTA DOOR TO DOOR"
```

(Cambio de VENTAS → VENTA, singular)

---

## 🏪 ¿QUÉ ES "OXXO"?

⚠️ **No entiendo bien tu instrucción:**

"Debe aparecer un OXXO, aunque diga distrito"

¿Te referías a:
- ☐ Un ícono/emoji? 🏪
- ☐ Un campo nuevo llamado "OXXO"?
- ☐ Una tienda OXXO en Drive?
- ☐ Otra cosa?

**Clarifica** para que agregue esto correctamente.

---

## 📋 FLUJO CORRECTO (Sin Deepgram)

```
Claude genera archivos .py
    ↓
Tú descargas directo (sin Deepgram)
    ↓
Reemplazas en tu repo
    ↓
Git commit + push
    ↓
✅ Funciona perfecto
```

---

## ❌ FLUJO INCORRECTO (Con Deepgram)

```
Claude genera archivos .py
    ↓
Tú los pasas por Deepgram (PROBLEMA)
    ↓
Deepgram introduce errores
    ↓
Pegas texto dañado en repo
    ↓
❌ No funciona, código roto
```

---

## 🚀 RESUMEN

```
NUNCA:
❌ auth.py → Deepgram → Copiar/Pegar → GitHub

SIEMPRE:
✅ auth.py → Descargar → Reemplazar → GitHub
```

---

## 📞 SI DISTRITO SIGUE SIN APARECER

1. **Verifica** que DISTRITO está en Drive (columna C)
2. **Borra caché:** `rm -rf .streamlit/cache_data/*`
3. **Reinicia:** `streamlit run app_maestra_vendedores.py`
4. **Espera** 5 segundos (Streamlit recarga)
5. **Presiona F5** en el navegador (recarga frontend)
6. **Verifica** que aparece DISTRITO

Si aún no aparece:
- Envíame screenshot de qué ves en la búsqueda
- Dime si agregaste DISTRITO en Google Drive

---

**Documento**: PROBLEMA_DEEPGRAM_SOLUCION.md  
**Prioridad**: 🔴 CRÍTICA - Este es tu problema principal  
**Solución**: Descarga directo, sin Deepgram
