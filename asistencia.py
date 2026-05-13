import streamlit as st
import pandas as pd

from datetime import datetime, timedelta

from st_aggrid import (
    AgGrid,
    GridOptionsBuilder,
    GridUpdateMode,
    JsCode
)

# =====================================================
# CACHE
# =====================================================

@st.cache_data(ttl=60)
def cargar_colaboradores_cache(data):
    return pd.DataFrame(data)

# =====================================================
# GENERAR MES
# =====================================================

def generar_asistencia_mes(
    hoja_asistencia,
    df_colab
):

    hoy = datetime.now()

    periodo_actual = hoy.strftime("%Y-%m")

    valores = hoja_asistencia.get_all_values()

    # =================================================
    # CREAR CABECERA
    # =================================================

    if not valores:

        headers = [
            "PERIODO",
            "DNI",
            "NOMBRE",
            "SUPERVISOR",
            "COORDINADOR",
            "DEPARTAMENTO",
            "PROVINCIA",
            "ESTADO"
        ]

        for dia in range(1, 32):

            headers.append(
                f"DIA_{dia}"
            )

        hoja_asistencia.append_row(headers)

        valores = hoja_asistencia.get_all_values()

    headers = valores[0]

    data = valores[1:]

    # =================================================
    # DATAFRAME
    # =================================================

    if data:

        df_existente = pd.DataFrame(
            data,
            columns=headers
        )

    else:

        df_existente = pd.DataFrame(
            columns=headers
        )

    # =================================================
    # VALIDAR PERIODO
    # =================================================

    if not df_existente.empty:

        existe_periodo = (
            df_existente["PERIODO"]
            .astype(str)
            .eq(periodo_actual)
            .any()
        )

        if existe_periodo:

            return

    # =================================================
    # CREAR NUEVO MES
    # =================================================

    registros = []

    df_activos = df_colab[
        df_colab["ESTADO"]
        .astype(str)
        .str.upper()
        == "ACTIVO"
    ]

    for _, row in df_activos.iterrows():

        fila = {

            "PERIODO": periodo_actual,

            "DNI": str(
                row.get("DNI", "")
            ),

            "NOMBRE": str(
                row.get("NOMBRES", "")
            ),

            "SUPERVISOR": str(
                row.get("SUPERVISOR A CARGO", "")
            ),

            "COORDINADOR": str(
                row.get("COORDINADOR", "")
            ),

            "DEPARTAMENTO": str(
                row.get("DEPARTAMENTO", "")
            ),

            "PROVINCIA": str(
                row.get("PROVINCIA", "")
            ),

            "ESTADO": str(
                row.get("ESTADO", "")
            )
        }

        for dia in range(1, 32):

            fila[f"DIA_{dia}"] = ""

        registros.append(fila)

    if registros:

        df_nuevo = pd.DataFrame(registros)

        hoja_asistencia.append_rows(
            df_nuevo.astype(str)
            .values.tolist()
        )

# =====================================================
# SEMANA ACTUAL
# =====================================================

def obtener_semana_actual():

    hoy = datetime.now()

    inicio_semana = (
        hoy -
        timedelta(days=hoy.weekday())
    )

    dias_editables = []

    for i in range(7):

        fecha = (
            inicio_semana +
            timedelta(days=i)
        )

        if fecha <= hoy:

            dias_editables.append(
                fecha.day
            )

    return dias_editables

# =====================================================
# COLORES
# =====================================================

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

    return {

        'textAlign': 'center'
    }
}

