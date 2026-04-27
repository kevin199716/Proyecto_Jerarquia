import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

# =========================
# LIMPIAR FECHA
# =========================
def limpiar_fecha(valor):
    try:
        if valor in ["", None]:
            return None
        return pd.to_datetime(valor).date()
    except:
        return None


# =========================
# MOTIVOS
# =========================
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


# =========================
# TABLA (🔥 FIX ADMIN)
# =========================
def mostrar_tabla(hoja, razon_usuario=None):

    data = hoja.get_all_records()

    if not data:
        st.info("No hay datos")
        return None

    df = pd.DataFrame(data)
    df.columns = df.columns.str.strip().str.upper()

    # 🔥 NUEVO FIX ADMIN
    rol = st.session_state.get("rol", "")

    if rol != "backoffice":
        df = df[df["RAZON SOCIAL"] == razon_usuario]

    st.dataframe(df, use_container_width=True)
    return df


# =========================
# DAR DE BAJA
# =========================
def dar_de_baja(df, hoja, razon_usuario=None):

    st.subheader("🔻 Dar de baja")

    df.columns = df.columns.str.strip().str.upper()

    # 🔥 FIX ADMIN
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

    if len(df_filtrado) > 1:

        opciones = df_filtrado.reset_index()

        seleccion = st.selectbox(
            "Selecciona registro",
            opciones.index,
            format_func=lambda i: f"{opciones.loc[i,'RAZON SOCIAL']} - {opciones.loc[i,'CARGO (ROL)']}"
        )

        fila = opciones.loc[seleccion]
        index_global = fila["index"]

    else:
        fila = df_filtrado.iloc[0]
        index_global = fila.name

    fecha = st.date_input("Fecha de cese")
    motivo = st.selectbox("Motivo de baja", MOTIVOS)

    if st.button("Dar de baja"):

        fecha_creacion = limpiar_fecha(fila.get("FECHA DE CREACION USUARIO"))

        if fecha_creacion and fecha < fecha_creacion:
            st.error("❌ Fecha de baja no puede ser menor a la fecha de creación")
            return

        hoy = datetime.now().date()
        max_fecha = hoy + timedelta(days=2)

        if fecha > max_fecha:
            st.error(f"❌ Solo puedes colocar hasta {max_fecha}")
            return

        ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        hoja.update_cell(index_global+2, df.columns.get_loc("ESTADO")+1, "INACTIVO")
        hoja.update_cell(index_global+2, df.columns.get_loc("FECHA DE CESE")+1, str(fecha))
        hoja.update_cell(index_global+2, df.columns.get_loc("MOTIVO")+1, motivo)

        if "FECHA MOV" in df.columns:
            hoja.update_cell(
                index_global+2,
                df.columns.get_loc("FECHA MOV")+1,
                str(fecha)
            )

        if "FECHA_BAJA_REGISTRO" in df.columns:
            hoja.update_cell(
                index_global+2,
                df.columns.get_loc("FECHA_BAJA_REGISTRO")+1,
                ahora
            )

        st.success("✅ Baja aplicada correctamente")


# =========================
# EDITAR (🔥 FIX ADMIN)
# =========================
def editar_registro(df, hoja, hoja_ubi):

    st.subheader("✏️ Editar registro")

    df.columns = df.columns.str.strip().str.upper()
    df["DNI"] = df["DNI"].astype(str)

    # 🔥 FIX ADMIN
    rol = st.session_state.get("rol", "")
    razon_usuario = st.session_state.get("razon", "")

    if rol != "backoffice":
        df = df[df["RAZON SOCIAL"] == razon_usuario]

    dni = st.text_input("DNI a editar", key="dni_edit")

    if not dni:
        return

    df_filtrado = df[df["DNI"] == dni]

    if df_filtrado.empty:
        st.error("No encontrado")
        return

    if len(df_filtrado) > 1:

        opciones = df_filtrado.reset_index()

        seleccion = st.selectbox(
            "Selecciona registro",
            opciones.index,
            format_func=lambda i: f"{opciones.loc[i,'RAZON SOCIAL']} - {opciones.loc[i,'CARGO (ROL)']}"
        )

        fila = opciones.loc[seleccion]
        index_global = fila["index"]

    else:
        fila = df_filtrado.iloc[0]
        index_global = fila.name

    st.success("Registro seleccionado")

    # 🔴 AQUÍ DEJAS TU LÓGICA TAL CUAL