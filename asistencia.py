from datetime import datetime, timedelta

import pandas as pd
import streamlit as st

from st_aggrid import (
    AgGrid,
    GridOptionsBuilder,
    GridUpdateMode,
    JsCode,
    DataReturnMode
)


# =====================================================
# CONFIGURACION
# =====================================================
COLUMNAS_BASE = [
    "SUPERVISOR",
    "COORDINADOR",
    "DEPARTAMENTO",
    "PROVINCIA",
    "DNI",
    "NOMBRE",
    "ESTADO",
    "MES",
    "PERIODO"
]

COLUMNAS_DIAS = [
    f"DIA_{i}"
    for i in range(1, 32)
]

COLUMNAS_ASISTENCIA = COLUMNAS_BASE + COLUMNAS_DIAS

KEY_DF_CACHE = "asis_df_total_cache"
KEY_DF_ORIGINAL = "asis_df_original_visible"
KEY_LAST_MSG = "asis_last_msg"


# =====================================================
# UTILIDADES GENERALES
# =====================================================
def normalizar_columnas(df):
    df = df.copy()
    df.columns = (
        df.columns
        .astype(str)
        .str.strip()
        .str.upper()
    )
    return df


def obtener_periodo_actual():
    return datetime.now().strftime("%Y-%m")


def obtener_mes_actual():
    return str(datetime.now().month)


def columna_numero_a_letra(numero):
    letras = ""

    while numero:
        numero, residuo = divmod(numero - 1, 26)
        letras = chr(65 + residuo) + letras

    return letras


def limpiar_valor_marca(valor):
    valor = str(valor).strip().upper()

    if valor in ["A", "F", ""]:
        return valor

    return ""


def dias_semana_actual():
    hoy = datetime.now().date()
    inicio_semana = hoy - timedelta(days=hoy.weekday())

    dias = []

    for i in range(7):
        fecha = inicio_semana + timedelta(days=i)

        if fecha.month == hoy.month:
            dias.append(fecha.day)

    return dias


def rango_semana_texto():
    hoy = datetime.now().date()
    inicio_semana = hoy - timedelta(days=hoy.weekday())
    fin_semana = inicio_semana + timedelta(days=6)

    return f"{inicio_semana.strftime('%d/%m/%Y')} al {fin_semana.strftime('%d/%m/%Y')}"


# =====================================================
# GOOGLE SHEETS
# =====================================================
def leer_sheet_df(hoja_asistencia):
    valores = hoja_asistencia.get_all_values()

    if not valores:
        return pd.DataFrame(columns=COLUMNAS_ASISTENCIA)

    headers = [
        str(x).strip().upper()
        for x in valores[0]
    ]

    data = valores[1:]
    filas_ok = []

    for fila in data:
        fila = list(fila)

        if len(fila) < len(headers):
            fila += [""] * (len(headers) - len(fila))

        if len(fila) > len(headers):
            fila = fila[:len(headers)]

        filas_ok.append(fila)

    df = pd.DataFrame(filas_ok, columns=headers)
    df = df.fillna("").replace("None", "")
    df = normalizar_columnas(df)

    for col in COLUMNAS_ASISTENCIA:
        if col not in df.columns:
            df[col] = ""

    df = df[COLUMNAS_ASISTENCIA].copy()
    df["ROW_SHEET"] = df.index + 2

    return df


def asegurar_cabecera(hoja_asistencia):
    valores = hoja_asistencia.get_all_values()

    if not valores:
        hoja_asistencia.append_row(
            COLUMNAS_ASISTENCIA,
            value_input_option="USER_ENTERED"
        )
        return True

    headers = [
        str(x).strip().upper()
        for x in valores[0]
    ]

    faltantes = [
        col
        for col in COLUMNAS_ASISTENCIA
        if col not in headers
    ]

    if faltantes:
        st.error(
            "La hoja Asistencia tiene cabecera incompleta. "
            f"Faltan columnas: {', '.join(faltantes)}. "
            "Deja vacía la pestaña Asistencia para que el sistema cree la estructura correcta."
        )
        return False

    return True


