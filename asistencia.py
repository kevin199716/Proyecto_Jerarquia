# ASISTENCIA_V5_HTML_TABLE_20260601
# ─────────────────────────────────────────────────────────────────────────────
# CAMBIOS vs V4:
# 1. Tabla principal = HTML puro con scroll — nunca inputs editables en celdas
#    La columna DIA_X muestra chips de color dentro de la misma fila
# 2. Panel de marcación integrado EN LA MISMA SECCIÓN (no debajo), 3 columnas
# 3. Actualización inline en session_state — sin recargar Drive al guardar
# 4. Robusto ante altas manuales/por otro módulo: botón Sincronizar limpia caché
# 5. Errores manejados con retry suave, sin crash para el usuario
# 6. Paginación virtual: muestra 100 filas, scroll interno, cero inputs fantasma
# ─────────────────────────────────────────────────────────────────────────────

import calendar
import pytz
from datetime import datetime, date

import pandas as pd
import streamlit as st
from sheets import subir_archivo_drive, obtener_o_crear_worksheet

NOMBRE_LIBRO     = "maestra_vendedores"
HOJA_SUSTENTOS   = "Sustentos_Bajas"
TZ_LIMA          = pytz.timezone("America/Lima")
CACHE_TTL_SECONDS = 90

MARCAS = ["", "A", "A-BM", "A-VAC", "NA-SA", "NA-CA"]
MARCAS_LABELS = {
    "A":     "✅ A — Asistió",
    "A-BM":  "🏥 A-BM — Baja Médica",
    "A-VAC": "🌴 A-VAC — Vacaciones",
    "NA-SA": "❌ NA-SA — Sin aviso",
    "NA-CA": "⚠️ NA-CA — Con aviso",
}

# Colores semáforo para chips en tabla HTML
_CHIP_CSS: dict[str, str] = {
    "A":     "background:#D1FAE5;color:#065F46",
    "A-BM":  "background:#DBEAFE;color:#1E40AF",
    "A-VAC": "background:#FEF9C3;color:#854D0E",
    "NA-SA": "background:#FEE2E2;color:#991B1B",
    "NA-CA": "background:#FFE4BA;color:#92400E",
    "":      "background:#F1F5F9;color:#6B6175",
}

BASE_COLS = [
    "RAZON SOCIAL", "SUPERVISOR", "COORDINADOR", "DEPARTAMENTO", "PROVINCIA",
    "DNI", "NOMBRE", "CARGO", "ESTADO", "FECHA_ALTA", "FECHA_CESE", "MES", "PERIODO"
]
DAY_COLS = [f"DIA_{i}" for i in range(1, 32)]
ALL_COLS = BASE_COLS + DAY_COLS


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
    return v if v in MARCAS else ""

def _worksheet_key(worksheet) -> str:
    try:
        return f"{worksheet.spreadsheet.id}:{worksheet.id}:{worksheet.title}"
    except Exception:
        return str(id(worksheet))

def _letra_col(n: int) -> str:
    out = ""
    while n:
        n, rem = divmod(n - 1, 26)
        out = chr(65 + rem) + out
    return out

def _norm_header(h) -> str:
    return normalizar_texto(h).upper()


# =============================================================================
# Lecturas optimizadas — batch_get, caché 90 s
# =============================================================================

@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def _leer_header_cached(_worksheet, cache_key: str):
    try:
        return [_norm_header(x) for x in _worksheet.row_values(1)]
    except Exception:
        return []

def leer_header(worksheet) -> list:
    return _leer_header_cached(worksheet, _worksheet_key(worksheet))

@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def _leer_columnas_cached(_worksheet, cache_key: str, columnas_tuple: tuple):
    headers = [_norm_header(x) for x in _worksheet.row_values(1)]
    if not headers:
        return headers, {}
    header_to_index = {h: i + 1 for i, h in enumerate(headers) if h}
    ranges, selected = [], []
    for col in columnas_tuple:
        coln = _norm_header(col)
        if coln in header_to_index:
            letra = _letra_col(header_to_index[coln])
            ranges.append(f"{letra}2:{letra}")
            selected.append(coln)
    if not ranges:
        return headers, {}
    values = _worksheet.batch_get(ranges)
    data = {}
    for coln, vals in zip(selected, values):
        data[coln] = [normalizar_texto(r[0]) if r else "" for r in vals]
    return headers, data

def limpiar_cache_asistencia():
    for fn in [_leer_header_cached, _leer_columnas_cached]:
        try:
            fn.clear()
        except Exception:
            pass

def df_desde_columnas(data: dict, extra_row_sheet: bool = False) -> pd.DataFrame:
    if not data:
        return pd.DataFrame()
    max_len = max((len(v) for v in data.values()), default=0)
    fixed = {k: v + [""] * (max_len - len(v)) for k, v in data.items()}
    df = pd.DataFrame(fixed)
    if extra_row_sheet:
        df["ROW_SHEET"] = range(2, len(df) + 2)
    return df


