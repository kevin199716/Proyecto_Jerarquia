import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import pytz

zona_peru = pytz.timezone("America/Lima")

def ahora_peru():
    return datetime.now(zona_peru).strftime("%Y-%m-%d %H:%M:%S")


def limpiar_fecha(valor):
    try:
        if valor in ["", None]:
            return None
        return pd.to_datetime(valor).date()
    except:
        return None


MOTIVOS = [
    "",
    "Renuncia Laboral",
    "NSPP",
    "Baja por Productividad",
    "Baja por FPD",
    "Baja - VNE3",
    "Baja por politica de Actividad",
    "Abandono Laboral / Faltas Injustificadas",
    "Baja No asistio Campo",
    "Baja por cierre de Operaciones"
]


def mostrar_tabla(hoja, razon_usuario=None):

    data = hoja.get_all_records()

    if not data:
        st.info("No hay datos")
        return None

    df = pd.DataFrame(data)
    df.columns = df.columns.str.strip().str.upper()

    rol = st.session_state.get("rol", "")

    if rol != "backoffice":
        df = df[df["RAZON SOCIAL"] == razon_usuario]

    st.dataframe(df, use_container_width=True)
    return df


def dar_de_baja(df, hoja, razon_usuario=None):

    st.subheader("🔻 Dar de baja")

    df.columns = df.columns.str.strip().str.upper()

    rol = st.session_state.get("rol", "")

    if rol != "backoffice":
        df = df[df["RAZON SOCIAL"] == razon_usuario]

    dni = st.text_input("DNI", key="dni_baja")

    if not dni:
        return

    df["DNI"] = df["DNI"].astype(str)
    df_filtrado = df[df["DNI"] == dni]

    if df_filtrado.empty:
        st.error("No encontrado")
        return

    fila = df_filtrado.iloc[0]
    index_global = fila.name

    fecha = st.date_input("Fecha de cese")
    motivo = st.selectbox("Motivo de baja", MOTIVOS)

    if st.button("Dar de baja"):

        hoja.update_cell(index_global+2, df.columns.get_loc("ESTADO")+1, "INACTIVO")
        hoja.update_cell(index_global+2, df.columns.get_loc("FECHA DE CESE")+1, str(fecha))
        hoja.update_cell(index_global+2, df.columns.get_loc("MOTIVO")+1, motivo)

        # 🔥 HORA CORREGIDA
        if "FECHA_BAJA_REGISTRO" in df.columns:
            hoja.update_cell(
                index_global+2,
                df.columns.get_loc("FECHA_BAJA_REGISTRO")+1,
                ahora_peru()
            )

        st.success("✅ Baja aplicada correctamente")