import streamlit as st
import pandas as pd
import calendar
import pytz
from datetime import datetime, timedelta

# =====================================================
# CONFIG
# =====================================================

zona_peru = pytz.timezone("America/Lima")

COLUMNAS_BASE_ASISTENCIA = [
    "PERIODO",
    "DNI",
    "NOMBRE",
    "SUPERVISOR",
    "COORDINADOR",
    "DEPARTAMENTO",
    "PROVINCIA",
    "ESTADO",
    "FECHA_CREACION_USUARIO",
    "FECHA_DE_CESE"
]

COLUMNAS_FIJAS_VISTA = [
    "SUPERVISOR",
    "COORDINADOR",
    "DEPARTAMENTO",
    "PROVINCIA",
    "DNI",
    "NOMBRE",
    "ESTADO"
]


# =====================================================
# FECHAS
# =====================================================

def ahora_peru():
    return datetime.now(zona_peru)


def periodo_actual():
    return ahora_peru().strftime("%Y-%m")


def dias_del_mes():
    hoy = ahora_peru()
    cantidad_dias = calendar.monthrange(hoy.year, hoy.month)[1]
    return [f"DIA_{i}" for i in range(1, cantidad_dias + 1)]


def dias_editables_semana_actual():
    """
    Edita desde lunes de la semana actual hasta hoy.
    Ejemplo: si hoy es martes 12, solo DIA_11 y DIA_12.
    """
    hoy = ahora_peru()
    lunes = hoy - timedelta(days=hoy.weekday())

    dias = []

    fecha = lunes
    while fecha.date() <= hoy.date():
        if fecha.month == hoy.month:
            dias.append(f"DIA_{fecha.day}")
        fecha += timedelta(days=1)

    return dias


# =====================================================
# HELPERS
# =====================================================

def limpiar_texto(valor):
    if pd.isna(valor):
        return ""

    valor = str(valor).strip()

    if valor.lower() in ["none", "nan", "nat"]:
        return ""

    return valor


def lista_limpia_ordenada(serie):
    return sorted(
        serie
        .astype(str)
        .fillna("")
        .str.strip()
        .replace("", pd.NA)
        .dropna()
        .unique()
        .tolist(),
        key=str
    )


def limpiar_cache_asistencia():
    claves = [
        "cache_colaboradores_df",
        "cache_colaboradores_time",
        "cache_asistencia_df",
        "cache_asistencia_time"
    ]

    for clave in claves:
        if clave in st.session_state:
            del st.session_state[clave]


# =====================================================
# LECTURA SEGURA
# =====================================================

def leer_hoja_segura(hoja):
    try:
        valores = hoja.get_all_values()

        if not valores:
            return pd.DataFrame()

        headers = [str(h).strip().upper() for h in valores[0]]
        data = valores[1:]

        if not headers:
            return pd.DataFrame()

        df = pd.DataFrame(data, columns=headers)
        df.columns = df.columns.str.strip().str.upper()

        for col in df.columns:
            df[col] = df[col].apply(limpiar_texto)

        return df

    except Exception as e:
        st.error(f"❌ Error leyendo hoja: {e}")
        return pd.DataFrame()


def cargar_colaboradores(hoja_colaboradores, ttl=120):
    ahora = datetime.now().timestamp()

    if (
        "cache_colaboradores_df" in st.session_state
        and "cache_colaboradores_time" in st.session_state
        and ahora - st.session_state["cache_colaboradores_time"] < ttl
    ):
        return st.session_state["cache_colaboradores_df"].copy()

    df = leer_hoja_segura(hoja_colaboradores)

    st.session_state["cache_colaboradores_df"] = df.copy()
    st.session_state["cache_colaboradores_time"] = ahora

    return df


def cargar_asistencia(hoja_asistencia, ttl=120):
    ahora = datetime.now().timestamp()

    if (
        "cache_asistencia_df" in st.session_state
        and "cache_asistencia_time" in st.session_state
        and ahora - st.session_state["cache_asistencia_time"] < ttl
    ):
        return st.session_state["cache_asistencia_df"].copy()

    df = leer_hoja_segura(hoja_asistencia)

    st.session_state["cache_asistencia_df"] = df.copy()
    st.session_state["cache_asistencia_time"] = ahora

    return df


# =====================================================
# CREAR / COMPLETAR ASISTENCIA
# =====================================================

