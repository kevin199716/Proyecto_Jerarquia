# =====================================================
# app_maestra_vendedores.py
# =====================================================

import streamlit as st
import sys
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# =====================================================
# IMPORTS
# =====================================================

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

# =====================================================
# CONFIG
# =====================================================

st.set_page_config(
    page_title="Sistema",
    layout="wide"
)

# =====================================================
# USUARIOS
# =====================================================

USUARIOS = cargar_usuarios()

# =====================================================
# SESSION
# =====================================================

if "autenticado" not in st.session_state:

    st.session_state["autenticado"] = False

# =====================================================
# LOGIN
# =====================================================

if not st.session_state["autenticado"]:

    mostrar_bienvenida()

    login(USUARIOS)

    st.stop()

# =====================================================
# SHEETS
# =====================================================

hoja_colaboradores = conectar_google_sheets(
    "maestra_vendedores",
    "colaboradores"
)

hoja_ubicaciones = conectar_google_sheets(
    "maestra_vendedores",
    "ubicaciones"
)

hoja_asistencia = conectar_google_sheets(
    "maestra_vendedores",
    "Asistencia"
)

# =====================================================
# VARIABLES
# =====================================================

rol = st.session_state.get("rol")

razon = st.session_state.get("razon")

# =====================================================
# TITLE
# =====================================================

st.title("📊 Sistema de Vendedores")

# =====================================================
# MENU
# =====================================================

if rol == "editor":

    menu = st.radio(
        "Menú",
        ["Edición", "Asistencia"],
        horizontal=True
    )

else:

    menu = st.radio(
        "Menú",
        ["Registro", "Bajas", "Asistencia"],
        horizontal=True
    )

# =====================================================
# REGISTRO
# =====================================================

if menu == "Registro":

    mostrar_formulario(
        hoja_colaboradores,
        hoja_ubicaciones
    )

# =====================================================
# BAJAS
# =====================================================

elif menu == "Bajas":

    df = registro.mostrar_tabla(
        hoja_colaboradores,
        razon
    )

    if df is not None:

        registro.dar_de_baja(
            df,
            hoja_colaboradores,
            razon
        )

# =====================================================
# EDICION
# =====================================================

elif menu == "Edición":

    df = registro.mostrar_tabla(
        hoja_colaboradores
    )

    if df is not None:

        registro.editar_registro(
            df,
            hoja_colaboradores,
            hoja_ubicaciones
        )

# =====================================================
# ASISTENCIA
# =====================================================

elif menu == "Asistencia":

    mostrar_asistencia(
        hoja_asistencia,
        hoja_colaboradores
    )