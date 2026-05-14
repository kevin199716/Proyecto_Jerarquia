from datetime import datetime, timedelta

import pandas as pd
import streamlit as st

try:
    from st_aggrid import (
        AgGrid,
        GridOptionsBuilder,
        GridUpdateMode,
        JsCode,
        DataReturnMode,
    )
except Exception:
    AgGrid = None
    GridOptionsBuilder = None
    GridUpdateMode = None
    JsCode = None
    DataReturnMode = None


# =====================================================
# CONFIG ASISTENCIA
# =====================================================
COLUMNAS_BASE = [
    "SUPERVISOR",
    "COORDINADOR",
    "DEPARTAMENTO",
    "PROVINCIA",
    "DNI",
    "NOMBRE",
    "ESTADO",
    "MES",
    "PERIODO",
]

COLUMNAS_DIAS = [f"DIA_{i}" for i in range(1, 32)]
COLUMNAS_ASISTENCIA = COLUMNAS_BASE + COLUMNAS_DIAS

VALORES_ASISTENCIA = ["", "A", "F"]


# =====================================================
# ESTILOS
# =====================================================
def pintar_estilos_asistencia():
    st.markdown(
        """
        <style>
            .asis-info {
                background: #EAF2FF;
                border-left: 6px solid #0D6EFD;
                padding: 10px 14px;
                border-radius: 10px;
                margin-bottom: 10px;
            }
            .asis-alerta {
                background: #FFF2F2;
                border-left: 6px solid #DC3545;
                padding: 10px 14px;
                border-radius: 10px;
                margin-bottom: 10px;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


# =====================================================
# UTILIDADES
# =====================================================
def normalizar_columnas(df):
    df = df.copy()
    df.columns = df.columns.astype(str).str.strip().str.upper()
    return df


def periodo_actual():
    return datetime.now().strftime("%Y-%m")


def mes_actual():
    return str(datetime.now().month)


def numero_a_letra(n):
    letras = ""
    while n:
        n, rem = divmod(n - 1, 26)
        letras = chr(65 + rem) + letras
    return letras


def dias_semana_actual():
    hoy = datetime.now().date()
    inicio = hoy - timedelta(days=hoy.weekday())
    dias = []

    for i in range(7):
        fecha = inicio + timedelta(days=i)
        if fecha.month == hoy.month:
            dias.append(fecha.day)

    return dias


def columnas_semana_actual():
    return [f"DIA_{d}" for d in dias_semana_actual()]


def limpiar_marca(valor):
    valor = str(valor).strip().upper()
    if valor in VALORES_ASISTENCIA:
        return valor
    return ""


# =====================================================
# GOOGLE SHEETS - LECTURA / CABECERA
# =====================================================
def leer_sheet_df(hoja):
    valores = hoja.get_all_values()

    if not valores:
        return pd.DataFrame(columns=COLUMNAS_ASISTENCIA)

    headers = [str(x).strip().upper() for x in valores[0]]
    data = valores[1:]

    filas_ok = []
    for fila in data:
        fila = list(fila)
        if len(fila) < len(headers):
            fila += [""] * (len(headers) - len(fila))
        if len(fila) > len(headers):
            fila = fila[:len(headers)]
        filas_ok.append(fila)

    df = pd.DataFrame(filas_ok, columns=headers)
    df = df.fillna("").replace("None", "")
    return normalizar_columnas(df)


def validar_o_crear_cabecera(hoja):
    valores = hoja.get_all_values()

    if not valores:
        hoja.append_row(COLUMNAS_ASISTENCIA, value_input_option="USER_ENTERED")
        return True

    headers = [str(x).strip().upper() for x in valores[0]]
    faltantes = [c for c in COLUMNAS_ASISTENCIA if c not in headers]

    if faltantes:
        st.error(
            "La hoja Asistencia tiene cabeceras incorrectas. "
            "Borra solo el contenido de la pestaña Asistencia y vuelve a sincronizar. "
            f"Columnas faltantes: {', '.join(faltantes)}"
        )
        return False

    return True


# =====================================================
# SINCRONIZACION
# =====================================================
def obtener_colaboradores_activos(hoja_colaboradores, razon=None, rol=None):
    data = hoja_colaboradores.get_all_records()
    df = pd.DataFrame(data)

    if df.empty:
        return pd.DataFrame()

    df = normalizar_columnas(df)

    for col in ["ESTADO", "DNI"]:
        if col not in df.columns:
            return pd.DataFrame()

    df["DNI"] = df["DNI"].astype(str).str.strip()
    df["ESTADO"] = df["ESTADO"].astype(str).str.strip().str.upper()

    df = df[df["ESTADO"].eq("ACTIVO")].copy()

    if rol == "dealer" and razon and "RAZON SOCIAL" in df.columns:
        df = df[df["RAZON SOCIAL"].astype(str).str.strip().eq(str(razon).strip())].copy()

    return df


def construir_filas_nuevas(df_colab, dnis_existentes):
    periodo = periodo_actual()
    mes = mes_actual()
    nuevas = []

    for _, row in df_colab.iterrows():
        dni = str(row.get("DNI", "")).strip()

        if not dni or dni in dnis_existentes:
            continue

        fila = {
            "SUPERVISOR": str(row.get("SUPERVISOR A CARGO", row.get("SUPERVISOR", ""))).strip(),
            "COORDINADOR": str(row.get("COORDINADOR", "")).strip(),
            "DEPARTAMENTO": str(row.get("DEPARTAMENTO", "")).strip(),
            "PROVINCIA": str(row.get("PROVINCIA", "")).strip(),
            "DNI": dni,
            "NOMBRE": str(row.get("NOMBRES", row.get("NOMBRE", ""))).strip(),
            "ESTADO": "ACTIVO",
            "MES": mes,
            "PERIODO": periodo,
        }

        for col in COLUMNAS_DIAS:
            fila[col] = ""

        nuevas.append([fila.get(col, "") for col in COLUMNAS_ASISTENCIA])

    return nuevas


def sincronizar_asistencia(hoja_asistencia, hoja_colaboradores, razon=None, rol=None):
    if not validar_o_crear_cabecera(hoja_asistencia):
        return 0

    periodo = periodo_actual()
    df_asis = leer_sheet_df(hoja_asistencia)

    dnis_existentes = set()
    if not df_asis.empty and "PERIODO" in df_asis.columns and "DNI" in df_asis.columns:
        dnis_existentes = set(
            df_asis.loc[df_asis["PERIODO"].astype(str).eq(periodo), "DNI"]
            .astype(str)
            .str.strip()
            .tolist()
        )

    df_colab = obtener_colaboradores_activos(hoja_colaboradores, razon=razon, rol=rol)
    nuevas = construir_filas_nuevas(df_colab, dnis_existentes)

    if nuevas:
        hoja_asistencia.append_rows(nuevas, value_input_option="USER_ENTERED")

    return len(nuevas)


# =====================================================
# PREPARAR DATA VISIBLE
# =====================================================
def preparar_df_visible(df_total, razon=None, rol=None):
    periodo = periodo_actual()

    for col in COLUMNAS_ASISTENCIA:
        if col not in df_total.columns:
            df_total[col] = ""

    df_total = df_total[COLUMNAS_ASISTENCIA].copy()
    df_total["ROW_SHEET"] = df_total.index + 2

    df = df_total[df_total["PERIODO"].astype(str).eq(periodo)].copy()

    if rol == "dealer" and razon and "RAZON SOCIAL" in df.columns:
        df = df[df["RAZON SOCIAL"].astype(str).str.strip().eq(str(razon).strip())].copy()

    return df


def aplicar_filtros(df):
    c1, c2, c3, c4 = st.columns(4)

    with c1:
        supervisores = sorted([x for x in df["SUPERVISOR"].astype(str).unique() if x.strip()])
        supervisor = st.selectbox("Supervisor", ["TODOS"] + supervisores, key="asis_filtro_supervisor")

    with c2:
        coordinadores = sorted([x for x in df["COORDINADOR"].astype(str).unique() if x.strip()])
        coordinador = st.selectbox("Coordinador", ["TODOS"] + coordinadores, key="asis_filtro_coordinador")

    with c3:
        departamentos = sorted([x for x in df["DEPARTAMENTO"].astype(str).unique() if x.strip()])
        departamento = st.selectbox("Departamento", ["TODOS"] + departamentos, key="asis_filtro_departamento")

    with c4:
        buscar = st.text_input("Buscar DNI / Nombre", key="asis_buscar_texto")

    df_filtrado = df.copy()

    if supervisor != "TODOS":
        df_filtrado = df_filtrado[df_filtrado["SUPERVISOR"].astype(str).eq(supervisor)]

    if coordinador != "TODOS":
        df_filtrado = df_filtrado[df_filtrado["COORDINADOR"].astype(str).eq(coordinador)]

    if departamento != "TODOS":
        df_filtrado = df_filtrado[df_filtrado["DEPARTAMENTO"].astype(str).eq(departamento)]

    if buscar.strip():
        patron = buscar.strip().upper()
        df_filtrado = df_filtrado[
            df_filtrado["DNI"].astype(str).str.upper().str.contains(patron, na=False)
            | df_filtrado["NOMBRE"].astype(str).str.upper().str.contains(patron, na=False)
        ].copy()

    return df_filtrado


# =====================================================
# GUARDADO
# =====================================================
def guardar_cambios(hoja_asistencia, df_original, df_editado, cols_editables):
    valores = hoja_asistencia.get_all_values()

    if not valores:
        raise ValueError("La hoja Asistencia está vacía. Sincroniza primero.")

    headers = [str(x).strip().upper() for x in valores[0]]
    mapa_col = {col: idx + 1 for idx, col in enumerate(headers)}

    updates = []

    original_idx = df_original.set_index("ROW_SHEET", drop=False)

    for _, fila in df_editado.iterrows():
        row_sheet = int(fila["ROW_SHEET"])

        if row_sheet not in original_idx.index:
            continue

        for col in cols_editables:
            if col not in mapa_col:
                continue

            nuevo = limpiar_marca(fila.get(col, ""))
            original = limpiar_marca(original_idx.loc[row_sheet, col])

            if nuevo != original:
                letra = numero_a_letra(mapa_col[col])
                updates.append({
                    "range": f"{letra}{row_sheet}",
                    "values": [[nuevo]],
                })

    if updates:
        hoja_asistencia.batch_update(updates, value_input_option="USER_ENTERED")

    return len(updates)


# =====================================================
# EDITOR AGGRID
# =====================================================
def mostrar_editor_aggrid(df_visible, cols_semana):
    if AgGrid is None:
        st.error("Falta instalar streamlit-aggrid. Agrega streamlit-aggrid en requirements.txt")
        return None

    columnas_mostrar = [
        "SUPERVISOR",
        "COORDINADOR",
        "DEPARTAMENTO",
        "PROVINCIA",
        "DNI",
        "NOMBRE",
    ] + cols_semana + ["ROW_SHEET"]

    df_grid = df_visible[columnas_mostrar].copy()

    for col in cols_semana:
        df_grid[col] = df_grid[col].apply(limpiar_marca)

    gb = GridOptionsBuilder.from_dataframe(df_grid)

    gb.configure_default_column(
        editable=False,
        filter=True,
        sortable=True,
        resizable=True,
    )

    gb.configure_column("ROW_SHEET", hide=True)

    for col in ["SUPERVISOR", "COORDINADOR", "DEPARTAMENTO", "PROVINCIA", "DNI", "NOMBRE"]:
        gb.configure_column(col, editable=False, pinned="left" if col in ["DNI", "NOMBRE"] else None, width=155)

    estilo = JsCode(
        """
        function(params) {
            if (params.value == 'A') {
                return {'backgroundColor': '#C6EFCE', 'color': '#006100', 'fontWeight': 'bold', 'textAlign': 'center'};
            }
            if (params.value == 'F') {
                return {'backgroundColor': '#FFC7CE', 'color': '#9C0006', 'fontWeight': 'bold', 'textAlign': 'center'};
            }
            return {'backgroundColor': '#FFFFFF', 'color': '#000000', 'textAlign': 'center'};
        }
        """
    )

    for col in cols_semana:
        gb.configure_column(
            col,
            editable=True,
            width=92,
            singleClickEdit=True,
            cellEditor="agSelectCellEditor",
            cellEditorParams={"values": VALORES_ASISTENCIA},
            cellStyle=estilo,
        )

    grid_options = gb.build()
    grid_options["stopEditingWhenCellsLoseFocus"] = True
    grid_options["suppressCellFocus"] = False

    response = AgGrid(
        df_grid,
        gridOptions=grid_options,
        allow_unsafe_jscode=True,
        theme="streamlit",
        height=520,
        fit_columns_on_grid_load=False,
        update_mode=GridUpdateMode.MODEL_CHANGED,
        data_return_mode=DataReturnMode.FILTERED_AND_SORTED,
        reload_data=False,
        key="asis_grid_v4",
    )

    return pd.DataFrame(response["data"])


# =====================================================
# MAIN
# =====================================================
def mostrar_asistencia(hoja_asistencia, hoja_colaboradores, razon=None, rol=None):
    pintar_estilos_asistencia()

    st.subheader("🗓️ Asistencia")

    st.markdown(
        """
        <div class="asis-info">
            Marca solo <b>A</b> o <b>F</b>. La edición queda limitada a la semana actual.
            El guardado viaja a Google Sheets únicamente al presionar <b>Guardar Asistencia</b>.
        </div>
        """,
        unsafe_allow_html=True,
    )

    if not validar_o_crear_cabecera(hoja_asistencia):
        return

    c_sync, c_status = st.columns([1, 4])

    with c_sync:
        sincronizar = st.button("🔄 Sincronizar mes", key="asis_btn_sync")

    with c_status:
        st.caption("Sincroniza cuando ingresen altas nuevas o al iniciar un mes. No borra marcaciones previas.")

    if sincronizar:
        with st.spinner("Sincronizando activos con Asistencia..."):
            try:
                cantidad = sincronizar_asistencia(
                    hoja_asistencia,
                    hoja_colaboradores,
                    razon=razon,
                    rol=rol,
                )
                st.success(f"Sincronización correcta. Nuevos registros agregados: {cantidad}")
            except Exception as e:
                st.error(f"Error sincronizando asistencia: {e}")
                st.exception(e)
                return

    try:
        df_total = leer_sheet_df(hoja_asistencia)
    except Exception as e:
        st.error(f"Error leyendo la hoja Asistencia: {e}")
        st.exception(e)
        return

    if df_total.empty:
        st.warning("La hoja Asistencia está vacía. Presiona Sincronizar mes.")
        return

    df_periodo = preparar_df_visible(df_total, razon=razon, rol=rol)

    if df_periodo.empty:
        st.warning("No hay registros del periodo actual. Presiona Sincronizar mes.")
        return

    df_filtrado = aplicar_filtros(df_periodo)

    if df_filtrado.empty:
        st.warning("No hay registros con los filtros seleccionados.")
        return

    limite_filas = st.slider(
        "Cantidad de registros a mostrar",
        min_value=20,
        max_value=300,
        value=min(80, max(20, len(df_filtrado))),
        step=20,
        key="asis_limite_filas",
    )

    df_visible = df_filtrado.head(limite_filas).copy()
    cols_semana = columnas_semana_actual()

    st.caption(f"Registros visibles: {len(df_visible)} de {len(df_filtrado)} | Columnas editables: {', '.join(cols_semana)}")

    df_editado = mostrar_editor_aggrid(df_visible, cols_semana)

    st.markdown(
        """
        <div class="asis-alerta">
            Importante: después de marcar, presiona <b>Guardar Asistencia</b>. Si cambias de filtro antes de guardar, puedes perder cambios no guardados.
        </div>
        """,
        unsafe_allow_html=True,
    )

    if st.button("💾 Guardar Asistencia", key="asis_btn_guardar"):
        if df_editado is None or df_editado.empty:
            st.warning("No hay información capturada para guardar.")
            return

        with st.spinner("Guardando marcaciones en Google Sheets..."):
            try:
                cambios = guardar_cambios(
                    hoja_asistencia=hoja_asistencia,
                    df_original=df_visible,
                    df_editado=df_editado,
                    cols_editables=cols_semana,
                )

                if cambios == 0:
                    st.info("No se detectaron cambios nuevos para guardar.")
                else:
                    st.success(f"✅ Asistencia guardada correctamente. Celdas actualizadas: {cambios}")

            except Exception as e:
                st.error(f"Error guardando asistencia: {e}")
                st.exception(e)
                return
