# FIX_ASISTENCIA_RANGOS_MINIMOS_SIN_FREEZE_20260602
# Presencialidad Dealer optimizada para Render Free + Google Sheets:
# - NO escribe al abrir/refrescar.
# - NO sincroniza automáticamente.
# - NO borra histórico.
# - Lee SOLO columnas necesarias por rango, no toda la hoja completa.
# - Filtra por dealer en memoria con data mínima.
# - Solo escribe al presionar Guardar Presencialidad.
# - A-BM permite sustento histórico; otras marcas solo día actual.

import calendar
import time
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
    "DNI", "NOMBRE", "ESTADO", "FECHA_ALTA", "FECHA_CESE", "MES", "PERIODO"
]
DAY_COLS = [f"DIA_{i}" for i in range(1, 32)]
ALL_COLS = BASE_COLS + DAY_COLS

DISPLAY_COLS = [
    "RAZON SOCIAL", "DNI", "NOMBRE", "SUPERVISOR", "COORDINADOR", "DEPARTAMENTO",
    "PROVINCIA", "ESTADO", "FECHA_ALTA", "FECHA_CESE", "PERIODO"
]

MAX_FILAS_EDITOR = 200
CACHE_TTL_SECONDS = 10  # corto: reduce frizado, pero permite ver cambios al refrescar en pocos segundos


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


def _first_existing(header_map: dict, candidates: list[str]):
    for c in candidates:
        key = _norm_header(c)
        if key in header_map:
            return key
    return None


# =============================================================================
# Lecturas optimizadas por rango / sin get_all_records / sin get_all_values total
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
def _leer_columnas_cached(_worksheet, cache_key: str, columnas_tuple: tuple[str, ...]):
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
        # vals viene como [[valor], [valor], ...]
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

    # Solo personal operativo si existe cargo. Si no existe, no bloquea.
    if "CARGO (ROL)" in df.columns:
        cargo = df["CARGO (ROL)"].astype(str).str.upper()
        df = df[cargo.str.contains("PROMOTOR|AGENTE", na=False)].copy()

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

def leer_asistencia(hoja_asistencia, periodo: str, col_dia: str, razon_usuario: str = "ALL") -> tuple[pd.DataFrame, list[str]]:
    headers = leer_header(hoja_asistencia)
    if not headers:
        # No escribimos cabecera al abrir. Se crea recién al guardar si hace falta.
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


def vista_live(hoja_colaboradores, hoja_asistencia, periodo: str, col_dia: str, razon_usuario: str = "ALL") -> tuple[pd.DataFrame, list[str]]:
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
    filtros = [("RAZON SOCIAL", razon), ("SUPERVISOR", sup), ("COORDINADOR", coord), ("DEPARTAMENTO", dep), ("PROVINCIA", prov), ("ESTADO", estado)]
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


def garantizar_cabecera_si_vacia(hoja_asistencia, headers: list[str]) -> list[str]:
    if headers:
        return headers
    hoja_asistencia.append_row(ALL_COLS, value_input_option="USER_ENTERED")
    limpiar_cache_asistencia()
    return ALL_COLS.copy()


def guardar_marca(hoja_asistencia, row: pd.Series, headers: list[str], col_dia: str, marca: str):
    headers = [normalizar_texto(h).upper() for h in headers]
    headers = garantizar_cabecera_si_vacia(hoja_asistencia, headers)

    if col_dia not in headers:
        # Agrega columna faltante al final. No borra ni mueve columnas.
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
# UI principal
# =============================================================================

