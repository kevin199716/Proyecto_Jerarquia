# asistencia.py

import streamlit as st
import pandas as pd
from datetime import datetime


# =========================================================
# CONFIG
# =========================================================

COLUMNAS_DIAS = [f"DIA_{i}" for i in range(1, 32)]

COLUMNAS_BASE = [
    "SUPERVISOR",
    "COORDINADOR",
    "DEPARTAMENTO",
    "PROVINCIA",
    "DNI",
    "NOMBRE",
    "ESTADO",
    "MES",
    "PERIODO"
]

COLUMNAS_FINAL = COLUMNAS_BASE + COLUMNAS_DIAS


# =========================================================
# LEER DRIVE
# =========================================================

@st.cache_data(ttl=60)
def leer_drive_data(data):

    df = pd.DataFrame(data)

    if df.empty:
        return pd.DataFrame(columns=COLUMNAS_FINAL)

    # NORMALIZAR
    df.columns = (
        df.columns
        .astype(str)
        .str.strip()
        .str.upper()
    )

    # ASEGURAR COLUMNAS
    for col in COLUMNAS_FINAL:

        if col not in df.columns:
            df[col] = ""

    # SOLO COLUMNAS NECESARIAS
    df = df[COLUMNAS_FINAL]

    # LIMPIAR NONE
    df = df.fillna("")

    for col in COLUMNAS_DIAS:

        df[col] = (
            df[col]
            .astype(str)
            .replace("None", "")
            .replace("nan", "")
        )

    return df


# =========================================================
# PREPARAR DATA
# =========================================================

def preparar_data(
    hoja_asistencia,
    hoja_colaboradores
):

    # =========================================
    # DRIVE
    # =========================================

    registros_drive = hoja_asistencia.get_all_records()

    df_drive = leer_drive_data(registros_drive)

    # =========================================
    # COLABORADORES
    # =========================================

    colaboradores = hoja_colaboradores.get_all_records()

    df_colab = pd.DataFrame(colaboradores)

    if df_colab.empty:
        return df_drive

    df_colab.columns = (
        df_colab.columns
        .astype(str)
        .str.strip()
        .str.upper()
    )

    # =========================================
    # COLUMNAS
    # =========================================

    columnas_necesarias = [
        "SUPERVISOR A CARGO",
        "COORDINADOR",
        "DEPARTAMENTO",
        "PROVINCIA",
        "DNI",
        "NOMBRES",
        "ESTADO"
    ]

    for col in columnas_necesarias:

        if col not in df_colab.columns:
            df_colab[col] = ""

    # =========================================
    # RENOMBRE
    # =========================================

    df_colab = df_colab.rename(columns={

        "SUPERVISOR A CARGO": "SUPERVISOR",
        "NOMBRES": "NOMBRE"

    })

    # =========================================
    # MES
    # =========================================

    hoy = datetime.now()

    mes_actual = hoy.month

    periodo_actual = hoy.strftime("%Y-%m")

    # =========================================
    # FILTRO MES
    # =========================================

    if not df_drive.empty:

        df_mes = df_drive[
            df_drive["PERIODO"].astype(str)
            == periodo_actual
        ].copy()

    else:

        df_mes = pd.DataFrame()

    # =========================================
    # SI NO EXISTE MES
    # =========================================

    if df_mes.empty:

        df_mes = pd.DataFrame()

        df_mes["SUPERVISOR"] = df_colab["SUPERVISOR"]
        df_mes["COORDINADOR"] = df_colab["COORDINADOR"]
        df_mes["DEPARTAMENTO"] = df_colab["DEPARTAMENTO"]
        df_mes["PROVINCIA"] = df_colab["PROVINCIA"]

        df_mes["DNI"] = (
            df_colab["DNI"]
            .astype(str)
        )

        df_mes["NOMBRE"] = df_colab["NOMBRE"]
        df_mes["ESTADO"] = df_colab["ESTADO"]

        df_mes["MES"] = mes_actual
        df_mes["PERIODO"] = periodo_actual

        for col in COLUMNAS_DIAS:
            df_mes[col] = ""

        df_mes = df_mes.fillna("")

        return df_mes

    # =========================================
    # SI EXISTE MES
    # =========================================

    df_mes = df_mes.fillna("")

    return df_mes


