import streamlit as st
import pandas as pd
from datetime import datetime

# =====================================================
# COLUMNAS
# =====================================================

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

COLUMNAS_FINALES = COLUMNAS_BASE + COLUMNAS_DIAS

# =====================================================
# CACHE
# =====================================================

@st.cache_data(ttl=60)
def cargar_datos_drive(registros):

    df = pd.DataFrame(registros)

    if df.empty:

        return pd.DataFrame(columns=COLUMNAS_FINALES)

    df.columns = (
        df.columns
        .astype(str)
        .str.strip()
        .str.upper()
    )

    for col in COLUMNAS_FINALES:

        if col not in df.columns:

            df[col] = ""

    df = df[COLUMNAS_FINALES]

    df = df.fillna("")

    return df

# =====================================================
# MAIN
# =====================================================

def mostrar_asistencia(
    hoja_asistencia,
    hoja_colaboradores
):

    st.subheader("🗓️ Control de Asistencia")

    # =================================================
    # CARGA DRIVE
    # =================================================

    registros_asistencia = hoja_asistencia.get_all_records()

    df_drive = cargar_datos_drive(
        registros_asistencia
    )

    # =================================================
    # MES ACTUAL
    # =================================================

    hoy = datetime.now()

    periodo_actual = hoy.strftime("%Y-%m")

    mes_actual = hoy.month

    # =================================================
    # FILTRO MES
    # =================================================

    if not df_drive.empty:

        df_mes = df_drive[
            df_drive["PERIODO"].astype(str)
            == periodo_actual
        ].copy()

    else:

        df_mes = pd.DataFrame()

    # =================================================
    # SI NO EXISTE MES
    # =================================================

    if df_mes.empty:

        registros_colab = hoja_colaboradores.get_all_records()

        df_colab = pd.DataFrame(registros_colab)

        df_colab.columns = (
            df_colab.columns
            .astype(str)
            .str.strip()
            .str.upper()
        )

        df_mes = pd.DataFrame()

        df_mes["SUPERVISOR"] = df_colab.get(
            "SUPERVISOR A CARGO",
            ""
        )

        df_mes["COORDINADOR"] = df_colab.get(
            "COORDINADOR",
            ""
        )

        df_mes["DEPARTAMENTO"] = df_colab.get(
            "DEPARTAMENTO",
            ""
        )

        df_mes["PROVINCIA"] = df_colab.get(
            "PROVINCIA",
            ""
        )

        df_mes["DNI"] = (
            df_colab.get("DNI", "")
            .astype(str)
        )

        df_mes["NOMBRE"] = df_colab.get(
            "NOMBRES",
            ""
        )

        df_mes["ESTADO"] = df_colab.get(
            "ESTADO",
            ""
        )

        df_mes["MES"] = mes_actual

        df_mes["PERIODO"] = periodo_actual

        for col in COLUMNAS_DIAS:

            df_mes[col] = ""

    # =================================================
    # LIMPIAR
    # =================================================

    df_mes = df_mes.fillna("")

    for col in COLUMNAS_DIAS:

        df_mes[col] = (
            df_mes[col]
            .astype(str)
            .replace("None", "")
            .replace("nan", "")
        )

    # =================================================
    # FILTROS
    # =================================================

    col1, col2 = st.columns(2)

    with col1:

        lista_sup = ["TODOS"] + sorted([
            x for x in
            df_mes["SUPERVISOR"]
            .astype(str)
            .unique()
            .tolist()
            if x != ""
        ])

        filtro_sup = st.selectbox(
            "🔎 Supervisor",
            lista_sup
        )

    with col2:

        lista_coord = ["TODOS"] + sorted([
            x for x in
            df_mes["COORDINADOR"]
            .astype(str)
            .unique()
            .tolist()
            if x != ""
        ])

        filtro_coord = st.selectbox(
            "🔎 Coordinador",
            lista_coord
        )

    # =================================================
    # FILTRAR
    # =================================================

    if filtro_sup != "TODOS":

        df_mes = df_mes[
            df_mes["SUPERVISOR"] == filtro_sup
        ]

    if filtro_coord != "TODOS":

        df_mes = df_mes[
            df_mes["COORDINADOR"] == filtro_coord
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
    # DIA EDITABLE
    # =================================================

    dia_actual = datetime.now().day

    columna_editable = f"DIA_{dia_actual}"

    # =================================================
    # CONFIG
    # =================================================

    config = {}

    for col in columnas_visibles:

        if col.startswith("DIA_"):

            config[col] = st.column_config.SelectboxColumn(

                col,

                options=["", "A", "F"],

                width="small",

                required=False,

                disabled=(col != columna_editable)

            )

        else:

            config[col] = st.column_config.TextColumn(

                col,

                width="medium",

                disabled=True

            )

    # =================================================
    # EDITOR
    # =================================================

    edited_df = st.data_editor(

        df_mes[columnas_visibles],

        use_container_width=True,

        hide_index=True,

        num_rows="fixed",

        height=700,

        column_config=config,

        key="editor_asistencia"
    )

    # =================================================
    # GUARDAR
    # =================================================

    if st.button("💾 Guardar Asistencia"):

        try:

            # =========================================
            # RECUPERAR COLUMNAS
            # =========================================

            for col in COLUMNAS_BASE:

                edited_df[col] = df_mes[col].values

            edited_df["MES"] = mes_actual
            edited_df["PERIODO"] = periodo_actual

            edited_df = edited_df[COLUMNAS_FINALES]

            # =========================================
            # HISTORICO
            # =========================================

            df_historico = df_drive[
                df_drive["PERIODO"].astype(str)
                != periodo_actual
            ].copy()

            df_final = pd.concat([
                df_historico,
                edited_df
            ])

            df_final = df_final.fillna("")

            # =========================================
            # DRIVE
            # =========================================

            hoja_asistencia.clear()

            hoja_asistencia.update(
                [df_final.columns.tolist()]
                +
                df_final.values.tolist()
            )

            st.success(
                "✅ Asistencia guardada correctamente"
            )

        except Exception as e:

            st.error(f"❌ Error: {e}")