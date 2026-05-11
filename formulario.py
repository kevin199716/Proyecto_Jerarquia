import streamlit as st
import pandas as pd
from datetime import datetime
import pytz

# =========================
# HORA PERÚ
# =========================
zona_peru = pytz.timezone("America/Lima")

def ahora_peru():
    return datetime.now(zona_peru).strftime("%Y-%m-%d")


# =========================
# LIMPIAR FORM
# =========================
def limpiar_form():

    for k in list(st.session_state.keys()):

        if k not in [
            "autenticado",
            "rol",
            "razon",
            "usuario"
        ]:
            del st.session_state[k]


# =========================
# NORMALIZAR DNI
# =========================
def normalizar_dni(valor):

    if pd.isna(valor):
        return ""

    dni = str(valor).strip().replace(".0", "")

    if dni.isdigit():
        dni = dni.zfill(8)

    return dni


# =========================
# FORMULARIO
# =========================
def mostrar_formulario(
    hoja_colaboradores,
    hoja_ubicaciones
):

    st.subheader("📋 Registro de Vendedores")

    # =========================
    # MENSAJE OK
    # =========================
    if st.session_state.get("mensaje_ok"):

        st.success("✅ Registrado correctamente")

        del st.session_state["mensaje_ok"]

    usuario_actual = st.session_state.get("usuario", "")

    rol = st.session_state.get("rol", "")

    razon_usuario = st.session_state.get("razon", "")

    # =========================
    # UBICACIONES
    # =========================
    data_ubi = hoja_ubicaciones.get_all_records()

    df_ubi = pd.DataFrame(data_ubi)

    df_ubi.columns = (
        df_ubi.columns
        .str.strip()
        .str.upper()
    )

    # =========================
    # DEPARTAMENTOS
    # =========================
    departamentos = sorted(
        df_ubi["DEPARTAMENTO"]
        .dropna()
        .unique()
    )

    departamento = st.selectbox(
        "DEPARTAMENTO",
        [""] + departamentos
    )

    # =========================
    # PROVINCIAS
    # =========================
    provincias = []

    if departamento:

        df_filtrado = df_ubi[
            df_ubi["DEPARTAMENTO"] == departamento
        ]

        provincias = sorted(
            df_filtrado["PROVINCIA"]
            .dropna()
            .unique()
        )

    provincia = st.selectbox(
        "PROVINCIA",
        [""] + provincias
    )

    # =========================
    # FILTRO PROVINCIA
    # =========================
    df_provincia = pd.DataFrame()

    if provincia:

        df_provincia = df_ubi[
            df_ubi["PROVINCIA"] == provincia
        ]

    # ==================================================
    # COORDINADOR
    # ==================================================
    coordinador = ""

    dni_coordinador = ""

    coordinadores = []

    if not df_provincia.empty:

        coordinadores = sorted(
            df_provincia[
                "COORDINADOR FINAL"
            ]
            .dropna()
            .astype(str)
            .unique()
        )

    coordinador = st.selectbox(
        "COORDINADOR",
        [""] + coordinadores
    )

    # =========================
    # DNI COORDINADOR
    # =========================
    if coordinador:

        fila_coord = df_provincia[
            df_provincia[
                "COORDINADOR FINAL"
            ] == coordinador
        ]

        if not fila_coord.empty:

            dni_coordinador = str(
                fila_coord.iloc[0][
                    "DNI COORDINADOR"
                ]
            )

    st.text_input(
        "DNI COORDINADOR",
        value=dni_coordinador,
        disabled=True
    )

    # ==================================================
    # SUPERVISOR
    # ==================================================
    supervisor = ""

    dni_supervisor = ""

    supervisores = []

    if not df_provincia.empty:

        supervisores = sorted(
            df_provincia[
                "SUPERVISOR A CARGO FINAL"
            ]
            .dropna()
            .astype(str)
            .unique()
        )

    supervisor = st.selectbox(
        "SUPERVISOR A CARGO",
        [""] + supervisores
    )

    # =========================
    # DNI SUPERVISOR
    # =========================
    if supervisor:

        fila_supervisor = df_provincia[
            df_provincia[
                "SUPERVISOR A CARGO FINAL"
            ] == supervisor
        ]

        if not fila_supervisor.empty:

            dni_supervisor = str(
                fila_supervisor.iloc[0][
                    "DNI SUPERVISOR"
                ]
            )

    st.text_input(
        "DNI SUPERVISOR",
        value=dni_supervisor,
        disabled=True
    )

    # =========================
    # FORMULARIO
    # =========================
    with st.form("form_registro"):

        col1, col2 = st.columns(2)

        razones = [
            "MALUTECH S.A.C.",
            "2CONNECT SERVICES S.A.C.",
            "INTERCONEXION 360 SAC",
            "NOGALES HIGH SAC",
            "MULTIPLE FORCE SAC",
            "KONECTA SAC"
        ]

        # =========================
        # COLUMNA 1
        # =========================
        with col1:

            if rol == "backoffice":

                razon = st.selectbox(
                    "RAZÓN SOCIAL",
                    [""] + razones
                )

            else:

                razon = razon_usuario

                st.text_input(
                    "RAZÓN SOCIAL",
                    value=razon,
                    disabled=True
                )

            canal = st.selectbox(
                "CANAL",
                ["VENTAS INDIRECTAS"]
            )

            subcanal = st.selectbox(
                "SUB CANAL",
                [
                    "VENTAS INDIRECTAS",
                    "OUTBOUND"
                ]
            )

            region = st.selectbox(
                "REGIÓN",
                [
                    "NORORIENTE",
                    "SUR",
                    "CENTRO"
                ]
            )

            cargo = st.selectbox(
                "CARGO (ROL)",
                [
                    "Agente BO D2D - Dealer",
                    "Promotor D2D - Dealer",
                    "Supervisor D2D - Dealer",
                    "Coordinador D2D - Dealer"
                ]
            )

        # =========================
        # COLUMNA 2
        # =========================
        with col2:

            nombres = st.text_input(
                "NOMBRES"
            )

            apellido_p = st.text_input(
                "APELLIDO PATERNO"
            )

            apellido_m = st.text_input(
                "APELLIDO MATERNO"
            )

            celular = st.text_input(
                "CELULAR"
            )

            tipo_doc = st.selectbox(
                "TIPO DE DOC",
                [
                    "DNI",
                    "CPP",
                    "CEX",
                    "OTROS"
                ]
            )

            dni = st.text_input(
                "DNI"
            )

            correo = st.text_input(
                "CORREO"
            )

            tipo_contrato = st.selectbox(
                "TIPO DE CONTRATO",
                [
                    "PLANILLA",
                    "COMISIONISTA",
                    "SUB DEALER",
                    "MEDIA PLANILLA"
                ]
            )

            fecha_creacion = st.date_input(
                "FECHA CREACIÓN",
                value=datetime.now().date()
            )

            contrato_firmado = st.selectbox(
                "CONTRATO FIRMADO",
                [
                    "SI",
                    "NO"
                ]
            )

        # =========================
        # BOTÓN
        # =========================
        submit = st.form_submit_button(
            "Guardar"
        )

        # =========================
        # GUARDAR
        # =========================
        if submit:

            dni_limpio = normalizar_dni(
                dni
            )

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

                "",

                usuario_actual,

                ""

            ])

            st.session_state["mensaje_ok"] = True

            limpiar_form()

            st.rerun()