# =========================================================
# MOSTRAR
# =========================================================

def mostrar_asistencia(
    hoja_asistencia,
    hoja_colaboradores
):

    st.subheader("🗓️ Control de Asistencia")

    # =====================================================
    # CARGA UNICA
    # =====================================================

    if "df_asistencia" not in st.session_state:

        st.session_state.df_asistencia = preparar_data(
            hoja_asistencia,
            hoja_colaboradores
        )

    df = st.session_state.df_asistencia.copy()

    # =====================================================
    # LIMPIAR NONE
    # =====================================================

    df = df.fillna("")

    for col in COLUMNAS_DIAS:

        df[col] = (
            df[col]
            .astype(str)
            .replace("None", "")
            .replace("nan", "")
        )

    # =====================================================
    # FILTROS
    # =====================================================

    col1, col2 = st.columns(2)

    with col1:

        supervisores = ["TODOS"] + sorted([
            x for x in
            df["SUPERVISOR"]
            .astype(str)
            .unique()
            .tolist()
            if x != ""
        ])

        filtro_sup = st.selectbox(
            "🔎 Supervisor",
            supervisores
        )

    with col2:

        coordinadores = ["TODOS"] + sorted([
            x for x in
            df["COORDINADOR"]
            .astype(str)
            .unique()
            .tolist()
            if x != ""
        ])

        filtro_coord = st.selectbox(
            "🔎 Coordinador",
            coordinadores
        )

    # =====================================================
    # FILTRO
    # =====================================================

    if filtro_sup != "TODOS":

        df = df[
            df["SUPERVISOR"] == filtro_sup
        ]

    if filtro_coord != "TODOS":

        df = df[
            df["COORDINADOR"] == filtro_coord
        ]

    # =====================================================
    # COLUMNAS
    # =====================================================

    columnas_visibles = [
        "PROVINCIA",
        "DNI",
        "NOMBRE",
        "ESTADO"
    ] + COLUMNAS_DIAS

    # =====================================================
    # DIA EDITABLE
    # =====================================================

    dia_actual = datetime.now().day

    columna_editable = f"DIA_{dia_actual}"

    # =====================================================
    # CONFIG
    # =====================================================

    config = {}

    for col in columnas_visibles:

        if col.startswith("DIA_"):

            config[col] = st.column_config.SelectboxColumn(

                col,

                options=["", "A", "F"],

                default="",

                width="small",

                required=False,

                disabled=(col != columna_editable)

            )

        else:

            config[col] = st.column_config.Column(

                col,

                width="medium",

                disabled=True

            )

    # =====================================================
    # EDITOR
    # =====================================================

    edited_df = st.data_editor(

        df[columnas_visibles],

        key="EDITOR_ASISTENCIA",

        use_container_width=True,

        hide_index=True,

        num_rows="fixed",

        height=700,

        column_config=config,

        disabled=[
            c for c in columnas_visibles
            if not c.startswith("DIA_")
        ]
    )

    # =====================================================
    # GUARDAR
    # =====================================================

    if st.button("💾 Guardar Asistencia"):

        try:

            # =========================================
            # RECUPERAR COLUMNAS
            # =========================================

            for col in df.columns:

                if col not in edited_df.columns:

                    edited_df[col] = df[col].values

            # =========================================
            # LIMPIAR
            # =========================================

            edited_df = edited_df.fillna("")

            # =========================================
            # ORDEN
            # =========================================

            edited_df = edited_df[COLUMNAS_FINAL]

            # =========================================
            # GUARDAR DRIVE
            # =========================================

            hoja_asistencia.clear()

            hoja_asistencia.update(

                [edited_df.columns.tolist()]
                +
                edited_df.values.tolist()

            )

            # =========================================
            # SESSION
            # =========================================

            st.session_state.df_asistencia = edited_df

            st.success(
                "✅ Asistencia guardada correctamente"
            )

        except Exception as e:

            st.error(f"❌ Error: {e}")