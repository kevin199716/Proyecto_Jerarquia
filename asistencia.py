import streamlit as st
import pandas as pd
import calendar
from datetime import datetime, timedelta

from st_aggrid import (
    AgGrid,
    GridOptionsBuilder,
    GridUpdateMode,
    DataReturnMode,
    JsCode
)


def obtener_columnas_dias():
    hoy = datetime.now()
    dias_mes = calendar.monthrange(hoy.year, hoy.month)[1]
    return [f"DIA_{i}" for i in range(1, dias_mes + 1)]


def obtener_semana_actual():
    hoy = datetime.now()
    inicio_semana = hoy - timedelta(days=hoy.weekday())

    dias = []
    for i in range(7):
        fecha = inicio_semana + timedelta(days=i)
        if fecha.month == hoy.month:
            dias.append(fecha.day)

    return dias


def col_num_to_letter(n):
    letra = ""
    while n > 0:
        n, r = divmod(n - 1, 26)
        letra = chr(65 + r) + letra
    return letra


def leer_sheet(hoja):
    valores = hoja.get_all_values()

    if not valores:
        return [], pd.DataFrame()

    headers = [str(x).strip() for x in valores[0]]
    rows = valores[1:]

    ancho = len(headers)
    rows_fix = []

    for r in rows:
        r = r + [""] * (ancho - len(r))
        rows_fix.append(r[:ancho])

    df = pd.DataFrame(rows_fix, columns=headers)
    return headers, df


def crear_fila_asistencia(row):
    hoy = datetime.now()

    nombre = (
        str(row.get("NOMBRES", "")).strip()
        + " "
        + str(row.get("APELLIDO PATERNO", "")).strip()
    ).strip()

    fila = {
        "MES": hoy.strftime("%B").upper(),
        "PERIODO": hoy.strftime("%Y-%m"),
        "SUPERVISOR": str(row.get("SUPERVISOR A CARGO", "")).strip(),
        "COORDINADOR": str(row.get("COORDINADOR", "")).strip(),
        "DEPARTAMENTO": str(row.get("DEPARTAMENTO", "")).strip(),
        "PROVINCIA": str(row.get("PROVINCIA", "")).strip(),
        "DNI": str(row.get("DNI", "")).strip(),
        "NOMBRE": nombre,
        "ESTADO": str(row.get("ESTADO", "")).strip(),
    }

    for d in obtener_columnas_dias():
        fila[d] = ""

    return fila


def asegurar_base_asistencia(hoja_asistencia, df_colab):
    columnas_base = [
        "MES",
        "PERIODO",
        "SUPERVISOR",
        "COORDINADOR",
        "DEPARTAMENTO",
        "PROVINCIA",
        "DNI",
        "NOMBRE",
        "ESTADO",
    ]

    columnas_dias = obtener_columnas_dias()
    columnas_finales = columnas_base + columnas_dias

    headers, df_sheet = leer_sheet(hoja_asistencia)

    if not headers:
        headers = columnas_finales
        registros = []

        for _, row in df_colab.iterrows():
            registros.append(crear_fila_asistencia(row))

        df_nuevo = pd.DataFrame(registros)

        for c in headers:
            if c not in df_nuevo.columns:
                df_nuevo[c] = ""

        df_nuevo = df_nuevo[headers]

        hoja_asistencia.update(
            "A1",
            [headers] + df_nuevo.astype(str).values.tolist(),
            value_input_option="USER_ENTERED",
        )

        headers, df_sheet = leer_sheet(hoja_asistencia)
        return headers, df_sheet

    faltantes = []

    for c in columnas_finales:
        if c not in headers:
            faltantes.append(c)

    if faltantes:
        headers = headers + faltantes
        hoja_asistencia.update(
            "A1",
            [headers],
            value_input_option="USER_ENTERED",
        )

        for c in faltantes:
            df_sheet[c] = ""

    for c in headers:
        if c not in df_sheet.columns:
            df_sheet[c] = ""

    cantidad_sheet = len(df_sheet)
    cantidad_colab = len(df_colab)

    if cantidad_sheet < cantidad_colab:
        registros_faltantes = []

        for idx in range(cantidad_sheet, cantidad_colab):
            row = df_colab.iloc[idx]
            registros_faltantes.append(crear_fila_asistencia(row))

        df_faltantes = pd.DataFrame(registros_faltantes)

        for c in headers:
            if c not in df_faltantes.columns:
                df_faltantes[c] = ""

        df_faltantes = df_faltantes[headers]

        hoja_asistencia.append_rows(
            df_faltantes.astype(str).values.tolist(),
            value_input_option="USER_ENTERED",
        )

        headers, df_sheet = leer_sheet(hoja_asistencia)

    return headers, df_sheet


