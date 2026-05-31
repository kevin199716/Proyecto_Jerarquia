import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import pytz

# =========================
# ZONA HORARIA PERÚ
# =========================
zona_peru = pytz.timezone("America/Lima")

def ahora_peru():
    return datetime.now(zona_peru).strftime("%Y-%m-%d %H:%M:%S")


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
# TABLA (FIX ADMIN)
# =========================
def mostrar_tabla(hoja, razon_usuario=None):

    data = hoja.get_all_records()

    if not data:
        st.info("No hay datos")
        return None

    df = pd.DataFrame(data)

    df.columns = df.columns.str.strip().str.upper()

    rol = st.session_state.get("rol", "")

    # 🔥 ADMIN VE TODO
    if rol != "backoffice":
        df = df[df["RAZON SOCIAL"] == razon_usuario]

    st.dataframe(df, use_container_width=True)

    return df


# =========================
# DAR DE BAJA
# =========================
def dar_de_baja(df, hoja, razon_usuario=None):

    st.markdown("<span class='wow-section-title'>🔻 Dar de baja</span>", unsafe_allow_html=True)

    df.columns = df.columns.str.strip().str.upper()

    rol = st.session_state.get("rol", "")

    usuario_actual = st.session_state.get("usuario", "")

    # 🔥 ADMIN VE TODO
    if rol != "backoffice":
        df = df[df["RAZON SOCIAL"] == razon_usuario]

    dni = st.text_input("DNI", key="dni_baja")

    if not dni:
        return

    df["DNI"] = df["DNI"].astype(str)

    df_filtrado = df[df["DNI"] == dni]

    if df_filtrado.empty:
        st.error("❌ No encontrado")
        return

    # =========================
    # SI HAY MÁS DE 1 REGISTRO
    # =========================
    if len(df_filtrado) > 1:

        opciones = df_filtrado.reset_index()

        seleccion = st.selectbox(
            "Selecciona registro",
            opciones.index,
            format_func=lambda i:
            f"{opciones.loc[i,'RAZON SOCIAL']} - {opciones.loc[i,'CARGO (ROL)']}"
        )

        fila = opciones.loc[seleccion]

        index_global = fila["index"]

    else:

        fila = df_filtrado.iloc[0]

        index_global = fila.name

    # =========================
    # FECHA CESE
    # =========================
    hoy = datetime.now().date()

    fecha_minima = hoy - timedelta(days=3)

    fecha = st.date_input(
        "Fecha de cese",
        value=hoy,
        min_value=fecha_minima,
        max_value=hoy
    )

    motivo = st.selectbox(
        "Motivo de baja",
        MOTIVOS
    )

    # =========================
    # BOTÓN BAJA
    # =========================
    if st.button("Dar de baja"):

        fecha_creacion = limpiar_fecha(
            fila.get("FECHA DE CREACION USUARIO")
        )

        # 🔴 VALIDACIÓN
        if fecha_creacion and fecha < fecha_creacion:
            st.error("❌ Fecha menor a creación")
            return

        ahora = ahora_peru()

        # 🔥 FECHA MOV
        fecha_mov = datetime.now().strftime("%Y-%m-%d")

        # =========================
        # ACTUALIZAR
        # =========================
        hoja.update_cell(
            index_global+2,
            df.columns.get_loc("ESTADO")+1,
            "INACTIVO"
        )

        hoja.update_cell(
            index_global+2,
            df.columns.get_loc("FECHA DE CESE")+1,
            str(fecha)
        )

        hoja.update_cell(
            index_global+2,
            df.columns.get_loc("MOTIVO")+1,
            motivo
        )

        # =========================
        # FECHA MOV
        # =========================
        if "FECHA MOV" in df.columns:

            hoja.update_cell(
                index_global+2,
                df.columns.get_loc("FECHA MOV")+1,
                fecha_mov
            )

        # =========================
        # FECHA BAJA REGISTRO
        # =========================
        if "FECHA_BAJA_REGISTRO" in df.columns:

            hoja.update_cell(
                index_global+2,
                df.columns.get_loc("FECHA_BAJA_REGISTRO")+1,
                ahora
            )

        # =========================
        # USUARIO BAJA
        # =========================
        if "USUARIO_BAJA" in df.columns:

            hoja.update_cell(
                index_global+2,
                df.columns.get_loc("USUARIO_BAJA")+1,
                usuario_actual
            )

        st.success("✅ Baja aplicada correctamente")


# =========================
# EDITAR (SIN CAMBIOS)
# =========================
def editar_registro(df, hoja, hoja_ubi):

    st.markdown("<span class='wow-section-title'>✏️ Editar registro</span>", unsafe_allow_html=True)

    df.columns = df.columns.str.strip().str.upper()

    df["DNI"] = df["DNI"].astype(str)

    rol = st.session_state.get("rol", "")

    razon_usuario = st.session_state.get("razon", "")

    if rol != "backoffice":
        df = df[df["RAZON SOCIAL"] == razon_usuario]

    dni = st.text_input("DNI a editar", key="dni_edit")

    if not dni:
        return

    df_filtrado = df[df["DNI"] == dni]

    if df_filtrado.empty:
        st.error("❌ No encontrado")
        return

    if len(df_filtrado) > 1:

        opciones = df_filtrado.reset_index()

        seleccion = st.selectbox(
            "Selecciona registro",
            opciones.index,
            format_func=lambda i:
            f"{opciones.loc[i,'RAZON SOCIAL']} - {opciones.loc[i,'CARGO (ROL)']}"
        )

        fila = opciones.loc[seleccion]

        index_global = fila["index"]

    else:

        fila = df_filtrado.iloc[0]

        index_global = fila.name

    st.success("Registro seleccionado")

    # 🔴 TU LÓGICA DE EDICIÓN SIGUE AQUÍ (NO SE TOCA)