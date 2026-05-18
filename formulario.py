import re
from datetime import datetime, timedelta

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
    conservar = {"autenticado", "rol", "razon", "usuario", "user", "pass", "mensaje_ok", "mensaje_sync_warning"}
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


def hacer_columnas_unicas(columnas: list[str]) -> list[str]:
    """
    Evita el error: AttributeError: DataFrame object has no attribute str.
    Ese error aparece cuando una cabecera está duplicada y df[col] devuelve otro DataFrame.
    En la hoja ubicaciones hay columnas repetidas / bloques separados.
    """
    salida = []
    vistos = {}
    for i, col in enumerate(columnas, start=1):
        base = str(col).strip().upper() or f"COLUMNA_{i}"
        if base not in vistos:
            vistos[base] = 1
            salida.append(base)
        else:
            vistos[base] += 1
            salida.append(f"{base}_{vistos[base]}")
    return salida


def serie_columna(df: pd.DataFrame, columna: str) -> pd.Series:
    """Devuelve siempre una Serie aunque la columna exista duplicada."""
    if df.empty or columna not in df.columns:
        return pd.Series([], dtype=str)
    obj = df[columna]
    if isinstance(obj, pd.DataFrame):
        obj = obj.iloc[:, 0]
    return obj.astype(str).str.strip()


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
@st.cache_data(ttl=300, show_spinner=False)
def _leer_ubicaciones_cached(_hoja_ubicaciones):
    valores = _hoja_ubicaciones.get_all_values()
    if not valores:
        return pd.DataFrame()

    headers = [str(h).strip().upper() for h in valores[0]]
    data = valores[1:]
    n = len(headers)
    filas = []
    for fila in data:
        fila = list(fila)
        if len(fila) < n:
            fila += [""] * (n - len(fila))
        filas.append(fila[:n])

    df = pd.DataFrame(filas, columns=headers)

    # En ubicaciones hay dos columnas con el mismo nombre: DNI FINAL.
    # La primera corresponde a supervisor y la segunda a coordinador.
    nuevas_columnas = []
    contador_dni = 0
    for col in df.columns:
        col_up = str(col).strip().upper()
        if col_up == "DNI FINAL":
            contador_dni += 1
            nuevas_columnas.append("DNI SUPERVISOR" if contador_dni == 1 else "DNI COORDINADOR")
        else:
            nuevas_columnas.append(col_up)

    df.columns = hacer_columnas_unicas(nuevas_columnas)
    df = normalizar_columnas(df).fillna("")

    # Limpieza segura: no usar df[c].str directo porque si una cabecera queda duplicada
    # pandas devuelve DataFrame y rompe Render.
    df = df.astype(str).apply(lambda col: col.str.strip())
    return df


def leer_ubicaciones(hoja_ubicaciones, forzar=False):
    if forzar:
        _leer_ubicaciones_cached.clear()
    return _leer_ubicaciones_cached(hoja_ubicaciones)


@st.cache_data(ttl=300, show_spinner=False)
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
# LISTAS DESDE UBICACIONES
# =========================
def lista_limpia(df: pd.DataFrame, columna: str) -> list[str]:
    if df.empty or columna not in df.columns:
        return []
    serie = serie_columna(df, columna)
    return sorted(
        serie
        .replace("", pd.NA)
        .dropna()
        .unique()
        .tolist()
    )


def buscar_dni_por_nombre(df: pd.DataFrame, columna_nombre: str, columna_dni: str, nombre: str) -> str:
    if not nombre or df.empty or columna_nombre not in df.columns or columna_dni not in df.columns:
        return ""
    serie_nombre = serie_columna(df, columna_nombre)
    base = df[serie_nombre.eq(str(nombre).strip())]
    if base.empty:
        return ""
    valor = base.iloc[0].get(columna_dni, "")
    return limpiar_texto(valor).replace(".0", "")


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
    dni_sin_punto = dni_original.replace(".0", "")
    if not dni_original:
        errores.append("❌ El DNI es obligatorio.")
    elif not dni_sin_punto.isdigit():
        errores.append("❌ El DNI solo debe contener números.")
    elif len(dni_sin_punto) > 8:
        errores.append("❌ El DNI no puede tener más de 8 dígitos.")
    elif len(dni_limpio) != 8:
        errores.append("❌ El DNI debe quedar con exactamente 8 dígitos.")

    correo = limpiar_texto(campos.get("CORREO", ""))
    if correo and not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", correo):
        errores.append("❌ El CORREO no tiene un formato válido.")

    region = limpiar_texto(campos.get("REGION", "")).upper()
    if region and region not in ("CENTRAL", "NORORIENTE", "SUR"):
        errores.append("❌ REGIÓN inválida. Solo se permite CENTRAL, NORORIENTE o SUR.")

    contrato = limpiar_texto(campos.get("TIPO DE CONTRATO", "")).upper()
    if contrato and contrato not in ("PLANILLA", "MEDIA PLANILLA"):
        errores.append("❌ Tipo de contrato inválido. Solo se permite PLANILLA o MEDIA PLANILLA.")

    firmado = limpiar_texto(campos.get("CONTRATO FIRMADO", "")).upper()
    if firmado != "SI":
        errores.append("❌ CONTRATO FIRMADO debe quedar en SI para registrar el alta.")

    fecha_alta = campos.get("FECHA DE CREACION USUARIO")
    if fecha_alta and dni_limpio:
        ok, msg = validar_dni_unico_historico(df_colab, dni_limpio, fecha_alta)
        if not ok:
            errores.append(msg)

    return errores


