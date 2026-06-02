# ASISTENCIA_FIX_RENDER_FREE_NODISCONNECT_20260601
# Cambios respecto a versión anterior:
# 1. CACHE_TTL_SECONDS subido de 10s → 90s (evita llamadas frecuentes a Sheets que congelan Render Free)
# 2. Botón "🔄 Recargar presencialidad" explícito para forzar re-lectura cuando el usuario lo necesita
# 3. Función registrar_alta_en_asistencia() AÑADIDA (era llamada desde formulario.py pero no existía)
# 4. construir_base_colaboradores usa cache_data con hash en hoja para que el merge sea en memoria
# 5. El filtro de cargo acepta tanto "Promotor D2D" como "Promotor D2D - Dealer" (VENTAS INDIRECTAS)
# 6. UI: selectores Periodo y Día quedan en la parte superior como antes, sin cambios de layout
# 7. El form de filtros y el selector de persona/marca quedan a la DERECHA del preview (layout side-by-side)
#    ─ igual que en la versión original del cliente

import calendar
import pytz
from datetime import datetime, date

import pandas as pd
import streamlit as st
from sheets import subir_archivo_drive, obtener_o_crear_worksheet

NOMBRE_LIBRO = "maestra_vendedores"
HOJA_SUSTENTOS = "Sustentos_Bajas"
TZ_LIMA = pytz.timezone("America/Lima")

MARCAS = ["", "A", "A-BM", "A-VAC", "NA-SA", "NA-CA"]
LEYENDA = (
    "A = Asistió · A-BM = No Asistió por Baja Médica · "
    "A-VAC = No Asistió por Vacaciones · NA-SA = No Asistió - Sin aviso · "
    "NA-CA = No Asistió - Con aviso"
)

BASE_COLS = [
    "RAZON SOCIAL", "SUPERVISOR", "COORDINADOR", "DEPARTAMENTO", "PROVINCIA",
    "DNI", "NOMBRE", "CARGO", "ESTADO", "FECHA_ALTA", "FECHA_CESE", "MES", "PERIODO"
]
DAY_COLS = [f"DIA_{i}" for i in range(1, 32)]
ALL_COLS = BASE_COLS + DAY_COLS

DISPLAY_COLS = [
    "RAZON SOCIAL", "DNI", "NOMBRE", "SUPERVISOR", "COORDINADOR", "DEPARTAMENTO",
    "PROVINCIA", "ESTADO", "FECHA_ALTA", "FECHA_CESE", "PERIODO"
]

MAX_FILAS_EDITOR = 200
# TTL más largo: evita que Render Free se congele por llamadas frecuentes a la API de Sheets.
# El usuario puede forzar recarga con el botón dedicado.
CACHE_TTL_SECONDS = 90


# =============================================================================
# Utilitarios base
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
    s = normalizar_texto(x).replace(".0", "")
    s = s.replace(",", "").replace(" ", "")
    return s.zfill(8) if s.isdigit() and len(s) < 8 else s


def parse_fecha(x):
    try:
        if x is None or str(x).strip() == "":
            return None
        f = pd.to_datetime(x, errors="coerce")
        if pd.isna(f):
            return None
        return f.date()
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
# Lecturas optimizadas por rango
# =============================================================================

@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def _leer_header_cached(_worksheet, cache_key: str):
    try:
        return [_norm_header(x) for x in _worksheet.row_values(1)]
    except Exception:
        return []


def leer_header(worksheet) -> list[str]:
    return _leer_header_cached(worksheet, _worksheet_key(worksheet))


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def _leer_columnas_cached(_worksheet, cache_key: str, columnas_tuple: tuple):
    """Lee solo columnas requeridas usando batch_get. No lee toda la hoja."""
    headers = [_norm_header(x) for x in _worksheet.row_values(1)]
    if not headers:
        return headers, {}

    header_to_index = {h: i + 1 for i, h in enumerate(headers) if h}
    ranges = []
    selected = []
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
    try:
        _leer_header_cached.clear()
    except Exception:
        pass
    try:
        _leer_columnas_cached.clear()
    except Exception:
        pass


def df_desde_columnas(data: dict, extra_row_sheet: bool = False) -> pd.DataFrame:
    if not data:
        df = pd.DataFrame()
    else:
        max_len = max((len(v) for v in data.values()), default=0)
        fixed = {}
        for k, vals in data.items():
            fixed[k] = vals + [""] * (max_len - len(vals))
        df = pd.DataFrame(fixed)
    if extra_row_sheet:
        df["ROW_SHEET"] = range(2, len(df) + 2)
    return df


