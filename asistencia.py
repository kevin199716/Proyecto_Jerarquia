from datetime import datetime, timedelta

import pandas as pd
import streamlit as st
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, JsCode, DataReturnMode

# =====================================================
# CONFIG ASISTENCIA
# =====================================================
COLUMNAS_BASE = [
    "SUPERVISOR", "COORDINADOR", "DEPARTAMENTO", "PROVINCIA",
    "DNI", "NOMBRE", "ESTADO", "MES", "PERIODO"
]
COLUMNAS_DIAS = [f"DIA_{i}" for i in range(1, 32)]
COLUMNAS_ASISTENCIA = COLUMNAS_BASE + COLUMNAS_DIAS

# =====================================================
# UTILIDADES
# =====================================================
def _normalizar_columnas(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = df.columns.astype(str).str.strip().str.upper()
    return df


def _periodo_actual() -> str:
    return datetime.now().strftime("%Y-%m")


def _mes_actual() -> str:
    return str(datetime.now().month)


def _leer_sheet_df(hoja) -> pd.DataFrame:
    valores = hoja.get_all_values()
    if not valores:
        return pd.DataFrame(columns=COLUMNAS_ASISTENCIA)

    headers = [str(x).strip().upper() for x in valores[0]]
    data = valores[1:]

    # Ajusta filas cortas/largas al tamaño de cabecera
    data_fix = []
    for fila in data:
        fila = list(fila)
        if len(fila) < len(headers):
            fila = fila + [""] * (len(headers) - len(fila))
        if len(fila) > len(headers):
            fila = fila[:len(headers)]
        data_fix.append(fila)

    df = pd.DataFrame(data_fix, columns=headers)
    df = df.replace("None", "").fillna("")
    return _normalizar_columnas(df)


def _asegurar_cabecera(hoja_asistencia) -> bool:
    valores = hoja_asistencia.get_all_values()

    if not valores:
        hoja_asistencia.append_row(COLUMNAS_ASISTENCIA)
        return True

    headers = [str(x).strip().upper() for x in valores[0]]
    faltantes = [c for c in COLUMNAS_ASISTENCIA if c not in headers]

    if faltantes:
        st.error(
            "La hoja Asistencia tiene una cabecera diferente o incompleta. "
            f"Faltan columnas: {', '.join(faltantes)}. "
            "Para dejarlo limpio, borra la pestaña Asistencia y déjala vacía; el sistema creará la cabecera correcta."
        )
        return False

    return True


def obtener_dias_semana_actual() -> list[int]:
    hoy = datetime.now().date()
    inicio_semana = hoy - timedelta(days=hoy.weekday())  # lunes
    fin_semana = inicio_semana + timedelta(days=6)       # domingo

    # Se permite editar toda la semana actual de lunes a domingo.
    return [
        (inicio_semana + timedelta(days=i)).day
        for i in range(7)
        if (inicio_semana + timedelta(days=i)).month == hoy.month
        and inicio_semana <= (inicio_semana + timedelta(days=i)) <= fin_semana
    ]


def _construir_filas_mes(df_colab: pd.DataFrame, dnis_existentes: set[str]) -> list[list[str]]:
    periodo = _periodo_actual()
    mes = _mes_actual()

    df_colab = _normalizar_columnas(df_colab)

    if "ESTADO" not in df_colab.columns or "DNI" not in df_colab.columns:
        return []

    df_activos = df_colab[
        df_colab["ESTADO"].astype(str).str.strip().str.upper().eq("ACTIVO")
    ].copy()

    registros = []
    for _, row in df_activos.iterrows():
        dni = str(row.get("DNI", "")).strip()
        if not dni or dni in dnis_existentes:
            continue

        fila = {
            "SUPERVISOR": str(row.get("SUPERVISOR A CARGO", "")).strip(),
            "COORDINADOR": str(row.get("COORDINADOR", "")).strip(),
            "DEPARTAMENTO": str(row.get("DEPARTAMENTO", "")).strip(),
            "PROVINCIA": str(row.get("PROVINCIA", "")).strip(),
            "DNI": dni,
            "NOMBRE": str(row.get("NOMBRES", "")).strip(),
            "ESTADO": "ACTIVO",
            "MES": mes,
            "PERIODO": periodo,
        }

        for col in COLUMNAS_DIAS:
            fila[col] = ""

        registros.append([fila.get(col, "") for col in COLUMNAS_ASISTENCIA])

    return registros


def sincronizar_mes_actual(hoja_asistencia, hoja_colaboradores) -> None:
    if not _asegurar_cabecera(hoja_asistencia):
        return

    periodo = _periodo_actual()
    df_asis = _leer_sheet_df(hoja_asistencia)

    if "PERIODO" not in df_asis.columns:
        st.error("No existe la columna PERIODO en Asistencia.")
        return

    dnis_periodo = set(
        df_asis.loc[df_asis["PERIODO"].astype(str).eq(periodo), "DNI"]
        .astype(str).str.strip().tolist()
    ) if "DNI" in df_asis.columns else set()

    data_colab = hoja_colaboradores.get_all_records()
    df_colab = pd.DataFrame(data_colab)
    nuevas_filas = _construir_filas_mes(df_colab, dnis_periodo)

    if nuevas_filas:
        hoja_asistencia.append_rows(nuevas_filas, value_input_option="USER_ENTERED")


def _limpiar_valores_dia(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy().fillna("")
    for col in COLUMNAS_DIAS:
        if col in df.columns:
            df[col] = (
                df[col].astype(str).str.strip().str.upper()
                .replace({"NAN": "", "NONE": ""})
            )
            df[col] = df[col].apply(lambda x: x if x in ["", "A", "F"] else "")
    return df


def _columna_a_letra(num: int) -> str:
    letras = ""
    while num:
        num, rem = divmod(num - 1, 26)
        letras = chr(65 + rem) + letras
    return letras

# =====================================================
# MAIN
# =====================================================
def mostrar_asistencia(hoja_asistencia, hoja_colaboradores):
    st.markdown("## 🗓️ Control de Asistencia")

    if not _asegurar_cabecera(hoja_asistencia):
        return

    periodo = _periodo_actual()

    # Botón manual para evitar escrituras automáticas en cada rerun/selectbox.
    c_sync, c_msg = st.columns([1, 5])
    with c_sync:
        if st.button("🔄 Sincronizar mes", key="btn_sync_asistencia"):
            try:
                sincronizar_mes_actual(hoja_asistencia, hoja_colaboradores)
                st.success("Mes sincronizado correctamente.")
                st.rerun()
            except Exception as e:
                st.error(f"Error sincronizando mes: {e}")
                return
    with c_msg:
        st.caption("Usa sincronizar solo cuando ingresen altas nuevas o al iniciar un mes. Guardar usa escritura masiva, no celda por celda.")

    df_total = _leer_sheet_df(hoja_asistencia)

    for col in COLUMNAS_ASISTENCIA:
        if col not in df_total.columns:
            df_total[col] = ""

    df_total = df_total[COLUMNAS_ASISTENCIA].copy()
    df_total["__ROW_SHEET__"] = df_total.index + 2

    df = df_total[df_total["PERIODO"].astype(str).eq(periodo)].copy()

    if df.empty:
        st.warning("No hay registros para el periodo actual. Presiona 'Sincronizar mes'.")
        return

    supervisores = sorted([x for x in df["SUPERVISOR"].astype(str).unique().tolist() if x.strip()])
    coordinadores = sorted([x for x in df["COORDINADOR"].astype(str).unique().tolist() if x.strip()])

    c1, c2 = st.columns(2)
    with c1:
        filtro_supervisor = st.selectbox("🔍 Supervisor", ["TODOS"] + supervisores, key="asis_supervisor")
    with c2:
        filtro_coord = st.selectbox("🔍 Coordinador", ["TODOS"] + coordinadores, key="asis_coordinador")

    if filtro_supervisor != "TODOS":
        df = df[df["SUPERVISOR"].astype(str).eq(filtro_supervisor)]
    if filtro_coord != "TODOS":
        df = df[df["COORDINADOR"].astype(str).eq(filtro_coord)]

    dias_editables = obtener_dias_semana_actual()
    st.info("Solo editable semana actual de lunes a domingo | A = Asistencia | F = Falta")

    df_grid = df[COLUMNAS_ASISTENCIA + ["__ROW_SHEET__"]].copy()
    df_grid = _limpiar_valores_dia(df_grid)

    gb = GridOptionsBuilder.from_dataframe(df_grid)
    gb.configure_default_column(editable=False, resizable=True, filter=True, sortable=True)
    gb.configure_column("__ROW_SHEET__", hide=True)

    columnas_fijas = ["SUPERVISOR", "COORDINADOR", "DEPARTAMENTO", "PROVINCIA", "DNI", "NOMBRE", "ESTADO"]
    for col in columnas_fijas:
        gb.configure_column(col, editable=False, pinned="left" if col in ["DNI", "NOMBRE"] else None, width=155)

    gb.configure_column("MES", editable=False, width=85)
    gb.configure_column("PERIODO", editable=False, width=110)

    estilo_dia = JsCode("""
    function(params) {
        if(params.value == 'A') {
            return {'backgroundColor': '#C6EFCE', 'color': '#006100', 'fontWeight': 'bold', 'textAlign': 'center'}
        }
        if(params.value == 'F') {
            return {'backgroundColor': '#FFC7CE', 'color': '#9C0006', 'fontWeight': 'bold', 'textAlign': 'center'}
        }
        return {'backgroundColor': 'white', 'color': 'black', 'textAlign': 'center'}
    }
    """)

    for col in COLUMNAS_DIAS:
        numero_dia = int(col.replace("DIA_", ""))
        gb.configure_column(
            col,
            editable=(numero_dia in dias_editables),
            width=90,
            singleClickEdit=True,
            cellEditor="agSelectCellEditor",
            cellEditorParams={"values": ["", "A", "F"]},
            cellStyle=estilo_dia,
        )

    grid_response = AgGrid(
        df_grid,
        gridOptions=gb.build(),
        allow_unsafe_jscode=True,
        theme="streamlit",
        height=520,
        fit_columns_on_grid_load=False,
        update_mode=GridUpdateMode.MANUAL,
        data_return_mode=DataReturnMode.AS_INPUT,
        reload_data=False,
        key="grid_asistencia",
    )

    st.caption("A = Asistencia 🟩 | F = Falta 🟥")

    if st.button("💾 Guardar Asistencia", key="btn_guardar_asistencia"):
        try:
            nuevo_df = pd.DataFrame(grid_response["data"]).fillna("")
            nuevo_df = _limpiar_valores_dia(nuevo_df)

            headers = [str(x).strip().upper() for x in hoja_asistencia.get_all_values()[0]]
            col_index = {col: idx + 1 for idx, col in enumerate(headers)}

            updates = []
            for _, fila in nuevo_df.iterrows():
                row_sheet = int(fila["__ROW_SHEET__"])

                for dia in dias_editables:
                    col = f"DIA_{dia}"
                    if col not in col_index:
                        continue

                    valor_nuevo = str(fila.get(col, "")).strip().upper()
                    valor_original = str(
                        df_total.loc[df_total["__ROW_SHEET__"].eq(row_sheet), col].iloc[0]
                    ).strip().upper()

                    if valor_nuevo != valor_original:
                        letra = _columna_a_letra(col_index[col])
                        updates.append({
                            "range": f"{letra}{row_sheet}",
                            "values": [[valor_nuevo]],
                        })

            if not updates:
                st.info("No hay cambios para guardar.")
                return

            # Una sola llamada batch para evitar error de cuota por update_cell repetido.
            hoja_asistencia.batch_update(updates, value_input_option="USER_ENTERED")

            st.success(f"✅ Asistencia guardada correctamente. Cambios aplicados: {len(updates)}")
            st.rerun()

        except Exception as e:
            st.error(f"❌ Error guardando asistencia: {e}")
