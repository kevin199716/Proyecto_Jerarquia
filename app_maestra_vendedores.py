import streamlit as st
import sys
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import registro_mod as registro
from auth import cargar_usuarios, login
from ui_inicio import mostrar_bienvenida
from sheets import conectar_google_sheets
from formulario import mostrar_formulario

st.set_page_config(page_title="Sistema", layout="wide")

USUARIOS = cargar_usuarios()

if "autenticado" not in st.session_state:
    st.session_state["autenticado"] = False

if not st.session_state["autenticado"]:
    mostrar_bienvenida()
    login(USUARIOS)
    st.stop()

hoja_colaboradores = conectar_google_sheets("maestra_vendedores", "colaboradores")
hoja_ubicaciones = conectar_google_sheets("maestra_vendedores", "ubicaciones")

rol = st.session_state.get("rol")
razon = st.session_state.get("razon")

st.title("📊 Sistema de Vendedores")

# =========================
# ADMIN
# =========================
if rol == "backoffice":

    tab1, tab2 = st.tabs(["Registro", "Bajas"])

    with tab1:
        mostrar_formulario(hoja_colaboradores, hoja_ubicaciones)

    df = registro.mostrar_tabla(hoja_colaboradores, razon)

    if df is not None:
        with tab2:
            registro.dar_de_baja(df, hoja_colaboradores, razon)

# =========================
# DEALER (ESTO TE FALTABA)
# =========================
elif rol == "dealer":

    st.subheader(f"📌 Socio: {razon}")

    tab1, tab2 = st.tabs(["Registro", "Bajas"])

    with tab1:
        mostrar_formulario(hoja_colaboradores, hoja_ubicaciones)

    df = registro.mostrar_tabla(hoja_colaboradores, razon)

    if df is not None:
        with tab2:
            registro.dar_de_baja(df, hoja_colaboradores, razon)

# =========================
# EDITOR
# =========================
elif rol == "editor":

    st.subheader("✏️ Modo edición")

    df = registro.mostrar_tabla(hoja_colaboradores)

    if df is not None:
        registro.editar_registro(df, hoja_colaboradores, hoja_ubicaciones)

else:
    st.warning(f"Sin permisos para el rol: {rol}")