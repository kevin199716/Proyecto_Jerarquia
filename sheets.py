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
# ==============================================================================
# IMPORTANTE: Las Cuentas de Servicio de Google tienen cuota de almacenamiento CERO.
# Para poder subir archivos, debes crear una Unidad Compartida (Shared Drive) en tu
# Google Drive corporativo (de @wowperu.pe), añadir al correo de la Cuenta de Servicio
# como miembro con permisos de "Administrador de contenido", crear una carpeta
# llamada "Sustentos_Bajas_Medicas" adentro, y pegar su ID aquí abajo:
ID_CARPETA_SUSTENTOS = ""

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
    """Establece conexión con la API de Google Drive v3."""
    try:
        creds = obtener_credenciales()
        service = build('drive', 'v3', credentials=creds)
        return service
    except Exception as e:
        st.error(f"⚠️ Error al conectar con Google Drive API: {e}")
        st.stop()


def obtener_o_crear_carpeta_sustentos(drive_service) -> str:
    """Retorna el ID de la carpeta de sustentos. Si ID_CARPETA_SUSTENTOS está configurado, lo usa directamente.
    De lo contrario, busca la carpeta 'Sustentos_Bajas_Medicas' en todas las unidades (incluyendo compartidas).
    """
    if ID_CARPETA_SUSTENTOS:
        return ID_CARPETA_SUSTENTOS

    nombre_carpeta = "Sustentos_Bajas_Medicas"
    try:
        # Buscar si ya existe la carpeta en cualquier unidad compartida
        query = f"name = '{nombre_carpeta}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
        resultados = drive_service.files().list(
            q=query, 
            fields="files(id, name)",
            supportsAllDrives=True,
            includeItemsFromAllDrives=True
        ).execute()
        archivos = resultados.get("files", [])
        
        if archivos:
            return archivos[0]["id"]
        
        # Si no existe, la creamos (intentar crearla en la raíz de la cuenta de servicio si no se configuró ID_CARPETA_SUSTENTOS)
        metadata_carpeta = {
            "name": nombre_carpeta,
            "mimeType": "application/vnd.google-apps.folder"
        }
        carpeta = drive_service.files().create(
            body=metadata_carpeta, 
            fields="id",
            supportsAllDrives=True
        ).execute()
        
        # Darle permisos de lectura a cualquiera con el link para que RRHH pueda verla
        drive_service.permissions().create(
            fileId=carpeta["id"],
            body={"type": "anyone", "role": "reader"},
            fields="id",
            supportsAllDrives=True
        ).execute()
        
        return carpeta["id"]
    except Exception as e:
        st.error(f"⚠️ Error al gestionar la carpeta de sustentos en Drive: {e}")
        raise e


def subir_archivo_drive(nombre_archivo: str, contenido_bytes: bytes, mime_type: str) -> str:
    """
    Sube un archivo en memoria (bytes) a la carpeta de sustentos en Google Drive (soporta Unidades Compartidas).
    Retorna la URL pública para visualizar el archivo.
    """
    try:
        drive_service = conectar_google_drive()
        id_carpeta = obtener_o_crear_carpeta_sustentos(drive_service)
        
        metadata_archivo = {
            "name": nombre_archivo,
            "parents": [id_carpeta]
        }
        
        # Subir el flujo de bytes
        fh = io.BytesIO(contenido_bytes)
        media = MediaIoBaseUpload(fh, mimetype=mime_type, resumable=True)
        
        archivo = drive_service.files().create(
            body=metadata_archivo,
            media_body=media,
            fields="id, webViewLink",
            supportsAllDrives=True
        ).execute()
        
        file_id = archivo.get("id")
        
        # Habilitar permisos de visualización pública ("cualquiera con el link puede leer")
        drive_service.permissions().create(
            fileId=file_id,
            body={"type": "anyone", "role": "reader"},
            fields="id",
            supportsAllDrives=True
        ).execute()
        
        # Obtener el link de visualización actualizado
        info = drive_service.files().get(
            fileId=file_id, 
            fields="webViewLink",
            supportsAllDrives=True
        ).execute()
        return info.get("webViewLink")
        
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