# =============================================================================
# Construcción de base colaboradores
# =============================================================================

def nombre_colaborador_from_df(df: pd.DataFrame) -> pd.Series:
    n  = df.get("NOMBRES", pd.Series([""] * len(df))).astype(str).map(normalizar_texto)
    ap = df.get("APELLIDO PATERNO", pd.Series([""] * len(df))).astype(str).map(normalizar_texto)
    am = df.get("APELLIDO MATERNO", pd.Series([""] * len(df))).astype(str).map(normalizar_texto)
    return (n + " " + ap + " " + am).str.replace(r"\s+", " ", regex=True).str.strip()

def _es_cargo_presencialidad(cargo_str: str) -> bool:
    return "PROMOTOR D2D" in str(cargo_str).upper().replace("-", " ").replace("  ", " ").strip()

def construir_base_colaboradores(hoja_colaboradores, periodo: str, razon_usuario: str = "ALL") -> pd.DataFrame:
    columnas_necesarias = (
        "RAZON SOCIAL", "SUPERVISOR A CARGO", "SUPERVISOR", "COORDINADOR",
        "DEPARTAMENTO", "PROVINCIA", "DNI", "NOMBRES", "APELLIDO PATERNO", "APELLIDO MATERNO",
        "ESTADO", "FECHA DE CREACION USUARIO", "FECHA_ALTA", "FECHA DE CESE", "FECHA_CESE",
        "CARGO (ROL)"
    )
    headers, data = _leer_columnas_cached(
        hoja_colaboradores, _worksheet_key(hoja_colaboradores), columnas_necesarias
    )
    if not headers or not data:
        return pd.DataFrame(columns=BASE_COLS)
    df = df_desde_columnas(data)
    if df.empty:
        return pd.DataFrame(columns=BASE_COLS)
    if razon_usuario and razon_usuario.upper() != "ALL" and "RAZON SOCIAL" in df.columns:
        df = df[df["RAZON SOCIAL"].map(normalizar_razon).eq(normalizar_razon(razon_usuario))].copy()
    if "CARGO (ROL)" in df.columns:
        df = df[df["CARGO (ROL)"].astype(str).apply(_es_cargo_presencialidad)].copy()
    if df.empty:
        return pd.DataFrame(columns=BASE_COLS)
    out = pd.DataFrame(index=df.index)
    out["RAZON SOCIAL"] = df.get("RAZON SOCIAL", "").map(normalizar_texto) if "RAZON SOCIAL" in df else ""
    out["SUPERVISOR"] = (
        df["SUPERVISOR A CARGO"].map(normalizar_texto) if "SUPERVISOR A CARGO" in df.columns
        else df.get("SUPERVISOR", "").map(normalizar_texto) if "SUPERVISOR" in df.columns else ""
    )
    out["COORDINADOR"]  = df.get("COORDINADOR", "").map(normalizar_texto)  if "COORDINADOR"  in df else ""
    out["DEPARTAMENTO"] = df.get("DEPARTAMENTO", "").map(normalizar_texto) if "DEPARTAMENTO" in df else ""
    out["PROVINCIA"]    = df.get("PROVINCIA", "").map(normalizar_texto)    if "PROVINCIA"    in df else ""
    out["DNI"]          = df.get("DNI", "").map(normalizar_dni)            if "DNI"          in df else ""
    out["NOMBRE"]       = nombre_colaborador_from_df(df)
    out["CARGO"]        = df.get("CARGO (ROL)", "").map(normalizar_texto)  if "CARGO (ROL)"  in df else ""
    out["ESTADO"]       = df.get("ESTADO", "ACTIVO").map(lambda x: normalizar_texto(x).upper()) if "ESTADO" in df else "ACTIVO"
    out["FECHA_ALTA"] = (
        df["FECHA DE CREACION USUARIO"].map(fecha_str) if "FECHA DE CREACION USUARIO" in df.columns
        else df["FECHA_ALTA"].map(fecha_str) if "FECHA_ALTA" in df.columns else ""
    )
    out["FECHA_CESE"] = (
        df["FECHA DE CESE"].map(fecha_str) if "FECHA DE CESE" in df.columns
        else df["FECHA_CESE"].map(fecha_str) if "FECHA_CESE" in df.columns else ""
    )
    out["MES"]    = str(int(periodo[-2:]))
    out["PERIODO"] = periodo
    out = out[out["DNI"].astype(str).str.strip().ne("")].copy()
    out["KEY"] = out["DNI"].astype(str) + "|" + out["FECHA_ALTA"].astype(str) + "|" + periodo
    out = out.drop_duplicates("KEY", keep="last")
    return out


# =============================================================================
# Lectura asistencia y vista live
# =============================================================================