def generar_asistencia_mes(hoja_asistencia, df_colab):
    periodo = periodo_actual()
    columnas_dias = dias_del_mes()

    columnas_finales = (
        COLUMNAS_BASE_ASISTENCIA
        + columnas_dias
        + ["USUARIO_REGISTRO", "FECHA_REGISTRO"]
    )

    df_asistencia = leer_hoja_segura(hoja_asistencia)

    if df_asistencia.empty:
        hoja_asistencia.clear()
        hoja_asistencia.update("A1", [columnas_finales])
        df_asistencia = pd.DataFrame(columns=columnas_finales)

    for col in columnas_finales:
        if col not in df_asistencia.columns:
            df_asistencia[col] = ""

    existentes = set()

    if "PERIODO" in df_asistencia.columns and "DNI" in df_asistencia.columns:
        existentes = set(
            df_asistencia["PERIODO"].astype(str).str.strip()
            + "_"
            + df_asistencia["DNI"].astype(str).str.strip()
        )

    filas_nuevas = []

    for _, row in df_colab.iterrows():
        dni = limpiar_texto(row.get("DNI", ""))

        if not dni:
            continue

        llave = f"{periodo}_{dni}"

        if llave in existentes:
            continue

        nombre = (
            f"{limpiar_texto(row.get('NOMBRES', ''))} "
            f"{limpiar_texto(row.get('APELLIDO PATERNO', ''))} "
            f"{limpiar_texto(row.get('APELLIDO MATERNO', ''))}"
        ).strip()

        fila = {
            "PERIODO": periodo,
            "DNI": dni,
            "NOMBRE": nombre,
            "SUPERVISOR": limpiar_texto(row.get("SUPERVISOR A CARGO", "")),
            "COORDINADOR": limpiar_texto(row.get("COORDINADOR", "")),
            "DEPARTAMENTO": limpiar_texto(row.get("DEPARTAMENTO", "")),
            "PROVINCIA": limpiar_texto(row.get("PROVINCIA", "")),
            "ESTADO": limpiar_texto(row.get("ESTADO", "")),
            "FECHA_CREACION_USUARIO": limpiar_texto(row.get("FECHA DE CREACION USUARIO", "")),
            "FECHA_DE_CESE": limpiar_texto(row.get("FECHA DE CESE", "")),
            "USUARIO_REGISTRO": st.session_state.get("usuario", ""),
            "FECHA_REGISTRO": ahora_peru().strftime("%Y-%m-%d %H:%M:%S")
        }

        for dia in columnas_dias:
            fila[dia] = ""

        filas_nuevas.append([fila.get(col, "") for col in columnas_finales])

    if filas_nuevas:
        hoja_asistencia.append_rows(filas_nuevas)
        limpiar_cache_asistencia()


# =====================================================
# VALIDACIÓN INACTIVOS
# =====================================================

def obtener_dia_cese(fecha_cese):
    try:
        if not fecha_cese:
            return None

        fecha = pd.to_datetime(fecha_cese, errors="coerce")

        if pd.isna(fecha):
            return None

        return fecha.day

    except Exception:
        return None


# =====================================================
# UI PRINCIPAL
# =====================================================