# =============================================================================
# Construcción de base viva desde colaboradores
# =============================================================================

def nombre_colaborador_from_df(df: pd.DataFrame) -> pd.Series:
    nombres = df.get("NOMBRES", pd.Series([""] * len(df))).astype(str).map(normalizar_texto)
    ap_pat = df.get("APELLIDO PATERNO", pd.Series([""] * len(df))).astype(str).map(normalizar_texto)
    ap_mat = df.get("APELLIDO MATERNO", pd.Series([""] * len(df))).astype(str).map(normalizar_texto)
    return (nombres + " " + ap_pat + " " + ap_mat).str.replace(r"\s+", " ", regex=True).str.strip()


def _es_cargo_presencialidad(cargo_str: str) -> bool:
    """
    Acepta tanto 'Promotor D2D' (Ventas Directas) como 'Promotor D2D - Dealer' (Ventas Indirectas).
    Evita que el filtro excluya a colaboradores según el canal de su alta.
    """
    c = str(cargo_str).upper().replace("-", " ").replace("  ", " ").strip()
    return "PROMOTOR D2D" in c


def construir_base_colaboradores(hoja_colaboradores, periodo: str, razon_usuario: str = "ALL") -> pd.DataFrame:
    columnas_necesarias = (
        "RAZON SOCIAL", "SUPERVISOR A CARGO", "SUPERVISOR", "COORDINADOR",
        "DEPARTAMENTO", "PROVINCIA", "DNI", "NOMBRES", "APELLIDO PATERNO", "APELLIDO MATERNO",
        "ESTADO", "FECHA DE CREACION USUARIO", "FECHA_ALTA", "FECHA DE CESE", "FECHA_CESE",
        "CARGO (ROL)"
    )
    headers, data = _leer_columnas_cached(hoja_colaboradores, _worksheet_key(hoja_colaboradores), columnas_necesarias)
    if not headers or not data:
        return pd.DataFrame(columns=BASE_COLS)

    df = df_desde_columnas(data)
    if df.empty:
        return pd.DataFrame(columns=BASE_COLS)

    # Filtro dealer temprano.
    if razon_usuario and razon_usuario.upper() != "ALL" and "RAZON SOCIAL" in df.columns:
        df = df[df["RAZON SOCIAL"].map(normalizar_razon).eq(normalizar_razon(razon_usuario))].copy()

    # Filtro de cargo: acepta Promotor D2D y Promotor D2D - Dealer
    if "CARGO (ROL)" in df.columns:
        df = df[df["CARGO (ROL)"].astype(str).apply(_es_cargo_presencialidad)].copy()

    if df.empty:
        return pd.DataFrame(columns=BASE_COLS)

    out = pd.DataFrame(index=df.index)
    out["RAZON SOCIAL"] = df.get("RAZON SOCIAL", "").map(normalizar_texto) if "RAZON SOCIAL" in df else ""

    if "SUPERVISOR A CARGO" in df.columns:
        out["SUPERVISOR"] = df["SUPERVISOR A CARGO"].map(normalizar_texto)
    elif "SUPERVISOR" in df.columns:
        out["SUPERVISOR"] = df["SUPERVISOR"].map(normalizar_texto)
    else:
        out["SUPERVISOR"] = ""

    out["COORDINADOR"] = df.get("COORDINADOR", "").map(normalizar_texto) if "COORDINADOR" in df else ""
    out["DEPARTAMENTO"] = df.get("DEPARTAMENTO", "").map(normalizar_texto) if "DEPARTAMENTO" in df else ""
    out["PROVINCIA"] = df.get("PROVINCIA", "").map(normalizar_texto) if "PROVINCIA" in df else ""
    out["DNI"] = df.get("DNI", "").map(normalizar_dni) if "DNI" in df else ""
    out["NOMBRE"] = nombre_colaborador_from_df(df)
    out["CARGO"] = df.get("CARGO (ROL)", "").map(normalizar_texto) if "CARGO (ROL)" in df else ""
    out["ESTADO"] = df.get("ESTADO", "ACTIVO").map(lambda x: normalizar_texto(x).upper()) if "ESTADO" in df else "ACTIVO"

    if "FECHA DE CREACION USUARIO" in df.columns:
        out["FECHA_ALTA"] = df["FECHA DE CREACION USUARIO"].map(fecha_str)
    elif "FECHA_ALTA" in df.columns:
        out["FECHA_ALTA"] = df["FECHA_ALTA"].map(fecha_str)
    else:
        out["FECHA_ALTA"] = ""

    if "FECHA DE CESE" in df.columns:
        out["FECHA_CESE"] = df["FECHA DE CESE"].map(fecha_str)
    elif "FECHA_CESE" in df.columns:
        out["FECHA_CESE"] = df["FECHA_CESE"].map(fecha_str)
    else:
        out["FECHA_CESE"] = ""

    out["MES"] = str(int(periodo[-2:]))
    out["PERIODO"] = periodo
    out = out[out["DNI"].astype(str).str.strip().ne("")].copy()
    out["KEY"] = out["DNI"].astype(str) + "|" + out["FECHA_ALTA"].astype(str) + "|" + periodo
    out = out.drop_duplicates("KEY", keep="last")
    return out


