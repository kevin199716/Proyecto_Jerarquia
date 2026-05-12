# =========================================================
# asistencia.py
# VERSION PRO - OPTIMIZADA
# =========================================================

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

from st_aggrid import (
    AgGrid,
    GridOptionsBuilder,
    GridUpdateMode,
    JsCode
)

# =========================================================
# CONFIG
# =========================================================

DIAS = [f"DIA_{i}" for i in range(1, 32)]

# =========================================================
# PERIODO
# =========================================================

def obtener_periodo():

    return datetime.now().strftime("%Y-%m")

# =========================================================
# LEER HOJA
# =========================================================

def leer_sheet_seguro(hoja):

    try:

        valores = hoja.get_all_values()

        if not valores:
            return pd.DataFrame()

        headers = valores[0]

        data = valores[1:]

        if len(headers) == 0:
            return pd.DataFrame()

        df = pd.DataFrame(
            data,
            columns=headers
        )

        return df

    except Exception as e:

        st.error(
            f"Error leyendo hoja: {e}"
        )

        return pd.DataFrame()

# =========================================================
# GENERAR MES
# =========================================================

def generar_asistencia_mes(
    hoja_asistencia,
    df_colab
):

    periodo = obtener_periodo()

    df_asistencia = leer_sheet_seguro(
        hoja_asistencia
    )

    filas_nuevas = []

    for _, row in df_colab.iterrows():

        dni = str(
            row.get("DNI", "")
        ).strip()

        if not dni:
            continue

        existe = False

        if not df_asistencia.empty:

            if "DNI" in df_asistencia.columns:

                df_asistencia["DNI"] = (
                    df_asistencia["DNI"]
                    .astype(str)
                )

                existe = (

                    (
                        df_asistencia["PERIODO"]
                        == periodo
                    )

                    &

                    (
                        df_asistencia["DNI"]
                        == dni
                    )

                ).any()

        if not existe:

            fila = {

                "PERIODO":
                    periodo,

                "DNI":
                    dni,

                "NOMBRE":
                    f"{row.get('NOMBRES','')} "
                    f"{row.get('APELLIDO PATERNO','')} "
                    f"{row.get('APELLIDO MATERNO','')}",

                "SUPERVISOR":
                    row.get(
                        "SUPERVISOR A CARGO",
                        ""
                    ),

                "COORDINADOR":
                    row.get(
                        "COORDINADOR",
                        ""
                    ),

                "DEPARTAMENTO":
                    row.get(
                        "DEPARTAMENTO",
                        ""
                    ),

                "PROVINCIA":
                    row.get(
                        "PROVINCIA",
                        ""
                    ),

                "ESTADO":
                    row.get(
                        "ESTADO",
                        ""
                    ),

                "FECHA_CREACION_USUARIO":
                    row.get(
                        "FECHA DE CREACION USUARIO",
                        ""
                    ),

                "FECHA_DE_CESE":
                    row.get(
                        "FECHA DE CESE",
                        ""
                    )
            }

            for dia in DIAS:

                fila[dia] = ""

            filas_nuevas.append(
                fila
            )

    if filas_nuevas:

        valores = []

        for fila in filas_nuevas:

            valores.append(
                list(fila.values())
            )

        hoja_asistencia.append_rows(
            valores
        )

# =========================================================
# SEMANA EDITABLE
# =========================================================

def dias_editables():

    hoy = datetime.now()

    inicio_semana = hoy - timedelta(
        days=hoy.weekday()
    )

    editable = []

    for i in range(7):

        dia = inicio_semana + timedelta(days=i)

        editable.append(
            f"DIA_{dia.day}"
        )

    return editable

# =========================================================
# MOSTRAR
# =========================================================

