import os, sys
import streamlit as st

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import registro_mod as registro
from auth import cargar_usuarios, login
from ui_inicio import mostrar_bienvenida
from sheets import conectar_google_sheets, conectar_google_sheets_opcional
from formulario import mostrar_formulario
from asistencia import mostrar_asistencia
from cobranza_calidad import mostrar_cobranza
from wow_theme import inject_global_theme, render_app_header, render_sidebar_user, render_sidebar_help, wow_section

st.set_page_config(page_title="WOW", page_icon="🟣", layout="wide", initial_sidebar_state="expanded")
inject_global_theme()

@st.cache_resource(show_spinner=False)
def get_worksheet(nombre_hoja, nombre_worksheet):
    return conectar_google_sheets(nombre_hoja, nombre_worksheet)

USUARIOS = cargar_usuarios()
if "autenticado" not in st.session_state:
    st.session_state["autenticado"] = False

if not st.session_state["autenticado"]:
    mostrar_bienvenida()
    login(USUARIOS)
    st.stop()

rol     = st.session_state.get("rol", "")
razon   = st.session_state.get("razon", "")
usuario = st.session_state.get("usuario", st.session_state.get("username", ""))

# CONEXIONES
hoja_colaboradores = get_worksheet("maestra_vendedores", "colaboradores")
hoja_ubicaciones   = get_worksheet("maestra_vendedores", "ubicaciones")
hoja_asistencia    = get_worksheet("maestra_vendedores", "Asistencia")
hoja_sustentos     = get_worksheet("maestra_vendedores", "Sustentos_Bajas")

# SIDEBAR
render_sidebar_user(usuario=usuario, rol=rol, razon=razon)

if rol == "backoffice":
    opciones_menu = ["Alta", "Bajas", "Presencialidad Dealer", "Cobranza_Calidad"]
elif rol == "dealer":
    opciones_menu = ["Alta", "Bajas", "Presencialidad Dealer"]
elif rol in ("presencialidad", "presencialidad_dealer"):
    opciones_menu = ["Bajas", "Presencialidad Dealer", "Cobranza_Calidad"]
elif rol == "editor":
    opciones_menu = ["Edición", "Presencialidad Dealer"]
else:
    opciones_menu = []

if opciones_menu:
    pagina = st.sidebar.radio("Módulo", opciones_menu, label_visibility="collapsed", key=f"nav_{rol}")
else:
    pagina = ""

st.sidebar.markdown("<div style='height:14px;'></div>", unsafe_allow_html=True)
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
        if rol == "editor":
            return registro.mostrar_tabla(hoja_colaboradores)
        return registro.mostrar_tabla(hoja_colaboradores, razon)
    except Exception as e:
        st.error(f"Error cargando matriz: {e}")
        return None

# BACKOFFICE
if rol == "backoffice":
    if pagina == "Alta":
        mostrar_formulario(hoja_colaboradores, hoja_ubicaciones)
        mostrar_matriz_jerarquia()
    elif pagina == "Bajas":
        df = mostrar_matriz_jerarquia()
        if df is not None:
            st.divider()
            registro.dar_de_baja(df, hoja_colaboradores, razon)
    elif pagina == "Presencialidad Dealer":
        mostrar_asistencia(hoja_asistencia, hoja_colaboradores, hoja_sustentos=hoja_sustentos)
        mostrar_matriz_jerarquia()
    elif pagina == "Cobranza_Calidad":
        hoja_cobranza, error_conexion = conectar_google_sheets_opcional("Facturas - Calidad", "Consolidado")
        if error_conexion:
            st.error(f"❌ No se pudo conectar con el módulo de Cobranza:\n\n{error_conexion}")
        else:
            mostrar_cobranza(hoja_cobranza, razon)

# DEALER
elif rol == "dealer":
    wow_section(f"Socio: {razon}", "📌")
    if pagina == "Alta":
        mostrar_formulario(hoja_colaboradores, hoja_ubicaciones)
        mostrar_matriz_jerarquia()
    elif pagina == "Bajas":
        df = mostrar_matriz_jerarquia()
        if df is not None:
            st.divider()
            registro.dar_de_baja(df, hoja_colaboradores, razon)
    elif pagina == "Presencialidad Dealer":
        mostrar_asistencia(hoja_asistencia, hoja_colaboradores, hoja_sustentos=hoja_sustentos, razon=razon)
        mostrar_matriz_jerarquia()

# PRESENCIALIDAD
elif rol in ("presencialidad", "presencialidad_dealer"):
    wow_section(f"Presencialidad Dealer: {razon}", "🗓️")
    if pagina == "Bajas":
        df = mostrar_matriz_jerarquia()
        if df is not None:
            st.divider()
            registro.dar_de_baja(df, hoja_colaboradores, razon)
    elif pagina == "Presencialidad Dealer":
        mostrar_asistencia(hoja_asistencia, hoja_colaboradores, hoja_sustentos=hoja_sustentos, razon=razon)
        mostrar_matriz_jerarquia()
    elif pagina == "Cobranza_Calidad":
        hoja_cobranza, error_conexion = conectar_google_sheets_opcional("Facturas - Calidad", "Consolidado")
        if error_conexion:
            st.error(f"❌ {error_conexion}")
        else:
            mostrar_cobranza(hoja_cobranza, razon)

# EDITOR
elif rol == "editor":
    wow_section("Modo edición", "✏️")
    if pagina == "Edición":
        df = mostrar_matriz_jerarquia()
        if df is not None:
            st.divider()
            registro.editar_registro(df, hoja_colaboradores, hoja_ubicaciones)
    elif pagina == "Presencialidad Dealer":
        mostrar_asistencia(hoja_asistencia, hoja_colaboradores, hoja_sustentos=hoja_sustentos)
        mostrar_matriz_jerarquia()

else:
    st.warning(f"Sin permisos para el rol: {rol}")
