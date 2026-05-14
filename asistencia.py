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
# CACHE
# =====================================================

@st.cache_data(ttl=60)
def cache_dataframe(data):

    return pd.DataFrame(data)

# =====================================================
# GENERAR BASE
# =====================================================

def generar_base(
    hoja_asistencia,
    hoja_colaboradores
):

    hoy = datetime.now()

    periodo_actual = hoy.strftime("%Y-%m")

    mes_actual = hoy.strftime("%m")

    # =====================================================
    # COLABORADORES
    # =====================================================

    data_colab = hoja_colaboradores.get_all_records()

    df_colab = pd.DataFrame(data_colab)

    df_colab = df_colab.fillna("")

    # =====================================================
    # DRIVE
    # =====================================================

    data_drive = hoja_asistencia.get_all_records()

    if data_drive:

        df_drive = cache_dataframe(data_drive)

    else:

        df_drive = pd.DataFrame()

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

    columnas_dias = [
        f"DIA_{i}" for i in range(1, 32)
    ]

    columnas_finales = (
        columnas_fijas
        + columnas_dias
        + ["MES", "PERIODO"]
    )

    # =====================================================
    # SI NO EXISTE DATA
    # =====================================================

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

            for d in columnas_dias:

                fila[d] = ""

            filas.append(fila)

        return pd.DataFrame(filas)

    # =====================================================
    # ASEGURAR COLUMNAS
    # =====================================================

    for c in columnas_finales:

        if c not in df_drive.columns:

            df_drive[c] = ""

    # =====================================================
    # FILTRAR PERIODO
    # =====================================================

    df_periodo = df_drive[
        df_drive["PERIODO"].astype(str)
        == periodo_actual
    ].copy()

    # =====================================================
    # NUEVO MES
    # =====================================================

    if df_periodo.empty:

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

            for d in columnas_dias:

                fila[d] = ""

            filas.append(fila)

        return pd.DataFrame(filas)

    # =====================================================
    # AGREGAR NUEVOS
    # =====================================================

    dni_existentes = (
        df_periodo["DNI"]
        .astype(str)
        .tolist()
    )

    nuevos = []

    for _, row in df_colab.iterrows():

        dni = str(row.get("DNI", ""))

        if dni not in dni_existentes:

            fila = {
                "SUPERVISOR": str(row.get("SUPERVISOR A CARGO", "")),
                "COORDINADOR": str(row.get("COORDINADOR", "")),
                "DEPARTAMENTO": str(row.get("DEPARTAMENTO", "")),
                "PROVINCIA": str(row.get("PROVINCIA", "")),
                "DNI": dni,
                "NOMBRE": str(row.get("NOMBRES", "")),
                "ESTADO": str(row.get("ESTADO", "")),
                "MES": mes_actual,
                "PERIODO": periodo_actual
            }

            for d in columnas_dias:

                fila[d] = ""

            nuevos.append(fila)

    if nuevos:

        df_nuevos = pd.DataFrame(nuevos)

        df_periodo = pd.concat(
            [df_periodo, df_nuevos],
            ignore_index=True
        )

    # =====================================================
    # LIMPIAR
    # =====================================================

    df_periodo = (
        df_periodo
        .fillna("")
        .astype(str)
    )

    return df_periodo[columnas_finales]

# =====================================================
# MOSTRAR
# =====================================================

