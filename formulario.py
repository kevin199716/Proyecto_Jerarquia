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
    conservar = {
        "autenticado", "rol", "razon", "usuario", "user", "pass",
        "mensaje_ok", "mensaje_sync_warning", "alta_form_version",
    }
    for k in list(st.session_state.keys()):
        # Conserva navegación/sidebar y mensajes globales; limpia solo campos del alta.
        if k in conservar or str(k).startswith("nav_"):
            continue
        if str(k).startswith("alta_v"):
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


def asegurar_columnas_colaboradores(hoja_colaboradores, columnas_requeridas: list[str]) -> list[str]:
    """
    Agrega al final de la cabecera solo las columnas nuevas que no existan.
    No reordena ni toca columnas existentes para no chancar la matriz actual.
    Se ejecuta únicamente al guardar alta, no durante el llenado del formulario.
    """
    headers = obtener_headers(hoja_colaboradores)
    if not headers:
        return []

    headers_set = {h.strip().upper() for h in headers}
    col_actual = len(headers)
    for col in columnas_requeridas:
        col_up = str(col).strip().upper()
        if col_up and col_up not in headers_set:
            col_actual += 1
            hoja_colaboradores.update_cell(1, col_actual, col_up)
            headers.append(col_up)
            headers_set.add(col_up)
    return headers


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
    fecha_alta = parse_fecha(fecha_alta)
    if fecha_alta is None:
        return False, "❌ La FECHA DE CREACION USUARIO no es válida."
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

    # Para histórico de reingreso solo se evalúan bajas reales.
    # FECHA MOV NO se llena en altas; se usa únicamente al aplicar baja.
    # Si por datos antiguos existe FECHA MOV en un registro ACTIVO, se ignora.
    columnas_baja_base = [
        "FECHA DE CESE",
        "FECHA CESE",
        "FECHA_BAJA_REGISTRO",
        "FECHA BAJA REGISTRO",
    ]

    fechas_baja = []
    for _, row in encontrados.iterrows():
        estado_row = limpiar_texto(row.get("ESTADO", "")).upper()

        for col in columnas_baja_base:
            if col in encontrados.columns:
                f = parse_fecha(row.get(col))
                if f:
                    fechas_baja.append(f)

        # FECHA MOV solo cuenta como baja si la fila ya está INACTIVA.
        if estado_row == "INACTIVO" and "FECHA MOV" in encontrados.columns:
            f_mov = parse_fecha(row.get("FECHA MOV"))
            if f_mov:
                fechas_baja.append(f_mov)

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

    canal_val = limpiar_texto(campos.get("CANAL", "")).upper()
    requeridos = [
        "RAZON SOCIAL", "CANAL", "SUB CANAL", "REGION", "CARGO (ROL)",
        "NOMBRES", "APELLIDO PATERNO", "CELULAR",
        "TIPO DE DOC", "DNI", "CORREO", "TIPO DE CONTRATO",
        "FECHA DE CREACION USUARIO", "CONTRATO FIRMADO",
    ]

    if canal_val == "VENTAS DIRECTAS":
        requeridos += ["SUPERVISOR", "CAPACITADOR", "ORIGEN_INGRESO", "FUENTE_INGRESO"]
    else:
        requeridos += ["DEPARTAMENTO", "PROVINCIA", "SUPERVISOR A CARGO", "DNI SUPERVISOR", "COORDINADOR", "DNI COORDINADOR"]

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

    if canal_val == "VENTAS DIRECTAS":
        for c in ["SUPERVISOR", "CAPACITADOR", "ORIGEN_INGRESO", "FUENTE_INGRESO"]:
            if limpiar_texto(campos.get(c, "")) == "":
                errores.append(f"❌ Campo obligatorio pendiente para Ventas Directas: {c}")
    elif canal_val == "VENTAS INDIRECTAS":
        if limpiar_texto(campos.get("TIPO_GESTION", "")).upper() != "CAMPO":
            errores.append("❌ Para VENTAS INDIRECTAS, TIPO_GESTION debe ser CAMPO.")

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
        "TIPO GESTION": "TIPO_GESTION",
        "TIPO_GESTIÓN": "TIPO_GESTION",
        "ORIGEN INGRESO": "ORIGEN_INGRESO",
        "FUENTE INGRESO": "FUENTE_INGRESO",
    }

    row = []
    for h in headers:
        col = aliases.get(h, h)
        row.append(limpiar_texto(campos.get(col, "")))
    return row


