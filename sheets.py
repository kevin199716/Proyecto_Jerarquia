import json
import streamlit as st
import gspread
import os
import io
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

# ==============================================================================
# CONFIGURACIÓN DE DRIVE
# Comparte la carpeta de destino con el email de la cuenta de servicio
# (campo "client_email" en tus credenciales) dándole rol "Editor".
# Luego copia el ID de esa carpeta desde la URL de Google Drive y
# ponlo en Streamlit Secrets como: ID_CARPETA_SUSTENTOS = "..."
# ==============================================================================
ID_CARPETA_SUSTENTOS = os.getenv("ID_CARPETA_SUSTENTOS", "1nQBObQhWpfFIa-BUZrGWszLo4RJ7FCQN")

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

def obtener_credenciales():
    """Obtiene las credenciales de la cuenta de servicio de Google desde variables de entorno o archivo local."""
    try:
        credenciales_str = os.getenv("GOOGLE_CREDENTIALS")
        
        if credenciales_str:
            credenciales_json = json.loads(credenciales_str)
            return Credentials.from_service_account_info(credenciales_json, scopes=SCOPES)
        
        # Opcional: buscar archivo local si no está la variable (útil para desarrollo local)
        elif os.path.exists("credenciales.json"):
            return Credentials.from_service_account_file("credenciales.json", scopes=SCOPES)
        
        else:
            st.error("⚠️ No se encontró la variable de entorno GOOGLE_CREDENTIALS ni el archivo credenciales.json")
            st.stop()
    except Exception as e:
        st.error(f"⚠️ Error al obtener credenciales de Google: {e}")
        st.stop()


def conectar_google_sheets(nombre_hoja: str, nombre_worksheet: str):
    try:
        creds = obtener_credenciales()
        client = gspread.authorize(creds)
        
        # Para mayor robustez abrimos por ID si es posible en el futuro.
        # Por ahora mantenemos compatibilidad abriendo por nombre.
        sheet = client.open(nombre_hoja).worksheet(nombre_worksheet)
        return sheet
    except Exception as e:
        st.error(f"⚠️ Error al conectar con Google Sheets: {e}")
        st.stop()


def conectar_google_drive():
    """Establece conexión con la API de Google Drive v3 (mantenido por compatibilidad)."""
    try:
        creds = obtener_credenciales()
        service = build('drive', 'v3', credentials=creds)
        return service
    except Exception as e:
        st.error(f"⚠️ Error al conectar con Google Drive API: {e}")
        st.stop()


def subir_archivo_drive(nombre_archivo: str, contenido_bytes: bytes, mime_type: str) -> str:
    """Sube un archivo a la carpeta de Drive compartida con la cuenta de servicio."""
    if not ID_CARPETA_SUSTENTOS:
        raise Exception("⚠️ Falta configurar ID_CARPETA_SUSTENTOS en Streamlit Secrets.")
    try:
        creds = obtener_credenciales()
        service = build("drive", "v3", credentials=creds)
        media = MediaIoBaseUpload(io.BytesIO(contenido_bytes), mimetype=mime_type, resumable=False)
        archivo = service.files().create(
            body={"name": nombre_archivo, "parents": [ID_CARPETA_SUSTENTOS]},
            media_body=media,
            fields="id, webViewLink",
            supportsAllDrives=True,
        ).execute()
        # Dar permiso de lectura con link para que RRHH pueda verlo
        service.permissions().create(
            fileId=archivo["id"],
            body={"type": "anyone", "role": "reader"},
            supportsAllDrives=True,
        ).execute()
        return archivo.get("webViewLink", "")
    except Exception as e:
        raise Exception(f"Error al subir el archivo '{nombre_archivo}' a Google Drive: {e}")


def obtener_o_crear_worksheet(nombre_hoja: str, nombre_worksheet: str, columnas_defecto: list[str]):
    """
    Busca una pestaña específica en un libro de Sheets.
    Si no existe, la crea con las columnas por defecto especificadas.
    """
    try:
        creds = obtener_credenciales()
        client = gspread.authorize(creds)
        spreadsheet = client.open(nombre_hoja)
        try:
            worksheet = spreadsheet.worksheet(nombre_worksheet)
            return worksheet
        except gspread.exceptions.WorksheetNotFound:
            # Crear la pestaña con las dimensiones correctas
            worksheet = spreadsheet.add_worksheet(
                title=nombre_worksheet,
                rows="1000",
                cols=str(len(columnas_defecto))
            )
            # Agregar cabecera por defecto
            worksheet.append_row(columnas_defecto, value_input_option="USER_ENTERED")
            return worksheet
    except Exception as e:
        st.error(f"⚠️ Error al gestionar la pestaña '{nombre_worksheet}': {e}")
        st.stop()