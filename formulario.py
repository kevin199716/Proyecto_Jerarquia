import re
from datetime import datetime

import pandas as pd
import pytz
import streamlit as st

# =========================
# HORA PERÚ
# =========================
zona_peru = pytz.timezone("America/Lima")


def ahora_peru_fecha() -> str:
    return datetime.now(zona_peru).strftime("%Y-%m-%d")


def ahora_peru_fecha_hora() -> str:
    return datetime.now(zona_peru).strftime("%Y-%m-%d %H:%M:%S")


# =========================
# LIMPIAR FORM
# =========================
def limpiar_form():
    conservar = {"autenticado", "rol", "razon", "usuario", "user", "pass"}
    for k in list(st.session_state.keys()):
        if k not in conservar:
            del st.session_state[k]


# =========================
# NORMALIZADORES
# =========================
def limpiar_texto(valor) -> str:
    if pd.isna(valor) if not isinstance(valor, str) else False:
        return ""
    s = str(valor).strip()
    return "" if s.upper() in ("NONE", "NAN", "NULL") else s


def normalizar_columnas(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = df.columns.astype(str).str.strip().str.upper()
    return df


def normalizar_dni(valor) -> str:
    dni = limpiar_texto(valor).replace(".0", "")
    dni = re.sub(r"\D", "", dni)
    if dni and len(dni) < 8:
        dni = dni.zfill(8)
    return dni


def limpiar_celular(valor) -> str:
    return re.sub(r"\D", "", limpiar_texto(valor))


def parse_fecha(valor):
    if valor in (None, ""):
        return None
    try:
        f = pd.to_datetime(valor, errors="coerce", dayfirst=False)
        if pd.isna(f):
            return None
        return f.date()
    except Exception:
        return None


# =========================
# LECTURAS GOOGLE SHEETS
# =========================
def leer_ubicaciones(hoja_ubicaciones):
    valores = hoja_ubicaciones.get_all_values()
    if not valores:
        return pd.DataFrame()

    headers = [str(h).strip().upper() for h in valores[0]]
    data = valores[1:]
    df = pd.DataFrame(data, columns=headers)

    nuevas_columnas = []
    contador_dni = 0
    for col in df.columns:
        if col == "DNI FINAL":
            contador_dni += 1
            nuevas_columnas.append("DNI SUPERVISOR" if contador_dni == 1 else "DNI COORDINADOR")
        else:
            nuevas_columnas.append(col)

    df.columns = nuevas_columnas
    return normalizar_columnas(df).fillna("")


@st.cache_data(ttl=60, show_spinner=False)
def _leer_colaboradores_cached(_hoja_colaboradores):
    data = _hoja_colaboradores.get_all_records()
    df = pd.DataFrame(data)
    if df.empty:
        return pd.DataFrame()
    return normalizar_columnas(df).fillna("")


def leer_colaboradores(hoja_colaboradores, forzar=False):
    if forzar:
        _leer_colaboradores_cached.clear()
    return _leer_colaboradores_cached(hoja_colaboradores)


def obtener_headers(hoja_colaboradores) -> list[str]:
    valores = hoja_colaboradores.get_all_values()
    if not valores:
        return []
    return [str(h).strip().upper() for h in valores[0]]


# =========================
# VALIDACIONES DE NEGOCIO
# =========================
def validar_dni_unico_historico(df_colab: pd.DataFrame, dni_limpio: str, fecha_alta) -> tuple[bool, str]:
    if df_colab.empty or "DNI" not in df_colab.columns:
        return True, ""

    df = df_colab.copy()
    df["DNI_NORM"] = df["DNI"].apply(normalizar_dni)
    encontrados = df[df["DNI_NORM"].eq(dni_limpio)].copy()

    if encontrados.empty:
        return True, ""

    if "ESTADO" in encontrados.columns:
        activos = encontrados[encontrados["ESTADO"].astype(str).str.strip().str.upper().eq("ACTIVO")]
    else:
        activos = pd.DataFrame()

    if not activos.empty:
        detalle = activos.iloc[0]
        razon = limpiar_texto(detalle.get("RAZON SOCIAL", ""))
        nombre = " ".join([
            limpiar_texto(detalle.get("NOMBRES", detalle.get("NOMBRE", ""))),
            limpiar_texto(detalle.get("APELLIDO PATERNO", "")),
            limpiar_texto(detalle.get("APELLIDO MATERNO", "")),
        ]).strip()
        return False, (
            f"❌ El DNI {dni_limpio} ya se encuentra ACTIVO en la base. "
            f"No se puede registrar nuevamente, indistintamente del dealer. "
            f"Registro activo: {razon} / {nombre}."
        )

    # Si solo hay históricos inactivos, la nueva alta debe ser estrictamente mayor
    # a la última fecha de cese/movimiento registrada.
    columnas_baja = [
        "FECHA DE CESE",
        "FECHA CESE",
        "FECHA MOV",
        "FECHA_BAJA_REGISTRO",
        "FECHA BAJA REGISTRO",
    ]

    fechas_baja = []
    for _, row in encontrados.iterrows():
        for col in columnas_baja:
            if col in encontrados.columns:
                f = parse_fecha(row.get(col))
                if f:
                    fechas_baja.append(f)

    if fechas_baja:
        ultima_baja = max(fechas_baja)
        if fecha_alta <= ultima_baja:
            return False, (
                f"❌ La fecha de alta ({fecha_alta}) debe ser MAYOR a la última baja/movimiento "
                f"del DNI {dni_limpio}: {ultima_baja}. No puede ser igual ni menor."
            )

    return True, ""


def validar_formulario(campos: dict, df_colab: pd.DataFrame) -> list[str]:
    errores = []

    requeridos = [
        "RAZON SOCIAL", "CANAL", "SUB CANAL", "REGION", "CARGO (ROL)",
        "NOMBRES", "APELLIDO PATERNO", "APELLIDO MATERNO", "CELULAR",
        "TIPO DE DOC", "DNI", "CORREO", "TIPO DE CONTRATO",
        "FECHA DE CREACION USUARIO", "CONTRATO FIRMADO",
        "DEPARTAMENTO", "PROVINCIA", "SUPERVISOR A CARGO", "DNI SUPERVISOR",
        "COORDINADOR", "DNI COORDINADOR",
    ]

    for c in requeridos:
        if limpiar_texto(campos.get(c, "")) == "":
            errores.append(f"❌ Campo obligatorio pendiente: {c}")

    celular = limpiar_celular(campos.get("CELULAR", ""))
    if celular and (not celular.isdigit() or len(celular) != 9):
        errores.append("❌ El CELULAR debe tener exactamente 9 dígitos.")

    dni_original = limpiar_texto(campos.get("DNI", ""))
    dni_limpio = normalizar_dni(dni_original)
    if not dni_original:
        errores.append("❌ El DNI es obligatorio.")
    elif not dni_original.replace(".0", "").isdigit():
        errores.append("❌ El DNI solo debe contener números.")
    elif len(dni_original.replace(".0", "")) > 8:
        errores.append("❌ El DNI no puede tener más de 8 dígitos.")
    elif len(dni_limpio) != 8:
        errores.append("❌ El DNI debe quedar con exactamente 8 dígitos.")

    correo = limpiar_texto(campos.get("CORREO", ""))
    if correo and not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", correo):
        errores.append("❌ El CORREO no tiene un formato válido.")

    contrato = limpiar_texto(campos.get("TIPO DE CONTRATO", "")).upper()
    if contrato and contrato not in ("PLANILLA", "MEDIA PLANILLA"):
        errores.append("❌ Tipo de contrato inválido. Solo se permite PLANILLA o MEDIA PLANILLA.")

    firmado = limpiar_texto(campos.get("CONTRATO FIRMADO", "")).upper()
    if firmado != "SI":
        errores.append("❌ CONTRATO FIRMADO debe quedar en SI para registrar el alta.")

    fecha_alta = campos.get("FECHA DE CREACION USUARIO")
    if fecha_alta:
        ok, msg = validar_dni_unico_historico(df_colab, dni_limpio, fecha_alta)
        if not ok:
            errores.append(msg)

    return errores


# =========================
# APPEND POR NOMBRE DE COLUMNA
# =========================
def valor_por_columna(headers: list[str], campos: dict) -> list[str]:
    # Compatibilidad con nombres reales/variaciones de la hoja.
    aliases = {
        "FECHA CREACIÓN": "FECHA DE CREACION USUARIO",
        "FECHA DE CREACIÓN USUARIO": "FECHA DE CREACION USUARIO",
        "FECHA_CREACION_USUARIO": "FECHA DE CREACION USUARIO",
        "CORREO": "CORREO (USUARIO SGC/PRONTO)",
        "EMAIL": "CORREO (USUARIO SGC/PRONTO)",
        "FECHA ALTA REGISTRO": "FECHA_ALTA_REGISTRO",
        "USUARIO ALTA": "USUARIO_ALTA",
    }

    row = []
    for h in headers:
        col = aliases.get(h, h)
        row.append(campos.get(col, ""))
    return row


# =========================
# FORMULARIO
# =========================
def mostrar_formulario(hoja_colaboradores, hoja_ubicaciones, hoja_asistencia=None):
    st.markdown("<span class='wow-section-title'>📋 Alta de Vendedores</span>", unsafe_allow_html=True)

    if st.session_state.get("mensaje_ok"):
        msg_ok = st.session_state.get("mensaje_ok")
        st.success(msg_ok if isinstance(msg_ok, str) else "✅ Registrado correctamente")
        del st.session_state["mensaje_ok"]

    if st.session_state.get("mensaje_sync_warning"):
        st.warning(st.session_state.get("mensaje_sync_warning"))
        del st.session_state["mensaje_sync_warning"]

    usuario_actual = st.session_state.get("usuario", "")
    rol = st.session_state.get("rol", "")
    razon_usuario = st.session_state.get("razon", "")

    df_colab = leer_colaboradores(hoja_colaboradores)
    df_ubi = leer_ubicaciones(hoja_ubicaciones)

    if df_ubi.empty:
        st.error("❌ No se pudo leer la hoja de ubicaciones.")
        return

    razones = [
        "MALUTECH S.A.C.",
        "2CONNECT SERVICES S.A.C.",
        "INTERCONEXION 360 SAC",
        "NOGALES HIGH SAC",
        "MULTIPLE FORCE SAC",
        "KONECTA SAC",
    ]

    departamentos = []
    if "DEPARTAMENTO" in df_ubi.columns:
        departamentos = sorted(df_ubi["DEPARTAMENTO"].replace("", pd.NA).dropna().astype(str).unique())

    # ==========================================================
    # IMPORTANTE: estos campos quedan FUERA del st.form.
    # En Streamlit, los widgets dentro de un form no recalculan dependientes
    # hasta presionar submit. Por eso provincia/DNI supervisor/DNI coordinador
    # se congelaban o quedaban en blanco.
    # ==========================================================
    st.caption("Primero completa datos del colaborador y dealer. La ubicación y jerarquía se actualiza en línea desde la hoja ubicaciones.")

    col_izq, col_der = st.columns(2)

    with col_izq:
        st.markdown("**Datos del colaborador**")
        nombres = st.text_input("NOMBRES", key="alta_nombres")
        apellido_p = st.text_input("APELLIDO PATERNO", key="alta_apellido_p")
        apellido_m = st.text_input("APELLIDO MATERNO", key="alta_apellido_m")
        celular = st.text_input("CELULAR", max_chars=9, key="alta_celular")
        tipo_doc = st.selectbox("TIPO DE DOC", ["DNI", "CPP", "CEX", "OTROS"], key="alta_tipo_doc")
        dni = st.text_input("DNI", max_chars=8, key="alta_dni")
        correo = st.text_input("CORREO (USUARIO SGC/PRONTO)", key="alta_correo")

    with col_der:
        st.markdown("**Datos comerciales**")
        if rol == "backoffice":
            razon = st.selectbox("RAZÓN SOCIAL", [""] + razones, key="alta_razon")
        else:
            razon = razon_usuario
            st.text_input("RAZÓN SOCIAL", value=razon, disabled=True, key="alta_razon_dealer")

        canal = st.selectbox("CANAL", ["VENTAS INDIRECTAS"], key="alta_canal")
        subcanal = st.selectbox("SUB CANAL", ["VENTAS INDIRECTAS", "OUTBOUND"], key="alta_subcanal")
        region = st.selectbox("REGIÓN", ["", "NORORIENTE", "SUR", "CENTRO", "CENTRAL"], key="alta_region")
        cargo = st.selectbox(
            "CARGO (ROL)",
            [
                "",
                "Agente BO D2D - Dealer",
                "Promotor D2D - Dealer",
                "Supervisor D2D - Dealer",
                "Coordinador D2D - Dealer",
            ],
            key="alta_cargo",
        )
        tipo_contrato = st.selectbox(
            "TIPO DE CONTRATO",
            ["", "PLANILLA", "MEDIA PLANILLA"],
            key="alta_tipo_contrato",
        )
        fecha_creacion = st.date_input("FECHA CREACIÓN USUARIO", value=datetime.now(zona_peru).date(), key="alta_fecha_creacion")
        contrato_firmado = st.selectbox("CONTRATO FIRMADO", ["SI", "NO"], index=0, key="alta_contrato_firmado")

    st.divider()
    st.markdown("**Ubicación y jerarquía**")
    col_u1, col_u2 = st.columns(2)

    with col_u1:
        departamento = st.selectbox("DEPARTAMENTO", [""] + departamentos, key="alta_departamento")

        provincias = []
        if departamento and "DEPARTAMENTO" in df_ubi.columns and "PROVINCIA" in df_ubi.columns:
            df_dep = df_ubi[df_ubi["DEPARTAMENTO"].astype(str).str.strip().eq(str(departamento).strip())]
            provincias = sorted(df_dep["PROVINCIA"].replace("", pd.NA).dropna().astype(str).unique())

        provincia = st.selectbox("PROVINCIA", [""] + provincias, key="alta_provincia")

        # Coordinador filtrado por departamento/provincia cuando exista relación en la hoja.
        df_jer = df_ubi.copy()
        if departamento and "DEPARTAMENTO" in df_jer.columns:
            df_jer = df_jer[df_jer["DEPARTAMENTO"].astype(str).str.strip().eq(str(departamento).strip())]
        if provincia and "PROVINCIA" in df_jer.columns:
            df_jer = df_jer[df_jer["PROVINCIA"].astype(str).str.strip().eq(str(provincia).strip())]

        coordinadores = []
        if "COORDINADOR FINAL" in df_jer.columns:
            coordinadores = sorted(df_jer["COORDINADOR FINAL"].replace("", pd.NA).dropna().astype(str).unique())
        elif "COORDINADOR FINAL" in df_ubi.columns:
            coordinadores = sorted(df_ubi["COORDINADOR FINAL"].replace("", pd.NA).dropna().astype(str).unique())

        coordinador = st.selectbox("COORDINADOR", [""] + coordinadores, key="alta_coordinador")
        dni_coordinador = ""
        if coordinador and "COORDINADOR FINAL" in df_ubi.columns:
            df_match = df_jer if not df_jer.empty else df_ubi
            fila_coord = df_match[df_match["COORDINADOR FINAL"].astype(str).str.strip().eq(str(coordinador).strip())]
            if fila_coord.empty:
                fila_coord = df_ubi[df_ubi["COORDINADOR FINAL"].astype(str).str.strip().eq(str(coordinador).strip())]
            if not fila_coord.empty and "DNI COORDINADOR" in fila_coord.columns:
                dni_coordinador = limpiar_texto(fila_coord.iloc[0].get("DNI COORDINADOR", "")).replace(".0", "")
        st.text_input("DNI COORDINADOR", value=dni_coordinador, disabled=True, key="alta_dni_coordinador")

    with col_u2:
        supervisores = []
        if "SUPERVISOR A CARGO FINAL" in df_jer.columns:
            supervisores = sorted(df_jer["SUPERVISOR A CARGO FINAL"].replace("", pd.NA).dropna().astype(str).unique())
        elif "SUPERVISOR A CARGO FINAL" in df_ubi.columns:
            supervisores = sorted(df_ubi["SUPERVISOR A CARGO FINAL"].replace("", pd.NA).dropna().astype(str).unique())

        supervisor = st.selectbox("SUPERVISOR A CARGO", [""] + supervisores, key="alta_supervisor")
        dni_supervisor = ""
        if supervisor and "SUPERVISOR A CARGO FINAL" in df_ubi.columns:
            df_match = df_jer if not df_jer.empty else df_ubi
            fila_supervisor = df_match[df_match["SUPERVISOR A CARGO FINAL"].astype(str).str.strip().eq(str(supervisor).strip())]
            if fila_supervisor.empty:
                fila_supervisor = df_ubi[df_ubi["SUPERVISOR A CARGO FINAL"].astype(str).str.strip().eq(str(supervisor).strip())]
            if not fila_supervisor.empty and "DNI SUPERVISOR" in fila_supervisor.columns:
                dni_supervisor = limpiar_texto(fila_supervisor.iloc[0].get("DNI SUPERVISOR", "")).replace(".0", "")
        st.text_input("DNI SUPERVISOR", value=dni_supervisor, disabled=True, key="alta_dni_supervisor")

    st.markdown("")
    submit = st.button("Guardar Alta", key="btn_guardar_alta")

    if submit:
        dni_limpio = normalizar_dni(dni)
        celular_limpio = limpiar_celular(celular)
        correo_limpio = limpiar_texto(correo).lower()
        marca_alta = ahora_peru_fecha_hora()

        campos = {
            "FECHA MOV": str(fecha_creacion),  # movimiento del alta: solo fecha
            "RAZON SOCIAL": razon,
            "CANAL": canal,
            "SUB CANAL": subcanal,
            "REGION": region,
            "DEPARTAMENTO": departamento,
            "PROVINCIA": provincia,
            "SUPERVISOR A CARGO": supervisor,
            "DNI SUPERVISOR": dni_supervisor,
            "COORDINADOR": coordinador,
            "DNI COORDINADOR": dni_coordinador,
            "CARGO (ROL)": cargo,
            "NOMBRES": limpiar_texto(nombres).upper(),
            "APELLIDO PATERNO": limpiar_texto(apellido_p).upper(),
            "APELLIDO MATERNO": limpiar_texto(apellido_m).upper(),
            "CELULAR": celular_limpio,
            "TIPO DE DOC": tipo_doc,
            "DNI": dni_limpio,
            "CORREO (USUARIO SGC/PRONTO)": correo_limpio,
            "ESTADO": "ACTIVO",
            "TIPO DE CONTRATO": tipo_contrato,
            "FECHA DE CREACION USUARIO": str(fecha_creacion),
            "FECHA DE CESE": "",
            "MOTIVO": "",
            "CONTRATO FIRMADO": contrato_firmado,
            "FECHA_ALTA_REGISTRO": marca_alta,  # marcaje de registro: fecha y hora
            "FECHA ALTA REGISTRO": marca_alta,
            "FECHA_BAJA_REGISTRO": "",
            "FECHA BAJA REGISTRO": "",
            "USUARIO_ALTA": usuario_actual,
            "USUARIO ALTA": usuario_actual,
            "USUARIO_BAJA": "",
            "USUARIO BAJA": "",
        }

        errores = validar_formulario(campos, df_colab)
        if errores:
            for err in errores:
                st.error(err)
            return

        try:
            headers = obtener_headers(hoja_colaboradores)
            if not headers:
                st.error("❌ La hoja colaboradores no tiene cabecera. No se puede registrar.")
                return

            fila = valor_por_columna(headers, campos)
            hoja_colaboradores.append_row(fila, value_input_option="USER_ENTERED")
            leer_colaboradores(hoja_colaboradores, forzar=True)

            # Hace que el alta aparezca en Presencialidad Dealer sin esperar 5 minutos.
            if hoja_asistencia is not None:
                try:
                    from asistencia import sincronizar_mes, cargar_cache_desde_drive
                    nuevos, actualizados = sincronizar_mes(hoja_asistencia, hoja_colaboradores)
                    cargar_cache_desde_drive(hoja_asistencia, forzar=True)
                    st.session_state["mensaje_ok"] = f"✅ Registrado correctamente. Presencialidad actualizada: nuevos {nuevos}, base actualizada {actualizados}."
                except Exception as e_sync:
                    st.session_state["mensaje_ok"] = "✅ Registrado correctamente. Para verlo en Presencialidad Dealer, presiona Sincronizar mes."
                    st.session_state["mensaje_sync_warning"] = f"⚠️ No se pudo sincronizar presencialidad automáticamente: {e_sync}"
            else:
                st.session_state["mensaje_ok"] = "✅ Registrado correctamente. Para verlo en Presencialidad Dealer, presiona Sincronizar mes."

            limpiar_form()
            st.rerun()
        except Exception as e:
            st.error(f"❌ Error al registrar el alta: {e}")
