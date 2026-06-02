# ASISTENCIA_V6_DATA_EDITOR_INLINE_20260601
# ─────────────────────────────────────────────────────────────────────────────
# ARQUITECTURA:
# • st.data_editor con columna DIA_X como SelectboxColumn → marcación inline
#   en la misma fila, sin panel separado — exactamente como en la imagen antigua
# • Al presionar "💾 Guardar marcaciones" procesa solo las filas que cambiaron
# • Retroactivo A-BM: el selectbox de días pasados solo ofrece ["", "A-BM"]
# • Upload sustento A-BM: aparece contextualmene cuando hay A-BM pendiente de guardar
# • Bloque Jerarquía rediseñado: estadísticas + tabla profesional
# • Sin inputs fantasma, sin "None" visible, sin recarga de Drive al guardar
# • batch_get + caché 90s → escala a millones de filas en Sheets sin reventar
# ─────────────────────────────────────────────────────────────────────────────

import calendar
import pytz
from datetime import datetime, date

import pandas as pd
import streamlit as st
from sheets import subir_archivo_drive, obtener_o_crear_worksheet

NOMBRE_LIBRO    = "maestra_vendedores"
HOJA_SUSTENTOS  = "Sustentos_Bajas"
TZ_LIMA         = pytz.timezone("America/Lima")
CACHE_TTL       = 90

MARCAS_HOY   = ["", "A", "A-BM", "A-VAC", "NA-SA", "NA-CA"]
MARCAS_RETRO = ["", "A-BM"]   # días pasados: solo baja médica con sustento

MARCAS_LABELS = {
    "":      "— Sin marca",
    "A":     "✅ Asistió",
    "A-BM":  "🏥 Baja Médica",
    "A-VAC": "🌴 Vacaciones",
    "NA-SA": "❌ No asistió / Sin aviso",
    "NA-CA": "⚠️ No asistió / Con aviso",
}

_CHIP_STYLE: dict[str, str] = {
    "A":     "background:#D1FAE5;color:#065F46",
    "A-BM":  "background:#DBEAFE;color:#1E40AF",
    "A-VAC": "background:#FEF9C3;color:#854D0E",
    "NA-SA": "background:#FEE2E2;color:#991B1B",
    "NA-CA": "background:#FFE4BA;color:#92400E",
    "":      "",
}

BASE_COLS = [
    "RAZON SOCIAL", "SUPERVISOR", "COORDINADOR", "DEPARTAMENTO", "PROVINCIA",
    "DNI", "NOMBRE", "CARGO", "ESTADO", "FECHA_ALTA", "FECHA_CESE", "MES", "PERIODO"
]
DAY_COLS = [f"DIA_{i}" for i in range(1, 32)]
ALL_COLS  = BASE_COLS + DAY_COLS


# =============================================================================
# Utilitarios
# =============================================================================

def hoy_lima() -> date:
    return datetime.now(TZ_LIMA).date()

def periodo_lima() -> str:
    h = hoy_lima()
    return f"{h.year}-{h.month:02d}"

def normalizar_texto(x) -> str:
    if x is None:
        return ""
    s = str(x).strip()
    if s.upper() in {"NAN", "NONE", "NULL"}:
        return ""
    return " ".join(s.split())

def normalizar_razon(x) -> str:
    return normalizar_texto(x).upper().replace(".", "")

def normalizar_dni(x) -> str:
    s = normalizar_texto(x).replace(".0", "").replace(",", "").replace(" ", "")
    return s.zfill(8) if s.isdigit() and len(s) < 8 else s

def parse_fecha(x):
    try:
        if x is None or str(x).strip() == "":
            return None
        f = pd.to_datetime(x, errors="coerce")
        return None if pd.isna(f) else f.date()
    except Exception:
        return None

def fecha_str(x) -> str:
    f = parse_fecha(x)
    return str(f) if f else normalizar_texto(x)

def limpiar_marca(x) -> str:
    v = normalizar_texto(x).upper()
    return v if v in MARCAS_HOY else ""

def _worksheet_key(ws) -> str:
    try:
        return f"{ws.spreadsheet.id}:{ws.id}:{ws.title}"
    except Exception:
        return str(id(ws))

def _letra_col(n: int) -> str:
    out = ""
    while n:
        n, rem = divmod(n - 1, 26)
        out = chr(65 + rem) + out
    return out

def _norm_h(h) -> str:
    return normalizar_texto(h).upper()


# =============================================================================
# Lecturas con caché optimizado — batch_get solo columnas necesarias
# =============================================================================

@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def _leer_header_cached(_ws, ck: str):
    try:
        return [_norm_h(x) for x in _ws.row_values(1)]
    except Exception:
        return []

def leer_header(ws) -> list:
    return _leer_header_cached(ws, _worksheet_key(ws))