def leer_asistencia(hoja_asistencia, periodo: str, col_dia: str, razon_usuario: str = "ALL") -> tuple:
    headers = leer_header(hoja_asistencia)
    if not headers:
        return pd.DataFrame(columns=ALL_COLS + ["ROW_SHEET", "KEY"]), ALL_COLS.copy()
    cols = tuple(BASE_COLS + [col_dia])
    _headers, data = _leer_columnas_cached(hoja_asistencia, _worksheet_key(hoja_asistencia), cols)
    df = df_desde_columnas(data, extra_row_sheet=True)
    if df.empty:
        return pd.DataFrame(columns=ALL_COLS + ["ROW_SHEET", "KEY"]), headers
    for c in BASE_COLS + [col_dia]:
        if c not in df.columns:
            df[c] = ""
    df["DNI"]        = df["DNI"].map(normalizar_dni)
    df["FECHA_ALTA"] = df["FECHA_ALTA"].map(fecha_str)
    df["PERIODO"]    = df["PERIODO"].map(normalizar_texto)
    df = df[df["PERIODO"].astype(str).eq(periodo)].copy()
    if razon_usuario and razon_usuario.upper() != "ALL" and "RAZON SOCIAL" in df.columns:
        df = df[df["RAZON SOCIAL"].map(normalizar_razon).eq(normalizar_razon(razon_usuario))].copy()
    df["KEY"]   = df["DNI"].astype(str) + "|" + df["FECHA_ALTA"].astype(str) + "|" + df["PERIODO"].astype(str)
    df[col_dia] = df[col_dia].map(limpiar_marca)
    return df, headers

def vista_live(hoja_colaboradores, hoja_asistencia, periodo: str, col_dia: str, razon_usuario: str = "ALL") -> tuple:
    base    = construir_base_colaboradores(hoja_colaboradores, periodo, razon_usuario)
    asis_p, headers = leer_asistencia(hoja_asistencia, periodo, col_dia, razon_usuario)
    marcas  = (
        asis_p[["KEY", "ROW_SHEET", col_dia]].drop_duplicates("KEY", keep="last")
        if not asis_p.empty
        else pd.DataFrame(columns=["KEY", "ROW_SHEET", col_dia])
    )
    live = base.merge(marcas, on="KEY", how="left", suffixes=("", "_ASIS"))
    live[col_dia]     = live.get(col_dia, "").map(limpiar_marca)
    live["ROW_SHEET"] = live.get("ROW_SHEET", "").fillna("")
    return live, headers


# =============================================================================
# Filtros y validaciones
# =============================================================================

def opciones(df, col):
    if col not in df.columns:
        return ["TODOS"]
    vals = sorted([v for v in df[col].dropna().astype(str).map(normalizar_texto).unique() if v])
    return ["TODOS"] + vals

def filtrar(df, razon, sup, coord, dep, prov, estado):
    r = df.copy()
    for col, val in [("RAZON SOCIAL", razon), ("SUPERVISOR", sup), ("COORDINADOR", coord),
                     ("DEPARTAMENTO", dep), ("PROVINCIA", prov), ("ESTADO", estado)]:
        if val and val != "TODOS" and col in r.columns:
            r = r[r[col].astype(str).map(normalizar_texto).eq(val)].copy()
    return r

def editable_en_fecha(row, fecha_sel: date) -> bool:
    """True si el colaborador puede tener asistencia en esa fecha (rango alta/cese/estado)."""
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

def periodos_disponibles():
    h = hoy_lima()
    periodos = []
    y, m = h.year, h.month
    for i in range(6):   # 6 meses para retroactivos A-BM
        yy, mm = y, m - i
        while mm <= 0:
            yy -= 1
            mm += 12
        periodos.append(f"{yy}-{mm:02d}")
    return periodos

def fecha_desde_periodo_dia(periodo: str, dia: int) -> date:
    y, m = map(int, periodo.split("-"))
    return date(y, m, min(int(dia), calendar.monthrange(y, m)[1]))


# =============================================================================
# Escritura
# =============================================================================

def guardar_sustento(row, periodo, dia, archivo) -> str:
    if archivo is None:
        return ""
    contenido = archivo.getvalue()
    mime      = archivo.type or "application/octet-stream"
    ext       = "pdf" if mime == "application/pdf" else "jpg"
    dni       = normalizar_dni(row.get("DNI"))
    ts        = datetime.now(TZ_LIMA).strftime("%Y%m%d_%H%M%S")
    nombre_archivo = f"sustento_ABM_{dni}_{periodo}_DIA_{dia}_{ts}.{ext}"
    link = subir_archivo_drive(nombre_archivo, contenido, mime)
    cols = ["PERIODO", "DIA", "FECHA_ASISTENCIA", "DNI", "NOMBRE", "RAZON SOCIAL",
            "MOTIVO", "LINK_DOCUMENTO", "FECHA_SUBIDA", "USUARIO_REGISTRO"]
    hoja = obtener_o_crear_worksheet(NOMBRE_LIBRO, HOJA_SUSTENTOS, cols)
    hoja.append_row([
        periodo, f"DIA_{dia}", str(fecha_desde_periodo_dia(periodo, dia)),
        dni, row.get("NOMBRE", ""), row.get("RAZON SOCIAL", ""),
        "A-BM", link, datetime.now(TZ_LIMA).strftime("%Y-%m-%d %H:%M:%S"),
        st.session_state.get("usuario", "")
    ], value_input_option="USER_ENTERED")
    return link

