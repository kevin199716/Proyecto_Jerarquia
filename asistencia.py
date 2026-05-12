import streamlit as st
import pandas as pd
import calendar
import pytz
from datetime import datetime, timedelta

zona_peru = pytz.timezone("America/Lima")

def ahora_peru():
    return datetime.now(zona_peru)

def periodo_actual():
    return ahora_peru().strftime("%Y-%m")

def columnas_dias_mes():
    hoy = ahora_peru()
    dias = calendar.monthrange(hoy.year, hoy.month)[1]
    return [f"DIA_{i}" for i in range(1, dias + 1)]

def columnas_editables_semana():
    hoy = ahora_peru()
    lunes = hoy - timedelta(days=hoy.weekday())
    dias = []
    for i in range(7):
        d = lunes + timedelta(days=i)
        if d.month == hoy.month:
            dias.append(f"DIA_{d.day}")
    return dias

def leer_hoja_segura(hoja):
    valores = hoja.get_all_values()
    if not valores:
        return pd.DataFrame()

    headers = [str(h).strip().upper() for h in valores[0]]
    data = valores[1:]

    if not headers:
        return pd.DataFrame()

    df = pd.DataFrame(data, columns=headers)
    df.columns = df.columns.str.strip().str.upper()
    return df.fillna("")

def leer_cache(nombre, hoja, ttl=120):
    ahora = datetime.now().timestamp()
    key_data = f"{nombre}_data"
    key_time = f"{nombre}_time"

    if key_data in st.session_state and key_time in st.session_state:
        if ahora - st.session_state[key_time] < ttl:
            return st.session_state[key_data].copy()

    df = leer_hoja_segura(hoja)
    st.session_state[key_data] = df.copy()
    st.session_state[key_time] = ahora
    return df

def limpiar_cache():
    for k in [
        "asistencia_data",
        "asistencia_time",
        "colaboradores_data",
        "colaboradores_time"
    ]:
        if k in st.session_state:
            del st.session_state[k]

def preparar_colaboradores(df):
    df.columns = df.columns.str.strip().str.upper()
    for col in df.columns:
        df[col] = df[col].astype(str).fillna("").str.strip()
    return df