@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def _leer_cols_cached(_ws, ck: str, cols_tuple: tuple):
    headers = [_norm_h(x) for x in _ws.row_values(1)]
    if not headers:
        return headers, {}
    h2i = {h: i + 1 for i, h in enumerate(headers) if h}
    ranges, sel = [], []
    for col in cols_tuple:
        cn = _norm_h(col)
        if cn in h2i:
            letra = _letra_col(h2i[cn])
            ranges.append(f"{letra}2:{letra}")
            sel.append(cn)
    if not ranges:
        return headers, {}
    values = _ws.batch_get(ranges)
    data = {}
    for cn, vals in zip(sel, values):
        data[cn] = [normalizar_texto(r[0]) if r else "" for r in vals]
    return headers, data

def limpiar_cache():
    for fn in [_leer_header_cached, _leer_cols_cached]:
        try:
            fn.clear()
        except Exception:
            pass

def df_de_cols(data: dict, row_sheet: bool = False) -> pd.DataFrame:
    if not data:
        return pd.DataFrame()
    max_len = max((len(v) for v in data.values()), default=0)
    fixed   = {k: v + [""] * (max_len - len(v)) for k, v in data.items()}
    df      = pd.DataFrame(fixed)
    if row_sheet:
        df["ROW_SHEET"] = range(2, len(df) + 2)
    return df


# =============================================================================
# Construcción base colaboradores
# =============================================================================

def nombre_from_df(df: pd.DataFrame) -> pd.Series:
    n  = df.get("NOMBRES", pd.Series([""] * len(df))).astype(str).map(normalizar_texto)
    ap = df.get("APELLIDO PATERNO", pd.Series([""] * len(df))).astype(str).map(normalizar_texto)
    am = df.get("APELLIDO MATERNO", pd.Series([""] * len(df))).astype(str).map(normalizar_texto)
    return (n + " " + ap + " " + am).str.replace(r"\s+", " ", regex=True).str.strip()

def _es_d2d(cargo: str) -> bool:
    return "PROMOTOR D2D" in str(cargo).upper().replace("-", " ").replace("  ", " ").strip()

def base_colaboradores(hoja_col, periodo: str, razon: str = "ALL") -> pd.DataFrame:
    cols = (
        "RAZON SOCIAL", "SUPERVISOR A CARGO", "SUPERVISOR", "COORDINADOR",
        "DEPARTAMENTO", "PROVINCIA", "DNI", "NOMBRES", "APELLIDO PATERNO", "APELLIDO MATERNO",
        "ESTADO", "FECHA DE CREACION USUARIO", "FECHA_ALTA", "FECHA DE CESE", "FECHA_CESE",
        "CARGO (ROL)"
    )
    headers, data = _leer_cols_cached(hoja_col, _worksheet_key(hoja_col), cols)
    if not headers or not data:
        return pd.DataFrame(columns=BASE_COLS)
    df = df_de_cols(data)
    if df.empty:
        return pd.DataFrame(columns=BASE_COLS)
    if razon and razon.upper() != "ALL" and "RAZON SOCIAL" in df.columns:
        df = df[df["RAZON SOCIAL"].map(normalizar_razon).eq(normalizar_razon(razon))].copy()
    if "CARGO (ROL)" in df.columns:
        df = df[df["CARGO (ROL)"].astype(str).apply(_es_d2d)].copy()
    if df.empty:
        return pd.DataFrame(columns=BASE_COLS)

    out = pd.DataFrame(index=df.index)
    out["RAZON SOCIAL"] = df.get("RAZON SOCIAL", "").map(normalizar_texto) if "RAZON SOCIAL" in df else ""
    out["SUPERVISOR"]   = (
        df["SUPERVISOR A CARGO"].map(normalizar_texto) if "SUPERVISOR A CARGO" in df.columns
        else df.get("SUPERVISOR", "").map(normalizar_texto) if "SUPERVISOR" in df.columns else ""
    )
    out["COORDINADOR"]  = df.get("COORDINADOR",  "").map(normalizar_texto) if "COORDINADOR"  in df else ""
    out["DEPARTAMENTO"] = df.get("DEPARTAMENTO", "").map(normalizar_texto) if "DEPARTAMENTO" in df else ""
    out["PROVINCIA"]    = df.get("PROVINCIA",    "").map(normalizar_texto) if "PROVINCIA"    in df else ""
    out["DNI"]          = df.get("DNI", "").map(normalizar_dni) if "DNI" in df else ""
    out["NOMBRE"]       = nombre_from_df(df)
    out["CARGO"]        = df.get("CARGO (ROL)", "").map(normalizar_texto) if "CARGO (ROL)" in df else ""
    out["ESTADO"]       = df.get("ESTADO", "ACTIVO").map(lambda x: normalizar_texto(x).upper()) if "ESTADO" in df else "ACTIVO"
    out["FECHA_ALTA"]   = (
        df["FECHA DE CREACION USUARIO"].map(fecha_str) if "FECHA DE CREACION USUARIO" in df.columns
        else df["FECHA_ALTA"].map(fecha_str) if "FECHA_ALTA" in df.columns else ""
    )
    out["FECHA_CESE"]   = (
        df["FECHA DE CESE"].map(fecha_str) if "FECHA DE CESE" in df.columns
        else df["FECHA_CESE"].map(fecha_str) if "FECHA_CESE" in df.columns else ""
    )
    out["MES"]    = str(int(periodo[-2:]))
    out["PERIODO"] = periodo
    out = out[out["DNI"].astype(str).str.strip().ne("")].copy()
    out["KEY"] = out["DNI"] + "|" + out["FECHA_ALTA"] + "|" + periodo
    return out.drop_duplicates("KEY", keep="last")


