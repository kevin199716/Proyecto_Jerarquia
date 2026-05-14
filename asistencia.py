# asistencia.py

import streamlit as st
import pandas as pd
from datetime import datetime

from st_aggrid import (
    AgGrid,
    GridOptionsBuilder,
    GridUpdateMode,
    DataReturnMode,
    JsCode
)

# =========================================================
# CACHE
# =========================================================

@st.cache_data(ttl=30)
def cargar_data_asistencia():

    # 👇 IMPORTANTE
    hoja_asistencia = st.session_state.get("hoja_asistencia")

    if hoja_asistencia is None:
        return []

    try:
        return hoja_asistencia.get_all_records()
    except:
        return []


# =========================================================
# GENERAR BASE
# =========================================================

def generar_base(df_colab):

    hoy = datetime.now()

    periodo_actual = hoy.strftime("%Y-%m")
    mes_actual = hoy.strftime("%m")

    data = cargar_data_asistencia()

    df_bd = pd.DataFrame(data)

    # =====================================================
    # COLUMNAS
    # =====================================================

    columnas_base = [
        "SUPERVISOR",
        "COORDINADOR",
        "DEPARTAMENTO",
        "PROVINCIA",
        "DNI",
        "NOMBRE",
        "ESTADO"
    ]

    columnas_dias = [f"DIA_{i}" for i in range(1, 32)]

    columnas_finales = (
        columnas_base
        + columnas_dias
        + ["MES", "PERIODO"]
    )

    # =====================================================
    # SI NO EXISTE DATA
    # =====================================================

    if df_bd.empty:

        filas = []

        for _, row in df_colab.iterrows():

            fila = {
                "SUPERVISOR": str(row.get("SUPERVISOR A CARGO", "")),
                "COORDINADOR": str(row.get("COORDINADOR", "")),
                "DEPARTAMENTO": str(row.get("DEPARTAMENTO", "")),
                "PROVINCIA": str(row.get("PROVINCIA", "")),
                "DNI": str(row.get("DNI", "")),
                "NOMBRE": str(row.get("NOMBRES", "")),
                "ESTADO": str(row.get("ESTADO", "")),
                "MES": mes_actual,
                "PERIODO": periodo_actual
            }

            for d in columnas_dias:
                fila[d] = ""

            filas.append(fila)

        return pd.DataFrame(filas)

    # =====================================================
    # ASEGURAR COLUMNAS
    # =====================================================

    for c in columnas_finales:

        if c not in df_bd.columns:
            df_bd[c] = ""

    # =====================================================
    # FILTRAR PERIODO ACTUAL
    # =====================================================

    if "PERIODO" in df_bd.columns:

        df_mes = df_bd[
            df_bd["PERIODO"].astype(str) == periodo_actual
        ].copy()

    else:

        df_mes = df_bd.copy()

    # =====================================================
    # SI EL MES NO EXISTE
    # =====================================================

    if df_mes.empty:

        filas = []

        for _, row in df_colab.iterrows():

            fila = {
                "SUPERVISOR": str(row.get("SUPERVISOR A CARGO", "")),
                "COORDINADOR": str(row.get("COORDINADOR", "")),
                "DEPARTAMENTO": str(row.get("DEPARTAMENTO", "")),
                "PROVINCIA": str(row.get("PROVINCIA", "")),
                "DNI": str(row.get("DNI", "")),
                "NOMBRE": str(row.get("NOMBRES", "")),
                "ESTADO": str(row.get("ESTADO", "")),
                "MES": mes_actual,
                "PERIODO": periodo_actual
            }

            for d in columnas_dias:
                fila[d] = ""

            filas.append(fila)

        return pd.DataFrame(filas)

    # =====================================================
    # COMPLETAR REGISTROS FALTANTES
    # =====================================================

    dni_existentes = (
        df_mes["DNI"]
        .astype(str)
        .tolist()
    )

    nuevos = []

    for _, row in df_colab.iterrows():

        dni = str(row.get("DNI", ""))

        if dni not in dni_existentes:

            fila = {
                "SUPERVISOR": str(row.get("SUPERVISOR A CARGO", "")),
                "COORDINADOR": str(row.get("COORDINADOR", "")),
                "DEPARTAMENTO": str(row.get("DEPARTAMENTO", "")),
                "PROVINCIA": str(row.get("PROVINCIA", "")),
                "DNI": dni,
                "NOMBRE": str(row.get("NOMBRES", "")),
                "ESTADO": str(row.get("ESTADO", "")),
                "MES": mes_actual,
                "PERIODO": periodo_actual
            }

            for d in columnas_dias:
                fila[d] = ""

            nuevos.append(fila)

    if nuevos:

        df_nuevos = pd.DataFrame(nuevos)

        df_mes = pd.concat(
            [df_mes, df_nuevos],
            ignore_index=True
        )

    # =====================================================
    # LIMPIAR
    # =====================================================

    df_mes = df_mes[columnas_finales]

    df_mes = df_mes.fillna("").astype(str)

    return df_mes


# =========================================================
# MOSTRAR
# =========================================================

