"""
wow_theme.py — v5

Rollback de v4: quita el wrapping agresivo de tablas/formularios/sidebar
y deja SOLO el cambio de color en las cabeceras (column headers) de
los dataframes de vendedores.

Cambios reales en v5 respecto a v3:
- CSS de glide-data-grid: cabeceras moradas con tipografía bold uppercase
- NO se aplica gradient bar a forms
- NO se aplica border wrapper a contenedores
- Sidebar morado intacto
"""

import textwrap
import streamlit as st


def _md(html: str):
    st.markdown(textwrap.dedent(html), unsafe_allow_html=True)


_THEME_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;600&display=swap');

:root {
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
    --ink-900: #1A1521;
    --ink-700: #3D3548;
    --ink-500: #6B6175;
    --ink-400: #8F8898;
    --ink-300: #C8C2CE;
    --ink-200: #E5E0EA;
    --ink-100: #F2EEF5;
    --ink-50:  #F8F6FA;
    --success-700: #1F7A47;
    --success-100: #D7F0DF;
    --danger-700: #B3261E;
    --danger-100: #F8DAD7;
    --warning-700: #8A5A00;
    --warning-100: #FFE8B3;
    --shadow-sm: 0 1px 2px rgba(26,21,33,0.06), 0 1px 1px rgba(26,21,33,0.04);
    --shadow-md: 0 4px 12px rgba(26,21,33,0.07);
    --shadow-brand: 0 8px 24px rgba(75,0,103,0.25);
    --shadow-cta: 0 6px 18px rgba(236,102,8,0.30);
}

html, body, [class*="css"], .stApp {
    font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif !important;
    color: var(--ink-900);
}
code, kbd, pre, .mono { font-family: 'JetBrains Mono', monospace !important; }

.main .block-container {
    padding-top: 1rem !important;
    padding-bottom: 4rem;
    max-width: 1280px;
}
[data-testid="stHeader"] { display: none !important; height: 0 !important; }
.stApp > header { height: 0 !important; }

/* ============================================================
   SIDEBAR POST-LOGIN — morado con nav vertical
   ============================================================ */
section[data-testid="stSidebar"] > div:first-child {
    background: linear-gradient(180deg, #4B0067 0%, #3a0052 100%);
    padding-top: 1.5rem;
}
section[data-testid="stSidebar"] label,
section[data-testid="stSidebar"] p,
section[data-testid="stSidebar"] .stMarkdown p,
section[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p,
section[data-testid="stSidebar"] [data-testid="stWidgetLabel"] span,
section[data-testid="stSidebar"] h1,
section[data-testid="stSidebar"] h2,
section[data-testid="stSidebar"] h3 {
    color: white !important;
}
body[data-wow-hide-sidebar="true"] section[data-testid="stSidebar"],
body[data-wow-hide-sidebar="true"] [data-testid="collapsedControl"] { display: none !important; }

section[data-testid="stSidebar"] [data-testid="stRadio"] > label { display: none; }
section[data-testid="stSidebar"] [data-testid="stRadio"] > div {
    flex-direction: column !important; gap: 4px !important;
}
section[data-testid="stSidebar"] [data-testid="stRadio"] label {
    background: transparent !important;
    border: none !important;
    border-radius: 10px !important;
    padding: 11px 14px !important;
    color: rgba(255,255,255,0.78) !important;
    font-weight: 600 !important;
    font-size: 13.5px !important;
    width: 100%;
    cursor: pointer;
    transition: background 0.15s;
}
section[data-testid="stSidebar"] [data-testid="stRadio"] label:hover {
    background: rgba(255,255,255,0.08) !important;
    color: white !important;
}
section[data-testid="stSidebar"] [data-testid="stRadio"] label:has(input:checked) {
    background: rgba(255,255,255,0.14) !important;
    color: white !important;
    box-shadow: inset 3px 0 0 var(--wow-orange-500);
    font-weight: 700 !important;
}
section[data-testid="stSidebar"] input {
    background: white !important;
    color: var(--ink-900) !important;
    border: 1.5px solid rgba(255,255,255,0.2) !important;
    border-radius: 10px !important;
    padding: 10px 12px !important;
    font-size: 14px !important;
}
section[data-testid="stSidebar"] .stButton > button {
    background: rgba(255,255,255,0.08) !important;
    color: white !important;
    border: 1px solid rgba(255,255,255,0.18) !important;
    border-radius: 10px !important;
    width: 100%; height: 42px;
    font-weight: 600 !important; font-size: 13px !important;
}
section[data-testid="stSidebar"] .stButton > button:hover {
    background: rgba(236,102,8,0.20) !important;
    border-color: rgba(236,102,8,0.4) !important;
}

/* ============================================================
   BOTONES área principal
   ============================================================ */
.main .stFormSubmitButton > button {
    background: var(--wow-orange-500) !important;
    color: white !important; border: none !important;
    border-radius: 10px !important; padding: 10px 22px !important;
    font-weight: 700 !important; font-size: 13.5px !important;
    box-shadow: var(--shadow-cta);
}
.main .stFormSubmitButton > button:hover { background: var(--wow-orange-600) !important; }
.main .stButton > button {
    background: var(--wow-purple-500) !important;
    color: white !important; border: none !important;
    border-radius: 10px !important; padding: 9px 18px !important;
    font-weight: 700 !important; font-size: 13px !important;
    box-shadow: 0 4px 12px rgba(165,49,239,0.25);
}
.main .stButton > button:hover { background: var(--wow-purple-700) !important; }

/* ============================================================
   SECTION TITLES (wow-section-title) — clase usada por los módulos
   ============================================================ */
.wow-section-title {
    display: inline-block;
    color: var(--ink-900);
    font-weight: 700; font-size: 16px;
    letter-spacing: -0.2px;
    border-bottom: 3px solid var(--wow-orange-500);
    padding-bottom: 6px;
    margin: 22px 0 14px;
}

/* ============================================================
   INPUTS / SELECTS área principal
   ============================================================ */
.main [data-testid="stWidgetLabel"] p,
.main .stSelectbox label,
.main .stTextInput label,
.main .stDateInput label {
    color: var(--wow-purple-700) !important;
    font-weight: 600 !important; font-size: 12px !important;
    letter-spacing: 0.3px; text-transform: uppercase;
}
.main .stTextInput > div > div > input,
.main [data-testid="stTextInput"] input,
.main [data-testid="stDateInput"] input {
    border: 1.5px solid var(--ink-200) !important;
    border-radius: 10px !important;
    background: white !important;
    padding: 10px 14px !important;
    font-size: 13px !important;
}
.main .stTextInput > div > div > input:focus,
.main [data-testid="stTextInput"] input:focus,
.main [data-testid="stDateInput"] input:focus {
    border-color: var(--wow-purple-500) !important;
    box-shadow: 0 0 0 3px rgba(165,49,239,0.15) !important;
}
.main .stSelectbox > div > div,
.main div[data-baseweb="select"] > div {
    border: 1.5px solid var(--ink-200) !important;
    border-radius: 10px !important; background: white !important;
    min-height: 42px;
}

/* ============================================================
   TABLAS DE VENDEDORES — SOLO color de cabeceras (column headers)
   ============================================================ */
/* glide-data-grid: variables CSS para tematizar el canvas internamente */
.glideDataEditor,
[data-testid="stDataFrame"] > div,
[data-testid="stDataEditor"] > div {
    --gdg-bg-header: #4B0067;
    --gdg-bg-header-hovered: #6E1098;
    --gdg-bg-header-has-focus: #6E1098;
    --gdg-text-header: #FFFFFF;
    --gdg-text-header-selected: #FFFFFF;
    --gdg-header-bottom-border-color: #3a0052;
    --gdg-accent-color: #A531EF;
    --gdg-accent-fg: white;
    --gdg-accent-light: rgba(165,49,239,0.10);
    --gdg-bg-cell: #FFFFFF;
    --gdg-bg-cell-medium: #FAF8FC;
    --gdg-text-dark: #1A1521;
    --gdg-text-medium: #6B6175;
    --gdg-border-color: #E5E0EA;
    --gdg-font-family: 'Plus Jakarta Sans', -apple-system, sans-serif;
    --gdg-header-font-style: 700 12px;
    --gdg-base-font-style: 13px;
}

/* ============================================================
   DIVIDER
   ============================================================ */
hr { border-color: var(--ink-100) !important; margin: 1.5rem 0 !important; }

/* ============================================================
   ALERTS
   ============================================================ */
[data-testid="stAlert"] {
    border-radius: 12px !important;
    padding: 14px 16px !important;
    border: 1px solid !important;
}
[data-testid="stAlert"][kind="success"] { background: var(--success-100) !important; border-color: #B0DCC1 !important; color: var(--success-700) !important; }
[data-testid="stAlert"][kind="error"]   { background: var(--danger-100) !important;  border-color: #ECB7B3 !important; color: var(--danger-700) !important; }
[data-testid="stAlert"][kind="warning"] { background: var(--warning-100) !important; border-color: #F0D78A !important; color: var(--warning-700) !important; }
[data-testid="stAlert"][kind="info"]    { background: var(--wow-sky-100) !important; border-color: var(--wow-sky-200) !important; color: #1F6A7E !important; }

/* ============================================================
   COMPONENTES — Login / Header / Sidebar
   ============================================================ */
.wow-login-hero {
    background:
      radial-gradient(700px 400px at 0% 0%, rgba(165,49,239,0.45), transparent 60%),
      radial-gradient(500px 300px at 100% 100%, rgba(236,102,8,0.30), transparent 55%),
      linear-gradient(135deg, #2A003D 0%, #4B0067 55%, #6E1098 100%);
    color: white;
    padding: 44px 48px;
    display: flex; flex-direction: column; justify-content: space-between;
    position: relative; overflow: hidden;
    border-radius: 20px;
    box-shadow: var(--shadow-brand);
    min-height: 540px;
}
.wow-login-hero .brand img { height: 32px; }
.wow-login-eyebrow {
    display: inline-flex; align-items: center; gap: 6px;
    background: rgba(255,255,255,0.12);
    border: 1px solid rgba(255,255,255,0.22);
    color: rgba(255,255,255,0.9);
    border-radius: 999px;
    padding: 5px 14px;
    font-size: 11px; font-weight: 700;
    letter-spacing: 1.2px; text-transform: uppercase;
    margin-bottom: 18px;
}
.wow-login-hero h1 {
    margin: 0 0 14px; font-size: 34px; font-weight: 800;
    letter-spacing: -0.5px; line-height: 1.1; color: white !important;
}
.wow-login-hero h1 .accent { color: #FFB07A; }
.wow-login-hero p {
    font-size: 14px; color: rgba(255,255,255,0.82) !important;
    margin: 0; line-height: 1.55; max-width: 480px;
}
.wow-login-hero .features { display: flex; gap: 24px; margin-top: 32px; flex-wrap: wrap; }
.wow-login-hero .feat {
    display: flex; align-items: center; gap: 8px;
    font-size: 12px; color: rgba(255,255,255,0.85); font-weight: 500;
}
.wow-login-hero .feat .ico {
    width: 28px; height: 28px; border-radius: 8px;
    background: rgba(255,255,255,0.12);
    border: 1px solid rgba(255,255,255,0.18);
    display: grid; place-items: center; font-size: 14px;
}
.wow-login-hero .footer { font-size: 11px; color: rgba(255,255,255,0.5); letter-spacing: 0.5px; }
.wow-login-form-eyebrow {
    display: inline-flex; align-items: center; gap: 6px;
    background: var(--wow-orange-50);
    border: 1px solid var(--wow-orange-100);
    color: var(--wow-orange-600);
    border-radius: 999px;
    padding: 5px 11px;
    font-size: 11px; font-weight: 700;
    letter-spacing: 1px; text-transform: uppercase;
    margin-bottom: 18px;
}

.wow-app-header {
    background: linear-gradient(120deg, #2A003D 0%, #4B0067 50%, #6E1098 100%);
    border-radius: 16px;
    padding: 20px 26px;
    margin: 0 0 22px;
    position: relative; overflow: hidden;
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
    display: flex; justify-content: space-between;
    align-items: center; flex-wrap: wrap; gap: 16px;
}
.wow-app-header h1 {
    margin: 0; font-size: 20px; font-weight: 800;
    letter-spacing: -0.4px; color: white !important;
}
.wow-app-header-sub {
    margin: 2px 0 0; font-size: 12.5px;
    color: rgba(255,255,255,0.78) !important;
}
.wow-app-header-meta { display: flex; gap: 8px; flex-wrap: wrap; }
.wow-pill {
    display: inline-flex; align-items: center; gap: 4px;
    padding: 4px 11px; border-radius: 999px;
    font-size: 11px; font-weight: 700;
    letter-spacing: 0.3px; text-transform: uppercase;
    border: 1px solid;
}
.wow-pill-orange { background: rgba(236,102,8,0.18); color: #FFD0A8; border-color: rgba(236,102,8,0.35); }
.wow-pill-purple { background: rgba(255,255,255,0.10); color: white; border-color: rgba(255,255,255,0.22); }

.wow-sidebar-brand-pl {
    display: flex; align-items: center; justify-content: center;
    padding: 0 0 14px;
    border-bottom: 1px solid rgba(255,255,255,0.1);
    margin-bottom: 16px;
}
.wow-sidebar-brand-pl img { max-width: 100%; height: 28px; object-fit: contain; }
.wow-user-card {
    display: flex; align-items: center; gap: 11px;
    padding: 12px;
    background: rgba(255,255,255,0.06);
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 10px;
    margin-bottom: 18px;
}
.wow-user-avatar {
    width: 38px; height: 38px;
    border-radius: 50%;
    background: linear-gradient(135deg, #EC6608, #F2944A);
    display: grid; place-items: center;
    color: white; font-weight: 800; font-size: 15px;
    box-shadow: inset 0 0 0 2px rgba(255,255,255,0.3);
    flex-shrink: 0;
}
.wow-user-info { min-width: 0; flex: 1; }
.wow-user-name { font-size: 13px; font-weight: 700; color: white !important; text-transform: capitalize; line-height: 1.2; }
.wow-user-meta {
    font-size: 10px; color: rgba(255,255,255,0.55) !important;
    text-transform: uppercase; letter-spacing: 0.5px;
    font-weight: 600; margin-top: 2px;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.wow-nav-label {
    font-size: 10px; font-weight: 700;
    color: rgba(255,255,255,0.55) !important;
    letter-spacing: 1.5px; text-transform: uppercase;
    padding: 8px 14px 4px;
}
.wow-sidebar-help {
    margin-top: 24px; padding: 12px 14px;
    background: rgba(236,102,8,0.10);
    border: 1px solid rgba(236,102,8,0.25);
    border-radius: 10px;
}
.wow-sidebar-help-title {
    font-size: 11.5px; font-weight: 700;
    color: white !important;
    display: flex; align-items: center; gap: 6px;
    margin-bottom: 4px;
}
.wow-sidebar-help-body {
    font-size: 10.5px;
    color: rgba(255,255,255,0.65) !important;
    line-height: 1.45;
}

#MainMenu { visibility: hidden; }
footer { visibility: hidden; }

@media (max-width: 900px) {
    .wow-login-hero { padding: 28px 24px; min-height: 360px; }
    .wow-login-hero h1 { font-size: 24px; }
    .wow-app-header { padding: 16px 18px; }
    .wow-app-header h1 { font-size: 17px; }
    .main .block-container { padding-left: 1rem; padding-right: 1rem; }
}
</style>
"""


def inject_global_theme():
    st.markdown(_THEME_CSS, unsafe_allow_html=True)


def hide_sidebar_for_login():
    st.markdown(
        """
        <style>
            section[data-testid="stSidebar"],
            [data-testid="collapsedControl"] { display: none !important; }
            .main .block-container { max-width: 1280px; padding-top: 1.5rem; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_app_header(usuario: str, rol: str, razon: str):
    usuario_safe = usuario.capitalize() if usuario else "—"
    rol_safe = rol or "—"
    razon_safe = razon or "—"
    _md(f"""
<div class="wow-app-header">
<div class="wow-app-header-row">
<div><h1>Portal de Vendedores</h1>
<p class="wow-app-header-sub">Hola, <strong>{usuario_safe}</strong> · sesión activa</p></div>
<div class="wow-app-header-meta">
<span class="wow-pill wow-pill-orange">{rol_safe}</span>
<span class="wow-pill wow-pill-purple">{razon_safe}</span>
</div></div></div>
""")


def render_sidebar_user(usuario: str, rol: str, razon: str):
    inicial = (usuario[0] if usuario else "?").upper()
    usuario_safe = usuario.capitalize() if usuario else "—"
    rol_safe = (rol or "—").upper()
    razon_short = (razon.split()[0] if razon else "—")
    st.sidebar.markdown(textwrap.dedent(f"""
<div class="wow-sidebar-brand-pl">
<img src="https://raw.githubusercontent.com/leocorbur/st_apps/refs/heads/main/images/logo_horizontal_blanco.png" alt="WOW D2D" />
</div>
<div class="wow-user-card">
<div class="wow-user-avatar">{inicial}</div>
<div class="wow-user-info">
<div class="wow-user-name">{usuario_safe}</div>
<div class="wow-user-meta">{rol_safe} · {razon_short}</div>
</div></div>
<div class="wow-nav-label">Módulos</div>
"""), unsafe_allow_html=True)


def render_sidebar_help():
    st.sidebar.markdown(textwrap.dedent("""
<div class="wow-sidebar-help">
<div class="wow-sidebar-help-title">❓ ¿Necesitas ayuda?</div>
<div class="wow-sidebar-help-body">Soporte:<br/><strong style="color:#FFB07A;">ksa@wowperu.pe</strong></div>
</div>
"""), unsafe_allow_html=True)


def wow_section(titulo: str, icono: str = ""):
    safe = f"{icono} {titulo}".strip()
    st.markdown(f'<span class="wow-section-title">{safe}</span>', unsafe_allow_html=True)


def wow_callout(texto_html: str):
    _md(f"""
<div style="background:#FAE8EA; border:1px solid #F5D4D9; border-left:4px solid #EC6608; border-radius:10px; padding:14px 18px; margin:14px 0; color:#4B0067; font-size:13px; line-height:1.55;">
{texto_html}
</div>
""")
