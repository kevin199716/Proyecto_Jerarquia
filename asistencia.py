from datetime import datetime, timedelta

import pandas as pd
import streamlit as st

# =====================================================
# ASISTENCIA ULTRA OPTIMIZADA
# - No edita los 31 dias a la vez.
# - Solo edita UN DIA seleccionado de la semana actual.
# - Muestra espejo mensual DIA_1 a DIA_31.
# - Guarda en Google Sheets solo al presionar guardar.
# - Sin st.rerun() al guardar.
# - Solo incluye cargos que contengan PROMOTOR.
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

COLUMNAS_EDITOR_BASE = [
    "DNI",
    "NOMBRE",
    "SUPERVISOR",
    "COORDINADOR",
    "DEPARTAMENTO",
    "PROVINCIA",
]


# =====================================================
# UTILIDADES
# =====================================================
def normalizar_columnas(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = df.columns.astype(str).str.strip().str.upper()
    return df


def limpiar_texto(valor) -> str:
    valor = "" if pd.isna(valor) else str(valor)
    return valor.strip()


def limpiar_marca(valor) -> str:
    valor = "" if pd.isna(valor) else str(valor)
    valor = valor.strip().upper()

    if valor in ["A", "F"]:
        return valor

    if valor in ["NONE", "NAN", "NULL", "-"]:
        return ""

    return ""


def periodo_actual() -> str:
    return datetime.now().strftime("%Y-%m")


def mes_actual() -> str:
    return str(datetime.now().month)


def dias_semana_actual() -> list[int]:
    hoy = datetime.now().date()
    inicio = hoy - timedelta(days=hoy.weekday())

    dias = []
    for i in range(7):
        fecha = inicio + timedelta(days=i)
        if fecha.month == hoy.month:
            dias.append(fecha.day)

    return dias


def letra_columna(numero: int) -> str:
    letras = ""
    while numero:
        numero, resto = divmod(numero - 1, 26)
        letras = chr(65 + resto) + letras
    return letras


def mostrar_valor_color(valor) -> str:
    valor = limpiar_marca(valor)
    if valor == "A":
        return "🟩 A"
    if valor == "F":
        return "🟥 F"
    return ""


def es_promotor(row: pd.Series) -> bool:
    cargo = ""
    for col in ["CARGO (ROL)", "CARGO", "ROL"]:
        if col in row.index:
            cargo = limpiar_texto(row.get(col, "")).upper()
            break

    # Si no existe columna cargo, no bloqueamos para no dejar vacia la asistencia.
    if not cargo:
        return True

    return "PROMOTOR" in cargo


# =====================================================
# LECTURA SHEETS
# =====================================================
def leer_asistencia_desde_drive(hoja_asistencia) -> pd.DataFrame:
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

    for col in COLUMNAS_ASISTENCIA:
        if col not in df.columns:
            df[col] = ""

    df = df[COLUMNAS_ASISTENCIA].copy()
    df["ROW_SHEET"] = df.index + 2

    for col in COLUMNAS_DIAS:
        df[col] = df[col].apply(limpiar_marca)

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
            value_input_option="USER_ENTERED",
        )
        return True

    headers = [str(x).strip().upper() for x in valores[0]]
    faltantes = [c for c in COLUMNAS_ASISTENCIA if c not in headers]

    if faltantes:
        st.error("La hoja Asistencia tiene cabecera incompleta o diferente.")
        st.write("Columnas faltantes:", faltantes)
        st.warning("Borra solo el contenido de la hoja Asistencia y presiona Sincronizar mes.")
        return False

    return True


# =====================================================
# PROMOTORES / SINCRONIZACION
# =====================================================
def obtener_promotores_activos(df_colab: pd.DataFrame) -> pd.DataFrame:
    if df_colab.empty:
        return pd.DataFrame()

    if "DNI" not in df_colab.columns or "ESTADO" not in df_colab.columns:
        return pd.DataFrame()

    df = df_colab.copy()
    df = df[
        df["ESTADO"].astype(str).str.strip().str.upper().eq("ACTIVO")
    ].copy()

    if df.empty:
        return df

    df = df[df.apply(es_promotor, axis=1)].copy()
    df["DNI"] = df["DNI"].astype(str).str.strip()
    df = df[df["DNI"].ne("")].copy()

    return df