# =============================================================================
# Lectura asistencia y merge live
# =============================================================================

def leer_asistencia(hoja_asis, periodo: str, col_dia: str, razon: str = "ALL") -> tuple:
    headers = leer_header(hoja_asis)
    if not headers:
        return pd.DataFrame(columns=ALL_COLS + ["ROW_SHEET", "KEY"]), ALL_COLS.copy()
    cols = tuple(BASE_COLS + [col_dia])
    _, data = _leer_cols_cached(hoja_asis, _worksheet_key(hoja_asis), cols)
    df = df_de_cols(data, row_sheet=True)
    if df.empty:
        return pd.DataFrame(columns=ALL_COLS + ["ROW_SHEET", "KEY"]), headers
    for c in BASE_COLS + [col_dia]:
        if c not in df.columns:
            df[c] = ""
    df["DNI"]        = df["DNI"].map(normalizar_dni)
    df["FECHA_ALTA"] = df["FECHA_ALTA"].map(fecha_str)
    df["PERIODO"]    = df["PERIODO"].map(normalizar_texto)
    df = df[df["PERIODO"].eq(periodo)].copy()
    if razon and razon.upper() != "ALL" and "RAZON SOCIAL" in df.columns:
        df = df[df["RAZON SOCIAL"].map(normalizar_razon).eq(normalizar_razon(razon))].copy()
    df["KEY"]   = df["DNI"] + "|" + df["FECHA_ALTA"] + "|" + df["PERIODO"]
    df[col_dia] = df[col_dia].map(limpiar_marca)
    return df, headers

def vista_live(hoja_col, hoja_asis, periodo: str, col_dia: str, razon: str = "ALL") -> tuple:
    base           = base_colaboradores(hoja_col, periodo, razon)
    asis, headers  = leer_asistencia(hoja_asis, periodo, col_dia, razon)
    marcas         = (
        asis[["KEY", "ROW_SHEET", col_dia]].drop_duplicates("KEY", keep="last")
        if not asis.empty
        else pd.DataFrame(columns=["KEY", "ROW_SHEET", col_dia])
    )
    live = base.merge(marcas, on="KEY", how="left", suffixes=("", "_A"))
    live[col_dia]     = live.get(col_dia, "").map(limpiar_marca)
    live["ROW_SHEET"] = live.get("ROW_SHEET", "").fillna("").astype(str)
    return live, headers


# =============================================================================
# Filtros
# =============================================================================

def _opciones(df, col):
    if col not in df.columns:
        return ["TODOS"]
    vals = sorted([v for v in df[col].dropna().astype(str).map(normalizar_texto).unique() if v])
    return ["TODOS"] + vals

def _filtrar(df, sup, coord, dep, prov, estado):
    r = df.copy()
    for col, val in [("SUPERVISOR", sup), ("COORDINADOR", coord),
                     ("DEPARTAMENTO", dep), ("PROVINCIA", prov), ("ESTADO", estado)]:
        if val and val != "TODOS" and col in r.columns:
            r = r[r[col].astype(str).map(normalizar_texto).eq(val)].copy()
    return r

def en_rango(row, fecha_sel: date) -> bool:
    alta   = parse_fecha(row.get("FECHA_ALTA"))
    cese   = parse_fecha(row.get("FECHA_CESE"))
    estado = normalizar_texto(row.get("ESTADO")).upper()
    if alta and fecha_sel < alta:
        return False
    if cese and fecha_sel > cese:
        return False
    if estado != "ACTIVO" and not (cese and fecha_sel <= cese):
        return False
    return True

def periodos_disp():
    h = hoy_lima()
    out = []
    y, m = h.year, h.month
    for i in range(6):
        yy, mm = y, m - i
        while mm <= 0:
            yy -= 1; mm += 12
        out.append(f"{yy}-{mm:02d}")
    return out

def fecha_de_periodo_dia(periodo: str, dia: int) -> date:
    y, m = map(int, periodo.split("-"))
    return date(y, m, min(dia, calendar.monthrange(y, m)[1]))


# =============================================================================
# Escritura Sheets + Drive
# =============================================================================