def mostrar_asistencia(hoja_asistencia, hoja_colaboradores):

    st.markdown("""
        <style>
            div[data-testid="stMetric"] {
                background: #FFFFFF;
                border-radius: 14px;
                padding: 14px;
                border-left: 6px solid #8B5CF6;
                box-shadow: 0px 2px 10px rgba(0,0,0,0.06);
            }

            div[data-testid="stDataFrame"] {
                border-radius: 12px;
            }
        </style>
    """, unsafe_allow_html=True)

    st.markdown("## 🗓️ Control de Asistencia")

    # =====================================================
    # CARGA DE DATA
    # =====================================================

    df_colab = cargar_colaboradores(hoja_colaboradores)

    if df_colab.empty:
        st.warning("No hay colaboradores registrados.")
        return

    generar_asistencia_mes(hoja_asistencia, df_colab)

    df = cargar_asistencia(hoja_asistencia)

    if df.empty:
        st.warning("No hay registros de asistencia.")
        return

    periodo = periodo_actual()

    if "PERIODO" in df.columns:
        df = df[df["PERIODO"].astype(str).str.strip() == periodo]

    if df.empty:
        st.warning("No hay registros para el periodo actual.")
        return

    for col in df.columns:
        df[col] = df[col].apply(limpiar_texto)

    # =====================================================
    # KPIS
    # =====================================================

    total = len(df)
    activos = len(df[df["ESTADO"].astype(str).str.upper() == "ACTIVO"])
    inactivos = total - activos

    c1, c2, c3 = st.columns(3)

    c1.metric("👥 HC TOTAL", total)
    c2.metric("✅ ACTIVOS", activos)
    c3.metric("❌ INACTIVOS", inactivos)

    st.divider()

    # =====================================================
    # FILTROS
    # =====================================================

    col1, col2 = st.columns(2)

    supervisores = lista_limpia_ordenada(df["SUPERVISOR"])
    coordinadores = lista_limpia_ordenada(df["COORDINADOR"])

    with col1:
        filtro_supervisor = st.selectbox(
            "🔍 Supervisor",
            ["TODOS"] + supervisores,
            key="filtro_supervisor_asistencia"
        )

    with col2:
        filtro_coordinador = st.selectbox(
            "🔍 Coordinador",
            ["TODOS"] + coordinadores,
            key="filtro_coordinador_asistencia"
        )

    if filtro_supervisor != "TODOS":
        df = df[df["SUPERVISOR"].astype(str).str.strip() == filtro_supervisor]

    if filtro_coordinador != "TODOS":
        df = df[df["COORDINADOR"].astype(str).str.strip() == filtro_coordinador]

    # =====================================================
    # COLUMNAS
    # =====================================================

    columnas_dias = dias_del_mes()
    columnas_editables = dias_editables_semana_actual()

    columnas_mostrar = COLUMNAS_FIJAS_VISTA + columnas_dias
    columnas_mostrar = [col for col in columnas_mostrar if col in df.columns]

    df_view = df[columnas_mostrar].copy()

    for col in df_view.columns:
        df_view[col] = df_view[col].apply(limpiar_texto)

    # =====================================================
    # COLUMNAS DESHABILITADAS
    # =====================================================

    columnas_deshabilitadas = COLUMNAS_FIJAS_VISTA.copy()

    for dia in columnas_dias:
        if dia not in columnas_editables:
            columnas_deshabilitadas.append(dia)

    # =====================================================
    # CONFIGURACIÓN VISUAL
    # =====================================================

    column_config = {}

    for dia in columnas_dias:
        if dia in df_view.columns:
            column_config[dia] = st.column_config.SelectboxColumn(
                label=dia.replace("_", " "),
                options=["", "A", "F"],
                width="small",
                help="A = Asistencia | F = Falta"
            )

    st.info(
        "Se muestran todos los días del mes. "
        "Solo se puede editar desde el lunes de la semana actual hasta hoy. "
        "A = Asistencia | F = Falta."
    )

    # =====================================================
    # FORMULARIO PARA EVITAR RECARGA POR CADA SELECCIÓN
    # =====================================================

    with st.form("form_asistencia"):
        edited_df = st.data_editor(
            df_view,
            use_container_width=True,
            hide_index=True,
            height=560,
            num_rows="fixed",
            disabled=columnas_deshabilitadas,
            column_config=column_config,
            key="editor_asistencia"
        )

        guardar = st.form_submit_button("💾 Guardar Asistencia")

    # =====================================================
    # GUARDAR
    # =====================================================

    if guardar:
        with st.spinner("Guardando asistencia..."):

            df_real = leer_hoja_segura(hoja_asistencia)

            if df_real.empty:
                st.error("La hoja Asistencia está vacía o no tiene encabezados.")
                return

            for col in df_real.columns:
                df_real[col] = df_real[col].apply(limpiar_texto)

            for _, row in edited_df.iterrows():
                dni = limpiar_texto(row.get("DNI", ""))

                if not dni:
                    continue

                mask = (
                    (df_real["PERIODO"].astype(str).str.strip() == periodo)
                    &
                    (df_real["DNI"].astype(str).str.strip() == dni)
                )

                indices = df_real[mask].index

                if len(indices) == 0:
                    continue

                idx_real = indices[0]

                estado = limpiar_texto(df_real.loc[idx_real, "ESTADO"]).upper()
                fecha_cese = limpiar_texto(df_real.loc[idx_real, "FECHA_DE_CESE"])
                dia_cese = obtener_dia_cese(fecha_cese)

                for dia in columnas_editables:
                    if dia not in df_real.columns or dia not in row:
                        continue

                    numero_dia = int(dia.replace("DIA_", ""))

                    if estado == "INACTIVO" and dia_cese and numero_dia > dia_cese:
                        continue

                    valor = limpiar_texto(row.get(dia, "")).upper()

                    if valor not in ["", "A", "F"]:
                        valor = ""

                    df_real.loc[idx_real, dia] = valor

            df_real = df_real.fillna("")

            hoja_asistencia.update(
                "A1",
                [df_real.columns.tolist()] + df_real.values.tolist()
            )

            limpiar_cache_asistencia()

            st.success("✅ Asistencia guardada correctamente.")
            st.rerun()