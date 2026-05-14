# =========================================================
# asistencia.py
# VERSION FINAL ESTABLE - SIN FREEZE
# =========================================================

import streamlit as st
import pandas as pd
from st_aggrid import (
    AgGrid,
    GridOptionsBuilder,
    GridUpdateMode,
    JsCode
)

from datetime import datetime
import calendar

# =========================================================
# COLUMNAS DIAS
# =========================================================

def obtener_columnas_dias():

    hoy = datetime.now()

    dias_mes = calendar.monthrange(
        hoy.year,
        hoy.month
    )[1]

    return [
        f"DIA_{i}"
        for i in range(1, dias_mes + 1)
    ]


# =========================================================
# ASEGURAR COLUMNAS
# =========================================================

def asegurar_columnas_asistencia(
    hoja_asistencia
):

    columnas_fijas = [
        "SUPERVISOR",
        "COORDINADOR",
        "DEPARTAMENTO",
        "PROVINCIA",
        "DNI",
        "NOMBRE",
        "ESTADO"
    ]

    columnas = (
        columnas_fijas +
        obtener_columnas_dias()
    )

    data = hoja_asistencia.get_all_values()

    # =========================================
    # SI NO EXISTE NADA
    # =========================================

    if len(data) == 0:

        hoja_asistencia.append_row(
            columnas
        )

        return columnas

    headers = [
        str(x).strip()
        for x in data[0]
    ]

    # =========================================
    # AGREGAR DIAS FALTANTES
    # =========================================

    faltantes = []

    for col in columnas:

        if col not in headers:

            faltantes.append(col)

    if faltantes:

        headers.extend(faltantes)

        hoja_asistencia.update(
            "A1",
            [headers]
        )

    return headers


# =========================================================
# GENERAR BASE
# =========================================================

def generar_base_asistencia(
    hoja_asistencia,
    df_colab
):

    headers = asegurar_columnas_asistencia(
        hoja_asistencia
    )

    data = hoja_asistencia.get_all_records()

    # =========================================
    # SI YA EXISTE DATA
    # =========================================

    if len(data) > 0:

        return pd.DataFrame(data)

    # =========================================
    # CREAR BASE NUEVA
    # =========================================

    registros = []

    for _, row in df_colab.iterrows():

        fila = {}

        fila["SUPERVISOR"] = str(
            row.get(
                "SUPERVISOR A CARGO",
                ""
            )
        )

        fila["COORDINADOR"] = str(
            row.get(
                "COORDINADOR",
                ""
            )
        )

        fila["DEPARTAMENTO"] = str(
            row.get(
                "DEPARTAMENTO",
                ""
            )
        )

        fila["PROVINCIA"] = str(
            row.get(
                "PROVINCIA",
                ""
            )
        )

        fila["DNI"] = str(
            row.get(
                "DNI",
                ""
            )
        )

        fila["NOMBRE"] = (
            str(row.get("NOMBRES", ""))
            + " " +
            str(row.get("APELLIDO PATERNO", ""))
        ).strip()

        fila["ESTADO"] = str(
            row.get(
                "ESTADO",
                ""
            )
        )

        for dia in obtener_columnas_dias():

            fila[dia] = ""

        registros.append(fila)

    df_final = pd.DataFrame(registros)

    hoja_asistencia.clear()

    hoja_asistencia.update(
        "A1",
        [df_final.columns.tolist()] +
        df_final.values.tolist()
    )

    return df_final


# =========================================================
# MAIN
# =========================================================

