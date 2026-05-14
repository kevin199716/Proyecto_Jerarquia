# ============================================================
# ARCHIVO 1: app_maestra_vendedores.py
# Copia desde la siguiente línea hasta antes de ARCHIVO 2
# ============================================================

import os
import sys
import streamlit as st

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import registro_mod as registro

from auth import (
    cargar_usuarios,
    login
)

from ui_inicio import (
    mostrar_bienvenida
)

from sheets import (
    conectar_google_sheets
)

from formulario import (
    mostrar_formulario
)

from asistencia import (
    mostrar_asistencia
)

# =========================
# CONFIG
# =========================
st.set_page_config(
    page_title="Sistema",
    layout="wide"
)

# =========================
# CACHE GOOGLE SHEETS
# =========================
@st.cache_resource(show_spinner=False)
def get_worksheet(nombre_archivo, nombre_worksheet):
    return conectar_google_sheets(nombre_archivo, nombre_worksheet)

# =========================
# LOGIN
# =========================
USUARIOS = cargar_usuarios()

if "autenticado" not in st.session_state:
    st.session_state["autenticado"] = False

if not st.session_state["autenticado"]:
    mostrar_bienvenida()
    login(USUARIOS)
    st.stop()

# =========================
# VARIABLES
# =========================
rol = st.session_state.get("rol", "")
razon = st.session_state.get("razon", "")
usuario = st.session_state.get("usuario", "")

# =========================
# CABECERA AZUL
# =========================
st.markdown(
    f"""
    <div style="background-color:#EAF3FF;border:1px solid #BBD7FF;border-radius:10px;padding:12px 16px;margin-bottom:12px;">
        <b>Usuario:</b> {usuario} &nbsp;&nbsp; | &nbsp;&nbsp;
        <b>Rol:</b> {rol} &nbsp;&nbsp; | &nbsp;&nbsp;
        <b>Razón:</b> {razon}
    </div>
    """,
    unsafe_allow_html=True
)

st.title("📊 Sistema de Vendedores")

# =========================
# MENU
# =========================
def menu_paginas(opciones):
    return st.radio(
        "Módulo",
        opciones,
        horizontal=True,
        label_visibility="collapsed",
        key=f"menu_{rol}"
    )

# =====================================================
# BACKOFFICE
# =====================================================
if rol == "backoffice":
    pagina = menu_paginas(["Registro", "Bajas", "Asistencia"])

    if pagina == "Registro":
        hoja_colaboradores = get_worksheet("maestra_vendedores", "colaboradores")
        hoja_ubicaciones = get_worksheet("maestra_vendedores", "ubicaciones")

        mostrar_formulario(hoja_colaboradores, hoja_ubicaciones)

        st.divider()
        registro.mostrar_tabla(hoja_colaboradores, razon)

    elif pagina == "Bajas":
        hoja_colaboradores = get_worksheet("maestra_vendedores", "colaboradores")

        df = registro.mostrar_tabla(hoja_colaboradores, razon)

        if df is not None:
            registro.dar_de_baja(df, hoja_colaboradores, razon)

    elif pagina == "Asistencia":
        hoja_asistencia = get_worksheet("maestra_vendedores", "Asistencia")
        hoja_colaboradores = get_worksheet("maestra_vendedores", "colaboradores")

        mostrar_asistencia(hoja_asistencia, hoja_colaboradores, registro, razon)

# =====================================================
# DEALER
# =====================================================
elif rol == "dealer":
    st.subheader(f"📌 Socio: {razon}")

    pagina = menu_paginas(["Registro", "Bajas", "Asistencia"])

    if pagina == "Registro":
        hoja_colaboradores = get_worksheet("maestra_vendedores", "colaboradores")
        hoja_ubicaciones = get_worksheet("maestra_vendedores", "ubicaciones")

        mostrar_formulario(hoja_colaboradores, hoja_ubicaciones)

        st.divider()
        registro.mostrar_tabla(hoja_colaboradores, razon)

    elif pagina == "Bajas":
        hoja_colaboradores = get_worksheet("maestra_vendedores", "colaboradores")

        df = registro.mostrar_tabla(hoja_colaboradores, razon)

        if df is not None:
            registro.dar_de_baja(df, hoja_colaboradores, razon)

    elif pagina == "Asistencia":
        hoja_asistencia = get_worksheet("maestra_vendedores", "Asistencia")
        hoja_colaboradores = get_worksheet("maestra_vendedores", "colaboradores")

        mostrar_asistencia(hoja_asistencia, hoja_colaboradores, registro, razon)

