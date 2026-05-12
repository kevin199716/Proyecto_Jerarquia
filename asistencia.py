# =========================================================
# ASISTENCIA.PY
# VERSION OPTIMIZADA FINAL
# =========================================================

import streamlit as st
import pandas as pd
import calendar
from datetime import datetime, timedelta

# =========================================================
# CACHE COLABORADORES
# =========================================================

@st.cache_data(ttl=300)
def cargar_colaboradores_cache(data):

    df = pd.DataFrame(data)

    df.columns = df.columns.str.strip().str.upper()

    return df


# =========================================================
# GENERAR COLUMNAS MES
# =========================================================

def obtener_columnas_mes():

    hoy = datetime.now()

    dias_mes = calendar.monthrange(
        hoy.year,
        hoy.month
    )[1]

    columnas = []

    for i in range(1, dias_mes + 1):

        columnas.append(f"DIA_{i}")

    return columnas


# =========================================================
# SEMANA ACTUAL
# =========================================================

def obtener_semana_actual():

    hoy = datetime.now()

    inicio_semana = hoy - timedelta(days=hoy.weekday())

    fin_semana = inicio_semana + timedelta(days=6)

    dias_editables = []

    for i in range(7):

        dia = inicio_semana + timedelta(days=i)

        if dia.month == hoy.month:

            dias_editables.append(
                f"DIA_{dia.day}"
            )

    return dias_editables


# =========================================================
# GENERAR ASISTENCIA
# =========================================================

def generar_asistencia_mes(
    hoja_asistencia,
    df_colab
):

    valores = hoja_asistencia.get_all_values()

    if len(valores) <= 1:

        hoy = datetime.now()

        periodo = hoy.strftime("%Y-%m")

        columnas_mes = obtener_columnas_mes()

        registros = []

        for _, row in df_colab.iterrows():

            fila = {
                "PERIODO": periodo,
                "DNI": str(
                    row.get("DNI", "")
                ),
                "NOMBRE": f"""
{row.get('NOMBRES', '')}
{row.get('APELLIDO PATERNO', '')}
{row.get('APELLIDO MATERNO', '')}
""".replace("\n", " ").strip(),

                "SUPERVISOR": row.get(
                    "SUPERVISOR A CARGO",
                    ""
                ),

                "COORDINADOR": row.get(
                    "COORDINADOR",
                    ""
                ),

                "DEPARTAMENTO": row.get(
                    "DEPARTAMENTO",
                    ""
                ),

                "PROVINCIA": row.get(
                    "PROVINCIA",
                    ""
                ),

                "ESTADO": row.get(
                    "ESTADO",
                    ""
                )
            }

            for col in columnas_mes:

                fila[col] = ""

            registros.append(fila)

        df_asistencia = pd.DataFrame(registros)

        hoja_asistencia.clear()

        hoja_asistencia.update(
            [
                df_asistencia.columns.values.tolist()
            ] +
            df_asistencia.values.tolist()
        )


# =========================================================
# MAIN
# =========================================================

def mostrar_asistencia(
    hoja_asistencia,
    hoja_colaboradores
):

    st.markdown("""
    <style>

    .stDataFrame {
        border-radius: 12px;
    }

    div[data-baseweb="select"] {
        background-color: white;
    }

    </style>
    """, unsafe_allow_html=True)

    # =====================================================
    # DATA
    # =====================================================

    data_colab = hoja_colaboradores.get_all_records()

    df_colab = cargar_colaboradores_cache(
        data_colab
    )

    generar_asistencia_mes(
        hoja_asistencia,
        df_colab
    )

    data_asistencia = hoja_asistencia.get_all_records()

    df = pd.DataFrame(data_asistencia)

    if df.empty:

        st.warning("Sin registros")

        return

    # =====================================================
    # KPIS
    # =====================================================

    activos = len(
        df[df["ESTADO"] == "ACTIVO"]
    )

    inactivos = len(
        df[df["ESTADO"] != "ACTIVO"]
    )

    total = len(df)

    st.markdown("## 🗓️ Control de Asistencia")

    c1, c2, c3 = st.columns(3)

    with c1:
        st.metric(
            "👥 HC TOTAL",
            total
        )

    with c2:
        st.metric(
            "✅ ACTIVOS",
            activos
        )

    with c3:
        st.metric(
            "❌ INACTIVOS",
            inactivos
        )

    st.divider()

    # =====================================================
    # FILTROS
    # =====================================================

    colf1, colf2 = st.columns(2)

    supervisores = sorted(
        df["SUPERVISOR"]
        .fillna("")
        .unique()
        .tolist()
    )

    coordinadores = sorted(
        df["COORDINADOR"]
        .fillna("")
        .unique()
        .tolist()
    )

    with colf1:

        filtro_supervisor = st.selectbox(
            "🔍 Supervisor",
            ["TODOS"] + supervisores
        )

    with colf2:

        filtro_coord = st.selectbox(
            "🔍 Coordinador",
            ["TODOS"] + coordinadores
        )

    # =====================================================
    # FILTROS DATA
    # =====================================================

    if filtro_supervisor != "TODOS":

        df = df[
            df["SUPERVISOR"] ==
            filtro_supervisor
        ]

    if filtro_coord != "TODOS":

        df = df[
            df["COORDINADOR"] ==
            filtro_coord
        ]

    # =====================================================
    # COLUMNAS
    # =====================================================

    columnas_base = [

        "SUPERVISOR",
        "COORDINADOR",
        "DEPARTAMENTO",
        "PROVINCIA",
        "DNI",
        "NOMBRE",
        "ESTADO"
    ]

    columnas_mes = obtener_columnas_mes()

    columnas_editables = (
        obtener_semana_actual()
    )

    columnas_mostrar = (
        columnas_base +
        columnas_mes
    )

    # =====================================================
    # CONFIG
    # =====================================================

    config = {}

    for col in columnas_mes:

        editable = (
            col in columnas_editables
        )

        config[col] = st.column_config.SelectboxColumn(

            label=col,

            options=[
                "",
                "A",
                "F"
            ],

            width="small",

            disabled=not editable
        )

    st.info(
        "Solo editable semana actual "
        "| A = Asistencia | "
        "F = Falta"
    )

    # =====================================================
    # DATA EDITOR
    # =====================================================

    edited_df = st.data_editor(

        df[columnas_mostrar],

        use_container_width=True,

        hide_index=True,

        num_rows="fixed",

        column_config=config,

        disabled=[
            "SUPERVISOR",
            "COORDINADOR",
            "DEPARTAMENTO",
            "PROVINCIA",
            "DNI",
            "NOMBRE",
            "ESTADO"
        ],

        key="asistencia_editor"
    )

    # =====================================================
    # SAVE
    # =====================================================

    if st.button(
        "💾 Guardar Asistencia",
        use_container_width=False
    ):

        hoja_asistencia.clear()

        hoja_asistencia.update(
            [
                edited_df.columns
                .tolist()
            ] +
            edited_df.values.tolist()
        )

        st.success(
            "✅ Asistencia guardada"
        )