import os
import sys

import streamlit as st

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# =========================
# IMPORTS EXISTENTES
# =========================
import registro_mod as registro

from auth import (
    cargar_usuarios,
    login,
)

from ui_inicio import (
    mostrar_bienvenida,
)

from sheets import (
    conectar_google_sheets,
)

from formulario import (
    mostrar_formulario,
)

from asistencia import (
    mostrar_asistencia,
)


# =========================
# CONFIG
# =========================
st.set_page_config(
    page_title="Sistema",
    layout="wide",
)


# =========================
# CACHE SOLO CONEXIONES
# =========================
@st.cache_resource(show_spinner=False)
def get_worksheet(nombre_hoja, nombre_worksheet):
    return conectar_google_sheets(
        nombre_hoja,
        nombre_worksheet,
    )


# =========================
# USUARIOS / LOGIN
# =========================
USUARIOS = cargar_usuarios()

if "autenticado" not in st.session_state:
    st.session_state["autenticado"] = False

if not st.session_state["autenticado"]:
    mostrar_bienvenida()
    login(USUARIOS)
    st.stop()


# =========================
# GOOGLE SHEETS
# =========================
hoja_colaboradores = get_worksheet(
    "maestra_vendedores",
    "colaboradores",
)

hoja_ubicaciones = get_worksheet(
    "maestra_vendedores",
    "ubicaciones",
)

hoja_asistencia = get_worksheet(
    "maestra_vendedores",
    "Asistencia",
)


# =========================
# VARIABLES SESION
# =========================
rol = st.session_state.get("rol", "")
razon = st.session_state.get("razon", "")


# =========================
# TITLE
# =========================
st.title("📊 Sistema de Vendedores")


# =========================
# MENU SIN EJECUTAR TODO
# =========================
def seleccionar_modulo(opciones, key):
    return st.radio(
        "Módulo",
        opciones,
        horizontal=True,
        label_visibility="collapsed",
        key=key,
    )


# =====================================================
# BACKOFFICE
# =====================================================
if rol == "backoffice":
    modulo = seleccionar_modulo(
        ["Registro", "Bajas", "Asistencia"],
        "menu_backoffice",
    )

    if modulo == "Registro":
        mostrar_formulario(
            hoja_colaboradores,
            hoja_ubicaciones,
        )

    elif modulo == "Bajas":
        df = registro.mostrar_tabla(
            hoja_colaboradores,
            razon,
        )

        if df is not None:
            registro.dar_de_baja(
                df,
                hoja_colaboradores,
                razon,
            )

    elif modulo == "Asistencia":
        mostrar_asistencia(
            hoja_asistencia,
            hoja_colaboradores,
        )


# =====================================================
# DEALER
# =====================================================
elif rol == "dealer":
    st.subheader(f"📌 Socio: {razon}")

    modulo = seleccionar_modulo(
        ["Registro", "Bajas", "Asistencia"],
        "menu_dealer",
    )

    if modulo == "Registro":
        mostrar_formulario(
            hoja_colaboradores,
            hoja_ubicaciones,
        )

    elif modulo == "Bajas":
        df = registro.mostrar_tabla(
            hoja_colaboradores,
            razon,
        )

        if df is not None:
            registro.dar_de_baja(
                df,
                hoja_colaboradores,
                razon,
            )

    elif modulo == "Asistencia":
        mostrar_asistencia(
            hoja_asistencia,
            hoja_colaboradores,
        )


# =====================================================
# EDITOR
# =====================================================
elif rol == "editor":
    st.subheader("✏️ Modo edición")

    modulo = seleccionar_modulo(
        ["Edición", "Asistencia"],
        "menu_editor",
    )

    if modulo == "Edición":
        df = registro.mostrar_tabla(
            hoja_colaboradores,
        )

        if df is not None:
            registro.editar_registro(
                df,
                hoja_colaboradores,
                hoja_ubicaciones,
            )

    elif modulo == "Asistencia":
        mostrar_asistencia(
            hoja_asistencia,
            hoja_colaboradores,
        )


# =====================================================
# SIN PERMISOS
# =====================================================
else:
    st.warning(f"Sin permisos para el rol: {rol}")