# =====================================================
# EDITOR
# =====================================================
elif rol == "editor":
    st.subheader("✏️ Modo edición")

    pagina = menu_paginas(["Edición", "Asistencia"])

    if pagina == "Edición":
        hoja_colaboradores = get_worksheet("maestra_vendedores", "colaboradores")
        hoja_ubicaciones = get_worksheet("maestra_vendedores", "ubicaciones")

        df = registro.mostrar_tabla(hoja_colaboradores)

        if df is not None:
            registro.editar_registro(df, hoja_colaboradores, hoja_ubicaciones)

    elif pagina == "Asistencia":
        hoja_asistencia = get_worksheet("maestra_vendedores", "Asistencia")
        hoja_colaboradores = get_worksheet("maestra_vendedores", "colaboradores")

        mostrar_asistencia(hoja_asistencia, hoja_colaboradores, registro, razon)

else:
    st.warning(f"Sin permisos para el rol: {rol}")


# ============================================================
# ARCHIVO 2: asistencia.py
# Copia desde la siguiente línea en un archivo aparte llamado asistencia.py
# ============================================================

from datetime import datetime, timedelta

import pandas as pd
import streamlit as st

# =====================================================
# COLUMNAS
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
    "PROVINCIA"
]

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


def dias_semana_actual():
    hoy = datetime.now().date()
    inicio = hoy - timedelta(days=hoy.weekday())
    dias = []

    for i in range(7):
        fecha = inicio + timedelta(days=i)
        if fecha.month == hoy.month:
            dias.append(fecha.day)

    return dias


def leer_asistencia(hoja):
    valores = hoja.get_all_values()

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
    return normalizar_columnas(df)


def validar_o_crear_cabecera(hoja):
    valores = hoja.get_all_values()

    if not valores:
        hoja.append_row(COLUMNAS_ASISTENCIA, value_input_option="USER_ENTERED")
        return True

    headers = [str(x).strip().upper() for x in valores[0]]
    faltantes = [c for c in COLUMNAS_ASISTENCIA if c not in headers]

    if faltantes:
        st.error("La hoja Asistencia tiene cabecera incompleta. Borra el contenido de la hoja Asistencia y vuelve a sincronizar.")
        st.write("Columnas faltantes:", faltantes)
        return False

    return True


def letra_columna(numero):
    letras = ""
    while numero:
        numero, resto = divmod(numero - 1, 26)
        letras = chr(65 + resto) + letras
    return letras


def limpiar_marca(valor):
    valor = str(valor).strip().upper()
    if valor in ["A", "F", ""]:
        return valor
    return ""


def construir_registros_nuevos(df_colab, dnis_existentes_periodo):
    df_colab = normalizar_columnas(df_colab)

    if "DNI" not in df_colab.columns or "ESTADO" not in df_colab.columns:
        return []

    df_activos = df_colab[
        df_colab["ESTADO"].astype(str).str.strip().str.upper().eq("ACTIVO")
    ].copy()

    registros = []
    periodo = periodo_actual()
    mes = mes_actual()

    for _, row in df_activos.iterrows():
        dni = str(row.get("DNI", "")).strip()

        if not dni:
            continue

        if dni in dnis_existentes_periodo:
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


# =====================================================
# SINCRONIZAR
# =====================================================
def sincronizar_mes(hoja_asistencia, hoja_colaboradores):
    if not validar_o_crear_cabecera(hoja_asistencia):
        return 0

    periodo = periodo_actual()
    df_asis = leer_asistencia(hoja_asistencia)

    dnis_existentes = set()
    if not df_asis.empty and "PERIODO" in df_asis.columns and "DNI" in df_asis.columns:
        dnis_existentes = set(
            df_asis.loc[
                df_asis["PERIODO"].astype(str).eq(periodo),
                "DNI"
            ].astype(str).str.strip().tolist()
        )

    df_colab = pd.DataFrame(hoja_colaboradores.get_all_records())
    nuevos = construir_registros_nuevos(df_colab, dnis_existentes)

    if nuevos:
        hoja_asistencia.append_rows(nuevos, value_input_option="USER_ENTERED")

    return len(nuevos)


