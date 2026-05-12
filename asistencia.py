import streamlit as st
import pandas as pd
from datetime import datetime
import calendar

# =========================================
# CONFIG
# =========================================
DIAS = [f"DIA_{i}" for i in range(1, 32)]


# =========================================
# PERIODO ACTUAL
# =========================================
def obtener_periodo():

    return datetime.now().strftime("%Y-%m")


# =========================================
# LEER ASISTENCIA
# =========================================
def leer_asistencia(hoja_asistencia):

    try:

        values = hoja_asistencia.get_all_values()

        if not values:
            return pd.DataFrame()

        headers = values[0]

        data = values[1:]

        if not headers:
            return pd.DataFrame()

        df = pd.DataFrame(
            data,
            columns=headers
        )

        return df

    except Exception as e:

        st.error(
            f"Error leyendo asistencia: {e}"
        )

        return pd.DataFrame()


# =========================================
# GENERAR MES
# =========================================
def generar_asistencia_mes(
    hoja_asistencia,
    df_colab
):

    periodo = obtener_periodo()

    df_asistencia = leer_asistencia(
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

            # =========================
            # DÍAS VACÍOS
            # =========================
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
        row.get(
            "FECHA_DE_CESE",
            ""
        )
    ).strip()

    bloqueados = []

    if (
        estado == "INACTIVO"
        and fecha_cese
    ):

        try:

            fecha = pd.to_datetime(
                fecha_cese
            )

            dia_cese = fecha.day

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
# ESTILOS
# =========================================
def colorear_asistencia(val):

    val = str(val).upper()

    if val == "A":

        return "background-color:#d4edda;color:black"

    elif val == "F":

        return "background-color:#f8d7da;color:black"

    return ""


# =========================================
# MOSTRAR
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
    df = leer_asistencia(
        hoja_asistencia
    )

    if df.empty:

        st.warning(
            "No hay registros"
        )

        return

    periodo = obtener_periodo()

    df = df[
        df["PERIODO"] == periodo
    ]

    # =========================================
    # MÉTRICAS
    # =========================================
    total = len(df)

    activos = len(
        df[
            df["ESTADO"]
            == "ACTIVO"
        ]
    )

    inactivos = len(
        df[
            df["ESTADO"]
            == "INACTIVO"
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

    # =========================================
    # FILTROS
    # =========================================
    f1, f2, f3 = st.columns(3)

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

    provincias = sorted(
        df["PROVINCIA"]
        .dropna()
        .unique()
    )

    supervisor_sel = f1.selectbox(
        "Supervisor",
        ["TODOS"] + list(supervisores)
    )

    coordinador_sel = f2.selectbox(
        "Coordinador",
        ["TODOS"] + list(coordinadores)
    )

    provincia_sel = f3.selectbox(
        "Provincia",
        ["TODOS"] + list(provincias)
    )

    # =========================================
    # FILTROS
    # =========================================
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

    if provincia_sel != "TODOS":

        df = df[
            df["PROVINCIA"]
            == provincia_sel
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
        columnas_fijas
        + DIAS
    )

    df_view = df[
        columnas
    ].copy()

    # =========================================
    # TABLA
    # =========================================
    edited_df = st.data_editor(

        df_view,

        use_container_width=True,

        height=600,

        num_rows="fixed",

        disabled=columnas_fijas
    )

    # =========================================
    # GUARDAR
    # =========================================
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
            "✅ Asistencia guardada correctamente"
        )