def garantizar_cabecera_si_vacia(hoja_asistencia, headers: list) -> list:
    if headers:
        return headers
    hoja_asistencia.append_row(ALL_COLS, value_input_option="USER_ENTERED")
    limpiar_cache_asistencia()
    return ALL_COLS.copy()

def guardar_marca(hoja_asistencia, row: pd.Series, headers: list, col_dia: str, marca: str) -> str:
    headers = [_norm_header(h) for h in headers]
    headers = garantizar_cabecera_si_vacia(hoja_asistencia, headers)
    if col_dia not in headers:
        nueva_col = len(headers) + 1
        hoja_asistencia.update_cell(1, nueva_col, col_dia)
        headers.append(col_dia)
        limpiar_cache_asistencia()
    row_sheet = normalizar_texto(row.get("ROW_SHEET"))
    col_idx   = headers.index(col_dia) + 1
    col_letra = _letra_col(col_idx)
    if row_sheet.isdigit():
        hoja_asistencia.update_acell(f"{col_letra}{int(row_sheet)}", marca)
        limpiar_cache_asistencia()
        return "actualizado"
    nueva = []
    for h in headers:
        nueva.append(row.get(h, "") if h in BASE_COLS else (marca if h == col_dia else ""))
    hoja_asistencia.append_row(nueva, value_input_option="USER_ENTERED")
    limpiar_cache_asistencia()
    return "nuevo"

def registrar_alta_en_asistencia(hoja_asistencia, campos: dict) -> str:
    try:
        limpiar_cache_asistencia()
        dni    = campos.get("DNI", "")
        nombre = " ".join([
            campos.get("NOMBRES", ""),
            campos.get("APELLIDO PATERNO", ""),
            campos.get("APELLIDO MATERNO", ""),
        ]).strip()
        return f"Colaborador DNI {dni} – {nombre} disponible en Presencialidad Dealer."
    except Exception as e:
        return f"Recarga Presencialidad para ver al colaborador ({e})."


# =============================================================================
# CSS global
# =============================================================================

_CSS = """
<style>
/* ── Leyenda chips ── */
.leyenda-wrap { display:flex; flex-wrap:wrap; gap:6px; margin:2px 0 10px; }
.chip { padding:3px 10px; border-radius:20px; font-size:11px; font-weight:600; white-space:nowrap; }
.chip-A    { background:#D1FAE5; color:#065F46; }
.chip-BM   { background:#DBEAFE; color:#1E40AF; }
.chip-VAC  { background:#FEF9C3; color:#854D0E; }
.chip-NASA { background:#FEE2E2; color:#991B1B; }
.chip-NACA { background:#FFE4BA; color:#92400E; }

/* ── Tabla HTML personalizada ── */
.asis-table-wrap {
    width:100%; overflow-x:auto; overflow-y:auto;
    max-height:460px;
    border-radius:10px;
    border:1px solid #E5E0EA;
    margin-bottom:6px;
}
.asis-table {
    width:100%; border-collapse:collapse;
    font-size:12.5px; font-family:inherit;
}
.asis-table thead th {
    position:sticky; top:0; z-index:2;
    background:#4B0067; color:white;
    padding:9px 10px; text-align:left;
    font-size:11px; font-weight:700; letter-spacing:.4px;
    white-space:nowrap;
}
.asis-table tbody tr { border-bottom:1px solid #F2EEF5; }
.asis-table tbody tr:hover { background:#FAF3FE; }
.asis-table tbody td {
    padding:7px 10px; color:#1A1521;
    vertical-align:middle; white-space:nowrap;
}
.asis-table tbody td.nombre-col { white-space:normal; min-width:160px; max-width:240px; }
.dia-chip {
    display:inline-block; padding:2px 9px; border-radius:12px;
    font-size:11px; font-weight:700; letter-spacing:.3px;
}
.st-badge-activo   { background:#D1FAE5; color:#065F46; padding:1px 8px; border-radius:12px; font-size:11px; font-weight:700; }
.st-badge-inactivo { background:#FEE2E2; color:#991B1B; padding:1px 8px; border-radius:12px; font-size:11px; font-weight:700; }

/* ── Panel marcación integrado ── */
.mrc-panel {
    background:linear-gradient(135deg,#FAF3FE 0%,#F3E5FA 100%);
    border:1.5px solid #E9D5F5; border-radius:14px;
    padding:14px 18px; margin:4px 0;
}
.mrc-row { display:flex; flex-wrap:wrap; gap:6px 20px; font-size:12.5px; color:#3D3548; line-height:1.7; }
.mrc-row b { color:#4B0067; }
.badge-marca { display:inline-block; padding:2px 9px; border-radius:12px; font-size:11px; font-weight:700; background:#EDE9FE; color:#4B0067; }

/* ── Métricas mini ── */
.mini-metric { background:white; border:1px solid #E5E0EA; border-radius:10px; padding:10px 14px 8px; text-align:center; }
.mini-metric .val { font-size:22px; font-weight:800; color:#4B0067; line-height:1.1; }
.mini-metric .lbl { font-size:11px; color:#6B6175; margin-top:2px; }

/* ── Banner retroactivo ── */
.retro-banner { background:#FFF7ED; border:1.5px solid #FED7AA; border-radius:10px; padding:10px 14px; font-size:12.5px; color:#92400E; margin:6px 0; }

/* ── Info sync banner ── */
.sync-banner { background:#EFF6FF; border:1.5px solid #BFDBFE; border-radius:10px; padding:8px 14px; font-size:12px; color:#1E40AF; margin:4px 0; }
</style>
"""


