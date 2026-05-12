import streamlit as st
import pandas as pd
from datetime import datetime

# =========================================
# COLUMNAS DÍAS
# =========================================
DIAS = [f"DIA_{i}" for i in range(1, 32)]


# =========================================
# PERIODO ACTUAL
# =========================================
def obtener_periodo():

    return datetime.now().strftime("%Y-%m")


# =========================================
# GENERAR ASISTENCIA
# =========================================
def generar_asistencia_mes(
    hoja_asistencia,
    df_colab
):

    periodo = obtener_periodo()

    registros = hoja_asistencia.get_all_records()

    df_asistencia = pd.DataFrame(registros)

    filas_nuevas = []

    for _, row in df_colab.iterrows():

        dni = str(row["DNI"]).strip()

        existe = False

        if not df_asistencia.empty:

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
                    f"{row['NOMBRES']} {row['APELLIDO PATERNO']} {row['APELLIDO MATERNO']}",

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

            filas_nuevas.append(fila)

    # =========================================
    # INSERTAR
    # =========================================
    if filas_nuevas:

        valores = []

        for fila in filas_nuevas:

            valores.append(
                list(fila.values())
            )

        hoja_asistencia.append_rows(
            valores
        )


# =========================================
# BLOQUEAR DÍAS
# =========================================
def bloquear_dias(row):

    estado = str(
        row.get("ESTADO", "")
    ).upper()

    fecha_cese = str(
        row.get("FECHA_DE_CESE", "")
    ).strip()

    bloqueados = []

    if (
        estado == "INACTIVO"
        and fecha_cese
    ):

        try:

            dia_cese = int(
                fecha_cese.split("-")[2]
            )

            for d in range(
                dia_cese + 1,
                32
            ):

                bloqueados.append(
                    f"DIA_{d}"
                )

        except:
            pass

    return bloqueados


# =========================================
# MOSTRAR ASISTENCIA
# =========================================
def mostrar_asistencia(
    hoja_asistencia,
    hoja_colaboradores
):

    st.subheader(
        "📅 Control de Asistencia"
    )

    # =========================================
    # LEER COLABORADORES
    # =========================================
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

    # =========================================
    # GENERAR MES
    # =========================================
    generar_asistencia_mes(
        hoja_asistencia,
        df_colab
    )

    # =========================================
    # LEER ASISTENCIA
    # =========================================
    registros = (
        hoja_asistencia
        .get_all_records()
    )

    df = pd.DataFrame(
        registros
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

    # =========================================
    # COLUMNAS
    # =========================================
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
        columnas_fijas + DIAS
    )

    df_view = df[
        columnas
    ].copy()

    # =========================================
    # EDITOR
    # =========================================
    edited_df = st.data_editor(

        df_view,

        use_container_width=True,

        num_rows="fixed",

        disabled=columnas_fijas
    )

    # =========================================
    # GUARDAR
    # =========================================
    if st.button(
        "💾 Guardar Asistencia"
    ):

        df_original = pd.DataFrame(
            registros
        )

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

            dias_bloqueados = (
                bloquear_dias(row)
            )

            for dia in DIAS:

                if dia in dias_bloqueados:
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

                hoja_asistencia.update_cell(
                    row_index,
                    col_index,
                    valor
                )

        st.success(
            "✅ Asistencia guardada"
        )