def mostrar_asistencia(hoja_asistencia, hoja_colaboradores, registro_mod=None, razon=None):
    st.markdown("<span class='wow-section-title'>🗓️ Presencialidad Dealer</span>", unsafe_allow_html=True)

    usuario_razon = normalizar_texto(razon if razon is not None else st.session_state.get("razon", "ALL"))
    es_dealer = usuario_razon and usuario_razon.upper() != "ALL"

    periodo = st.selectbox("PERIODO", periodos_disponibles(), index=0, key="asis_periodo")
    y, m = map(int, periodo.split("-"))
    dias = list(range(1, calendar.monthrange(y, m)[1] + 1))
    dia_default = hoy_lima().day if periodo == periodo_lima() and hoy_lima().day in dias else 1
    dia = st.selectbox("DÍA", dias, index=dias.index(dia_default), key="asis_dia")
    col_dia = f"DIA_{dia}"
    fecha_sel = fecha_desde_periodo_dia(periodo, dia)

    st.info(
        f"📅 Periodo: **{periodo}** | Día seleccionado: **{col_dia}** | "
        "La información se lee al abrir/refrescar la página. "
        "Solo se escribe al presionar **Guardar Presencialidad**. "
        "A-BM permite sustento histórico."
    )

    try:
        with st.spinner("Cargando información desde Drive…"):
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
        st.warning("No hay colaboradores para mostrar con este usuario/periodo. Revisa razón social, estado o datos de colaboradores.")
        return

    with st.form("form_filtros_presencialidad", clear_on_submit=False):
        c1, c2, c3, c4, c5, c6 = st.columns(6)
        with c1:
            op_r = opciones(df_live, "RAZON SOCIAL")
            f_razon = st.selectbox("Razón Social", op_r, index=0, disabled=es_dealer)
        with c2:
            f_sup = st.selectbox("Supervisor", opciones(df_live, "SUPERVISOR"), index=0)
        with c3:
            f_coord = st.selectbox("Coordinador", opciones(df_live, "COORDINADOR"), index=0)
        with c4:
            f_dep = st.selectbox("Departamento", opciones(df_live, "DEPARTAMENTO"), index=0)
        with c5:
            f_prov = st.selectbox("Provincia", opciones(df_live, "PROVINCIA"), index=0)
        with c6:
            f_estado = st.selectbox("Estado", opciones(df_live, "ESTADO"), index=0)
        st.form_submit_button("🔎 Aplicar filtros", use_container_width=True)

    df_f = filtrar(df_live, f_razon if not es_dealer else "TODOS", f_sup, f_coord, f_dep, f_prov, f_estado)
    if df_f.empty:
        st.warning("No hay registros con los filtros seleccionados.")
        return

    df_f["_EDITABLE_FECHA"] = df_f.apply(lambda r: editable_en_fecha(r, fecha_sel), axis=1)
    df_editor_base = df_f[df_f["_EDITABLE_FECHA"]].copy()

    st.caption(f"Registros encontrados: **{len(df_f)}** | Editables para el día seleccionado: **{len(df_editor_base)}**")

    if df_editor_base.empty:
        st.warning("No hay personal editable para el día seleccionado. Puede ser por fecha de alta/cese o estado inactivo.")
        return

    if len(df_editor_base) > MAX_FILAS_EDITOR:
        st.warning(f"⚠️ Hay {len(df_editor_base)} registros. Se muestran {MAX_FILAS_EDITOR} por vista para proteger el navegador. No borra datos.")
        paginas = list(range(1, (len(df_editor_base) + MAX_FILAS_EDITOR - 1) // MAX_FILAS_EDITOR + 1))
        pag = st.selectbox("Bloque de registros", paginas, index=0, key="asis_bloque")
        ini = (int(pag) - 1) * MAX_FILAS_EDITOR
        df_editor_base = df_editor_base.iloc[ini:ini + MAX_FILAS_EDITOR].copy()

    st.markdown("<span class='wow-section-title'>✏️ Registrar presencialidad</span>", unsafe_allow_html=True)
    st.info("**Motivos de validación:** " + LEYENDA)

    editor_cols = DISPLAY_COLS + [col_dia, "ROW_SHEET"]
    for c in editor_cols:
        if c not in df_editor_base.columns:
            df_editor_base[c] = ""
    df_editor = df_editor_base[editor_cols].copy()
    df_editor[col_dia] = df_editor[col_dia].map(limpiar_marca)

    editado = st.data_editor(
        df_editor,
        use_container_width=True,
        height=min(500, 70 + len(df_editor) * 32),
        hide_index=True,
        disabled=[c for c in editor_cols if c != col_dia],
        column_config={
            col_dia: st.column_config.SelectboxColumn(col_dia, options=MARCAS, width="small"),
            "ROW_SHEET": st.column_config.TextColumn("FILA", disabled=True, width="small"),
        },
        num_rows="fixed",
        key=f"editor_presencialidad_{periodo}_{col_dia}_{usuario_razon}",
    )

    df_edit = pd.DataFrame(editado).fillna("")
    cambios = []
    for i, r in df_edit.iterrows():
        marca_nueva = limpiar_marca(r.get(col_dia, ""))
        marca_original = limpiar_marca(df_editor.iloc[i].get(col_dia, "")) if i < len(df_editor) else ""
        if marca_nueva != marca_original:
            cambios.append((i, r, marca_nueva, marca_original))

    necesita_sustento = [x for x in cambios if x[2] == "A-BM"]
    archivo_bm = None
    if necesita_sustento:
        st.warning(f"Se detectó A-BM en {len(necesita_sustento)} registro(s). Adjunta sustento para guardar.")
        archivo_bm = st.file_uploader(
            "Adjuntar sustento de Baja Médica (PDF o imagen)",
            type=["pdf", "png", "jpg", "jpeg"],
            key=f"file_abm_{periodo}_{dia}",
        )

    if st.button("💾 Guardar Presencialidad", key=f"btn_guardar_presencialidad_{periodo}_{dia}"):
        if not cambios:
            st.info("No hay cambios para guardar.")
            return

        if fecha_sel != hoy_lima():
            no_abm = [x for x in cambios if x[2] != "A-BM"]
            if no_abm:
                st.error("Para días anteriores/futuros solo se permite registrar A-BM con sustento. Las demás marcas solo aplican al día actual.")
                return
        if necesita_sustento and archivo_bm is None:
            st.error("Falta adjuntar sustento obligatorio para A-BM.")
            return

        try:
            guardados = 0
            for _, r, marca, _orig in cambios:
                if marca == "A-BM":
                    guardar_sustento(r, periodo, dia, archivo_bm)
                guardar_marca(hoja_asistencia, r, headers, col_dia, marca)
                guardados += 1
                time.sleep(0.05)
            st.success(f"✅ Presencialidad guardada correctamente. Cambios aplicados: {guardados}")
            st.rerun()
        except Exception as e:
            st.error(f"Error guardando presencialidad: {e}")

    # Espejo mensual NO carga todo por defecto para proteger Render Free.
    with st.expander("📊 Ver espejo del día seleccionado", expanded=False):
        cols_espejo = DISPLAY_COLS + [col_dia]
        st.dataframe(df_f[cols_espejo].copy(), use_container_width=True, hide_index=True, height=420)

    # Matriz de jerarquía bajo demanda. No cargar automáticamente.
    if registro_mod is not None:
        st.divider()
        st.markdown("<span class='wow-section-title'>📋 Matriz de jerarquía</span>", unsafe_allow_html=True)
        if st.button("📥 Cargar / descargar matriz de jerarquía", key="btn_cargar_matriz_jerarquia"):
            try:
                registro_mod.mostrar_tabla(hoja_colaboradores, razon)
            except Exception as e:
                st.warning(f"No se pudo cargar la matriz de jerarquía: {e}")
