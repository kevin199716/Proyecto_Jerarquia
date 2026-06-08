"""
auth.py — Autenticación
v2.5.0 - Sin imagen EMPRESAS
"""
import json
import os
import textwrap
import streamlit as st

def cargar_usuarios():
    try:
        if os.path.exists("/etc/secrets/USUARIOS_CONTRASENAS"):
            with open("/etc/secrets/USUARIOS_CONTRASENAS") as f:
                return json.load(f)
        elif os.path.exists("usuarios.json"):
            with open("usuarios.json", encoding="utf-8") as f:
                return json.load(f)
        else:
            st.error("❌ No se encontró usuarios.json")
            st.stop()
    except Exception as e:
        st.error(f"❌ Error: {e}")
        st.stop()

def _md(html: str):
    st.markdown(textwrap.dedent(html), unsafe_allow_html=True)

def login(usuarios):
    from wow_theme import hide_sidebar_for_login
    hide_sidebar_for_login()

    col_hero, col_form = st.columns([1.05, 0.95], gap="medium")

    # HERO (izquierda)
    with col_hero:
        _md("""
<div class="wow-login-hero" style="border-radius:20px; height:100%; min-height:540px;">
<div class="brand" style="font-size:48px; font-weight:800; color:white; letter-spacing:-2px; margin-bottom:24px;">✦ WOW</div>
<div>
<div class="wow-login-eyebrow">✦ WOW</div>
<h1>Gestiona tu fuerza de ventas<br/><span class="accent">con claridad</span>.</h1>
<p>Jerarquía: Distrito, descansos médicos y vacaciones. Sincronizado en tiempo real.</p>
<div class="features">
<div class="feat"><div class="ico">👥</div> Altas y bajas</div>
<div class="feat"><div class="ico">🏥</div> Descansos médicos</div>
<div class="feat"><div class="ico">✈️</div> Vacaciones</div>
</div>
</div>
<div class="footer">© 2026 WAP Perú · v2.5.0</div>
</div>
""")

    # FORM (derecha)
    with col_form:
        _md("""
<div style="padding:24px 8px 0;">
<div class="wow-login-form-eyebrow">🔒 Acceso seguro</div>
<h2 style="margin:0 0 6px; font-size:26px; font-weight:800; color:var(--ink-900); letter-spacing:-0.4px;">Bienvenido de vuelta</h2>
<p style="margin:0 0 20px; font-size:13.5px; color:var(--ink-500); line-height:1.5;">Ingresa con tus credenciales corporativas para acceder al portal.</p>
</div>
""")

        usuario = st.text_input(
            "Usuario",
            key="user",
            placeholder="ej: admin",
        ).strip().lower()

        contraseña = st.text_input(
            "Contraseña",
            type="password",
            key="pass",
            placeholder="••••••••",
        ).strip()

        ingresar = st.button(
            "Ingresar al portal  →",
            key="btn_login",
            type="primary",
            use_container_width=True,
        )

        if ingresar:
            datos_usuario = usuarios.get(usuario)
            if datos_usuario and contraseña == str(datos_usuario.get("password")):
                if datos_usuario.get("estado") != "activo":
                    st.error("❌ Usuario inactivo")
                    return
                st.session_state["autenticado"] = True
                st.session_state["usuario"] = usuario
                st.session_state["rol"] = datos_usuario.get("rol")
                st.session_state["razon"] = datos_usuario.get("razon", "")
                st.success("✅ Ingreso correcto")
                st.rerun()
            else:
                st.error("❌ Usuario o contraseña incorrectos")

        _md("""
<div style="margin-top:18px; padding:12px 14px; background:#DFF1F6; border:1px solid #B7E2ED; border-radius:10px; color:#1F6A7E; font-size:12px; line-height:1.5; display:flex; gap:10px; align-items:flex-start;">
<span style="font-size:14px;">ℹ️</span>
<div><strong>¿Problemas para ingresar?</strong> Contacta: <strong style="color:#4B0067;">ksa@wowperu.pe</strong></div>
</div>
""")

    _md("""
<style>
.main button[kind="primary"] {
    background: #EC6608 !important;
    color: white !important;
    border: 1px solid #EC6608 !important;
    box-shadow: 0 6px 18px rgba(236,102,8,0.30) !important;
    font-weight: 700 !important;
    height: 48px !important;
    font-size: 14px !important;
}
.main button[kind="primary"]:hover {
    background: #D45605 !important;
    color: white !important;
}
</style>
""")
