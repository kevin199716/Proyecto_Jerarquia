# FIX_ASISTENCIA_LIVE_NO_AUTO_WRITE_TABLA_VISIBLE_20260601
# Presencialidad Dealer: lectura en vivo + guardado puntual. No sincroniza ni escribe al abrir.

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
LEYENDA = "A = Asistió · A-BM = No Asistió por Baja Médica · A-VAC = No Asistió por Vacaciones · NA-SA = No Asistió - Sin aviso · NA-CA = No Asistió - Con aviso"

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


def asegurar_headers_asistencia(hoja_asistencia):
    """Solo crea cabecera si la hoja está totalmente vacía. No borra nada."""
    vals = hoja_asistencia.get_all_values()
    if not vals:
        hoja_asistencia.append_row(ALL_COLS, value_input_option="USER_ENTERED")
        return ALL_COLS.copy()
    headers = [normalizar_texto(h).upper() for h in vals[0]]
    # No agregamos columnas automáticamente para evitar escrituras al abrir.
    return headers


def leer_sheet_df(worksheet) -> pd.DataFrame:
    vals = worksheet.get_all_values()
    if not vals:
        return pd.DataFrame()
    headers = [normalizar_texto(h).upper() for h in vals[0]]
    rows = vals[1:]
    rows = [r + [""] * (len(headers) - len(r)) if len(r) < len(headers) else r[:len(headers)] for r in rows]
    df = pd.DataFrame(rows, columns=headers)
    df["ROW_SHEET"] = range(2, len(df) + 2)
    return df


def nombre_colaborador(row: pd.Series) -> str:
    if "NOMBRE" in row and normalizar_texto(row.get("NOMBRE")):
        return normalizar_texto(row.get("NOMBRE"))
    partes = [row.get("NOMBRES", ""), row.get("APELLIDO PATERNO", ""), row.get("APELLIDO MATERNO", "")]
    return " ".join([normalizar_texto(p) for p in partes if normalizar_texto(p)]).strip()


def construir_base_colaboradores(hoja_colaboradores, periodo: str) -> pd.DataFrame:
    df = leer_sheet_df(hoja_colaboradores)
    if df.empty:
        return pd.DataFrame(columns=BASE_COLS)

    # Solo promotores/agentes operativos; si no existe cargo, no bloquea.
    if "CARGO (ROL)" in df.columns:
        cargo = df["CARGO (ROL)"].astype(str).str.upper()
        df = df[cargo.str.contains("PROMOTOR|AGENTE", na=False)].copy()

    out = pd.DataFrame()
    out["RAZON SOCIAL"] = df.get("RAZON SOCIAL", "").apply(normalizar_texto) if "RAZON SOCIAL" in df else ""
    out["SUPERVISOR"] = df.get("SUPERVISOR A CARGO", df.get("SUPERVISOR", "")).apply(normalizar_texto) if any(c in df.columns for c in ["SUPERVISOR A CARGO", "SUPERVISOR"]) else ""
    out["COORDINADOR"] = df.get("COORDINADOR", "").apply(normalizar_texto) if "COORDINADOR" in df else ""
    out["DEPARTAMENTO"] = df.get("DEPARTAMENTO", "").apply(normalizar_texto) if "DEPARTAMENTO" in df else ""
    out["PROVINCIA"] = df.get("PROVINCIA", "").apply(normalizar_texto) if "PROVINCIA" in df else ""
    out["DNI"] = df.get("DNI", "").apply(normalizar_dni) if "DNI" in df else ""
    out["NOMBRE"] = df.apply(nombre_colaborador, axis=1)
    out["ESTADO"] = df.get("ESTADO", "ACTIVO").apply(lambda x: normalizar_texto(x).upper()) if "ESTADO" in df else "ACTIVO"
    out["FECHA_ALTA"] = df.get("FECHA DE CREACION USUARIO", df.get("FECHA_ALTA", "")).apply(fecha_str) if any(c in df.columns for c in ["FECHA DE CREACION USUARIO", "FECHA_ALTA"]) else ""
    out["FECHA_CESE"] = df.get("FECHA DE CESE", df.get("FECHA_CESE", "")).apply(fecha_str) if any(c in df.columns for c in ["FECHA DE CESE", "FECHA_CESE"]) else ""
    out["MES"] = str(int(periodo[-2:]))
    out["PERIODO"] = periodo
    out = out[out["DNI"].astype(str).str.strip().ne("")].copy()
    out["KEY"] = out["DNI"].astype(str) + "|" + out["FECHA_ALTA"].astype(str) + "|" + periodo
    out = out.drop_duplicates("KEY", keep="last")
    return out


