# =========================================================
# asistencia.py
# VERSION FINAL ANTIFREEZE + GUARDA DRIVE
# =========================================================

import streamlit as st
import pandas as pd
import calendar

from datetime import datetime

from st_aggrid import (
    AgGrid,
    GridOptionsBuilder,
    GridUpdateMode,
    JsCode
)

# =========================================================
# CACHE
# =========================================================

@st.cache_data(ttl=60)
def cargar_asistencia_cache(
    hoja_asistencia
):
    return hoja_asistencia.get_all_records()

# =========================================================
# COLUMNAS
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

    valores = hoja_asistencia.get_all_values()

    # =====================================================
    # VACIO
    # =====================================================

    if len(valores) == 0:

        hoja_asistencia.append_row(
            columnas
        )

        return columnas

    headers = [
        str(x).strip()
        for x in valores[0]
    ]

    faltantes = []

    for c in columnas:

        if c not in headers:
            faltantes.append(c)

    # =====================================================
    # AGREGAR SOLO FALTANTES
    # =====================================================

    if len(faltantes) > 0:

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

    asegurar_columnas_asistencia(
        hoja_asistencia
    )

    data = cargar_asistencia_cache(
        hoja_asistencia
    )

    # =====================================================
    # YA EXISTE
    # =====================================================

    if len(data) > 0:

        df = pd.DataFrame(data)

        # =============================================
        # ASEGURAR COLUMNAS DIAS
        # =============================================

        for dia in obtener_columnas_dias():

            if dia not in df.columns:

                df[dia] = ""

        return df

    # =====================================================
    # CREAR NUEVO
    # =====================================================

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

    df = pd.DataFrame(registros)

    hoja_asistencia.clear()

    hoja_asistencia.update(
        "A1",
        [df.columns.tolist()] +
        df.values.tolist()
    )

    return df

# =========================================================
# MAIN
# =========================================================

def mostrar_asistencia(
    hoja_asistencia,
    hoja_colaboradores
):

    st.markdown(
        "# 🗓️ Control de Asistencia"
    )

    # =====================================================
    # CARGAR COLABORADORES
    # =====================================================

    colaboradores = (
        hoja_colaboradores
        .get_all_records()
    )

    df_colab = pd.DataFrame(
        colaboradores
    )

    df_colab.columns = (
        df_colab.columns
        .str.strip()
        .str.upper()
    )

    # =====================================================
    # ASISTENCIA
    # =====================================================

    df = generar_base_asistencia(
        hoja_asistencia,
        df_colab
    )

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

    # =====================================================
    # ASEGURAR COLUMNAS
    # =====================================================

    for c in columnas:

        if c not in df.columns:

            df[c] = ""

    df = df[columnas]

    # =====================================================
    # LIMPIAR NONE
    # =====================================================

    df = df.fillna("")

    # =====================================================
    # FILTROS
    # =====================================================

    c1, c2 = st.columns(2)

    with c1:

        supervisor = st.selectbox(
            "🔍 Supervisor",
            ["TODOS"] +
            sorted(
                df["SUPERVISOR"]
                .astype(str)
                .unique()
                .tolist()
            )
        )

    with c2:

        coordinador = st.selectbox(
            "🔍 Coordinador",
            ["TODOS"] +
            sorted(
                df["COORDINADOR"]
                .astype(str)
                .unique()
                .tolist()
            )
        )

    # =====================================================
    # FILTROS
    # =====================================================

    if supervisor != "TODOS":

        df = df[
            df["SUPERVISOR"]
            == supervisor
        ]

    if coordinador != "TODOS":

        df = df[
            df["COORDINADOR"]
            == coordinador
        ]

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

        if(params.value == 'A') {

            return {
                'backgroundColor': '#B7E4C7',
                'color': '#1B4332',
                'fontWeight': 'bold',
                'textAlign': 'center'
            }

        }

        if(params.value == 'F') {

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

    gb = GridOptionsBuilder.from_dataframe(
        df
    )

    # =====================================================
    # FIJAS
    # =====================================================

    for c in columnas_fijas:

        gb.configure_column(
            c,
            editable=False,
            width=160
        )

    # =====================================================
    # DIAS
    # =====================================================

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

    # =====================================================
    # OPCIONES
    # =====================================================

    gb.configure_grid_options(

        suppressRowClickSelection=True,

        suppressColumnVirtualisation=True,

        suppressRowVirtualisation=True,

        domLayout='normal'

    )

    gridOptions = gb.build()

    # =====================================================
    # TABLA
    # =====================================================

    response = AgGrid(

        df,

        gridOptions=gridOptions,

        allow_unsafe_jscode=True,

        enable_enterprise_modules=False,

        fit_columns_on_grid_load=False,

        update_mode=GridUpdateMode.VALUE_CHANGED,

        reload_data=False,

        height=520,

        theme="streamlit",

        key="asistencia_grid"

    )

    # =====================================================
    # DATA
    # =====================================================

    df_editado = pd.DataFrame(
        response["data"]
    )

    # =====================================================
    # LEYENDA
    # =====================================================

    st.markdown(
        "A = Asistencia 🟩 | "
        "F = Falta 🟥"
    )

    # =====================================================
    # BOTON
    # =====================================================

    guardar = st.button(
        "💾 Guardar Asistencia"
    )

    # =====================================================
    # GUARDAR
    # =====================================================

    if guardar:

        try:

            cambios = []

            for fila in range(len(df_editado)):

                for dia in columnas_dias:

                    nuevo = str(
                        df_editado
                        .iloc[fila][dia]
                    ).strip()

                    actual = str(
                        df
                        .iloc[fila][dia]
                    ).strip()

                    if nuevo != actual:

                        fila_real = fila + 2

                        col_real = (
                            list(df.columns)
                            .index(dia)
                        ) + 1

                        cambios.append({
                            "fila": fila_real,
                            "col": col_real,
                            "valor": nuevo
                        })

            # =================================================
            # SOLO ACTUALIZA CAMBIOS
            # =================================================

            if len(cambios) > 0:

                requests = []

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

                    requests.append({
                        "range": rango,
                        "values": [
                            [c["valor"]]
                        ]
                    })

                hoja_asistencia.batch_update(
                    requests
                )

            # =================================================
            # LIMPIAR CACHE
            # =================================================

            st.cache_data.clear()

            # =================================================
            # MENSAJE
            # =================================================

            st.success(
                "✅ Asistencia guardada correctamente"
            )

        except Exception as e:

            st.error(
                f"❌ Error: {e}"
            )