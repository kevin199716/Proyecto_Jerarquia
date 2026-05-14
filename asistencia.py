# =====================================================
# asistencia.py
# VERSION FINAL ESTABLE
# =====================================================

import streamlit as st
import pandas as pd
from datetime import datetime

# =====================================================
# COLUMNAS
# =====================================================

COLUMNAS_DIAS = [
    f"DIA_{i}" for i in range(1, 32)
]

COLUMNAS_BASE = [
    "PERIODO",
    "MES",
    "SUPERVISOR",
    "COORDINADOR",
    "DEPARTAMENTO",
    "PROVINCIA",
    "DNI",
    "NOMBRE",
    "ESTADO"
]

COLUMNAS_FINAL = (
    COLUMNAS_BASE +
    COLUMNAS_DIAS
)

# =====================================================
# CACHE DRIVE
# =====================================================

@st.cache_data(ttl=60)
def leer_drive(_worksheet):

    valores = _worksheet.get_all_values()

    if not valores:

        return pd.DataFrame(
            columns=COLUMNAS_FINAL
        )

    headers = valores[0]

    filas = valores[1:]

    filas_ok = []

    for fila in filas:

        fila = fila + (
            [""] * (
                len(headers) - len(fila)
            )
        )

        filas_ok.append(
            fila[:len(headers)]
        )

    df = pd.DataFrame(
        filas_ok,
        columns=headers
    )

    # =================================================
    # COLUMNAS FALTANTES
    # =================================================

    for col in COLUMNAS_FINAL:

        if col not in df.columns:
            df[col] = ""

    df = df[COLUMNAS_FINAL]

    df = df.fillna("").astype(str)

    return df

# =====================================================
# CREAR FILA
# =====================================================

def crear_fila(row):

    hoy = datetime.now()

    fila = {

        "PERIODO": hoy.strftime("%Y-%m"),

        "MES": hoy.strftime("%m"),

        "SUPERVISOR": str(
            row.get(
                "SUPERVISOR A CARGO",
                ""
            )
        ).strip(),

        "COORDINADOR": str(
            row.get(
                "COORDINADOR",
                ""
            )
        ).strip(),

        "DEPARTAMENTO": str(
            row.get(
                "DEPARTAMENTO",
                ""
            )
        ).strip(),

        "PROVINCIA": str(
            row.get(
                "PROVINCIA",
                ""
            )
        ).strip(),

        "DNI": str(
            row.get(
                "DNI",
                ""
            )
        ).strip(),

        "NOMBRE": str(
            row.get(
                "NOMBRES",
                ""
            )
        ).strip(),

        "ESTADO": str(
            row.get(
                "ESTADO",
                ""
            )
        ).strip()
    }

    for d in COLUMNAS_DIAS:
        fila[d] = ""

    return fila

# =====================================================
# PREPARAR DATA
# =====================================================

def preparar_data(
    hoja_asistencia,
    hoja_colaboradores
):

    hoy = datetime.now()

    periodo_actual = hoy.strftime("%Y-%m")

    # =================================================
    # DRIVE
    # =================================================

    df_drive = leer_drive(
        hoja_asistencia
    )

    # =================================================
    # COLABORADORES
    # =================================================

    df_colab = pd.DataFrame(
        hoja_colaboradores.get_all_records()
    ).fillna("")

    if not df_colab.empty:

        df_colab.columns = (
            df_colab.columns
            .str.strip()
            .str.upper()
        )

    # =================================================
    # SOLO MES ACTUAL
    # =================================================

    df_mes = df_drive[
        df_drive["PERIODO"].astype(str)
        == periodo_actual
    ].copy()

    # =================================================
    # SI NO EXISTE
    # =================================================

    if df_mes.empty:

        registros = []

        for _, row in df_colab.iterrows():

            registros.append(
                crear_fila(row)
            )

        df_mes = pd.DataFrame(
            registros
        )

    else:

        # =============================================
        # SOLO DNI
        # =============================================

        claves = set(
            df_mes["DNI"]
            .astype(str)
            .tolist()
        )

        nuevos = []

        for _, row in df_colab.iterrows():

            dni = str(
                row.get("DNI", "")
            ).strip()

            if dni == "":
                continue

            # =========================================
            # SOLO DNI
            # =========================================

            clave = dni

            if clave not in claves:

                nuevos.append(
                    crear_fila(row)
                )

                claves.add(clave)

        # =============================================
        # NUEVOS
        # =============================================

        if nuevos:

            df_mes = pd.concat(
                [
                    df_mes,
                    pd.DataFrame(nuevos)
                ],
                ignore_index=True
            )

    # =================================================
    # ELIMINAR DUPLICADOS
    # =================================================

    df_mes = df_mes.drop_duplicates(
        subset=["PERIODO", "DNI"],
        keep="first"
    )

    df_mes = df_mes.fillna("")

    return (
        df_drive.fillna(""),
        df_mes.fillna("")
    )

