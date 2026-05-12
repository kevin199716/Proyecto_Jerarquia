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
# LEER UBICACIONES
# =========================
def leer_ubicaciones(hoja_ubicaciones):

    valores = hoja_ubicaciones.get_all_values()

    if not valores:
        return pd.DataFrame()

    headers = [
        str(h).strip().upper()
        for h in valores[0]
    ]

    data = valores[1:]

    df = pd.DataFrame(
        data,
        columns=headers
    )

    # =========================
    # RENOMBRAR COLUMNAS
    # =========================
    nuevas_columnas = []

    contador_dni = 0

    for col in df.columns:

        if col == "DNI FINAL":

            contador_dni += 1

            if contador_dni == 1:
                nuevas_columnas.append(
                    "DNI SUPERVISOR"
                )

            else:
                nuevas_columnas.append(
                    "DNI COORDINADOR"
                )

        else:
            nuevas_columnas.append(col)

    df.columns = nuevas_columnas

    return df


# =========================
# FORMULARIO
# =========================
def mostrar_formulario(
    hoja_colaboradores,
    hoja_ubicaciones
):

    st.subheader("📋 Registro de Vendedores")

    if st.session_state.get("mensaje_ok"):

        st.success("✅ Registrado correctamente")

        del st.session_state["mensaje_ok"]

    usuario_actual = st.session_state.get("usuario", "")

    rol = st.session_state.get("rol", "")

    razon_usuario = st.session_state.get("razon", "")

    # =========================
    # UBICACIONES
    # =========================
    df_ubi = leer_ubicaciones(
        hoja_ubicaciones
    )

    # =========================
    # DEPARTAMENTOS
    # =========================
    departamentos = sorted(

        df_ubi["DEPARTAMENTO"]
        .replace("", pd.NA)
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
            .replace("", pd.NA)
            .dropna()
            .unique()
        )

    provincia = st.selectbox(
        "PROVINCIA",
        [""] + provincias
    )

    # ==================================================
    # COORDINADORES
    # ==================================================
    coordinador = ""

    dni_coordinador = ""

    coordinadores = sorted(

        df_ubi[
            "COORDINADOR FINAL"
        ]
        .replace("", pd.NA)
        .dropna()
        .astype(str)
        .unique()
    )

    coordinador = st.selectbox(
        "COORDINADOR",
        [""] + coordinadores
    )

    if coordinador:

        fila_coord = df_ubi[
            df_ubi[
                "COORDINADOR FINAL"
            ] == coordinador
        ]

        if not fila_coord.empty:

            dni_coordinador = str(
                fila_coord.iloc[0][
                    "DNI COORDINADOR"
                ]
            ).replace(".0", "").strip()

    st.text_input(
        "DNI COORDINADOR",
        value=dni_coordinador,
        disabled=True
    )

    # ==================================================
    # SUPERVISORES
    # ==================================================
    supervisor = ""

    dni_supervisor = ""

    supervisores = sorted(

        df_ubi[
            "SUPERVISOR A CARGO FINAL"
        ]
        .replace("", pd.NA)
        .dropna()
        .astype(str)
        .unique()
    )

    supervisor = st.selectbox(
        "SUPERVISOR A CARGO",
        [""] + supervisores
    )

    if supervisor:

        fila_supervisor = df_ubi[
            df_ubi[
                "SUPERVISOR A CARGO FINAL"
            ] == supervisor
        ]

        if not fila_supervisor.empty:

            dni_supervisor = str(
                fila_supervisor.iloc[0][
                    "DNI SUPERVISOR"
                ]
            ).replace(".0", "").strip()

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

        with col2:

            nombres = st.text_input("NOMBRES")

            apellido_p = st.text_input("APELLIDO PATERNO")

            apellido_m = st.text_input("APELLIDO MATERNO")

            celular = st.text_input("CELULAR")

            tipo_doc = st.selectbox(
                "TIPO DE DOC",
                [
                    "DNI",
                    "CPP",
                    "CEX",
                    "OTROS"
                ]
            )

            dni = st.text_input("DNI")

            correo = st.text_input("CORREO")

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

        submit = st.form_submit_button(
            "Guardar"
        )

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