# =========================================================
# asistencia.py
# VERSION FINAL ESTABLE
# NO FREEZE
# SOLO SEMANA ACTUAL
# GUARDA REAL DRIVE
# ORDENA COLUMNAS
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

@st.cache_data(ttl=120)
def cargar_data_asistencia(
    hoja_asistencia
):
    return hoja_asistencia.get_all_records()

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
# SEMANA ACTUAL
# =========================================================

def obtener_semana_actual():

    hoy = datetime.now().day

    inicio = ((hoy - 1) // 7) * 7 + 1
    fin = min(inicio + 6, 31)

    return list(range(inicio, fin + 1))

# =========================================================
# ASEGURAR COLUMNAS
# =========================================================

def asegurar_columnas(
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

    if len(data) == 0:

        hoja_asistencia.append_row(
            columnas
        )

        return columnas

    headers = [
        str(x).strip()
        for x in data[0]
    ]

    faltantes = []

    for c in columnas:

        if c not in headers:
            faltantes.append(c)

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

def generar_base(
    hoja_asistencia,
    df_colab
):

    asegurar_columnas(
        hoja_asistencia
    )

    data = cargar_data_asistencia(
        hoja_asistencia
    )

    # =====================================================
    # YA EXISTE
    # =====================================================

    if len(data) > 0:

        df = pd.DataFrame(data)

        # =============================================
        # NUEVOS REGISTROS
        # =============================================

        dnis_existentes = (
            df["DNI"]
            .astype(str)
            .tolist()
        )

        nuevos = df_colab[
            ~df_colab["DNI"]
            .astype(str)
            .isin(dnis_existentes)
        ]

        if len(nuevos) > 0:

            nuevos_registros = []

            for _, row in nuevos.iterrows():

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

                nuevos_registros.append(fila)

            df_nuevo = pd.DataFrame(
                nuevos_registros
            )

            df = pd.concat(
                [df, df_nuevo],
                ignore_index=True
            )

            hoja_asistencia.clear()

            hoja_asistencia.update(
                "A1",
                [df.columns.tolist()] +
                df.values.tolist()
            )

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
    # COLAB
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
    # BASE
    # =====================================================

    df = generar_base(
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

    for c in columnas:

        if c not in df.columns:

            df[c] = ""

    df = df[columnas]

    # =====================================================
    # ORDENAR
    # =====================================================

    df = df.sort_values(
        by=[
            "NOMBRE",
            "PROVINCIA"
        ],
        ascending=True
    ).reset_index(drop=True)

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

    semana_actual = obtener_semana_actual()

    # =====================================================
    # FIJAS
    # =====================================================

    for c in columnas_fijas:

        gb.configure_column(
            c,
            editable=False,
            sortable=True,
            filter=True,
            width=150
        )

    # =====================================================
    # DIAS
    # =====================================================

    for dia in columnas_dias:

        numero = int(
            dia.replace(
                "DIA_",
                ""
            )
        )

        editable = numero in semana_actual

        gb.configure_column(

            dia,

            editable=editable,

            sortable=False,

            filter=False,

            width=90,

            singleClickEdit=True,

            cellEditor='agSelectCellEditor',

            cellEditorParams={
                'values': ['', 'A', 'F']
            },

            cellStyle=color_js

        )

    # =====================================================
    # GRID OPTIONS
    # =====================================================

    gb.configure_grid_options(

        animateRows=False,

        suppressRowTransform=True,

        suppressColumnVirtualisation=False,

        suppressRowVirtualisation=False,

        rowBuffer=0,

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

        theme="streamlit",

        height=520,

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

            # =============================================
            # REEMPLAZAR VACIOS
            # =============================================

            df_editado = (
                df_editado
                .fillna("")
            )

            # =============================================
            # ACTUALIZAR COMPLETO
            # =============================================

            hoja_asistencia.clear()

            hoja_asistencia.update(

                "A1",

                [
                    df_editado.columns.tolist()
                ] +
                df_editado.values.tolist()

            )

            # =============================================
            # LIMPIAR CACHE
            # =============================================

            st.cache_data.clear()

            # =============================================
            # MENSAJE
            # =============================================

            st.success(
                "✅ Asistencia guardada correctamente"
            )

        except Exception as e:

            st.error(
                f"❌ Error al guardar: {e}"
            )