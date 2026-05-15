import json
import os
import streamlit as st

# =========================
# CARGAR USUARIOS
# =========================
def cargar_usuarios():
    try:
        if os.path.exists("/etc/secrets/USUARIOS_CONTRASENAS"):
            with open("/etc/secrets/USUARIOS_CONTRASENAS") as f:
                return json.load(f)

        elif os.path.exists("usuarios.json"):
            with open("usuarios.json", encoding="utf-8") as f:
                return json.load(f)

        else:
            st.error("❌ No se encontró el archivo usuarios.json")
            st.stop()

    except Exception as e:
        st.error(f"❌ Error leyendo usuarios: {e}")
        st.stop()


# =========================
# LOGIN
# =========================
def login(usuarios):

    st.markdown(
        """
        <style>
            section[data-testid="stSidebar"] > div:first-child {
                background-color: #4B0067;
            }
            section[data-testid="stSidebar"] label,
            section[data-testid="stSidebar"] p,
            section[data-testid="stSidebar"] input,
            section[data-testid="stSidebar"] .stMarkdown p {
                color: white !important;
            }
            section[data-testid="stSidebar"] .stButton > button {
                background-color: #EC6608 !important;
                color: white !important;
                border: none !important;
                border-radius: 8px !important;
                width: 100%;
            }
            section[data-testid="stSidebar"] .stButton > button:hover {
                background-color: #c4550a !important;
            }
        </style>
        """,
        unsafe_allow_html=True
    )

    st.sidebar.markdown(
        "<p style='color:white; font-size:18px; font-weight:700; margin-bottom:8px;'>🔐 Ingreso de usuario</p>",
        unsafe_allow_html=True
    )

    usuario = st.sidebar.text_input("Usuario", key="user").strip().lower()
    contraseña = st.sidebar.text_input("Contraseña", type="password", key="pass").strip()

    if st.sidebar.button("Ingresar"):

        datos_usuario = usuarios.get(usuario)

        if datos_usuario and contraseña == str(datos_usuario.get("password")):

            if datos_usuario.get("estado") != "activo":
                st.sidebar.error("❌ Usuario inactivo")
                return

            st.session_state["autenticado"] = True
            st.session_state["usuario"] = usuario
            st.session_state["rol"] = datos_usuario.get("rol")
            st.session_state["razon"] = datos_usuario.get("razon", "")

            st.sidebar.success("✅ Ingreso correcto")
            st.rerun()

        else:
            st.sidebar.error("❌ Usuario o contraseña incorrectos")