def mostrar_asistencia():

    hoja_asistencia = st.session_state.get("hoja_asistencia")
    hoja_colab = st.session_state.get("hoja_colaboradores")

    if hoja_asistencia is None:
        st.error("❌ No existe hoja_asistencia")
        return

    if hoja_colab is None:
        st.error("❌ No existe hoja_colaboradores")
        return

    st.markdown("# 🗓️ Control de Asistencia")

    # =====================================================
    # DATA
    # =====================================================

    data_colab = hoja_colab.get_all_records()

    df_colab = pd.DataFrame(data_colab)

    df = generar_base(df_colab)

    # =====================================================
    # FILTROS
    # =====================================================

    col1, col2 = st.columns(2)

    with col1:

        supervisores = ["TODOS"] + sorted(
            df["SUPERVISOR"]
            .astype(str)
            .unique()
            .tolist()
        )

        filtro_supervisor = st.selectbox(
            "🔎 Supervisor",
            supervisores
        )

    with col2:

        coordinadores = ["TODOS"] + sorted(
            df["COORDINADOR"]
            .astype(str)
            .unique()
            .tolist()
        )

        filtro_coord = st.selectbox(
            "🔎 Coordinador",
            coordinadores
        )

    # =====================================================
    # FILTRAR
    # =====================================================

    if filtro_supervisor != "TODOS":

        df = df[
            df["SUPERVISOR"] == filtro_supervisor
        ]

    if filtro_coord != "TODOS":

        df = df[
            df["COORDINADOR"] == filtro_coord
        ]

    df = df.reset_index(drop=True)

    # =====================================================
    # GRID
    # =====================================================

    gb = GridOptionsBuilder.from_dataframe(df)

    hoy = datetime.now().day

    dias_editables = [
        f"DIA_{i}"
        for i in range(max(1, hoy - 6), hoy + 1)
    ]

    columnas_fijas = [
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

    for col in df.columns:

        if col in columnas_fijas:

            gb.configure_column(
                col,
                editable=False,
                width=140
            )

        elif col.startswith("DIA_"):

            gb.configure_column(
                col,
                editable=col in dias_editables,
                cellEditor="agSelectCellEditor",
                cellEditorParams={
                    "values": ["", "A", "F"]
                },
                singleClickEdit=True,
                width=85
            )

    # =====================================================
    # COLOR
    # =====================================================

    estilo = JsCode("""
    function(params) {

        if(params.value == 'A') {
            return {
                'backgroundColor': '#b7e4c7',
                'color': '#1b4332',
                'fontWeight': 'bold',
                'textAlign': 'center'
            }
        }

        if(params.value == 'F') {
            return {
                'backgroundColor': '#f4b6c2',
                'color': '#9d0208',
                'fontWeight': 'bold',
                'textAlign': 'center'
            }
        }
    }
    """)

    for i in range(1, 32):

        gb.configure_column(
            f"DIA_{i}",
            cellStyle=estilo
        )

    # =====================================================
    # GRID OPTIONS
    # =====================================================

    gb.configure_grid_options(
        alwaysShowHorizontalScroll=True,
        alwaysShowVerticalScroll=True,
        suppressRowTransform=True,
        suppressAnimationFrame=True,
        rowBuffer=10,
        domLayout="normal"
    )

    grid_options = gb.build()

    # =====================================================
    # GRID FINAL
    # =====================================================

    response = AgGrid(
        df,
        gridOptions=grid_options,
        allow_unsafe_jscode=True,
        update_mode=GridUpdateMode.VALUE_CHANGED,
        data_return_mode=DataReturnMode.FILTERED_AND_SORTED,
        fit_columns_on_grid_load=False,
        reload_data=False,
        theme="streamlit",
        height=600,
        key="grid_asistencia"
    )

    df_editado = pd.DataFrame(
        response["data"]
    ).fillna("").astype(str)

    # =====================================================
    # LEYENDA
    # =====================================================

    st.markdown(
        "A = Asistencia 🟩 | F = Falta 🟥"
    )

    # =====================================================
    # GUARDAR
    # =====================================================

    if st.button("💾 Guardar Asistencia"):

        try:

            data_total = hoja_asistencia.get_all_records()

            df_total = pd.DataFrame(data_total)

            periodo_actual = datetime.now().strftime("%Y-%m")

            if not df_total.empty:

                if "PERIODO" not in df_total.columns:
                    df_total["PERIODO"] = periodo_actual

                df_total = df_total[
                    df_total["PERIODO"] != periodo_actual
                ]

            df_final = pd.concat(
                [df_total, df_editado],
                ignore_index=True
            )

            df_final = df_final.fillna("").astype(str)

            hoja_asistencia.clear()

            hoja_asistencia.update(
                [
                    df_final.columns.values.tolist()
                ] +
                df_final.values.tolist()
            )

            cargar_data_asistencia.clear()

            st.success(
                "✅ Asistencia guardada correctamente"
            )

        except Exception as e:

            st.error(
                f"❌ Error al guardar: {str(e)}"
            )