def construir_filas_nuevas(df_colaboradores, df_asistencia):
    periodo = obtener_periodo_actual()
    mes = obtener_mes_actual()

    df_colaboradores = normalizar_columnas(df_colaboradores)

    if "DNI" not in df_colaboradores.columns or "ESTADO" not in df_colaboradores.columns:
        return []

    existentes_periodo = set()

    if not df_asistencia.empty:
        existentes_periodo = set(
            df_asistencia.loc[
                df_asistencia["PERIODO"].astype(str).eq(periodo),
                "DNI"
            ]
            .astype(str)
            .str.strip()
            .tolist()
        )

    df_activos = df_colaboradores[
        df_colaboradores["ESTADO"]
        .astype(str)
        .str.strip()
        .str.upper()
        .eq("ACTIVO")
    ].copy()

    filas = []

    for _, row in df_activos.iterrows():
        dni = str(row.get("DNI", "")).strip()

        if not dni or dni in existentes_periodo:
            continue

        fila = {
            "SUPERVISOR": str(row.get("SUPERVISOR A CARGO", "")).strip(),
            "COORDINADOR": str(row.get("COORDINADOR", "")).strip(),
            "DEPARTAMENTO": str(row.get("DEPARTAMENTO", "")).strip(),
            "PROVINCIA": str(row.get("PROVINCIA", "")).strip(),
            "DNI": dni,
            "NOMBRE": str(row.get("NOMBRES", "")).strip(),
            "ESTADO": "ACTIVO",
            "MES": mes,
            "PERIODO": periodo
        }

        for col in COLUMNAS_DIAS:
            fila[col] = ""

        filas.append([
            fila.get(col, "")
            for col in COLUMNAS_ASISTENCIA
        ])

    return filas


def sincronizar_mes(hoja_asistencia, hoja_colaboradores):
    if not asegurar_cabecera(hoja_asistencia):
        return 0

    df_asistencia = leer_sheet_df(hoja_asistencia)

    data_colaboradores = hoja_colaboradores.get_all_records()
    df_colaboradores = pd.DataFrame(data_colaboradores)

    filas_nuevas = construir_filas_nuevas(
        df_colaboradores,
        df_asistencia
    )

    if filas_nuevas:
        hoja_asistencia.append_rows(
            filas_nuevas,
            value_input_option="USER_ENTERED"
        )

    return len(filas_nuevas)


def cargar_asistencia_desde_drive(hoja_asistencia, forzar=False):
    if forzar or KEY_DF_CACHE not in st.session_state:
        st.session_state[KEY_DF_CACHE] = leer_sheet_df(hoja_asistencia)

    return st.session_state[KEY_DF_CACHE].copy()


def guardar_cambios_en_drive(hoja_asistencia, df_editado, df_original_visible, dias_editables):
    valores_sheet = hoja_asistencia.get_all_values()

    if not valores_sheet:
        return 0

    headers = [
        str(x).strip().upper()
        for x in valores_sheet[0]
    ]

    mapa_columnas = {
        col: idx + 1
        for idx, col in enumerate(headers)
    }

    original_por_row = df_original_visible.set_index("ROW_SHEET")

    updates = []

    for _, fila in df_editado.iterrows():
        row_sheet = int(fila["ROW_SHEET"])

        if row_sheet not in original_por_row.index:
            continue

        for dia in dias_editables:
            col = f"DIA_{dia}"

            if col not in mapa_columnas:
                continue

            nuevo = limpiar_valor_marca(fila.get(col, ""))
            original = limpiar_valor_marca(original_por_row.loc[row_sheet, col])

            if nuevo != original:
                letra = columna_numero_a_letra(mapa_columnas[col])

                updates.append({
                    "range": f"{letra}{row_sheet}",
                    "values": [[nuevo]]
                })

    if not updates:
        return 0

    hoja_asistencia.batch_update(
        updates,
        value_input_option="USER_ENTERED"
    )

    return len(updates)