def mostrar_asistencia(
    hoja_asistencia,
    hoja_colaboradores
):

    # =====================================================
    # ESTILOS
    # =====================================================

    st.markdown("""

    <style>

    .main {
        background-color:#f7f9fc;
    }

    .block-container {
        padding-top:1rem;
    }

    div[data-testid="stMetric"] {

        background:white;

        padding:15px;

        border-radius:14px;

        box-shadow:0 2px 10px rgba(0,0,0,0.05);

        border-left:6px solid #6c5ce7;
    }

    </style>

    """, unsafe_allow_html=True)

    st.subheader(
        "📅 Control de Asistencia"
    )

    # =====================================================
    # COLABORADORES
    # =====================================================

    data_colab = (
        hoja_colaboradores
        .get_all_records()
    )

    df_colab = pd.DataFrame(
        data_colab
    )

    if df_colab.empty:

        st.warning(
            "No hay colaboradores"
        )

        return

    df_colab.columns = (
        df_colab.columns
        .str.strip()
        .str.upper()
    )

    # =====================================================
    # GENERAR MES
    # =====================================================

    generar_asistencia_mes(
        hoja_asistencia,
        df_colab
    )

    # =====================================================
    # LEER ASISTENCIA
    # =====================================================

    df = leer_sheet_seguro(
        hoja_asistencia
    )

    if df.empty:

        st.warning(
            "No hay asistencia"
        )

        return

    periodo = obtener_periodo()

    df = df[
        df["PERIODO"] == periodo
    ]

    # =====================================================
    # KPIS
    # =====================================================

    total = len(df)

    activos = len(
        df[
            df["ESTADO"] == "ACTIVO"
        ]
    )

    inactivos = len(
        df[
            df["ESTADO"] == "INACTIVO"
        ]
    )

    c1, c2, c3 = st.columns(3)

    c1.metric(
        "👥 HC TOTAL",
        total
    )

    c2.metric(
        "✅ ACTIVOS",
        activos
    )

    c3.metric(
        "❌ INACTIVOS",
        inactivos
    )

    st.divider()

    # =====================================================
    # FILTROS
    # =====================================================

    f1, f2 = st.columns(2)

    supervisores = sorted(
        df["SUPERVISOR"]
        .dropna()
        .unique()
    )

    coordinadores = sorted(
        df["COORDINADOR"]
        .dropna()
        .unique()
    )

    supervisor_sel = f1.selectbox(
        "🔍 Supervisor",
        ["TODOS"] + list(supervisores)
    )

    coordinador_sel = f2.selectbox(
        "🔍 Coordinador",
        ["TODOS"] + list(coordinadores)
    )

    if supervisor_sel != "TODOS":

        df = df[
            df["SUPERVISOR"]
            == supervisor_sel
        ]

    if coordinador_sel != "TODOS":

        df = df[
            df["COORDINADOR"]
            == coordinador_sel
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

    columnas = (
        columnas_fijas
        + DIAS
    )

    columnas_existentes = [

        c for c in columnas

        if c in df.columns
    ]

    df_view = df[
        columnas_existentes
    ].copy()

    # =====================================================
    # LIMPIAR NULOS
    # =====================================================

    df_view = df_view.fillna("")

    # =====================================================
    # DIAS EDITABLES
    # =====================================================

    editable = dias_editables()

    # =====================================================
    # AGGRID
    # =====================================================

    gb = GridOptionsBuilder.from_dataframe(
        df_view
    )

    # =====================================================
    # DEFAULT COLUMN
    # =====================================================

    gb.configure_default_column(

        sortable=True,

        filter=True,

        resizable=True
    )

    # =====================================================
    # COLUMNAS FIJAS
    # =====================================================

    for col in columnas_fijas:

        gb.configure_column(

            col,

            pinned="left",

            editable=False,

            cellStyle={
                "backgroundColor":"#f1f2f6",
                "fontWeight":"bold"
            }
        )

    # =====================================================
    # DÍAS
    # =====================================================

    for dia in DIAS:

        if dia in df_view.columns:

            gb.configure_column(

                dia,

                editable=dia in editable,

                width=75,

                cellEditor="agSelectCellEditor",

                cellEditorParams={
                    "values":[
                        "",
                        "A",
                        "F"
                    ]
                },

                cellStyle=JsCode("""

                function(params) {

                    if (params.value == 'A') {

                        return {
                            'backgroundColor':'#2ecc71',
                            'color':'white',
                            'fontWeight':'bold'
                        }
                    }

                    if (params.value == 'F') {

                        return {
                            'backgroundColor':'#e74c3c',
                            'color':'white',
                            'fontWeight':'bold'
                        }
                    }

                    return {
                        'backgroundColor':'white'
                    }
                }

                """)
            )

    # =====================================================
    # GRID OPTIONS
    # =====================================================

    gb.configure_grid_options(

        rowHeight=38,

        headerHeight=42,

        domLayout='autoHeight'
    )

    gridOptions = gb.build()

    st.info(
        "Solo editable semana actual | A = Asistencia | F = Falta"
    )

    # =====================================================
    # TABLA
    # =====================================================

    response = AgGrid(

        df_view,

        gridOptions=gridOptions,

        update_mode=GridUpdateMode.MANUAL,

        data_return_mode="AS_INPUT",

        fit_columns_on_grid_load=False,

        allow_unsafe_jscode=True,

        enable_enterprise_modules=False,

        reload_data=False,

        height=650,

        theme="balham"
    )

    edited_df = response["data"]

    # =====================================================
    # GUARDAR
    # =====================================================

    if st.button(
        "💾 Guardar Asistencia"
    ):

        registros = (
            hoja_asistencia
            .get_all_records()
        )

        df_original = pd.DataFrame(
            registros
        )

        batch_updates = []

        for idx, row in edited_df.iterrows():

            dni = str(
                row["DNI"]
            ).strip()

            fila_sheet = df_original[

                (
                    df_original["DNI"]
                    .astype(str)
                    == dni
                )

                &

                (
                    df_original["PERIODO"]
                    == periodo
                )
            ]

            if fila_sheet.empty:
                continue

            row_index = (
                fila_sheet.index[0]
                + 2
            )

            for dia in editable:

                if dia not in row:
                    continue

                valor = str(
                    row[dia]
                ).upper().strip()

                if valor not in [
                    "",
                    "A",
                    "F"
                ]:
                    continue

                col_index = (
                    df_original.columns
                    .get_loc(dia)
                    + 1
                )

                batch_updates.append({

                    "range":
                        f"{chr(64+col_index)}{row_index}",

                    "values":
                        [[valor]]
                })

        if batch_updates:

            hoja_asistencia.batch_update(
                batch_updates
            )

        st.success(
            "✅ Asistencia guardada correctamente"
        )