def mostrar_asistencia(
    hoja_asistencia,
    hoja_colaboradores
):

    st.markdown(
        "## 🗓️ Control de Asistencia"
    )

    # =====================================================
    # CARGAR DATA
    # =====================================================

    data_colab = (
        hoja_colaboradores
        .get_all_records()
    )

    df_colab = pd.DataFrame(
        data_colab
    )

    df_colab.columns = (
        df_colab.columns
        .str.strip()
        .str.upper()
    )

    # =====================================================
    # BASE ASISTENCIA
    # =====================================================

    df_asistencia = generar_base_asistencia(
        hoja_asistencia,
        df_colab
    )

    # =====================================================
    # FILTROS
    # =====================================================

    col1, col2 = st.columns(2)

    with col1:

        supervisor = st.selectbox(
            "🔍 Supervisor",
            ["TODOS"] +
            sorted(
                df_asistencia[
                    "SUPERVISOR"
                ]
                .dropna()
                .astype(str)
                .unique()
                .tolist()
            )
        )

    with col2:

        coordinador = st.selectbox(
            "🔍 Coordinador",
            ["TODOS"] +
            sorted(
                df_asistencia[
                    "COORDINADOR"
                ]
                .dropna()
                .astype(str)
                .unique()
                .tolist()
            )
        )

    # =====================================================
    # FILTRAR
    # =====================================================

    if supervisor != "TODOS":

        df_asistencia = df_asistencia[
            df_asistencia["SUPERVISOR"]
            == supervisor
        ]

    if coordinador != "TODOS":

        df_asistencia = df_asistencia[
            df_asistencia["COORDINADOR"]
            == coordinador
        ]

    # =====================================================
    # COLUMNAS
    # =====================================================

    columnas_fijas = [
        "SUPERVISOR",
        "COORDINADOR",
        "DEPARTAMENTO",
        "PROVINCIA",
        "DNI",
        "NOMBRE",
        "ESTADO"
    ]

    columnas_dias = (
        obtener_columnas_dias()
    )

    columnas = (
        columnas_fijas +
        columnas_dias
    )

    df_asistencia = (
        df_asistencia[columnas]
    )

    # =====================================================
    # INFO
    # =====================================================

    st.info(
        "Solo editable semana actual | "
        "A = Asistencia | "
        "F = Falta"
    )

    # =====================================================
    # COLORES
    # =====================================================

    color_js = JsCode("""

    function(params) {

        if (params.value == 'A') {

            return {
                'backgroundColor': '#B7E4C7',
                'color': '#1B4332',
                'fontWeight': 'bold',
                'textAlign': 'center'
            }

        }

        if (params.value == 'F') {

            return {
                'backgroundColor': '#F4ACB7',
                'color': '#9D0208',
                'fontWeight': 'bold',
                'textAlign': 'center'
            }

        }

        return {
            'textAlign': 'center'
        }

    }

    """)

    # =====================================================
    # GRID
    # =====================================================

    gb = (
        GridOptionsBuilder
        .from_dataframe(df_asistencia)
    )

    # =========================================
    # COLUMNAS FIJAS
    # =========================================

    for col in columnas_fijas:

        gb.configure_column(
            col,
            editable=False,
            width=150
        )

    # =========================================
    # COLUMNAS DIAS
    # =========================================

    for dia in columnas_dias:

        gb.configure_column(

            dia,

            editable=True,

            singleClickEdit=True,

            cellEditor='agSelectCellEditor',

            cellEditorParams={
                'values': ['', 'A', 'F']
            },

            cellStyle=color_js,

            width=90
        )

    gb.configure_grid_options(
        domLayout='normal'
    )

    gridOptions = gb.build()

    # =====================================================
    # TABLA
    # =====================================================

    response = AgGrid(

        df_asistencia,

        gridOptions=gridOptions,

        allow_unsafe_jscode=True,

        update_mode=GridUpdateMode.VALUE_CHANGED,

        fit_columns_on_grid_load=False,

        reload_data=False,

        height=500,

        theme="streamlit",

        key="tabla_asistencia"

    )

    # =====================================================
    # DF EDITADO
    # =====================================================

    df_editado = pd.DataFrame(
        response["data"]
    )

    # =====================================================
    # LEYENDA
    # =====================================================

    st.markdown(
        """
        A = Asistencia 🟩 | F = Falta 🟥
        """
    )

    # =====================================================
    # GUARDAR
    # =====================================================

    if st.button(
        "💾 Guardar Asistencia"
    ):

        try:

            # =============================================
            # NO VOLVER A LEER DRIVE
            # =============================================

            df_drive = (
                df_asistencia.copy()
            )

            cambios = []

            for i in range(len(df_editado)):

                for dia in columnas_dias:

                    nuevo = str(
                        df_editado
                        .iloc[i][dia]
                    ).strip()

                    actual = str(
                        df_drive
                        .iloc[i][dia]
                    ).strip()

                    if nuevo != actual:

                        fila_real = i + 2

                        col_real = (
                            list(df_drive.columns)
                            .index(dia)
                        ) + 1

                        cambios.append({
                            "fila": fila_real,
                            "col": col_real,
                            "valor": nuevo
                        })

            # =============================================
            # BATCH UPDATE
            # =============================================

            batch_data = []

            for c in cambios:

                col = c["col"]

                letra = ""

                while col > 0:

                    col, resto = divmod(
                        col - 1,
                        26
                    )

                    letra = (
                        chr(65 + resto)
                        + letra
                    )

                rango = (
                    f"{letra}{c['fila']}"
                )

                batch_data.append({
                    "range": rango,
                    "values": [
                        [c["valor"]]
                    ]
                })

            if len(batch_data) > 0:

                hoja_asistencia.batch_update(
                    batch_data
                )

            st.success(
                "✅ Asistencia guardada correctamente"
            )

        except Exception as e:

            st.error(
                f"❌ Error: {e}"
            )