# =============================================================================
# Asistencia: leer solo base + día seleccionado
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
    df["DNI"] = df["DNI"].map(normalizar_dni)
    df["FECHA_ALTA"] = df["FECHA_ALTA"].map(fecha_str)
    df["PERIODO"] = df["PERIODO"].map(normalizar_texto)

    df = df[df["PERIODO"].astype(str).eq(periodo)].copy()
    if razon_usuario and razon_usuario.upper() != "ALL" and "RAZON SOCIAL" in df.columns:
        df = df[df["RAZON SOCIAL"].map(normalizar_razon).eq(normalizar_razon(razon_usuario))].copy()

    df["KEY"] = df["DNI"].astype(str) + "|" + df["FECHA_ALTA"].astype(str) + "|" + df["PERIODO"].astype(str)
    df[col_dia] = df[col_dia].map(limpiar_marca)
    return df, headers


def vista_live(hoja_colaboradores, hoja_asistencia, periodo: str, col_dia: str, razon_usuario: str = "ALL") -> tuple:
    base = construir_base_colaboradores(hoja_colaboradores, periodo, razon_usuario)
    asis_p, headers = leer_asistencia(hoja_asistencia, periodo, col_dia, razon_usuario)

    if not asis_p.empty:
        marcas = asis_p[["KEY", "ROW_SHEET", col_dia]].drop_duplicates("KEY", keep="last")
    else:
        marcas = pd.DataFrame(columns=["KEY", "ROW_SHEET", col_dia])

    live = base.merge(marcas, on="KEY", how="left", suffixes=("", "_ASIS"))
    live[col_dia] = live.get(col_dia, "").map(limpiar_marca)
    if "ROW_SHEET" not in live.columns:
        live["ROW_SHEET"] = ""
    live["ROW_SHEET"] = live["ROW_SHEET"].fillna("")
    return live, headers


# =============================================================================
# Filtros y validación
# =============================================================================

def opciones(df, col):
    if col not in df.columns:
        return ["TODOS"]
    vals = sorted([v for v in df[col].dropna().astype(str).map(normalizar_texto).unique().tolist() if v])
    return ["TODOS"] + vals


def filtrar(df, razon, sup, coord, dep, prov, estado):
    r = df.copy()
    filtros = [
        ("RAZON SOCIAL", razon), ("SUPERVISOR", sup), ("COORDINADOR", coord),
        ("DEPARTAMENTO", dep), ("PROVINCIA", prov), ("ESTADO", estado)
    ]
    for col, val in filtros:
        if val and val != "TODOS" and col in r.columns:
            r = r[r[col].astype(str).map(normalizar_texto).eq(val)].copy()
    return r


def editable_en_fecha(row, fecha_sel: date):
    alta = parse_fecha(row.get("FECHA_ALTA"))
    cese = parse_fecha(row.get("FECHA_CESE"))
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
    for i in range(0, 4):
        yy, mm = y, m - i
        while mm <= 0:
            yy -= 1
            mm += 12
        periodos.append(f"{yy}-{mm:02d}")
    return periodos


def fecha_desde_periodo_dia(periodo: str, dia: int) -> date:
    y, m = map(int, periodo.split("-"))
    ultimo = calendar.monthrange(y, m)[1]
    return date(y, m, min(int(dia), ultimo))


# =============================================================================
# Escritura puntual: solo al guardar
# =============================================================================