def _leyenda_html() -> str:
    return """<div class='leyenda-wrap'>
      <span class='chip chip-A'>✅ A — Asistió</span>
      <span class='chip chip-BM'>🏥 A-BM — Baja Médica</span>
      <span class='chip chip-VAC'>🌴 A-VAC — Vacaciones</span>
      <span class='chip chip-NASA'>❌ NA-SA — Sin aviso</span>
      <span class='chip chip-NACA'>⚠️ NA-CA — Con aviso</span>
    </div>"""


def _chip_dia(marca: str) -> str:
    """Devuelve un <span> chip de color para la columna DIA en la tabla HTML."""
    css = _CHIP_CSS.get(marca, _CHIP_CSS[""])
    label = marca if marca else "—"
    return f"<span class='dia-chip' style='{css}'>{label}</span>"


def _badge_estado(estado: str) -> str:
    cls = "st-badge-activo" if estado == "ACTIVO" else "st-badge-inactivo"
    return f"<span class='{cls}'>{estado}</span>"


def _tabla_html(df: pd.DataFrame, col_dia: str, limite: int = 200) -> str:
    """
    Genera tabla HTML pura con scroll vertical.
    La columna DIA muestra chips de color — nunca inputs editables.
    """
    filas = df.head(limite)
    cols  = ["DNI", "NOMBRE", "SUPERVISOR", "COORDINADOR",
             "DEPARTAMENTO", "PROVINCIA", "ESTADO", "FECHA_ALTA", "FECHA_CESE", col_dia]
    cabeceras = ["DNI", "Nombre", "Supervisor", "Coordinador",
                 "Departamento", "Provincia", "Estado", "Alta", "Cese", col_dia]

    thead = "".join(f"<th>{h}</th>" for h in cabeceras)
    rows_html = []
    for _, r in filas.iterrows():
        cells = []
        for c in cols:
            val = str(r.get(c, "") or "").strip()
            if c == col_dia:
                cells.append(f"<td>{_chip_dia(val)}</td>")
            elif c == "NOMBRE":
                cells.append(f"<td class='nombre-col'>{val}</td>")
            elif c == "ESTADO":
                cells.append(f"<td>{_badge_estado(val)}</td>")
            else:
                cells.append(f"<td>{val if val else '—'}</td>")
        rows_html.append("<tr>" + "".join(cells) + "</tr>")

    tbody = "".join(rows_html)
    return (
        f"<div class='asis-table-wrap'>"
        f"<table class='asis-table'>"
        f"<thead><tr>{thead}</tr></thead>"
        f"<tbody>{tbody}</tbody>"
        f"</table>"
        f"</div>"
    )


# =============================================================================
# UI Principal
# =============================================================================

