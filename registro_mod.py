# registro_mod_v2_20260601 — jerarquía profesional con stats y tabla HTML
from datetime import datetime, timedelta
import re
import pandas as pd
import pytz
import streamlit as st

zona_peru = pytz.timezone("America/Lima")

def ahora_peru_fecha_hora():
    return datetime.now(zona_peru).strftime("%Y-%m-%d %H:%M:%S")

def hoy_peru_fecha():
    return datetime.now(zona_peru).date()

# =============================================================================
# Utilitarios
# =============================================================================

def limpiar_texto(valor) -> str:
    if pd.isna(valor) if not isinstance(valor, str) else False:
        return ""
    s = str(valor).strip()
    return "" if s.upper() in ("NONE","NAN","NULL") else s

def limpiar_fecha(valor):
    try:
        if valor in ("", None): return None
        f = pd.to_datetime(valor, errors="coerce")
        return None if pd.isna(f) else f.date()
    except Exception:
        return None

def normalizar_dni(valor) -> str:
    dni = limpiar_texto(valor).replace(".0","")
    if dni.isdigit() and len(dni) < 8:
        dni = dni.zfill(8)
    return dni

def limpiar_numero_texto(valor, zfill_dni=False) -> str:
    v = limpiar_texto(valor).replace(".0","").replace(",","")
    if v == "": return ""
    digitos = re.sub(r"\D","",v)
    if digitos:
        if zfill_dni and len(digitos) < 8:
            digitos = digitos.zfill(8)
        return digitos
    return v.strip()

