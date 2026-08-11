import streamlit as st
import pandas as pd
import datetime
import pytz
from utils import validar_correo, mostrar_resumen, mostrar_mapa



def filtrar_por_rol(df, usuario, rol, usuarios):
    if rol == "backoffice":
        return df[df["correo_backoffice"] == usuario].drop(columns=["fecha_blacklist", "blacklist"])

    if rol == "supervisor":
        backoffices_asignados = [
            u for u, info in usuarios.items()
            if info.get("rol") == "backoffice" and info.get("supervisor") == usuario
        ]
        return df[df["correo_backoffice"].isin(backoffices_asignados)]

    if rol == "principal":
        return df

    return pd.DataFrame()  # vacío si rol desconocido


def mostrar_tabla_por_rol(hoja_colaboradores, usuario, rol, usuarios):
    """Muestra los registros filtrados según rol"""
    st.subheader("📄 Datos registrados")
    try:
        registros = hoja_colaboradores.get_all_records()
        if not registros:
            st.info("Aún no hay registros en la hoja.")
            return None, None

        df = pd.DataFrame(registros)
        df_usuario = filtrar_por_rol(df, usuario, rol, usuarios)

        st.dataframe(df_usuario.reset_index(drop=True), use_container_width=True)

        # 👉 Solo muestra resumen
        if rol in ("principal", "supervisor"):
            mostrar_resumen(df_usuario)
            mostrar_mapa(df_usuario)



        return df, df_usuario

    except Exception as e:
        st.error(f"⚠️ Error al obtener datos: {e}")
        return None, None


def dar_de_baja(df, df_usuario, hoja_colaboradores, correo_backoffice):
    """Permite seleccionar y dar de baja un colaborador"""
    st.markdown("---")
    st.subheader("🔻 Dar de baja a un colaborador")

    if "fecha_baja" not in df.columns or "motivo_baja" not in df.columns:
        st.warning("⚠️ Las columnas 'fecha_baja' y 'motivo_baja' no existen en la hoja.")
        return

    df_usuario_activos = df_usuario[df_usuario["fecha_baja"] == ""]
    nombres_disponibles = df_usuario_activos["nombre_colaborador_agencia"].tolist()

    if not nombres_disponibles:
        st.info("")
        return

    seleccionado = st.selectbox("Selecciona al colaborador a dar de baja:", nombres_disponibles)
    motivo_baja = st.text_input("Motivo de baja")

    if st.button("Dar de baja"):
        if motivo_baja.strip() == "":
            st.warning("⚠️ Por favor ingresa un motivo.")
        else:
            index_global = df[
                (df["correo_backoffice"] == correo_backoffice) &
                (df["nombre_colaborador_agencia"] == seleccionado)
            ].index[0]

            fecha_baja = datetime.datetime.now(pytz.timezone("America/Lima")).strftime("%Y-%m-%d")

            hoja_colaboradores.update_cell(index_global + 2, df.columns.get_loc("fecha_baja") + 1, fecha_baja)
            hoja_colaboradores.update_cell(index_global + 2, df.columns.get_loc("motivo_baja") + 1, motivo_baja)

            st.success(f"✅ {seleccionado} fue dado de baja correctamente.")


def editar_registros(df, df_usuario, hoja_colaboradores, correo_backoffice, hoja_ubicaciones, dominios_permitidos):
    """Permite seleccionar y editar a un colaborador"""
    st.markdown("---")
    st.subheader("Editar colaborador")

    if "fecha_baja" not in df.columns or "motivo_baja" not in df.columns:
        st.warning("⚠️ Las columnas 'fecha_baja' y 'motivo_baja' no existen en la hoja.")
        return
    
    df_usuario_activos = df_usuario[df_usuario["fecha_baja"] == ""]
    nombres_disponibles = df_usuario_activos["nombre_colaborador_agencia"].tolist()

    if not nombres_disponibles:
        st.info("")
        return

    seleccionado = st.selectbox("Selecciona al colaborador a editar:", nombres_disponibles)
    cargo = st.selectbox("Cargo:", ["Backoffice", "Supervisor", "Vendedor", "Freelance", "Dueño", "Formador", "Digital"])
    correo = st.text_input("Correo electrónico", "")

    # Detalla ubicacion del vendedor
    ubicaciones = hoja_ubicaciones.get_all_records()
    df_ubicaciones = pd.DataFrame(ubicaciones)

    departamento = st.selectbox(
    "Ubicación departamento",
    options=df_ubicaciones["DEPARTAMENTO"].unique(),
    key="select_departamento"
    )

    provincias = df_ubicaciones[df_ubicaciones["DEPARTAMENTO"]==departamento]["PROVINCIA"].unique()
    provincia = st.selectbox(
        "Ubicación provincia",
        options=provincias,
        key="select_provincia"
    )
    
    if st.button("Actualizar"):
        if not departamento.strip() or not provincia.strip() or not cargo.strip() or not correo.strip():
            st.warning("⚠️ Por favor ingresar datos completos.")
        elif not validar_correo(correo, cargo, dominios_permitidos):  # <--- Aquí defines tus dominios permitidos
            pass  # El validador ya muestra el error
        else:
            index_global = df[
                (df["correo_backoffice"] == correo_backoffice) &
                (df["nombre_colaborador_agencia"] == seleccionado)
            ].index[0]
            hoja_colaboradores.update_cell(index_global + 2, df.columns.get_loc("cargo") + 1, cargo)
            hoja_colaboradores.update_cell(index_global + 2, df.columns.get_loc("correo") + 1, correo)
            hoja_colaboradores.update_cell(index_global + 2, df.columns.get_loc("ubicacion_departamento") + 1, departamento)
            hoja_colaboradores.update_cell(index_global + 2, df.columns.get_loc("ubicacion_provincia") + 1, provincia)

            st.success(f"✅ Datos actualizados.")


def blacklist(df_usuario, hoja_colaboradores):
    """Permite marcar a un usuario en la blacklist"""
    st.markdown("---")
    st.subheader("Marca a usuario en la blacklist")

    df_usuario_ = df_usuario[df_usuario["blacklist"] == ""]
    nombres_disponibles = df_usuario_["nombre_colaborador_agencia"].tolist()

    seleccionado = st.selectbox("Selecciona al colaborador para la blacklist:", nombres_disponibles)

    opcion_si = st.selectbox(
        "¿Confirmas la selección?",
        ["Selecciona...", "Si"]
    )

    if st.button("Actualizar"):
        if opcion_si != "Si":
            st.warning("⚠️ Por favor marcar la opción correctamente.")
        else:
            index_global = df_usuario[
                (df_usuario["nombre_colaborador_agencia"] == seleccionado)
            ].index[0]
        
        fecha_blacklist = datetime.datetime.now(pytz.timezone("America/Lima")).strftime("%Y-%m-%d")

        hoja_colaboradores.update_cell(index_global + 2, df_usuario.columns.get_loc("fecha_blacklist") + 1, fecha_blacklist)
        hoja_colaboradores.update_cell(index_global + 2, df_usuario.columns.get_loc("blacklist") + 1, opcion_si)

        st.success(f"✅Colaborador enviado a la blacklist.")



