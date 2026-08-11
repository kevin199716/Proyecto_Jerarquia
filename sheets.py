import json
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials

def conectar_google_sheets(nombre_hoja: str, nombre_worksheet: str):
    """Conecta con Google Sheets (modo LOCAL)"""

    try:
        # 👉 Cargar credenciales desde archivo local
        with open("credenciales.json") as f:
            credenciales_json = json.load(f)

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