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

# =========================
# CONFIG
# =========================
st.set_page_config(page_title="Sistema", layout="wide")

# =========================
# CACHE CONEXIONES GOOGLE
# =========================
@st.cache_resource(show_spinner=False)
def get_worksheet(nombre_archivo: str, nombre_worksheet: str):
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
# VARIABLES SESION
# =========================
rol = st.session_state.get("rol", "")
razon = st.session_state.get("razon", "")

# =========================
# CONEXIONES
# =========================
hoja_colaboradores = get_worksheet("maestra_vendedores", "colaboradores")
hoja_ubicaciones = get_worksheet("maestra_vendedores", "ubicaciones")
hoja_asistencia = get_worksheet("maestra_vendedores", "Asistencia")

# =========================
# UI
# =========================
st.title("📊 Sistema de Vendedores")

# IMPORTANTE:
# No uso st.tabs porque Streamlit ejecuta todas las pestañas en cada selección.
# Con radio horizontal solo corre la pantalla seleccionada y baja la demora.

def navegar(opciones):
    return st.radio(
        "Módulo",
        opciones,
        horizontal=True,
        label_visibility="collapsed",
        key=f"nav_{rol}",
    )

if rol == "backoffice":
    pagina = navegar(["Registro", "Bajas", "Asistencia"])

    if pagina == "Registro":
        mostrar_formulario(hoja_colaboradores, hoja_ubicaciones)

    elif pagina == "Bajas":
        df = registro.mostrar_tabla(hoja_colaboradores, razon)
        if df is not None:
            registro.dar_de_baja(df, hoja_colaboradores, razon)

    elif pagina == "Asistencia":
        mostrar_asistencia(hoja_asistencia, hoja_colaboradores)

elif rol == "dealer":
    st.subheader(f"📌 Socio: {razon}")
    pagina = navegar(["Registro", "Bajas", "Asistencia"])

    if pagina == "Registro":
        mostrar_formulario(hoja_colaboradores, hoja_ubicaciones)

    elif pagina == "Bajas":
        df = registro.mostrar_tabla(hoja_colaboradores, razon)
        if df is not None:
            registro.dar_de_baja(df, hoja_colaboradores, razon)

    elif pagina == "Asistencia":
        mostrar_asistencia(hoja_asistencia, hoja_colaboradores)

elif rol == "editor":
    st.subheader("✏️ Modo edición")
    pagina = navegar(["Edición", "Asistencia"])

    if pagina == "Edición":
        df = registro.mostrar_tabla(hoja_colaboradores)
        if df is not None:
            registro.editar_registro(df, hoja_colaboradores, hoja_ubicaciones)

    elif pagina == "Asistencia":
        mostrar_asistencia(hoja_asistencia, hoja_colaboradores)

else:
    st.warning(f"Sin permisos para el rol: {rol}")