""")

# =====================================================
# MAIN
# =====================================================

def mostrar_asistencia(
    hoja_asistencia,
    hoja_colaboradores
):

    st.markdown(
        "## 🗓️ Control de Asistencia"
    )

    # =================================================
    # COLABORADORES
    # =================================================

    data_colab = (
        hoja_colaboradores
        .get_all_records()
    )

    df_colab = cargar_colaboradores_cache(
        data_colab
    )

    df_colab.columns = (
        df_colab.columns
        .str.strip()
        .str.upper()
    )

    # =================================================
    # GENERAR MES
    # =================================================

    generar_asistencia_mes(
        hoja_asistencia,
        df_colab
    )

    # =================================================
    # LEER DATA
    # =================================================

    valores = (
        hoja_asistencia
        .get_all_values()
    )

    if not valores:

        st.warning(
            "No hay registros"
        )

        return

    headers = valores[0]

    data = valores[1:]

    df_total = pd.DataFrame(
        data,
        columns=headers
    )

    # =================================================
    # VALIDAR
    # =================================================

    if "PERIODO" not in df_total.columns:

        st.error(
            "La hoja Asistencia tiene estructura incorrecta"
        )

        return

    # =================================================
    # MES ACTUAL
    # =================================================

    periodo_actual = datetime.now().strftime("%Y-%m")

    df = df_total[
        df_total["PERIODO"]
        .astype(str)
        == periodo_actual
    ].copy()

    if df.empty:

        st.warning(
            "No hay registros del mes actual"
        )

        return

    # =================================================
    # FILTROS
    # =================================================

    supervisores = sorted(
        list(
            set(
                df["SUPERVISOR"]
                .astype(str)
                .tolist()
            )
        )
    )

    coordinadores = sorted(
        list(
            set(
                df["COORDINADOR"]
                .astype(str)
                .tolist()
            )
        )
    )

    c1, c2 = st.columns(2)

    with c1:

        filtro_supervisor = st.selectbox(
            "🔍 Supervisor",
            ["TODOS"] + supervisores
        )

    with c2:

        filtro_coord = st.selectbox(
            "🔍 Coordinador",
            ["TODOS"] + coordinadores
        )

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

    # =================================================
    # DIAS EDITABLES
    # =================================================

    dias_editables = obtener_semana_actual()

    st.info(
        "Solo editable semana actual | "
        "A = Asistencia | "
        "F = Falta"
    )

    # =================================================
    # COLUMNAS
    # =================================================

    columnas_base = [

        "SUPERVISOR",
        "COORDINADOR",
        "DEPARTAMENTO",
        "PROVINCIA",
        "DNI",
        "NOMBRE",
        "ESTADO"
    ]

    columnas_dias = [

        f"DIA_{dia}"
        for dia in range(1, 32)
    ]

    columnas_finales = (
        columnas_base +
        columnas_dias
    )

    columnas_existentes = [

        c for c in columnas_finales
        if c in df.columns
    ]

    df = df[columnas_existentes]

    # =================================================
    # GRID
    # =================================================

    gb = GridOptionsBuilder.from_dataframe(df)

    gb.configure_default_column(
        editable=False,
        resizable=True
    )

    # =================================================
    # COLUMNAS
    # =================================================

    columnas_normales = [

        "SUPERVISOR",
        "COORDINADOR",
        "DEPARTAMENTO",
        "PROVINCIA",
        "DNI",
        "NOMBRE",
        "ESTADO"
    ]

    for col in columnas_normales:

        gb.configure_column(
            col,
            width=170,
            editable=False
        )

    # =================================================
    # DIAS
    # =================================================

    for dia in range(1, 32):

        col = f"DIA_{dia}"

        editable = (
            dia in dias_editables
        )

        gb.configure_column(
            col,
            editable=editable,
            width=95,
            cellEditor="agSelectCellEditor",
            cellEditorParams={
                "values": ["", "A", "F"]
            },
            cellStyle=cellstyle_jscode
        )

    gridOptions = gb.build()

    # =================================================
    # GRID
    # =================================================

    grid_response = AgGrid(
        df,
        gridOptions=gridOptions,
        update_mode=GridUpdateMode.MANUAL,
        allow_unsafe_jscode=True,
        theme="streamlit",
        height=500
    )

    # =================================================
    # BOTON GUARDAR
    # =================================================

    guardar = st.button(
        "💾 Guardar Asistencia"
    )

    # =================================================
    # GUARDAR
    # =================================================

    if guardar:

        nuevo_df = pd.DataFrame(
            grid_response["data"]
        )

        nuevo_df = nuevo_df.fillna("")

        # =============================================
        # HISTORICO
        # =============================================

        df_historico = df_total[
            df_total["PERIODO"]
            != periodo_actual
        ].copy()

        # =============================================
        # MES ACTUAL
        # =============================================

        df_mes = df_total[
            df_total["PERIODO"]
            == periodo_actual
        ].copy()

        # =============================================
        # ACTUALIZAR
        # =============================================

        for _, row in nuevo_df.iterrows():

            dni = str(row["DNI"])

            for dia in range(1, 32):

                col = f"DIA_{dia}"

                valor = row.get(col, "")

                df_mes.loc[
                    df_mes["DNI"]
                    .astype(str)
                    == dni,
                    col
                ] = valor

        # =============================================
        # FINAL
        # =============================================

        df_final = pd.concat(
            [df_historico, df_mes],
            ignore_index=True
        )

        # =============================================
        # GUARDAR DRIVE
        # =============================================

        hoja_asistencia.clear()

        hoja_asistencia.update(
            [df_final.columns.values.tolist()] +
            df_final.astype(str).values.tolist()
        )

        st.success(
            "✅ Asistencia guardada correctamente"
        )

        st.rerun()