# =========================
# APPEND POR NOMBRE DE COLUMNA
# =========================
def valor_por_columna(headers: list[str], campos: dict) -> list[str]:
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

    # Solo ubicación se lee al cargar. Está cacheada 5 minutos para que el formulario no se frizee.
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

    departamentos = lista_limpia(df_ubi, "DEPARTAMENTO")
    supervisores = lista_limpia(df_ubi, "SUPERVISOR A CARGO FINAL")
    coordinadores = lista_limpia(df_ubi, "COORDINADOR FINAL")

    st.caption("La provincia depende del departamento. Supervisor, coordinador y DNI se leen desde la misma hoja ubicaciones, sin cambiar la lógica original.")

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
        region = st.selectbox("REGIÓN", ["", "CENTRAL", "NORORIENTE", "SUR"], key="alta_region")
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
        tipo_contrato = st.selectbox("TIPO DE CONTRATO", ["PLANILLA", "MEDIA PLANILLA"], key="alta_tipo_contrato")
        hoy_alta = datetime.now(zona_peru).date()
        fecha_creacion = st.date_input(
            "FECHA CREACIÓN USUARIO",
            value=hoy_alta,
            min_value=hoy_alta - timedelta(days=1),
            max_value=hoy_alta + timedelta(days=1),
            key="alta_fecha_creacion",
            help="Solo permite ayer, hoy o mañana."
        )
        contrato_firmado = st.selectbox("CONTRATO FIRMADO", ["SI"], index=0, key="alta_contrato_firmado")

    st.divider()
    st.markdown("**Ubicación y jerarquía**")
    col_u1, col_u2 = st.columns(2)

    with col_u1:
        departamento = st.selectbox("DEPARTAMENTO", [""] + departamentos, key="alta_departamento")

        provincias = []
        if departamento and "DEPARTAMENTO" in df_ubi.columns and "PROVINCIA" in df_ubi.columns:
            df_dep = df_ubi[serie_columna(df_ubi, "DEPARTAMENTO").eq(str(departamento).strip())]
            provincias = lista_limpia(df_dep, "PROVINCIA")

        provincia = st.selectbox("PROVINCIA", [""] + provincias, key="alta_provincia")

        coordinador = st.selectbox("COORDINADOR", [""] + coordinadores, key="alta_coordinador")
        dni_coordinador = buscar_dni_por_nombre(df_ubi, "COORDINADOR FINAL", "DNI COORDINADOR", coordinador)
        st.text_input("DNI COORDINADOR", value=dni_coordinador, disabled=True, key="alta_dni_coordinador")

    with col_u2:
        supervisor = st.selectbox("SUPERVISOR A CARGO", [""] + supervisores, key="alta_supervisor")
        dni_supervisor = buscar_dni_por_nombre(df_ubi, "SUPERVISOR A CARGO FINAL", "DNI SUPERVISOR", supervisor)
        st.text_input("DNI SUPERVISOR", value=dni_supervisor, disabled=True, key="alta_dni_supervisor")

    st.markdown("")
    submit = st.button("Guardar Alta", key="btn_guardar_alta")

    if submit:
        dni_limpio = normalizar_dni(dni)
        celular_limpio = limpiar_celular(celular)
        correo_limpio = limpiar_texto(correo).lower()
        marca_alta = ahora_peru_fecha_hora()

        campos = {
            "FECHA MOV": str(fecha_creacion),
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
            "CORREO": correo_limpio,
            "CORREO (USUARIO SGC/PRONTO)": correo_limpio,
            "ESTADO": "ACTIVO",
            "TIPO DE CONTRATO": tipo_contrato,
            "FECHA DE CREACION USUARIO": str(fecha_creacion),
            "FECHA DE CESE": "",
            "MOTIVO": "",
            "CONTRATO FIRMADO": contrato_firmado,
            "FECHA_ALTA_REGISTRO": marca_alta,
            "FECHA ALTA REGISTRO": marca_alta,
            "FECHA_BAJA_REGISTRO": "",
            "FECHA BAJA REGISTRO": "",
            "USUARIO_ALTA": usuario_actual,
            "USUARIO ALTA": usuario_actual,
            "USUARIO_BAJA": "",
            "USUARIO BAJA": "",
        }

        # Colaboradores se lee SOLO al guardar para validar histórico/duplicados.
        # Así no se congela el formulario mientras llenas campos.
        df_colab = leer_colaboradores(hoja_colaboradores, forzar=True)
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
