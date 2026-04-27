import json
import os
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials


def conectar_google_sheets(nombre_hoja: str, nombre_worksheet: str):
    """
    ✔ Local → usa credenciales.json
    ✔ Render → usa variable GOOGLE_CREDENTIALS
    """

    try:
        # 🔥 Detecta si existe variable en Render
        credenciales_env = os.getenv("GOOGLE_CREDENTIALS")

        if credenciales_env:
            # 👉 PRODUCCIÓN (Render)
            credenciales_json = json.loads(credenciales_env)
        else:
            # 👉 LOCAL
            with open("credenciales.json") as f:
                credenciales_json = json.load(f)

        # 🔐 Crear credenciales
        creds = Credentials.from_service_account_info(
            credenciales_json,
            scopes=[
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive"
            ]
        )

        client = gspread.authorize(creds)
        sheet = client.open(nombre_hoja).worksheet(nombre_worksheet)

        return sheet

    except Exception as e:
        st.error(f"⚠️ Error al conectar con Google Sheets: {e}")
        st.stop()