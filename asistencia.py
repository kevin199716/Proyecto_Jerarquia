import streamlit as st
import pandas as pd
from datetime import datetime
from st_aggrid import (
    AgGrid,
    GridOptionsBuilder,
    GridUpdateMode,
    DataReturnMode,
    JsCode
)

# =====================================================
# CONFIG
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

# =====================================================
# CACHE
# =====================================================

@st.cache_data(ttl=60)
def cargar_asistencia(_hoja):
    data = _hoja.get_all_records()

    if not data:
        return pd.DataFrame()

    return pd.DataFrame(data).fillna("")


@st.cache_data(ttl=60)
def cargar_colaboradores(_hoja):
    data = _hoja.get_all_records()

    if not data:
        return pd.DataFrame()

    return pd.DataFrame(data).fillna("")


# =====================================================
# GENERAR BASE
# =====================================================

def generar_base(hoja_asistencia, hoja_colaboradores):

    hoy = datetime.now()

    periodo_actual = hoy.strftime("%Y-%m")
    mes_actual = hoy.strftime("%m")

    df_drive = cargar_asistencia(hoja_asistencia)

    df_colab = cargar_colaboradores(hoja_colaboradores)

    # =================================================
    # SI DRIVE VACIO
    # =================================================

    if df_drive.empty:

        filas = []

        for _, row in df_colab.iterrows():

            fila = {
                "SUPERVISOR": str(row.get("SUPERVISOR A CARGO", "")),
                "COORDINADOR": str(row.get("COORDINADOR", "")),
                "DEPARTAMENTO": str(row.get("DEPARTAMENTO", "")),
                "PROVINCIA": str(row.get("PROVINCIA", "")),
                "DNI": str(row.get("DNI", "")),
                "NOMBRE": str(row.get("NOMBRES", "")),
                "ESTADO": str(row.get("ESTADO", "")),
                "MES": mes_actual,
                "PERIODO": periodo_actual
            }

            for d in COLUMNAS_DIAS:
                fila[d] = ""

            filas.append(fila)

        return pd.DataFrame(filas)

    # =================================================
    # ASEGURAR COLUMNAS
    # =================================================

    if "PERIODO" not in df_drive.columns:
        df_drive["PERIODO"] = periodo_actual

    if "MES" not in df_drive.columns:
        df_drive["MES"] = mes_actual

    # =================================================
    # FILTRAR SOLO MES ACTUAL
    # =================================================

    df_mes = df_drive[
        df_drive["PERIODO"].astype(str)
        == periodo_actual
    ].copy()

    # =================================================
    # AGREGAR NUEVOS
    # =================================================

    for _, row in df_colab.iterrows():

        dni = str(row.get("DNI", ""))

        supervisor = str(row.get("SUPERVISOR A CARGO", ""))

        existe = (

            (df_mes["DNI"].astype(str) == dni)
            &
            (df_mes["SUPERVISOR"].astype(str) == supervisor)

        ).any()

        if not existe:

            nueva = {
                "SUPERVISOR": supervisor,
                "COORDINADOR": str(row.get("COORDINADOR", "")),
                "DEPARTAMENTO": str(row.get("DEPARTAMENTO", "")),
                "PROVINCIA": str(row.get("PROVINCIA", "")),
                "DNI": dni,
                "NOMBRE": str(row.get("NOMBRES", "")),
                "ESTADO": str(row.get("ESTADO", "")),
                "MES": mes_actual,
                "PERIODO": periodo_actual
            }

            for d in COLUMNAS_DIAS:
                nueva[d] = ""

            df_mes = pd.concat(
                [df_mes, pd.DataFrame([nueva])],
                ignore_index=True
            )

    return df_mes.fillna("")


# =====================================================
# MOSTRAR
# =====================================================