def construir_registros_nuevos(df_colab: pd.DataFrame, dnis_existentes: set[str]) -> list[list[str]]:
    df_prom = obtener_promotores_activos(df_colab)

    if df_prom.empty:
        return []

    periodo = periodo_actual()
    mes = mes_actual()
    registros = []

    for _, row in df_prom.iterrows():
        dni = limpiar_texto(row.get("DNI", ""))

        if not dni or dni in dnis_existentes:
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
    df_asis = leer_asistencia_desde_drive(hoja_asistencia)

    dnis_existentes = set()
    if not df_asis.empty:
        dnis_existentes = set(
            df_asis.loc[
                df_asis["PERIODO"].astype(str).eq(periodo),
                "DNI",
            ].astype(str).str.strip().tolist()
        )

    df_colab = leer_colaboradores(hoja_colaboradores)
    nuevos = construir_registros_nuevos(df_colab, dnis_existentes)

    if nuevos:
        hoja_asistencia.append_rows(nuevos, value_input_option="USER_ENTERED")

    return len(nuevos)


# =====================================================
# SESSION CACHE
# =====================================================
def cargar_cache_asistencia(hoja_asistencia, forzar=False) -> pd.DataFrame:
    periodo = periodo_actual()
    key_df = f"asis_df_cache_{periodo}"

    if forzar or key_df not in st.session_state:
        st.session_state[key_df] = leer_asistencia_desde_drive(hoja_asistencia)

    return st.session_state[key_df].copy()


def actualizar_cache_celda(row_sheet: int, columna: str, valor: str):
    periodo = periodo_actual()
    key_df = f"asis_df_cache_{periodo}"

    if key_df not in st.session_state:
        return

    df = st.session_state[key_df].copy()
    mask = df["ROW_SHEET"].eq(row_sheet)
    if mask.any() and columna in df.columns:
        df.loc[mask, columna] = valor
        st.session_state[key_df] = df


# =====================================================
# FILTROS
# =====================================================
def opciones(df: pd.DataFrame, columna: str) -> list[str]:
    if columna not in df.columns:
        return ["TODOS"]

    vals = (
        df[columna]
        .astype(str)
        .str.strip()
        .replace("", pd.NA)
        .dropna()
        .unique()
        .tolist()
    )

    return ["TODOS"] + sorted(vals)


def filtrar_df(df, supervisor, coordinador, departamento):
    res = df.copy()

    if supervisor != "TODOS":
        res = res[res["SUPERVISOR"].astype(str).str.strip().eq(supervisor)]

    if coordinador != "TODOS":
        res = res[res["COORDINADOR"].astype(str).str.strip().eq(coordinador)]

    if departamento != "TODOS":
        res = res[res["DEPARTAMENTO"].astype(str).str.strip().eq(departamento)]

    return res


# =====================================================
# GUARDADO
# =====================================================
def guardar_cambios_dia(hoja_asistencia, cambios: list[dict]) -> int:
    if not cambios:
        return 0

    valores = hoja_asistencia.get_all_values()
    if not valores:
        raise ValueError("La hoja Asistencia está vacía.")

    headers = [str(x).strip().upper() for x in valores[0]]
    mapa_col = {c: i + 1 for i, c in enumerate(headers)}

    updates = []

    for item in cambios:
        row_sheet = int(item["ROW_SHEET"])
        columna = str(item["COLUMNA"]).strip().upper()
        valor = limpiar_marca(item["VALOR"])

        if columna not in mapa_col:
            continue

        letra = letra_columna(mapa_col[columna])
        updates.append({
            "range": f"{letra}{row_sheet}",
            "values": [[valor]],
        })

    if updates:
        hoja_asistencia.batch_update(updates, value_input_option="USER_ENTERED")

    return len(updates)


