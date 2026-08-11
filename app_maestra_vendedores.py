import streamlit as st

from auth import cargar_usuarios, login
from ui_inicio import mostrar_bienvenida
from sheets import conectar_google_sheets
from formulario import mostrar_formulario
from registro import dar_de_baja, mostrar_tabla_por_rol, editar_registros, blacklist

st.set_page_config(page_title="Formulario de Registro", page_icon="📝", layout="wide")

# =========================
# USUARIOS
# =========================
USUARIOS = cargar_usuarios()

# =========================
# SESIÓN
# =========================
if "autenticado" not in st.session_state:
    st.session_state["autenticado"] = False

if not st.session_state["autenticado"]:
    mostrar_bienvenida()
    login(USUARIOS)
    st.stop()

# =========================
# CONEXIÓN A GOOGLE SHEETS
# =========================
hoja_colaboradores = conectar_google_sheets("maestra_vendedores", "colaboradores")
hoja_ubicaciones = conectar_google_sheets("maestra_vendedores", "ubicaciones")

# =========================
# DATOS DE SESIÓN
# =========================
correo_usuario = st.session_state["usuario"]
rol_usuario = st.session_state["rol"]

# =========================
# FORMULARIO NUEVO
# =========================
if rol_usuario == "backoffice":
    mostrar_formulario(hoja_colaboradores, hoja_ubicaciones)

# =========================
# TABLA Y ACCIONES
# =========================
df, df_usuario = mostrar_tabla_por_rol(
    hoja_colaboradores,
    correo_usuario,
    rol_usuario,
    USUARIOS
)

if df is not None and df_usuario is not None:

    if rol_usuario == "backoffice":
        editar_registros(
            df,
            df_usuario,
            hoja_colaboradores,
            correo_usuario,
            hoja_ubicaciones,
            []  # ya no usamos dominios_permitidos
        )

        dar_de_baja(
            df,
            df_usuario,
            hoja_colaboradores,
            correo_usuario
        )

    if rol_usuario == "supervisor":
        blacklist(df_usuario, hoja_colaboradores)