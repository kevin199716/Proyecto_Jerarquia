# =========================================================
# asistencia.py
# VERSION FINAL ESTABLE
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
# OBTENER MES ACTUAL
# =========================================================

def obtener_mes_actual():

    hoy = datetime.now()

    return hoy.month, hoy.year


# =========================================================
# GENERAR COLUMNAS DIAS
# =========================================================

def obtener_columnas_dias():

    mes, anio = obtener_mes_actual()

    cantidad_dias = calendar.monthrange(
        anio,
        mes
    )[1]

    columnas = []

    for i in range(1, cantidad_dias + 1):

        columnas.append(f"DIA_{i}")

    return columnas


# =========================================================
# ASEGURAR COLUMNAS EN GOOGLE SHEETS
# =========================================================

def asegurar_columnas_asistencia(
    hoja_asistencia
):

    data = hoja_asistencia.get_all_values()

    if not data:

        headers = [
            "SUPERVISOR",
            "COORDINADOR",
            "DEPARTAMENTO",
            "PROVINCIA",
            "DNI",
            "NOMBRE",
            "ESTADO"
        ]

        headers.extend(
            obtener_columnas_dias()
        )

        hoja_asistencia.append_row(headers)

        return headers

    headers = data[0]

    headers = [x.strip() for x in headers]

    dias_actuales = obtener_columnas_dias()

    faltantes = []

    for dia in dias_actuales:

        if dia not in headers:

            faltantes.append(dia)

    if faltantes:

        headers.extend(faltantes)

        hoja_asistencia.update(
            "A1",
            [headers]
        )

    return headers


# =========================================================
# GENERAR BASE ASISTENCIA
# =========================================================

def generar_base_asistencia(
    hoja_asistencia,
    df_colab
):

    headers = asegurar_columnas_asistencia(
        hoja_asistencia
    )

    data = hoja_asistencia.get_all_records()

    if len(data) > 0:

        return pd.DataFrame(data)

    columnas_base = [
        "SUPERVISOR",
        "COORDINADOR",
        "DEPARTAMENTO",
        "PROVINCIA",
        "DNI",
        "NOMBRE",
        "ESTADO"
    ]

    columnas_finales = columnas_base + obtener_columnas_dias()

    registros = []

    for _, row in df_colab.iterrows():

        registro = {}

        registro["SUPERVISOR"] = str(
            row.get(
                "SUPERVISOR A CARGO",
                ""
            )
        )

        registro["COORDINADOR"] = str(
            row.get(
                "COORDINADOR",
                ""
            )
        )

        registro["DEPARTAMENTO"] = str(
            row.get(
                "DEPARTAMENTO",
                ""
            )
        )

        registro["PROVINCIA"] = str(
            row.get(
                "PROVINCIA",
                ""
            )
        )

        registro["DNI"] = str(
            row.get(
                "DNI",
                ""
            )
        )

        nombre = (
            str(row.get("NOMBRES", "")) + " " +
            str(row.get("APELLIDO PATERNO", ""))
        )

        registro["NOMBRE"] = nombre.strip()

        registro["ESTADO"] = str(
            row.get(
                "ESTADO",
                ""
            )
        )

        for dia in obtener_columnas_dias():

            registro[dia] = ""

        registros.append(registro)

    df_final = pd.DataFrame(registros)

    hoja_asistencia.clear()

    hoja_asistencia.update(
        "A1",
        [df_final.columns.tolist()] +
        df_final.values.tolist()
    )

    return df_final


# =========================================================
# MOSTRAR ASISTENCIA
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

    data_colab = hoja_colaboradores.get_all_records()

    df_colab = pd.DataFrame(data_colab)

    df_colab.columns = (
        df_colab.columns
        .str.strip()
        .str.upper()
    )

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
            df_asistencia["SUPERVISOR"] == supervisor
        ]

    if coordinador != "TODOS":

        df_asistencia = df_asistencia[
            df_asistencia["COORDINADOR"] == coordinador
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

    columnas_dias = obtener_columnas_dias()

    columnas = columnas_fijas + columnas_dias

    df_asistencia = df_asistencia[columnas]

    # =====================================================
    # MENSAJE
    # =====================================================

    st.info(
        "Solo editable semana actual | "
        "A = Asistencia | "
        "F = Falta"
    )

    # =====================================================
    # GRID
    # =====================================================

    gb = GridOptionsBuilder.from_dataframe(
        df_asistencia
    )

    for col in columnas_fijas:

        gb.configure_column(
            col,
            editable=False,
            width=140
        )

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

    for dia in columnas_dias:

        gb.configure_column(
            dia,
            editable=True,
            singleClickEdit=True,
            cellEditor="agSelectCellEditor",
            cellEditorParams={
                "values": ["", "A", "F"]
            },
            cellStyle=color_js,
            width=90
        )

    gb.configure_grid_options(
        domLayout='normal',
        suppressRowClickSelection=True
    )

    gridOptions = gb.build()

    # =====================================================
    # TABLA
    # =====================================================

    response = AgGrid(

        df_asistencia,

        gridOptions=gridOptions,

        update_mode=GridUpdateMode.VALUE_CHANGED,

        allow_unsafe_jscode=True,

        fit_columns_on_grid_load=False,

        height=500,

        reload_data=False,

        theme="streamlit",

        key="tabla_asistencia"

    )

    df_editado = pd.DataFrame(
        response["data"]
    )

    # =====================================================
    # GUARDAR
    # =====================================================

    if st.button(
        "💾 Guardar Asistencia"
    ):

        try:

            data_drive = hoja_asistencia.get_all_records()

            df_drive = pd.DataFrame(data_drive)

            cambios = []

            for i in range(len(df_editado)):

                for dia in columnas_dias:

                    valor_nuevo = str(
                        df_editado.iloc[i][dia]
                    ).strip()

                    valor_drive = str(
                        df_drive.iloc[i][dia]
                    ).strip()

                    if valor_nuevo != valor_drive:

                        fila_real = i + 2

                        columna_real = (
                            list(df_drive.columns)
                            .index(dia)
                        ) + 1

                        cambios.append({
                            "fila": fila_real,
                            "columna": columna_real,
                            "valor": valor_nuevo
                        })

            # =============================================
            # UPDATE MASIVO
            # =============================================

            batch_data = []

            for c in cambios:

                letra = ""

                col = c["columna"]

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
                    "values": [[c["valor"]]]
                })

            if batch_data:

                hoja_asistencia.batch_update(
                    batch_data
                )

            st.success(
                "✅ Asistencia guardada correctamente"
            )

        except Exception as e:

            st.error(
                f"❌ Error guardando: {e}"
            )