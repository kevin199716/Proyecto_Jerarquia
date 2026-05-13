import streamlit as st
import pandas as pd

from datetime import datetime, timedelta

from st_aggrid import (
    AgGrid,
    GridOptionsBuilder,
    GridUpdateMode,
    JsCode
)

# ============================================
# CACHE
# ============================================

@st.cache_data(ttl=60)
def cargar_colaboradores_cache(data):
    return pd.DataFrame(data)

# ============================================
# OBTENER HOJA MES
# ============================================

def obtener_hoja_mes(spreadsheet):

    hoy = datetime.now()

    nombre_hoja = f"ASISTENCIA_{hoy.strftime('%Y_%m')}"

    hojas = [
        x.title
        for x in spreadsheet.worksheets()
    ]

    if nombre_hoja not in hojas:

        hoja = spreadsheet.add_worksheet(
            title=nombre_hoja,
            rows=5000,
            cols=60
        )

    else:

        hoja = spreadsheet.worksheet(
            nombre_hoja
        )

    return hoja

# ============================================
# GENERAR ASISTENCIA
# ============================================

def generar_asistencia_mes(
    hoja_asistencia,
    df_colab
):

    valores = hoja_asistencia.get_all_values()

    # SI YA EXISTE DATA
    if len(valores) > 1:
        return

    hoy = datetime.now()

    periodo = hoy.strftime("%Y-%m")

    registros = []

    # SOLO ACTIVOS
    df_activos = df_colab[
        df_colab["ESTADO"]
        .astype(str)
        .str.upper()
        == "ACTIVO"
    ]

    for _, row in df_activos.iterrows():

        fila = {
            "PERIODO": periodo,
            "DNI": str(row.get("DNI", "")),
            "NOMBRE": str(row.get("NOMBRES", "")),
            "SUPERVISOR": str(row.get("SUPERVISOR A CARGO", "")),
            "COORDINADOR": str(row.get("COORDINADOR", "")),
            "DEPARTAMENTO": str(row.get("DEPARTAMENTO", "")),
            "PROVINCIA": str(row.get("PROVINCIA", "")),
            "ESTADO": str(row.get("ESTADO", "")),
            "FECHA_REGISTRO": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        for dia in range(1, 32):

            fila[f"DIA_{dia}"] = ""

        registros.append(fila)

    df_nuevo = pd.DataFrame(registros)

    hoja_asistencia.update(
        [df_nuevo.columns.values.tolist()] +
        df_nuevo.astype(str).values.tolist()
    )

# ============================================
# SEMANA EDITABLE
# ============================================

def obtener_semana_actual():

    hoy = datetime.now()

    inicio_semana = hoy - timedelta(days=hoy.weekday())

    dias_editables = []

    for i in range(7):

        fecha = inicio_semana + timedelta(days=i)

        if fecha <= hoy:

            dias_editables.append(fecha.day)

    return dias_editables

# ============================================
# COLORES
# ============================================

cellstyle_jscode = JsCode("""

function(params) {

    if(params.value == 'A') {
        return {
            'backgroundColor': '#c8f7c5',
            'color': 'green',
            'fontWeight': 'bold',
            'textAlign': 'center'
        }
    }

    if(params.value == 'F') {
        return {
            'backgroundColor': '#ffb3b3',
            'color': 'red',
            'fontWeight': 'bold',
            'textAlign': 'center'
        }
    }

    return {
        'textAlign': 'center'
    }
}

""")

# ============================================
# MAIN
# ============================================

def mostrar_asistencia(
    spreadsheet,
    hoja_colaboradores
):

    st.markdown("## 🗓️ Control de Asistencia")

    # ====================================
    # HOJA DEL MES
    # ====================================

    hoja_asistencia = obtener_hoja_mes(
        spreadsheet
    )

    # ====================================
    # COLABORADORES
    # ====================================

    data_colab = hoja_colaboradores.get_all_records()

    df_colab = cargar_colaboradores_cache(
        data_colab
    )

    df_colab.columns = (
        df_colab.columns
        .str.strip()
        .str.upper()
    )

    # ====================================
    # GENERAR BASE MES
    # ====================================

    generar_asistencia_mes(
        hoja_asistencia,
        df_colab
    )

    # ====================================
    # LEER DATA
    # ====================================

    valores = hoja_asistencia.get_all_values()

    headers = valores[0]

    data = valores[1:]

    df = pd.DataFrame(
        data,
        columns=headers
    )

    # ====================================
    # FILTROS
    # ====================================

    supervisores = sorted(
        list(
            set(
                df["SUPERVISOR"]
                .astype(str)
                .tolist()
            )
        )
    )

    coordinadores = sorted(
        list(
            set(
                df["COORDINADOR"]
                .astype(str)
                .tolist()
            )
        )
    )

    c1, c2 = st.columns(2)

    with c1:

        filtro_supervisor = st.selectbox(
            "🔍 Supervisor",
            ["TODOS"] + supervisores
        )

    with c2:

        filtro_coord = st.selectbox(
            "🔍 Coordinador",
            ["TODOS"] + coordinadores
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

    dias_editables = obtener_semana_actual()

    columnas_base = [
        "SUPERVISOR",
        "COORDINADOR",
        "DEPARTAMENTO",
        "PROVINCIA",
        "DNI",
        "NOMBRE",
        "ESTADO"
    ]

    columnas_dias = [
        f"DIA_{dia}"
        for dia in range(1, 32)
    ]

    columnas_finales = (
        columnas_base +
        columnas_dias
    )

    columnas_existentes = [
        c for c in columnas_finales
        if c in df.columns
    ]

    df = df[columnas_existentes]

    # ====================================
    # GRID
    # ====================================

    gb = GridOptionsBuilder.from_dataframe(df)

    gb.configure_default_column(
        editable=False,
        resizable=True
    )

    columnas_fijas = [
        "SUPERVISOR",
        "COORDINADOR",
        "DEPARTAMENTO",
        "PROVINCIA",
        "DNI",
        "NOMBRE",
        "ESTADO"
    ]

    for col in columnas_fijas:

        gb.configure_column(
            col,
            pinned="left",
            editable=False,
            width=180
        )

    for dia in range(1, 32):

        col = f"DIA_{dia}"

        editable = dia in dias_editables

        gb.configure_column(
            col,
            editable=editable,
            width=90,
            cellEditor="agSelectCellEditor",
            cellEditorParams={
                "values": ["", "A", "F"]
            },
            cellStyle=cellstyle_jscode
        )

    gridOptions = gb.build()

    grid_response = AgGrid(
        df,
        gridOptions=gridOptions,
        update_mode=GridUpdateMode.MANUAL,
        allow_unsafe_jscode=True,
        fit_columns_on_grid_load=False,
        reload_data=False,
        theme="streamlit",
        height=700
    )

    # ====================================
    # GUARDAR
    # ====================================

    if st.button("💾 Guardar Asistencia"):

        nuevo_df = pd.DataFrame(
            grid_response["data"]
        )

        nuevo_df = nuevo_df.fillna("")

        hoja_asistencia.update(
            [nuevo_df.columns.values.tolist()] +
            nuevo_df.astype(str).values.tolist()
        )

        st.success(
            "✅ Asistencia guardada correctamente"
        )