def normalizar_columnas(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = df.columns.astype(str).str.strip().str.upper()
    return df

def hacer_columnas_unicas(columnas: list) -> list:
    salida, vistos = [], {}
    for i, col in enumerate(columnas, start=1):
        base = str(col).strip().upper() or f"COLUMNA_{i}"
        if base not in vistos:
            vistos[base] = 1; salida.append(base)
        else:
            vistos[base] += 1; salida.append(f"{base}_{vistos[base]}")
    return salida

def leer_records_sin_exigir_header_unico(hoja) -> list:
    valores = hoja.get_all_values()
    if not valores: return []
    headers = hacer_columnas_unicas([str(h).strip().upper() for h in valores[0]])
    n = len(headers)
    registros = []
    for fila in valores[1:]:
        fila = list(fila)
        if len(fila) < n: fila += [""] * (n - len(fila))
        registros.append({headers[i]: fila[i] for i in range(n)})
    return registros

def forzar_columnas_texto(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for c in df.columns:
        cu = str(c).upper()
        if "DNI" in cu:
            df[c] = df[c].apply(lambda x: limpiar_numero_texto(x, True)).astype(str)
        elif "CELULAR" in cu or cu.startswith("ID") or "ID " in cu:
            df[c] = df[c].apply(lambda x: limpiar_numero_texto(x, False)).astype(str)
    return df

def col_idx(df: pd.DataFrame, *nombres):
    for n in nombres:
        if n in df.columns:
            return df.columns.get_loc(n) + 1
    return None

MOTIVOS = [
    "", "Renuncia Laboral", "NSPP", "Baja por Productividad", "Baja por FPD",
    "Baja - VNE3", "Baja por politica de Actividad",
    "Abandono Laboral / Faltas Injustificadas", "Baja No asistio Campo",
    "Baja por cierre de Operaciones",
]

# =============================================================================
# CSS compartido para jerarquía
# =============================================================================

_CSS_JER = """
<style>
.jer-stats { display:flex; flex-wrap:wrap; gap:10px; margin:10px 0 14px; }
.jer-stat {
    flex:1; min-width:120px;
    background:white; border:1px solid #E5E0EA; border-radius:12px;
    padding:12px 16px 10px; text-align:center;
    box-shadow:0 1px 4px rgba(75,0,103,.07);
}
.jer-stat .sv { font-size:22px; font-weight:800; color:#4B0067; line-height:1.1; }
.jer-stat .sl { font-size:10.5px; color:#6B6175; margin-top:4px; font-weight:600; text-transform:uppercase; letter-spacing:.4px; }
.jer-wrap {
    width:100%; overflow-x:auto; overflow-y:auto; max-height:520px;
    border-radius:12px; border:1px solid #E5E0EA; margin-bottom:8px;
    box-shadow:0 2px 8px rgba(75,0,103,.06);
}
.jer-table { width:100%; border-collapse:collapse; font-size:12.5px; font-family:inherit; }
.jer-table thead th {
    position:sticky; top:0; z-index:2;
    background:linear-gradient(135deg,#4B0067 0%,#3a0052 100%);
    color:white; padding:10px 12px; text-align:left;
    font-size:11px; font-weight:700; letter-spacing:.5px; white-space:nowrap;
}
.jer-table tbody tr { border-bottom:1px solid #F2EEF5; }
.jer-table tbody tr:nth-child(even) { background:#FDFAFF; }
.jer-table tbody tr:hover { background:#F3E5FA; }
.jer-table tbody td { padding:8px 12px; color:#1A1521; white-space:nowrap; vertical-align:middle; }
.jer-table tbody td.nm { white-space:normal; min-width:160px; max-width:260px; }
.jer-badge-a { background:#D1FAE5; color:#065F46; padding:2px 9px; border-radius:10px; font-size:10.5px; font-weight:700; }
.jer-badge-i { background:#FEE2E2; color:#991B1B; padding:2px 9px; border-radius:10px; font-size:10.5px; font-weight:700; }
.jer-search { display:flex; gap:10px; flex-wrap:wrap; align-items:center; margin-bottom:10px; }
</style>
"""

def _inject_jer_css():
    st.markdown(_CSS_JER, unsafe_allow_html=True)

def _stats_html(df: pd.DataFrame) -> str:
    total   = len(df)
    activos = int((df.get("ESTADO", pd.Series()).astype(str).str.upper() == "ACTIVO").sum()) if "ESTADO" in df.columns else 0
    inact   = total - activos
    sups    = df["SUPERVISOR"].nunique() if "SUPERVISOR" in df.columns else (df["SUPERVISOR A CARGO"].nunique() if "SUPERVISOR A CARGO" in df.columns else 0)
    razones = df["RAZON SOCIAL"].nunique() if "RAZON SOCIAL" in df.columns else 0
    return f"""<div class='jer-stats'>
<div class='jer-stat'><div class='sv'>{total}</div><div class='sl'>Total registros</div></div>
<div class='jer-stat'><div class='sv' style='color:#065F46'>{activos}</div><div class='sl'>Activos</div></div>
<div class='jer-stat'><div class='sv' style='color:#991B1B'>{inact}</div><div class='sl'>Inactivos</div></div>
<div class='jer-stat'><div class='sv'>{sups}</div><div class='sl'>Supervisores</div></div>
<div class='jer-stat'><div class='sv'>{razones}</div><div class='sl'>Socios</div></div>
</div>"""

def _tabla_html(df: pd.DataFrame, max_filas: int = 500) -> str:
    # Columnas preferidas en orden
    pref = ["RAZON SOCIAL","DNI","NOMBRES","APELLIDO PATERNO","APELLIDO MATERNO",
            "SUPERVISOR A CARGO","SUPERVISOR","COORDINADOR","CARGO (ROL)","CARGO",
            "DEPARTAMENTO","PROVINCIA","ESTADO","FECHA DE CREACION USUARIO","FECHA_ALTA",
            "FECHA DE CESE","FECHA_CESE","MOTIVO","CANAL"]
    cols = [c for c in pref if c in df.columns]
    # Agregar columnas extra no cubiertas
    resto = [c for c in df.columns if c not in cols and not c.startswith("_")]
    cols += resto[:8]  # máximo 8 extra

    label = {
        "RAZON SOCIAL":"Razón Social","DNI":"DNI","NOMBRES":"Nombres",
        "APELLIDO PATERNO":"Ap. Paterno","APELLIDO MATERNO":"Ap. Materno",
        "SUPERVISOR A CARGO":"Supervisor","SUPERVISOR":"Supervisor",
        "COORDINADOR":"Coordinador","CARGO (ROL)":"Cargo","CARGO":"Cargo",
        "DEPARTAMENTO":"Departamento","PROVINCIA":"Provincia","ESTADO":"Estado",
        "FECHA DE CREACION USUARIO":"Alta","FECHA_ALTA":"Alta",
        "FECHA DE CESE":"Cese","FECHA_CESE":"Cese",
        "MOTIVO":"Motivo","CANAL":"Canal",
    }
    thead = "".join(f"<th>{label.get(c,c)}</th>" for c in cols)
    rows  = []
    for _, r in df.head(max_filas).iterrows():
        cells = []
        for c in cols:
            v = str(r.get(c,"") or "").strip()
            if c == "ESTADO":
                cls = "jer-badge-a" if v.upper()=="ACTIVO" else "jer-badge-i"
                cells.append(f"<td><span class='{cls}'>{v or '—'}</span></td>")
            elif c in ("NOMBRES","APELLIDO PATERNO","APELLIDO MATERNO"):
                cells.append(f"<td class='nm'>{v or '—'}</td>")
            else:
                cells.append(f"<td>{v or '—'}</td>")
        rows.append("<tr>"+"".join(cells)+"</tr>")
    return (f"<div class='jer-wrap'><table class='jer-table'>"
            f"<thead><tr>{thead}</tr></thead>"
            f"<tbody>{''.join(rows)}</tbody>"
            f"</table></div>")


# =============================================================================
# TABLA — Módulo jerarquía/matriz
# =============================================================================

def _opciones_filtro(df: pd.DataFrame, col: str) -> list:
    if df.empty or col not in df.columns: return ["TODOS"]
    vals = (df[col].astype(str).str.strip()
            .replace(["","None","NONE","nan","NaN","NULL","null"], pd.NA)
            .dropna().unique().tolist())
    return ["TODOS"] + sorted([v for v in vals if str(v).strip()])

def _aplicar_select(df: pd.DataFrame, col: str, val: str) -> pd.DataFrame:
    if val == "TODOS" or col not in df.columns: return df
    return df[df[col].astype(str).str.strip().eq(val)].copy()

@st.cache_data(ttl=180, show_spinner=False)
def _leer_matriz_cached(_hoja):
    return leer_records_sin_exigir_header_unico(_hoja)

def mostrar_tabla(hoja, razon_usuario=None):
    _inject_jer_css()

    key_reload = f"mxr_{st.session_state.get('rol','')}"
    if st.button("♻️ Recargar matriz", key=key_reload):
        _leer_matriz_cached.clear()

    data = _leer_matriz_cached(hoja)
    if not data:
        st.info("No hay datos en la jerarquía.")
        return None

    df = normalizar_columnas(pd.DataFrame(data)).fillna("")
    df = forzar_columnas_texto(df)
    rol = st.session_state.get("rol","")

    if rol != "backoffice" and razon_usuario and "RAZON SOCIAL" in df.columns:
        df = df[df["RAZON SOCIAL"].astype(str).str.strip().eq(razon_usuario)]

    # Stats
    st.markdown(_stats_html(df), unsafe_allow_html=True)

    # Filtros compactos
    st.caption("Filtros en memoria — no vuelve a leer Drive mientras filtras.")
    fa, fb, fc, fd = st.columns([1.4,1,1,1])
    with fa:
        buscar = st.text_input("🔍 DNI / nombre", key="mxr_buscar", placeholder="Ej: 76043772").strip()
    with fb:
        f_estado = st.selectbox("Estado", _opciones_filtro(df,"ESTADO"), key="mxr_estado")
    with fc:
        f_razon  = st.selectbox("Socio", _opciones_filtro(df,"RAZON SOCIAL"), key="mxr_razon")
    with fd:
        f_dep    = st.selectbox("Departamento", _opciones_filtro(df,"DEPARTAMENTO"), key="mxr_dep")

    fe, ff = st.columns(2)
    with fe:
        f_sup   = st.selectbox("Supervisor", _opciones_filtro(df,"SUPERVISOR A CARGO" if "SUPERVISOR A CARGO" in df.columns else "SUPERVISOR"), key="mxr_sup")
    with ff:
        f_canal = st.selectbox("Canal", _opciones_filtro(df,"CANAL"), key="mxr_canal")

    df_v = df.copy()
    for col, val in [
        ("ESTADO", f_estado), ("RAZON SOCIAL", f_razon),
        ("DEPARTAMENTO", f_dep), ("CANAL", f_canal),
    ]:
        df_v = _aplicar_select(df_v, col, val)
    # Supervisor puede estar en dos columnas
    for scol in ["SUPERVISOR A CARGO","SUPERVISOR"]:
        if scol in df_v.columns and f_sup != "TODOS":
            df_v = df_v[df_v[scol].astype(str).str.strip().eq(f_sup)].copy()
            break

    if buscar:
        cols_b = [c for c in ["DNI","NOMBRES","NOMBRE","APELLIDO PATERNO","APELLIDO MATERNO","CORREO (USUARIO SGC/PRONTO)"] if c in df_v.columns]
        if cols_b:
            pat  = buscar.upper()
            mask = pd.Series(False, index=df_v.index)
            for c in cols_b:
                mask |= df_v[c].astype(str).str.upper().str.contains(pat, na=False, regex=False)
            df_v = df_v[mask].copy()

    st.caption(f"Mostrando **{len(df_v)}** de **{len(df)}** registros.")

    MAX = 500
    if len(df_v) > MAX:
        st.caption(f"Se muestran los primeros {MAX}. Usa filtros para acotar.")
    st.markdown(_tabla_html(df_v, MAX), unsafe_allow_html=True)
    return df


# =============================================================================
# DAR DE BAJA
# =============================================================================

def dar_de_baja(df, hoja, razon_usuario=None):
    st.markdown("<span class='wow-section-title'>🔻 Dar de baja</span>", unsafe_allow_html=True)

    df = normalizar_columnas(df).fillna("")
    rol = st.session_state.get("rol","")
    usuario_actual = st.session_state.get("usuario","")

    if rol != "backoffice" and razon_usuario and "RAZON SOCIAL" in df.columns:
        df = df[df["RAZON SOCIAL"].astype(str).str.strip().eq(razon_usuario)]

    if "DNI" not in df.columns:
        st.error("❌ La base no tiene columna DNI.")
        return

    dni = st.text_input("DNI del colaborador a dar de baja", key="dni_baja",
                        placeholder="Ej: 76043772").strip()
    if not dni:
        return

    dni_limpio = normalizar_dni(dni)
    df["DNI_NORM"] = df["DNI"].apply(normalizar_dni)
    df_filtrado    = df[df["DNI_NORM"].eq(dni_limpio)].copy()

    if df_filtrado.empty:
        st.error("❌ DNI no encontrado en la base.")
        return

    activos = (df_filtrado[df_filtrado["ESTADO"].astype(str).str.strip().str.upper().eq("ACTIVO")].copy()
               if "ESTADO" in df_filtrado.columns else df_filtrado.copy())

    if activos.empty:
        st.warning("⚠️ El DNI existe pero no tiene registros activos para dar de baja.")
        st.dataframe(df_filtrado.drop(columns=["DNI_NORM"], errors="ignore"), use_container_width=True)
        return

    if len(activos) > 1:
        opciones   = activos.reset_index()
        seleccion  = st.selectbox(
            "Selecciona registro activo",
            opciones.index,
            format_func=lambda i: (
                f"{limpiar_texto(opciones.loc[i].get('RAZON SOCIAL',''))} — "
                f"{limpiar_texto(opciones.loc[i].get('CARGO (ROL)',''))} — "
                f"Alta: {limpiar_texto(opciones.loc[i].get('FECHA DE CREACION USUARIO',''))}"
            )
        )
        fila = opciones.loc[seleccion]
        index_global = int(fila["index"])
    else:
        fila = activos.iloc[0]; index_global = int(fila.name)

    st.info(
        f"📋 Seleccionado: **{limpiar_texto(fila.get('RAZON SOCIAL',''))}** / "
        f"**{limpiar_texto(fila.get('NOMBRES', fila.get('NOMBRE','')))}** / "
        f"Alta: {limpiar_texto(fila.get('FECHA DE CREACION USUARIO',''))}"
    )

    fecha_creacion = limpiar_fecha(fila.get("FECHA DE CREACION USUARIO"))
    hoy = hoy_peru_fecha()
    fecha  = st.date_input("Fecha de cese", value=hoy,
                           min_value=hoy - timedelta(days=2), max_value=hoy,
                           key="fecha_cese_baja", help="Permite antier, ayer u hoy.")
    motivo = st.selectbox("Motivo de baja", MOTIVOS, key="motivo_baja")

    if st.button("🔻 Confirmar baja", key="btn_dar_baja", type="primary"):
        if not motivo:
            st.error("❌ Selecciona un motivo de baja.")
            return
        if fecha_creacion and fecha < fecha_creacion:
            st.error("❌ La fecha de cese no puede ser menor a la fecha de alta.")
            return
        try:
            row_sheet = index_global + 2
            fecha_mov = str(fecha)
            marca_baja = ahora_peru_fecha_hora()
            for col_name, valor in [
                (col_idx(df,"ESTADO"),                                "INACTIVO"),
                (col_idx(df,"FECHA DE CESE","FECHA CESE"),            str(fecha)),
                (col_idx(df,"MOTIVO"),                                motivo),
                (col_idx(df,"FECHA MOV"),                             fecha_mov),
                (col_idx(df,"FECHA_BAJA_REGISTRO","FECHA BAJA REG"), marca_baja),
                (col_idx(df,"USUARIO_BAJA","USUARIO BAJA"),           usuario_actual),
            ]:
                if col_name:
                    hoja.update_cell(row_sheet, col_name, valor)
            st.success(f"✅ Baja aplicada correctamente — {fecha_mov}")
            _leer_matriz_cached.clear()
        except Exception as e:
            st.error(f"❌ Error al aplicar la baja: {e}")


# =============================================================================
# EDITAR
# =============================================================================

def editar_registro(df, hoja, hoja_ubi):
    st.markdown("<span class='wow-section-title'>✏️ Editar registro</span>", unsafe_allow_html=True)
    df = normalizar_columnas(df).fillna("")
    if "DNI" not in df.columns:
        st.error("❌ La base no tiene columna DNI.")
        return
    rol = st.session_state.get("rol","")
    razon_usuario = st.session_state.get("razon","")
    if rol != "backoffice" and razon_usuario and "RAZON SOCIAL" in df.columns:
        df = df[df["RAZON SOCIAL"].astype(str).str.strip().eq(razon_usuario)]
    dni = st.text_input("DNI a editar", key="dni_edit", placeholder="Ej: 76043772")
    if not dni: return
    dni_limpio = normalizar_dni(dni)
    df["DNI_NORM"] = df["DNI"].apply(normalizar_dni)
    df_filtrado = df[df["DNI_NORM"].eq(dni_limpio)].copy()
    if df_filtrado.empty:
        st.error("❌ No encontrado"); return
    if len(df_filtrado) > 1:
        opciones  = df_filtrado.reset_index()
        seleccion = st.selectbox(
            "Selecciona registro",
            opciones.index,
            format_func=lambda i: f"{opciones.loc[i].get('RAZON SOCIAL','')} — {opciones.loc[i].get('CARGO (ROL)','')} — {opciones.loc[i].get('ESTADO','')}"
        )
        fila = opciones.loc[seleccion]; index_global = fila["index"]
    else:
        fila = df_filtrado.iloc[0]; index_global = fila.name
    st.success(f"Registro encontrado — fila Sheets: {int(index_global)+2}")
    st.info("Implementa aquí los campos que deseas editar según tu lógica de negocio.")
