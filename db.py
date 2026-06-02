"""
auth.py — v3
Fix crítico: usar textwrap.dedent() para que st.markdown no interprete el HTML
indentado como bloque de código.
"""
import json
import os
import textwrap

import streamlit as st


# =========================
# CARGAR USUARIOS — BACKEND INTACTO
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


# Helper para no repetir textwrap.dedent
def _md(html: str):
    st.markdown(textwrap.dedent(html), unsafe_allow_html=True)


# =========================
# LOGIN — v3
# =========================
def login(usuarios):
    from wow_theme import hide_sidebar_for_login
    hide_sidebar_for_login()

    col_hero, col_form = st.columns([1.05, 0.95], gap="medium")

    # ─── HERO (col izquierda) ───────────────────────────────────────────────
    with col_hero:
        _md("""
<div class="wow-login-hero" style="border-radius:20px; height:100%; min-height:540px;">
<div class="brand"><img src="https://raw.githubusercontent.com/leocorbur/st_apps/refs/heads/main/images/logo_horizontal_blanco.png" alt="WOW D2D" /></div>
<div>
<div class="wow-login-eyebrow">✦ Portal de Vendedores</div>
<h1>Gestiona tu fuerza de ventas<br/><span class="accent">con claridad</span>.</h1>
<p>Altas, bajas, asistencia y jerarquía en un solo lugar. Toda la operación de WOW D2D, sincronizada en tiempo real.</p>
<div class="features">
<div class="feat"><div class="ico">👥</div> Altas y bajas</div>
<div class="feat"><div class="ico">🗓️</div> Asistencia diaria</div>
<div class="feat"><div class="ico">📋</div> Jerarquía</div>
</div>
</div>
<div class="footer">© 2026 WOW Perú · v2.4.0</div>
</div>
""")

    # ─── FORM (col derecha) ─────────────────────────────────────────────────
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
                    st.error("❌ Usuario inactivo. Contacta a soporte.")
                    return
                st.session_state["autenticado"] = True
                st.session_state["usuario"] = usuario
                st.session_state["rol"] = datos_usuario.get("rol")
                st.session_state["razon"] = datos_usuario.get("razon", "")
                st.success("✅ Ingreso correcto")
                st.rerun()
            else:
                st.error("❌ Usuario o contraseña incorrectos")

        # Caja de soporte
        _md("""
<div style="margin-top:18px; padding:12px 14px; background:#DFF1F6; border:1px solid #B7E2ED; border-radius:10px; color:#1F6A7E; font-size:12px; line-height:1.5; display:flex; gap:10px; align-items:flex-start;">
<span style="font-size:14px;">ℹ️</span>
<div><strong>¿Problemas para ingresar?</strong> Contacta al área de soporte: <strong style="color:#4B0067;">ksa@wowperu.pe</strong></div>
</div>
""")

    # Botón primary naranja en main area (override final con !important)
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