def generar_asistencia_mes(hoja_asistencia, df_colab):
    df_asistencia = leer_cache("asistencia", hoja_asistencia, ttl=30)
    periodo = periodo_actual()
    dias_mes = columnas_dias_mes()

    columnas_base = [
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

    columnas_finales = columnas_base + dias_mes + [
        "USUARIO_REGISTRO",
        "FECHA_REGISTRO"
    ]

    if df_asistencia.empty:
        hoja_asistencia.clear()
        hoja_asistencia.update([columnas_finales])
        df_asistencia = pd.DataFrame(columns=columnas_finales)

    for col in columnas_finales:
        if col not in df_asistencia.columns:
            df_asistencia[col] = ""

    existentes = set()
    if not df_asistencia.empty and "PERIODO" in df_asistencia.columns and "DNI" in df_asistencia.columns:
        existentes = set(
            df_asistencia["PERIODO"].astype(str).str.strip()
            + "_"
            + df_asistencia["DNI"].astype(str).str.strip()
        )

    nuevas = []

    for _, row in df_colab.iterrows():
        dni = str(row.get("DNI", "")).strip()
        if not dni:
            continue

        llave = f"{periodo}_{dni}"
        if llave in existentes:
            continue

        nombre = (
            f"{row.get('NOMBRES', '')} "
            f"{row.get('APELLIDO PATERNO', '')} "
            f"{row.get('APELLIDO MATERNO', '')}"
        ).strip()

        fila = {
            "PERIODO": periodo,
            "DNI": dni,
            "NOMBRE": nombre,
            "SUPERVISOR": row.get("SUPERVISOR A CARGO", ""),
            "COORDINADOR": row.get("COORDINADOR", ""),
            "DEPARTAMENTO": row.get("DEPARTAMENTO", ""),
            "PROVINCIA": row.get("PROVINCIA", ""),
            "ESTADO": row.get("ESTADO", ""),
            "FECHA_CREACION_USUARIO": row.get("FECHA DE CREACION USUARIO", ""),
            "FECHA_DE_CESE": row.get("FECHA DE CESE", ""),
            "USUARIO_REGISTRO": st.session_state.get("usuario", ""),
            "FECHA_REGISTRO": ahora_peru().strftime("%Y-%m-%d %H:%M:%S")
        }

        for d in dias_mes:
            fila[d] = ""

        nuevas.append([fila.get(c, "") for c in columnas_finales])

    if nuevas:
        hoja_asistencia.append_rows(nuevas)
        limpiar_cache()

def dia_cese_valido(fecha_cese):
    try:
        if not fecha_cese:
            return None
        return pd.to_datetime(fecha_cese, errors="coerce").day
    except:
        return None

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
    .stDataFrame {
        border-radius: 12px;
    }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("## 🗓️ Control de Asistencia")

    df_colab = leer_cache("colaboradores", hoja_colaboradores, ttl=120)
    if df_colab.empty:
        st.warning("No hay colaboradores.")
        return

    df_colab = preparar_colaboradores(df_colab)

    generar_asistencia_mes(hoja_asistencia, df_colab)

    df = leer_cache("asistencia", hoja_asistencia, ttl=120)
    if df.empty:
        st.warning("Sin registros de asistencia.")
        return

    for col in df.columns:
        df[col] = df[col].astype(str).fillna("").str.strip()

    periodo = periodo_actual()

    if "PERIODO" in df.columns:
        df = df[df["PERIODO"].astype(str).str.strip() == periodo]

    if df.empty:
        st.warning("No hay registros para el periodo actual.")
        return

    total = len(df)
    activos = len(df[df["ESTADO"].astype(str).str.upper() == "ACTIVO"])
    inactivos = total - activos

    c1, c2, c3 = st.columns(3)
    c1.metric("👥 HC TOTAL", total)
    c2.metric("✅ ACTIVOS", activos)
    c3.metric("❌ INACTIVOS", inactivos)

    st.divider()

    col1, col2 = st.columns(2)

    supervisores = sorted(
        df["SUPERVISOR"].astype(str).fillna("").str.strip().replace("", pd.NA).dropna().unique().tolist()
    )

    coordinadores = sorted(
        df["COORDINADOR"].astype(str).fillna("").str.strip().replace("", pd.NA).dropna().unique().tolist()
    )

    with col1:
        filtro_supervisor = st.selectbox("🔍 Supervisor", ["TODOS"] + supervisores)

    with col2:
        filtro_coordinador = st.selectbox("🔍 Coordinador", ["TODOS"] + coordinadores)

    if filtro_supervisor != "TODOS":
        df = df[df["SUPERVISOR"].astype(str).str.strip() == filtro_supervisor]

    if filtro_coordinador != "TODOS":
        df = df[df["COORDINADOR"].astype(str).str.strip() == filtro_coordinador]

    columnas_base = [
        "SUPERVISOR",
        "COORDINADOR",
        "DEPARTAMENTO",
        "PROVINCIA",
        "DNI",
        "NOMBRE",
        "ESTADO"
    ]

    dias_mes = columnas_dias_mes()
    dias_editables = columnas_editables_semana()

    columnas_mostrar = columnas_base + dias_mes
    columnas_mostrar = [c for c in columnas_mostrar if c in df.columns]

    df_view = df[columnas_mostrar].copy()

    for col in dias_mes:
        if col in df_view.columns:
            df_view[col] = df_view[col].replace(["None", "nan", "NaT"], "")

    disabled_cols = columnas_base.copy()

    for dia in dias_mes:
        if dia not in dias_editables:
            disabled_cols.append(dia)

    config = {}

    for dia in dias_mes:
        if dia in df_view.columns:
            config[dia] = st.column_config.SelectboxColumn(
                label=dia.replace("_", " "),
                options=["", "A", "F"],
                width="small",
                help="A = Asistencia | F = Falta"
            )

    st.info(
        "Se muestran todos los días del mes. Solo se puede editar la semana actual "
        "(lunes a domingo). A = Asistencia | F = Falta"
    )

    with st.form("form_asistencia"):
        edited_df = st.data_editor(
            df_view,
            use_container_width=True,
            hide_index=True,
            height=560,
            num_rows="fixed",
            disabled=disabled_cols,
            column_config=config,
            key="editor_asistencia"
        )

        guardar = st.form_submit_button("💾 Guardar Asistencia")

    if guardar:
        with st.spinner("Guardando asistencia..."):

            df_real = leer_hoja_segura(hoja_asistencia)

            if df_real.empty:
                st.error("La hoja Asistencia está vacía o sin encabezados.")
                return

            for col in df_real.columns:
                df_real[col] = df_real[col].astype(str).fillna("").str.strip()

            for _, row in edited_df.iterrows():
                dni = str(row["DNI"]).strip()

                mask = (
                    (df_real["PERIODO"].astype(str).str.strip() == periodo)
                    &
                    (df_real["DNI"].astype(str).str.strip() == dni)
                )

                idxs = df_real[mask].index

                if len(idxs) == 0:
                    continue

                idx_real = idxs[0]

                estado = str(df_real.loc[idx_real, "ESTADO"]).upper().strip()
                fecha_cese = str(df_real.loc[idx_real, "FECHA_DE_CESE"]).strip()
                dia_cese = dia_cese_valido(fecha_cese)

                for dia in dias_editables:
                    if dia not in df_real.columns or dia not in row:
                        continue

                    num_dia = int(dia.replace("DIA_", ""))

                    if estado == "INACTIVO" and dia_cese and num_dia > dia_cese:
                        continue

                    valor = str(row[dia]).upper().strip()

                    if valor in ["NONE", "NAN"]:
                        valor = ""

                    if valor not in ["", "A", "F"]:
                        valor = ""

                    df_real.loc[idx_real, dia] = valor

            df_real = df_real.fillna("").replace(["None", "nan", "NaT"], "")

            hoja_asistencia.update(
                "A1",
                [df_real.columns.tolist()] + df_real.values.tolist()
            )

            limpiar_cache()

            st.success("✅ Asistencia guardada correctamente")
            st.rerun()