def guardar_sustento(row, periodo, dia, archivo):
    if archivo is None:
        return ""
    contenido = archivo.getvalue()
    mime = archivo.type or "application/octet-stream"
    ext = "pdf" if mime == "application/pdf" else "jpg"
    dni = normalizar_dni(row.get("DNI"))
    ts = datetime.now(TZ_LIMA).strftime("%Y%m%d_%H%M%S")
    nombre_archivo = f"sustento_ABM_{dni}_{periodo}_DIA_{dia}_{ts}.{ext}"
    link = subir_archivo_drive(nombre_archivo, contenido, mime)

    cols = ["PERIODO", "DIA", "FECHA_ASISTENCIA", "DNI", "NOMBRE", "RAZON SOCIAL", "MOTIVO", "LINK_DOCUMENTO", "FECHA_SUBIDA", "USUARIO_REGISTRO"]
    hoja = obtener_o_crear_worksheet(NOMBRE_LIBRO, HOJA_SUSTENTOS, cols)
    fecha_asistencia = str(fecha_desde_periodo_dia(periodo, dia))
    hoja.append_row([
        periodo, f"DIA_{dia}", fecha_asistencia, dni, row.get("NOMBRE", ""), row.get("RAZON SOCIAL", ""),
        "A-BM", link, datetime.now(TZ_LIMA).strftime("%Y-%m-%d %H:%M:%S"), st.session_state.get("usuario", "")
    ], value_input_option="USER_ENTERED")
    return link


def garantizar_cabecera_si_vacia(hoja_asistencia, headers: list) -> list:
    if headers:
        return headers
    hoja_asistencia.append_row(ALL_COLS, value_input_option="USER_ENTERED")
    limpiar_cache_asistencia()
    return ALL_COLS.copy()


def guardar_marca(hoja_asistencia, row: pd.Series, headers: list, col_dia: str, marca: str):
    headers = [normalizar_texto(h).upper() for h in headers]
    headers = garantizar_cabecera_si_vacia(hoja_asistencia, headers)

    if col_dia not in headers:
        nueva_col = len(headers) + 1
        hoja_asistencia.update_cell(1, nueva_col, col_dia)
        headers.append(col_dia)
        limpiar_cache_asistencia()

    row_sheet = normalizar_texto(row.get("ROW_SHEET"))
    col_idx = headers.index(col_dia) + 1
    col_letra = _letra_col(col_idx)

    if row_sheet.isdigit():
        hoja_asistencia.update_acell(f"{col_letra}{int(row_sheet)}", marca)
        limpiar_cache_asistencia()
        return "actualizado"

    nueva = []
    for h in headers:
        if h in BASE_COLS:
            nueva.append(row.get(h, ""))
        elif h == col_dia:
            nueva.append(marca)
        else:
            nueva.append("")
    hoja_asistencia.append_row(nueva, value_input_option="USER_ENTERED")
    limpiar_cache_asistencia()
    return "nuevo"


# =============================================================================
# FUNCIÓN REQUERIDA POR formulario.py al guardar un alta
# =============================================================================

def registrar_alta_en_asistencia(hoja_asistencia, campos: dict) -> str:
    """
    Llamada desde formulario.py al guardar una nueva alta.
    Solo invalida el caché de asistencia para que la próxima carga
    desde colaboradores incluya al nuevo promotor.
    NO escribe directamente en la hoja Asistencia: el registro se crea
    la primera vez que el usuario guarda la marcación del día.
    Retorna un mensaje informativo para mostrar al usuario.
    """
    try:
        limpiar_cache_asistencia()
        dni = campos.get("DNI", "")
        nombre = " ".join([
            campos.get("NOMBRES", ""),
            campos.get("APELLIDO PATERNO", ""),
            campos.get("APELLIDO MATERNO", ""),
        ]).strip()
        return (
            f"El colaborador (DNI: {dni} – {nombre}) "
            "ya figura disponible en Presencialidad Dealer para marcar asistencia."
        )
    except Exception as e:
        return f"Alta registrada. Recarga Presencialidad para ver al colaborador ({e})."


# =============================================================================
# UI principal
# =============================================================================