def guardar_sustento(row, periodo, dia, archivo) -> str:
    if not archivo:
        return ""
    contenido = archivo.getvalue()
    mime      = archivo.type or "application/octet-stream"
    ext       = "pdf" if "pdf" in mime else "jpg"
    dni       = normalizar_dni(row.get("DNI", ""))
    ts        = datetime.now(TZ_LIMA).strftime("%Y%m%d_%H%M%S")
    fname     = f"sustento_ABM_{dni}_{periodo}_DIA{dia}_{ts}.{ext}"
    link      = subir_archivo_drive(fname, contenido, mime)
    cols      = ["PERIODO","DIA","FECHA","DNI","NOMBRE","RAZON SOCIAL",
                 "MOTIVO","LINK","FECHA_SUBIDA","USUARIO"]
    hoja      = obtener_o_crear_worksheet(NOMBRE_LIBRO, HOJA_SUSTENTOS, cols)
    hoja.append_row([
        periodo, f"DIA_{dia}", str(fecha_de_periodo_dia(periodo, dia)),
        dni, row.get("NOMBRE",""), row.get("RAZON SOCIAL",""),
        "A-BM", link, datetime.now(TZ_LIMA).strftime("%Y-%m-%d %H:%M:%S"),
        st.session_state.get("usuario","")
    ], value_input_option="USER_ENTERED")
    return link

def _cabecera_si_vacia(hoja_asis, headers: list) -> list:
    if headers:
        return headers
    hoja_asis.append_row(ALL_COLS, value_input_option="USER_ENTERED")
    limpiar_cache()
    return ALL_COLS.copy()

def guardar_marca(hoja_asis, row: pd.Series, headers: list, col_dia: str, marca: str) -> str:
    headers = [_norm_h(h) for h in headers]
    headers = _cabecera_si_vacia(hoja_asis, headers)
    if col_dia not in headers:
        hoja_asis.update_cell(1, len(headers) + 1, col_dia)
        headers.append(col_dia)
        limpiar_cache()
    rs     = normalizar_texto(row.get("ROW_SHEET", ""))
    ci     = headers.index(col_dia) + 1
    cl     = _letra_col(ci)
    if rs.isdigit():
        hoja_asis.update_acell(f"{cl}{int(rs)}", marca)
        limpiar_cache()
        return "actualizado"
    nueva = [row.get(h, "") if h in BASE_COLS else (marca if h == col_dia else "") for h in headers]
    hoja_asis.append_row(nueva, value_input_option="USER_ENTERED")
    limpiar_cache()
    return "nuevo"

def registrar_alta_en_asistencia(hoja_asis, campos: dict) -> str:
    try:
        limpiar_cache()
        return f"Colaborador DNI {campos.get('DNI','')} disponible en Presencialidad."
    except Exception as e:
        return f"Recarga Presencialidad para ver al colaborador ({e})."


# =============================================================================
# CSS global del módulo
# =============================================================================

_CSS = """
<style>
/* ── Leyenda ── */
.asis-leyenda { display:flex; flex-wrap:wrap; gap:6px; margin:4px 0 10px; }
.asis-chip { padding:3px 11px; border-radius:20px; font-size:11px; font-weight:600; white-space:nowrap; border:1px solid rgba(0,0,0,.06); }
.chip-A    { background:#D1FAE5; color:#065F46; }
.chip-BM   { background:#DBEAFE; color:#1E40AF; }
.chip-VAC  { background:#FEF9C3; color:#854D0E; }
.chip-NASA { background:#FEE2E2; color:#991B1B; }
.chip-NACA { background:#FFE4BA; color:#92400E; }

/* ── Métricas ── */
.asis-metrics { display:grid; grid-template-columns:repeat(4,1fr); gap:10px; margin:10px 0; }
.asis-metric {
    background:white; border:1px solid #E5E0EA; border-radius:12px;
    padding:12px 16px 10px; text-align:center;
    box-shadow:0 1px 3px rgba(75,0,103,.06);
}
.asis-metric .v { font-size:26px; font-weight:800; color:#4B0067; line-height:1; }
.asis-metric .l { font-size:11px; color:#6B6175; margin-top:4px; }
.asis-metric.m-ok .v  { color:#065F46; }
.asis-metric.m-pen .v { color:#92400E; }
.asis-metric.m-tot .v { color:#1E40AF; }

/* ── Banner retroactivo ── */
.retro-banner {
    background:#FFF7ED; border:1.5px solid #FED7AA; border-radius:10px;
    padding:10px 16px; font-size:12.5px; color:#92400E; margin:6px 0 10px;
    display:flex; align-items:center; gap:8px;
}

/* ── Bloque de guardado A-BM ── */
.bm-box {
    background:#EFF6FF; border:1.5px solid #BFDBFE; border-radius:12px;
    padding:14px 18px; margin:8px 0;
}
.bm-box-title { font-size:12px; font-weight:700; color:#1E40AF; margin-bottom:8px; }

/* ── Jerarquía stats ── */
.jer-stats { display:flex; flex-wrap:wrap; gap:10px; margin:10px 0 14px; }
.jer-stat {
    flex:1; min-width:120px;
    background:white; border:1px solid #E5E0EA; border-radius:10px;
    padding:10px 14px; text-align:center;
    box-shadow:0 1px 3px rgba(75,0,103,.06);
}
.jer-stat .sv { font-size:20px; font-weight:800; color:#4B0067; line-height:1.1; }
.jer-stat .sl { font-size:10.5px; color:#6B6175; margin-top:3px; font-weight:600; text-transform:uppercase; letter-spacing:.4px; }

/* ── Tabla jerarquía HTML ── */
.jer-wrap {
    width:100%; overflow-x:auto; overflow-y:auto; max-height:500px;
    border-radius:10px; border:1px solid #E5E0EA; margin:4px 0;
}
.jer-table { width:100%; border-collapse:collapse; font-size:12.5px; font-family:inherit; }
.jer-table thead th {
    position:sticky; top:0; z-index:2;
    background:linear-gradient(135deg,#4B0067,#3a0052);
    color:white; padding:9px 12px; text-align:left;
    font-size:11px; font-weight:700; letter-spacing:.5px; white-space:nowrap;
}
.jer-table tbody tr { border-bottom:1px solid #F2EEF5; }
.jer-table tbody tr:hover { background:#FAF3FE; }
.jer-table tbody td { padding:7px 12px; color:#1A1521; white-space:nowrap; }
.jer-table tbody td.nm { white-space:normal; min-width:160px; }
.jr-badge-a { background:#D1FAE5; color:#065F46; padding:1px 8px; border-radius:10px; font-size:10.5px; font-weight:700; }
.jr-badge-i { background:#FEE2E2; color:#991B1B; padding:1px 8px; border-radius:10px; font-size:10.5px; font-weight:700; }

/* ── Sync banner ── */
.sync-info { background:#EFF6FF; border:1px solid #BFDBFE; border-radius:10px; padding:8px 14px; font-size:12px; color:#1E40AF; margin:4px 0; }
</style>
"""


