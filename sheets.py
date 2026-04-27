import json
import streamlit as st
import gspread
import os
from google.oauth2.service_account import Credentials


def conectar_google_sheets(nombre_hoja: str, nombre_worksheet: str):
    try:
        # 🔥 Leer JSON directo (NO base64)
        credenciales_str = os.getenv("GOOGLE_CREDENTIALS")

        if not credenciales_str:
            st.error("⚠️ No existe GOOGLE_CREDENTIALS en Render")
            st.stop()

        credenciales_json = json.loads(credenciales_str)

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