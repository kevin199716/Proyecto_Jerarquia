import os

import pandas as pd
import streamlit as st

# Excel de referencia compartido para Zona Agrupada (canal Indirecto).
# Se puede sobreescribir con una variable de entorno si en el VPS vive en otra ruta.
RUTA_UBIGEOS = os.getenv(
    "RUTA_UBIGEOS_ZONA_AGRUPADA",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "ubigeos_habilitados_venta_region.xlsx"),
)


@st.cache_data(ttl=3600, show_spinner=False)
def _leer_ubigeos_cached(ruta: str) -> pd.DataFrame:
    if not os.path.exists(ruta):
        return pd.DataFrame()
    df = pd.read_excel(ruta, sheet_name="Ubigeos")
    df.columns = df.columns.astype(str).str.strip().str.upper()
    for c in df.columns:
        df[c] = df[c].astype(str).str.strip()
    return df


def leer_ubigeos() -> pd.DataFrame:
    return _leer_ubigeos_cached(RUTA_UBIGEOS)


def lista_zonas_agrupadas() -> list[str]:
    df = leer_ubigeos()
    if df.empty or "ZONA_AGRUPADA" not in df.columns:
        return []
    return sorted(z for z in df["ZONA_AGRUPADA"].dropna().unique().tolist() if z and z.upper() != "NAN")


# Excepciones de negocio: fuerzan una única zona agrupada para TODO el
# departamento, aunque no coincida con el mapeo geográfico del Excel.
# Amazonas NO es excepción: usa su zona real ("AMAZONAS", ya resuelta por el
# filtro normal contra el Excel) — corregido 06/11/2026, se había forzado
# "CAJAMARCA" por error.
EXCEPCIONES_DEPARTAMENTO = {
    "LA LIBERTAD": "CHICLAYO",
}

_TILDES = (("Á", "A"), ("É", "E"), ("Í", "I"), ("Ó", "O"), ("Ú", "U"), ("Ñ", "N"))


def _normalizar(s) -> str:
    s = str(s or "").strip().upper()
    for a, b in _TILDES:
        s = s.replace(a, b)
    return " ".join(s.split())


def zona_excepcion(departamento: str) -> str:
    """Zona agrupada fija para un departamento con regla de negocio especial, o '' si no aplica."""
    return EXCEPCIONES_DEPARTAMENTO.get(_normalizar(departamento), "")


def _zonas_unicas(df: pd.DataFrame) -> list[str]:
    return sorted(z for z in df["ZONA_AGRUPADA"].dropna().unique().tolist() if z and z.upper() != "NAN")


def zonas_disponibles(departamento: str, provincia: str = "", distrito: str = "") -> list[str]:
    """
    Zonas agrupadas válidas para una ubicación, de más a menos específico:
    excepción de departamento > distrito > provincia > departamento > (sin filtrar).
    El departamento manda; provincia y distrito solo afinan dentro de él.
    """
    excepcion = zona_excepcion(departamento)
    if excepcion:
        return [excepcion]
    df = leer_ubigeos()
    if df.empty or "ZONA_AGRUPADA" not in df.columns or "DEPARTAMENTO" not in df.columns or not departamento:
        return lista_zonas_agrupadas()
    df_dep = df[df["DEPARTAMENTO"].map(_normalizar) == _normalizar(departamento)]
    if df_dep.empty:
        # El departamento no está en el Excel de ubigeos habilitados: no se puede
        # restringir con certeza, se deja la lista completa en vez de bloquear.
        return lista_zonas_agrupadas()
    if distrito and "DISTRITO" in df_dep.columns:
        df_dist = df_dep[df_dep["DISTRITO"].map(_normalizar) == _normalizar(distrito)]
        if not df_dist.empty:
            return _zonas_unicas(df_dist)
    if provincia and "PROVINCIA" in df_dep.columns:
        df_prov = df_dep[df_dep["PROVINCIA"].map(_normalizar) == _normalizar(provincia)]
        if not df_prov.empty:
            return _zonas_unicas(df_prov)
    return _zonas_unicas(df_dep)