def _leyenda():
    return """<div class='asis-leyenda'>
<span class='asis-chip chip-A'>✅ A — Asistió</span>
<span class='asis-chip chip-BM'>🏥 A-BM — Baja Médica</span>
<span class='asis-chip chip-VAC'>🌴 A-VAC — Vacaciones</span>
<span class='asis-chip chip-NASA'>❌ NA-SA — Sin aviso</span>
<span class='asis-chip chip-NACA'>⚠️ NA-CA — Con aviso</span>
</div>"""


def _metricas_html(total, editables, marcados, pendientes):
    return f"""<div class='asis-metrics'>
<div class='asis-metric m-tot'><div class='v'>{total}</div><div class='l'>👥 Total filtrado</div></div>
<div class='asis-metric'><div class='v'>{editables}</div><div class='l'>✏️ Editables</div></div>
<div class='asis-metric m-ok'><div class='v'>{marcados}</div><div class='l'>✅ Marcados</div></div>
<div class='asis-metric m-pen'><div class='v'>{pendientes}</div><div class='l'>⏳ Pendientes</div></div>
</div>"""


def _tabla_jerarquia_html(df: pd.DataFrame) -> str:
    cols = ["RAZON SOCIAL","DNI","NOMBRE","SUPERVISOR","COORDINADOR",
            "DEPARTAMENTO","PROVINCIA","ESTADO","FECHA_ALTA","FECHA_CESE"]
    cols = [c for c in cols if c in df.columns]
    labels = {"RAZON SOCIAL":"Razón Social","DNI":"DNI","NOMBRE":"Nombre",
              "SUPERVISOR":"Supervisor","COORDINADOR":"Coordinador",
              "DEPARTAMENTO":"Departamento","PROVINCIA":"Provincia",
              "ESTADO":"Estado","FECHA_ALTA":"Alta","FECHA_CESE":"Cese"}
    thead = "".join(f"<th>{labels.get(c,c)}</th>" for c in cols)
    rows  = []
    for _, r in df.iterrows():
        cells = []
        for c in cols:
            v = str(r.get(c,"") or "").strip()
            if c == "ESTADO":
                cls = "jr-badge-a" if v.upper()=="ACTIVO" else "jr-badge-i"
                cells.append(f"<td><span class='{cls}'>{v or '—'}</span></td>")
            elif c == "NOMBRE":
                cells.append(f"<td class='nm'>{v or '—'}</td>")
            else:
                cells.append(f"<td>{v or '—'}</td>")
        rows.append("<tr>"+"".join(cells)+"</tr>")
    tbody = "".join(rows)
    return (f"<div class='jer-wrap'><table class='jer-table'>"
            f"<thead><tr>{thead}</tr></thead><tbody>{tbody}</tbody>"
            f"</table></div>")


def _stats_jerarquia(df: pd.DataFrame) -> str:
    total   = len(df)
    activos = int((df.get("ESTADO","").astype(str).str.upper() == "ACTIVO").sum()) if "ESTADO" in df.columns else 0
    inact   = total - activos
    sups    = df["SUPERVISOR"].nunique() if "SUPERVISOR" in df.columns else 0
    deps    = df["DEPARTAMENTO"].nunique() if "DEPARTAMENTO" in df.columns else 0
    return f"""<div class='jer-stats'>
<div class='jer-stat'><div class='sv'>{total}</div><div class='sl'>Total registros</div></div>
<div class='jer-stat'><div class='sv' style='color:#065F46'>{activos}</div><div class='sl'>Activos</div></div>
<div class='jer-stat'><div class='sv' style='color:#991B1B'>{inact}</div><div class='sl'>Inactivos</div></div>
<div class='jer-stat'><div class='sv'>{sups}</div><div class='sl'>Supervisores</div></div>
<div class='jer-stat'><div class='sv'>{deps}</div><div class='sl'>Departamentos</div></div>
</div>"""


