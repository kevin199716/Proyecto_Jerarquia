from datetime import datetime, timedelta

import pandas as pd
import streamlit as st

# =====================================================
# ASISTENCIA OPTIMIZADA
# Reemplazar SOLO este archivo: asistencia.py
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

COLUMNAS_FIJAS_EDITOR = [
    "DNI",
    "NOMBRE",
    "SUPERVISOR",
    "COORDINADOR",
    "DEPARTAMENTO",
    "PROVINCIA",
    "ESTADO",
    "MES",
    "PERIODO",
]

KEY_DF_TOTAL = "asis_df_total_cache"
KEY_DF_ORIGINAL = "asis_df_original_cache"
KEY_HEADERS = "asis_headers_cache"
KEY_LOADED = "asis_loaded"
KEY_LAST_MSG = "asis_last_msg"


# =====================================================
# UTILIDADES
# =====================================================
def normalizar_columnas(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = df.columns.astype(str).str.strip().str.upper()
    return df


def limpiar_texto(valor) -> str:
    valor = "" if pd.isna(valor) else str(valor)
    valor = valor.strip()
    if valor.upper() in ["NONE", "NAN", "NULL"]:
        return ""
    return valor


def limpiar_marca(valor) -> str:
    valor = limpiar_texto(valor).upper()
    if valor in ["A", "F"]:
        return valor
    return ""


def periodo_actual() -> str:
    return datetime.now().strftime("%Y-%m")


def mes_actual() -> str:
    return str(datetime.now().month)


def dias_semana_actual() -> list[int]:
    hoy = datetime.now().date()
    inicio_semana = hoy - timedelta(days=hoy.weekday())

    dias = []
    for i in range(7):
        fecha = inicio_semana + timedelta(days=i)
        if fecha.month == hoy.month:
            dias.append(fecha.day)

    return dias


def letra_columna(numero: int) -> str:
    letras = ""
    while numero:
        numero, resto = divmod(numero - 1, 26)
        letras = chr(65 + resto) + letras
    return letras


def es_promotor(row: pd.Series) -> bool:
    cargo = ""

    for col in ["CARGO (ROL)", "CARGO", "ROL"]:
        if col in row.index:
            cargo = limpiar_texto(row.get(col, "")).upper()
            break

    if not cargo:
        return True

    return "PROMOTOR" in cargo


# =====================================================
# GOOGLE SHEETS
# =====================================================
def validar_o_crear_cabecera(hoja_asistencia) -> bool:
    valores = hoja_asistencia.get_all_values()

    if not valores:
        hoja_asistencia.append_row(
            COLUMNAS_ASISTENCIA,
            value_input_option="USER_ENTERED",
        )
        return True

    headers = [limpiar_texto(x).upper() for x in valores[0]]
    faltantes = [c for c in COLUMNAS_ASISTENCIA if c not in headers]

    if faltantes:
        st.error("La hoja Asistencia tiene cabecera incompleta o diferente.")
        st.write("Columnas faltantes:", faltantes)
        st.warning("Solución rápida: borra SOLO el contenido de la pestaña Asistencia y luego presiona Sincronizar mes.")
        return False

    return True


def leer_asistencia_drive(hoja_asistencia) -> tuple[pd.DataFrame, list[str]]:
    valores = hoja_asistencia.get_all_values()

    if not valores:
        return pd.DataFrame(columns=COLUMNAS_ASISTENCIA), COLUMNAS_ASISTENCIA.copy()

    headers = [limpiar_texto(x).upper() for x in valores[0]]
    data = valores[1:]

    filas = []
    for fila in data:
        fila = list(fila)

        if len(fila) < len(headers):
            fila += [""] * (len(headers) - len(fila))

        if len(fila) > len(headers):
            fila = fila[:len(headers)]

        filas.append(fila)

    df = pd.DataFrame(filas, columns=headers)
    df = df.fillna("").replace("None", "")
    df = normalizar_columnas(df)

    for col in COLUMNAS_ASISTENCIA:
        if col not in df.columns:
            df[col] = ""

    df = df[COLUMNAS_ASISTENCIA].copy()
    df["ROW_SHEET"] = df.index + 2

    for col in COLUMNAS_DIAS:
        df[col] = df[col].apply(limpiar_marca)

    return df, headers


def leer_colaboradores_drive(hoja_colaboradores) -> pd.DataFrame:
    data = hoja_colaboradores.get_all_records()
    df = pd.DataFrame(data)

    if df.empty:
        return pd.DataFrame()

    df = normalizar_columnas(df)
    df = df.fillna("").replace("None", "")

    return df


def obtener_promotores_activos(df_colab: pd.DataFrame) -> pd.DataFrame:
    if df_colab.empty:
        return pd.DataFrame()

    if "DNI" not in df_colab.columns or "ESTADO" not in df_colab.columns:
        return pd.DataFrame()

    df = df_colab.copy()

    df = df[
        df["ESTADO"]
        .astype(str)
        .str.strip()
        .str.upper()
        .eq("ACTIVO")
    ].copy()

    if df.empty:
        return df

    df = df[df.apply(es_promotor, axis=1)].copy()
    df["DNI"] = df["DNI"].astype(str).str.strip()
    df = df[df["DNI"].ne("")].copy()

    return df


def construir_filas_nuevas(df_colab: pd.DataFrame, dnis_existentes_periodo: set[str]) -> list[list[str]]:
    df_promotores = obtener_promotores_activos(df_colab)

    if df_promotores.empty:
        return []

    periodo = periodo_actual()
    mes = mes_actual()
    filas = []

    for _, row in df_promotores.iterrows():
        dni = limpiar_texto(row.get("DNI", ""))

        if not dni or dni in dnis_existentes_periodo:
            continue

        fila = {
            "SUPERVISOR": limpiar_texto(row.get("SUPERVISOR A CARGO", row.get("SUPERVISOR", ""))),
            "COORDINADOR": limpiar_texto(row.get("COORDINADOR", "")),
            "DEPARTAMENTO": limpiar_texto(row.get("DEPARTAMENTO", "")),
            "PROVINCIA": limpiar_texto(row.get("PROVINCIA", "")),
            "DNI": dni,
            "NOMBRE": limpiar_texto(row.get("NOMBRES", row.get("NOMBRE", ""))),
            "ESTADO": "ACTIVO",
            "MES": mes,
            "PERIODO": periodo,
        }

        for col in COLUMNAS_DIAS:
            fila[col] = ""

        filas.append([fila.get(col, "") for col in COLUMNAS_ASISTENCIA])

    return filas


def sincronizar_mes(hoja_asistencia, hoja_colaboradores) -> int:
    if not validar_o_crear_cabecera(hoja_asistencia):
        return 0

    periodo = periodo_actual()
    df_asistencia, _ = leer_asistencia_drive(hoja_asistencia)

    dnis_existentes = set()
    if not df_asistencia.empty:
        dnis_existentes = set(
            df_asistencia.loc[
                df_asistencia["PERIODO"].astype(str).eq(periodo),
                "DNI",
            ]
            .astype(str)
            .str.strip()
            .tolist()
        )

    df_colab = leer_colaboradores_drive(hoja_colaboradores)
    nuevas = construir_filas_nuevas(df_colab, dnis_existentes)

    if nuevas:
        hoja_asistencia.append_rows(
            nuevas,
            value_input_option="USER_ENTERED",
        )

    return len(nuevas)


def cargar_cache_desde_drive(hoja_asistencia) -> None:
    df_total, headers = leer_asistencia_drive(hoja_asistencia)
    st.session_state[KEY_DF_TOTAL] = df_total.copy()
    st.session_state[KEY_DF_ORIGINAL] = df_total.copy()
    st.session_state[KEY_HEADERS] = headers
    st.session_state[KEY_LOADED] = True


# =====================================================
# FILTROS Y ESTILOS
# =====================================================
def lista_opciones(df: pd.DataFrame, columna: str) -> list[str]:
    if df.empty or columna not in df.columns:
        return ["TODOS"]

    valores = (
        df[columna]
        .astype(str)
        .str.strip()
        .replace("", pd.NA)
        .dropna()
        .unique()
        .tolist()
    )

    return ["TODOS"] + sorted(valores)


def filtrar_df(df: pd.DataFrame, supervisor: str, coordinador: str, departamento: str) -> pd.DataFrame:
    resultado = df.copy()

    if supervisor != "TODOS":
        resultado = resultado[resultado["SUPERVISOR"].astype(str).str.strip().eq(supervisor)]

    if coordinador != "TODOS":
        resultado = resultado[resultado["COORDINADOR"].astype(str).str.strip().eq(coordinador)]

    if departamento != "TODOS":
        resultado = resultado[resultado["DEPARTAMENTO"].astype(str).str.strip().eq(departamento)]

    return resultado


def estilo_asistencia(valor: str) -> str:
    valor = limpiar_marca(valor)

    if valor == "A":
        return "background-color:#C6EFCE;color:#006100;font-weight:bold;text-align:center;"

    if valor == "F":
        return "background-color:#FFC7CE;color:#9C0006;font-weight:bold;text-align:center;"

    return "text-align:center;"


def mostrar_espejo_mes(df: pd.DataFrame) -> None:
    if df.empty:
        st.info("No hay datos para mostrar en el espejo mensual.")
        return

    columnas = COLUMNAS_FIJAS_EDITOR + COLUMNAS_DIAS
    df_vista = df[columnas].copy()

    styler = df_vista.style.applymap(
        estilo_asistencia,
        subset=COLUMNAS_DIAS,
    )

    st.dataframe(
        styler,
        use_container_width=True,
        height=420,
    )


# =====================================================
# GUARDADO
# =====================================================
def preparar_updates(df_editado: pd.DataFrame, df_original: pd.DataFrame, headers: list[str], cols_editables: list[str]) -> list[dict]:
    mapa_col = {
        limpiar_texto(col).upper(): idx + 1
        for idx, col in enumerate(headers)
    }

    updates = []

    for _, row in df_editado.iterrows():
        try:
            row_sheet = int(row["ROW_SHEET"])
        except Exception:
            continue

        original_match = df_original[df_original["ROW_SHEET"].eq(row_sheet)]
        if original_match.empty:
            continue

        original = original_match.iloc[0]

        for col in cols_editables:
            if col not in mapa_col:
                continue

            nuevo = limpiar_marca(row.get(col, ""))
            anterior = limpiar_marca(original.get(col, ""))

            if nuevo != anterior:
                letra = letra_columna(mapa_col[col])
                updates.append({
                    "range": f"{letra}{row_sheet}",
                    "values": [[nuevo]],
                })

    return updates


def actualizar_cache_con_editado(df_editado: pd.DataFrame, cols_editables: list[str]) -> None:
    if KEY_DF_TOTAL not in st.session_state:
        return

    df_total = st.session_state[KEY_DF_TOTAL].copy()

    for _, row in df_editado.iterrows():
        try:
            row_sheet = int(row["ROW_SHEET"])
        except Exception:
            continue

        mask = df_total["ROW_SHEET"].eq(row_sheet)

        for col in cols_editables:
            if col in df_total.columns:
                df_total.loc[mask, col] = limpiar_marca(row.get(col, ""))

    st.session_state[KEY_DF_TOTAL] = df_total.copy()
    st.session_state[KEY_DF_ORIGINAL] = df_total.copy()


# =====================================================
# MAIN
# =====================================================
def mostrar_asistencia(hoja_asistencia, hoja_colaboradores, registro_mod=None, razon=None):
    st.subheader("🗓️ Control de Asistencia")

    if not validar_o_crear_cabecera(hoja_asistencia):
        return

    periodo = periodo_actual()
    dias_editables_num = dias_semana_actual()
    cols_editables = [f"DIA_{d}" for d in dias_editables_num]

    c1, c2, c3 = st.columns([1, 1, 5])

    with c1:
        if st.button("🔄 Sincronizar mes", key="btn_sync_asistencia"):
            try:
                nuevos = sincronizar_mes(hoja_asistencia, hoja_colaboradores)
                cargar_cache_desde_drive(hoja_asistencia)
                st.success(f"Mes sincronizado. Registros nuevos: {nuevos}")
            except Exception as e:
                st.error(f"Error sincronizando mes: {e}")
                return

    with c2:
        if st.button("♻️ Recargar Drive", key="btn_reload_asistencia"):
            try:
                cargar_cache_desde_drive(hoja_asistencia)
                st.success("Datos recargados desde Drive.")
            except Exception as e:
                st.error(f"Error recargando Drive: {e}")
                return

    with c3:
        st.info(
            "Se muestra DIA_1 a DIA_31. Solo se puede editar la semana actual. "
            "Los cambios se escriben en Drive solo al presionar Guardar Asistencia."
        )

    if not st.session_state.get(KEY_LOADED):
        try:
            cargar_cache_desde_drive(hoja_asistencia)
        except Exception as e:
            st.error(f"Error cargando asistencia desde Drive: {e}")
            return

    df_total = st.session_state[KEY_DF_TOTAL].copy()
    df_original = st.session_state[KEY_DF_ORIGINAL].copy()
    headers = st.session_state.get(KEY_HEADERS, COLUMNAS_ASISTENCIA)

    for col in COLUMNAS_ASISTENCIA:
        if col not in df_total.columns:
            df_total[col] = ""
        if col not in df_original.columns:
            df_original[col] = ""

    df_mes = df_total[df_total["PERIODO"].astype(str).eq(periodo)].copy()

    if df_mes.empty:
        st.warning("No hay registros del periodo actual. Presiona Sincronizar mes.")
        return

    f1, f2, f3 = st.columns(3)

    with f1:
        filtro_supervisor = st.selectbox(
            "Supervisor",
            lista_opciones(df_mes, "SUPERVISOR"),
            key="asis_supervisor",
        )

    df_base_coord = filtrar_df(df_mes, filtro_supervisor, "TODOS", "TODOS")

    with f2:
        filtro_coord = st.selectbox(
            "Coordinador",
            lista_opciones(df_base_coord, "COORDINADOR"),
            key="asis_coordinador",
        )

    df_base_dep = filtrar_df(df_base_coord, "TODOS", filtro_coord, "TODOS")

    with f3:
        filtro_dep = st.selectbox(
            "Departamento",
            lista_opciones(df_base_dep, "DEPARTAMENTO"),
            key="asis_departamento",
        )

    df_filtrado = filtrar_df(df_mes, filtro_supervisor, filtro_coord, filtro_dep)

    if df_filtrado.empty:
        st.warning("No hay registros con los filtros seleccionados.")
        return

    total_filtrado = len(df_filtrado)

    st.caption(
        f"Registros encontrados: {total_filtrado} | Columnas editables esta semana: {', '.join(cols_editables)}"
    )

    if total_filtrado > 300:
        st.warning(
            "Hay muchos registros en pantalla. Para evitar cuelgues, filtra por supervisor/coordinador/departamento "
            "o trabaja por bloques de 300."
        )
        cantidad = st.slider(
            "Cantidad de registros a mostrar",
            min_value=50,
            max_value=300,
            value=100,
            step=50,
            key="asis_limite",
        )
    else:
        cantidad = total_filtrado

    df_filtrado = df_filtrado.head(cantidad).copy()

    st.markdown("### Editar asistencia")

    columnas_editor = COLUMNAS_FIJAS_EDITOR + COLUMNAS_DIAS + ["ROW_SHEET"]
    df_editor = df_filtrado[columnas_editor].copy()

    for col in COLUMNAS_DIAS:
        df_editor[col] = df_editor[col].apply(limpiar_marca)

    disabled_cols = [col for col in df_editor.columns if col not in cols_editables]

    column_config = {"ROW_SHEET": None}

    for col in COLUMNAS_DIAS:
        column_config[col] = st.column_config.SelectboxColumn(
            col,
            options=["", "A", "F"],
            width="small",
        )

    editado = st.data_editor(
        df_editor,
        use_container_width=True,
        height=520,
        hide_index=True,
        disabled=disabled_cols,
        column_config=column_config,
        num_rows="fixed",
        key="editor_asistencia_mes_completo",
    )

    if st.button("💾 Guardar Asistencia", key="btn_guardar_asistencia"):
        try:
            df_editado = pd.DataFrame(editado).fillna("")

            updates = preparar_updates(
                df_editado=df_editado,
                df_original=df_original,
                headers=headers,
                cols_editables=cols_editables,
            )

            if not updates:
                st.info("No se detectaron cambios para guardar.")
            else:
                hoja_asistencia.batch_update(
                    updates,
                    value_input_option="USER_ENTERED",
                )

                actualizar_cache_con_editado(df_editado, cols_editables)

                st.success(f"✅ Asistencia guardada correctamente. Cambios aplicados: {len(updates)}")

        except Exception as e:
            st.error(f"❌ Error guardando asistencia: {e}")

    st.markdown("### Espejo mensual completo DIA_1 a DIA_31")
    mostrar_espejo_mes(df_filtrado)

    if registro_mod is not None:
        st.divider()
        st.subheader("📋 Matriz de jerarquía")
        try:
            registro_mod.mostrar_tabla(hoja_colaboradores, razon)
        except Exception as e:
            st.warning(f"No se pudo cargar la matriz inferior de jerarquía: {e}")
