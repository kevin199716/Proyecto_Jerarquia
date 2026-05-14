from datetime import datetime, timedelta
from typing import Dict, List, Tuple

import pandas as pd
import streamlit as st


# =====================================================
# CONFIGURACION GENERAL
# =====================================================
COLUMNAS_BASE = [
    "RAZON SOCIAL",
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

VALORES_ASISTENCIA = ["", "A", "F"]


# =====================================================
# UTILIDADES BASICAS
# =====================================================
def normalizar_columnas(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = df.columns.astype(str).str.strip().str.upper()
    return df


def limpiar_texto(valor) -> str:
    if pd.isna(valor):
        return ""
    texto = str(valor).strip()
    if texto.upper() in ["NAN", "NONE", "NAT"]:
        return ""
    return texto


def periodo_actual() -> str:
    return datetime.now().strftime("%Y-%m")


def mes_actual() -> str:
    return str(datetime.now().month)


def nombre_mes_actual() -> str:
    meses = {
        1: "ENERO",
        2: "FEBRERO",
        3: "MARZO",
        4: "ABRIL",
        5: "MAYO",
        6: "JUNIO",
        7: "JULIO",
        8: "AGOSTO",
        9: "SETIEMBRE",
        10: "OCTUBRE",
        11: "NOVIEMBRE",
        12: "DICIEMBRE",
    }
    return meses.get(datetime.now().month, str(datetime.now().month))


def fecha_hoy() -> datetime.date:
    return datetime.now().date()


def numero_a_letra(n: int) -> str:
    letras = ""
    while n:
        n, rem = divmod(n - 1, 26)
        letras = chr(65 + rem) + letras
    return letras


# =====================================================
# SEMANA ACTUAL
# =====================================================
def dias_semana_actual() -> List[int]:
    hoy = fecha_hoy()
    inicio = hoy - timedelta(days=hoy.weekday())
    dias = []

    for i in range(7):
        fecha = inicio + timedelta(days=i)
        if fecha.month == hoy.month:
            dias.append(fecha.day)

    return dias


def columnas_semana_actual() -> List[str]:
    return [f"DIA_{d}" for d in dias_semana_actual()]


def texto_semana_actual() -> str:
    dias = dias_semana_actual()
    if not dias:
        return "Semana actual"
    return f"Semana editable: días {min(dias)} al {max(dias)} de {nombre_mes_actual()}"


# =====================================================
# LECTURA Y CABECERA SHEET
# =====================================================
def leer_sheet_df(hoja) -> pd.DataFrame:
    valores = hoja.get_all_values()

    if not valores:
        return pd.DataFrame(columns=COLUMNAS_ASISTENCIA)

    headers = [limpiar_texto(x).upper() for x in valores[0]]
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


def validar_o_crear_cabecera(hoja) -> bool:
    valores = hoja.get_all_values()

    if not valores:
        hoja.append_row(
            COLUMNAS_ASISTENCIA,
            value_input_option="USER_ENTERED"
        )
        return True

    headers = [limpiar_texto(x).upper() for x in valores[0]]
    faltantes = [col for col in COLUMNAS_ASISTENCIA if col not in headers]

    if faltantes:
        st.error(
            "La hoja Asistencia tiene cabeceras antiguas o incompletas. "
            "Para corregirlo rápido: borra TODO el contenido de la pestaña Asistencia, "
            "déjala vacía y vuelve a entrar al módulo Asistencia. "
            f"Columnas faltantes: {', '.join(faltantes)}"
        )
        return False

    return True


# =====================================================
# FECHAS ALTA / BAJA
# =====================================================
def convertir_fecha(valor):
    texto = limpiar_texto(valor)
    if not texto:
        return None

    fecha = pd.to_datetime(texto, errors="coerce", dayfirst=True)
    if pd.isna(fecha):
        fecha = pd.to_datetime(texto, errors="coerce", dayfirst=False)

    if pd.isna(fecha):
        return None

    return fecha.date()


def obtener_fecha_alta(row: pd.Series):
    posibles = [
        "FECHA DE CREACION USUARIO",
        "FECHA CREACION USUARIO",
        "FECHA ALTA",
        "FECHA DE ALTA",
        "FECHA MOV"
    ]

    for col in posibles:
        if col in row.index:
            fecha = convertir_fecha(row.get(col, ""))
            if fecha:
                return fecha

    return None


def obtener_fecha_baja(row: pd.Series):
    posibles = [
        "FECHA DE CESE",
        "FECHA CESE",
        "FECHA BAJA",
        "FECHA DE BAJA"
    ]

    for col in posibles:
        if col in row.index:
            fecha = convertir_fecha(row.get(col, ""))
            if fecha:
                return fecha

    return None


def promotor_vigente_en_mes(row: pd.Series, anio: int, mes: int) -> bool:
    inicio_mes = datetime(anio, mes, 1).date()

    if mes == 12:
        fin_mes = datetime(anio + 1, 1, 1).date() - timedelta(days=1)
    else:
        fin_mes = datetime(anio, mes + 1, 1).date() - timedelta(days=1)

    fecha_alta = obtener_fecha_alta(row)
    fecha_baja = obtener_fecha_baja(row)

    if fecha_alta and fecha_alta > fin_mes:
        return False

    if fecha_baja and fecha_baja < inicio_mes:
        return False

    return True


# =====================================================
# SINCRONIZACION DE PROMOTORES
# =====================================================
def construir_filas_nuevas(df_colab: pd.DataFrame, dnis_existentes_periodo: set) -> List[List[str]]:
    if df_colab.empty:
        return []

    df_colab = normalizar_columnas(df_colab)

    if "DNI" not in df_colab.columns:
        st.error("La hoja colaboradores no tiene la columna DNI.")
        return []

    anio = datetime.now().year
    mes = datetime.now().month
    periodo = periodo_actual()
    mes_texto = mes_actual()

    registros = []

    for _, row in df_colab.iterrows():
        dni = limpiar_texto(row.get("DNI", ""))
        if not dni:
            continue

        if dni in dnis_existentes_periodo:
            continue

        estado = limpiar_texto(row.get("ESTADO", "")).upper()

        # Regla: se sincroniza ACTIVO y también quien haya estado vigente en el mes.
        # Esto conserva casos que luego pasaron a baja dentro del mes.
        if estado != "ACTIVO" and not promotor_vigente_en_mes(row, anio, mes):
            continue

        fila = {
            "RAZON SOCIAL": limpiar_texto(row.get("RAZON SOCIAL", "")),
            "SUPERVISOR": limpiar_texto(row.get("SUPERVISOR A CARGO", "")),
            "COORDINADOR": limpiar_texto(row.get("COORDINADOR", "")),
            "DEPARTAMENTO": limpiar_texto(row.get("DEPARTAMENTO", "")),
            "PROVINCIA": limpiar_texto(row.get("PROVINCIA", "")),
            "DNI": dni,
            "NOMBRE": limpiar_texto(row.get("NOMBRES", "")),
            "ESTADO": estado if estado else "ACTIVO",
            "MES": mes_texto,
            "PERIODO": periodo,
        }

        for col in COLUMNAS_DIAS:
            fila[col] = ""

        registros.append([fila.get(col, "") for col in COLUMNAS_ASISTENCIA])

    return registros


def sincronizar_asistencia(hoja_asistencia, hoja_colaboradores) -> Tuple[int, str]:
    if not validar_o_crear_cabecera(hoja_asistencia):
        return 0, "Cabecera inválida."

    periodo = periodo_actual()
    df_asis = leer_sheet_df(hoja_asistencia)

    dnis_existentes = set()
    if not df_asis.empty and "PERIODO" in df_asis.columns and "DNI" in df_asis.columns:
        dnis_existentes = set(
            df_asis.loc[
                df_asis["PERIODO"].astype(str).eq(periodo),
                "DNI"
            ].astype(str).str.strip().tolist()
        )

    data_colab = hoja_colaboradores.get_all_records()
    df_colab = pd.DataFrame(data_colab)

    nuevas = construir_filas_nuevas(df_colab, dnis_existentes)

    if nuevas:
        hoja_asistencia.append_rows(
            nuevas,
            value_input_option="USER_ENTERED"
        )

    return len(nuevas), f"Sincronización terminada. Nuevos registros: {len(nuevas)}"


# =====================================================
# LIMPIEZA ASISTENCIA
# =====================================================
def limpiar_valores_asistencia(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy().fillna("")

    for col in COLUMNAS_DIAS:
        if col in df.columns:
            df[col] = (
                df[col]
                .astype(str)
                .str.strip()
                .str.upper()
                .replace({"NAN": "", "NONE": ""})
            )
            df[col] = df[col].apply(lambda x: x if x in VALORES_ASISTENCIA else "")

    return df


def aplicar_filtros(df: pd.DataFrame, rol_usuario: str, razon_usuario: str) -> pd.DataFrame:
    df = df.copy()

    if rol_usuario == "dealer" and razon_usuario and "RAZON SOCIAL" in df.columns:
        df = df[df["RAZON SOCIAL"].astype(str).str.upper().eq(razon_usuario.upper())]

    return df


# =====================================================
# GUARDADO EN BLOQUE
# =====================================================
def construir_updates(
    df_original_periodo: pd.DataFrame,
    df_editado: pd.DataFrame,
    headers_sheet: List[str],
    cols_editables: List[str]
) -> List[Dict]:
    mapa_columna = {col: idx + 1 for idx, col in enumerate(headers_sheet)}
    updates = []

    original_por_row = {
        int(row["ROW_SHEET"]): row
        for _, row in df_original_periodo.iterrows()
    }

    for _, fila in df_editado.iterrows():
        try:
            row_sheet = int(fila["ROW_SHEET"])
        except Exception:
            continue

        if row_sheet not in original_por_row:
            continue

        original = original_por_row[row_sheet]

        for col in cols_editables:
            if col not in mapa_columna:
                continue

            nuevo = limpiar_texto(fila.get(col, "")).upper()
            if nuevo not in VALORES_ASISTENCIA:
                nuevo = ""

            anterior = limpiar_texto(original.get(col, "")).upper()
            if anterior not in VALORES_ASISTENCIA:
                anterior = ""

            if nuevo != anterior:
                letra = numero_a_letra(mapa_columna[col])
                updates.append({
                    "range": f"{letra}{row_sheet}",
                    "values": [[nuevo]]
                })

    return updates


def guardar_asistencia(hoja_asistencia, df_original_periodo: pd.DataFrame, df_editado: pd.DataFrame, cols_editables: List[str]) -> Tuple[int, str]:
    valores = hoja_asistencia.get_all_values()

    if not valores:
        return 0, "La hoja Asistencia está vacía. Primero sincroniza el mes."

    headers_sheet = [limpiar_texto(x).upper() for x in valores[0]]

    df_editado = limpiar_valores_asistencia(df_editado)
    updates = construir_updates(
        df_original_periodo=df_original_periodo,
        df_editado=df_editado,
        headers_sheet=headers_sheet,
        cols_editables=cols_editables
    )

    if not updates:
        return 0, "No se detectaron cambios para guardar."

    hoja_asistencia.batch_update(
        updates,
        value_input_option="USER_ENTERED"
    )

    return len(updates), f"Asistencia guardada correctamente. Cambios aplicados: {len(updates)}"


# =====================================================
# UI PRINCIPAL
# =====================================================
def mostrar_asistencia(hoja_asistencia, hoja_colaboradores, razon_usuario="", rol_usuario=""):
    st.subheader("🗓️ Control de Asistencia")

    st.caption(
        "Esta versión no guarda al seleccionar A/F. Solo guarda cuando presionas el botón Guardar Asistencia."
    )

    if not validar_o_crear_cabecera(hoja_asistencia):
        return

    periodo = periodo_actual()

    col_a, col_b = st.columns([1, 4])

    with col_a:
        if st.button("🔄 Sincronizar mes", key="btn_sync_asistencia", type="secondary"):
            with st.spinner("Sincronizando asistencia con la maestra..."):
                cantidad, mensaje = sincronizar_asistencia(
                    hoja_asistencia,
                    hoja_colaboradores
                )
            if cantidad >= 0:
                st.success(mensaje)

    with col_b:
        st.info(texto_semana_actual())

    df_total = leer_sheet_df(hoja_asistencia)

    if df_total.empty:
        st.warning("La hoja Asistencia no tiene registros. Presiona 'Sincronizar mes'.")
        return

    for col in COLUMNAS_ASISTENCIA:
        if col not in df_total.columns:
            df_total[col] = ""

    df_total = df_total[COLUMNAS_ASISTENCIA].copy()
    df_total["ROW_SHEET"] = df_total.index + 2

    df_periodo = df_total[df_total["PERIODO"].astype(str).eq(periodo)].copy()
    df_periodo = aplicar_filtros(df_periodo, rol_usuario, razon_usuario)

    if df_periodo.empty:
        st.warning("No hay registros para el periodo actual. Presiona 'Sincronizar mes'.")
        return

    # Filtros antes de pintar tabla para no cargar demasiados registros en Render.
    st.markdown("### Filtros")

    f1, f2, f3 = st.columns(3)

    supervisores = sorted([x for x in df_periodo["SUPERVISOR"].astype(str).unique().tolist() if x.strip()])
    coordinadores = sorted([x for x in df_periodo["COORDINADOR"].astype(str).unique().tolist() if x.strip()])
    departamentos = sorted([x for x in df_periodo["DEPARTAMENTO"].astype(str).unique().tolist() if x.strip()])

    with f1:
        supervisor_sel = st.selectbox(
            "Supervisor",
            ["TODOS"] + supervisores,
            key="asis_filtro_supervisor"
        )

    with f2:
        coordinador_sel = st.selectbox(
            "Coordinador",
            ["TODOS"] + coordinadores,
            key="asis_filtro_coordinador"
        )

    with f3:
        departamento_sel = st.selectbox(
            "Departamento",
            ["TODOS"] + departamentos,
            key="asis_filtro_departamento"
        )

    df_vista = df_periodo.copy()

    if supervisor_sel != "TODOS":
        df_vista = df_vista[df_vista["SUPERVISOR"].astype(str).eq(supervisor_sel)]

    if coordinador_sel != "TODOS":
        df_vista = df_vista[df_vista["COORDINADOR"].astype(str).eq(coordinador_sel)]

    if departamento_sel != "TODOS":
        df_vista = df_vista[df_vista["DEPARTAMENTO"].astype(str).eq(departamento_sel)]

    if df_vista.empty:
        st.warning("No hay registros con los filtros seleccionados.")
        return

    columnas_editables = columnas_semana_actual()

    columnas_vista = [
        "RAZON SOCIAL",
        "SUPERVISOR",
        "COORDINADOR",
        "DEPARTAMENTO",
        "PROVINCIA",
        "DNI",
        "NOMBRE",
        "ESTADO",
        "PERIODO",
        "ROW_SHEET"
    ] + columnas_editables

    df_vista = limpiar_valores_asistencia(df_vista[columnas_vista].copy())

    st.caption(
        f"Mostrando {len(df_vista)} registros. Solo se renderizan los días de la semana actual para evitar congelamientos."
    )

    # FORM: evita que cada selección A/F dispare el proceso completo.
    with st.form("form_asistencia_guardado", clear_on_submit=False):
        df_editado = st.data_editor(
            df_vista,
            key="editor_asistencia_semana",
            hide_index=True,
            use_container_width=True,
            height=520,
            disabled=[
                "RAZON SOCIAL",
                "SUPERVISOR",
                "COORDINADOR",
                "DEPARTAMENTO",
                "PROVINCIA",
                "DNI",
                "NOMBRE",
                "ESTADO",
                "PERIODO",
                "ROW_SHEET"
            ],
            column_config={
                "ROW_SHEET": None,
                **{
                    col: st.column_config.SelectboxColumn(
                        col,
                        options=VALORES_ASISTENCIA,
                        required=False,
                        width="small"
                    )
                    for col in columnas_editables
                }
            }
        )

        guardar = st.form_submit_button(
            "💾 Guardar Asistencia",
            type="primary"
        )

    if guardar:
        with st.spinner("Guardando asistencia en Google Sheets..."):
            cambios, mensaje = guardar_asistencia(
                hoja_asistencia=hoja_asistencia,
                df_original_periodo=df_periodo,
                df_editado=pd.DataFrame(df_editado),
                cols_editables=columnas_editables
            )

        if cambios > 0:
            st.success(mensaje)
        else:
            st.info(mensaje)

    st.markdown("---")
    st.caption("A = Asistencia | F = Falta | Vacío = sin marcación")
