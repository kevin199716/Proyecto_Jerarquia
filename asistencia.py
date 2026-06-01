"""
asistencia.py — CONTROL DE PRESENCIALIDAD POR PERIODO
FIX_PERIODO_MES_A_BM_HISTORICO_20260601

Reglas:
- Selector de PERIODO: permite validar mayo, junio u otros periodos existentes.
- Botón Sincronizar periodo: crea/actualiza el periodo seleccionado sin borrar histórico.
- El editor trabaja por día seleccionado del periodo.
- Motivos permitidos: A, A-BM, A-VAC, NA-SA, NA-CA.
- A-BM se registra también como histórico en Sustentos_Bajas usando append_row.
"""

import calendar
import time
from datetime import datetime, date

import pandas as pd
import pytz
import streamlit as st

# =====================================================
# ZONA HORARIA PERÚ
# =====================================================
ZONA_PERU = pytz.timezone("America/Lima")


def ahora_peru() -> datetime:
    return datetime.now(ZONA_PERU)


def periodo_actual_peru() -> str:
    return ahora_peru().strftime("%Y-%m")


def mes_actual_peru() -> str:
    return str(ahora_peru().month)


def hoy_dia_peru() -> int:
    return ahora_peru().day


def fecha_hora_peru_str() -> str:
    return ahora_peru().strftime("%Y-%m-%d %H:%M:%S")


# =====================================================
# CONSTANTES
# =====================================================
COLUMNAS_BASE = [
    "DNI", "NOMBRE", "SUPERVISOR", "COORDINADOR", "DEPARTAMENTO", "PROVINCIA",
    "ESTADO", "FECHA_ALTA", "FECHA_CESE", "MES", "PERIODO",
]
COLUMNAS_DIAS = [f"DIA_{i}" for i in range(1, 32)]
COLUMNAS_ASISTENCIA = COLUMNAS_BASE + COLUMNAS_DIAS

COLUMNAS_FIJAS_EDITOR = [
    "DNI", "NOMBRE", "SUPERVISOR", "COORDINADOR", "DEPARTAMENTO", "PROVINCIA",
    "ESTADO", "FECHA_ALTA", "FECHA_CESE", "MES", "PERIODO",
]

MARCAS_VALIDAS = ["", "A", "A-BM", "A-VAC", "NA-SA", "NA-CA"]

KEY_DF_TOTAL = "asis_df_total_cache"
KEY_DF_ORIGINAL = "asis_df_original_cache"
KEY_HEADERS = "asis_headers_cache"
KEY_LOADED = "asis_loaded"
KEY_LOAD_TS = "asis_load_timestamp"
CACHE_TTL = 300
MAX_FILAS_EDITOR = 200


# =====================================================
# UTILIDADES
# =====================================================
def limpiar_texto(valor) -> str:
    if pd.isna(valor) if not isinstance(valor, str) else False:
        return ""
    s = str(valor).strip()
    return "" if s.upper() in ("NONE", "NAN", "NULL") else s


