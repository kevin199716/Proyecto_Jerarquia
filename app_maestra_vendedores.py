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
st.set_page_config(
    page_title="Sistema",
    layout="wide"
)


# =========================
# ESTILOS / CABECERA
# =========================
def pintar_estilos_base():
    st.markdown(
        """
        <style>
            .bloque-usuario {
                background: linear-gradient(90deg, #0B5ED7, #0D6EFD);
                color: white;
                padding: 12px 16px;
                border-radius: 12px;
                margin-bottom: 12px;
                font-weight: 600;
            }
            .bloque-usuario span {
                display: inline-block;
                margin-right: 22px;
            }
            div[data-testid="stRadio"] > div {
                background: #F3F7FF;
                padding: 10px;
                border-radius: 12px;
                border: 1px solid #D6E6FF;
            }
        </style>
        """,
        unsafe_allow_html=True
    )


def mostrar_barra_usuario(rol, razon):
    usuario = (
        st.session_state.get("usuario")
        or st.session_state.get("username")
        or st.session_state.get("user")
        or "Usuario"
    )

    razon_txt = razon if razon else "ALL"

    st.markdown(
        f"""
        <div class="bloque-usuario">
            <span>👤 Usuario: {usuario}</span>
            <span>🔐 Rol: {rol}</span>
            <span>🏢 Razón: {razon_txt}</span>
        </div>
        """,
        unsafe_allow_html=True
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


# =========================
# UI GENERAL
# =========================
pintar_estilos_base()

st.title("📊 Sistema de Vendedores")
mostrar_barra_usuario(rol, razon)


# =====================================================
# MENU
# =====================================================
def menu_paginas(opciones):
    return st.radio(
        "Módulo",
        opciones,
        horizontal=True,
        label_visibility="collapsed",
        key=f"menu_principal_{rol}"
    )


# =====================================================
# BACKOFFICE
# =====================================================
if rol == "backoffice":
    pagina = menu_paginas([
        "Registro",
        "Bajas",
        "Asistencia"
    ])

    if pagina == "Registro":
        hoja_colaboradores = get_worksheet("maestra_vendedores", "colaboradores")
        hoja_ubicaciones = get_worksheet("maestra_vendedores", "ubicaciones")

        mostrar_formulario(
            hoja_colaboradores,
            hoja_ubicaciones
        )

    elif pagina == "Bajas":
        hoja_colaboradores = get_worksheet("maestra_vendedores", "colaboradores")

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
        hoja_asistencia = get_worksheet("maestra_vendedores", "Asistencia")
        hoja_colaboradores = get_worksheet("maestra_vendedores", "colaboradores")

        mostrar_asistencia(
            hoja_asistencia,
            hoja_colaboradores,
            razon=razon,
            rol=rol
        )


# =====================================================
# DEALER
# =====================================================
elif rol == "dealer":
    st.subheader(f"📌 Socio: {razon}")

    pagina = menu_paginas([
        "Registro",
        "Bajas",
        "Asistencia"
    ])

    if pagina == "Registro":
        hoja_colaboradores = get_worksheet("maestra_vendedores", "colaboradores")
        hoja_ubicaciones = get_worksheet("maestra_vendedores", "ubicaciones")

        mostrar_formulario(
            hoja_colaboradores,
            hoja_ubicaciones
        )

    elif pagina == "Bajas":
        hoja_colaboradores = get_worksheet("maestra_vendedores", "colaboradores")

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
        hoja_asistencia = get_worksheet("maestra_vendedores", "Asistencia")
        hoja_colaboradores = get_worksheet("maestra_vendedores", "colaboradores")

        mostrar_asistencia(
            hoja_asistencia,
            hoja_colaboradores,
            razon=razon,
            rol=rol
        )


# =====================================================
# EDITOR
# =====================================================
elif rol == "editor":
    st.subheader("✏️ Modo edición")

    pagina = menu_paginas([
        "Edición",
        "Asistencia"
    ])

    if pagina == "Edición":
        hoja_colaboradores = get_worksheet("maestra_vendedores", "colaboradores")
        hoja_ubicaciones = get_worksheet("maestra_vendedores", "ubicaciones")

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
        hoja_asistencia = get_worksheet("maestra_vendedores", "Asistencia")
        hoja_colaboradores = get_worksheet("maestra_vendedores", "colaboradores")

        mostrar_asistencia(
            hoja_asistencia,
            hoja_colaboradores,
            razon=razon,
            rol=rol
        )


# =====================================================
# SIN PERMISOS
# =====================================================
else:
    st.warning(f"Sin permisos para el rol: {rol}")
