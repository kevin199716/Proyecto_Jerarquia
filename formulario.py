import streamlit as st
import pandas as pd
from datetime import datetime
import pytz

# =========================
# ZONA HORARIA PERÚ
# =========================
zona_peru = pytz.timezone("America/Lima")

def ahora_peru():
    return datetime.now(zona_peru).strftime("%Y-%m-%d %H:%M:%S")


# =========================
# LIMPIAR FORMULARIO
# =========================
def limpiar_form():
    for k in list(st.session_state.keys()):
        if k not in ["autenticado", "rol", "razon", "usuario"]:
            del st.session_state[k]


# =========================
# NORMALIZAR DNI
# =========================
def normalizar_dni(valor):
    if pd.isna(valor):
        return ""

    dni = str(valor).strip()
    dni = dni.replace("'", "").replace(".0", "").replace(" ", "")

    if dni.isdigit():
        dni = dni.zfill(8)

    return dni


# =========================
# FORMULARIO
# =========================
def mostrar_formulario(hoja_colaboradores, hoja_ubicaciones):

    st.subheader("📋 Registro de Vendedores")

    if st.session_state.get("mensaje_ok"):
        st.success("✅ Registrado correctamente")
        del st.session_state["mensaje_ok"]

    usuario_actual = st.session_state.get("usuario", "")

    data_ubi = hoja_ubicaciones.get_all_records()
    df_ubi = pd.DataFrame(data_ubi)
    df_ubi.columns = df_ubi.columns.str.strip().str.upper()

    departamentos = sorted(df_ubi["DEPARTAMENTO"].dropna().unique())
    departamento = st.selectbox("DEPARTAMENTO", [""] + departamentos)

    provincias = []
    if departamento:
        df_filtrado = df_ubi[df_ubi["DEPARTAMENTO"] == departamento]
        provincias = sorted(df_filtrado["PROVINCIA"].dropna().unique())

    provincia = st.selectbox("PROVINCIA", [""] + provincias)

    with st.form("form_registro"):

        col1, col2 = st.columns(2)

        rol = st.session_state.get("rol", "")
        razon_usuario = st.session_state.get("razon", "")

        razones = [
            "MALUTECH S.A.C.",
            "2CONNECT SERVICES S.A.C.",
            "INTERCONEXION 360 SAC",
            "NOGALES HIGH S.A.C.",
            "MULTIPLE FORCE SAC",
            "KONECTA SAC"
        ]

        with col1:

            if rol == "backoffice":
                razon = st.selectbox("RAZON SOCIAL", [""] + razones)
            else:
                razon = razon_usuario
                st.text_input("RAZON SOCIAL", value=razon, disabled=True)

            canal = st.selectbox("CANAL", ["VENTAS INDIRECTAS"])
            subcanal = st.selectbox("SUB CANAL", ["VENTAS INDIRECTAS", "OUTBOUND"])
            region = st.selectbox("REGION", ["NORORIENTE", "SUR", "CENTRAL"])

        with col2:

            nombres = st.text_input("NOMBRES")
            dni = st.text_input("DNI")
            correo = st.text_input("CORREO")

        submit = st.form_submit_button("Guardar")

        if submit:

            if not departamento:
                st.error("❌ Debes seleccionar DEPARTAMENTO")
                return

            if not provincia:
                st.error("❌ Debes seleccionar PROVINCIA")
                return

            if not nombres:
                st.error("❌ Nombres obligatorios")
                return

            if not dni:
                st.error("❌ DNI obligatorio")
                return

            dni_limpio = normalizar_dni(dni)

            hoja_colaboradores.append_row([
                "",
                razon,
                canal,
                subcanal,
                region,
                departamento,
                provincia,
                "",
                "",
                "",
                "",
                "",
                nombres,
                "",
                "",
                "",
                "",
                dni_limpio,
                correo.lower(),
                "ACTIVO",
                "",
                str(datetime.now().date()),
                "",
                "",
                "",
                ahora_peru(),
                "",
                usuario_actual,  # 🔥 USUARIO ALTA
                ""
            ])

            st.session_state["mensaje_ok"] = True
            limpiar_form()
            st.rerun()