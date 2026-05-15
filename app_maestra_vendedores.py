import os
import sys

import streamlit as st

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# =========================
# IMPORTS ORIGINALES (BACKEND INTACTO)
# =========================
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

# 🆕 NUEVO — Tema centralizado
from wow_theme import (
    inject_global_theme,
    render_app_header,
    wow_section
)


# =========================
# CONFIG
# =========================
st.set_page_config(
    page_title="WOW D2D | Portal Vendedores",
    page_icon="🟣",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 🆕 Inyectar tema global UNA sola vez (reemplaza el viejo bloque <style>)
inject_global_theme()


# =========================
# CACHE SOLO PARA CONEXION
# =========================
@st.cache_resource(show_spinner=False)
def get_worksheet(nombre_hoja, nombre_worksheet):
    return conectar_google_sheets(
        nombre_hoja,
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
usuario = st.session_state.get("usuario", st.session_state.get("username", ""))


# =========================
# CONEXIONES GOOGLE SHEETS
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
# CABECERA WOW
# =========================
render_app_header(
    usuario=usuario,
    rol=rol,
    razon=razon
)


# =====================================================
# FUNCIONES UI
# =====================================================
def mostrar_matriz_jerarquia(titulo="Estado actual de la jerarquía", icono="📋"):
    st.divider()
    wow_section(titulo, icono)

    try:
        if rol == "editor":
            return registro.mostrar_tabla(
                hoja_colaboradores
            )

        return registro.mostrar_tabla(
            hoja_colaboradores,
            razon
        )

    except Exception as e:
        st.error(
            f"No se pudo cargar la matriz de jerarquía: {e}"
        )
        return None


def menu_modulos(opciones):
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

    pagina = menu_modulos([
        "Registro",
        "Bajas",
        "Asistencia"
    ])

    if pagina == "Registro":
        mostrar_formulario(
            hoja_colaboradores,
            hoja_ubicaciones
        )

        mostrar_matriz_jerarquia()

    elif pagina == "Bajas":
        df = mostrar_matriz_jerarquia()

        if df is not None:
            st.divider()
            registro.dar_de_baja(
                df,
                hoja_colaboradores,
                razon
            )

    elif pagina == "Asistencia":
        mostrar_asistencia(
            hoja_asistencia,
            hoja_colaboradores
        )

        mostrar_matriz_jerarquia()


# =====================================================
# DEALER
# =====================================================
elif rol == "dealer":

    wow_section(f"Socio: {razon}", "📌")

    pagina = menu_modulos([
        "Registro",
        "Bajas",
        "Asistencia"
    ])

    if pagina == "Registro":
        mostrar_formulario(
            hoja_colaboradores,
            hoja_ubicaciones
        )

        mostrar_matriz_jerarquia()

    elif pagina == "Bajas":
        df = mostrar_matriz_jerarquia()

        if df is not None:
            st.divider()
            registro.dar_de_baja(
                df,
                hoja_colaboradores,
                razon
            )

    elif pagina == "Asistencia":
        mostrar_asistencia(
            hoja_asistencia,
            hoja_colaboradores
        )

        mostrar_matriz_jerarquia()


# =====================================================
# EDITOR
# =====================================================
elif rol == "editor":

    wow_section("Modo edición", "✏️")

    pagina = menu_modulos([
        "Edición",
        "Asistencia"
    ])

    if pagina == "Edición":
        df = mostrar_matriz_jerarquia()

        if df is not None:
            st.divider()
            registro.editar_registro(
                df,
                hoja_colaboradores,
                hoja_ubicaciones
            )

    elif pagina == "Asistencia":
        mostrar_asistencia(
            hoja_asistencia,
            hoja_colaboradores
        )

        mostrar_matriz_jerarquia()


# =====================================================
# SIN PERMISOS
# =====================================================
else:
    st.warning(
        f"Sin permisos para el rol: {rol}"
    )
