from datetime import datetime, timedelta, date

import pandas as pd
import streamlit as st


# =====================================================
# CONFIGURACION DE ASISTENCIA
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

VALORES_VALIDOS = ["", "A", "F"]


# =====================================================
# UTILIDADES GENERALES
# =====================================================
def normalizar_columnas(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = df.columns.astype(str).str.strip().str.upper()
    return df


def periodo_actual() -> str:
    return datetime.now().strftime("%Y-%m")


def mes_actual() -> str:
    return str(datetime.now().month)


def fecha_hoy() -> date:
    return datetime.now().date()


def dias_semana_actual() -> list[int]:
    hoy = fecha_hoy()
    inicio_semana = hoy - timedelta(days=hoy.weekday())
    dias = []

    for i in range(7):
        fecha = inicio_semana + timedelta(days=i)
        if fecha.month == hoy.month:
            dias.append(fecha.day)

    return dias


def columna_a_letra(numero: int) -> str:
    letras = ""

    while numero:
        numero, residuo = divmod(numero - 1, 26)
        letras = chr(65 + residuo) + letras

    return letras


def limpiar_dni(valor) -> str:
    if pd.isna(valor):
        return ""

    texto = str(valor).strip()

    if texto.endswith(".0"):
        texto = texto[:-2]

    return texto


def limpiar_marca(valor) -> str:
    if pd.isna(valor):
        return ""

    texto = str(valor).strip().upper()

    if texto in ["NAN", "NONE", "NULL"]:
        return ""

    if texto not in VALORES_VALIDOS:
        return ""

    return texto


# =====================================================
# LECTURA / CABECERA GOOGLE SHEETS
# =====================================================
def leer_sheet_df(hoja) -> pd.DataFrame:
    valores = hoja.get_all_values()

    if not valores:
        return pd.DataFrame(columns=COLUMNAS_ASISTENCIA)

    headers = [str(x).strip().upper() for x in valores[0]]
    data = valores[1:]

    filas_corregidas = []

    for fila in data:
        fila = list(fila)

        if len(fila) < len(headers):
            fila = fila + [""] * (len(headers) - len(fila))

        if len(fila) > len(headers):
            fila = fila[:len(headers)]

        filas_corregidas.append(fila)

    df = pd.DataFrame(filas_corregidas, columns=headers)
    df = df.fillna("").replace("None", "")
    df = normalizar_columnas(df)

    if "DNI" in df.columns:
        df["DNI"] = df["DNI"].apply(limpiar_dni)

    for col in COLUMNAS_DIAS:
        if col in df.columns:
            df[col] = df[col].apply(limpiar_marca)

    return df


def asegurar_cabecera(hoja_asistencia) -> bool:
    valores = hoja_asistencia.get_all_values()

    if not valores:
        hoja_asistencia.append_row(
            COLUMNAS_ASISTENCIA,
            value_input_option="USER_ENTERED",
        )
        return True

    headers = [str(x).strip().upper() for x in valores[0]]
    faltantes = [col for col in COLUMNAS_ASISTENCIA if col not in headers]

    if faltantes:
        st.error(
            "La hoja Asistencia tiene una cabecera incompleta. "
            f"Faltan columnas: {', '.join(faltantes)}. "
            "Para corregirlo: borra TODO el contenido de la pestaña Asistencia y vuelve a entrar al módulo."
        )
        return False

    return True


# =====================================================
# SINCRONIZACION CON COLABORADORES
# =====================================================
def obtener_columna(row: pd.Series, opciones: list[str]) -> str:
    for col in opciones:
        if col in row.index:
            valor = row.get(col, "")
            if pd.isna(valor):
                return ""
            return str(valor).strip()
    return ""


def construir_registros_nuevos(df_colaboradores: pd.DataFrame, claves_existentes: set[str]) -> list[list[str]]:
    if df_colaboradores.empty:
        return []

    df_colaboradores = normalizar_columnas(df_colaboradores)

    if "DNI" not in df_colaboradores.columns:
        st.error("La hoja colaboradores no tiene columna DNI.")
        return []

    if "ESTADO" not in df_colaboradores.columns:
        st.error("La hoja colaboradores no tiene columna ESTADO.")
        return []

    periodo = periodo_actual()
    mes = mes_actual()

    df_colaboradores["DNI"] = df_colaboradores["DNI"].apply(limpiar_dni)
    df_colaboradores["ESTADO"] = df_colaboradores["ESTADO"].astype(str).str.strip().str.upper()

    df_activos = df_colaboradores[df_colaboradores["ESTADO"].eq("ACTIVO")].copy()

    registros = []

    for _, row in df_activos.iterrows():
        dni = limpiar_dni(row.get("DNI", ""))

        if not dni:
            continue

        clave = f"{dni}|{periodo}"

        if clave in claves_existentes:
            continue

        fila = {
            "SUPERVISOR": obtener_columna(row, ["SUPERVISOR A CARGO", "SUPERVISOR"]),
            "COORDINADOR": obtener_columna(row, ["COORDINADOR"]),
            "DEPARTAMENTO": obtener_columna(row, ["DEPARTAMENTO"]),
            "PROVINCIA": obtener_columna(row, ["PROVINCIA"]),
            "DNI": dni,
            "NOMBRE": obtener_columna(row, ["NOMBRES", "NOMBRE"]),
            "ESTADO": "ACTIVO",
            "MES": mes,
            "PERIODO": periodo,
        }

        for col in COLUMNAS_DIAS:
            fila[col] = ""

        registros.append([fila.get(col, "") for col in COLUMNAS_ASISTENCIA])

    return registros


def sincronizar_mes_actual(hoja_asistencia, hoja_colaboradores) -> int:
    if not asegurar_cabecera(hoja_asistencia):
        return 0

    periodo = periodo_actual()
    df_asistencia = leer_sheet_df(hoja_asistencia)

    claves_existentes = set()

    if not df_asistencia.empty and "DNI" in df_asistencia.columns and "PERIODO" in df_asistencia.columns:
        tmp = df_asistencia.copy()
        tmp["DNI"] = tmp["DNI"].apply(limpiar_dni)
        tmp["PERIODO"] = tmp["PERIODO"].astype(str).str.strip()
        tmp = tmp[tmp["PERIODO"].eq(periodo)]
        claves_existentes = set((tmp["DNI"] + "|" + tmp["PERIODO"]).tolist())

    data_colaboradores = hoja_colaboradores.get_all_records()
    df_colaboradores = pd.DataFrame(data_colaboradores)

    registros_nuevos = construir_registros_nuevos(
        df_colaboradores,
        claves_existentes,
    )

    if registros_nuevos:
        hoja_asistencia.append_rows(
            registros_nuevos,
            value_input_option="USER_ENTERED",
        )

    return len(registros_nuevos)


# =====================================================
# PREPARAR TABLA PARA PANTALLA
# =====================================================
def preparar_df_periodo(df_total: pd.DataFrame, periodo: str) -> pd.DataFrame:
    for col in COLUMNAS_ASISTENCIA:
        if col not in df_total.columns:
            df_total[col] = ""

    df_total = df_total[COLUMNAS_ASISTENCIA].copy()
    df_total["ROW_SHEET"] = df_total.index + 2

    df_periodo = df_total[df_total["PERIODO"].astype(str).str.strip().eq(periodo)].copy()

    for col in COLUMNAS_DIAS:
        df_periodo[col] = df_periodo[col].apply(limpiar_marca)

    return df_periodo


def aplicar_filtros(df: pd.DataFrame, supervisor: str, coordinador: str) -> pd.DataFrame:
    df_filtrado = df.copy()

    if supervisor != "TODOS":
        df_filtrado = df_filtrado[df_filtrado["SUPERVISOR"].astype(str).eq(supervisor)]

    if coordinador != "TODOS":
        df_filtrado = df_filtrado[df_filtrado["COORDINADOR"].astype(str).eq(coordinador)]

    return df_filtrado


# =====================================================
# GUARDADO EN DRIVE / GOOGLE SHEETS
# =====================================================
def construir_updates(df_original: pd.DataFrame, df_editado: pd.DataFrame, headers: list[str], dias_editables: list[int]) -> list[dict]:
    col_index = {col: idx + 1 for idx, col in enumerate(headers)}

    if "ROW_SHEET" not in df_editado.columns:
        return []

    df_original = df_original.copy()
    df_editado = df_editado.copy()

    df_original["ROW_SHEET"] = df_original["ROW_SHEET"].astype(int)
    df_editado["ROW_SHEET"] = df_editado["ROW_SHEET"].astype(int)

    original_por_fila = df_original.set_index("ROW_SHEET")

    updates = []

    for _, fila in df_editado.iterrows():
        row_sheet = int(fila["ROW_SHEET"])

        if row_sheet not in original_por_fila.index:
            continue

        for dia in dias_editables:
            col = f"DIA_{dia}"

            if col not in col_index:
                continue

            valor_nuevo = limpiar_marca(fila.get(col, ""))
            valor_original = limpiar_marca(original_por_fila.loc[row_sheet, col])

            if valor_nuevo != valor_original:
                letra = columna_a_letra(col_index[col])
                updates.append({
                    "range": f"{letra}{row_sheet}",
                    "values": [[valor_nuevo]],
                })

    return updates


def guardar_asistencia(hoja_asistencia, df_original: pd.DataFrame, df_editado: pd.DataFrame, dias_editables: list[int]) -> int:
    valores = hoja_asistencia.get_all_values()

    if not valores:
        raise ValueError("La hoja Asistencia está vacía. Primero sincroniza el mes.")

    headers = [str(x).strip().upper() for x in valores[0]]

    updates = construir_updates(
        df_original=df_original,
        df_editado=df_editado,
        headers=headers,
        dias_editables=dias_editables,
    )

    if not updates:
        return 0

    hoja_asistencia.batch_update(
        updates,
        value_input_option="USER_ENTERED",
    )

    return len(updates)


# =====================================================
# INTERFAZ PRINCIPAL
# =====================================================
def mostrar_asistencia(hoja_asistencia, hoja_colaboradores):
    st.markdown("## 🗓️ Control de Asistencia")

    if not asegurar_cabecera(hoja_asistencia):
        return

    periodo = periodo_actual()
    dias_editables = dias_semana_actual()

    st.info(
        "Solo se puede editar la semana actual. "
        "Usa A para asistencia y F para falta. "
        "El guardado se envía directo a Google Sheets."
    )

    col_sync, col_periodo = st.columns([1, 4])

    with col_sync:
        sincronizar = st.button(
            "🔄 Sincronizar mes",
            key="btn_sincronizar_asistencia",
        )

    with col_periodo:
        st.write(f"**Periodo actual:** {periodo}")

    if sincronizar:
        try:
            insertados = sincronizar_mes_actual(
                hoja_asistencia,
                hoja_colaboradores,
            )

            if insertados > 0:
                st.success(f"Sincronización correcta. Registros nuevos agregados: {insertados}")
            else:
                st.info("Sincronización correcta. No había registros nuevos por agregar.")

        except Exception as e:
            st.error(f"Error sincronizando asistencia: {e}")
            return

    df_total = leer_sheet_df(hoja_asistencia)

    if df_total.empty:
        st.warning("La hoja Asistencia no tiene registros. Presiona Sincronizar mes.")
        return

    df_periodo = preparar_df_periodo(
        df_total,
        periodo,
    )

    if df_periodo.empty:
        st.warning("No hay registros para el periodo actual. Presiona Sincronizar mes.")
        return

    supervisores = sorted([
        x for x in df_periodo["SUPERVISOR"].astype(str).unique().tolist()
        if str(x).strip()
    ])

    coordinadores = sorted([
        x for x in df_periodo["COORDINADOR"].astype(str).unique().tolist()
        if str(x).strip()
    ])

    col1, col2 = st.columns(2)

    with col1:
        filtro_supervisor = st.selectbox(
            "🔍 Supervisor",
            ["TODOS"] + supervisores,
            key="filtro_supervisor_asistencia",
        )

    with col2:
        filtro_coordinador = st.selectbox(
            "🔍 Coordinador",
            ["TODOS"] + coordinadores,
            key="filtro_coordinador_asistencia",
        )

    df_filtrado = aplicar_filtros(
        df_periodo,
        filtro_supervisor,
        filtro_coordinador,
    )

    if df_filtrado.empty:
        st.warning("No hay registros con los filtros seleccionados.")
        return

    columnas_ocultas = ["ROW_SHEET"]
    columnas_bloqueadas = [
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

    dias_bloqueados = [
        col for col in COLUMNAS_DIAS
        if int(col.replace("DIA_", "")) not in dias_editables
    ]

    columnas_deshabilitadas = columnas_bloqueadas + dias_bloqueados + columnas_ocultas

    column_config = {}

    for col in COLUMNAS_DIAS:
        dia = int(col.replace("DIA_", ""))
        if dia in dias_editables:
            column_config[col] = st.column_config.SelectboxColumn(
                col,
                options=VALORES_VALIDOS,
                required=False,
                width="small",
            )
        else:
            column_config[col] = st.column_config.TextColumn(
                col,
                disabled=True,
                width="small",
            )

    st.caption("Marca A/F y luego presiona Guardar Asistencia. No se escribe celda por celda; se guarda en bloque.")

    df_editor = df_filtrado[COLUMNAS_ASISTENCIA + ["ROW_SHEET"]].copy()

    df_editado = st.data_editor(
        df_editor,
        hide_index=True,
        use_container_width=True,
        height=520,
        disabled=columnas_deshabilitadas,
        column_config=column_config,
        key="editor_asistencia_final",
    )

    if st.button(
        "💾 Guardar Asistencia",
        key="btn_guardar_asistencia_final",
        type="primary",
    ):
        try:
            cambios = guardar_asistencia(
                hoja_asistencia=hoja_asistencia,
                df_original=df_filtrado,
                df_editado=df_editado,
                dias_editables=dias_editables,
            )

            if cambios == 0:
                st.warning("No se detectaron cambios para guardar.")
            else:
                st.success(f"✅ Asistencia guardada correctamente en Google Sheets. Cambios aplicados: {cambios}")

        except Exception as e:
            st.error(f"❌ Error guardando asistencia: {e}")
