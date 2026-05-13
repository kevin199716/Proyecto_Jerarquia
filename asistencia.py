# ============================================
# asistencia.py
# VERSION FINAL COMPLETA
# ============================================

import streamlit as st
import pandas as pd

from datetime import datetime, timedelta

from st_aggrid import (
    AgGrid,
    GridOptionsBuilder,
    GridUpdateMode,
    JsCode
)

# ============================================
# CACHE
# ============================================

@st.cache_data(ttl=60)
def cargar_colaboradores_cache(data):
    return pd.DataFrame(data)

# ============================================
# GENERAR ASISTENCIA
# ============================================

def generar_asistencia_mes(
    hoja_asistencia,
    df_colab
):

    valores = hoja_asistencia.get_all_values()

    # SI ESTA VACIO
    if len(valores) <= 1:

        hoy = datetime.now()

        periodo = hoy.strftime("%Y-%m")

        registros = []

        for _, row in df_colab.iterrows():

            fila = {
                "PERIODO": periodo,
                "DNI": str(row.get("DNI", "")),
                "NOMBRE": str(row.get("NOMBRES", "")),
                "SUPERVISOR": str(row.get("SUPERVISOR A CARGO", "")),
                "COORDINADOR": str(row.get("COORDINADOR", "")),
                "DEPARTAMENTO": str(row.get("DEPARTAMENTO", "")),
                "PROVINCIA": str(row.get("PROVINCIA", "")),
                "ESTADO": str(row.get("ESTADO", "")),
                "FECHA_CREACION_USUARIO": str(
                    row.get("FECHA DE CREACION USUARIO", "")
                ),
                "FECHA_DE_CESE": str(
                    row.get("FECHA DE CESE", "")
                ),
            }

            for dia in range(1, 32):

                fila[f"DIA_{dia}"] = ""

            registros.append(fila)

        df_nuevo = pd.DataFrame(registros)

        hoja_asistencia.clear()

        hoja_asistencia.update(
            [df_nuevo.columns.values.tolist()] +
            df_nuevo.values.tolist()
        )

# ============================================
# SEMANA ACTUAL
# ============================================

def obtener_semana_actual():

    hoy = datetime.now()

    inicio_semana = hoy - timedelta(days=hoy.weekday())

    dias_editables = []

    for i in range(7):

        fecha = inicio_semana + timedelta(days=i)

        if fecha <= hoy:

            dias_editables.append(fecha.day)

    return dias_editables

# ============================================
# COLORES
# ============================================

cellstyle_jscode = JsCode("""
function(params) {

    if(params.value == 'A') {
        return {
            'backgroundColor': '#c8f7c5',
            'color': 'green',
            'fontWeight': 'bold',
            'textAlign': 'center'
        }
    }

    if(params.value == 'F') {
        return {
            'backgroundColor': '#ffb3b3',
            'color': 'red',
            'fontWeight': 'bold',
            'textAlign': 'center'
        }
    }

    if(params.data.ESTADO == 'INACTIVO') {
        return {
            'backgroundColor': '#eeeeee',
            'color': '#888888'
        }
    }

    return {
        'textAlign': 'center'
    }
}
""")

# ============================================
# MAIN
# ============================================

