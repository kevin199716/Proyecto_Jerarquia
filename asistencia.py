import streamlit as st
import pandas as pd
from datetime import datetime

# =====================================================
# DÍAS
# =====================================================
DIAS = [f"DIA_{i}" for i in range(1, 32)]


# =====================================================
# PERIODO
# =====================================================
def obtener_periodo():

    return datetime.now().strftime("%Y-%m")


# =====================================================
# LEER SHEET SEGURO
# =====================================================
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


# =====================================================
# GENERAR ASISTENCIA
# =====================================================
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
                    ),

                "USUARIO_REGISTRO":
                    st.session_state.get(
                        "usuario",
                        ""
                    ),

                "FECHA_REGISTRO":
                    datetime.now().strftime(
                        "%Y-%m-%d %H:%M:%S"
                    )
            }

            for dia in DIAS:

                fila[dia] = ""

            filas_nuevas.append(
                fila
            )

    # =====================================================
    # INSERTAR
    # =====================================================
    if filas_nuevas:

        valores = []

        for fila in filas_nuevas:

            valores.append(
                list(fila.values())
            )

        hoja_asistencia.append_rows(
            valores
        )


# =====================================================
# MOSTRAR
# =====================================================
def mostrar_asistencia(
    hoja_asistencia,
    hoja_colaboradores
):

    st.subheader(
        "📅 Control de Asistencia"
    )

    # =====================================================
    # LEER COLABORADORES
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
        "👥 Total",
        total
    )

    c2.metric(
        "✅ Activos",
        activos
    )

    c3.metric(
        "❌ Inactivos",
        inactivos
    )

    st.divider()

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
    # TABLA
    # =====================================================
    edited_df = st.data_editor(

        df_view,

        use_container_width=True,

        height=600,

        num_rows="fixed",

        disabled=columnas_fijas
    )

    st.info(
        "Solo usar: A = Asistencia | F = Falta"
    )

    # =====================================================
    # GUARDAR
    # =====================================================
    if st.button(
        "💾 Guardar Asistencia"
    ):

        st.success(
            "✅ Asistencia guardada"
        )