# =====================================================
# MAIN
# =====================================================

def mostrar_asistencia(
    hoja_asistencia,
    hoja_colaboradores
):

    st.subheader(
        "🗓️ Control de Asistencia"
    )

    # =================================================
    # SESSION
    # =================================================

    if "df_asistencia" not in st.session_state:

        df_drive, df_mes = preparar_data(
            hoja_asistencia,
            hoja_colaboradores
        )

        st.session_state[
            "df_asistencia_drive"
        ] = df_drive

        st.session_state[
            "df_asistencia"
        ] = df_mes

    # =================================================
    # DATA
    # =================================================

    df_drive = st.session_state[
        "df_asistencia_drive"
    ]

    df_mes = st.session_state[
        "df_asistencia"
    ]

    # =================================================
    # FILTROS
    # =================================================

    col1, col2 = st.columns(2)

    with col1:

        supervisores = ["TODOS"]

        if "SUPERVISOR" in df_mes.columns:

            supervisores += sorted(
                df_mes["SUPERVISOR"]
                .astype(str)
                .unique()
                .tolist()
            )

        filtro_sup = st.selectbox(
            "🔎 Supervisor",
            supervisores
        )

    with col2:

        coordinadores = ["TODOS"]

        if "COORDINADOR" in df_mes.columns:

            coordinadores += sorted(
                df_mes["COORDINADOR"]
                .astype(str)
                .unique()
                .tolist()
            )

        filtro_coord = st.selectbox(
            "🔎 Coordinador",
            coordinadores
        )

    # =================================================
    # FILTRO
    # =================================================

    df = df_mes.copy()

    if filtro_sup != "TODOS":

        df = df[
            df["SUPERVISOR"]
            == filtro_sup
        ]

    if filtro_coord != "TODOS":

        df = df[
            df["COORDINADOR"]
            == filtro_coord
        ]

    # =================================================
    # COLUMNAS
    # =================================================

    columnas_visibles = [

        "PROVINCIA",
        "DNI",
        "NOMBRE",
        "ESTADO"

    ] + COLUMNAS_DIAS

    # =================================================
    # SOLO DIA ACTUAL
    # =================================================

    dia_actual = datetime.now().day

    columnas_editables = [
        f"DIA_{dia_actual}"
    ]

    # =================================================
    # CONFIG
    # =================================================

    config = {}

    for col in columnas_visibles:

        if col.startswith("DIA_"):

            editable = (
                col in columnas_editables
            )

            config[col] = st.column_config.SelectboxColumn(

                col,

                options=["", "A", "F"],

                required=False,

                width="small",

                disabled=not editable
            )

        else:

            config[col] = st.column_config.TextColumn(

                col,

                width="medium",

                disabled=True
            )

    # =================================================
    # TABLA
    # =================================================

    edited_df = st.data_editor(

        df[columnas_visibles],

        use_container_width=True,

        hide_index=True,

        num_rows="fixed",

        key="ASISTENCIA_EDITOR",

        column_config=config,

        height=700
    )

    # =================================================
    # BOTON
    # =================================================

    if st.button(
        "💾 Guardar Asistencia"
    ):

        try:

            # =========================================
            # RECUPERAR COLUMNAS BASE
            # =========================================

            for col in COLUMNAS_BASE:

                edited_df[col] = (
                    df[col].values
                )

            # =========================================
            # HISTORICO
            # =========================================

            periodo_actual = (
                datetime.now()
                .strftime("%Y-%m")
            )

            historico = df_drive[
                df_drive["PERIODO"]
                != periodo_actual
            ].copy()

            # =========================================
            # FINAL
            # =========================================

            df_final = pd.concat(
                [
                    historico,
                    edited_df
                ],
                ignore_index=True
            )

            # =========================================
            # ELIMINAR DUPLICADOS
            # =========================================

            df_final = df_final.drop_duplicates(

                subset=["PERIODO", "DNI"],

                keep="first"
            )

            df_final = df_final.fillna("")

            # =========================================
            # ORDEN
            # =========================================

            df_final = df_final[
                COLUMNAS_FINAL
            ]

            # =========================================
            # DRIVE
            # =========================================

            hoja_asistencia.clear()

            hoja_asistencia.update(

                [
                    df_final.columns.tolist()
                ]
                +
                df_final.values.tolist()

            )

            # =========================================
            # LIMPIAR CACHE
            # =========================================

            st.cache_data.clear()

            st.session_state.pop(
                "df_asistencia",
                None
            )

            st.session_state.pop(
                "df_asistencia_drive",
                None
            )

            st.success(
                "✅ Asistencia guardada correctamente"
            )

            st.rerun()

        except Exception as e:

            st.error(
                f"❌ Error: {e}"
            )