# =============================================================================
# UI Principal
# =============================================================================

def mostrar_asistencia(hoja_asistencia, hoja_colaboradores, registro_mod=None, razon=None):
    st.markdown(_CSS, unsafe_allow_html=True)
    st.markdown("<span class='wow-section-title'>🗓️ Presencialidad Dealer</span>", unsafe_allow_html=True)

    usuario_razon = normalizar_texto(razon if razon is not None else st.session_state.get("razon","ALL"))
    es_dealer     = bool(usuario_razon and usuario_razon.upper() != "ALL")

    # ── Control: Periodo · Día · Sincronizar ────────────────────────────────
    c1, c2, c3 = st.columns([1.5, 1.5, 0.7])
    with c1:
        periodo = st.selectbox("📅 Periodo", periodos_disp(), index=0, key="asis_periodo")
    y, m  = map(int, periodo.split("-"))
    dias  = list(range(1, calendar.monthrange(y, m)[1] + 1))
    dd    = hoy_lima().day if periodo == periodo_lima() and hoy_lima().day in dias else 1
    with c2:
        dia = st.selectbox("📆 Día", dias, index=dias.index(dd), key="asis_dia")
    with c3:
        st.markdown("<div style='height:26px'></div>", unsafe_allow_html=True)
        if st.button("🔄 Sincronizar", key="btn_sync",
                     help="Releer desde Drive — útil tras altas/bajas en otro módulo o edición manual en Sheets"):
            limpiar_cache()
            for k in [k for k in st.session_state if k.startswith("asis_edit_")]:
                del st.session_state[k]
            st.rerun()

    col_dia   = f"DIA_{dia}"
    fecha_sel = fecha_de_periodo_dia(periodo, dia)
    es_retro  = fecha_sel < hoy_lima()

    st.markdown(_leyenda(), unsafe_allow_html=True)

    if es_retro:
        st.markdown(
            "<div class='retro-banner'>⚠️ <b>Fecha retroactiva</b> — "
            "Solo se puede marcar <b>A-BM (Baja Médica)</b> con sustento adjunto. "
            "Aplica a cualquier día o mes anterior.</div>",
            unsafe_allow_html=True
        )

    # ── Carga ───────────────────────────────────────────────────────────────
    with st.spinner("⏳ Cargando datos desde Drive…"):
        try:
            df_live, headers = vista_live(
                hoja_colaboradores, hoja_asistencia, periodo, col_dia,
                usuario_razon if es_dealer else "ALL"
            )
        except Exception as e:
            st.error(f"Error al cargar presencialidad: {e}")
            st.markdown("<div class='sync-info'>💡 Usa <b>🔄 Sincronizar</b> si acabas de hacer altas/bajas en otro módulo.</div>", unsafe_allow_html=True)
            return

    if df_live.empty:
        st.warning("No hay promotores D2D para este usuario/periodo.")
        st.markdown("<div class='sync-info'>💡 Si recién ingresaste un alta, usa <b>🔄 Sincronizar</b>.</div>", unsafe_allow_html=True)
        return

    # ── Filtros ──────────────────────────────────────────────────────────────
    with st.expander("🔍 Filtros", expanded=False):
        with st.form("form_filtros", clear_on_submit=False):
            fa, fb, fc = st.columns([1.5,1,1])
            with fa:
                buscar = st.text_input("DNI / nombre / supervisor", placeholder="Ej: 12345678")
            with fb:
                f_sup   = st.selectbox("Supervisor",   _opciones(df_live,"SUPERVISOR"),   index=0)
            with fc:
                f_coord = st.selectbox("Coordinador",  _opciones(df_live,"COORDINADOR"),  index=0)
            fd, fe, ff = st.columns(3)
            with fd:
                f_dep    = st.selectbox("Departamento", _opciones(df_live,"DEPARTAMENTO"), index=0)
            with fe:
                f_prov   = st.selectbox("Provincia",    _opciones(df_live,"PROVINCIA"),    index=0)
            with ff:
                f_estado = st.selectbox("Estado",       _opciones(df_live,"ESTADO"),       index=0)
            st.form_submit_button("🔎 Aplicar", use_container_width=True)

    df_f = _filtrar(df_live, f_sup, f_coord, f_dep, f_prov, f_estado)
    q    = normalizar_texto(buscar).upper() if "buscar" in dir() else ""
    if q:
        mask = pd.Series(False, index=df_f.index)
        for c in ["DNI","NOMBRE","SUPERVISOR","COORDINADOR","DEPARTAMENTO","PROVINCIA"]:
            if c in df_f.columns:
                mask |= df_f[c].astype(str).str.upper().str.contains(q, na=False)
        df_f = df_f[mask].copy()

    if df_f.empty:
        st.warning("Sin resultados con los filtros aplicados.")
        return

    df_f["_en_rango"] = df_f.apply(lambda r: en_rango(r, fecha_sel), axis=1)

    # Métricas
    total     = len(df_f)
    edit_mask = df_f["_en_rango"]
    editables = int(edit_mask.sum())
    marcados  = int((df_f.loc[edit_mask, col_dia].ne("")).sum()) if editables else 0
    pendientes = editables - marcados

    st.markdown(_metricas_html(total, editables, marcados, pendientes), unsafe_allow_html=True)

    # ═══════════════════════════════════════════════════════════════════════
    # BLOQUE 1 — data_editor con columna DIA_X inline (selectbox por fila)
    # ═══════════════════════════════════════════════════════════════════════
    st.markdown(
        f"<span class='wow-section-title'>📋 Lista de personal — marcación {col_dia} inline</span>",
        unsafe_allow_html=True
    )
    st.caption(
        f"Edita la columna **{col_dia}** directamente. "
        "En fechas pasadas solo aparece A-BM. Presiona **💾 Guardar marcaciones** cuando termines."
    )

    # Preparar DataFrame para el editor
    cols_editor = ["DNI","NOMBRE","SUPERVISOR","COORDINADOR",
                   "DEPARTAMENTO","PROVINCIA","ESTADO","FECHA_ALTA","FECHA_CESE", col_dia]
    for c in cols_editor:
        if c not in df_f.columns:
            df_f[c] = ""

    # La marca disponible depende de si es retroactivo
    marcas_sel = MARCAS_RETRO if es_retro else MARCAS_HOY

    # Bloquear edición de filas fuera de rango
    df_edit = df_f[cols_editor + ["_en_rango","KEY","ROW_SHEET"]].copy()
    df_edit[col_dia] = df_edit[col_dia].apply(limpiar_marca)

    # Solo filas en rango son editables; las demás se muestran igual pero bloqueadas
    df_editables_mask = df_edit["_en_rango"]
    df_para_editor    = df_edit[cols_editor].reset_index(drop=True)
    keys_list         = df_edit["KEY"].reset_index(drop=True)
    row_sheet_list    = df_edit["ROW_SHEET"].reset_index(drop=True)
    en_rango_list     = df_edit["_en_rango"].reset_index(drop=True)

    LIMITE = 300
    if len(df_para_editor) > LIMITE:
        st.caption(f"Mostrando {LIMITE} de {len(df_para_editor)} registros. Usa filtros para acotar.")
        df_para_editor = df_para_editor.head(LIMITE)
        keys_list      = keys_list.head(LIMITE)
        row_sheet_list = row_sheet_list.head(LIMITE)
        en_rango_list  = en_rango_list.head(LIMITE)

    # Configuración de columnas del editor
    col_cfg = {
        "DNI":          st.column_config.TextColumn("DNI", disabled=True, width="small"),
        "NOMBRE":       st.column_config.TextColumn("Nombre", disabled=True, width="large"),
        "SUPERVISOR":   st.column_config.TextColumn("Supervisor", disabled=True),
        "COORDINADOR":  st.column_config.TextColumn("Coordinador", disabled=True),
        "DEPARTAMENTO": st.column_config.TextColumn("Departamento", disabled=True),
        "PROVINCIA":    st.column_config.TextColumn("Provincia", disabled=True),
        "ESTADO":       st.column_config.TextColumn("Estado", disabled=True, width="small"),
        "FECHA_ALTA":   st.column_config.TextColumn("Alta", disabled=True, width="small"),
        "FECHA_CESE":   st.column_config.TextColumn("Cese", disabled=True, width="small"),
        col_dia: st.column_config.SelectboxColumn(
            col_dia,
            options=marcas_sel,
            required=False,
            width="small",
        ),
    }

    editor_key = f"asis_editor_{periodo}_{dia}"
    df_edited  = st.data_editor(
        df_para_editor,
        column_config=col_cfg,
        use_container_width=True,
        hide_index=True,
        height=min(540, 56 + len(df_para_editor) * 35),
        key=editor_key,
        num_rows="fixed",
    )

    # ═══════════════════════════════════════════════════════════════════════
    # Detectar cambios y guardar
    # ═══════════════════════════════════════════════════════════════════════

    # Cambios: filas donde DIA_x difiere entre original y editado
    cambios = []
    for i in range(len(df_para_editor)):
        marca_orig  = limpiar_marca(df_para_editor.iloc[i].get(col_dia,""))
        marca_nueva = limpiar_marca(df_edited.iloc[i].get(col_dia,"") if df_edited is not None else "")
        if marca_nueva != marca_orig and en_rango_list.iloc[i]:
            if es_retro and marca_nueva not in MARCAS_RETRO:
                continue   # silenciosamente ignorar si no es A-BM en retroactivo
            cambios.append({
                "idx":        i,
                "key":        keys_list.iloc[i],
                "row_sheet":  row_sheet_list.iloc[i],
                "nombre":     df_para_editor.iloc[i].get("NOMBRE",""),
                "dni":        df_para_editor.iloc[i].get("DNI",""),
                "marca_orig": marca_orig,
                "marca_nueva":marca_nueva,
                "row_data":   df_live[df_live["KEY"] == keys_list.iloc[i]].iloc[0].to_dict()
                              if not df_live[df_live["KEY"] == keys_list.iloc[i]].empty else {},
            })

    # Panel de guardado — se muestra solo si hay cambios pendientes
    if cambios:
        n_bm     = sum(1 for c in cambios if c["marca_nueva"] == "A-BM")
        n_otros  = len(cambios) - n_bm

        if n_bm > 0:
            st.markdown(
                f"<div class='bm-box'>"
                f"<div class='bm-box-title'>🏥 {n_bm} marca(s) A-BM — adjunta los sustentos antes de guardar</div>",
                unsafe_allow_html=True
            )
            archivos_bm = {}
            for c in cambios:
                if c["marca_nueva"] == "A-BM":
                    dni_c = c["dni"]
                    nombre_c = normalizar_texto(c["nombre"])
                    f = st.file_uploader(
                        f"Sustento para {dni_c} — {nombre_c}",
                        type=["pdf","png","jpg","jpeg"],
                        key=f"file_bm_{periodo}_{dia}_{dni_c}",
                    )
                    archivos_bm[c["key"]] = f
            st.markdown("</div>", unsafe_allow_html=True)
        else:
            archivos_bm = {}

        if n_otros > 0:
            st.info(
                f"📝 **{n_otros}** cambio(s) listos para guardar: "
                + ", ".join(f"{c['dni']} → {c['marca_nueva']}" for c in cambios if c['marca_nueva'] != 'A-BM')
            )

        guardar_btn = st.button(
            f"💾 Guardar {len(cambios)} marcación(es)",
            key="btn_guardar",
            type="primary",
            use_container_width=True,
        )

        if guardar_btn:
            errores = []
            exitos  = []
            for c in cambios:
                try:
                    if c["marca_nueva"] == "A-BM":
                        archivo = archivos_bm.get(c["key"])
                        if not archivo:
                            errores.append(f"⛔ {c['dni']}: falta sustento A-BM.")
                            continue
                        with st.spinner(f"📤 Subiendo sustento {c['dni']}…"):
                            guardar_sustento(c["row_data"], periodo, dia, archivo)

                    row_serie = pd.Series(c["row_data"])
                    row_serie["ROW_SHEET"] = c["row_sheet"]
                    with st.spinner(f"💾 Guardando {c['dni']} → {c['marca_nueva']}…"):
                        res = guardar_marca(hoja_asistencia, row_serie, headers, col_dia, c["marca_nueva"])
                    exitos.append(f"✅ {c['dni']} ({normalizar_texto(c['nombre'])}) → **{c['marca_nueva']}** ({res})")
                except Exception as e:
                    errores.append(f"❌ {c['dni']}: {e}")

            for msg in exitos:
                st.success(msg)
            for msg in errores:
                st.error(msg)
            if exitos:
                st.rerun()
    else:
        st.caption("✔ Sin cambios pendientes. Edita la columna " + col_dia + " en la tabla de arriba y guarda aquí.")

    # ═══════════════════════════════════════════════════════════════════════
    # BLOQUE 2 — Espejo marcaciones del día
    # ═══════════════════════════════════════════════════════════════════════
    ya_marcados = df_f[df_f[col_dia].ne("")] if col_dia in df_f.columns else pd.DataFrame()
    with st.expander(f"📊 Marcaciones registradas hoy — {col_dia} ({len(ya_marcados)} de {total})", expanded=False):
        if ya_marcados.empty:
            st.info("Aún no hay marcaciones para este día.")
        else:
            cols_esp = ["DNI","NOMBRE","SUPERVISOR","DEPARTAMENTO","PROVINCIA","ESTADO",col_dia]
            cols_esp = [c for c in cols_esp if c in ya_marcados.columns]
            st.dataframe(
                ya_marcados[cols_esp].reset_index(drop=True),
                use_container_width=True, hide_index=True, height=360,
                column_config={
                    "DNI":    st.column_config.TextColumn("DNI"),
                    "NOMBRE": st.column_config.TextColumn("Nombre", width="large"),
                    col_dia:  st.column_config.TextColumn(col_dia, width="small"),
                }
            )

    # ═══════════════════════════════════════════════════════════════════════
    # BLOQUE 3 — Jerarquía completa rediseñada
    # ═══════════════════════════════════════════════════════════════════════
    st.divider()
    st.markdown(
        "<span class='wow-section-title'>📋 Jerarquía completa de promotores D2D</span>",
        unsafe_allow_html=True
    )
    st.caption("Datos en memoria — misma lectura, sin llamada adicional a Drive.")
    st.markdown(_stats_jerarquia(df_live), unsafe_allow_html=True)
    st.markdown(_tabla_jerarquia_html(df_live), unsafe_allow_html=True)
    st.caption(f"Total en base: **{len(df_live)}** promotores D2D del socio.")