def leer_asistencia(hoja_asistencia) -> tuple[pd.DataFrame, list[str]]:
    headers = asegurar_headers_asistencia(hoja_asistencia)
    df = leer_sheet_df(hoja_asistencia)
    if df.empty:
        df = pd.DataFrame(columns=headers + ["ROW_SHEET"])
    for c in ALL_COLS:
        if c not in df.columns:
            df[c] = ""
    if "ROW_SHEET" not in df.columns:
        df["ROW_SHEET"] = ""
    df["DNI"] = df["DNI"].apply(normalizar_dni)
    df["FECHA_ALTA"] = df["FECHA_ALTA"].apply(fecha_str)
    df["PERIODO"] = df["PERIODO"].apply(normalizar_texto)
    df["KEY"] = df["DNI"].astype(str) + "|" + df["FECHA_ALTA"].astype(str) + "|" + df["PERIODO"].astype(str)
    return df, headers


def vista_live(hoja_colaboradores, hoja_asistencia, periodo: str) -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    base = construir_base_colaboradores(hoja_colaboradores, periodo)
    asis, headers = leer_asistencia(hoja_asistencia)
    asis_p = asis[asis["PERIODO"].astype(str).eq(periodo)].copy()

    cols_marca = [c for c in DAY_COLS if c in asis_p.columns]
    marcas = asis_p[["KEY", "ROW_SHEET"] + cols_marca].drop_duplicates("KEY", keep="last") if not asis_p.empty else pd.DataFrame(columns=["KEY", "ROW_SHEET"] + cols_marca)

    live = base.merge(marcas, on="KEY", how="left", suffixes=("", "_ASIS"))
    for c in DAY_COLS:
        if c not in live.columns:
            live[c] = ""
        live[c] = live[c].apply(limpiar_marca)
    if "ROW_SHEET" not in live.columns:
        live["ROW_SHEET"] = ""
    live["ROW_SHEET"] = live["ROW_SHEET"].fillna("")
    return live, asis, headers


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


def editable_en_fecha(row, fecha_sel: date, marca_abm=False):
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


def guardar_marca(hoja_asistencia, row: pd.Series, headers: list[str], col_dia: str, marca: str):
    headers = [normalizar_texto(h).upper() for h in headers]
    if not headers:
        headers = ALL_COLS.copy()
    # Asegurar columnas mínimas en memoria; no crear columnas al abrir, solo al guardar si no existe día crítico.
    if col_dia not in headers:
        raise Exception(f"La hoja Asistencia no tiene la columna {col_dia}. Revisa cabecera de la hoja.")

    row_sheet = normalizar_texto(row.get("ROW_SHEET"))
    col_idx = headers.index(col_dia) + 1
    col_letra = _letra_col(col_idx)

    if row_sheet.isdigit():
        hoja_asistencia.update_acell(f"{col_letra}{int(row_sheet)}", marca)
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
    return "nuevo"


def _letra_col(n):
    out = ""
    while n:
        n, rem = divmod(n - 1, 26)
        out = chr(65 + rem) + out
    return out


