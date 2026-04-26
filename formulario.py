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
    dni = dni.replace("'", "")
    dni = dni.replace(".0", "")
    dni = dni.replace(" ", "")

    if dni.isdigit():
        dni = dni.zfill(8)

    return dni


# =========================
# NORMALIZAR ESTADO
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

    departamento = st.selectbox(
        "DEPARTAMENTO",
        [""] + departamentos,
        key="dep"
    )

    provincias = []
    if departamento:
        df_filtrado = df_ubi[df_ubi["DEPARTAMENTO"] == departamento]
        provincias = sorted(df_filtrado["PROVINCIA"].dropna().unique())

    provincia = st.selectbox(
        "PROVINCIA",
        [""] + provincias,
        key="prov"
    )

    # =========================
    # FORMULARIO
    # =========================
    with st.form("form_registro"):

        col1, col2 = st.columns(2)

        razon_usuario = st.session_state.get("razon", "")

        # =========================
        # COLUMNA 1
        # =========================
        with col1:

            st.text_input(
                "RAZON SOCIAL",
                value=razon_usuario,
                disabled=True,
                key="razon_disabled"
            )

            canal = st.selectbox(
                "CANAL",
                ["VENTAS INDIRECTAS"],
                key="canal"
            )

            subcanal = st.selectbox(
                "SUB CANAL",
                ["VENTAS INDIRECTAS", "OUTBOUND"],
                key="subcanal"
            )

            region = st.selectbox(
                "REGION",
                ["NORORIENTE", "SUR", "CENTRAL"],
                key="region"
            )

            supervisor = st.text_input("SUPERVISOR A CARGO", key="sup")
            dni_supervisor = st.text_input("DNI SUPERVISOR", key="dnisup")

            coordinador = st.text_input("COORDINADOR", key="coord")
            dni_coordinador = st.text_input("DNI COORDINADOR", key="dnicoord")

            cargo = st.selectbox(
                "CARGO (ROL)",
                [
                    "Agente BO D2D - Dealer",
                    "Promotor D2D - Dealer",
                    "Supervisor D2D - Dealer",
                    "Coordinador D2D - Dealer"
                ],
                key="cargo"
            )

        # =========================
        # COLUMNA 2
        # =========================
        with col2:

            nombres = st.text_input("NOMBRES", key="nom")
            apellido_p = st.text_input("APELLIDO PATERNO", key="ap")
            apellido_m = st.text_input("APELLIDO MATERNO", key="am")

            celular = st.text_input("CELULAR", key="cel")

            tipo_doc = st.selectbox(
                "TIPO DE DOC",
                ["DNI", "CPP", "CEX", "OTROS"],
                key="tipodoc"
            )

            dni = st.text_input("DNI", key="dni")

            correo = st.text_input("CORREO", key="correo")

            tipo_contrato = st.selectbox(
                "TIPO DE CONTRATO",
                ["PLANILLA", "COMISIONISTA", "SUB DEALER", "MEDIA PLANILLA"],
                key="contrato"
            )

            hoy = datetime.now().date()

            fecha_creacion = st.date_input(
                "FECHA CREACION",
                value=hoy,
                min_value=hoy - timedelta(days=3),
                max_value=hoy + timedelta(days=7),
                key="fecha"
            )

            contrato_firmado = st.selectbox(
                "CONTRATO FIRMADO",
                ["SI", "NO"],
                key="firma"
            )

        submit = st.form_submit_button("Guardar")

        if submit:

            # =========================
            # NORMALIZAR DNI INGRESADO
            # =========================
            dni_limpio = normalizar_dni(dni)

            # =========================
            # VALIDACIONES BÁSICAS
            # =========================
            if not dni_limpio.isdigit() or len(dni_limpio) != 8:
                st.error("❌ DNI inválido. Debe tener 8 dígitos.")
                return

            if not celular.strip().startswith("9"):
                st.error("❌ Celular inválido. Debe iniciar con 9.")
                return

            if "@" not in correo:
                st.error("❌ Correo inválido.")
                return

            if departamento == "":
                st.error("❌ Debes seleccionar departamento.")
                return

            if provincia == "":
                st.error("❌ Debes seleccionar provincia.")
                return

            # =========================
            # VALIDACIÓN DNI GLOBAL
            # =========================
            data = hoja_colaboradores.get_all_records()
            df = pd.DataFrame(data)

            if not df.empty:

                df.columns = df.columns.str.strip().str.upper()

                columnas_obligatorias = [
                    "DNI",
                    "ESTADO",
                    "FECHA DE CREACION USUARIO",
                    "FECHA DE CESE"
                ]

                for col in columnas_obligatorias:
                    if col not in df.columns:
                        st.error(f"❌ No existe la columna obligatoria en Sheets: {col}")
                        return

                df["DNI_NORMALIZADO"] = df["DNI"].apply(normalizar_dni)
                df["ESTADO_NORMALIZADO"] = df["ESTADO"].apply(normalizar_texto)

                historial = df[df["DNI_NORMALIZADO"] == dni_limpio]

                # =========================
                # BLOQUEO 1: SI YA EXISTE ACTIVO
                # =========================
                activos = historial[historial["ESTADO_NORMALIZADO"] == "ACTIVO"]

                if not activos.empty:
                    st.error(
                        f"❌ DNI DUPLICADO: el DNI {dni_limpio} ya tiene "
                        f"{len(activos)} registro(s) ACTIVO(s). No se puede volver a registrar."
                    )
                    return

                # =========================
                # BLOQUEO 2: VALIDAR TRAMOS
                # =========================
                for _, row in historial.iterrows():

                    f_ini = pd.to_datetime(
                        row.get("FECHA DE CREACION USUARIO"),
                        errors="coerce"
                    )

                    f_fin = pd.to_datetime(
                        row.get("FECHA DE CESE"),
                        errors="coerce"
                    )

                    if pd.isna(f_ini):
                        continue

                    f_ini = f_ini.date()

                    # Si por algún motivo está sin fecha de cese, también bloquea
                    if pd.isna(f_fin):
                        st.error(
                            f"❌ DNI DUPLICADO: el DNI {dni_limpio} tiene un registro sin fecha de cese. "
                            f"No se puede registrar hasta regularizar la baja."
                        )
                        return

                    f_fin = f_fin.date()

                    # No puede entrar dentro del tramo anterior
                    if f_ini <= fecha_creacion <= f_fin:
                        st.error(
                            f"❌ TRASLAPE DE DNI: el DNI {dni_limpio} ya estuvo activo "
                            f"desde {f_ini} hasta {f_fin}. No puedes registrarlo dentro de ese rango."
                        )
                        return

                    # Regla final: debe ser estrictamente posterior a la última baja
                    if fecha_creacion <= f_fin:
                        st.error(
                            f"❌ FECHA NO PERMITIDA: el DNI {dni_limpio} solo puede registrarse "
                            f"después de su última baja ({f_fin})."
                        )
                        return

            # =========================
            # GUARDAR
            # =========================
            hoja_colaboradores.append_row([
                "",                         # FECHA MOV
                razon_usuario,              # RAZON SOCIAL
                canal,                       # CANAL
                subcanal,                    # SUB CANAL
                region,                      # REGION
                departamento,                # DEPARTAMENTO
                provincia,                   # PROVINCIA
                supervisor,                  # SUPERVISOR A CARGO
                dni_supervisor,              # DNI SUPERVISOR
                coordinador,                 # COORDINADOR
                dni_coordinador,             # DNI COORDINADOR
                cargo,                       # CARGO (ROL)
                nombres,                     # NOMBRES
                apellido_p,                  # APELLIDO PATERNO
                apellido_m,                  # APELLIDO MATERNO
                celular,                     # CELULAR
                tipo_doc,                    # TIPO DE DOC
                dni_limpio,                  # DNI
                correo.lower(),              # CORREO
                "ACTIVO",                   # ESTADO
                tipo_contrato,               # TIPO DE CONTRATO
                str(fecha_creacion),         # FECHA DE CREACION USUARIO
                "",                         # FECHA DE CESE
                "",                         # MOTIVO
                contrato_firmado,            # CONTRATO FIRMADO
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),  # FECHA_ALTA_REGISTRO
                ""                          # FECHA_BAJA_REGISTRO
            ])

            st.success("✅ Guardado correctamente")
            limpiar_form()
            st.rerun()