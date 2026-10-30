import os
import re

import streamlit as st

# Carpeta raíz de auditoría de dealers en OneDrive. Configurable por variable de
# entorno para no romper si en el VPS la ruta montada es distinta a la de la
# máquina local.
RUTA_AUDITORIA_DEALERS = os.getenv(
    "RUTA_AUDITORIA_DEALERS",
    r"C:\Users\ksa\OneDrive - WOWTEL PERU\AUDITORIA DEALERS",
)

CARPETA_CONTRATOS = "CONTRATOS NUEVOS USUARIOS"
CARPETA_DNI = "DNI NUEVOS USUARIOS"


def _normalizar_razon(s: str) -> str:
    return re.sub(r"\s+", " ", str(s).strip().upper().replace(".", "").replace("-", "")).strip()


@st.cache_data(ttl=300, show_spinner=False)
def _listar_carpetas_dealer(ruta_raiz: str) -> dict[str, str]:
    """Mapa {razón social normalizada: ruta real de la carpeta del dealer}."""
    mapa: dict[str, str] = {}
    if not os.path.isdir(ruta_raiz):
        return mapa
    for nombre in os.listdir(ruta_raiz):
        ruta = os.path.join(ruta_raiz, nombre)
        if os.path.isdir(ruta):
            mapa[_normalizar_razon(nombre)] = ruta
    return mapa


def _buscar_dni_en_carpeta(ruta_carpeta: str, dni: str) -> bool:
    if not os.path.isdir(ruta_carpeta):
        return False
    try:
        for nombre_archivo in os.listdir(ruta_carpeta):
            if dni in nombre_archivo:
                return True
    except Exception:
        return False
    return False


def validar_documentos_promotor(razon_social: str, dni: str) -> tuple[bool, str]:
    """
    Verifica que el promotor tenga, en OneDrive, al menos un archivo de contrato
    y uno de copia de DNI cuyo nombre contenga su DNI, dentro de la carpeta del
    dealer correspondiente. Solo aplica a promotores (se llama condicionalmente
    desde formulario.py); Supervisor/Coordinador/Back office no pasan por aquí.
    """
    dni = str(dni).strip()
    if not dni:
        return False, "❌ No se puede validar documentos sin un DNI."

    mapa_carpetas = _listar_carpetas_dealer(RUTA_AUDITORIA_DEALERS)
    if not mapa_carpetas:
        return False, (
            f"❌ No se pudo acceder a la carpeta de auditoría de dealers "
            f"({RUTA_AUDITORIA_DEALERS}). No se puede validar contrato/DNI."
        )

    ruta_dealer = mapa_carpetas.get(_normalizar_razon(razon_social))
    if not ruta_dealer:
        return False, (
            f"❌ No se encontró una carpeta de auditoría para el dealer '{razon_social}'. "
            "Verifica el nombre exacto de la carpeta en OneDrive."
        )

    tiene_contrato = _buscar_dni_en_carpeta(os.path.join(ruta_dealer, CARPETA_CONTRATOS), dni)
    tiene_dni = _buscar_dni_en_carpeta(os.path.join(ruta_dealer, CARPETA_DNI), dni)

    faltantes = []
    if not tiene_contrato:
        faltantes.append("contrato")
    if not tiene_dni:
        faltantes.append("copia de DNI")

    if faltantes:
        return False, (
            f"❌ Falta subir en OneDrive ({razon_social}): {', '.join(faltantes)} "
            f"para el DNI {dni}."
        )

    return True, ""
