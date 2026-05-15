import json
import os
import streamlit as st


# =========================
# CARGAR USUARIOS  (BACKEND — NO CAMBIA)
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
# LOGIN  (UI rediseñada — backend intacto)
# =========================
def login(usuarios):
    """
    Sidebar de login con identidad WOW D2D:
    - Logo blanco
    - Etiqueta "Portal de Vendedores"
    - CTA naranja
    - Mensaje de soporte ksa@wowperu.pe
    Los estilos vienen del tema global (wow_theme.inject_global_theme).
    """

    # Logo + brand (solo sidebar — el bloque <style> global ya está inyectado por
    # app_maestra_vendedores.py vía inject_global_theme()).
    st.sidebar.markdown(
        """
        <div class="wow-sidebar-brand">
            <img src="https://raw.githubusercontent.com/leocorbur/st_apps/refs/heads/main/images/logo_horizontal_blanco.png"
                 alt="WOW D2D" />
            <div class="tag">Portal de Vendedores</div>
            <div class="bar"></div>
        </div>
        """,
        unsafe_allow_html=True
    )

    st.sidebar.markdown(
        '<div class="wow-sidebar-section-title">🔐 Acceso al portal</div>',
        unsafe_allow_html=True
    )

    usuario = st.sidebar.text_input(
        "Usuario",
        key="user",
        placeholder="ej: admin"
    ).strip().lower()

    contraseña = st.sidebar.text_input(
        "Contraseña",
        type="password",
        key="pass",
        placeholder="••••••••"
    ).strip()

    if st.sidebar.button("Ingresar al portal", key="btn_login"):

        datos_usuario = usuarios.get(usuario)

        if datos_usuario and contraseña == str(datos_usuario.get("password")):

            if datos_usuario.get("estado") != "activo":
                st.sidebar.error("❌ Usuario inactivo. Contacta a soporte.")
                return

            st.session_state["autenticado"] = True
            st.session_state["usuario"] = usuario
            st.session_state["rol"] = datos_usuario.get("rol")
            st.session_state["razon"] = datos_usuario.get("razon", "")

            st.sidebar.success("✅ Ingreso correcto")
            st.rerun()

        else:
            st.sidebar.error("❌ Usuario o contraseña incorrectos")

    # Soporte — visible siempre
    st.sidebar.markdown(
        """
        <div style="
            margin-top: 22px;
            padding: 12px 14px;
            background: rgba(255,255,255,0.08);
            border: 1px solid rgba(255,255,255,0.15);
            border-radius: 10px;
            color: rgba(255,255,255,0.85);
            font-size: 11.5px;
            line-height: 1.5;
        ">
            <div style="font-weight:700; margin-bottom:3px; color:white;">¿Problemas para ingresar?</div>
            Contacta a soporte:<br/>
            <strong style="color:#FFB07A;">ksa@wowperu.pe</strong>
        </div>
        """,
        unsafe_allow_html=True
    )
