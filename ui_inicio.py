import streamlit as st


def mostrar_bienvenida():
    """
    Pantalla previa al login.
    Se muestra en el área principal mientras la sidebar contiene el formulario de auth.
    El CSS viene del tema global (wow_theme.inject_global_theme).
    """

    # ── HERO con identidad WOW D2D ──────────────────────────────────────────────
    st.markdown(
        """
        <div class="wow-login-hero">
            <div class="wow-welcome-eyebrow">
                ✦ &nbsp; Portal de Vendedores
            </div>
            <h1>Gestiona tu fuerza de ventas<br/><span class="accent">con claridad</span>.</h1>
            <p>
                Altas, bajas, asistencia y jerarquía en un solo lugar.
                Toda la operación de WOW D2D, sincronizada en tiempo real.
            </p>
        </div>
        """,
        unsafe_allow_html=True
    )

    # ── Tres capacidades clave en grid ──────────────────────────────────────────
    st.markdown(
        """
        <div class="wow-action-grid">
            <div class="wow-action-card">
                <div class="ico" style="background:#FFF4EA; color:#D45605;">👥</div>
                <h4>Altas y bajas</h4>
                <p>Registra nuevos vendedores y gestiona ceses con motivos trazables.</p>
            </div>
            <div class="wow-action-card">
                <div class="ico" style="background:#FAF3FE; color:#4B0067;">🗓️</div>
                <h4>Asistencia diaria</h4>
                <p>Control mensual de promotores activos con sincronización a Drive.</p>
            </div>
            <div class="wow-action-card">
                <div class="ico" style="background:#DFF1F6; color:#1F6A7E;">📋</div>
                <h4>Jerarquía clara</h4>
                <p>Visualiza tu equipo: supervisores, coordinadores y dealers.</p>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    # ── Bloque de bienvenida tradicional ────────────────────────────────────────
    st.markdown(
        """
        <div class="wow-callout">
            <strong>👋 Bienvenido al Portal.</strong>
            Esta herramienta centraliza la gestión de tu fuerza de ventas.
            Ingresa con tus credenciales en el panel lateral para acceder a los módulos.
        </div>
        """,
        unsafe_allow_html=True
    )

    # ── Video corporativo (opcional) ────────────────────────────────────────────
    with st.expander("▶ Ver video introductorio (2 min)", expanded=False):
        st.markdown(
            """
            <video width="100%" controls style="border-radius:12px; box-shadow: 0 8px 24px rgba(0,0,0,0.1); margin-top: 6px;">
                <source src="https://raw.githubusercontent.com/leocorbur/st_apps/main/images/wowi.mp4" type="video/mp4">
                Tu navegador no soporta video HTML5.
            </video>
            """,
            unsafe_allow_html=True
        )

    # ── Footer de soporte ───────────────────────────────────────────────────────
    st.markdown(
        """
        <div style="
            margin-top: 20px;
            padding: 14px 18px;
            background: #DFF1F6;
            border: 1px solid #B7E2ED;
            border-radius: 10px;
            color: #1F6A7E;
            font-size: 13px;
            line-height: 1.55;
            display: flex;
            gap: 10px;
            align-items: flex-start;
        ">
            <span style="font-size:18px;">ℹ️</span>
            <div>
                <strong>¿Primera vez aquí?</strong>
                Si tienes dudas o necesitas asistencia, escríbenos a
                <strong>ksa@wowperu.pe</strong>.
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )
