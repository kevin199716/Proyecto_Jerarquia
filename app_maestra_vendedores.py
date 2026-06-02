# app_maestra_vendedores.py
# FIX_APP_SQL_PRESENCIALIDAD_LAZY_SHEETS_20260602

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
def get_worksheet(nombre_hoja, nombre_worksheet):
    return conectar_google_sheets(nombre_hoja, nombre_worksheet)

# IMPORTANTE:
# Ya NO conectamos Google Sheets al inicio.
# Si entras a Presencialidad Dealer, trabaja con PostgreSQL y no toca Drive.
def get_colaboradores_sheet():
    return get_worksheet("maestra_vendedores", "colaboradores")

def get_ubicaciones_sheet():
    return get_worksheet("maestra_vendedores", "ubicaciones")

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

if rol in ("backoffice", "dealer"):
    opciones_menu = ["Alta", "Bajas", "Presencialidad Dealer"]
elif rol == "editor":
    opciones_menu = ["Edición", "Presencialidad Dealer"]
elif rol in ("presencialidad", "presencialidad_dealer"):
    opciones_menu = ["Presencialidad Dealer"]
else:
    opciones_menu = []

if opciones_menu:
    pagina = st.sidebar.radio(
        "Módulo",
        opciones_menu,
        label_visibility="collapsed",
        key=f"nav_{rol}",
    )
else:
    pagina = ""

st.sidebar.markdown("<div style='height: 14px;'></div>", unsafe_allow_html=True)
if st.sidebar.button("🚪 Cerrar sesión", key="btn_logout"):
    for k in ["autenticado", "usuario", "rol", "razon", "user", "pass"]:
        if k in st.session_state:
            del st.session_state[k]
    st.rerun()

render_sidebar_help()
render_app_header(usuario=usuario, rol=rol, razon=razon)


def mostrar_matriz_jerarquia(titulo="Estado actual de la jerarquía", icono="📋"):
    st.divider()
    wow_section(titulo, icono)
    try:
        hoja_colaboradores = get_colaboradores_sheet()
        if rol == "editor":
            return registro.mostrar_tabla(hoja_colaboradores)
        return registro.mostrar_tabla(hoja_colaboradores, razon)
    except Exception as e:
        st.error(f"No se pudo cargar la matriz de jerarquía: {e}")
        return None


if rol == "backoffice":
    if pagina == "Alta":
        mostrar_formulario(get_colaboradores_sheet(), get_ubicaciones_sheet())
        mostrar_matriz_jerarquia()

    elif pagina == "Bajas":
        df = mostrar_matriz_jerarquia()
        if df is not None:
            st.divider()
            registro.dar_de_baja(df, get_colaboradores_sheet(), razon)

    elif pagina == "Presencialidad Dealer":
        # SQL: no usa hoja_asistencia ni hoja_colaboradores.
        mostrar_asistencia(None, None, razon=razon)

elif rol == "dealer":
    wow_section(f"Socio: {razon}", "📌")

    if pagina == "Alta":
        mostrar_formulario(get_colaboradores_sheet(), get_ubicaciones_sheet())
        mostrar_matriz_jerarquia()

    elif pagina == "Bajas":
        df = mostrar_matriz_jerarquia()
        if df is not None:
            st.divider()
            registro.dar_de_baja(df, get_colaboradores_sheet(), razon)

    elif pagina == "Presencialidad Dealer":
        # SQL: no usa hoja_asistencia ni hoja_colaboradores.
        mostrar_asistencia(None, None, razon=razon)

elif rol == "editor":
    wow_section("Modo edición", "✏️")

    if pagina == "Edición":
        df = mostrar_matriz_jerarquia()
        if df is not None:
            st.divider()
            registro.editar_registro(df, get_colaboradores_sheet(), get_ubicaciones_sheet())

    elif pagina == "Presencialidad Dealer":
        # SQL: no usa hoja_asistencia ni hoja_colaboradores.
        mostrar_asistencia(None, None, razon=razon)

elif rol in ("presencialidad", "presencialidad_dealer"):
    wow_section(f"Presencialidad Dealer: {razon}", "🗓️")
    if pagina == "Presencialidad Dealer":
        # SQL: no usa hoja_asistencia ni hoja_colaboradores.
        mostrar_asistencia(None, None, razon=razon)

else:
    st.warning(f"Sin permisos para el rol: {rol}")
