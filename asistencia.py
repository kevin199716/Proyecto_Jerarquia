# =========================================================
# asistencia.py  (SCRIPT COMPLETO FINAL)
# =========================================================

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
# CONFIG
# =========================================================

COLUMNAS_FIJAS = [
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

COLUMNAS_DIAS = [f"DIA_{i}" for i in range(1, 32)]


# =========================================================
# GENERAR BASE
# =========================================================

def generar_base(
    hoja_asistencia,
    hoja_colaboradores
):

    hoy = datetime.now()

    periodo_actual = hoy.strftime("%Y-%m")
    mes_actual = hoy.strftime("%m")

    # =====================================================
    # LEER ASISTENCIA DRIVE
    # =====================================================

    data_drive = hoja_asistencia.get_all_records()

    # =====================================================
    # SI EXISTE DATA
    # =====================================================

    if len(data_drive) > 0:

        df_drive = pd.DataFrame(data_drive)

        df_drive = df_drive.fillna("")

        # ============================================
        # ASEGURAR COLUMNAS
        # ============================================

        if "MES" not in df_drive.columns:
            df_drive["MES"] = mes_actual

        if "PERIODO" not in df_drive.columns:
            df_drive["PERIODO"] = periodo_actual

        # ============================================
        # FILTRAR PERIODO ACTUAL
        # ============================================

        df_periodo = df_drive[
            df_drive["PERIODO"].astype(str)
            == periodo_actual
        ].copy()

        # ============================================
        # SI YA EXISTE DATA DEL MES
        # ============================================

        if not df_periodo.empty:

            # ============================================
            # LEER COLABORADORES
            # ============================================

            data_colab = hoja_colaboradores.get_all_records()

            df_colab = pd.DataFrame(data_colab)

            df_colab = df_colab.fillna("")

            # ============================================
            # AGREGAR NUEVOS REGISTROS
            # ============================================

            dni_existentes = (
                df_periodo["DNI"]
                .astype(str)
                .tolist()
            )

            nuevos = []

            for _, row in df_colab.iterrows():

                dni = str(
                    row.get("DNI", "")
                )

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

                    for d in COLUMNAS_DIAS:
                        fila[d] = ""

                    nuevos.append(fila)

            if len(nuevos) > 0:

                df_nuevos = pd.DataFrame(nuevos)

                df_periodo = pd.concat(
                    [df_periodo, df_nuevos],
                    ignore_index=True
                )

            return df_periodo.fillna("")

    # =====================================================
    # SI NO EXISTE DATA
    # =====================================================

    data_colab = hoja_colaboradores.get_all_records()

    df_colab = pd.DataFrame(data_colab)

    df_colab = df_colab.fillna("")

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

        for d in COLUMNAS_DIAS:
            fila[d] = ""

        filas.append(fila)

    return pd.DataFrame(filas)


# =========================================================
# MOSTRAR ASISTENCIA
# =========================================================

def mostrar_asistencia(
    hoja_asistencia,
    hoja_colaboradores
):

    st.subheader("🗓️ Control de Asistencia")

    # =====================================================
    # GENERAR BASE
    # =====================================================

    df = generar_base(
        hoja_asistencia,
        hoja_colaboradores
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

        filtro_supervisor = st.selectbox(
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

        filtro_coord = st.selectbox(
            "🔍 Coordinador",
            coordinadores
        )

    # =====================================================
    # FILTRO
    # =====================================================

    if filtro_supervisor != "TODOS":

        df = df[
            df["SUPERVISOR"]
            == filtro_supervisor
        ]

    if filtro_coord != "TODOS":

        df = df[
            df["COORDINADOR"]
            == filtro_coord
        ]

    # =====================================================
    # SOLO COLUMNAS VISIBLES
    # =====================================================

    columnas_visibles = [
        "PROVINCIA",
        "DNI",
        "NOMBRE",
        "ESTADO"
    ] + COLUMNAS_DIAS

    df = df[columnas_visibles]

    # =====================================================
    # AGGRID
    # =====================================================

    gb = GridOptionsBuilder.from_dataframe(df)

    # =====================================================
    # COLUMNAS FIJAS
    # =====================================================

    for col in [
        "PROVINCIA",
        "DNI",
        "NOMBRE",
        "ESTADO"
    ]:

        gb.configure_column(
            col,
            editable=False,
            width=170
        )

    # =====================================================
    # SEMANA ACTUAL
    # =====================================================

    hoy = datetime.now().day

    semana_inicio = ((hoy - 1) // 7) * 7 + 1
    semana_fin = min(semana_inicio + 6, 31)

    # =====================================================
    # DIAS
    # =====================================================

    for i in range(1, 32):

        editable = semana_inicio <= i <= semana_fin

        gb.configure_column(
            f"DIA_{i}",

            editable=editable,

            cellEditor="agSelectCellEditor",

            cellEditorParams={
                "values": ["", "A", "F"]
            },

            width=90
        )

    # =====================================================
    # ESTILOS
    # =====================================================

    cellstyle_jscode = JsCode("""

    function(params) {

        if (params.value == 'A') {

            return {
                'backgroundColor': '#b7e4c7',
                'color': '#1b4332',
                'fontWeight': 'bold',
                'textAlign': 'center'
            }
        }

        if (params.value == 'F') {

            return {
                'backgroundColor': '#f4acb7',
                'color': '#9d0208',
                'fontWeight': 'bold',
                'textAlign': 'center'
            }
        }
    }

    """)

    for d in COLUMNAS_DIAS:

        gb.configure_column(
            d,
            cellStyle=cellstyle_jscode
        )

    # =====================================================
    # PERFORMANCE
    # =====================================================

    gb.configure_grid_options(

        suppressRowTransform=True,

        suppressAnimationFrame=True,

        pagination=False,

        rowBuffer=0,

        domLayout="normal"
    )

    grid_options = gb.build()

    # =====================================================
    # TABLA
    # =====================================================

    response = AgGrid(

        df,

        gridOptions=grid_options,

        height=620,

        theme="streamlit",

        allow_unsafe_jscode=True,

        fit_columns_on_grid_load=False,

        update_mode=GridUpdateMode.VALUE_CHANGED,

        data_return_mode=DataReturnMode.AS_INPUT,

        reload_data=False,

        key="ASISTENCIA_GRID",

        custom_css={

            ".ag-root-wrapper": {
                "font-size": "14px"
            },

            ".ag-cell": {
                "font-size": "14px",
                "padding-left": "8px",
                "padding-right": "8px"
            },

            ".ag-header-cell-label": {
                "font-size": "13px",
                "font-weight": "bold"
            }
        }
    )

    st.caption(
        "Solo editable semana actual | A = Asistencia | F = Falta"
    )

    # =====================================================
    # GUARDAR
    # =====================================================

    if st.button("💾 Guardar Asistencia"):

        df_editado = pd.DataFrame(
            response["data"]
        )

        # ============================================
        # RECUPERAR COLUMNAS OCULTAS
        # ============================================

        df_full = generar_base(
            hoja_asistencia,
            hoja_colaboradores
        )

        for col in df_full.columns:

            if col not in df_editado.columns:

                df_editado[col] = df_full[col]

        # ============================================
        # ORDEN
        # ============================================

        columnas_finales = (
            COLUMNAS_FIJAS +
            COLUMNAS_DIAS
        )

        df_editado = df_editado[columnas_finales]

        # ============================================
        # LIMPIAR DRIVE
        # ============================================

        hoja_asistencia.clear()

        # ============================================
        # GUARDAR
        # ============================================

        hoja_asistencia.update(

            [df_editado.columns.values.tolist()] +
            df_editado.values.tolist()
        )

        st.success(
            "✅ Asistencia guardada correctamente"
        )