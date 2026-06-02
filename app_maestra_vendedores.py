"""
APP_LAZY_RENDER_DRIVE_OPTIMIZADO_20260602
app_maestra_vendedores.py

Cambio principal:
- NO conecta Google Sheets al inicio de la app.
- Solo conecta la hoja que necesita el módulo seleccionado.
- Presencialidad Dealer ya NO carga matriz automáticamente.
- La matriz de jerarquía queda bajo demanda para no congelar Render/navegador.
"""

import os
import sys

import streamlit as st

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import registro_mod as registro
from auth import cargar_usuarios, login
from ui_inicio import mostrar_bienvenida
from sheets import conectar_google_sheets
from formulario import mostrar_formulario
from asistencia import mostrar_asistencia
from wow_theme import (
    inject_global_theme,
    render_app_header,
    render_sidebar_user,
    render_sidebar_help,
    wow_section,
)

st.set_page_config(
    page_title="WOW D2D | Portal Vendedores",
    page_icon="🟣",
    layout="wide",
    initial_sidebar_state="expanded",
)

inject_global_theme()


@st.cache_resource(show_spinner=False)
def get_worksheet(nombre_hoja: str, nombre_worksheet: str):
    return conectar_google_sheets(nombre_hoja, nombre_worksheet)


def ws_colaboradores():
    return get_worksheet("maestra_vendedores", "colaboradores")


def ws_ubicaciones():
    return get_worksheet("maestra_vendedores", "ubicaciones")


def ws_asistencia():
    return get_worksheet("maestra_vendedores", "Asistencia")


USUARIOS = cargar_usuarios()

if "autenticado" not in st.session_state:
    st.session_state["autenticado"] = False

if not st.session_state["autenticado"]:
    mostrar_bienvenida()
    login(USUARIOS)
    st.stop()

rol = st.session_state.get("rol", "")
razon = st.session_state.get("razon", "")
usuario = st.session_state.get("usuario", st.session_state.get("username", ""))

render_sidebar_user(usuario=usuario, rol=rol, razon=razon)

if rol == "backoffice":
    opciones_menu = ["Alta", "Bajas", "Presencialidad Dealer"]
elif rol == "dealer":
    opciones_menu = ["Alta", "Bajas", "Presencialidad Dealer"]
elif rol in ("presencialidad", "presencialidad_dealer"):
    opciones_menu = ["Presencialidad Dealer"]
elif rol == "editor":
    opciones_menu = ["Edición", "Presencialidad Dealer"]
else:
    opciones_menu = []

pagina = ""
if opciones_menu:
    pagina = st.sidebar.radio(
        "Módulo",
        opciones_menu,
        label_visibility="collapsed",
        key=f"nav_{rol}",
    )

st.sidebar.markdown("<div style='height: 14px;'></div>", unsafe_allow_html=True)
if st.sidebar.button("🚪 Cerrar sesión", key="btn_logout"):
    for k in ["autenticado", "usuario", "rol", "razon", "user", "pass"]:
        st.session_state.pop(k, None)
    st.rerun()

render_sidebar_help()
render_app_header(usuario=usuario, rol=rol, razon=razon)


def mostrar_matriz_jerarquia(titulo="Estado actual de la jerarquía", icono="📋"):
    """Carga la matriz solo cuando el usuario la solicita."""
    st.divider()
    wow_section(titulo, icono)
    st.caption("La matriz se carga bajo demanda para no congelar el módulo principal.")

    if not st.button("📥 Cargar / recargar matriz", key=f"btn_matriz_{titulo}_{rol}_{razon}"):
        st.info("La matriz está lista para cargarse cuando la necesites.")
        return None

    try:
        hoja_colaboradores = ws_colaboradores()
        if rol == "editor":
            return registro.mostrar_tabla(hoja_colaboradores)
        return registro.mostrar_tabla(hoja_colaboradores, razon)
    except Exception as e:
        st.error(f"No se pudo cargar la matriz de jerarquía: {e}")
        return None


# =========================
# BACKOFFICE
# =========================
if rol == "backoffice":
    if pagina == "Alta":
        hoja_colaboradores = ws_colaboradores()
        hoja_ubicaciones = ws_ubicaciones()
        hoja_asistencia = ws_asistencia()
        mostrar_formulario(hoja_colaboradores, hoja_ubicaciones, hoja_asistencia)
        mostrar_matriz_jerarquia()

    elif pagina == "Bajas":
        hoja_colaboradores = ws_colaboradores()
        df = mostrar_matriz_jerarquia()
        if df is not None:
            st.divider()
            registro.dar_de_baja(df, hoja_colaboradores, razon)

    elif pagina == "Presencialidad Dealer":
        # Solo carga la hoja Asistencia. No carga colaboradores ni ubicaciones.
        mostrar_asistencia(ws_asistencia(), None)
        mostrar_matriz_jerarquia("Estado actual de la jerarquía", "📋")

# =========================
# DEALER
# =========================
elif rol == "dealer":
    wow_section(f"Socio: {razon}", "📌")

    if pagina == "Alta":
        hoja_colaboradores = ws_colaboradores()
        hoja_ubicaciones = ws_ubicaciones()
        hoja_asistencia = ws_asistencia()
        mostrar_formulario(hoja_colaboradores, hoja_ubicaciones, hoja_asistencia)
        mostrar_matriz_jerarquia()

    elif pagina == "Bajas":
        hoja_colaboradores = ws_colaboradores()
        df = mostrar_matriz_jerarquia()
        if df is not None:
            st.divider()
            registro.dar_de_baja(df, hoja_colaboradores, razon)

    elif pagina == "Presencialidad Dealer":
        mostrar_asistencia(ws_asistencia(), None, razon=razon)
        mostrar_matriz_jerarquia("Estado actual de la jerarquía", "📋")

# =========================
# SOLO PRESENCIALIDAD
# =========================
elif rol in ("presencialidad", "presencialidad_dealer"):
    wow_section(f"Presencialidad Dealer: {razon}", "🗓️")
    if pagina == "Presencialidad Dealer":
        mostrar_asistencia(ws_asistencia(), None, razon=razon)
        mostrar_matriz_jerarquia("Estado actual de la jerarquía", "📋")

# =========================
# EDITOR
# =========================
elif rol == "editor":
    wow_section("Modo edición", "✏️")

    if pagina == "Edición":
        hoja_colaboradores = ws_colaboradores()
        df = mostrar_matriz_jerarquia()
        if df is not None:
            st.divider()
            registro.editar_registro(df, hoja_colaboradores, ws_ubicaciones())

    elif pagina == "Presencialidad Dealer":
        mostrar_asistencia(ws_asistencia(), None)
        mostrar_matriz_jerarquia("Estado actual de la jerarquía", "📋")

else:
    st.warning(f"Sin permisos para el rol: {rol}")
