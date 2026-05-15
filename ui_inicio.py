"""
ui_inicio.py — v2

En la nueva arquitectura, la "bienvenida" se renderiza dentro del hero del login
(área principal, columna izquierda) en auth.py.

Esta función se mantiene por compatibilidad con app_maestra_vendedores.py
y queda como no-op para no duplicar contenido.

Si en el futuro quieres mostrar contenido extra ANTES del login (banners de
mantenimiento, avisos legales, etc.), puedes agregarlo aquí.
"""

import streamlit as st


def mostrar_bienvenida():
    """No-op en v2. La bienvenida se renderiza dentro de auth.login()."""
    # Si quieres mostrar un aviso global (ej: mantenimiento programado),
    # descomenta y edita:
    #
    # st.info("ℹ️ Mantenimiento programado el sábado 20 de mayo, 22:00 - 23:00 PE.")
    return