def mostrar_asistencia(hoja_asistencia, hoja_colaboradores, registro_mod=None, razon=None):
    st.markdown("<span class='wow-section-title'>🗓️ Presencialidad Dealer</span>", unsafe_allow_html=True)

    usuario_razon = normalizar_texto(razon if razon is not None else st.session_state.get("razon", "ALL"))
    rol = normalizar_texto(st.session_state.get("rol", "")).lower()
    es_dealer = usuario_razon and usuario_razon.upper() != "ALL"

    periodos = periodos_disponibles()
    periodo = st.selectbox("PERIODO", periodos, index=0, key="asis_periodo")
    y, m = map(int, periodo.split("-"))
    dias = list(range(1, calendar.monthrange(y, m)[1] + 1))
    dia_default = hoy_lima().day if periodo == periodo_lima() and hoy_lima().day in dias else 1
    dia = st.selectbox("DÍA", dias, index=dias.index(dia_default), key="asis_dia")
    col_dia = f"DIA_{dia}"
    fecha_sel = fecha_desde_periodo_dia(periodo, dia)

    st.info(f"📅 Periodo: **{periodo}** | Día seleccionado: **{col_dia}** | La información se lee al abrir/refrescar la página. Solo se escribe al presionar **Guardar Presencialidad**. A-BM permite sustento histórico.")

    with st.spinner("Cargando información desde Drive…"):
        try:
            df_live, df_asis, headers = vista_live(hoja_colaboradores, hoja_asistencia, periodo)
        except Exception as e:
            st.error(f"No se pudo cargar presencialidad: {e}")
            return

    if es_dealer:
        df_live = df_live[df_live["RAZON SOCIAL"].map(normalizar_razon).eq(normalizar_razon(usuario_razon))].copy()

    if df_live.empty:
        st.warning("No hay colaboradores para mostrar con este usuario/periodo. Revisa que la razón social del usuario coincida con la hoja colaboradores.")
        return

    # Filtros solo en memoria.
    with st.form("form_filtros_presencialidad"):
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

    # Filas editables: marca normal solo día actual. A-BM se permite para cualquier día, pero la fila debe ser válida para esa fecha.
    df_f["_EDITABLE_FECHA"] = df_f.apply(lambda r: editable_en_fecha(r, fecha_sel), axis=1)
    df_editor_base = df_f[df_f["_EDITABLE_FECHA"]].copy()

    st.caption(f"Registros encontrados: **{len(df_f)}** | Editables para el día seleccionado: **{len(df_editor_base)}**")

    if df_editor_base.empty:
        st.warning("No hay personal editable para el día seleccionado. Puede ser por fecha de alta/cese o estado inactivo.")
        return

    if len(df_editor_base) > MAX_FILAS_EDITOR:
        st.warning(f"⚠️ Hay {len(df_editor_base)} registros. Se muestran {MAX_FILAS_EDITOR} por vista para proteger el navegador. No borra datos.")
        paginas = list(range(1, (len(df_editor_base) + MAX_FILAS_EDITOR - 1) // MAX_FILAS_EDITOR + 1))
        pag = st.selectbox("Bloque de registros", paginas, index=0)
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
        height=min(520, 70 + len(df_editor) * 34),
        hide_index=True,
        disabled=[c for c in editor_cols if c != col_dia],
        column_config={
            col_dia: st.column_config.SelectboxColumn(col_dia, options=MARCAS, width="small"),
            "ROW_SHEET": st.column_config.TextColumn("FILA", disabled=True, width="small"),
        },
        num_rows="fixed",
        key="editor_presencialidad_live",
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
        archivo_bm = st.file_uploader("Adjuntar sustento de Baja Médica (PDF o imagen)", type=["pdf", "png", "jpg", "jpeg"], key="file_abm")

    if st.button("💾 Guardar Presencialidad", key="btn_guardar_presencialidad"):
        if not cambios:
            st.info("No hay cambios para guardar.")
            return

        # Validación: marcas normales solo hoy. A-BM puede ser cualquier día del periodo.
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

    with st.expander("📊 Ver espejo mensual / descarga"):
        cols_espejo = DISPLAY_COLS + [c for c in DAY_COLS if c in df_f.columns]
        st.dataframe(df_f[cols_espejo].copy(), use_container_width=True, hide_index=True, height=420)

    if registro_mod is not None:
        st.divider()
        st.markdown("<span class='wow-section-title'>📋 Matriz de jerarquía</span>", unsafe_allow_html=True)
        try:
            registro_mod.mostrar_tabla(hoja_colaboradores, razon)
        except Exception as e:
            st.warning(f"No se pudo cargar la matriz de jerarquía: {e}")