def mostrar_asistencia(hoja_asistencia, hoja_colaboradores):
    st.markdown("# 🗓️ Control de Asistencia")

    data_colab = hoja_colaboradores.get_all_records()
    df_colab = pd.DataFrame(data_colab)

    if df_colab.empty:
        st.warning("No hay registros en colaboradores.")
        return

    df_colab.columns = df_colab.columns.str.strip().str.upper()

    headers, df = asegurar_base_asistencia(
        hoja_asistencia,
        df_colab,
    )

    if df.empty:
        st.warning("No hay registros de asistencia.")
        return

    df = df.fillna("").astype(str)
    df["_FILA_SHEET"] = df.index + 2

    columnas_base = [
        "MES",
        "PERIODO",
        "SUPERVISOR",
        "COORDINADOR",
        "DEPARTAMENTO",
        "PROVINCIA",
        "DNI",
        "NOMBRE",
        "ESTADO",
    ]

    columnas_dias = obtener_columnas_dias()
    columnas_finales = columnas_base + columnas_dias

    for c in columnas_finales:
        if c not in df.columns:
            df[c] = ""

    df = df[["_FILA_SHEET"] + columnas_finales]

    c1, c2 = st.columns(2)

    with c1:
        supervisor = st.selectbox(
            "🔍 Supervisor",
            ["TODOS"] + sorted([x for x in df["SUPERVISOR"].unique().tolist() if x]),
        )

    with c2:
        coordinador = st.selectbox(
            "🔍 Coordinador",
            ["TODOS"] + sorted([x for x in df["COORDINADOR"].unique().tolist() if x]),
        )

    if supervisor != "TODOS":
        df = df[df["SUPERVISOR"] == supervisor]

    if coordinador != "TODOS":
        df = df[df["COORDINADOR"] == coordinador]

    st.info("Solo editable semana actual | A = Asistencia | F = Falta")

    color_js = JsCode("""
    function(params) {
        if(params.value == 'A') {
            return {
                'backgroundColor': '#B7E4C7',
                'color': '#1B4332',
                'fontWeight': 'bold',
                'textAlign': 'center'
            }
        }

        if(params.value == 'F') {
            return {
                'backgroundColor': '#F4ACB7',
                'color': '#9D0208',
                'fontWeight': 'bold',
                'textAlign': 'center'
            }
        }

        return {
            'textAlign': 'center'
        }
    }
    """)

    gb = GridOptionsBuilder.from_dataframe(df)

    gb.configure_column("_FILA_SHEET", hide=True)

    for c in columnas_base:
        gb.configure_column(
            c,
            editable=False,
            sortable=True,
            filter=True,
            width=180,
            minWidth=150,
            resizable=True,
        )

    semana_actual = obtener_semana_actual()

    for dia in columnas_dias:
        numero = int(dia.replace("DIA_", ""))
        editable = numero in semana_actual

        gb.configure_column(
            dia,
            editable=editable,
            sortable=False,
            filter=False,
            width=110,
            minWidth=100,
            resizable=False,
            singleClickEdit=True,
            cellEditor="agSelectCellEditor",
            cellEditorParams={"values": ["", "A", "F"]},
            cellStyle=color_js,
        )

    gb.configure_grid_options(
        animateRows=False,
        suppressRowTransform=True,
        suppressAnimationFrame=True,
        suppressMovableColumns=True,
        rowBuffer=5,
        domLayout="normal",
    )

    grid_options = gb.build()

    response = AgGrid(
        df,
        gridOptions=grid_options,
        allow_unsafe_jscode=True,
        update_mode=GridUpdateMode.MANUAL,
        data_return_mode=DataReturnMode.AS_INPUT,
        fit_columns_on_grid_load=False,
        reload_data=False,
        enable_enterprise_modules=False,
        theme="streamlit",
        height=560,
        key="grid_asistencia_final",
    )

    st.markdown("A = Asistencia 🟩 | F = Falta 🟥")

    guardar = st.button("💾 Guardar Asistencia")

    if guardar:
        try:
            df_editado = pd.DataFrame(response["data"]).fillna("").astype(str)

            updates = []

            for _, row in df_editado.iterrows():
                fila_sheet = int(row["_FILA_SHEET"])

                original = df[df["_FILA_SHEET"].astype(int) == fila_sheet]

                if original.empty:
                    continue

                for dia in columnas_dias:
                    nuevo = str(row.get(dia, "")).strip().upper()

                    if nuevo not in ["", "A", "F"]:
                        nuevo = ""

                    actual = str(original.iloc[0].get(dia, "")).strip().upper()

                    if nuevo != actual:
                        col_sheet = headers.index(dia) + 1
                        letra = col_num_to_letter(col_sheet)
                        rango = f"{letra}{fila_sheet}"

                        updates.append({
                            "range": rango,
                            "values": [[nuevo]],
                        })

            if updates:
                hoja_asistencia.batch_update(
                    updates,
                    value_input_option="USER_ENTERED",
                )

            st.success("✅ Asistencia guardada correctamente")

        except Exception as e:
            st.error(f"❌ Error al guardar asistencia: {e}")