def mostrar_asistencia(
    hoja_asistencia,
    hoja_colaboradores
):

    st.subheader("🗓️ Control de Asistencia")

    df = generar_base(
        hoja_asistencia,
        hoja_colaboradores
    )

    # =================================================
    # FILTROS
    # =================================================

    col1, col2 = st.columns(2)

    with col1:

        supervisores = ["TODOS"]

        if "SUPERVISOR" in df.columns:

            supervisores += sorted(
                df["SUPERVISOR"]
                .astype(str)
                .unique()
                .tolist()
            )

        filtro_supervisor = st.selectbox(
            "🔎 Supervisor",
            supervisores
        )

    with col2:

        coordinadores = ["TODOS"]

        if "COORDINADOR" in df.columns:

            coordinadores += sorted(
                df["COORDINADOR"]
                .astype(str)
                .unique()
                .tolist()
            )

        filtro_coord = st.selectbox(
            "🔎 Coordinador",
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
    # COLUMNAS
    # =================================================

    columnas = [
        "PROVINCIA",
        "DNI",
        "NOMBRE",
        "ESTADO"
    ] + COLUMNAS_DIAS

    for c in columnas:
        if c not in df.columns:
            df[c] = ""

    df_grid = df[columnas].copy()

    # =================================================
    # SEMANA
    # =================================================

    hoy = datetime.now().day

    inicio = ((hoy - 1) // 7) * 7 + 1
    fin = min(inicio + 6, 31)

    # =================================================
    # GRID
    # =================================================

    gb = GridOptionsBuilder.from_dataframe(df_grid)

    gb.configure_default_column(
        editable=False,
        resizable=True
    )

    gb.configure_column(
        "PROVINCIA",
        width=180
    )

    gb.configure_column(
        "DNI",
        width=130
    )

    gb.configure_column(
        "NOMBRE",
        width=220
    )

    gb.configure_column(
        "ESTADO",
        width=120
    )

    color_js = JsCode("""

    function(params) {

        if (params.value == 'A') {

            return {
                'backgroundColor': '#b7e4c7',
                'fontWeight': 'bold',
                'textAlign': 'center'
            }
        }

        if (params.value == 'F') {

            return {
                'backgroundColor': '#f4acb7',
                'fontWeight': 'bold',
                'textAlign': 'center'
            }
        }
    }

    """)

    for i in range(1, 32):

        editable = inicio <= i <= fin

        gb.configure_column(

            f"DIA_{i}",

            editable=editable,

            width=85,

            cellEditor="agSelectCellEditor",

            cellEditorParams={
                "values": ["", "A", "F"]
            },

            cellStyle=color_js
        )

    gb.configure_grid_options(
        suppressRowVirtualisation=True,
        suppressColumnVirtualisation=True,
        animateRows=False
    )

    response = AgGrid(

        df_grid,

        gridOptions=gb.build(),

        theme="streamlit",

        allow_unsafe_jscode=True,

        fit_columns_on_grid_load=False,

        update_mode=GridUpdateMode.MANUAL,

        data_return_mode=DataReturnMode.AS_INPUT,

        reload_data=False,

        height=620,

        key="GRID_ASISTENCIA_FINAL"
    )

    st.caption(
        "Solo editable semana actual | A = Asistencia | F = Falta"
    )

    # =================================================
    # GUARDAR
    # =================================================

    if st.button("💾 Guardar Asistencia"):

        try:

            df_editado = pd.DataFrame(
                response["data"]
            ).fillna("")

            # =============================================
            # RECUPERAR COLUMNAS OCULTAS
            # =============================================

            for col in COLUMNAS_BASE:

                if col not in df_editado.columns:

                    df_editado[col] = (
                        df[col].values
                    )

            # =============================================
            # HISTORICO
            # =============================================

            df_drive = cargar_asistencia(
                hoja_asistencia
            )

            periodo_actual = datetime.now().strftime("%Y-%m")

            if not df_drive.empty:

                historico = df_drive[
                    df_drive["PERIODO"].astype(str)
                    != periodo_actual
                ].copy()

            else:

                historico = pd.DataFrame()

            # =============================================
            # FINAL
            # =============================================

            df_final = pd.concat(
                [historico, df_editado],
                ignore_index=True
            )

            columnas_finales = (
                COLUMNAS_BASE +
                COLUMNAS_DIAS
            )

            for c in columnas_finales:

                if c not in df_final.columns:
                    df_final[c] = ""

            df_final = df_final[columnas_finales]

            # =============================================
            # GUARDAR
            # =============================================

            hoja_asistencia.clear()

            hoja_asistencia.update(

                [df_final.columns.tolist()] +
                df_final.values.tolist()

            )

            st.cache_data.clear()

            st.success(
                "✅ Asistencia guardada correctamente"
            )

            st.rerun()

        except Exception as e:

            st.error(
                f"❌ Error guardando: {e}"
            )