def mostrar_asistencia(hoja_asistencia, hoja_colaboradores, registro_mod=None, razon=None):
    st.markdown(_CSS, unsafe_allow_html=True)
    st.markdown("<span class='wow-section-title'>🗓️ Presencialidad Dealer</span>", unsafe_allow_html=True)

    usuario_razon = normalizar_texto(razon if razon is not None else st.session_state.get("razon", "ALL"))
    es_dealer     = bool(usuario_razon and usuario_razon.upper() != "ALL")

    # ── Barra de control ────────────────────────────────────────────────────
    c_per, c_dia, c_sync = st.columns([1.5, 1.5, 0.8])
    with c_per:
        periodo = st.selectbox("📅 Periodo", periodos_disponibles(), index=0, key="asis_periodo")
    y, m  = map(int, periodo.split("-"))
    dias  = list(range(1, calendar.monthrange(y, m)[1] + 1))
    dia_def = hoy_lima().day if periodo == periodo_lima() and hoy_lima().day in dias else 1
    with c_dia:
        dia = st.selectbox("📆 Día", dias, index=dias.index(dia_def), key="asis_dia")
    with c_sync:
        st.markdown("<div style='height:26px'></div>", unsafe_allow_html=True)
        if st.button("🔄 Sincronizar", key="btn_sync",
                     help="Fuerza relecura completa desde Drive — útil tras altas/bajas en otros módulos o edición manual"):
            limpiar_cache_asistencia()
            # Limpiar marcas inline para que se lea la data fresca
            for k in list(st.session_state.keys()):
                if k.startswith("marcas_inline_"):
                    del st.session_state[k]
            st.rerun()

    col_dia   = f"DIA_{dia}"
    fecha_sel = fecha_desde_periodo_dia(periodo, dia)
    es_retro  = (fecha_sel < hoy_lima())

    st.markdown(_leyenda_html(), unsafe_allow_html=True)

    if es_retro:
        st.markdown(
            "<div class='retro-banner'>⚠️ <b>Fecha retroactiva</b> — "
            "Solo se puede registrar o corregir <b>A-BM</b> con sustento adjunto. "
            "Aplica a cualquier día del mes actual o meses anteriores.</div>",
            unsafe_allow_html=True
        )

    # ── Carga de datos ───────────────────────────────────────────────────────
    with st.spinner("⏳ Cargando datos desde Drive…"):
        try:
            df_live, headers = vista_live(
                hoja_colaboradores, hoja_asistencia, periodo, col_dia,
                usuario_razon if es_dealer else "ALL",
            )
        except Exception as e:
            st.error(f"Error al cargar presencialidad: {e}")
            st.markdown(
                "<div class='sync-banner'>💡 Si acabas de ingresar altas o bajas en otro módulo, "
                "usa <b>🔄 Sincronizar</b> para forzar la lectura actualizada desde Drive.</div>",
                unsafe_allow_html=True
            )
            return

    if df_live.empty:
        st.warning(
            "No hay promotores D2D para este usuario/periodo. "
            "Verifica razón social o que el cargo sea 'Promotor D2D'."
        )
        st.markdown(
            "<div class='sync-banner'>💡 Si recién ingresaste un alta, "
            "usa <b>🔄 Sincronizar</b> para ver al nuevo colaborador.</div>",
            unsafe_allow_html=True
        )
        return

    # Session state para actualización inline (sin releer Drive al guardar)
    SS_KEY = f"marcas_inline_{periodo}_{col_dia}"
    if SS_KEY not in st.session_state:
        st.session_state[SS_KEY] = {}

    # Aplicar marcas de sesión sobre el DataFrame en memoria
    for key_row, nueva_marca in st.session_state[SS_KEY].items():
        mask = df_live["KEY"] == key_row
        if mask.any():
            df_live.loc[mask, col_dia] = nueva_marca

    # ── Filtros ──────────────────────────────────────────────────────────────
    with st.expander("🔍 Filtros de búsqueda", expanded=False):
        with st.form("form_filtros_asis", clear_on_submit=False):
            fa, fb, fc = st.columns([1.5, 1, 1])
            with fa:
                texto_busqueda = st.text_input("DNI / nombre / supervisor", value="",
                                               placeholder="Ej: 12345678 o Kevin")
            with fb:
                f_sup   = st.selectbox("Supervisor",   opciones(df_live, "SUPERVISOR"),   index=0)
            with fc:
                f_coord = st.selectbox("Coordinador",  opciones(df_live, "COORDINADOR"),  index=0)
            fd, fe, ff = st.columns(3)
            with fd:
                f_dep    = st.selectbox("Departamento", opciones(df_live, "DEPARTAMENTO"), index=0)
            with fe:
                f_prov   = st.selectbox("Provincia",    opciones(df_live, "PROVINCIA"),    index=0)
            with ff:
                f_estado = st.selectbox("Estado",       opciones(df_live, "ESTADO"),       index=0)
            st.form_submit_button("🔎 Aplicar filtros", use_container_width=True)

    # ── Filtrado en memoria ──────────────────────────────────────────────────
    df_f = filtrar(df_live, "TODOS", f_sup, f_coord, f_dep, f_prov, f_estado)
    q = normalizar_texto(texto_busqueda).upper()
    if q:
        mask = pd.Series(False, index=df_f.index)
        for c in ["DNI", "NOMBRE", "SUPERVISOR", "COORDINADOR", "DEPARTAMENTO", "PROVINCIA"]:
            if c in df_f.columns:
                mask |= df_f[c].astype(str).str.upper().str.contains(q, na=False)
        df_f = df_f[mask].copy()

    if df_f.empty:
        st.warning("Sin resultados con los filtros aplicados.")
        return

    df_f["_EDITABLE"] = df_f.apply(lambda r: editable_en_fecha(r, fecha_sel), axis=1)
    df_editables      = df_f[df_f["_EDITABLE"]].copy()

    # ── Métricas rápidas ─────────────────────────────────────────────────────
    total     = len(df_f)
    editables = len(df_editables)
    marcados  = int((df_f.get(col_dia, pd.Series([""] * total)) != "").sum())
    pendientes = editables - int((df_editables.get(col_dia, pd.Series()) != "").sum())

    m1, m2, m3, m4 = st.columns(4)
    for col_ui, val, label in [
        (m1, total,      "👥 Total filtrado"),
        (m2, editables,  "✏️ Editables"),
        (m3, marcados,   "✅ Marcados"),
        (m4, pendientes, "⏳ Pendientes"),
    ]:
        with col_ui:
            st.markdown(
                f"<div class='mini-metric'>"
                f"<div class='val'>{val}</div>"
                f"<div class='lbl'>{label}</div>"
                f"</div>", unsafe_allow_html=True
            )

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    # ═══════════════════════════════════════════════════════════════════════
    # BLOQUE 1 — Tabla HTML: todos los registros visibles, scroll interno,
    #            columna DIA con chip de color — cero inputs editables
    # ═══════════════════════════════════════════════════════════════════════
    st.markdown(
        f"<span class='wow-section-title'>📋 Lista de personal — <b>{col_dia}</b> integrado</span>",
        unsafe_allow_html=True
    )

    LIMITE_TABLA = 200   # muestra hasta 200 filas; usa filtros para acotar más
    html_tabla   = _tabla_html(df_f, col_dia, LIMITE_TABLA)
    st.markdown(html_tabla, unsafe_allow_html=True)

    total_df = len(df_f)
    if total_df > LIMITE_TABLA:
        st.caption(f"Mostrando {LIMITE_TABLA} de {total_df} registros. Usa los filtros para acotar.")
    else:
        st.caption(f"Total: {total_df} registros del socio.")

    # ═══════════════════════════════════════════════════════════════════════
    # BLOQUE 2 — Panel de marcación (3 sub-bloques integrados)
    # ═══════════════════════════════════════════════════════════════════════
    st.markdown("<span class='wow-section-title'>✏️ Registrar asistencia</span>", unsafe_allow_html=True)

    with st.expander("📝 Panel de marcación", expanded=True):
        if df_editables.empty:
            st.warning(
                "No hay personal editable para esta fecha. "
                "Todos son INACTIVOS o la fecha cae fuera del rango alta/cese."
            )
        else:
            # Construir opciones sin DNIs duplicados
            opciones_persona = []
            mapa_persona     = {}
            seen_dni         = set()

            for idx, r in df_editables.iterrows():
                dni = normalizar_dni(r.get("DNI"))
                if dni in seen_dni:
                    continue
                seen_dni.add(dni)
                nombre       = normalizar_texto(r.get("NOMBRE"))
                sup          = normalizar_texto(r.get("SUPERVISOR"))
                marca_actual = limpiar_marca(r.get(col_dia, ""))
                ind          = f" [{marca_actual}]" if marca_actual else " [—]"
                etiqueta     = f"{dni} | {nombre} | {sup}{ind}"
                mapa_persona[etiqueta] = idx
                opciones_persona.append(etiqueta)

            # ── Sub-bloque A: Selector ──────────────────────────────────────
            col_a, col_b, col_c = st.columns([1.8, 2.2, 1.4])

            with col_a:
                st.markdown("**👤 Colaborador**")
                persona = st.selectbox(
                    "col",
                    opciones_persona, index=0,
                    key="asis_persona_sel",
                    help="[marca] = marcación actual · [—] = sin marca",
                    label_visibility="collapsed"
                )

            idx_sel_prev = mapa_persona.get(persona)

            # ── Sub-bloque B: Datos del colaborador (panel morado) ──────────
            with col_b:
                st.markdown("**📌 Datos del colaborador**")
                if idx_sel_prev is not None:
                    rp        = df_editables.loc[idx_sel_prev]
                    estado_p  = normalizar_texto(rp.get("ESTADO", "")).upper()
                    badge_cls = "st-badge-activo" if estado_p == "ACTIVO" else "st-badge-inactivo"
                    marca_p   = limpiar_marca(rp.get(col_dia, ""))
                    chip_p    = _chip_dia(marca_p)
                    st.markdown(
                        f"""<div class='mrc-panel'>
                        <div class='mrc-row'>
                          <span><b>DNI:</b> {normalizar_dni(rp.get('DNI',''))}</span>
                          <span><b>Nombre:</b> {normalizar_texto(rp.get('NOMBRE',''))}</span>
                          <span class='{badge_cls}'>{estado_p}</span>
                        </div>
                        <div class='mrc-row' style='margin-top:5px'>
                          <span><b>Supervisor:</b> {normalizar_texto(rp.get('SUPERVISOR',''))}</span>
                          <span><b>Coordinador:</b> {normalizar_texto(rp.get('COORDINADOR',''))}</span>
                        </div>
                        <div class='mrc-row' style='margin-top:5px'>
                          <span><b>Alta:</b> {rp.get('FECHA_ALTA','—')}</span>
                          <span><b>Cese:</b> {rp.get('FECHA_CESE','—') or '—'}</span>
                          <span><b>Marca {col_dia}:</b> {chip_p}</span>
                        </div>
                        </div>""",
                        unsafe_allow_html=True
                    )

            # ── Sub-bloque C: Marcación + upload + guardar ──────────────────
            with col_c:
                st.markdown("**📋 Marcación**")
                marcas_opciones = list(MARCAS_LABELS.keys())
                marcas_display  = [MARCAS_LABELS[k] for k in marcas_opciones]
                marca_idx = st.selectbox(
                    "Tipo",
                    range(len(marcas_opciones)),
                    format_func=lambda i: marcas_display[i],
                    index=0,
                    key="asis_marca_idx",
                    label_visibility="collapsed"
                )
                marca = marcas_opciones[marca_idx]

                if es_retro and marca and marca != "A-BM":
                    st.caption("⛔ Solo A-BM en fechas pasadas.")

                # Upload de sustento — visible únicamente al seleccionar A-BM
                archivo_bm = None
                if marca == "A-BM":
                    st.markdown(
                        "<div style='font-size:11.5px;color:#1E40AF;margin:4px 0 2px'>"
                        "🏥 Adjunta el sustento (PDF o imagen):</div>",
                        unsafe_allow_html=True
                    )
                    archivo_bm = st.file_uploader(
                        "Sustento",
                        type=["pdf", "png", "jpg", "jpeg"],
                        key=f"file_abm_{periodo}_{dia}",
                        label_visibility="collapsed"
                    )

                guardar = st.button(
                    "💾 Guardar",
                    key="btn_guardar_pres",
                    use_container_width=True,
                    type="primary",
                )

                if guardar:
                    idx_g = mapa_persona.get(persona)
                    if idx_g is None:
                        st.error("No se identificó al colaborador.")
                    elif not marca:
                        st.error("⛔ Selecciona una marcación.")
                    elif es_retro and marca != "A-BM":
                        st.error("⛔ Fechas pasadas: solo A-BM con sustento.")
                    elif marca == "A-BM" and archivo_bm is None:
                        st.error("⛔ Adjunta el sustento para A-BM.")
                    else:
                        row_g = df_editables.loc[idx_g].copy()
                        try:
                            if marca == "A-BM":
                                with st.spinner("📤 Subiendo sustento a Drive…"):
                                    guardar_sustento(row_g, periodo, dia, archivo_bm)
                            with st.spinner("💾 Guardando en Sheets…"):
                                resultado = guardar_marca(
                                    hoja_asistencia, row_g, headers, col_dia, marca
                                )
                            # Actualización inline: refleja la marca en la tabla
                            # sin releer Drive (basta con el session_state)
                            key_row = row_g.get("KEY", "")
                            if key_row:
                                st.session_state[SS_KEY][key_row] = marca
                            nombre_g = normalizar_texto(row_g.get("NOMBRE", ""))
                            st.success(
                                f"✅ **{marca}** guardado para **{nombre_g}** ({resultado})."
                            )
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error al guardar: {e}")
                            st.caption("Si el error persiste, usa 🔄 Sincronizar y vuelve a intentarlo.")

    # ═══════════════════════════════════════════════════════════════════════
    # BLOQUE 3 — Espejo de marcaciones del día (solo registros con marca)
    # ═══════════════════════════════════════════════════════════════════════
    marcados_df = df_f[df_f.get(col_dia, pd.Series()) != ""].copy() if col_dia in df_f.columns else pd.DataFrame()
    label_espejo = f"📊 Marcaciones registradas — {col_dia} ({len(marcados_df)} de {total})"

    with st.expander(label_espejo, expanded=False):
        if marcados_df.empty:
            st.info("Aún no hay marcaciones registradas para este día.")
        else:
            st.markdown(_tabla_html(marcados_df, col_dia, 500), unsafe_allow_html=True)

    # ── Jerarquía completa ───────────────────────────────────────────────────
    st.divider()
    st.markdown(
        "<span class='wow-section-title'>📋 Jerarquía completa de promotores</span>",
        unsafe_allow_html=True
    )
    st.caption(
        f"**{len(df_live)}** promotores D2D en memoria — "
        "datos de la misma lectura, sin llamada adicional a Drive."
    )
    cols_jer = ["RAZON SOCIAL", "DNI", "NOMBRE", "CARGO", "SUPERVISOR", "COORDINADOR",
                "DEPARTAMENTO", "PROVINCIA", "ESTADO", "FECHA_ALTA", "FECHA_CESE"]
    cols_jer = [c for c in cols_jer if c in df_live.columns]
    st.dataframe(
        df_live[cols_jer].reset_index(drop=True),
        use_container_width=True,
        hide_index=True,
        height=500,
        column_config={
            "DNI":    st.column_config.TextColumn("DNI"),
            "NOMBRE": st.column_config.TextColumn("Nombre", width="large"),
            "ESTADO": st.column_config.TextColumn("Estado"),
        },
    )
