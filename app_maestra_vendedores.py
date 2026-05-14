import os
import sys

import streamlit as st

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# =========================
# IMPORTS DEL PROYECTO
# =========================
import registro_mod as registro

from auth import cargar_usuarios, login
from ui_inicio import mostrar_bienvenida
from sheets import conectar_google_sheets
from formulario import mostrar_formulario
from asistencia import mostrar_asistencia


# =========================
# CONFIG STREAMLIT
# =========================
st.set_page_config(
    page_title="Sistema",
    layout="wide"
)


# =========================
# CACHE DE CONEXIONES
# =========================
@st.cache_resource(show_spinner=False)
def get_worksheet(nombre_archivo: str, nombre_worksheet: str):
    return conectar_google_sheets(
        nombre_archivo,
        nombre_worksheet
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
# VARIABLES DE SESION
# =========================
rol = st.session_state.get("rol", "")
razon = st.session_state.get("razon", "")


# =========================
# GOOGLE SHEETS
# =========================
hoja_colaboradores = get_worksheet(
    "maestra_vendedores",
    "colaboradores"
)

hoja_ubicaciones = get_worksheet(
    "maestra_vendedores",
    "ubicaciones"
)

hoja_asistencia = get_worksheet(
    "maestra_vendedores",
    "Asistencia"
)


# =========================
# UI PRINCIPAL
# =========================
st.title("📊 Sistema de Vendedores")


# IMPORTANTE:
# No usamos st.tabs para evitar que Streamlit ejecute Registro, Bajas y Asistencia al mismo tiempo.
# Con radio solo se ejecuta el modulo seleccionado, reduciendo congelamientos en Render.
def menu_paginas(opciones, key_menu):
    return st.radio(
        "Módulo",
        opciones,
        horizontal=True,
        label_visibility="collapsed",
        key=key_menu
    )


# =====================================================
# BACKOFFICE
# =====================================================
if rol == "backoffice":

    pagina = menu_paginas(
        ["Registro", "Bajas", "Asistencia"],
        "menu_backoffice"
    )

    if pagina == "Registro":
        mostrar_formulario(
            hoja_colaboradores,
            hoja_ubicaciones
        )

    elif pagina == "Bajas":
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

    elif pagina == "Asistencia":
        mostrar_asistencia(
            hoja_asistencia,
            hoja_colaboradores,
            razon_usuario=razon,
            rol_usuario=rol
        )


# =====================================================
# DEALER
# =====================================================
elif rol == "dealer":

    st.subheader(f"📌 Socio: {razon}")

    pagina = menu_paginas(
        ["Registro", "Bajas", "Asistencia"],
        "menu_dealer"
    )

    if pagina == "Registro":
        mostrar_formulario(
            hoja_colaboradores,
            hoja_ubicaciones
        )

    elif pagina == "Bajas":
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

    elif pagina == "Asistencia":
        mostrar_asistencia(
            hoja_asistencia,
            hoja_colaboradores,
            razon_usuario=razon,
            rol_usuario=rol
        )


# =====================================================
# EDITOR
# =====================================================
elif rol == "editor":

    st.subheader("✏️ Modo edición")

    pagina = menu_paginas(
        ["Edición", "Asistencia"],
        "menu_editor"
    )

    if pagina == "Edición":
        df = registro.mostrar_tabla(
            hoja_colaboradores
        )

        if df is not None:
            registro.editar_registro(
                df,
                hoja_colaboradores,
                hoja_ubicaciones
            )

    elif pagina == "Asistencia":
        mostrar_asistencia(
            hoja_asistencia,
            hoja_colaboradores,
            razon_usuario=razon,
            rol_usuario=rol
        )


# =====================================================
# SIN PERMISOS
# =====================================================
else:
    st.warning(f"Sin permisos para el rol: {rol}")
