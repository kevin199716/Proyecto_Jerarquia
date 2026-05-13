from datetime import datetime, timedelta

import pandas as pd
import streamlit as st

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
    # DF EXISTENTE
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
    # VALIDAR SI EXISTE MES
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
    # NUEVO MES
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

        # =============================================
        # DIAS
        # =============================================

        for dia in range(1, 32):

            fila[f"DIA_{dia}"] = ""

        registros.append(fila)

    # =================================================
    # GUARDAR NUEVO MES
    # =================================================

    if registros:

        df_nuevo = pd.DataFrame(
            registros
        )

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
    # MES ACTUAL
    # =================================================

    periodo_actual = datetime.now().strftime("%Y-%m")

    df = df_total[
        df_total["PERIODO"]
        .astype(str)
        == periodo_actual
    ].copy()

    # =================================================
    # LIMPIAR NONE
    # =================================================

    df = df.replace("None", "")
    df = df.fillna("")

    # =================================================
    # FILTROS
    # =================================================

    supervisores = sorted(
        df["SUPERVISOR"]
        .astype(str)
        .unique()
        .tolist()
    )

    coordinadores = sorted(
        df["COORDINADOR"]
        .astype(str)
        .unique()
        .tolist()
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
    # INFO
    # =================================================

    dias_editables = obtener_semana_actual()

    st.info(
        "Solo editable semana actual | "
        "A = Asistencia | "
        "F = Falta"
    )

    # =================================================
    # GRID BUILDER
    # =================================================

    gb = GridOptionsBuilder.from_dataframe(df)

    gb.configure_default_column(
        editable=False,
        resizable=True
    )

    # =================================================
    # COLUMNAS
    # =================================================

    for col in df.columns:

        # =============================================
        # DIAS
        # =============================================

        if "DIA_" in col:

            numero_dia = int(
                col.replace("DIA_", "")
            )

            editable = (
                numero_dia in dias_editables
            )

            gb.configure_column(

                col,

                editable=editable,

                width=90,

                singleClickEdit=True,

                cellEditor="agSelectCellEditor",

                cellEditorParams={
                    "values": ["", "A", "F"]
                },

                cellStyle=JsCode("""

                function(params) {

                    if(params.value == 'A') {

                        return {
                            'backgroundColor': '#C6EFCE',
                            'color': '#006100',
                            'fontWeight': 'bold',
                            'textAlign': 'center'
                        }
                    }

                    if(params.value == 'F') {

                        return {
                            'backgroundColor': '#FFC7CE',
                            'color': '#9C0006',
                            'fontWeight': 'bold',
                            'textAlign': 'center'
                        }
                    }

                    return {
                        'backgroundColor': 'white',
                        'color': 'black',
                        'textAlign': 'center'
                    }
                }

                """)
            )

        # =============================================
        # COLUMNAS NORMALES
        # =============================================

        else:

            gb.configure_column(
                col,
                editable=False,
                width=160
            )

    # =================================================
    # GRID OPTIONS
    # =================================================

    gridOptions = gb.build()

    # =================================================
    # GRID
    # =================================================

    grid_response = AgGrid(

        df,

        gridOptions=gridOptions,

        allow_unsafe_jscode=True,

        theme="streamlit",

        height=500,

        fit_columns_on_grid_load=False,

        reload_data=False,

        update_mode=GridUpdateMode.NO_UPDATE
    )

    # =================================================
    # LEYENDA
    # =================================================

    st.caption(
        "A = Asistencia 🟩 | F = Falta 🟥"
    )

    # =================================================
    # BOTON
    # =================================================

    guardar = st.button(
        "💾 Guardar Asistencia"
    )

    # =================================================
    # GUARDAR
    # =================================================

    if guardar:

        try:

            nuevo_df = pd.DataFrame(
                grid_response["data"]
            )

            nuevo_df = nuevo_df.fillna("")

            # =========================================
            # VALIDAR A/F
            # =========================================

            for col in nuevo_df.columns:

                if "DIA_" in col:

                    nuevo_df[col] = (
                        nuevo_df[col]
                        .astype(str)
                        .str.upper()
                        .replace("NAN", "")
                    )

                    nuevo_df[col] = nuevo_df[col].apply(
                        lambda x:
                        x if x in ["", "A", "F"]
                        else ""
                    )

            # =========================================
            # HISTORICO
            # =========================================

            df_historico = df_total[
                df_total["PERIODO"]
                != periodo_actual
            ].copy()

            # =========================================
            # PERIODO
            # =========================================

            nuevo_df["PERIODO"] = periodo_actual

            # =========================================
            # ORDEN COLUMNAS
            # =========================================

            nuevo_df = nuevo_df[
                headers
            ]

            # =========================================
            # FINAL
            # =========================================

            df_final = pd.concat(
                [df_historico, nuevo_df],
                ignore_index=True
            )

            # =========================================
            # GUARDAR GOOGLE SHEETS
            # =========================================

            hoja_asistencia.clear()

            hoja_asistencia.update(
                [df_final.columns.values.tolist()] +
                df_final.astype(str).values.tolist()
            )

            st.success(
                "✅ Asistencia guardada correctamente"
            )

        except Exception as e:

            st.error(
                f"❌ Error guardando asistencia: {e}"
            )