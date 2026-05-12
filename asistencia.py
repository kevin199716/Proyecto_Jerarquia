# asistencia.py

import streamlit as st
import pandas as pd
from datetime import datetime
import calendar
import pytz

# =====================================================
# CACHE
# =====================================================

@st.cache_data(ttl=60)
def cargar_colaboradores_cache(_hoja):

    data = _hoja.get_all_records()

    df = pd.DataFrame(data)

    df.columns = df.columns.str.strip().str.upper()

    return df


@st.cache_data(ttl=60)
def cargar_asistencia_cache(_hoja):

    try:

        data = _hoja.get_all_records()

        if not data:
            return pd.DataFrame()

        df = pd.DataFrame(data)

        df.columns = df.columns.str.strip().str.upper()

        return df

    except:
        return pd.DataFrame()


# =====================================================
# HORA PERU
# =====================================================

zona_peru = pytz.timezone("America/Lima")


def ahora_peru():
    return datetime.now(zona_peru)


# =====================================================
# GENERAR ASISTENCIA DEL MES
# =====================================================

def generar_asistencia_mes(
    hoja_asistencia,
    df_colab
):

    hoy = ahora_peru()

    periodo = hoy.strftime("%Y-%m")

    registros = cargar_asistencia_cache(
        hoja_asistencia
    )

    if not registros.empty:

        if "PERIODO" in registros.columns:

            existe = registros[
                registros["PERIODO"] == periodo
            ]

            if len(existe) > 0:
                return

    dias_mes = calendar.monthrange(
        hoy.year,
        hoy.month
    )[1]

    columnas = [
        "PERIODO",
        "DNI",
        "NOMBRE",
        "SUPERVISOR",
        "COORDINADOR",
        "DEPARTAMENTO",
        "PROVINCIA",
        "ESTADO",
        "FECHA_CREACION_USUARIO",
        "FECHA_DE_CESE"
    ]

    for dia in range(1, dias_mes + 1):

        columnas.append(
            f"DIA_{dia}"
        )

    columnas.extend([
        "USUARIO_REGISTRO",
        "FECHA_REGISTRO"
    ])

    valores = []

    for _, row in df_colab.iterrows():

        fila = [

            periodo,

            str(
                row.get("DNI", "")
            ),

            f"{row.get('NOMBRES','')} "
            f"{row.get('APELLIDO PATERNO','')} "
            f"{row.get('APELLIDO MATERNO','')}",

            row.get(
                "SUPERVISOR A CARGO",
                ""
            ),

            row.get(
                "COORDINADOR",
                ""
            ),

            row.get(
                "DEPARTAMENTO",
                ""
            ),

            row.get(
                "PROVINCIA",
                ""
            ),

            row.get(
                "ESTADO",
                ""
            ),

            row.get(
                "FECHA DE CREACION USUARIO",
                ""
            ),

            row.get(
                "FECHA DE CESE",
                ""
            )
        ]

        for _ in range(dias_mes):

            fila.append("")

        fila.extend([

            st.session_state.get(
                "usuario",
                ""
            ),

            ahora_peru().strftime(
                "%Y-%m-%d %H:%M:%S"
            )

        ])

        valores.append(fila)

    if len(
        hoja_asistencia.get_all_values()
    ) == 0:

        hoja_asistencia.append_row(
            columnas
        )

    if valores:

        hoja_asistencia.append_rows(
            valores
        )


# =====================================================
# MOSTRAR ASISTENCIA
# =====================================================

def mostrar_asistencia(
    hoja_asistencia,
    hoja_colaboradores
):

    st.markdown("""
    <style>

    .stDataFrame {
        border-radius: 12px;
        border: 1px solid #EAEAEA;
    }

    </style>
    """, unsafe_allow_html=True)

    st.markdown(
        "## 🗓️ Control de Asistencia"
    )

    # =================================================
    # CARGA RAPIDA
    # =================================================

    df_colab = cargar_colaboradores_cache(
        hoja_colaboradores
    )

    generar_asistencia_mes(
        hoja_asistencia,
        df_colab
    )

    df = cargar_asistencia_cache(
        hoja_asistencia
    )

    if df.empty:

        st.warning("Sin datos")
        return

    # =================================================
    # KPIS
    # =================================================

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

    # =================================================
    # FILTROS
    # =================================================

    col1, col2 = st.columns(2)

    supervisores = (
        ["TODOS"] +
        sorted(
            df["SUPERVISOR"]
            .dropna()
            .astype(str)
            .unique()
        )
    )

    coordinadores = (
        ["TODOS"] +
        sorted(
            df["COORDINADOR"]
            .dropna()
            .astype(str)
            .unique()
        )
    )

    with col1:

        filtro_supervisor = st.selectbox(
            "🔍 Supervisor",
            supervisores
        )

    with col2:

        filtro_coord = st.selectbox(
            "🔍 Coordinador",
            coordinadores
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
    # SEMANA EDITABLE
    # =================================================

    hoy = ahora_peru()

    dia_actual = hoy.day

    inicio_semana = (
        dia_actual - hoy.weekday()
    )

    columnas_editables = []

    for i in range(
        inicio_semana,
        dia_actual + 1
    ):

        if i > 0:

            columnas_editables.append(
                f"DIA_{i}"
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

    columnas_mostrar = (
        columnas_base +
        columnas_editables
    )

    df_view = df[
        columnas_mostrar
    ].copy()

    # =================================================
    # BLOQUEAR INACTIVOS
    # =================================================

    for col in columnas_editables:

        df_view.loc[
            df_view["ESTADO"]
            == "INACTIVO",
            col
        ] = ""

    # =================================================
    # INFO
    # =================================================

    st.info(
        "Solo editable semana actual "
        "| A = Asistencia "
        "| F = Falta"
    )

    # =================================================
    # CONFIG COLUMNAS
    # =================================================

    config = {}

    for col in columnas_editables:

        config[col] = st.column_config.SelectboxColumn(
            col,
            options=[
                "",
                "A",
                "F"
            ],
            width="small"
        )

    # =================================================
    # TABLA
    # =================================================

    edited_df = st.data_editor(

        df_view,

        use_container_width=True,

        hide_index=True,

        height=550,

        disabled=[

            "SUPERVISOR",
            "COORDINADOR",
            "DEPARTAMENTO",
            "PROVINCIA",
            "DNI",
            "NOMBRE",
            "ESTADO"
        ],

        column_config=config
    )

    # =================================================
    # GUARDAR
    # =================================================

    if st.button(
        "💾 Guardar Asistencia"
    ):

        registros = (
            hoja_asistencia
            .get_all_records()
        )

        df_real = pd.DataFrame(
            registros
        )

        for _, row in edited_df.iterrows():

            dni = str(
                row["DNI"]
            )

            mask = (
                df_real["DNI"]
                .astype(str)
                == dni
            )

            index_real = (
                df_real[mask]
                .index
            )

            if len(index_real) == 0:
                continue

            fila_sheet = (
                int(index_real[0]) + 2
            )

            for col in columnas_editables:

                valor = row[col]

                col_sheet = (
                    df_real.columns
                    .get_loc(col)
                    + 1
                )

                hoja_asistencia.update_cell(
                    fila_sheet,
                    col_sheet,
                    valor
                )

        cargar_asistencia_cache.clear()

        st.success(
            "✅ Asistencia guardada correctamente"
        )

        st.rerun()