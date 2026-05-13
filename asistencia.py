# asistencia.py

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode
from sheets import conectar_google_sheets

# =========================================================
# CACHE
# =========================================================

@st.cache_data(ttl=60)
def cargar_asistencia():
    hoja = conectar_google_sheets(
        "maestra_vendedores",
        "asistencia"
    )

    data = hoja.get_all_records()

    if not data:
        return pd.DataFrame()

    df = pd.DataFrame(data)

    df.columns = df.columns.str.strip().str.upper()

    return df


@st.cache_data(ttl=60)
def cargar_colaboradores():

    hoja = conectar_google_sheets(
        "maestra_vendedores",
        "colaboradores"
    )

    data = hoja.get_all_records()

    if not data:
        return pd.DataFrame()

    df = pd.DataFrame(data)

    df.columns = df.columns.str.strip().str.upper()

    return df


# =========================================================
# GENERAR MES
# =========================================================

def generar_asistencia_mes():

    hoja_asistencia = conectar_google_sheets(
        "maestra_vendedores",
        "asistencia"
    )

    df_asistencia = cargar_asistencia()
    df_colab = cargar_colaboradores()

    hoy = datetime.now()

    periodo_actual = hoy.strftime("%Y-%m")

    # =========================================
    # VALIDAR SI YA EXISTE EL PERIODO
    # =========================================

    if not df_asistencia.empty:

        if "PERIODO" in df_asistencia.columns:

            existe = (
                df_asistencia["PERIODO"]
                .astype(str)
                .eq(periodo_actual)
                .any()
            )

            if existe:
                return

    # =========================================
    # CREAR NUEVO MES
    # =========================================

    columnas_base = [
        "PERIODO",
        "SUPERVISOR",
        "COORDINADOR",
        "DEPARTAMENTO",
        "PROVINCIA",
        "DNI",
        "NOMBRE",
        "ESTADO"
    ]

    dias = [f"DIA_{i}" for i in range(1, 32)]

    columnas = columnas_base + dias

    registros = []

    for _, row in df_colab.iterrows():

        registro = {
            "PERIODO": periodo_actual,
            "SUPERVISOR": row.get("SUPERVISOR A CARGO", ""),
            "COORDINADOR": row.get("COORDINADOR", ""),
            "DEPARTAMENTO": row.get("DEPARTAMENTO", ""),
            "PROVINCIA": row.get("PROVINCIA", ""),
            "DNI": str(row.get("DNI", "")),
            "NOMBRE": (
                f"{row.get('NOMBRES','')} "
                f"{row.get('APELLIDO PATERNO','')} "
                f"{row.get('APELLIDO MATERNO','')}"
            ).strip(),
            "ESTADO": row.get("ESTADO", "")
        }

        for d in dias:
            registro[d] = ""

        registros.append(registro)

    nuevo_df = pd.DataFrame(registros)

    if df_asistencia.empty:

        hoja_asistencia.update(
            [columnas] + nuevo_df.values.tolist()
        )

    else:

        hoja_asistencia.append_rows(
            nuevo_df.values.tolist()
        )


# =========================================================
# TABLA
# =========================================================

