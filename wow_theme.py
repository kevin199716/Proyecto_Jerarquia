"""
wow_theme.py — Sistema de diseño WOW D2D (CSS centralizado + helpers)

Este módulo contiene TODO el CSS y los componentes HTML reutilizables del rediseño.
No tiene lógica de negocio; solo presentación.

Uso típico:
    from wow_theme import inject_global_theme, render_app_header, wow_section, wow_pill

    st.set_page_config(page_title="WOW D2D | Portal Vendedores", page_icon="🟣", layout="wide")
    inject_global_theme()
    render_app_header(usuario="admin", rol="backoffice", razon="MALUTECH S.A.C.")
"""

import streamlit as st


# =====================================================
# CSS GLOBAL
# =====================================================
_THEME_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;600&display=swap');

:root {
    /* Brand WOW */
    --wow-purple-900: #2A003D;
    --wow-purple-800: #3a0052;
    --wow-purple-700: #4B0067;
    --wow-purple-500: #A531EF;
    --wow-purple-100: #F3E5FA;
    --wow-purple-50:  #FAF3FE;

    --wow-orange-600: #D45605;
    --wow-orange-500: #EC6608;
    --wow-orange-100: #FDE6D2;
    --wow-orange-50:  #FFF4EA;

    --wow-sky-200: #B7E2ED;
    --wow-sky-100: #DFF1F6;

    --wow-pink-200: #F5D4D9;
    --wow-pink-100: #FAE8EA;
    --wow-pink-50:  #FDF4F5;

    /* Neutrales */
    --ink-900: #1A1521;
    --ink-700: #3D3548;
    --ink-500: #6B6175;
    --ink-400: #8F8898;
    --ink-300: #C8C2CE;
    --ink-200: #E5E0EA;
    --ink-100: #F2EEF5;
    --ink-50:  #F8F6FA;

    /* Semánticos */
    --success-700: #1F7A47;
    --success-100: #D7F0DF;
    --danger-700: #B3261E;
    --danger-100: #F8DAD7;
    --warning-700: #8A5A00;
    --warning-100: #FFE8B3;

    /* Tokens UI */
    --shadow-sm: 0 1px 2px rgba(26,21,33,0.06), 0 1px 1px rgba(26,21,33,0.04);
    --shadow-md: 0 4px 12px rgba(26,21,33,0.07);
    --shadow-brand: 0 8px 24px rgba(75,0,103,0.25);
    --shadow-cta: 0 6px 18px rgba(236,102,8,0.30);
}

/* ── Tipografía global ── */
html, body, [class*="css"], .stApp {
    font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif !important;
    color: var(--ink-900);
}
code, kbd, pre, .mono {
    font-family: 'JetBrains Mono', monospace !important;
}

/* ── Layout: respiración del contenedor principal ── */
.main .block-container {
    padding-top: 1.5rem;
    padding-bottom: 4rem;
    max-width: 1280px;
}