def normalizar_columnas(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = df.columns.astype(str).str.strip().str.upper()
    return df


def limpiar_marca(valor) -> str:
    v = limpiar_texto(valor).upper()
    return v if v in MARCAS_VALIDAS else ""


def letra_columna(numero: int) -> str:
    letras = ""
    while numero:
        numero, resto = divmod(numero - 1, 26)
        letras = chr(65 + resto) + letras
    return letras


def parse_fecha(valor):
    if valor in (None, ""):
        return None
    try:
        f = pd.to_datetime(valor, errors="coerce", dayfirst=False)
        if pd.isna(f):
            return None
        return f.date()
    except Exception:
        return None


def dias_del_periodo(periodo: str) -> list[int]:
    try:
        anio, mes = [int(x) for x in str(periodo).split("-")[:2]]
        ultimo = calendar.monthrange(anio, mes)[1]
        return list(range(1, ultimo + 1))
    except Exception:
        return list(range(1, 32))


def primer_dia_periodo(periodo: str) -> date:
    anio, mes = [int(x) for x in str(periodo).split("-")[:2]]
    return date(anio, mes, 1)


def ultimo_dia_periodo(periodo: str) -> date:
    anio, mes = [int(x) for x in str(periodo).split("-")[:2]]
    ultimo = calendar.monthrange(anio, mes)[1]
    return date(anio, mes, ultimo)


def periodo_a_mes(periodo: str) -> str:
    try:
        return str(int(str(periodo).split("-")[1]))
    except Exception:
        return mes_actual_peru()


def normalizar_dni(valor) -> str:
    import re
    return re.sub(r"\D", "", limpiar_texto(valor).replace(".0", ""))


def es_promotor(row: pd.Series) -> bool:
    for col in ("CARGO (ROL)", "CARGO", "ROL"):
        if col in row.index:
            cargo = limpiar_texto(row.get(col, "")).upper()
            if cargo:
                return "PROMOTOR" in cargo or "AGENTE" in cargo or "CEX" in cargo
    return True


def esta_vigente_en_periodo(row: pd.Series, periodo: str) -> bool:
    estado = limpiar_texto(row.get("ESTADO", "")).upper()
    fecha_alta = parse_fecha(row.get("FECHA DE CREACION USUARIO", row.get("FECHA_ALTA", "")))
    fecha_cese = parse_fecha(row.get("FECHA DE CESE", row.get("FECHA_CESE", "")))
    ini = primer_dia_periodo(periodo)
    fin = ultimo_dia_periodo(periodo)

    if fecha_alta and fecha_alta > fin:
        return False
    if estado == "ACTIVO":
        return True
    if estado == "INACTIVO" and fecha_cese:
        # Visible solo si estuvo activo en algún momento del periodo.
        return fecha_cese >= ini
    return False


# =====================================================
# GOOGLE SHEETS
# =====================================================
def obtener_headers(hoja) -> list[str]:
    valores = hoja.get_all_values()
    if not valores:
        return []
    return [limpiar_texto(x).upper() for x in valores[0]]


def validar_o_crear_cabecera(hoja_asistencia) -> bool:
    valores = hoja_asistencia.get_all_values()
    if not valores:
        hoja_asistencia.append_row(COLUMNAS_ASISTENCIA, value_input_option="USER_ENTERED")
        return True

    headers = [limpiar_texto(x).upper() for x in valores[0]]
    faltantes_minimos = [c for c in ["DNI", "NOMBRE", "ESTADO", "MES", "PERIODO", "DIA_1"] if c not in headers]
    if faltantes_minimos:
        st.error("La hoja Asistencia tiene cabecera incompleta.")
        st.write("Columnas mínimas faltantes:", faltantes_minimos)
        st.warning("Si la hoja está vacía o dañada, borra su contenido y presiona Sincronizar periodo.")
        return False
    return True


def leer_asistencia_drive(hoja_asistencia) -> tuple[pd.DataFrame, list[str]]:
    valores = hoja_asistencia.get_all_values()
    if not valores:
        return pd.DataFrame(columns=COLUMNAS_ASISTENCIA), COLUMNAS_ASISTENCIA.copy()

    headers = [limpiar_texto(x).upper() for x in valores[0]]
    data = valores[1:]
    n = len(headers)
    filas = []
    for fila in data:
        fila = list(fila)
        if len(fila) < n:
            fila += [""] * (n - len(fila))
        filas.append(fila[:n])

    df = pd.DataFrame(filas, columns=headers)
    df = normalizar_columnas(df).fillna("").replace("None", "").replace("nan", "")
    for col in COLUMNAS_ASISTENCIA:
        if col not in df.columns:
            df[col] = ""
    df["ROW_SHEET"] = df.index + 2
    for col in COLUMNAS_DIAS:
        if col in df.columns:
            df[col] = df[col].map(limpiar_marca)
    return df, headers


def leer_colaboradores_drive(hoja_colaboradores) -> pd.DataFrame:
    try:
        data = hoja_colaboradores.get_all_records()
    except Exception as e:
        st.error(f"Error leyendo colaboradores: {e}")
        return pd.DataFrame()
    df = pd.DataFrame(data)
    if df.empty:
        return df
    return normalizar_columnas(df).fillna("").replace("None", "")


def construir_fila_asistencia(headers: list[str], row: pd.Series, periodo: str) -> list[str]:
    nombre = " ".join([
        limpiar_texto(row.get("NOMBRES", row.get("NOMBRE", ""))),
        limpiar_texto(row.get("APELLIDO PATERNO", "")),
        limpiar_texto(row.get("APELLIDO MATERNO", "")),
    ]).strip()
    fila_dict = {
        "DNI": normalizar_dni(row.get("DNI", "")),
        "NOMBRE": nombre,
        "SUPERVISOR": limpiar_texto(row.get("SUPERVISOR A CARGO", row.get("SUPERVISOR", ""))),
        "COORDINADOR": limpiar_texto(row.get("COORDINADOR", "")),
        "DEPARTAMENTO": limpiar_texto(row.get("DEPARTAMENTO", "")),
        "PROVINCIA": limpiar_texto(row.get("PROVINCIA", "")),
        "ESTADO": limpiar_texto(row.get("ESTADO", "")),
        "FECHA_ALTA": limpiar_texto(row.get("FECHA DE CREACION USUARIO", row.get("FECHA_ALTA", ""))),
        "FECHA_CESE": limpiar_texto(row.get("FECHA DE CESE", row.get("FECHA_CESE", ""))),
        "MES": periodo_a_mes(periodo),
        "PERIODO": periodo,
    }
    for c in COLUMNAS_DIAS:
        fila_dict[c] = ""
    return [fila_dict.get(h, "") for h in headers]


def sincronizar_periodo(hoja_asistencia, hoja_colaboradores, periodo: str) -> int:
    if not validar_o_crear_cabecera(hoja_asistencia):
        return 0
    df_asistencia, headers = leer_asistencia_drive(hoja_asistencia)
    if not headers:
        headers = COLUMNAS_ASISTENCIA.copy()

    dnis_existentes = set()
    if not df_asistencia.empty:
        dnis_existentes = set(
            df_asistencia.loc[df_asistencia["PERIODO"].astype(str).eq(periodo), "DNI"]
            .astype(str).str.strip().tolist()
        )

    df_colab = leer_colaboradores_drive(hoja_colaboradores)
    if df_colab.empty or "DNI" not in df_colab.columns:
        return 0

    nuevas = []
    for _, row in df_colab.iterrows():
        dni = normalizar_dni(row.get("DNI", ""))
        if not dni or dni in dnis_existentes:
            continue
        if not es_promotor(row):
            continue
        if not esta_vigente_en_periodo(row, periodo):
            continue
        nuevas.append(construir_fila_asistencia(headers, row, periodo))

    if nuevas:
        for i in range(0, len(nuevas), 500):
            hoja_asistencia.append_rows(nuevas[i:i + 500], value_input_option="USER_ENTERED")
            time.sleep(0.3)
    return len(nuevas)


# =====================================================
# SUSTENTOS_BAJAS HISTÓRICO
# =====================================================
def obtener_hoja_sustentos():
    try:
        from sheets import conectar_google_sheets
        return conectar_google_sheets("maestra_vendedores", "Sustentos_Bajas")
    except Exception:
        return None


def asegurar_cabecera_sustentos(hoja_sustentos):
    if hoja_sustentos is None:
        return
    headers = hoja_sustentos.row_values(1)
    if headers:
        return
    hoja_sustentos.append_row([
        "FECHA_REGISTRO", "USUARIO", "PERIODO", "DIA", "COLUMNA_DIA",
        "DNI", "NOMBRE", "SUPERVISOR", "COORDINADOR", "DEPARTAMENTO", "PROVINCIA",
        "MOTIVO", "OBSERVACION",
    ], value_input_option="USER_ENTERED")


def registrar_sustento_bm_historico(hoja_sustentos, usuario: str, periodo: str, dia: int, row: pd.Series):
    if hoja_sustentos is None:
        return
    asegurar_cabecera_sustentos(hoja_sustentos)
    hoja_sustentos.append_row([
        fecha_hora_peru_str(), usuario, periodo, str(dia), f"DIA_{dia}",
        limpiar_texto(row.get("DNI", "")), limpiar_texto(row.get("NOMBRE", "")),
        limpiar_texto(row.get("SUPERVISOR", "")), limpiar_texto(row.get("COORDINADOR", "")),
        limpiar_texto(row.get("DEPARTAMENTO", "")), limpiar_texto(row.get("PROVINCIA", "")),
        "A-BM", "Registro histórico automático por marcación A-BM",
    ], value_input_option="USER_ENTERED")


# =====================================================
# CACHÉ
# =====================================================
def cache_vencido() -> bool:
    ts = st.session_state.get(KEY_LOAD_TS, 0)
    return (time.time() - ts) > CACHE_TTL


def cargar_cache_desde_drive(hoja_asistencia, forzar: bool = False) -> None:
    if not forzar and st.session_state.get(KEY_LOADED) and not cache_vencido():
        return
    with st.spinner("Cargando datos desde Google Drive…"):
        df_total, headers = leer_asistencia_drive(hoja_asistencia)
    st.session_state[KEY_DF_TOTAL] = df_total.copy()
    st.session_state[KEY_DF_ORIGINAL] = df_total.copy()
    st.session_state[KEY_HEADERS] = headers
    st.session_state[KEY_LOADED] = True
    st.session_state[KEY_LOAD_TS] = time.time()


# =====================================================
# FILTROS
# =====================================================
def lista_opciones(df: pd.DataFrame, columna: str) -> list[str]:
    if df.empty or columna not in df.columns:
        return ["TODOS"]
    valores = df[columna].astype(str).str.strip().replace("", pd.NA).dropna().unique().tolist()
    return ["TODOS"] + sorted(valores)


def filtrar_df(df: pd.DataFrame, supervisor: str, coordinador: str, departamento: str) -> pd.DataFrame:
    r = df.copy()
    if supervisor != "TODOS":
        r = r[r["SUPERVISOR"].astype(str).str.strip().eq(supervisor)]
    if coordinador != "TODOS":
        r = r[r["COORDINADOR"].astype(str).str.strip().eq(coordinador)]
    if departamento != "TODOS":
        r = r[r["DEPARTAMENTO"].astype(str).str.strip().eq(departamento)]
    return r


def periodos_disponibles(df_total: pd.DataFrame) -> list[str]:
    actual = periodo_actual_peru()
    vals = []
    if not df_total.empty and "PERIODO" in df_total.columns:
        vals = df_total["PERIODO"].astype(str).str.strip().replace("", pd.NA).dropna().unique().tolist()
    vals = sorted(set(vals + [actual]), reverse=True)
    return vals


# =====================================================
# GUARDADO
# =====================================================
def preparar_updates_dia(df_editado: pd.DataFrame, df_original: pd.DataFrame, headers: list[str], col_dia: str):
    if df_editado.empty or df_original.empty or "ROW_SHEET" not in df_editado.columns:
        return [], []
    mapa_col = {limpiar_texto(col).upper(): idx + 1 for idx, col in enumerate(headers)}
    if col_dia not in mapa_col:
        return [], []

    e = df_editado.copy()
    o = df_original.copy()
    e["ROW_SHEET"] = pd.to_numeric(e["ROW_SHEET"], errors="coerce")
    o["ROW_SHEET"] = pd.to_numeric(o["ROW_SHEET"], errors="coerce")
    e = e.dropna(subset=["ROW_SHEET"])
    o = o.dropna(subset=["ROW_SHEET"])
    e["ROW_SHEET"] = e["ROW_SHEET"].astype(int)
    o["ROW_SHEET"] = o["ROW_SHEET"].astype(int)
    orig = o.drop_duplicates("ROW_SHEET", keep="last").set_index("ROW_SHEET")

    updates = []
    cambios_bm = []
    col_num = mapa_col[col_dia]
    col_letra = letra_columna(col_num)

    for _, row in e.iterrows():
        rs = int(row["ROW_SHEET"])
        if rs not in orig.index:
            continue
        nuevo = limpiar_marca(row.get(col_dia, ""))
        anterior = limpiar_marca(orig.loc[rs].get(col_dia, ""))
        if nuevo == anterior:
            continue
        updates.append({"range": f"{col_letra}{rs}", "values": [[nuevo]]})
        if nuevo == "A-BM":
            cambios_bm.append(row)
    return updates, cambios_bm


def actualizar_cache_dia(df_editado: pd.DataFrame, col_dia: str):
    if KEY_DF_TOTAL not in st.session_state or df_editado.empty:
        return
    df_total = st.session_state[KEY_DF_TOTAL].copy()
    patch = df_editado[["ROW_SHEET", col_dia]].copy()
    patch["ROW_SHEET"] = pd.to_numeric(patch["ROW_SHEET"], errors="coerce")
    patch = patch.dropna(subset=["ROW_SHEET"])
    patch["ROW_SHEET"] = patch["ROW_SHEET"].astype(int)
    patch[col_dia] = patch[col_dia].map(limpiar_marca)
    patch = patch.drop_duplicates("ROW_SHEET", keep="last").set_index("ROW_SHEET")
    df_total["_rk"] = pd.to_numeric(df_total["ROW_SHEET"], errors="coerce")
    mapped = df_total["_rk"].map(patch[col_dia])
    ok = mapped.notna()
    df_total.loc[ok, col_dia] = mapped[ok].values
    df_total = df_total.drop(columns=["_rk"])
    st.session_state[KEY_DF_TOTAL] = df_total.copy()
    st.session_state[KEY_DF_ORIGINAL] = df_total.copy()
    st.session_state[KEY_LOAD_TS] = time.time()


# =====================================================
# ESTILOS / ESPEJO
# =====================================================
def estilo_asistencia(valor: str) -> str:
    v = limpiar_marca(valor)
    if v == "A":
        return "background-color:#D4EDDA;color:#155724;font-weight:bold;text-align:center;"
    if v in ("NA-SA", "NA-CA"):
        return "background-color:#F8D7DA;color:#721C24;font-weight:bold;text-align:center;"
    if v == "A-BM":
        return "background-color:#FFF3CD;color:#856404;font-weight:bold;text-align:center;"
    if v == "A-VAC":
        return "background-color:#D1ECF1;color:#0C5460;font-weight:bold;text-align:center;"
    return "text-align:center;"


def mostrar_espejo_mes(df: pd.DataFrame, dias_validos: list[int]) -> None:
    if df.empty:
        st.info("No hay datos para mostrar.")
        return
    cols_dias = [f"DIA_{d}" for d in dias_validos if f"DIA_{d}" in df.columns]
    columnas = [c for c in COLUMNAS_FIJAS_EDITOR if c in df.columns] + cols_dias
    df_vista = df[columnas].copy()
    try:
        styler = df_vista.style.applymap(estilo_asistencia, subset=cols_dias)
        st.dataframe(styler, use_container_width=True, height=420)
    except Exception:
        st.dataframe(df_vista, use_container_width=True, height=420)


# =====================================================
# MAIN
# =====================================================
def mostrar_asistencia(hoja_asistencia, hoja_colaboradores, registro_mod=None, razon=None):
    st.markdown("<span class='wow-section-title'>🗓️ Presencialidad Dealer</span>", unsafe_allow_html=True)

    if not validar_o_crear_cabecera(hoja_asistencia):
        return

    cargar_cache_desde_drive(hoja_asistencia)
    df_total = st.session_state.get(KEY_DF_TOTAL, pd.DataFrame()).copy()
    headers = st.session_state.get(KEY_HEADERS, COLUMNAS_ASISTENCIA)

    periodos = periodos_disponibles(df_total)
    actual = periodo_actual_peru()

    c0, c1, c2, c3 = st.columns([1.5, 1.2, 1.2, 4])
    with c0:
        periodo_sel = st.selectbox("PERIODO", periodos, index=periodos.index(actual) if actual in periodos else 0, key="asis_periodo_sel")
    dias_validos = dias_del_periodo(periodo_sel)
    dia_default = hoy_dia_peru() if periodo_sel == actual and hoy_dia_peru() in dias_validos else max(dias_validos)
    with c1:
        dia_sel = st.selectbox("DÍA", dias_validos, index=dias_validos.index(dia_default), key="asis_dia_sel")
    col_dia = f"DIA_{dia_sel}"

    with c2:
        if st.button("🔄 Sincronizar periodo", key="btn_sync_periodo"):
            with st.spinner("Sincronizando periodo con Drive…"):
                try:
                    nuevos = sincronizar_periodo(hoja_asistencia, hoja_colaboradores, periodo_sel)
                    cargar_cache_desde_drive(hoja_asistencia, forzar=True)
                    st.success(f"✅ Periodo {periodo_sel} sincronizado. Registros nuevos: {nuevos}")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error sincronizando: {e}")
                    return

    with c3:
        st.info(
            f"Periodo seleccionado: **{periodo_sel}** | Día en edición: **{col_dia}** | "
            "A-BM puede registrarse para cualquier día del periodo seleccionado."
        )

    if st.button("♻️ Recargar Drive", key="btn_reload_asistencia"):
        cargar_cache_desde_drive(hoja_asistencia, forzar=True)
        st.success("✅ Datos actualizados desde Drive.")
        st.rerun()

    df_total = st.session_state.get(KEY_DF_TOTAL, pd.DataFrame()).copy()
    df_original = st.session_state.get(KEY_DF_ORIGINAL, pd.DataFrame()).copy()
    for col in COLUMNAS_ASISTENCIA + ["ROW_SHEET"]:
        if col not in df_total.columns:
            df_total[col] = ""
        if col not in df_original.columns:
            df_original[col] = ""

    df_mes = df_total[df_total["PERIODO"].astype(str).eq(periodo_sel)].copy()
    if df_mes.empty:
        st.warning(f"⚠️ No hay registros para el periodo {periodo_sel}. Presiona Sincronizar periodo.")
        return

    f1, f2, f3 = st.columns(3)
    with f1:
        filtro_supervisor = st.selectbox("Supervisor", lista_opciones(df_mes, "SUPERVISOR"), key="asis_supervisor")
    df_base_coord = filtrar_df(df_mes, filtro_supervisor, "TODOS", "TODOS")
    with f2:
        filtro_coord = st.selectbox("Coordinador", lista_opciones(df_base_coord, "COORDINADOR"), key="asis_coordinador")
    df_base_dep = filtrar_df(df_base_coord, "TODOS", filtro_coord, "TODOS")
    with f3:
        filtro_dep = st.selectbox("Departamento", lista_opciones(df_base_dep, "DEPARTAMENTO"), key="asis_departamento")

    df_filtrado = filtrar_df(df_mes, filtro_supervisor, filtro_coord, filtro_dep)
    if df_filtrado.empty:
        st.warning("No hay registros con los filtros seleccionados.")
        return

    total_filtrado = len(df_filtrado)
    st.caption(f"Registros encontrados: **{total_filtrado}**")

    if total_filtrado > MAX_FILAS_EDITOR:
        st.warning(
            f"⚠️ Hay {total_filtrado} registros. Se muestran {MAX_FILAS_EDITOR} por vista para proteger el navegador."
        )
        pagina = st.selectbox(
            "Bloque de registros",
            list(range(1, max(1, -(-total_filtrado // MAX_FILAS_EDITOR)) + 1)),
            key="asis_pagina",
        )
        inicio = (int(pagina) - 1) * MAX_FILAS_EDITOR
        df_filtrado = df_filtrado.iloc[inicio: inicio + MAX_FILAS_EDITOR].copy()
        st.caption(f"Mostrando filas {inicio + 1}–{min(inicio + MAX_FILAS_EDITOR, total_filtrado)} de {total_filtrado}")

    st.markdown("<span class='wow-section-title'>✏️ Registrar presencialidad</span>", unsafe_allow_html=True)
    st.info(
        "Motivos de validación: A = Asistió · A-BM = No Asistió por Baja Médica · "
        "A-VAC = No Asistió por Vacaciones · NA-SA = No Asistió - Sin aviso · NA-CA = No Asistió - Con aviso"
    )

    columnas_editor = [c for c in COLUMNAS_FIJAS_EDITOR if c in df_filtrado.columns] + [col_dia, "ROW_SHEET"]
    for col in columnas_editor:
        if col not in df_filtrado.columns:
            df_filtrado[col] = ""
    df_editor = df_filtrado[columnas_editor].copy()
    df_editor[col_dia] = df_editor[col_dia].map(limpiar_marca)

    disabled_cols = [c for c in df_editor.columns if c != col_dia]
    column_config = {
        "ROW_SHEET": None,
        col_dia: st.column_config.SelectboxColumn(col_dia, options=MARCAS_VALIDAS, width="small"),
    }

    editado = st.data_editor(
        df_editor,
        use_container_width=True,
        height=min(620, 80 + len(df_editor) * 35),
        hide_index=True,
        disabled=disabled_cols,
        column_config=column_config,
        num_rows="fixed",
        key=f"editor_asistencia_{periodo_sel}_{col_dia}",
    )

    if st.button("💾 Guardar Presencialidad", key="btn_guardar_asistencia"):
        with st.spinner("Guardando en Google Drive…"):
            try:
                df_editado = pd.DataFrame(editado).fillna("")
                df_original_mes = df_original[df_original["PERIODO"].astype(str).eq(periodo_sel)].copy()
                updates, cambios_bm = preparar_updates_dia(df_editado, df_original_mes, headers, col_dia)
                if not updates:
                    st.info("ℹ️ No se detectaron cambios para guardar.")
                else:
                    for i in range(0, len(updates), 100):
                        hoja_asistencia.batch_update(updates[i:i + 100], value_input_option="USER_ENTERED")
                        time.sleep(0.1)

                    # Histórico A-BM: append, nunca reemplaza.
                    if cambios_bm:
                        hoja_sustentos = obtener_hoja_sustentos()
                        usuario = st.session_state.get("usuario", st.session_state.get("user", ""))
                        for row_bm in cambios_bm:
                            registrar_sustento_bm_historico(hoja_sustentos, usuario, periodo_sel, int(dia_sel), row_bm)

                    actualizar_cache_dia(df_editado, col_dia)
                    st.session_state["asis_guardado_msg"] = (
                        f"✅ Presencialidad guardada. Celdas actualizadas: {len(updates)}. "
                        f"Sustentos A-BM históricos agregados: {len(cambios_bm)}."
                    )
                    st.rerun()
            except Exception as e:
                st.error(f"❌ Error guardando asistencia: {e}")

    if msg := st.session_state.pop("asis_guardado_msg", None):
        st.success(msg)

    st.markdown("<span class='wow-section-title'>📊 Espejo mensual completo</span>", unsafe_allow_html=True)
    df_total_actual = st.session_state.get(KEY_DF_TOTAL, pd.DataFrame()).copy()
    df_mes_actual = df_total_actual[df_total_actual["PERIODO"].astype(str).eq(periodo_sel)].copy()
    df_espejo = filtrar_df(df_mes_actual, filtro_supervisor, filtro_coord, filtro_dep)
    mostrar_espejo_mes(df_espejo, dias_validos)

    if registro_mod is not None:
        st.divider()
        st.markdown("<span class='wow-section-title'>📋 Matriz de jerarquía</span>", unsafe_allow_html=True)
        try:
            registro_mod.mostrar_tabla(hoja_colaboradores, razon)
        except Exception as e:
            st.warning(f"No se pudo cargar la matriz de jerarquía: {e}")
