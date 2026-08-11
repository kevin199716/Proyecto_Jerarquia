import streamlit as st
from datetime import date, timedelta
import pandas as pd
import re

def mostrar_formulario(hoja_colaboradores, hoja_ubicaciones):

    st.title("📋 Formulario de Registro de Vendedores")

    # =========================
    # CARGAR UBICACIONES
    # =========================
    @st.cache_data(ttl=600)
    def cargar_ubicaciones():
        data = hoja_ubicaciones.get_all_records()

        df = pd.DataFrame(data)

        df.columns = df.columns.str.strip().str.upper()
        df["DEPARTAMENTO"] = df["DEPARTAMENTO"].astype(str).str.strip().str.upper()
        df["PROVINCIA"] = df["PROVINCIA"].astype(str).str.strip().str.upper()

        df = df[(df["DEPARTAMENTO"] != "") & (df["PROVINCIA"] != "")]

        return (
            df.groupby("DEPARTAMENTO")["PROVINCIA"]
            .apply(lambda x: sorted(set(x)))
            .to_dict()
        )

    ubicaciones = cargar_ubicaciones()

    # =========================
    # SESSION STATE
    # =========================
    if "departamento" not in st.session_state:
        st.session_state.departamento = ""

    if "provincia" not in st.session_state:
        st.session_state.provincia = ""

    def reset_provincia():
        st.session_state.provincia = ""

    # =========================
    # SELECTS FUERA DEL FORM
    # =========================
    departamento = st.selectbox(
        "Departamento",
        [""] + sorted(list(ubicaciones.keys())),
        key="departamento",
        on_change=reset_provincia
    )

    provincia = st.selectbox(
        "Provincia",
        [""] + ubicaciones.get(departamento, []),
        key="provincia"
    )

    # =========================
    # FORMULARIO
    # =========================
    with st.form("formulario"):

        razon_social = st.selectbox("Razón Social", ["",
            "MALUTECH S.A.C.",
            "2CONNECT SERVICES S.A.C.",
            "INTERCONEXION 360 SAC",
            "NOGALES HIGH S.A.C.",
            "MULTIPLE FORCE SAC"
        ])

        st.text_input("Canal", "VENTAS INDIRECTAS", disabled=True)

        subcanal = st.selectbox("Sub Canal", ["", "VENTAS INDIRECTAS", "Outbound"])
        region = st.selectbox("Región", ["", "NORORIENTE", "SUR", "CENTRAL"])

        supervisor = st.text_input("Supervisor")
        dni_supervisor = st.text_input("DNI Supervisor")

        coordinador = st.text_input("Coordinador")
        dni_coordinador = st.text_input("DNI Coordinador")

        cargo = st.selectbox("Cargo", ["",
            "Agente BO D2D - Dealer",
            "Promotor D2D - Dealer",
            "Supervisor D2D - Dealer",
            "Coordinador D2D - Dealer"
        ])

        nombres = st.text_input("Nombres")
        ape_paterno = st.text_input("Apellido Paterno")
        ape_materno = st.text_input("Apellido Materno")

        celular = st.text_input("Celular")
        tipo_doc = st.selectbox("Tipo Doc", ["", "DNI", "CPP", "CEX", "Otros"])
        dni = st.text_input("DNI")

        correo = st.text_input("Correo")
        tipo_contrato = st.selectbox("Tipo Contrato", ["", "PLANILLA", "COMISIONISTA", "SUB DEALER", "MEDIA PLANILLA"])
        contrato_firmado = st.selectbox("Contrato Firmado", ["", "SI", "NO"])

        hoy = date.today()
        fecha_creacion = st.date_input(
            "Fecha Creación Usuario",
            value=hoy,
            max_value=hoy + timedelta(days=2)
        )

        submit = st.form_submit_button("💾 Guardar")

        # =========================
        # VALIDACIONES
        # =========================
        if submit:

            # Normalizar y validar correo
            correo = correo.strip()
            patron_correo = r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"

            if not re.fullmatch(patron_correo, correo):
                st.error("❌ El CORREO no tiene un formato válido.")
                return

            if not razon_social or not departamento or not provincia:
                st.error("❌ Completa los campos obligatorios")
                return

            if not dni.isdigit() or len(dni) != 8:
                st.error("❌ DNI inválido")
                return

            # =========================
            # VALIDAR DNI ACTIVO
            # =========================
            registros = hoja_colaboradores.get_all_records()
            df = pd.DataFrame(registros)

            if not df.empty:
                df.columns = df.columns.str.strip().str.upper()
                df["DNI"] = df["DNI"].astype(str).str.strip()

                activo = df[(df["DNI"] == dni) & (df["ESTADO"] == "ACTIVO")]

                if not activo.empty:
                    st.error("❌ Este DNI ya está ACTIVO")
                    return

            # =========================
            # GUARDAR
            # =========================
            hoja_colaboradores.append_row([
                "",  # ✅ FIX: FECHA MOV vacía
                razon_social,
                "VENTAS INDIRECTAS",
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
                ape_paterno,
                ape_materno,
                celular,
                tipo_doc,
                dni,
                correo,
                "ACTIVO",
                tipo_contrato,
                str(fecha_creacion),
                "",
                "",
                contrato_firmado
            ])

            st.success("✅ Registro guardado correctamente")