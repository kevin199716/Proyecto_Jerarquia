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

@st.cache_data(ttl=60)
def cargar_data_asistencia():
    return st.session_state["hoja_asistencia"].get_all_records()

# =========================================================
# GENERAR BASE
# =========================================================

def generar_base(df_colab, data_asistencia):

    df_asistencia = pd.DataFrame(data_asistencia)

    if df_asistencia.empty:
        columnas = [
            "SUPERVISOR",
            "COORDINADOR",
            "DEPARTAMENTO",
            "PROVINCIA",
            "DNI",
            "NOMBRE",
            "ESTADO"
        ]

        for i in range(1, 32):
            columnas.append(f"DIA_{i}")

        columnas.extend(["MES", "PERIODO"])

        df_asistencia = pd.DataFrame(columns=columnas)

    # ============================================
    # ASEGURAR COLUMNAS
    # ============================================

    columnas_base = [
        "SUPERVISOR",
        "COORDINADOR",
        "DEPARTAMENTO",
        "PROVINCIA",
        "DNI",
        "NOMBRE",
        "ESTADO"
    ]

    for c in columnas_base:
        if c not in df_asistencia.columns:
            df_asistencia[c] = ""

    for i in range(1, 32):
        col = f"DIA_{i}"
        if col not in df_asistencia.columns:
            df_asistencia[col] = ""

    if "MES" not in df_asistencia.columns:
        df_asistencia["MES"] = datetime.now().strftime("%m")

    if "PERIODO" not in df_asistencia.columns:
        df_asistencia["PERIODO"] = datetime.now().strftime("%Y-%m")

    # ============================================
    # NO REDUCIR FILAS
    # ============================================

    if len(df_asistencia) < len(df_colab):

        faltantes = len(df_colab) - len(df_asistencia)

        nuevas = pd.DataFrame(index=range(faltantes))

        for c in df_asistencia.columns:
            nuevas[c] = ""

        nuevas["ESTADO"] = "ACTIVO"

        df_asistencia = pd.concat(
            [df_asistencia, nuevas],
            ignore_index=True
        )

    # ============================================
    # COMPLETAR DATA
    # ============================================

    columnas_map = {
        "SUPERVISOR": "SUPERVISOR A CARGO",
        "COORDINADOR": "COORDINADOR",
        "DEPARTAMENTO": "DEPARTAMENTO",
        "PROVINCIA": "PROVINCIA",
        "DNI": "DNI",
        "NOMBRE": "NOMBRES",
        "ESTADO": "ESTADO"
    }

    for col_destino, col_origen in columnas_map.items():

        if col_origen in df_colab.columns:

            df_asistencia[col_destino] = (
                df_colab[col_origen]
                .fillna("")
                .astype(str)
                .reset_index(drop=True)
            )

    # ============================================
    # ORDEN FINAL
    # ============================================

    columnas_finales = [
        "SUPERVISOR",
        "COORDINADOR",
        "DEPARTAMENTO",
        "PROVINCIA",
        "DNI",
        "NOMBRE",
        "ESTADO"
    ]

    for i in range(1, 32):
        columnas_finales.append(f"DIA_{i}")

    columnas_finales.extend(["MES", "PERIODO"])

    df_asistencia = df_asistencia[columnas_finales]

    return df_asistencia.fillna("")


# =========================================================
# MOSTRAR ASISTENCIA
# =========================================================

def mostrar_asistencia(hoja_asistencia, hoja_colaboradores):

    st.markdown("## 🗓️ Control de Asistencia")

    # =====================================================
    # DATA
    # =====================================================

    df_colab = pd.DataFrame(
        hoja_colaboradores.get_all_records()
    ).fillna("")

    data_asistencia = cargar_data_asistencia()

    df = generar_base(
        df_colab,
        data_asistencia
    )

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

        supervisor = st.selectbox(
            "🔍 Supervisor",
            supervisores
        )

    with col2:

        coordinadores = ["TODOS"] + sorted(
            df["COORDINADOR"]
            .astype(str)
            .unique()
            .tolist()
        )

        coordinador = st.selectbox(
            "🔍 Coordinador",
            coordinadores
        )

    # =====================================================
    # FILTRAR
    # =====================================================

    if supervisor != "TODOS":
        df = df[df["SUPERVISOR"] == supervisor]

    if coordinador != "TODOS":
        df = df[df["COORDINADOR"] == coordinador]

    df = df.reset_index(drop=True)

    # =====================================================
    # GRID
    # =====================================================

    gb = GridOptionsBuilder.from_dataframe(df)

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

    # ==========================================
    # SOLO EDITAR SEMANA ACTUAL
    # ==========================================

    hoy = datetime.now().day

    dias_editables = []

    for i in range(max(1, hoy - 6), hoy + 1):
        dias_editables.append(f"DIA_{i}")

    # ==========================================
    # COLUMNAS
    # ==========================================

    for col in df.columns:

        editable = col in dias_editables

        if col in columnas_fijas:

            gb.configure_column(
                col,
                editable=False,
                width=150
            )

        elif col.startswith("DIA_"):

            gb.configure_column(
                col,
                editable=editable,
                singleClickEdit=True,
                cellEditor="agSelectCellEditor",
                cellEditorParams={
                    "values": ["", "A", "F"]
                },
                width=90
            )

    # ==========================================
    # COLOR
    # ==========================================

    estilo = JsCode("""
    function(params) {

        if(params.value == 'A'){
            return {
                'backgroundColor': '#b7e4c7',
                'color': '#1b4332',
                'fontWeight': 'bold',
                'textAlign': 'center'
            }
        }

        if(params.value == 'F'){
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

    # ==========================================
    # GRID OPTIONS
    # ==========================================

    gb.configure_grid_options(
        animateRows=False,
        suppressRowTransform=True,
        suppressAnimationFrame=True,
        suppressMovableColumns=True,
        rowBuffer=5,
        domLayout="normal",
        alwaysShowHorizontalScroll=True,
        alwaysShowVerticalScroll=True
    )

    grid_options = gb.build()

    # =====================================================
    # AGGRID
    # =====================================================

    response = AgGrid(
        df,
        gridOptions=grid_options,
        allow_unsafe_jscode=True,
        update_mode=GridUpdateMode.VALUE_CHANGED,
        data_return_mode=DataReturnMode.FILTERED_AND_SORTED,
        fit_columns_on_grid_load=False,
        reload_data=False,
        enable_enterprise_modules=False,
        height=560,
        theme="streamlit",
        key="grid_asistencia_final"
    )

    # =====================================================
    # DATA COMPLETA
    # =====================================================

    df_editado = pd.DataFrame(response["data"])

    for c in df.columns:

        if c not in df_editado.columns:
            df_editado[c] = df[c]

    df_editado = df_editado[df.columns]

    df_editado = df_editado.fillna("").astype(str)

    # =====================================================
    # LEYENDA
    # =====================================================

    st.markdown(
        "A = Asistencia 🟩 | F = Falta 🟥"
    )

    # =====================================================
    # GUARDAR
    # =====================================================

    if st.button(
        "💾 Guardar Asistencia",
        use_container_width=False
    ):

        try:

            hoja_asistencia.clear()

            hoja_asistencia.update(
                [
                    df_editado.columns.values.tolist()
                ] +
                df_editado.values.tolist()
            )

            cargar_data_asistencia.clear()

            st.success(
                "✅ Asistencia guardada correctamente"
            )

        except Exception as e:

            st.error(
                f"❌ Error al guardar: {str(e)}"
            )