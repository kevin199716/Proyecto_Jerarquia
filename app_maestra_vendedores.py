import os
import sys

import streamlit as st

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# =========================
# IMPORTS ORIGINALES
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


# =========================
# CONFIG
# =========================
st.set_page_config(
    page_title="WOW | Portal Vendedores",
    page_icon="🟣",
    layout="wide"
)


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
# ESTILO CABECERA WOW
# =========================
st.markdown(
    """
    <style>
        /* ── Cabecera ── */
        .cabecera-app {
            background: linear-gradient(135deg, #4B0067 0%, #A531EF 100%);
            padding: 14px 18px;
            border-radius: 10px;
            color: white;
            margin-bottom: 14px;
        }
        .cabecera-app h2 {
            margin: 0;
            color: white !important;
        }
        .cabecera-app p {
            margin: 4px 0 0 0;
            color: white !important;
            font-size: 14px;
        }
        /* ── Sidebar fondo morado ── */
        section[data-testid="stSidebar"] > div:first-child {
            background-color: #4B0067;
        }
        section[data-testid="stSidebar"] label,
        section[data-testid="stSidebar"] p,
        section[data-testid="stSidebar"] .stMarkdown p {
            color: white !important;
        }
        /* ── Botones CTA (form submit) ── */
        .stFormSubmitButton > button {
            background-color: #EC6608 !important;
            color: white !important;
            border: none !important;
            border-radius: 8px !important;
        }
        .stFormSubmitButton > button:hover {
            background-color: #c4550a !important;
            color: white !important;
        }
        /* ── Botones normales ── */
        .stButton > button {
            background-color: #A531EF !important;
            color: white !important;
            border: none !important;
            border-radius: 8px !important;
        }
        .stButton > button:hover {
            background-color: #4B0067 !important;
            color: white !important;
        }
        /* ── Subheaders WOW ── */
        .wow-section-title {
            color: #4B0067;
            font-weight: 800;
            font-size: 1.1em;
            border-bottom: 3px solid #EC6608;
            padding-bottom: 6px;
            margin-bottom: 12px;
            display: inline-block;
        }
    </style>
    """,
    unsafe_allow_html=True
)

st.markdown(
    f"""
    <div class="cabecera-app">
        <h2>📊 Sistema de Vendedores</h2>
        <p><b>Usuario:</b> {usuario if usuario else '-'} &nbsp; | &nbsp; <b>Rol:</b> {rol if rol else '-'} &nbsp; | &nbsp; <b>Razón:</b> {razon if razon else '-'}</p>
    </div>
    """,
    unsafe_allow_html=True
)


# =====================================================
# FUNCIONES UI
# =====================================================
def mostrar_matriz_jerarquia(titulo="📋 Estado actual de la jerarquía"):
    st.divider()
    st.subheader(titulo)

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

    st.subheader(
        f"📌 Socio: {razon}"
    )

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

    st.subheader(
        "✏️ Modo edición"
    )

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