def mostrar_asistencia():

    generar_asistencia_mes()

    hoja_asistencia = conectar_google_sheets(
        "maestra_vendedores",
        "asistencia"
    )

    df = cargar_asistencia()

    if df.empty:
        st.warning("No hay datos")
        return

    df.columns = df.columns.str.strip().str.upper()

    # =========================================
    # PERIODO
    # =========================================

    periodo_actual = datetime.now().strftime("%Y-%m")

    df = df[
        df["PERIODO"].astype(str) == periodo_actual
    ]

    # =========================================
    # FILTROS
    # =========================================

    st.markdown("## 📅 Control de Asistencia")

    c1, c2, c3 = st.columns(3)

    with c1:
        st.metric("👥 HC TOTAL", len(df))

    with c2:
        st.metric(
            "✅ ACTIVOS",
            len(df[df["ESTADO"] == "ACTIVO"])
        )

    with c3:
        st.metric(
            "❌ INACTIVOS",
            len(df[df["ESTADO"] == "INACTIVO"])
        )

    supervisores = sorted(
        [
            str(x)
            for x in df["SUPERVISOR"]
            .dropna()
            .astype(str)
            .unique()
        ]
    )

    coordinadores = sorted(
        [
            str(x)
            for x in df["COORDINADOR"]
            .dropna()
            .astype(str)
            .unique()
        ]
    )

    c1, c2 = st.columns(2)

    with c1:
        supervisor = st.selectbox(
            "🔍 Supervisor",
            ["TODOS"] + supervisores
        )

    with c2:
        coordinador = st.selectbox(
            "🔍 Coordinador",
            ["TODOS"] + coordinadores
        )

    if supervisor != "TODOS":
        df = df[
            df["SUPERVISOR"] == supervisor
        ]

    if coordinador != "TODOS":
        df = df[
            df["COORDINADOR"] == coordinador
        ]

    # =========================================
    # SEMANA EDITABLE
    # =========================================

    hoy = datetime.now()

    inicio_semana = hoy - timedelta(days=hoy.weekday())

    dias_editables = []

    for i in range(7):

        dia = inicio_semana + timedelta(days=i)

        if dia <= hoy:

            dias_editables.append(
                f"DIA_{dia.day}"
            )

    st.info(
        "Solo editable semana actual | "
        "A = Asistencia | F = Falta"
    )

    # =========================================
    # GRID
    # =========================================

    gb = GridOptionsBuilder.from_dataframe(df)

    gb.configure_default_column(
        editable=False,
        filter=True,
        sortable=True,
        resizable=True
    )

    columnas_fijas = [
        "SUPERVISOR",
        "COORDINADOR",
        "DEPARTAMENTO",
        "PROVINCIA",
        "DNI",
        "NOMBRE",
        "ESTADO"
    ]

    for col in columnas_fijas:

        gb.configure_column(
            col,
            pinned="left",
            editable=False
        )

    for col in dias_editables:

        if col in df.columns:

            gb.configure_column(
                col,
                editable=True,
                cellEditor="agSelectCellEditor",
                cellEditorParams={
                    "values": ["A", "F"]
                }
            )

    # =========================================
    # COLOR A / F
    # =========================================

    estilo = """
    function(params) {

        if(params.value == 'A') {
            return {
                'backgroundColor': '#b7e4c7',
                'color': '#000',
                'fontWeight': 'bold'
            }
        }

        if(params.value == 'F') {
            return {
                'backgroundColor': '#ffadad',
                'color': '#000',
                'fontWeight': 'bold'
            }
        }

    }
    """

    for col in dias_editables:

        gb.configure_column(
            col,
            cellStyle=estilo
        )

    gridOptions = gb.build()

    respuesta = AgGrid(
        df,
        gridOptions=gridOptions,
        height=600,
        width='100%',
        update_mode=GridUpdateMode.VALUE_CHANGED,
        allow_unsafe_jscode=True,
        fit_columns_on_grid_load=False,
        reload_data=False
    )

    nuevo_df = pd.DataFrame(
        respuesta["data"]
    )

    # =========================================
    # GUARDAR
    # =========================================

    if st.button("💾 Guardar Asistencia"):

        try:

            headers = hoja_asistencia.row_values(1)

            dias_columnas = [
                f"DIA_{i}"
                for i in range(1, 32)
            ]

            progreso = st.progress(0)

            total = len(nuevo_df)

            for idx, fila in nuevo_df.iterrows():

                fila_sheet = idx + 2

                for col in dias_columnas:

                    if col in nuevo_df.columns:

                        valor = fila[col]

                        if pd.isna(valor):
                            valor = ""

                        try:

                            columna_sheet = (
                                headers.index(col) + 1
                            )

                            hoja_asistencia.update_cell(
                                fila_sheet,
                                columna_sheet,
                                valor
                            )

                        except:
                            pass

                progreso.progress(
                    (idx + 1) / total
                )

            st.success(
                "✅ Asistencia guardada correctamente"
            )

            st.cache_data.clear()

        except Exception as e:

            st.error(
                f"Error guardando asistencia: {e}"
            )