# =========================
# FORMULARIO
# =========================
def mostrar_formulario(hoja_colaboradores, hoja_ubicaciones, hoja_asistencia=None):
    st.markdown("<span class='wow-section-title'>📋 Alta de Vendedores</span>", unsafe_allow_html=True)

    msg_ok_pendiente = st.session_state.get("mensaje_ok")
    msg_warning_pendiente = st.session_state.get("mensaje_sync_warning")

    if msg_ok_pendiente:
        st.success(msg_ok_pendiente if isinstance(msg_ok_pendiente, str) else "✅ Alta registrada correctamente")

    if msg_warning_pendiente:
        st.warning(msg_warning_pendiente)

    usuario_actual = st.session_state.get("usuario", "")
    rol = st.session_state.get("rol", "")
    razon_usuario = st.session_state.get("razon", "")

    # Versión dinámica de llaves: cuando el alta se guarda correctamente,
    # se incrementa y todos los campos vuelven limpios como si se abriera el módulo desde cero.
    version_form = int(st.session_state.get("alta_form_version", 0))
    k = lambda nombre: f"alta_v{version_form}_{nombre}"

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
        "WOW TEL",
    ]

    departamentos = lista_limpia(df_ubi, "DEPARTAMENTO")
    supervisores = lista_limpia(df_ubi, "SUPERVISOR A CARGO FINAL")
    coordinadores = lista_limpia(df_ubi, "COORDINADOR FINAL")

    # Listas adicionales para canal VENTAS DIRECTAS (mismo worksheet ubicaciones).
    # Si la columna no existe, queda lista vacía y se muestra alerta controlada.
    supervisores_directo = lista_limpia(df_ubi, "SUPERVISOR")
    capacitadores = lista_limpia(df_ubi, "CAPACITADOR")
    origenes_ingreso = lista_limpia(df_ubi, "ORIGEN_INGRESO")
    fuentes_ingreso = lista_limpia(df_ubi, "FUENTE_INGRESO")

    st.caption("Para VENTAS INDIRECTAS se muestra ubicación y jerarquía tradicional. Para VENTAS DIRECTAS solo se habilitan sus campos adicionales; lo demás se oculta visualmente para evitar confusión.")

    col_izq, col_der = st.columns(2)

    with col_izq:
        st.markdown("**Datos del colaborador**")
        nombres = st.text_input("NOMBRES", key=k("nombres"))
        apellido_p = st.text_input("APELLIDO PATERNO", key=k("apellido_p"))
        apellido_m = st.text_input("APELLIDO MATERNO", key=k("apellido_m"))
        celular = st.text_input("CELULAR", max_chars=9, key=k("celular"))
        tipo_doc = st.selectbox("TIPO DE DOC", ["DNI", "CPP", "CEX", "OTROS"], key=k("tipo_doc"))
        dni = st.text_input("DNI", max_chars=8, key=k("dni"))
        correo = st.text_input("CORREO (USUARIO SGC/PRONTO)", key=k("correo"))

    with col_der:
        st.markdown("**Datos comerciales**")
        if rol == "backoffice":
            razon = st.selectbox("RAZÓN SOCIAL", [""] + razones, key=k("razon"))
        else:
            razon = razon_usuario
            st.text_input("RAZÓN SOCIAL", value=razon, disabled=True, key=k("razon_dealer"))

        canal = st.selectbox("CANAL", ["VENTAS INDIRECTAS", "VENTAS DIRECTAS"], key=k("canal"))
        if canal == "VENTAS DIRECTAS":
            subcanal = st.selectbox("SUB CANAL", ["VENTAS DIRECTAS"], key=k("subcanal"))
            tipo_gestion = ""
        else:
            subcanal = st.selectbox("SUB CANAL", ["VENTAS INDIRECTAS", "OUTBOUND"], key=k("subcanal"))
            tipo_gestion = "CAMPO"
        # TIPO_GESTION no se muestra en pantalla.
        # Regla: VENTAS INDIRECTAS viaja como CAMPO; VENTAS DIRECTAS viaja vacío.
        region = st.selectbox("REGIÓN", ["", "CENTRAL", "NORORIENTE", "SUR"], key=k("region"))
        cargo = st.selectbox(
            "CARGO (ROL)",
            [
                "",
                "Agente BO D2D - Dealer",
                "Promotor D2D - Dealer",
                "Supervisor D2D - Dealer",
                "Coordinador D2D - Dealer",
            ],
            key=k("cargo"),
        )
        tipo_contrato = st.selectbox("TIPO DE CONTRATO", ["PLANILLA", "MEDIA PLANILLA"], key=k("tipo_contrato"))
        hoy_alta = datetime.now(zona_peru).date()
        fecha_creacion = st.date_input(
            "FECHA CREACIÓN USUARIO",
            value=hoy_alta,
            min_value=hoy_alta - timedelta(days=1),
            max_value=hoy_alta + timedelta(days=1),
            key=k("fecha_creacion"),
            help="Solo permite ayer, hoy o mañana."
        )
        contrato_firmado = st.selectbox("CONTRATO FIRMADO", ["SI"], index=0, key=k("contrato_firmado"))

        supervisor_directo = ""
        capacitador = ""
        origen_ingreso = ""
        fuente_ingreso = ""
        if canal == "VENTAS DIRECTAS":
            st.markdown("**Datos adicionales Ventas Directas**")
            supervisor_directo = st.selectbox("SUPERVISOR", [""] + supervisores_directo, key=k("supervisor_directo"))
            capacitador = st.selectbox("CAPACITADOR", [""] + capacitadores, key=k("capacitador"))
            origen_ingreso = st.selectbox("ORIGEN INGRESO", [""] + origenes_ingreso, key=k("origen_ingreso"))
            fuente_ingreso = st.selectbox("FUENTE INGRESO", [""] + fuentes_ingreso, key=k("fuente_ingreso"))

    # =====================================================
    # UBICACIÓN / JERARQUÍA
    # =====================================================
    departamento = ""
    provincia = ""
    coordinador = ""
    dni_coordinador = ""

    if canal == "VENTAS INDIRECTAS":
        st.divider()
        st.markdown("**Ubicación y jerarquía**")
        col_u1, col_u2 = st.columns(2)

        with col_u1:
            departamento = st.selectbox("DEPARTAMENTO", [""] + departamentos, key=k("departamento"))

            provincias = []
            if departamento and "DEPARTAMENTO" in df_ubi.columns and "PROVINCIA" in df_ubi.columns:
                df_dep = df_ubi[serie_columna(df_ubi, "DEPARTAMENTO").eq(str(departamento).strip())]
                provincias = lista_limpia(df_dep, "PROVINCIA")

            provincia = st.selectbox("PROVINCIA", [""] + provincias, key=k("provincia"))

            coordinador = st.selectbox("COORDINADOR", [""] + coordinadores, key=k("coordinador"))
            dni_coordinador = buscar_dni_por_nombre(df_ubi, "COORDINADOR FINAL", "DNI COORDINADOR", coordinador)
            st.text_input("DNI COORDINADOR", value=dni_coordinador, disabled=True, key=k("dni_coordinador"))

        with col_u2:
            supervisor = st.selectbox("SUPERVISOR A CARGO", [""] + supervisores, key=k("supervisor"))
            dni_supervisor = buscar_dni_por_nombre(df_ubi, "SUPERVISOR A CARGO FINAL", "DNI SUPERVISOR", supervisor)
            st.text_input("DNI SUPERVISOR", value=dni_supervisor, disabled=True, key=k("dni_supervisor"))
    else:
        # Para VENTAS DIRECTAS se oculta completamente la jerarquía D2D indirecta.
        # El supervisor válido es el de Datos adicionales Ventas Directas.
        supervisor = supervisor_directo
        dni_supervisor = ""

    st.markdown("")
    submit = st.button("Guardar Alta", key=k("btn_guardar_alta"))

    # Mensaje también cerca del botón porque el navegador suele quedarse abajo luego del guardado.
    if msg_ok_pendiente:
        st.success(msg_ok_pendiente if isinstance(msg_ok_pendiente, str) else "✅ Alta registrada correctamente")
        st.session_state.pop("mensaje_ok", None)
    if msg_warning_pendiente:
        st.warning(msg_warning_pendiente)
        st.session_state.pop("mensaje_sync_warning", None)

    if submit:
        dni_limpio = normalizar_dni(dni)
        celular_limpio = limpiar_celular(celular)
        correo_limpio = limpiar_texto(correo).lower()
        marca_alta = ahora_peru_fecha_hora()

        campos = {
            # En ALTA no se marca FECHA MOV.
            # FECHA MOV se actualiza únicamente en BAJAS.
            "FECHA MOV": "",
            "RAZON SOCIAL": razon,
            "CANAL": limpiar_texto(canal),
            "SUB CANAL": limpiar_texto(subcanal),
            "TIPO_GESTION": limpiar_texto(tipo_gestion),
            "TIPO GESTION": limpiar_texto(tipo_gestion),
            "REGION": limpiar_texto(region),
            "DEPARTAMENTO": departamento,
            "PROVINCIA": provincia,
            "SUPERVISOR A CARGO": limpiar_texto(supervisor),
            "SUPERVISOR": limpiar_texto(supervisor),
            "DNI SUPERVISOR": limpiar_texto(dni_supervisor),
            "CAPACITADOR": limpiar_texto(capacitador),
            "ORIGEN_INGRESO": limpiar_texto(origen_ingreso),
            "ORIGEN INGRESO": limpiar_texto(origen_ingreso),
            "FUENTE_INGRESO": limpiar_texto(fuente_ingreso),
            "FUENTE INGRESO": limpiar_texto(fuente_ingreso),
            "COORDINADOR": limpiar_texto(coordinador),
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
            columnas_nuevas = [
                "TIPO_GESTION",
                "SUPERVISOR",
                "CAPACITADOR",
                "ORIGEN_INGRESO",
                "FUENTE_INGRESO",
            ]
            headers = asegurar_columnas_colaboradores(hoja_colaboradores, columnas_nuevas)
            if not headers:
                st.error("❌ La hoja colaboradores no tiene cabecera. No se puede registrar.")
                return

            fila = valor_por_columna(headers, campos)
            hoja_colaboradores.append_row(fila, value_input_option="USER_ENTERED")
            leer_colaboradores(hoja_colaboradores, forzar=True)

            if hoja_asistencia is not None:
                try:
                    # No se ejecuta Sincronizar mes completo aquí porque eso lee toda la base
                    # y hacía lento el alta. Solo se intenta agregar este DNI al periodo actual
                    # de Presencialidad, sin tocar marcajes existentes.
                    from asistencia import registrar_alta_en_asistencia
                    estado_pres = registrar_alta_en_asistencia(hoja_asistencia, campos)
                    st.session_state["mensaje_ok"] = f"✅ Alta registrada correctamente. {estado_pres}"
                except Exception as e_sync:
                    st.session_state["mensaje_ok"] = "✅ Alta registrada correctamente. Para verlo en Presencialidad Dealer, presiona Sincronizar mes."
                    st.session_state["mensaje_sync_warning"] = f"⚠️ No se pudo actualizar presencialidad en automático: {e_sync}"
            else:
                st.session_state["mensaje_ok"] = "✅ Alta registrada correctamente. Para verlo en Presencialidad Dealer, presiona Sincronizar mes."

            # Fuerza que el próximo render use llaves nuevas y todos los campos queden en blanco.
            st.session_state["alta_form_version"] = int(st.session_state.get("alta_form_version", 0)) + 1
            limpiar_form()
            st.rerun()
        except Exception as e:
            st.error(f"❌ Error al registrar el alta: {e}")
