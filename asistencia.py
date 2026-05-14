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
def cargar_data_asistencia(_hoja_asistencia):

    return _hoja_asistencia.get_all_records()

# =========================================================
# DIAS MES
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

    fin = min(
        inicio + 6,
        31
    )

    return list(
        range(inicio, fin + 1)
    )

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

        headers.extend(
            faltantes
        )

        hoja_asistencia.update(
            "A1",
            [headers]
        )

    return headers

# =========================================================
# BASE
# =========================================================

def generar_base(
    hoja_asistencia,
    df_colab
):

    asegurar_columnas(
        hoja_asistencia
    )

    # =====================================================
    # DATA DRIVE
    # =====================================================

    data = cargar_data_asistencia(
        _hoja_asistencia=hoja_asistencia
    )

    if len(data) > 0:

        df = pd.DataFrame(data)

    else:

        df = pd.DataFrame()

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

    for c in columnas:

        if c not in df.columns:
            df[c] = ""

    # =====================================================
    # NUEVOS DNI
    # =====================================================

    if "DNI" in df.columns:

        dnis_existentes = (
            df["DNI"]
            .astype(str)
            .tolist()
        )

    else:

        dnis_existentes = []

    nuevos = df_colab[
        ~df_colab["DNI"]
        .astype(str)
        .isin(dnis_existentes)
    ]

    # =====================================================
    # AGREGAR NUEVOS
    # =====================================================

    if len(nuevos) > 0:

        registros_nuevos = []

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

            registros_nuevos.append(
                fila
            )

        df_nuevo = pd.DataFrame(
            registros_nuevos
        )

        df = pd.concat(
            [df, df_nuevo],
            ignore_index=True
        )

    df = df[columnas]

    df = df.fillna("")

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
    # COLABORADORES
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
    # ORDEN
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

    st.info(
        "Solo editable semana actual | A = Asistencia | F = Falta"
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

    gb = GridOptionsBuilder.from_dataframe(df)

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

            width=90,

            singleClickEdit=True,

            cellEditor='agSelectCellEditor',

            cellEditorParams={
                'values': ['', 'A', 'F']
            },

            cellStyle=color_js

        )

    # =====================================================
    # GRID
    # =====================================================

    gb.configure_grid_options(

        suppressAnimationFrame=True,
        suppressRowTransform=True,
        animateRows=False,
        rowBuffer=5

    )

    gridOptions = gb.build()

    response = AgGrid(

        df,

        gridOptions=gridOptions,

        allow_unsafe_jscode=True,

        update_mode=GridUpdateMode.VALUE_CHANGED,

        fit_columns_on_grid_load=False,

        reload_data=False,

        enable_enterprise_modules=False,

        theme="streamlit",

        height=520,

        key="grid_asistencia"

    )

    df_editado = pd.DataFrame(
        response["data"]
    )

    st.markdown(
        "A = Asistencia 🟩 | F = Falta 🟥"
    )

    guardar = st.button(
        "💾 Guardar Asistencia"
    )

    # =====================================================
    # GUARDAR
    # =====================================================

    if guardar:

        try:

            with st.spinner(
                "Guardando asistencia..."
            ):

                df_editado = (
                    df_editado
                    .fillna("")
                )

                headers = (
                    df_editado.columns
                    .tolist()
                )

                values = (
                    df_editado
                    .astype(str)
                    .values
                    .tolist()
                )

                # =================================================
                # GUARDAR REAL
                # =================================================

                hoja_asistencia.clear()

                hoja_asistencia.update(

                    "A1",

                    [headers] + values

                )

                # =================================================
                # LIMPIAR CACHE
                # =================================================

                st.cache_data.clear()

            st.success(
                "✅ Asistencia guardada correctamente"
            )

        except Exception as e:

            st.error(
                f"❌ Error al guardar: {e}"
            )