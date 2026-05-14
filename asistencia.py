from datetime import datetime, timedelta

import pandas as pd
import streamlit as st

# =====================================================
# CONFIGURACIÓN GENERAL
# =====================================================
NOMBRE_HOJA_ASISTENCIA = "Asistencia"

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

COLUMNAS_DIAS = [f"DIA_{i}" for i in range(1, 32)]
COLUMNAS_ASISTENCIA = COLUMNAS_BASE + COLUMNAS_DIAS

COLUMNAS_VISIBLES_BASE = [
    "DNI",
    "NOMBRE",
    "SUPERVISOR",
    "COORDINADOR",
    "DEPARTAMENTO",
    "PROVINCIA",
    "ESTADO",
    "MES",
    "PERIODO"
]


# =====================================================
# UTILIDADES
# =====================================================
def normalizar_columnas(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = df.columns.astype(str).str.strip().str.upper()
    return df


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


def limpiar_texto(valor) -> str:
    return str(valor).strip()


def limpiar_marca(valor) -> str:
    valor = str(valor).strip().upper()

    if valor in ["A", "F", ""]:
        return valor

    return ""


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
            cargo = str(row.get(col, "")).strip().upper()
            break

    if not cargo:
        return True

    return "PROMOTOR" in cargo


# =====================================================
# LECTURA DE GOOGLE SHEETS
# =====================================================
def leer_asistencia(hoja_asistencia) -> pd.DataFrame:
    valores = hoja_asistencia.get_all_values()

    if not valores:
        return pd.DataFrame(columns=COLUMNAS_ASISTENCIA)

    headers = [str(x).strip().upper() for x in valores[0]]
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

    return df


def leer_colaboradores(hoja_colaboradores) -> pd.DataFrame:
    data = hoja_colaboradores.get_all_records()
    df = pd.DataFrame(data)

    if df.empty:
        return pd.DataFrame()

    df = normalizar_columnas(df)
    df = df.fillna("").replace("None", "")

    return df


def validar_o_crear_cabecera(hoja_asistencia) -> bool:
    valores = hoja_asistencia.get_all_values()

    if not valores:
        hoja_asistencia.append_row(
            COLUMNAS_ASISTENCIA,
            value_input_option="USER_ENTERED"
        )
        return True

    headers = [str(x).strip().upper() for x in valores[0]]
    faltantes = [c for c in COLUMNAS_ASISTENCIA if c not in headers]

    if faltantes:
        st.error("La hoja Asistencia tiene cabecera incompleta.")
        st.write("Columnas faltantes:", faltantes)
        st.warning(
            "Solución rápida: borra SOLO el contenido de la hoja Asistencia "
            "y vuelve a presionar Sincronizar mes."
        )
        return False

    return True


# =====================================================
# FILTRO DE PROMOTORES ACTIVOS
# =====================================================
def obtener_promotores_activos(df_colab: pd.DataFrame) -> pd.DataFrame:
    if df_colab.empty:
        return pd.DataFrame()

    if "ESTADO" not in df_colab.columns or "DNI" not in df_colab.columns:
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

    df = df[
        df.apply(es_promotor, axis=1)
    ].copy()

    df["DNI"] = df["DNI"].astype(str).str.strip()

    df = df[df["DNI"].ne("")].copy()

    return df


def obtener_dnis_promotores_activos(df_colab: pd.DataFrame) -> set[str]:
    df_promotores = obtener_promotores_activos(df_colab)

    if df_promotores.empty:
        return set()

    return set(df_promotores["DNI"].astype(str).str.strip().tolist())


# =====================================================
# SINCRONIZACIÓN DEL MES
# =====================================================
def construir_registros_nuevos(
    df_colab: pd.DataFrame,
    dnis_existentes_periodo: set[str]
) -> list[list[str]]:

    df_promotores = obtener_promotores_activos(df_colab)

    if df_promotores.empty:
        return []

    periodo = periodo_actual()
    mes = mes_actual()

    registros = []

    for _, row in df_promotores.iterrows():
        dni = limpiar_texto(row.get("DNI", ""))

        if not dni:
            continue

        if dni in dnis_existentes_periodo:
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

        registros.append([fila.get(col, "") for col in COLUMNAS_ASISTENCIA])

    return registros


def sincronizar_mes(hoja_asistencia, hoja_colaboradores) -> int:
    if not validar_o_crear_cabecera(hoja_asistencia):
        return 0

    periodo = periodo_actual()

    df_asistencia = leer_asistencia(hoja_asistencia)

    dnis_existentes = set()
    if not df_asistencia.empty and "PERIODO" in df_asistencia.columns and "DNI" in df_asistencia.columns:
        dnis_existentes = set(
            df_asistencia.loc[
                df_asistencia["PERIODO"].astype(str).eq(periodo),
                "DNI"
            ].astype(str).str.strip().tolist()
        )

    df_colab = leer_colaboradores(hoja_colaboradores)

    nuevos = construir_registros_nuevos(
        df_colab,
        dnis_existentes
    )

    if nuevos:
        hoja_asistencia.append_rows(
            nuevos,
            value_input_option="USER_ENTERED"
        )

    return len(nuevos)


# =====================================================
# ESTILO COLORES
# =====================================================
def estilo_asistencia(valor):
    valor = str(valor).strip().upper()

    if valor == "A":
        return "background-color:#C6EFCE;color:#006100;font-weight:bold;text-align:center;"

    if valor == "F":
        return "background-color:#FFC7CE;color:#9C0006;font-weight:bold;text-align:center;"

    return "text-align:center;"


def mostrar_vista_colores(df: pd.DataFrame):
    if df.empty:
        return

    columnas_dias_presentes = [
        c for c in COLUMNAS_DIAS
        if c in df.columns
    ]

    styler = df.style.applymap(
        estilo_asistencia,
        subset=columnas_dias_presentes
    )

    st.dataframe(
        styler,
        use_container_width=True,
        height=360
    )


# =====================================================
# FILTROS
# =====================================================
def lista_opciones(df: pd.DataFrame, columna: str) -> list[str]:
    if columna not in df.columns:
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

    valores = sorted(valores)

    return ["TODOS"] + valores


def aplicar_filtros(
    df: pd.DataFrame,
    filtro_supervisor: str,
    filtro_coord: str,
    filtro_dep: str
) -> pd.DataFrame:

    resultado = df.copy()

    if filtro_supervisor != "TODOS":
        resultado = resultado[
            resultado["SUPERVISOR"].astype(str).str.strip().eq(filtro_supervisor)
        ]

    if filtro_coord != "TODOS":
        resultado = resultado[
            resultado["COORDINADOR"].astype(str).str.strip().eq(filtro_coord)
        ]

    if filtro_dep != "TODOS":
        resultado = resultado[
            resultado["DEPARTAMENTO"].astype(str).str.strip().eq(filtro_dep)
        ]

    return resultado


# =====================================================
# GUARDADO
# =====================================================
def preparar_updates(
    df_editado: pd.DataFrame,
    df_total: pd.DataFrame,
    headers: list[str],
    cols_editables: list[str]
) -> list[dict]:

    mapa_col = {
        str(col).strip().upper(): idx + 1
        for idx, col in enumerate(headers)
    }

    updates = []

    for _, row in df_editado.iterrows():
        try:
            row_sheet = int(row["ROW_SHEET"])
        except Exception:
            continue

        original = df_total[
            df_total["ROW_SHEET"].eq(row_sheet)
        ]

        if original.empty:
            continue

        original = original.iloc[0]

        for col in cols_editables:
            if col not in mapa_col:
                continue

            nuevo = limpiar_marca(row.get(col, ""))
            anterior = limpiar_marca(original.get(col, ""))

            if nuevo != anterior:
                letra = letra_columna(mapa_col[col])
                updates.append({
                    "range": f"{letra}{row_sheet}",
                    "values": [[nuevo]]
                })

    return updates


# =====================================================
# MAIN
# =====================================================
def mostrar_asistencia(
    hoja_asistencia,
    hoja_colaboradores,
    registro_mod=None,
    razon=None
):

    st.subheader("🗓️ Control de Asistencia")

    if not validar_o_crear_cabecera(hoja_asistencia):
        return

    periodo = periodo_actual()

    dias_editables_num = dias_semana_actual()
    cols_editables = [f"DIA_{d}" for d in dias_editables_num]

    # =================================================
    # SINCRONIZAR
    # =================================================
    c_sync, c_info = st.columns([1, 5])

    with c_sync:
        if st.button("🔄 Sincronizar mes", key="btn_sync_asistencia"):
            try:
                creados = sincronizar_mes(
                    hoja_asistencia,
                    hoja_colaboradores
                )
                st.success(f"Sincronización correcta. Registros nuevos: {creados}")
            except Exception as e:
                st.error(f"Error sincronizando asistencia: {e}")
                return

    with c_info:
        st.info(
            "Se muestran DIA_1 a DIA_31. "
            "Solo se edita la semana actual. "
            "A = Asistencia | F = Falta."
        )

    # =================================================
    # LEER DATA
    # =================================================
    df_colab = leer_colaboradores(hoja_colaboradores)
    dnis_promotores = obtener_dnis_promotores_activos(df_colab)

    df_total = leer_asistencia(hoja_asistencia)

    for col in COLUMNAS_ASISTENCIA:
        if col not in df_total.columns:
            df_total[col] = ""

    df_total = df_total[COLUMNAS_ASISTENCIA].copy()
    df_total["ROW_SHEET"] = df_total.index + 2

    df_mes = df_total[
        df_total["PERIODO"]
        .astype(str)
        .eq(periodo)
    ].copy()

    if dnis_promotores:
        df_mes = df_mes[
            df_mes["DNI"]
            .astype(str)
            .str.strip()
            .isin(dnis_promotores)
        ].copy()

    if df_mes.empty:
        st.warning(
            "No hay promotores activos para el periodo actual. "
            "Presiona Sincronizar mes o valida que el cargo contenga PROMOTOR."
        )
        return

    # =================================================
    # FILTROS
    # =================================================
    f1, f2, f3 = st.columns(3)

    with f1:
        filtro_supervisor = st.selectbox(
            "Supervisor",
            lista_opciones(df_mes, "SUPERVISOR"),
            key="asis_filtro_supervisor"
        )

    df_temp = aplicar_filtros(
        df_mes,
        filtro_supervisor,
        "TODOS",
        "TODOS"
    )

    with f2:
        filtro_coord = st.selectbox(
            "Coordinador",
            lista_opciones(df_temp, "COORDINADOR"),
            key="asis_filtro_coordinador"
        )

    df_temp = aplicar_filtros(
        df_temp,
        "TODOS",
        filtro_coord,
        "TODOS"
    )

    with f3:
        filtro_dep = st.selectbox(
            "Departamento",
            lista_opciones(df_temp, "DEPARTAMENTO"),
            key="asis_filtro_departamento"
        )

    df_filtrado = aplicar_filtros(
        df_mes,
        filtro_supervisor,
        filtro_coord,
        filtro_dep
    )

    if df_filtrado.empty:
        st.warning("No hay registros con los filtros seleccionados.")
        return

    total_filtrado = len(df_filtrado)

    # =================================================
    # LIMITE DE FILAS SIN ERROR RANGE
    # =================================================
    if total_filtrado <= 300:
        cantidad_mostrar = total_filtrado
        st.caption(f"Registros visibles: {cantidad_mostrar} de {total_filtrado}")
    else:
        cantidad_mostrar = st.slider(
            "Cantidad de registros a mostrar",
            min_value=20,
            max_value=300,
            value=100,
            step=20,
            key="asis_cantidad_mostrar"
        )
        st.caption(f"Registros visibles: {cantidad_mostrar} de {total_filtrado}")

    df_filtrado = df_filtrado.head(cantidad_mostrar).copy()

    # =================================================
    # EDITOR
    # =================================================
    columnas_editor = COLUMNAS_VISIBLES_BASE + COLUMNAS_DIAS + ["ROW_SHEET"]

    df_editor = df_filtrado[columnas_editor].copy()

    for col in COLUMNAS_DIAS:
        df_editor[col] = df_editor[col].apply(limpiar_marca)

    disabled_cols = [
        col for col in df_editor.columns
        if col not in cols_editables
    ]

    column_config = {}
    for col in COLUMNAS_DIAS:
        column_config[col] = st.column_config.SelectboxColumn(
            col,
            options=["", "A", "F"],
            width="small"
        )

    st.caption(
        "Columnas editables esta semana: "
        + ", ".join(cols_editables)
    )

    with st.form("form_guardar_asistencia", clear_on_submit=False):
        editado = st.data_editor(
            df_editor,
            use_container_width=True,
            height=530,
            hide_index=True,
            disabled=disabled_cols,
            column_config=column_config,
            num_rows="fixed",
            key="editor_asistencia"
        )

        guardar = st.form_submit_button("💾 Guardar Asistencia")

    if guardar:
        try:
            df_editado = pd.DataFrame(editado).fillna("")

            valores_actuales = hoja_asistencia.get_all_values()

            if not valores_actuales:
                st.error("La hoja Asistencia está vacía. Sincroniza nuevamente.")
                return

            headers = [
                str(x).strip().upper()
                for x in valores_actuales[0]
            ]

            updates = preparar_updates(
                df_editado,
                df_total,
                headers,
                cols_editables
            )

            if not updates:
                st.info(
                    "No se detectaron cambios para guardar. "
                    "Si acabas de seleccionar A/F, haz click fuera de la celda y vuelve a presionar Guardar."
                )
            else:
                hoja_asistencia.batch_update(
                    updates,
                    value_input_option="USER_ENTERED"
                )

                st.success(
                    f"✅ Asistencia guardada correctamente. Cambios aplicados: {len(updates)}"
                )

        except Exception as e:
            st.error(f"❌ Error guardando asistencia: {e}")

    # =================================================
    # VISTA CON COLORES
    # =================================================
    st.markdown("### Vista de asistencia con colores")
    mostrar_vista_colores(
        df_filtrado[COLUMNAS_VISIBLES_BASE + COLUMNAS_DIAS].copy()
    )

    # =================================================
    # MATRIZ INFERIOR
    # =================================================
    if registro_mod is not None:
        st.divider()
        st.subheader("📋 Matriz de jerarquía")
        try:
            registro_mod.mostrar_tabla(
                hoja_colaboradores,
                razon
            )
        except Exception as e:
            st.warning(
                f"No se pudo cargar la matriz inferior de jerarquía: {e}"
            )