# =====================================================
# FORMATO VISUAL HTML ESPEJO
# =====================================================
def mostrar_espejo_colores(df):
    if df.empty:
        return

    df_html = df.copy()

    def pintar(valor):
        valor = str(valor).strip().upper()
        if valor == "A":
            return "background-color:#C6EFCE;color:#006100;font-weight:bold;text-align:center;"
        if valor == "F":
            return "background-color:#FFC7CE;color:#9C0006;font-weight:bold;text-align:center;"
        return "text-align:center;"

    styler = df_html.style.applymap(pintar, subset=COLUMNAS_DIAS)
    st.dataframe(styler, use_container_width=True, height=330)


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

    c1, c2 = st.columns([1, 4])

    with c1:
        if st.button("🔄 Sincronizar mes", key="sync_asistencia"):
            try:
                creados = sincronizar_mes(hoja_asistencia, hoja_colaboradores)
                st.success(f"Sincronización correcta. Registros nuevos: {creados}")
            except Exception as e:
                st.error(f"Error sincronizando asistencia: {e}")
                return

    with c2:
        st.info("Se muestran DIA_1 a DIA_31. Solo se edita la semana actual. Guarda solo al presionar el botón.")

    df_total = leer_asistencia(hoja_asistencia)

    for col in COLUMNAS_ASISTENCIA:
        if col not in df_total.columns:
            df_total[col] = ""

    df_total = df_total[COLUMNAS_ASISTENCIA].copy()
    df_total["ROW_SHEET"] = df_total.index + 2

    df_mes = df_total[df_total["PERIODO"].astype(str).eq(periodo)].copy()

    if df_mes.empty:
        st.warning("No hay registros del periodo actual. Presiona Sincronizar mes.")
        return

    sup_opciones = ["TODOS"] + sorted([x for x in df_mes["SUPERVISOR"].astype(str).unique() if x.strip()])
    coord_opciones = ["TODOS"] + sorted([x for x in df_mes["COORDINADOR"].astype(str).unique() if x.strip()])
    dep_opciones = ["TODOS"] + sorted([x for x in df_mes["DEPARTAMENTO"].astype(str).unique() if x.strip()])

    f1, f2, f3 = st.columns(3)

    with f1:
        filtro_sup = st.selectbox("Supervisor", sup_opciones, key="asis_filtro_sup")
    with f2:
        filtro_coord = st.selectbox("Coordinador", coord_opciones, key="asis_filtro_coord")
    with f3:
        filtro_dep = st.selectbox("Departamento", dep_opciones, key="asis_filtro_dep")

    df_filtrado = df_mes.copy()

    if filtro_sup != "TODOS":
        df_filtrado = df_filtrado[df_filtrado["SUPERVISOR"].astype(str).eq(filtro_sup)]
    if filtro_coord != "TODOS":
        df_filtrado = df_filtrado[df_filtrado["COORDINADOR"].astype(str).eq(filtro_coord)]
    if filtro_dep != "TODOS":
        df_filtrado = df_filtrado[df_filtrado["DEPARTAMENTO"].astype(str).eq(filtro_dep)]

    max_registros = st.slider(
        "Cantidad de registros a mostrar",
        min_value=20,
        max_value=300,
        value=min(100, max(20, len(df_filtrado))),
        step=20,
        key="asis_max_registros"
    )

    df_filtrado = df_filtrado.head(max_registros).copy()

    st.caption(f"Registros visibles: {len(df_filtrado)} | Columnas editables: {', '.join(cols_editables)}")

    columnas_editor = COLUMNAS_VISIBLES_BASE + COLUMNAS_DIAS + ["ROW_SHEET"]
    df_editor = df_filtrado[columnas_editor].copy()

    for col in COLUMNAS_DIAS:
        df_editor[col] = df_editor[col].apply(limpiar_marca)

    disabled_cols = [c for c in df_editor.columns if c not in cols_editables]

    column_config = {}
    for col in COLUMNAS_DIAS:
        column_config[col] = st.column_config.SelectboxColumn(
            col,
            options=["", "A", "F"],
            width="small"
        )

    with st.form("form_asistencia_guardado", clear_on_submit=False):
        editado = st.data_editor(
            df_editor,
            use_container_width=True,
            height=520,
            hide_index=True,
            disabled=disabled_cols,
            column_config=column_config,
            key="editor_asistencia_final"
        )

        guardar = st.form_submit_button("💾 Guardar Asistencia")

    if guardar:
        try:
            df_editado = pd.DataFrame(editado).fillna("")

            valores = hoja_asistencia.get_all_values()
            headers = [str(x).strip().upper() for x in valores[0]]
            mapa_col = {c: i + 1 for i, c in enumerate(headers)}

            updates = []

            for _, row in df_editado.iterrows():
                row_sheet = int(row["ROW_SHEET"])

                original = df_total[df_total["ROW_SHEET"].eq(row_sheet)]
                if original.empty:
                    continue

                original = original.iloc[0]

                for col in cols_editables:
                    nuevo = limpiar_marca(row.get(col, ""))
                    anterior = limpiar_marca(original.get(col, ""))

                    if nuevo != anterior:
                        letra = letra_columna(mapa_col[col])
                        updates.append({
                            "range": f"{letra}{row_sheet}",
                            "values": [[nuevo]]
                        })

            if not updates:
                st.info("No se detectaron cambios para guardar.")
            else:
                hoja_asistencia.batch_update(updates, value_input_option="USER_ENTERED")
                st.success(f"Asistencia guardada correctamente. Cambios aplicados: {len(updates)}")

        except Exception as e:
            st.error(f"Error guardando asistencia: {e}")

    with st.expander("👁️ Vista espejo con colores del mes", expanded=False):
        mostrar_espejo_colores(df_filtrado[COLUMNAS_VISIBLES_BASE + COLUMNAS_DIAS])

    st.divider()

    st.subheader("📋 Matriz de jerarquía")
    if registro_mod is not None:
        try:
            registro_mod.mostrar_tabla(hoja_colaboradores, razon)
        except Exception as e:
            st.warning(f"No se pudo cargar la matriz inferior de jerarquía: {e}")