def mostrar_asistencia(
    hoja_asistencia,
    hoja_colaboradores
):

    st.markdown("## 🗓️ Control de Asistencia")

    # ====================================
    # CARGAR COLABORADORES
    # ====================================

    data_colab = hoja_colaboradores.get_all_records()

    df_colab = cargar_colaboradores_cache(
        data_colab
    )

    df_colab.columns = (
        df_colab.columns
        .str.strip()
        .str.upper()
    )

    # ====================================
    # GENERAR BASE
    # ====================================

    generar_asistencia_mes(
        hoja_asistencia,
        df_colab
    )

    # ====================================
    # LEER ASISTENCIA
    # ====================================

    valores = hoja_asistencia.get_all_values()

    headers = valores[0]

    data = valores[1:]

    df = pd.DataFrame(
        data,
        columns=headers
    )

    # ====================================
    # LIMPIAR COLUMNAS
    # ====================================

    for col in [
        "SUPERVISOR",
        "COORDINADOR",
        "ESTADO",
        "NOMBRE",
        "DEPARTAMENTO",
        "PROVINCIA",
        "DNI"
    ]:

        if col in df.columns:

            df[col] = (
                df[col]
                .astype(str)
                .fillna("")
                .replace("nan", "")
            )

    # ====================================
    # KPIS
    # ====================================

    total = len(df)

    activos = len(
        df[df["ESTADO"] == "ACTIVO"]
    )

    inactivos = len(
        df[df["ESTADO"] == "INACTIVO"]
    )

    c1, c2, c3 = st.columns(3)

    with c1:
        st.metric("👥 HC TOTAL", total)

    with c2:
        st.metric("✅ ACTIVOS", activos)

    with c3:
        st.metric("❌ INACTIVOS", inactivos)

    st.divider()

    # ====================================
    # FILTROS
    # ====================================

    supervisores = sorted(
        [
            str(x)
            for x in df["SUPERVISOR"]
            .dropna()
            .unique()
            .tolist()
            if str(x).strip() != ""
        ]
    )

    coordinadores = sorted(
        [
            str(x)
            for x in df["COORDINADOR"]
            .dropna()
            .unique()
            .tolist()
            if str(x).strip() != ""
        ]
    )

    f1, f2 = st.columns(2)

    with f1:

        filtro_supervisor = st.selectbox(
            "🔍 Supervisor",
            ["TODOS"] + supervisores
        )

    with f2:

        filtro_coord = st.selectbox(
            "🔍 Coordinador",
            ["TODOS"] + coordinadores
        )

    # ====================================
    # FILTRAR
    # ====================================

    if filtro_supervisor != "TODOS":

        df = df[
            df["SUPERVISOR"] ==
            filtro_supervisor
        ]

    if filtro_coord != "TODOS":

        df = df[
            df["COORDINADOR"] ==
            filtro_coord
        ]

    # ====================================
    # SEMANA EDITABLE
    # ====================================

    dias_editables = obtener_semana_actual()

    st.info(
        "Solo editable semana actual | "
        "A = Asistencia | "
        "F = Falta"
    )

    # ====================================
    # COLUMNAS
    # ====================================

    columnas_base = [
        "SUPERVISOR",
        "COORDINADOR",
        "DEPARTAMENTO",
        "PROVINCIA",
        "DNI",
        "NOMBRE",
        "ESTADO"
    ]

    columnas_dias = []

    for dia in range(1, 32):

        columnas_dias.append(
            f"DIA_{dia}"
        )

    columnas_finales = (
        columnas_base +
        columnas_dias
    )

    columnas_existentes = [
        c for c in columnas_finales
        if c in df.columns
    ]

    df = df[columnas_existentes]

    # ====================================
    # GRID
    # ====================================

    gb = GridOptionsBuilder.from_dataframe(df)

    gb.configure_default_column(
        editable=False,
        sortable=False,
        filter=False,
        resizable=True
    )

    # ====================================
    # COLUMNAS FIJAS
    # ====================================

    columnas_fijas = [
        "SUPERVISOR",
        "COORDINADOR",
        "DEPARTAMENTO",
        "PROVINCIA",
        "DNI",
        "NOMBRE",
        "ESTADO"
    ]

    for col in columnas_fijas:

        gb.configure_column(
            col,
            pinned="left",
            editable=False,
            cellStyle=cellstyle_jscode,
            width=180
        )

    # ====================================
    # DIAS
    # ====================================

    for dia in range(1, 32):

        col = f"DIA_{dia}"

        editable = (
            dia in dias_editables
        )

        gb.configure_column(
            col,
            editable=editable,
            width=90,
            cellEditor="agSelectCellEditor",
            cellEditorParams={
                "values": ["", "A", "F"]
            },
            cellStyle=cellstyle_jscode
        )

    # ====================================
    # GRID OPTIONS
    # ====================================

    gb.configure_grid_options(
        suppressRowClickSelection=True,
        rowHeight=38,
        animateRows=False
    )

    gridOptions = gb.build()

    # ====================================
    # GRID
    # ====================================

    grid_response = AgGrid(
        df,
        gridOptions=gridOptions,
        update_mode=GridUpdateMode.MANUAL,
        allow_unsafe_jscode=True,
        fit_columns_on_grid_load=False,
        height=700,
        width="100%",
        reload_data=False,
        theme="streamlit"
    )

    # ====================================
    # GUARDAR
    # ====================================

    if st.button(
        "💾 Guardar Asistencia"
    ):

        nuevo_df = pd.DataFrame(
            grid_response["data"]
        )

        hoja_asistencia.clear()

        hoja_asistencia.update(
            [nuevo_df.columns.values.tolist()] +
            nuevo_df.values.tolist()
        )

        st.success(
            "✅ Asistencia guardada correctamente"
        )