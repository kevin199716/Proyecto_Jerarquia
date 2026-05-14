import streamlit as st
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
# CONEXION
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

except Exception as e:

    st.error(f"Error conexión Google Sheets: {e}")
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

    st.info("Registro OK")

# =====================================================
# BAJAS
# =====================================================

with tab2:

    st.info("Bajas OK")

# =====================================================
# ASISTENCIA
# =====================================================

with tab3:

    mostrar_asistencia(
        hoja_asistencia,
        hoja_colaboradores
    )