# =====================================================
# UI ASISTENCIA
# =====================================================
def preparar_df_para_grid(df):
    df = df.copy().fillna("")

    for col in COLUMNAS_DIAS:
        if col in df.columns:
            df[col] = df[col].apply(limpiar_valor_marca)

    return df


def mostrar_asistencia(hoja_asistencia, hoja_colaboradores):
    st.subheader("🗓️ Control de Asistencia")

    if not asegurar_cabecera(hoja_asistencia):
        return

    periodo = obtener_periodo_actual()
    dias_editables = dias_semana_actual()

    st.info(
        f"Periodo actual: {periodo} | Semana editable: {rango_semana_texto()} | "
        "A = Asistencia | F = Falta"
    )

    col_a, col_b, col_c = st.columns([1, 1, 4])

    with col_a:
        if st.button("🔄 Sincronizar mes", key="asis_btn_sync"):
            try:
                nuevos = sincronizar_mes(
                    hoja_asistencia,
                    hoja_colaboradores
                )

                st.session_state[KEY_DF_CACHE] = leer_sheet_df(hoja_asistencia)
                st.session_state[KEY_LAST_MSG] = f"Sincronización correcta. Filas nuevas: {nuevos}"

            except Exception as e:
                st.error(f"Error sincronizando asistencia: {e}")
                return

    with col_b:
        if st.button("🔃 Recargar Drive", key="asis_btn_reload"):
            try:
                st.session_state[KEY_DF_CACHE] = leer_sheet_df(hoja_asistencia)
                st.session_state[KEY_LAST_MSG] = "Datos recargados desde Drive."

            except Exception as e:
                st.error(f"Error recargando asistencia: {e}")
                return

    if KEY_LAST_MSG in st.session_state:
        st.success(st.session_state[KEY_LAST_MSG])

    df_total = cargar_asistencia_desde_drive(
        hoja_asistencia,
        forzar=False
    )

    if df_total.empty:
        st.warning("No hay registros en Asistencia. Presiona 'Sincronizar mes'.")
        return

    df_periodo = df_total[
        df_total["PERIODO"].astype(str).eq(periodo)
    ].copy()

    if df_periodo.empty:
        st.warning("No hay registros para el periodo actual. Presiona 'Sincronizar mes'.")
        return

    # =================================================
    # FILTROS
    # =================================================
    supervisores = sorted([
        x for x in df_periodo["SUPERVISOR"].astype(str).unique().tolist()
        if str(x).strip()
    ])

    coordinadores = sorted([
        x for x in df_periodo["COORDINADOR"].astype(str).unique().tolist()
        if str(x).strip()
    ])

    departamentos = sorted([
        x for x in df_periodo["DEPARTAMENTO"].astype(str).unique().tolist()
        if str(x).strip()
    ])

    c1, c2, c3 = st.columns(3)

    with c1:
        filtro_supervisor = st.selectbox(
            "🔍 Supervisor",
            ["TODOS"] + supervisores,
            key="asis_filtro_supervisor"
        )

    with c2:
        filtro_coordinador = st.selectbox(
            "🔍 Coordinador",
            ["TODOS"] + coordinadores,
            key="asis_filtro_coordinador"
        )

    with c3:
        filtro_departamento = st.selectbox(
            "🔍 Departamento",
            ["TODOS"] + departamentos,
            key="asis_filtro_departamento"
        )

    df_visible = df_periodo.copy()

    if filtro_supervisor != "TODOS":
        df_visible = df_visible[
            df_visible["SUPERVISOR"].astype(str).eq(filtro_supervisor)
        ]

    if filtro_coordinador != "TODOS":
        df_visible = df_visible[
            df_visible["COORDINADOR"].astype(str).eq(filtro_coordinador)
        ]

    if filtro_departamento != "TODOS":
        df_visible = df_visible[
            df_visible["DEPARTAMENTO"].astype(str).eq(filtro_departamento)
        ]

    if df_visible.empty:
        st.warning("No hay registros con los filtros seleccionados.")
        return

    df_grid = df_visible[
        COLUMNAS_ASISTENCIA + ["ROW_SHEET"]
    ].copy()

    df_grid = preparar_df_para_grid(df_grid)

    st.session_state[KEY_DF_ORIGINAL] = df_grid.copy()

    # =================================================
    # GRID COMPLETO: 31 DIAS VISIBLES
    # =================================================
    gb = GridOptionsBuilder.from_dataframe(df_grid)

    gb.configure_default_column(
        editable=False,
        filter=True,
        sortable=True,
        resizable=True
    )

    gb.configure_column(
        "ROW_SHEET",
        hide=True
    )

    for col in [
        "SUPERVISOR",
        "COORDINADOR",
        "DEPARTAMENTO",
        "PROVINCIA",
        "DNI",
        "NOMBRE",
        "ESTADO"
    ]:
        gb.configure_column(
            col,
            editable=False,
            pinned="left" if col in ["DNI", "NOMBRE"] else None,
            width=155
        )

    gb.configure_column("MES", editable=False, width=85)
    gb.configure_column("PERIODO", editable=False, width=110)

    estilo_dias = JsCode("""
    function(params) {
        if (params.value == 'A') {
            return {
                'backgroundColor': '#C6EFCE',
                'color': '#006100',
                'fontWeight': 'bold',
                'textAlign': 'center'
            };
        }
        if (params.value == 'F') {
            return {
                'backgroundColor': '#FFC7CE',
                'color': '#9C0006',
                'fontWeight': 'bold',
                'textAlign': 'center'
            };
        }
        return {
            'backgroundColor': 'white',
            'color': 'black',
            'textAlign': 'center'
        };
    }
    """)

    for col in COLUMNAS_DIAS:
        dia = int(col.replace("DIA_", ""))

        gb.configure_column(
            col,
            editable=(dia in dias_editables),
            width=82,
            singleClickEdit=True,
            cellEditor="agSelectCellEditor",
            cellEditorParams={
                "values": ["", "A", "F"]
            },
            cellStyle=estilo_dias
        )

    grid_options = gb.build()
    grid_options["suppressRowClickSelection"] = True
    grid_options["stopEditingWhenCellsLoseFocus"] = True
    grid_options["ensureDomOrder"] = True

    grid_response = AgGrid(
        df_grid,
        gridOptions=grid_options,
        allow_unsafe_jscode=True,
        theme="streamlit",
        height=520,
        fit_columns_on_grid_load=False,
        update_mode=GridUpdateMode.MANUAL,
        data_return_mode=DataReturnMode.AS_INPUT,
        reload_data=False,
        key="asis_grid_principal"
    )

    st.caption("A = Asistencia 🟩 | F = Falta 🟥 | Se muestran los 31 días. Solo la semana actual es editable.")

    # =================================================
    # GUARDAR
    # =================================================
    if st.button("💾 Guardar Asistencia", key="asis_btn_guardar"):
        try:
            df_editado = pd.DataFrame(grid_response["data"]).fillna("")
            df_editado = preparar_df_para_grid(df_editado)

            cambios = guardar_cambios_en_drive(
                hoja_asistencia,
                df_editado,
                st.session_state[KEY_DF_ORIGINAL],
                dias_editables
            )

            if cambios == 0:
                st.info("No se detectaron cambios para guardar.")
                return

            # Actualizar cache local sin recargar ni cerrar sesion
            df_cache = st.session_state[KEY_DF_CACHE].copy()

            for _, fila in df_editado.iterrows():
                row_sheet = int(fila["ROW_SHEET"])
                idx = df_cache.index[df_cache["ROW_SHEET"].eq(row_sheet)]

                if len(idx) == 0:
                    continue

                for dia in dias_editables:
                    col = f"DIA_{dia}"
                    df_cache.loc[idx, col] = limpiar_valor_marca(fila.get(col, ""))

            st.session_state[KEY_DF_CACHE] = df_cache
            st.session_state[KEY_LAST_MSG] = f"Asistencia guardada correctamente. Cambios aplicados: {cambios}"

            st.success(st.session_state[KEY_LAST_MSG])

        except Exception as e:
            st.error(f"Error guardando asistencia: {e}")
