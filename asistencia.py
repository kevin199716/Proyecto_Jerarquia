# =========================================================
# asistencia.py  (SCRIPT COMPLETO ESTABLE)
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
    # LEER DRIVE
    # =====================================================

    data_drive = hoja_asistencia.get_all_records()

    # =====================================================
    # SI EXISTE DATA
    # =====================================================

    if len(data_drive) > 0:

        df_drive = pd.DataFrame(data_drive)

        df_drive = df_drive.fillna("")

        # =================================================
        # ASEGURAR COLUMNAS
        # =================================================

        if "PERIODO" not in df_drive.columns:
            df_drive["PERIODO"] = periodo_actual

        if "MES" not in df_drive.columns:
            df_drive["MES"] = mes_actual

        # =================================================
        # FILTRAR MES ACTUAL
        # =================================================

        df_periodo = df_drive[
            df_drive["PERIODO"].astype(str)
            == periodo_actual
        ].copy()

        # =================================================
        # SI EXISTE DATA DEL MES
        # =================================================

        if not df_periodo.empty:

            # =============================================
            # LEER COLABORADORES
            # =============================================

            data_colab = hoja_colaboradores.get_all_records()

            df_colab = pd.DataFrame(data_colab)

            df_colab = df_colab.fillna("")

            # =============================================
            # AGREGAR NUEVOS DNIS
            # =============================================

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
    # DATA
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
    # FILTROS
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
    # COLUMNAS VISIBLES
    # =====================================================

    columnas_visibles = [
        "PROVINCIA",
        "DNI",
        "NOMBRE",
        "ESTADO"
    ] + COLUMNAS_DIAS

    df_visible = df[columnas_visibles].copy()

    # =====================================================
    # GRID
    # =====================================================

    gb = GridOptionsBuilder.from_dataframe(df_visible)

    # =====================================================
    # COLUMNAS
    # =====================================================

    gb.configure_column(
        "PROVINCIA",
        width=200,
        editable=False
    )

    gb.configure_column(
        "DNI",
        width=140,
        editable=False
    )

    gb.configure_column(
        "NOMBRE",
        width=220,
        editable=False
    )

    gb.configure_column(
        "ESTADO",
        width=140,
        editable=False
    )

    # =====================================================
    # SEMANA ACTUAL
    # =====================================================

    hoy = datetime.now().day

    semana_inicio = ((hoy - 1) // 7) * 7 + 1
    semana_fin = min(semana_inicio + 6, 31)

    # =====================================================
    # COLORES
    # =====================================================

    color_js = JsCode("""

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

    # =====================================================
    # DIAS
    # =====================================================

    for i in range(1, 32):

        editable = semana_inicio <= i <= semana_fin

        gb.configure_column(

            f"DIA_{i}",

            width=90,

            editable=editable,

            cellEditor="agSelectCellEditor",

            cellEditorParams={
                "values": ["", "A", "F"]
            },

            cellStyle=color_js
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

        df_visible,

        gridOptions=grid_options,

        theme="streamlit",

        height=520,

        fit_columns_on_grid_load=False,

        allow_unsafe_jscode=True,

        update_mode=GridUpdateMode.MANUAL,

        data_return_mode=DataReturnMode.AS_INPUT,

        reload_data=True,

        enable_enterprise_modules=False,

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

        try:

            # =============================================
            # DATA EDITADA
            # =============================================

            df_editado = pd.DataFrame(
                response["data"]
            ).fillna("")

            # =============================================
            # RECUPERAR COLUMNAS OCULTAS
            # =============================================

            for col in COLUMNAS_FIJAS:

                if col not in df_editado.columns:

                    df_editado[col] = df[col]

            # =============================================
            # PERIODO
            # =============================================

            hoy = datetime.now()

            periodo_actual = hoy.strftime("%Y-%m")
            mes_actual = hoy.strftime("%m")

            df_editado["PERIODO"] = periodo_actual
            df_editado["MES"] = mes_actual

            # =============================================
            # LEER DRIVE
            # =============================================

            data_drive = hoja_asistencia.get_all_records()

            if len(data_drive) > 0:

                df_drive = pd.DataFrame(data_drive)

                df_drive = df_drive.fillna("")

                # =========================================
                # HISTORICO
                # =========================================

                if "PERIODO" in df_drive.columns:

                    historico = df_drive[
                        df_drive["PERIODO"].astype(str)
                        != periodo_actual
                    ].copy()

                else:

                    historico = pd.DataFrame()

                # =========================================
                # UNIR
                # =========================================

                df_final = pd.concat(
                    [historico, df_editado],
                    ignore_index=True
                )

            else:

                df_final = df_editado.copy()

            # =============================================
            # ORDEN
            # =============================================

            columnas_finales = (
                COLUMNAS_FIJAS +
                COLUMNAS_DIAS
            )

            for col in columnas_finales:

                if col not in df_final.columns:
                    df_final[col] = ""

            df_final = df_final[columnas_finales]

            # =============================================
            # GUARDAR DRIVE
            # =============================================

            hoja_asistencia.clear()

            hoja_asistencia.update(

                [df_final.columns.values.tolist()] +
                df_final.values.tolist()
            )

            # =============================================
            # MENSAJE
            # =============================================

            st.success(
                "✅ Asistencia guardada correctamente"
            )

            # =============================================
            # RECARGAR
            # =============================================

            st.rerun()

        except Exception as e:

            st.error(
                f"❌ Error guardando asistencia: {e}"
            )