/* ── Sidebar morado WOW ── */
section[data-testid="stSidebar"] > div:first-child {
    background: linear-gradient(180deg, #4B0067 0%, #3a0052 100%);
}
section[data-testid="stSidebar"] label,
section[data-testid="stSidebar"] p,
section[data-testid="stSidebar"] .stMarkdown p,
section[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p,
section[data-testid="stSidebar"] [data-testid="stWidgetLabel"] span {
    color: white !important;
}
section[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p {
    font-size: 11px !important;
    font-weight: 700 !important;
    letter-spacing: 0.4px;
    text-transform: uppercase;
    opacity: 0.85;
}
section[data-testid="stSidebar"] input,
section[data-testid="stSidebar"] input::placeholder {
    color: var(--ink-900) !important;
}
section[data-testid="stSidebar"] input {
    background: white !important;
    border: 1.5px solid rgba(255,255,255,0.2) !important;
    border-radius: 10px !important;
    padding: 10px 12px !important;
    font-size: 14px !important;
}
section[data-testid="stSidebar"] input:focus {
    border-color: var(--wow-orange-500) !important;
    box-shadow: 0 0 0 3px rgba(236,102,8,0.25) !important;
}

/* CTA naranja en sidebar */
section[data-testid="stSidebar"] .stButton > button {
    background: var(--wow-orange-500) !important;
    color: white !important;
    border: none !important;
    border-radius: 10px !important;
    width: 100%;
    height: 44px;
    font-weight: 700 !important;
    font-size: 14px !important;
    letter-spacing: 0.2px;
    box-shadow: var(--shadow-cta);
    transition: filter 0.15s, transform 0.1s;
}
section[data-testid="stSidebar"] .stButton > button:hover {
    background: var(--wow-orange-600) !important;
    filter: brightness(1.02);
}
section[data-testid="stSidebar"] .stButton > button:active {
    transform: translateY(1px);
}

/* ── Botones (área principal) ── */
.stFormSubmitButton > button {
    background: var(--wow-orange-500) !important;
    color: white !important;
    border: none !important;
    border-radius: 10px !important;
    padding: 9px 18px !important;
    font-weight: 700 !important;
    font-size: 13px !important;
    letter-spacing: 0.2px;
    box-shadow: var(--shadow-cta);
}
.stFormSubmitButton > button:hover {
    background: var(--wow-orange-600) !important;
    color: white !important;
}
.stButton > button {
    background: var(--wow-purple-500) !important;
    color: white !important;
    border: none !important;
    border-radius: 10px !important;
    padding: 9px 18px !important;
    font-weight: 700 !important;
    font-size: 13px !important;
    box-shadow: 0 4px 12px rgba(165,49,239,0.25);
    transition: filter 0.15s;
}
.stButton > button:hover {
    background: var(--wow-purple-700) !important;
    color: white !important;
    filter: brightness(1.02);
}

/* ── Title de sección WOW (clase existente) ── */
.wow-section-title {
    display: inline-block;
    color: var(--ink-900);
    font-weight: 700;
    font-size: 16px;
    letter-spacing: -0.2px;
    border-bottom: 3px solid var(--wow-orange-500);
    padding-bottom: 6px;
    margin: 18px 0 12px;
}

/* ── Labels de campos ── */
[data-testid="stWidgetLabel"] p,
.stSelectbox label,
.stTextInput label,
.stDateInput label {
    color: var(--wow-purple-700) !important;
    font-weight: 600 !important;
    font-size: 12px !important;
    letter-spacing: 0.3px;
    text-transform: uppercase;
}

/* ── Inputs ── */
.stTextInput > div > div > input,
[data-testid="stTextInput"] input,
[data-testid="stDateInput"] input {
    border: 1.5px solid var(--ink-200) !important;
    border-radius: 10px !important;
    background: white !important;
    padding: 10px 14px !important;
    font-size: 13px !important;
    color: var(--ink-900) !important;
}
.stTextInput > div > div > input:focus,
[data-testid="stTextInput"] input:focus,
[data-testid="stDateInput"] input:focus {
    border-color: var(--wow-purple-500) !important;
    box-shadow: 0 0 0 3px rgba(165,49,239,0.15) !important;
}
.stTextInput > div > div > input:disabled,
[data-testid="stTextInput"] input:disabled {
    background: var(--ink-100) !important;
    color: var(--ink-500) !important;
    border-color: var(--ink-200) !important;
}

/* ── Selectboxes ── */
.stSelectbox > div > div,
div[data-baseweb="select"] > div {
    border: 1.5px solid var(--ink-200) !important;
    border-radius: 10px !important;
    background: white !important;
    min-height: 42px;
}
.stSelectbox > div > div:focus-within,
div[data-baseweb="select"] > div:focus-within {
    border-color: var(--wow-purple-500) !important;
    box-shadow: 0 0 0 3px rgba(165,49,239,0.15) !important;
}

/* ── Menú de navegación (radio horizontal) ── */
div[data-testid="stHorizontalBlock"] [data-testid="stRadio"] > div { gap: 8px; }
div[data-testid="stRadio"] label {
    background: white;
    border: 1.5px solid var(--ink-200);
    border-radius: 999px;
    padding: 7px 18px !important;
    color: var(--ink-700) !important;
    font-weight: 600 !important;
    transition: all 0.15s;
    cursor: pointer;
}
div[data-testid="stRadio"] label:hover {
    background: var(--wow-purple-50);
    border-color: var(--wow-purple-100);
    color: var(--wow-purple-700) !important;
}
div[data-testid="stRadio"] label[data-checked="true"],
div[data-testid="stRadio"] label:has(input:checked) {
    background: var(--wow-purple-700) !important;
    border-color: var(--wow-purple-700) !important;
    color: white !important;
    box-shadow: var(--shadow-brand);
}

/* ── Divisor ── */
hr { border-color: var(--ink-100) !important; margin: 1.5rem 0 !important; }

/* ── Scrollbars ── */
::-webkit-scrollbar { width: 10px; height: 10px; }
::-webkit-scrollbar-thumb { background: var(--ink-200); border-radius: 5px; }
::-webkit-scrollbar-thumb:hover { background: var(--ink-300); }

/* ── Alerts (Streamlit st.success / st.error / st.warning / st.info) ── */
[data-testid="stAlert"] {
    border-radius: 12px !important;
    border: 1px solid transparent !important;
    padding: 14px 16px !important;
}

/* ============================================================
   COMPONENTES PERSONALIZADOS WOW
   ============================================================ */

/* ── App header (post-login) ── */
.wow-app-header {
    background: linear-gradient(120deg, #2A003D 0%, #4B0067 50%, #6E1098 100%);
    border-radius: 16px;
    padding: 22px 28px;
    margin-bottom: 22px;
    position: relative;
    overflow: hidden;
    box-shadow: var(--shadow-brand);
    color: white;
}
.wow-app-header::before {
    content: "";
    position: absolute; right: -50px; top: -50px;
    width: 240px; height: 240px;
    border-radius: 50%;
    background: radial-gradient(circle, rgba(236,102,8,0.35), transparent 65%);
    pointer-events: none;
}
.wow-app-header-row {
    position: relative;
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 16px;
}
.wow-app-header h1 {
    margin: 0;
    font-size: 22px;
    font-weight: 800;
    letter-spacing: -0.4px;
    color: white !important;
}
.wow-app-header-sub {
    margin: 2px 0 0;
    font-size: 13px;
    color: rgba(255,255,255,0.78) !important;
}
.wow-app-header-meta {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
}

/* ── Pills (chips de metadata) ── */
.wow-pill {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 4px 11px;
    border-radius: 999px;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.3px;
    text-transform: uppercase;
    border: 1px solid;
}
.wow-pill-orange    { background: rgba(236,102,8,0.18);  color: #FFD0A8; border-color: rgba(236,102,8,0.35); }
.wow-pill-purple    { background: rgba(255,255,255,0.10); color: white;   border-color: rgba(255,255,255,0.22); }
.wow-pill-light     { background: var(--wow-purple-50);  color: var(--wow-purple-700); border-color: var(--wow-purple-100); }

/* ── Welcome card (bienvenida) ── */
.wow-welcome {
    background: white;
    border: 1px solid var(--ink-200);
    border-radius: 16px;
    padding: 28px 32px;
    margin-bottom: 18px;
    box-shadow: var(--shadow-sm);
    position: relative;
}
.wow-welcome-banner {
    background: linear-gradient(120deg, #2A003D 0%, #4B0067 60%, #6E1098 100%);
    border-radius: 16px;
    padding: 28px 32px;
    margin-bottom: 18px;
    color: white;
    position: relative;
    overflow: hidden;
    box-shadow: var(--shadow-brand);
}
.wow-welcome-banner::before {
    content: "";
    position: absolute; right: -60px; top: -60px;
    width: 320px; height: 320px;
    border-radius: 50%;
    background: radial-gradient(circle, rgba(236,102,8,0.35), transparent 65%);
}
.wow-welcome-banner-content { position: relative; }
.wow-welcome-eyebrow {
    display: inline-flex; align-items: center; gap: 6px;
    background: rgba(255,255,255,0.12);
    border: 1px solid rgba(255,255,255,0.22);
    color: rgba(255,255,255,0.9);
    border-radius: 999px;
    padding: 4px 12px;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 1.2px;
    text-transform: uppercase;
    margin-bottom: 14px;
}
.wow-welcome h2 {
    color: white !important;
    margin: 0 0 8px;
    font-size: 28px;
    font-weight: 800;
    letter-spacing: -0.5px;
    line-height: 1.15;
}
.wow-welcome p { font-size: 14px; color: rgba(255,255,255,0.82) !important; margin: 0; line-height: 1.55; max-width: 640px; }

/* ── KPI cards ── */
.wow-kpi-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 18px; }
.wow-kpi {
    background: white;
    border: 1px solid var(--ink-200);
    border-radius: 14px;
    padding: 16px;
    box-shadow: var(--shadow-sm);
}
.wow-kpi-icon {
    width: 34px; height: 34px;
    border-radius: 9px;
    display: grid; place-items: center;
    margin-bottom: 10px;
    font-size: 16px;
}
.wow-kpi-icon.purple { background: var(--wow-purple-50);  color: var(--wow-purple-700); }
.wow-kpi-icon.orange { background: var(--wow-orange-50);  color: var(--wow-orange-600); }
.wow-kpi-icon.sky    { background: var(--wow-sky-100);     color: #1F6A7E; }
.wow-kpi-icon.success{ background: #ECF8F0;                color: var(--success-700); }
.wow-kpi-value { font-size: 24px; font-weight: 800; color: var(--ink-900); letter-spacing: -0.4px; line-height: 1.1; }
.wow-kpi-label { font-size: 12px; color: var(--ink-500); margin-top: 2px; }

/* ── Action cards ── */
.wow-action-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-bottom: 12px; }
.wow-action-card {
    background: white;
    border: 1.5px solid var(--ink-200);
    border-radius: 12px;
    padding: 16px;
    text-decoration: none;
    color: inherit;
    display: block;
    transition: transform 0.15s, box-shadow 0.15s, border-color 0.15s;
}
.wow-action-card:hover {
    transform: translateY(-2px);
    box-shadow: var(--shadow-md);
    border-color: var(--wow-orange-500);
}
.wow-action-card .ico {
    width: 38px; height: 38px;
    border-radius: 10px;
    display: grid; place-items: center;
    background: var(--wow-purple-50);
    color: var(--wow-purple-700);
    margin-bottom: 12px;
    font-size: 18px;
}
.wow-action-card h4 { margin: 0 0 4px; font-size: 14px; font-weight: 700; color: var(--ink-900); }
.wow-action-card p  { margin: 0; font-size: 12px; color: var(--ink-500); line-height: 1.45; }

/* ── Pink callout (info contextual) ── */
.wow-callout {
    background: var(--wow-pink-100);
    border: 1px solid var(--wow-pink-200);
    border-left: 4px solid var(--wow-orange-500);
    border-radius: 10px;
    padding: 14px 18px;
    margin: 14px 0;
    color: var(--wow-purple-700);
    font-size: 13px;
    line-height: 1.55;
}
.wow-callout strong { color: var(--wow-purple-700); }

/* ── Login (área principal) ── */
.wow-login-hero {
    background:
      radial-gradient(700px 400px at 0% 0%, rgba(165,49,239,0.45), transparent 60%),
      radial-gradient(500px 300px at 100% 100%, rgba(236,102,8,0.30), transparent 55%),
      linear-gradient(135deg, #2A003D 0%, #4B0067 55%, #6E1098 100%);
    border-radius: 16px;
    padding: 32px 36px;
    color: white;
    box-shadow: var(--shadow-brand);
    position: relative;
    overflow: hidden;
    margin-bottom: 18px;
}
.wow-login-hero h1 {
    margin: 14px 0 8px;
    font-size: 32px;
    font-weight: 800;
    letter-spacing: -0.5px;
    line-height: 1.1;
    color: white !important;
}
.wow-login-hero h1 .accent { color: #FFB07A; }
.wow-login-hero p { font-size: 14px; color: rgba(255,255,255,0.82); margin: 0; line-height: 1.55; max-width: 520px; }

/* ── Sidebar login header ── */
.wow-sidebar-brand {
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 8px 0 18px;
}
.wow-sidebar-brand img { max-width: 100%; height: 32px; object-fit: contain; }
.wow-sidebar-brand .tag {
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 1.5px;
    color: rgba(255,255,255,0.6);
    text-transform: uppercase;
    margin-top: 8px;
}
.wow-sidebar-brand .bar {
    width: 36px; height: 3px;
    background: var(--wow-orange-500);
    border-radius: 2px;
    margin-top: 8px;
}
.wow-sidebar-section-title {
    color: white !important;
    font-size: 13px;
    font-weight: 700;
    letter-spacing: 0.3px;
    margin: 18px 0 6px;
    display: flex; align-items: center; gap: 6px;
}

/* ── Responsive ── */
@media (max-width: 900px) {
    .wow-kpi-row { grid-template-columns: 1fr 1fr; }
    .wow-action-grid { grid-template-columns: 1fr; }
    .wow-app-header { padding: 18px 20px; }
    .wow-app-header h1 { font-size: 18px; }
    .wow-welcome-banner { padding: 22px 22px; }
    .wow-welcome-banner h2 { font-size: 22px; }
    .main .block-container { padding-left: 1rem; padding-right: 1rem; }
}
@media (max-width: 600px) {
    .wow-kpi-row { grid-template-columns: 1fr 1fr; gap: 8px; }
    .wow-kpi { padding: 12px; }
    .wow-kpi-value { font-size: 20px; }
}
</style>
"""


def inject_global_theme():
    """Inyecta el CSS global de WOW D2D. Llamar UNA vez después de st.set_page_config."""
    st.markdown(_THEME_CSS, unsafe_allow_html=True)


# =====================================================
# COMPONENTES HTML REUTILIZABLES
# =====================================================
def render_app_header(usuario: str, rol: str, razon: str):
    """Cabecera principal post-login con saludo + meta info."""
    usuario_safe = usuario.capitalize() if usuario else "—"
    rol_safe = rol or "—"
    razon_safe = razon or "—"

    st.markdown(
        f"""
        <div class="wow-app-header">
          <div class="wow-app-header-row">
            <div>
              <h1>Portal de Vendedores</h1>
              <p class="wow-app-header-sub">
                Hola, <strong>{usuario_safe}</strong> · sesión activa
              </p>
            </div>
            <div class="wow-app-header-meta">
              <span class="wow-pill wow-pill-orange">{rol_safe}</span>
              <span class="wow-pill wow-pill-purple">{razon_safe}</span>
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def wow_section(titulo: str, icono: str = ""):
    """Subheader con barra naranja inferior (estilo WOW). Reemplazo de st.subheader()."""
    safe = f"{icono} {titulo}".strip()
    st.markdown(
        f'<span class="wow-section-title">{safe}</span>',
        unsafe_allow_html=True,
    )


def wow_callout(texto_html: str):
    """Bloque rosa con borde naranja para mensajes contextuales."""
    st.markdown(f'<div class="wow-callout">{texto_html}</div>', unsafe_allow_html=True)