def mostrar_asistencia(
    hoja_asistencia,
    hoja_colaboradores
):

    st.markdown("# 🗓️ Control de Asistencia")

    # =====================================================
    # BASE
    # =====================================================

    df = generar_base(
        hoja_asistencia,
        hoja_colaboradores
    )

    # =====================================================
    # ORDENAR
    # =====================================================

    df = df.sort_values(
        by=["NOMBRE"],
        ascending=True
    )

    df = df.reset_index(drop=True)

    # =====================================================
    # FILTROS
    # =====================================================

    col1, col2 = st.columns(2)

    with col1:

        supervisores = ["TODOS"] + sorted(
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

        coordinadores = ["TODOS"] + sorted(
            df["COORDINADOR"]
            .astype(str)
            .unique()
            .tolist()
        )

        filtro_coord = st.selectbox(
            "🔎 Coordinador",
            coordinadores
        )

    # =====================================================
    # FILTRAR
    # =====================================================

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

    # =====================================================
    # SOLO SEMANA ACTUAL
    # =====================================================

    st.info(
        "Solo editable semana actual | A = Asistencia | F = Falta"
    )

    # =====================================================
    # GRID
    # =====================================================

    gb = GridOptionsBuilder.from_dataframe(df)

    hoy = datetime.now().day

    dias_editables = [
        f"DIA_{i}"
        for i in range(max(1, hoy - 6), hoy + 1)
    ]

    columnas_bloqueadas = [
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

    for col in df.columns:

        if col in columnas_bloqueadas:

            gb.configure_column(
                col,
                editable=False,
                width=170
            )

        elif col.startswith("DIA_"):

            gb.configure_column(
                col,
                editable=col in dias_editables,
                width=90,
                cellEditor="agSelectCellEditor",
                cellEditorParams={
                    "values": ["", "A", "F"]
                }
            )

    # =====================================================
    # COLORES
    # =====================================================

    estilo = JsCode("""
    function(params) {

        if(params.value == 'A') {
            return {
                'backgroundColor': '#b7e4c7',
                'fontWeight': 'bold',
                'textAlign': 'center'
            }
        }

        if(params.value == 'F') {
            return {
                'backgroundColor': '#f4b6c2',
                'fontWeight': 'bold',
                'textAlign': 'center'
            }
        }
    }
    """)

    for i in range(1, 32):

        gb.configure_column(
            f"DIA_{i}",
            cellStyle=estilo
        )

    # =====================================================
    # GRID OPTIONS
    # =====================================================

    gb.configure_grid_options(
        suppressRowTransform=True,
        suppressAnimationFrame=True,
        rowBuffer=10,
        domLayout='normal'
    )

    grid_options = gb.build()

    # =====================================================
    # GRID
    # =====================================================

    response = AgGrid(
        df,
        gridOptions=grid_options,
        update_mode=GridUpdateMode.VALUE_CHANGED,
        data_return_mode=DataReturnMode.FILTERED_AND_SORTED,
        allow_unsafe_jscode=True,
        fit_columns_on_grid_load=False,
        enable_enterprise_modules=False,
        theme="streamlit",
        height=650,
        reload_data=False,
        key="GRID_ASISTENCIA"
    )

    df_editado = pd.DataFrame(
        response["data"]
    )

    # =====================================================
    # LEYENDA
    # =====================================================

    st.markdown(
        "A = Asistencia 🟩 | F = Falta 🟥"
    )

    # =====================================================
    # GUARDAR
    # =====================================================

    if st.button("💾 Guardar Asistencia"):

        try:

            periodo_actual = (
                datetime.now().strftime("%Y-%m")
            )

            data_total = hoja_asistencia.get_all_records()

            if data_total:

                df_total = pd.DataFrame(data_total)

            else:

                df_total = pd.DataFrame()

            # =====================================================
            # ELIMINAR SOLO PERIODO ACTUAL
            # =====================================================

            if not df_total.empty:

                df_total = df_total[
                    df_total["PERIODO"].astype(str)
                    != periodo_actual
                ]

            # =====================================================
            # CONCATENAR
            # =====================================================

            df_final = pd.concat(
                [df_total, df_editado],
                ignore_index=True
            )

            df_final = (
                df_final
                .fillna("")
                .astype(str)
            )

            # =====================================================
            # DRIVE
            # =====================================================

            hoja_asistencia.clear()

            hoja_asistencia.update(
                [
                    df_final.columns.values.tolist()
                ]
                +
                df_final.values.tolist()
            )

            cache_dataframe.clear()

            st.success(
                "✅ Asistencia guardada correctamente"
            )

        except Exception as e:

            st.error(
                f"❌ Error al guardar: {str(e)}"
            )