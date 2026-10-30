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