# =====================================================
# MAIN
# =====================================================
def mostrar_asistencia(hoja_asistencia, hoja_colaboradores, registro_mod=None, razon=None):
    st.subheader("🗓️ Control de Asistencia")

    if not validar_o_crear_cabecera(hoja_asistencia):
        return

    periodo = periodo_actual()
    dias_editables = dias_semana_actual()
    columnas_editables = [f"DIA_{d}" for d in dias_editables]

    c1, c2 = st.columns([1, 5])

    with c1:
        if st.button("🔄 Sincronizar mes", key="btn_sync_mes"):
            try:
                creados = sincronizar_mes(hoja_asistencia, hoja_colaboradores)
                st.session_state.pop(f"asis_df_cache_{periodo}", None)
                st.success(f"Mes sincronizado. Registros nuevos: {creados}")
            except Exception as e:
                st.error(f"Error sincronizando mes: {e}")
                return

    with c2:
        st.info(
            "Para evitar cuelgues: se edita UN DÍA a la vez. "
            "Abajo se ve el espejo completo DIA_1 a DIA_31."
        )

    df_total = cargar_cache_asistencia(hoja_asistencia)

    df_mes = df_total[df_total["PERIODO"].astype(str).eq(periodo)].copy()

    # Refuerza filtro de promotor activo usando colaboradores.
    df_colab = leer_colaboradores(hoja_colaboradores)
    df_prom = obtener_promotores_activos(df_colab)
    if not df_prom.empty:
        dnis_prom = set(df_prom["DNI"].astype(str).str.strip().tolist())
        df_mes = df_mes[df_mes["DNI"].astype(str).str.strip().isin(dnis_prom)].copy()

    if df_mes.empty:
        st.warning("No hay registros del periodo actual. Presiona Sincronizar mes.")
        return

    # Filtros encadenados.
    f1, f2, f3, f4 = st.columns(4)

    with f1:
        sup = st.selectbox("Supervisor", opciones(df_mes, "SUPERVISOR"), key="asis_sup")

    df_tmp = filtrar_df(df_mes, sup, "TODOS", "TODOS")

    with f2:
        coord = st.selectbox("Coordinador", opciones(df_tmp, "COORDINADOR"), key="asis_coord")

    df_tmp = filtrar_df(df_tmp, "TODOS", coord, "TODOS")

    with f3:
        dep = st.selectbox("Departamento", opciones(df_tmp, "DEPARTAMENTO"), key="asis_dep")

    df_filtrado = filtrar_df(df_mes, sup, coord, dep)

    with f4:
        dia_elegido = st.selectbox(
            "Día a editar",
            columnas_editables,
            key="asis_dia_elegido",
        )

    if df_filtrado.empty:
        st.warning("No hay registros con los filtros seleccionados.")
        return

    st.caption(f"Registros visibles: {len(df_filtrado)} | Día editable: {dia_elegido}")

    # =================================================
    # EDITOR LIVIANO: SOLO UN DIA
    # =================================================
    st.markdown("### Editar asistencia")

    df_editor = df_filtrado[COLUMNAS_EDITOR_BASE + [dia_elegido, "ROW_SHEET"]].copy()
    df_editor[dia_elegido] = df_editor[dia_elegido].apply(limpiar_marca)

    disabled_cols = [c for c in df_editor.columns if c != dia_elegido]

    editado = st.data_editor(
        df_editor,
        use_container_width=True,
        height=430,
        hide_index=True,
        disabled=disabled_cols,
        column_config={
            dia_elegido: st.column_config.SelectboxColumn(
                dia_elegido,
                options=["", "A", "F"],
                width="small",
            )
        },
        num_rows="fixed",
        key="editor_asistencia_un_dia",
    )

    if st.button("💾 Guardar Asistencia", key="btn_guardar_asistencia"):
        try:
            df_editado = pd.DataFrame(editado).fillna("")
            cambios = []

            for _, row in df_editado.iterrows():
                row_sheet = int(row["ROW_SHEET"])
                nuevo = limpiar_marca(row.get(dia_elegido, ""))

                original = df_total[df_total["ROW_SHEET"].eq(row_sheet)]
                if original.empty:
                    continue

                anterior = limpiar_marca(original.iloc[0].get(dia_elegido, ""))

                if nuevo != anterior:
                    cambios.append({
                        "ROW_SHEET": row_sheet,
                        "COLUMNA": dia_elegido,
                        "VALOR": nuevo,
                    })

            if not cambios:
                st.info("No se detectaron cambios para guardar.")
            else:
                total = guardar_cambios_dia(hoja_asistencia, cambios)

                for item in cambios:
                    actualizar_cache_celda(
                        int(item["ROW_SHEET"]),
                        item["COLUMNA"],
                        limpiar_marca(item["VALOR"]),
                    )

                st.success(f"✅ Asistencia guardada en Drive. Cambios aplicados: {total}")

        except Exception as e:
            st.error(f"❌ Error guardando asistencia: {e}")

    # =================================================
    # ESPEJO COMPLETO DEL MES
    # =================================================
    st.markdown("### Espejo mensual completo")

    df_espejo = df_filtrado[COLUMNAS_EDITOR_BASE + COLUMNAS_DIAS].copy()
    for col in COLUMNAS_DIAS:
        df_espejo[col] = df_espejo[col].apply(mostrar_valor_color)

    st.dataframe(
        df_espejo,
        use_container_width=True,
        height=360,
    )

    if registro_mod is not None:
        st.divider()
        st.subheader("📋 Matriz de jerarquía")
        try:
            registro_mod.mostrar_tabla(hoja_colaboradores, razon)
        except Exception as e:
            st.warning(f"No se pudo cargar la matriz inferior de jerarquía: {e}")
