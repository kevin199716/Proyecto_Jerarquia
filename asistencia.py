import streamlit as st
import sys
import os
from datetime import datetime

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
    page_title="Sistema de Vendedores",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =====================================================
# ESTILO GLOBAL
# =====================================================

st.markdown("""

<style>

.block-container {
    padding-top: 1rem;
}

div[data-testid="stMetric"] {
    background: #FFFFFF;
    border-radius: 14px;
    padding: 14px;
    border-left: 6px solid #8B5CF6;
    box-shadow: 0px 2px 10px rgba(0,0,0,0.06);
}

</style>

""", unsafe_allow_html=True)

# =====================================================
# USUARIOS
# =====================================================

USUARIOS = cargar_usuarios()

# =====================================================
# SESSION
# =====================================================

if "autenticado" not in st.session_state:
    st.session_state["autenticado"] = False

if "ultima_actividad" not in st.session_state:
    st.session_state["ultima_actividad"] = datetime.now()

# =====================================================
# LOGIN
# =====================================================

if not st.session_state["autenticado"]:

    mostrar_bienvenida()

    login(USUARIOS)

    st.stop()

# =====================================================
# GOOGLE SHEETS
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
# TITULO
# =====================================================

st.title("📊 Sistema de Vendedores")

# =====================================================
# BACKOFFICE
# =====================================================

if rol == "backoffice":

    tab1, tab2, tab3 = st.tabs([
        "Registro",
        "Bajas",
        "Asistencia"
    ])

    # =================================================
    # REGISTRO
    # =================================================

    with tab1:

        mostrar_formulario(
            hoja_colaboradores,
            hoja_ubicaciones
        )

    # =================================================
    # TABLA
    # =================================================

    df = registro.mostrar_tabla(
        hoja_colaboradores,
        razon
    )

    # =================================================
    # BAJAS
    # =================================================

    if df is not None:

        with tab2:

            registro.dar_de_baja(
                df,
                hoja_colaboradores,
                razon
            )

    # =================================================
    # ASISTENCIA
    # =================================================

    with tab3:

        mostrar_asistencia(
            hoja_asistencia,
            hoja_colaboradores
        )

# =====================================================
# DEALER
# =====================================================

elif rol == "dealer":

    st.subheader(
        f"📌 Socio: {razon}"
    )

    tab1, tab2, tab3 = st.tabs([
        "Registro",
        "Bajas",
        "Asistencia"
    ])

    # =================================================
    # REGISTRO
    # =================================================

    with tab1:

        mostrar_formulario(
            hoja_colaboradores,
            hoja_ubicaciones
        )

    # =================================================
    # TABLA
    # =================================================

    df = registro.mostrar_tabla(
        hoja_colaboradores,
        razon
    )

    # =================================================
    # BAJAS
    # =================================================

    if df is not None:

        with tab2:

            registro.dar_de_baja(
                df,
                hoja_colaboradores,
                razon
            )

    # =================================================
    # ASISTENCIA
    # =================================================

    with tab3:

        mostrar_asistencia(
            hoja_asistencia,
            hoja_colaboradores
        )

# =====================================================
# EDITOR
# =====================================================

elif rol == "editor":

    st.subheader(
        "✏️ Modo edición"
    )

    tab1, tab2 = st.tabs([
        "Edición",
        "Asistencia"
    ])

    # =================================================
    # EDICION
    # =================================================

    with tab1:

        df = registro.mostrar_tabla(
            hoja_colaboradores
        )

        if df is not None:

            registro.editar_registro(
                df,
                hoja_colaboradores,
                hoja_ubicaciones
            )

    # =================================================
    # ASISTENCIA
    # =================================================

    with tab2:

        mostrar_asistencia(
            hoja_asistencia,
            hoja_colaboradores
        )

# =====================================================
# SIN PERMISOS
# =====================================================

else:

    st.warning(
        f"Sin permisos para el rol: {rol}"
    )