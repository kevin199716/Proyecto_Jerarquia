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

    # 🔥 MENSAJE OK
    if st.session_state.get("mensaje_ok"):
        st.success("✅ Registrado correctamente")
        del st.session_state["mensaje_ok"]

    # =========================
    # UBICACIONES
    # =========================
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

    # =========================
    # FORM
    # =========================
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

            supervisor = st.text_input("SUPERVISOR A CARGO")
            dni_supervisor = st.text_input("DNI SUPERVISOR")

            coordinador = st.text_input("COORDINADOR")
            dni_coordinador = st.text_input("DNI COORDINADOR")

            cargo = st.selectbox(
                "CARGO (ROL)",
                [
                    "Agente BO D2D - Dealer",
                    "Promotor D2D - Dealer",
                    "Supervisor D2D - Dealer",
                    "Coordinador D2D - Dealer"
                ]
            )

        with col2:

            nombres = st.text_input("NOMBRES")
            apellido_p = st.text_input("APELLIDO PATERNO")
            apellido_m = st.text_input("APELLIDO MATERNO")

            celular = st.text_input("CELULAR")

            tipo_doc = st.selectbox("TIPO DE DOC", ["DNI", "CPP", "CEX", "OTROS"])
            dni = st.text_input("DNI")
            correo = st.text_input("CORREO")

            tipo_contrato = st.selectbox(
                "TIPO DE CONTRATO",
                ["PLANILLA", "COMISIONISTA", "SUB DEALER", "MEDIA PLANILLA"]
            )

            hoy = datetime.now().date()

            fecha_creacion = st.date_input(
                "FECHA CREACION",
                value=hoy
            )

            contrato_firmado = st.selectbox("CONTRATO FIRMADO", ["SI", "NO"])

        submit = st.form_submit_button("Guardar")

        # =========================
        # VALIDACIONES 🔥
        # =========================
        if submit:

            # 🔴 VALIDAR CAMPOS OBLIGATORIOS
            if not departamento:
                st.error("❌ Debes seleccionar DEPARTAMENTO")
                return

            if not provincia:
                st.error("❌ Debes seleccionar PROVINCIA")
                return

            if not nombres or not apellido_p:
                st.error("❌ Nombres y Apellidos son obligatorios")
                return

            if not dni:
                st.error("❌ DNI obligatorio")
                return

            dni_limpio = normalizar_dni(dni)

            if not dni_limpio.isdigit() or len(dni_limpio) != 8:
                st.error("❌ DNI inválido")
                return

            # =========================
            # GUARDAR
            # =========================
            hoja_colaboradores.append_row([
                "",
                razon,
                canal,
                subcanal,
                region,
                departamento,
                provincia,
                supervisor,
                dni_supervisor,
                coordinador,
                dni_coordinador,
                cargo,
                nombres,
                apellido_p,
                apellido_m,
                celular,
                tipo_doc,
                dni_limpio,
                correo.lower(),
                "ACTIVO",
                tipo_contrato,
                str(fecha_creacion),
                "",
                "",
                contrato_firmado,
                ahora_peru(),
                ""
            ])

            # 🔥 MENSAJE VERDE
            st.session_state["mensaje_ok"] = True

            limpiar_form()
            st.rerun()