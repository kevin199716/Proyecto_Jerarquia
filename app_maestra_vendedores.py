# =========================
# app_maestra_vendedores.py
# =========================

import streamlit as st
import traceback

from sheets import conectar_google_sheets
from asistencia import mostrar_asistencia

# =====================================================
# CONFIG
# =====================================================

st.set_page_config(
    page_title="Sistema de Vendedores",
    layout="wide"
)

# =====================================================
# TITULO
# =====================================================

st.title("📊 Sistema de Vendedores")

# =====================================================
# SESSION
# =====================================================

if "logeado" not in st.session_state:
    st.session_state.logeado = True

# =====================================================
# GOOGLE SHEETS
# =====================================================

try:

    hoja_colaboradores = conectar_google_sheets(
        "maestra_vendedores",
        "colaboradores"
    )

    hoja_asistencia = conectar_google_sheets(
        "maestra_vendedores",
        "Asistencia"
    )

except Exception:

    st.error("❌ Error conexión Google Sheets")
    st.code(traceback.format_exc())
    st.stop()

# =====================================================
# TABS
# =====================================================

tab1, tab2, tab3 = st.tabs([
    "Registro",
    "Bajas",
    "Asistencia"
])

# =====================================================
# REGISTRO
# =====================================================

with tab1:

    st.success("✅ Registro OK")

# =====================================================
# BAJAS
# =====================================================

with tab2:

    st.success("✅ Bajas OK")

# =====================================================
# ASISTENCIA
# =====================================================

with tab3:

    mostrar_asistencia(
        hoja_asistencia,
        hoja_colaboradores
    )