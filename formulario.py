import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

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
# NORMALIZAR TEXTO
# =========================
def normalizar_texto(valor):
    if pd.isna(valor):
        return ""
    return str(valor).strip().upper()

# =========================
# FORMULARIO
# =========================
def mostrar_formulario(hoja_colaboradores, hoja_ubicaciones):

    st.subheader("📋 Registro de Vendedores")

    # =========================
    # UBICACIONES
    # =========================
    data_ubi = hoja_ubicaciones.get_all_records()
    df_ubi = pd.DataFrame(data_ubi)

    if df_ubi.empty:
        st.error("❌ No se encontró data en la hoja ubicaciones")
        return

    df_ubi.columns = df_ubi.columns.str.strip().str.upper()

    departamentos = sorted(df_ubi["DEPARTAMENTO"].dropna().unique())

    departamento = st.selectbox("DEPARTAMENTO", [""] + departamentos)

    provincias = []
    if departamento:
        df_filtrado = df_ubi[df_ubi["DEPARTAMENTO"] == departamento]
        provincias = sorted(df_filtrado["PROVINCIA"].dropna().unique())

    provincia = st.selectbox("PROVINCIA", [""] + provincias)

    # =========================
    # FORMULARIO
    # =========================
    with st.form("form_registro"):

        col1, col2 = st.columns(2)

        rol = st.session_state.get("rol", "")
        razon_usuario = st.session_state.get("razon", "")

        # =========================
        # RAZON SOCIAL (FIX ADMIN)
        # =========================
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
                value=hoy,
                min_value=hoy - timedelta(days=3),
                max_value=hoy + timedelta(days=7)
            )

            contrato_firmado = st.selectbox("CONTRATO FIRMADO", ["SI", "NO"])

        submit = st.form_submit_button("Guardar")

        if submit:

            dni_limpio = normalizar_dni(dni)

            # =========================
            # VALIDACIONES
            # =========================
            if not dni_limpio.isdigit() or len(dni_limpio) != 8:
                st.error("❌ DNI inválido")
                return

            if not celular.startswith("9"):
                st.error("❌ Celular inválido")
                return

            if "@" not in correo:
                st.error("❌ Correo inválido")
                return

            if departamento == "" or provincia == "":
                st.error("❌ Ubicación incompleta")
                return

            # =========================
            # VALIDACION DNI
            # =========================
            data = hoja_colaboradores.get_all_records()
            df = pd.DataFrame(data)

            if not df.empty:

                df.columns = df.columns.str.strip().str.upper()

                df["DNI_NORMALIZADO"] = df["DNI"].apply(normalizar_dni)
                df["ESTADO_NORMALIZADO"] = df["ESTADO"].apply(normalizar_texto)

                historial = df[df["DNI_NORMALIZADO"] == dni_limpio]

                # ACTIVO DUPLICADO
                if not historial[historial["ESTADO_NORMALIZADO"] == "ACTIVO"].empty:
                    st.error("❌ DNI ya tiene registro ACTIVO")
                    return

                # TRASLAPE
                for _, row in historial.iterrows():

                    f_ini = pd.to_datetime(row["FECHA DE CREACION USUARIO"], errors="coerce")
                    f_fin = pd.to_datetime(row["FECHA DE CESE"], errors="coerce")

                    if pd.isna(f_ini):
                        continue

                    f_ini = f_ini.date()

                    if pd.isna(f_fin):
                        st.error("❌ DNI sin fecha de cese")
                        return

                    f_fin = f_fin.date()

                    if f_ini <= fecha_creacion <= f_fin:
                        st.error("❌ DNI en rango activo previo")
                        return

                    if fecha_creacion <= f_fin:
                        st.error("❌ Fecha debe ser posterior a baja")
                        return

            # =========================
            # GUARDAR
            # =========================
            hoja_colaboradores.append_row([
                "",
                razon,  # 🔥 FIX CLAVE
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
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                ""
            ])

            st.success("✅ Guardado correctamente")
            limpiar_form()
            st.rerun()