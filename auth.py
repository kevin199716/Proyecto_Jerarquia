import json
import os
import streamlit as st

def cargar_usuarios():
    try:
        if os.path.exists("/etc/secrets/USUARIOS_CONTRASENAS"):
            with open("/etc/secrets/USUARIOS_CONTRASENAS") as f:
                return json.load(f)

        elif os.path.exists("usuarios.json"):
            with open("usuarios.json") as f:
                return json.load(f)

        else:
            st.error("❌ No se encontró el archivo de usuarios.")
            st.stop()

    except Exception as e:
        st.error(f"❌ Error al leer usuarios: {e}")
        st.stop()


def login(usuarios: dict):

    st.sidebar.title("🔐 Ingreso de usuario")
    usuario = st.sidebar.text_input("Usuario")
    contraseña = st.sidebar.text_input("Contraseña", type="password")
    ingresar = st.sidebar.button("Ingresar")

    if ingresar:

        datos_usuario = usuarios.get(usuario)

        if datos_usuario and datos_usuario.get("password") == contraseña:

            if datos_usuario.get("estado") == "activo":

                st.session_state["autenticado"] = True
                st.session_state["usuario"] = usuario
                st.session_state["rol"] = datos_usuario.get("rol")

                # 🔥 ESTE ES EL CAMBIO CLAVE
                st.session_state["razon"] = datos_usuario.get("razon", "")

                st.success("✅ Ingreso exitoso")
                st.rerun()

            else:
                st.sidebar.error("❌ Usuario inactivo")

        else:
            st.sidebar.error("❌ Usuario o contraseña incorrectos")