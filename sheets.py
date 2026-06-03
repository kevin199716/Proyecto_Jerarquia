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


@st.cache_resource(show_spinner=False)
def _get_client():
    """Un único cliente gspread autorizado, reutilizado en todo el proceso."""
    creds = obtener_credenciales()
    return gspread.authorize(creds)


@st.cache_resource(show_spinner=False)
def _abrir_spreadsheet(nombre_hoja: str):
    """Abre el libro UNA sola vez por proceso. Evita buscar en Drive por nombre
    en cada lectura, que era una de las causas de lentitud y consumo."""
    return _get_client().open(nombre_hoja)


def conectar_google_sheets(nombre_hoja: str, nombre_worksheet: str):
    try:
        spreadsheet = _abrir_spreadsheet(nombre_hoja)
        return spreadsheet.worksheet(nombre_worksheet)
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
    """Sube el archivo a catbox.moe y retorna la URL pública permanente."""
    import requests
    try:
        response = requests.post(
            "https://catbox.moe/user/api.php",
            data={"reqtype": "fileupload"},
            files={"fileToUpload": (nombre_archivo, contenido_bytes, mime_type)},
            timeout=60,
        )
        response.raise_for_status()
        url = response.text.strip()
        if not url.startswith("https://"):
            raise Exception(f"Respuesta inesperada: {url}")
        return url
    except Exception as e:
        raise Exception(f"Error al subir el archivo '{nombre_archivo}': {e}")


def obtener_o_crear_worksheet(nombre_hoja: str, nombre_worksheet: str, columnas_defecto: list[str]):
    """
    Busca una pestaña específica en un libro de Sheets.
    Si no existe, la crea con las columnas por defecto.
    Si existe pero no tiene cabeceras, las agrega.
    """
    try:
        spreadsheet = _abrir_spreadsheet(nombre_hoja)
        try:
            worksheet = spreadsheet.worksheet(nombre_worksheet)
            # Verificar que la primera fila tenga cabeceras correctas
            primera_fila = worksheet.row_values(1)
            if not primera_fila or primera_fila[0] != columnas_defecto[0]:
                # Insertar fila de cabeceras al inicio
                worksheet.insert_row(columnas_defecto, index=1, value_input_option="USER_ENTERED")
            return worksheet
        except gspread.exceptions.WorksheetNotFound:
            worksheet = spreadsheet.add_worksheet(
                title=nombre_worksheet,
                rows="1000",
                cols=str(len(columnas_defecto))
            )
            worksheet.append_row(columnas_defecto, value_input_option="USER_ENTERED")
            return worksheet
    except Exception as e:
        st.error(f"⚠️ Error al gestionar la pestaña '{nombre_worksheet}': {e}")
        st.stop()