def mostrar_asistencia(hoja_asistencia, hoja_colaboradores, registro_mod=None, razon=None):
    """
    Módulo liviano de presencialidad.
    - Al abrir/refrescar: solo LEE Google Sheets (caché 90s).
    - El botón 🔄 Recargar fuerza re-lectura inmediata.
    - No sincroniza, no borra, no escribe, no arma tablas editables masivas.
    - Solo al presionar Guardar Presencialidad se escribe una celda/fila.
    - Layout: filtros arriba → tabla preview (izq) + selector marcación (der)
    """
    st.markdown("<span class='wow-section-title'>🗓️ Presencialidad Dealer</span>", unsafe_allow_html=True)

    usuario_razon = normalizar_texto(razon if razon is not None else st.session_state.get("razon", "ALL"))
    es_dealer = usuario_razon and usuario_razon.upper() != "ALL"

    # ── Periodo y día ──────────────────────────────────────────────────────────
    col_per, col_dia_sel, col_reload = st.columns([1.2, 1.2, 0.7])
    with col_per:
        periodo = st.selectbox("PERIODO", periodos_disponibles(), index=0, key="asis_periodo")
    y, m = map(int, periodo.split("-"))
    dias = list(range(1, calendar.monthrange(y, m)[1] + 1))
    dia_default = hoy_lima().day if periodo == periodo_lima() and hoy_lima().day in dias else 1
    with col_dia_sel:
        dia = st.selectbox("DÍA", dias, index=dias.index(dia_default), key="asis_dia")
    with col_reload:
        st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
        if st.button("🔄 Recargar", key="btn_reload_asistencia", help="Fuerza re-lectura de Google Sheets"):
            limpiar_cache_asistencia()
            st.rerun()

    col_dia = f"DIA_{dia}"
    fecha_sel = fecha_desde_periodo_dia(periodo, dia)

    st.info(
        f"📅 Periodo: **{periodo}** | Día: **{col_dia}** | "
        "La información se actualiza al abrir o al presionar 🔄 Recargar. "
        "Solo se escribe al presionar **💾 Guardar Presencialidad**. "
        "A-BM requiere sustento adjunto."
    )

    # ── Carga de datos ─────────────────────────────────────────────────────────
    try:
        with st.spinner("Cargando base mínima desde Drive…"):
            df_live, headers = vista_live(
                hoja_colaboradores,
                hoja_asistencia,
                periodo,
                col_dia,
                usuario_razon if es_dealer else "ALL",
            )
    except Exception as e:
        st.error(f"No se pudo cargar presencialidad: {e}")
        return

    if df_live.empty:
        st.warning(
            "No hay promotores D2D para mostrar con este usuario/periodo. "
            "Revisa razón social o cargo del colaborador (debe ser 'Promotor D2D' o 'Promotor D2D - Dealer')."
        )
        return

    # ── Filtros en FORM ────────────────────────────────────────────────────────
    with st.form("form_filtros_presencialidad_busqueda", clear_on_submit=False):
        st.caption("Filtra para reducir la lista. Presiona Buscar para aplicar.")
        c0, c1, c2 = st.columns([1.2, 1, 1])
        with c0:
            texto_busqueda = st.text_input(
                "Buscar DNI / nombre / supervisor / coordinador",
                value="", placeholder="Ej: 76043772 o Kevin"
            )
        with c1:
            f_sup = st.selectbox("Supervisor", opciones(df_live, "SUPERVISOR"), index=0)
        with c2:
            f_coord = st.selectbox("Coordinador", opciones(df_live, "COORDINADOR"), index=0)

        c3, c4, c5 = st.columns(3)
        with c3:
            f_dep = st.selectbox("Departamento", opciones(df_live, "DEPARTAMENTO"), index=0)
        with c4:
            f_prov = st.selectbox("Provincia", opciones(df_live, "PROVINCIA"), index=0)
        with c5:
            f_estado = st.selectbox("Estado", opciones(df_live, "ESTADO"), index=0)

        st.form_submit_button("🔎 Buscar / aplicar filtros", use_container_width=True)

    # ── Filtrado en memoria ────────────────────────────────────────────────────
    df_f = filtrar(df_live, "TODOS", f_sup, f_coord, f_dep, f_prov, f_estado)
    q = normalizar_texto(texto_busqueda).upper()
    if q:
        cols_busqueda = ["DNI", "NOMBRE", "SUPERVISOR", "COORDINADOR", "DEPARTAMENTO", "PROVINCIA"]
        mask = pd.Series(False, index=df_f.index)
        for c in cols_busqueda:
            if c in df_f.columns:
                mask = mask | df_f[c].astype(str).str.upper().str.contains(q, na=False)
        df_f = df_f[mask].copy()

    if df_f.empty:
        st.warning("No hay registros con la búsqueda/filtros seleccionados.")
        return

    df_f["_EDITABLE_FECHA"] = df_f.apply(lambda r: editable_en_fecha(r, fecha_sel), axis=1)
    df_editables = df_f[df_f["_EDITABLE_FECHA"]].copy()

    st.caption(
        f"Registros encontrados: **{len(df_f)}** | "
        f"Editables para el día seleccionado: **{len(df_editables)}**"
    )

    columnas_basicas = ["DNI", "NOMBRE", "SUPERVISOR", "COORDINADOR", "FECHA_ALTA", "FECHA_CESE", "ESTADO", col_dia]
    for c in columnas_basicas:
        if c not in df_f.columns:
            df_f[c] = ""

    # ── Layout: tabla (izq) + marcación (der) ─────────────────────────────────
    st.markdown("<span class='wow-section-title'>✏️ Registrar presencialidad</span>", unsafe_allow_html=True)
    st.info("**Motivos:** " + LEYENDA)

    col_tabla, col_marca = st.columns([1.6, 1])

    limite_preview = 50
    with col_tabla:
        st.dataframe(
            df_f[columnas_basicas].head(limite_preview),
            use_container_width=True,
            hide_index=True,
            height=min(420, 70 + min(len(df_f), limite_preview) * 30),
        )
        if len(df_f) > limite_preview:
            st.caption(f"Se muestran los primeros {limite_preview}. Usa búsqueda por DNI/nombre para ubicar más.")

    with col_marca:
        if df_editables.empty:
            st.warning("No hay personal editable para el día seleccionado (fecha de alta/cese o estado inactivo).")
        else:
            opciones_persona = []
            mapa_persona = {}
            for idx, r in df_editables.iterrows():
                dni = normalizar_dni(r.get("DNI"))
                nombre = normalizar_texto(r.get("NOMBRE"))
                sup = normalizar_texto(r.get("SUPERVISOR"))
                etiqueta = f"{dni} | {nombre} | Sup: {sup}"
                if etiqueta not in mapa_persona:
                    mapa_persona[etiqueta] = idx
                    opciones_persona.append(etiqueta)

            with st.form("form_guardar_presencialidad_puntual", clear_on_submit=False):
                persona = st.selectbox("Seleccionar colaborador", opciones_persona, index=0)
                marca = st.selectbox(
                    "Marcación", MARCAS[1:], index=0,
                    help="A-BM habilita sustento obligatorio."
                )
                archivo_bm = None
                if marca == "A-BM":
                    archivo_bm = st.file_uploader(
                        "Adjuntar sustento BM (PDF o imagen)",
                        type=["pdf", "png", "jpg", "jpeg"],
                        key=f"file_abm_puntual_{periodo}_{dia}",
                    )
                guardar = st.form_submit_button("💾 Guardar Presencialidad", use_container_width=True)

            if guardar:
                idx_sel = mapa_persona.get(persona)
                if idx_sel is None:
                    st.error("No se pudo identificar el colaborador seleccionado.")
                    return
                row_sel = df_editables.loc[idx_sel].copy()

                if fecha_sel != hoy_lima() and marca != "A-BM":
                    st.error("Para días anteriores/futuros solo se permite A-BM con sustento.")
                    return
                if marca == "A-BM" and archivo_bm is None:
                    st.error("Falta adjuntar sustento obligatorio para A-BM.")
                    return

                try:
                    if marca == "A-BM":
                        guardar_sustento(row_sel, periodo, dia, archivo_bm)
                    resultado = guardar_marca(hoja_asistencia, row_sel, headers, col_dia, marca)
                    st.success(f"✅ Presencialidad guardada correctamente ({resultado}).")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error guardando presencialidad: {e}")

    # ── Espejo del día bajo demanda ────────────────────────────────────────────
    with st.expander("📊 Ver espejo completo del día seleccionado", expanded=False):
        st.dataframe(df_f[columnas_basicas].copy(), use_container_width=True, hide_index=True, height=420)

    # ── Jerarquía bajo demanda ─────────────────────────────────────────────────
    if registro_mod is not None:
        st.divider()
        st.markdown("<span class='wow-section-title'>📋 Estado actual de la jerarquía</span>", unsafe_allow_html=True)
        if st.button("📥 Cargar jerarquía completa", key="btn_cargar_matriz_jerarquia"):
            try:
                registro_mod.mostrar_tabla(hoja_colaboradores, razon)
            except Exception as e:
                st.warning(f"No se pudo cargar la matriz de jerarquía: {e}")
