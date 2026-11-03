# FIX_FORMULARIO_WOW_TEL_CANAL_SUBCANAL_DEFAULT_20260602
import os
import re
from datetime import datetime, timedelta

import pandas as pd
import pytz
import streamlit as st

from auth import cargar_usuarios
from certificados import validar_certificado_aprobado
from concurrencia import LOCK_ALTAS, intentar_lock_sheet
from zonas import lista_zonas_agrupadas

# Cargos de promotor por canal: a estos cargos (y solo a estos) se les exige
# contrato + DNI en OneDrive y certificado de evaluación aprobado. Supervisor,
# Coordinador y Back office quedan exentos de esta validación documental.
CARGOS_PROMOTOR = {"Promotor D2D - Dealer", "Promotor - D2D", "Promotor OUT - Dealer"}

# Cargos de Supervisor/Coordinador por canal, usados para construir los
# desplegables dinámicos desde colaboradores (ya no desde la hoja ubicaciones).
CARGOS_SUPERVISOR_INDIRECTO = {"Supervisor D2D - Dealer", "Supervisor OUT - Dealer"}
CARGOS_COORDINADOR_INDIRECTO = {"Coordinador D2D - Dealer", "Coordinador OUT - Dealer"}
CARGOS_SUPERVISOR_DIRECTO = {"Supervisor - D2D"}
CARGOS_COORDINADOR_DIRECTO = {"Coordinador - D2D"}
CARGOS_JEFE_DIRECTO = {"JEFE CEX"}

# Únicos dealers que realmente operan OUTBOUND. Confirmado 31/10/2026: el
# resto de Indirecto (Nogales, Interconexión, Multiple Force, Malutech,
# 2Connect) NO debe ni ver la opción OUTBOUND en SUB CANAL, porque usarla por
# error se saltaba la validación obligatoria de documentos/certificado.
DEALERS_CON_OUTBOUND = {"KONECTA SAC", "SALESLAND", "GRUPO CREED SAC"}

# De los dealers OUTBOUND, solo Konecta y Salesland quedan exentos de subir
# contrato/DNI al momento del alta (lo regularizan después). Grupo Creed es
# prioridad alta (junto con Nogales, Interconexión y Multiple Force) y SÍ
# debe subir los documentos desde el alta, aunque su sub canal sea OUTBOUND.
# Confirmado 02/11/2026.
DEALERS_EXENTOS_DOCUMENTOS_OUTBOUND = {"KONECTA SAC", "SALESLAND"}

# Mismos 2 socios que arriba (Konecta y Salesland), pero es un concepto
# aparte: son los únicos que piden Modalidad + Horario Laboral + Horario
# Break al dar de alta a su personal OUTBOUND. Grupo Creed, aunque también
# es OUTBOUND, NO debe mostrar estos campos. Confirmado 03/11/2026.
DEALERS_CON_HORARIO_OUTBOUND = {"KONECTA SAC", "SALESLAND"}

# Carpeta local en el VPS donde se deja una copia del contrato/DNI subidos por
# la web, con la MISMA estructura de carpetas que OneDrive (RAZON SOCIAL /
# CONTRATOS NUEVOS USUARIOS | DNI NUEVOS USUARIOS). Un script en la PC de
# Kevin (ops/sync_vps_to_onedrive.ps1, tarea programada cada 20 min) descarga
# lo nuevo de aquí y lo deja en la carpeta real de OneDrive, para que el
# equipo siga viendo los documentos donde siempre los vio. Confirmado
# 01/11/2026: reemplaza a la sincronización OneDrive -> VPS (ya innecesaria,
# porque ahora el documento se sube directo en el formulario).
RUTA_WEB_UPLOADS_ONEDRIVE = os.getenv("RUTA_WEB_UPLOADS_ONEDRIVE", "/mnt/web_uploads_to_onedrive")

# El nombre de carpeta real en OneDrive (AUDITORIA DEALERS\<...>) no siempre
# es idéntico al valor de RAZON SOCIAL que se guarda en colaboradores/
# usuarios.json (p. ej. ahí dice "GRUPO CREED SAC" pero la carpeta real tiene
# puntos: "GRUPO CREED S.A.C"). Si no se mapea, el script de sincronización
# crea una carpeta nueva y duplicada en vez de usar la que ya existe.
# Confirmado 02/11/2026 tras detectar la carpeta duplicada "GRUPO CREED SAC".
CARPETA_ONEDRIVE_POR_RAZON = {
    "GRUPO CREED SAC": "GRUPO CREED S.A.C",
    "NOGALES HIGH SAC": "NOGALES HIGH S.A.C",
    "MALUTECH S.A.C": "MALUTECH S.A.C.",
    "MALUTECH SAC": "MALUTECH S.A.C.",
}


def carpeta_onedrive_dealer(razon: str) -> str:
    razon_limpia = limpiar_texto(razon).upper()
    return CARPETA_ONEDRIVE_POR_RAZON.get(razon_limpia, razon_limpia)

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
    """
    Normaliza el DNI al formato general: solo dígitos, siempre en 8 posiciones,
    rellenando con ceros a la izquierda si hace falta (p. ej. cuando llega más
    corto porque Google Sheets guardó el número sin el cero inicial).
    Debe dar el mismo resultado aquí y en registro_mod.py para que un mismo DNI
    se reconozca igual entre Alta, Bajas y Edición.
    """
    dni = limpiar_texto(valor).replace(".0", "")
    dni = re.sub(r"\D", "", dni)
    if not dni:
        return ""
    return dni.zfill(8) if len(dni) <= 8 else dni


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

    # Renombrar columnas vacías para evitar conflictos
    cols_renombradas = []
    contador_vacias = 0
    for col in df.columns:
        if str(col).strip() == "":
            contador_vacias += 1
            cols_renombradas.append(f"_COL_VACIA_{contador_vacias}")
        else:
            cols_renombradas.append(col)
    df.columns = cols_renombradas

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


@st.cache_data(ttl=60, show_spinner=False)
def _leer_colaboradores_cached(_hoja_colaboradores):
    valores = _hoja_colaboradores.get_all_values()
    if not valores:
        return pd.DataFrame()
    headers = hacer_columnas_unicas([str(h).strip().upper() for h in valores[0]])
    n = len(headers)
    filas = []
    for fila in valores[1:]:
        fila = list(fila)
        if len(fila) < n:
            fila += [""] * (n - len(fila))
        filas.append(fila[:n])
    df = pd.DataFrame(filas, columns=headers)
    if df.empty:
        return pd.DataFrame()
    return normalizar_columnas(df).fillna("")


def leer_colaboradores(hoja_colaboradores, forzar=False):
    if forzar:
        _leer_colaboradores_cached.clear()
    return _leer_colaboradores_cached(hoja_colaboradores)


def obtener_headers(hoja_colaboradores) -> list[str]:
    # row_values(1) trae solo la fila de cabecera (una llamada liviana). Antes
    # usaba get_all_values(), que descarga TODA la hoja (18,840+ filas) nada
    # más para leer la fila 1 — esto se ejecuta en cada Alta guardada, y era
    # la demora que se notaba al guardar.
    try:
        valores = hoja_colaboradores.row_values(1)
    except Exception:
        return []
    if not valores:
        return []
    return [str(h).strip().upper() for h in valores]


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
    nuevas = [str(c).strip().upper() for c in columnas_requeridas if str(c).strip().upper() and str(c).strip().upper() not in headers_set]

    if nuevas:
        # La grilla del Sheet tiene un límite de columnas propio (ej. 50) que no
        # crece solo al escribir más allá de él: hay que ampliarla primero, o
        # update_cell revienta con "exceeds grid limits" aunque los datos estén
        # bien (visto en producción: Range colaboradores!AY1 exceeds grid limits).
        col_necesario = col_actual + len(nuevas)
        try:
            col_hoja = hoja_colaboradores.col_count
        except Exception:
            col_hoja = col_actual
        if col_necesario > col_hoja:
            hoja_colaboradores.add_cols(col_necesario - col_hoja)

        for col_up in nuevas:
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
    if not nombre or df.empty or columna_nombre not in df.columns:
        return ""
    # Buscar la columna DNI con múltiples alternativas por si el sheet tiene otro nombre
    alternativas_dni = [columna_dni, "DNI FINAL", "DNI", "DNI_SUPERVISOR", "DNI_COORDINADOR"]
    col_dni_real = next((c for c in alternativas_dni if c in df.columns), None)
    if not col_dni_real:
        return ""
    serie_nombre = serie_columna(df, columna_nombre)
    # Comparación insensible a mayúsculas y espacios
    base = df[serie_nombre.str.upper().str.strip().eq(str(nombre).strip().upper())]
    if base.empty:
        return ""
    valor = base.iloc[0][col_dni_real] if col_dni_real in base.columns else ""
    return limpiar_texto(str(valor)).replace(".0", "")


# =========================
# RAZONES / SUPERVISOR-COORDINADOR DINÁMICOS (desde colaboradores, no desde
# la hoja auxiliar ubicaciones)
# =========================
def razones_dinamicas() -> list[str]:
    """Dealers (Indirecto) + WOW TEL (Directo), derivados de usuarios.json en vez
    de una lista fija en código: un dealer nuevo solo necesita su usuario ahí."""
    try:
        usuarios = cargar_usuarios()
    except Exception:
        usuarios = {}
    # activo_comercial (en usuarios.json): si la empresa deja de ser socia, se
    # pone en false en TODAS sus cuentas "dealer" y desaparece de RAZÓN
    # SOCIAL sin tocar código. Si falta el campo (dato viejo) se asume activo,
    # para no ocultar un dealer por un olvido de configuración.
    dealers = sorted({
        str(u.get("razon", "")).strip()
        for u in usuarios.values()
        if str(u.get("rol", "")).strip() == "dealer"
        and str(u.get("razon", "")).strip()
        and bool(u.get("activo_comercial", True))
    } - {"WOW TEL"})  # ej. "atc_alta" es rol=dealer con razon=WOW TEL; sin este
    # descarte, WOW TEL salía duplicado en RAZON SOCIAL (una vez por dealers,
    # otra por el fijo de abajo).
    return dealers + ["WOW TEL"]


def _normalizar_razon(s: str) -> str:
    """Misma normalización que registro_mod.py: ignora mayúsculas y puntuación
    (ej. 'NOGALES HIGH SAC' == 'NOGALES HIGH S.A.C.'), porque la razón social
    no siempre se escribe igual en usuarios.json que en colaboradores."""
    return re.sub(r"\s+", " ", str(s).strip().upper().replace(".", "").replace("-", "")).strip()


def _nombre_completo(row) -> str:
    # SOLO primer nombre + apellido paterno: es el término exacto con el que
    # SIEMPRE se guardó SUPERVISOR/COORDINADOR en colaboradores, en Directo e
    # Indirecto (confirmado contra el histórico real de la hoja: "Flavia
    # Rojas", "Cesar Aguilar", "Johan Ordinola", etc. — nunca nombre compuesto
    # completo ni apellido materno). Usar el campo NOMBRES completo rompía
    # esto apenas la ficha de la persona tenía más de un nombre (ej. "Flavia
    # Lizeth Leonor" salía como "Flavia Lizeth Leonor Rojas" en vez de
    # "Flavia Rojas"). La etiqueta debe quedar igual para un supervisor ya
    # existente y para uno nuevo: no se diferencia caso por caso.
    primer_nombre = limpiar_texto(row.get("NOMBRES", row.get("NOMBRE", ""))).split(" ")[0] if limpiar_texto(row.get("NOMBRES", row.get("NOMBRE", ""))) else ""
    return " ".join([
        primer_nombre,
        limpiar_texto(row.get("APELLIDO PATERNO", "")),
    ]).strip()


def opciones_supervisor_coordinador(
    df_colab: pd.DataFrame,
    cargos: set,
    razon: str = None,
    subcanal: str = None,
    mostrar_dni: bool = True,
) -> list[str]:
    """
    Opciones de colaboradores ACTIVOS cuyo cargo está en `cargos`. Si se pasa
    razon, filtra por esa razón social (un supervisor de un dealer no debe
    ofrecerse al registrar promotores de otro dealer). Si se pasa subcanal,
    prioriza coincidencias de SUB CANAL (p. ej. CEX) antes de caer al resto del
    canal. Indirecto muestra "NOMBRE COMPLETO — DNI" (mostrar_dni=True); Directo
    y CEX muestran solo "NOMBRE COMPLETO" (mostrar_dni=False), igual que hoy.
    """
    if df_colab.empty or "CARGO (ROL)" not in df_colab.columns:
        return []

    df = df_colab.copy()
    if "ESTADO" in df.columns:
        df = df[df["ESTADO"].astype(str).str.strip().str.upper().eq("ACTIVO")]

    # Coincidencia flexible: además del texto exacto en `cargos`, se acepta
    # cualquier CARGO (ROL) que EMPIECE con la misma palabra clave
    # (SUPERVISOR / COORDINADOR / JEFE). Hay registros históricos con cargos
    # distintos a los 4-5 fijos del desplegable actual (ej. variantes "OUT"
    # en vez de "D2D" para Konecta/Grupo Creed/Salesland, o "JEFE CEX" en
    # Directo) que de otro modo quedan fuera y el desplegable sale vacío
    # aunque la persona sí exista. Confirmado 02/11/2026.
    cargo_col = df["CARGO (ROL)"].astype(str).str.strip()
    palabras_clave = {c.split()[0].upper() for c in cargos if c.split()}
    coincide = cargo_col.isin(cargos) | cargo_col.str.upper().apply(
        lambda c: any(c.startswith(p) for p in palabras_clave)
    )
    df = df[coincide]

    if razon and "RAZON SOCIAL" in df.columns:
        razon_norm = _normalizar_razon(razon)
        df = df[df["RAZON SOCIAL"].astype(str).apply(_normalizar_razon).eq(razon_norm)]

    if subcanal and "SUB CANAL" in df.columns:
        df_subcanal = df[df["SUB CANAL"].astype(str).str.strip().str.upper().eq(str(subcanal).strip().upper())]
        if not df_subcanal.empty:
            df = df_subcanal

    # Una misma persona (mismo DNI) puede tener más de una fila ACTIVA con el
    # nombre escrito distinto (mayúsculas/minúsculas, con o sin "ñ") por
    # errores de digitación al registrarla. Si no se filtra, el desplegable
    # ofrece varias "versiones" de la misma persona y cada alta nueva termina
    # guardando un texto distinto para el mismo Supervisor/Coordinador. Se
    # deja solo UNA fila por DNI (la última, es decir la más reciente en la
    # hoja) como fuente del nombre a mostrar. Confirmado 02/11/2026.
    if "DNI" in df.columns:
        df = df[df["DNI"].astype(str).str.strip() != ""]
        df = df.drop_duplicates(subset="DNI", keep="last")

    opciones = []
    for _, row in df.iterrows():
        nombre = _nombre_completo(row)
        if not nombre:
            continue
        dni = limpiar_texto(row.get("DNI", "")).replace(".0", "")
        opciones.append(f"{nombre} — {dni}" if (mostrar_dni and dni) else nombre)
    return sorted(set(opciones))


def dni_de_opcion(opcion: str) -> str:
    if not opcion or "—" not in opcion:
        return ""
    return opcion.rsplit("—", 1)[-1].strip()


def nombre_de_opcion(opcion: str) -> str:
    if not opcion:
        return ""
    if "—" not in opcion:
        return opcion.strip()
    return opcion.rsplit("—", 1)[0].strip()


# =========================
# VALIDACIONES DE NEGOCIO
# =========================
def validar_formulario(campos: dict, df_colab: pd.DataFrame) -> list[str]:
    """Valida completamente un alta antes de escribirla en Google Sheets."""
    errores: list[str] = []

    def vacio(clave: str) -> bool:
        return limpiar_texto(campos.get(clave, "")) == ""

    canal = limpiar_texto(campos.get("CANAL", "")).upper()
    tipo_doc = limpiar_texto(campos.get("TIPO DE DOC", "")).upper()
    cargo_rol_temprano = limpiar_texto(campos.get("CARGO (ROL)", ""))
    # Jerarquía real: Coordinador es el rango más alto (no reporta a nadie),
    # Supervisor reporta a un Coordinador (no a otro Supervisor), y recién
    # Promotor/Agente BO reportan a ambos. Antes se exigían los 4 campos
    # (Supervisor+Coordinador) para CUALQUIER cargo salvo la primerísima vez
    # de cada dealer nuevo; eso rompía la jerarquía (un Coordinador no debe
    # tener que elegir supervisor/coordinador NUNCA, no solo la primera vez)
    # y dejaba huérfano el caso donde ya hay Supervisor pero aún no hay
    # Coordinador. Confirmado 02/11/2026.
    es_coordinador_indirecto = cargo_rol_temprano in CARGOS_COORDINADOR_INDIRECTO
    es_supervisor_indirecto = cargo_rol_temprano in CARGOS_SUPERVISOR_INDIRECTO
    # Directo/CEX/ATC usa un único campo "SUPERVISOR" (Jefe/Supervisor/
    # Coordinador mezclados); ahí se mantiene la excepción solo para el
    # primer registro de ese rango, como antes.
    es_primer_eslabon_directo = cargo_rol_temprano in (
        CARGOS_SUPERVISOR_DIRECTO | CARGOS_COORDINADOR_DIRECTO | CARGOS_JEFE_DIRECTO
    )

    # Campos generales obligatorios
    requeridos = [
        ("RAZON SOCIAL", "Razón social"),
        ("CANAL", "Canal"),
        ("SUB CANAL", "Sub canal"),
        ("REGION", "Región"),
        ("CARGO (ROL)", "Cargo (rol)"),
        ("NOMBRES", "Nombres"),
        ("APELLIDO PATERNO", "Apellido paterno"),
        ("APELLIDO MATERNO", "Apellido materno"),
        ("CELULAR", "Celular"),
        ("TIPO DE DOC", "Tipo de documento"),
        ("DNI", "DNI"),
        ("CORREO", "Correo"),
        ("TIPO DE CONTRATO", "Tipo de contrato"),
        ("FECHA DE CREACION USUARIO", "Fecha de creación usuario"),
        ("CONTRATO FIRMADO", "Contrato firmado"),
    ]

    # Ojo: WOW TEL usa canal D2D/ATC/RETAIL/CEX (nunca el texto literal
    # "VENTAS DIRECTAS"; ese valor fijo va en SUB CANAL). Por eso se compara
    # contra "VENTAS INDIRECTAS" -igual que "es_indirecto" más abajo en este
    # mismo archivo- y no al revés, o WOW TEL siempre caía en el bloque de
    # Dealers (Supervisor a cargo / DNI supervisor / Coordinador) sin poder
    # completarlos nunca, porque esos campos no existen en su formulario.
    if canal == "VENTAS INDIRECTAS":
        requeridos += [
            ("DEPARTAMENTO", "Departamento"),
            ("PROVINCIA", "Provincia"),
            ("ZONA AGRUPADA", "Zona agrupada"),
        ]
        # Si el socio todavía no tiene a NADIE con ese cargo (desplegable
        # vacío), no se le puede exigir elegir uno — se deja continuar sin
        # asignarlo, se completa cuando el socio registre al suyo.
        # Confirmado 02/11/2026.
        if not es_coordinador_indirecto and campos.get("_HAY_COORDINADOR_DISPONIBLE", True):
            # Supervisor Y Promotor/Agente BO necesitan Coordinador.
            requeridos += [
                ("COORDINADOR", "Coordinador"),
                ("DNI COORDINADOR", "DNI coordinador"),
            ]
        if (
            not es_coordinador_indirecto
            and not es_supervisor_indirecto
            and campos.get("_HAY_SUPERVISOR_DISPONIBLE", True)
        ):
            # Solo Promotor/Agente BO necesitan además Supervisor.
            requeridos += [
                ("SUPERVISOR A CARGO", "Supervisor a cargo"),
                ("DNI SUPERVISOR", "DNI supervisor"),
            ]
    else:
        if not es_primer_eslabon_directo and campos.get("_HAY_SUPERVISOR_DIRECTO_DISPONIBLE", True):
            requeridos += [
                ("SUPERVISOR", "Supervisor"),
            ]
        requeridos += [
            ("CAPACITADOR", "Capacitador"),
            ("ORIGEN_INGRESO", "Origen de ingreso"),
            ("FUENTE_INGRESO", "Fuente de ingreso"),
        ]

    for clave, etiqueta in requeridos:
        if vacio(clave):
            errores.append(f"❌ Falta completar: {etiqueta}")

    # DNI: se valida sobre lo que realmente escribió el usuario.
    # NO se rellena con ceros para hacer pasar un DNI corto.
    dni_original = limpiar_texto(campos.get("DNI", "")).replace(".0", "")
    if tipo_doc == "DNI":
        if not dni_original:
            errores.append("❌ El DNI es obligatorio.")
        elif not dni_original.isdigit():
            errores.append("❌ El DNI solo debe contener números.")
        elif len(dni_original) != 8:
            errores.append("❌ El DNI debe tener exactamente 8 dígitos numéricos.")
    elif dni_original and not dni_original.isdigit():
        errores.append("❌ El documento solo debe contener números.")

    # Celular: exactamente 9 dígitos y empieza en 9.
    celular = limpiar_celular(campos.get("CELULAR", ""))
    if not celular:
        errores.append("❌ El CELULAR es obligatorio.")
    elif not celular.isdigit() or len(celular) != 9 or not celular.startswith("9"):
        errores.append("❌ El CELULAR debe tener exactamente 9 dígitos y comenzar con 9.")

    # Correo
    correo = limpiar_texto(campos.get("CORREO", ""))
    if correo and not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", correo):
        errores.append("❌ El CORREO no tiene un formato válido.")

    # Reglas de catálogo
    region = limpiar_texto(campos.get("REGION", "")).upper()
    if region and region not in ("CENTRAL", "NORORIENTE", "SUR"):
        errores.append("❌ REGIÓN inválida. Solo se permite CENTRAL, NORORIENTE o SUR.")

    contrato = limpiar_texto(campos.get("TIPO DE CONTRATO", "")).upper()
    if contrato and contrato not in ("PLANILLA", "MEDIA PLANILLA"):
        errores.append("❌ Tipo de contrato inválido. Solo se permite PLANILLA o MEDIA PLANILLA.")

    firmado = limpiar_texto(campos.get("CONTRATO FIRMADO", "")).upper()
    if firmado != "SI":
        errores.append("❌ CONTRATO FIRMADO debe quedar en SI para registrar el alta.")

    if canal == "VENTAS INDIRECTAS" and limpiar_texto(campos.get("TIPO_GESTION", "")).upper() != "CAMPO":
        errores.append("❌ Para VENTAS INDIRECTAS, TIPO_GESTION debe ser CAMPO.")

    # Histórico/duplicado (DNI activo, fecha de alta vs. última baja) NO se
    # valida aquí: lo hace validar_reingreso justo después, en el bloque de
    # guardado. Antes ambas funciones revisaban lo mismo con textos distintos
    # y el usuario veía dos mensajes de error diferentes para el mismo motivo.
    dni_limpio = normalizar_dni(dni_original)

    # Requisitos documentales: SOLO para cargos de promotor (Supervisor,
    # Coordinador y Agente BO quedan exentos, como se pidió). Se valida solo si
    # el DNI ya tiene el formato correcto, para no duplicar el mismo error.
    # Excepción canal OUT (SUB CANAL = OUTBOUND, ej. Konecta/Salesland/Grupo
    # Creed outbound): no es obligatorio tener contrato/DNI/certificado al
    # momento del alta, hay tolerancia para regularizar y cargarlos después.
    # Confirmado 31/10/2026.
    # El contrato y la copia de DNI ya NO se buscan en OneDrive (el VPS no
    # puede acceder a esa carpeta, que vive en la PC local de cada usuario):
    # ahora se suben directamente en el propio formulario. Esa presencia se
    # valida en mostrar_formulario (archivo_contrato/archivo_dni), no aquí.
    cargo_rol = limpiar_texto(campos.get("CARGO (ROL)", ""))
    es_outbound = limpiar_texto(campos.get("SUB CANAL", "")).upper() == "OUTBOUND"
    if cargo_rol in CARGOS_PROMOTOR and dni_limpio and not es_outbound and not any("DNI debe tener" in e or "DNI solo" in e for e in errores):
        if canal == "VENTAS INDIRECTAS":
            ok_cert, msg_cert = validar_certificado_aprobado(dni_limpio)
            if not ok_cert:
                errores.append(msg_cert)

    return errores


def validar_reingreso(df_colab: pd.DataFrame, dni_limpio: str, fecha_alta) -> tuple[bool, str, bool]:
    """
    Retorna (ok, mensaje_error, es_reingreso).
    - ok=False: bloquear el alta
    - es_reingreso=True: mostrar advertencia de indicadores (no bloquea)
    """
    fecha_alta = parse_fecha(fecha_alta)
    if fecha_alta is None:
        return False, "❌ La FECHA DE CREACION USUARIO no es válida.", False
    if df_colab.empty or "DNI" not in df_colab.columns:
        return True, "", False

    df = df_colab.copy()
    df["DNI_NORM"] = df["DNI"].apply(normalizar_dni)
    encontrados = df[df["DNI_NORM"].eq(dni_limpio)].copy()

    if encontrados.empty:
        return True, "", False  # DNI nuevo, sin histórico

    # Si está ACTIVO → bloquear siempre
    if "ESTADO" in encontrados.columns:
        activos = encontrados[encontrados["ESTADO"].astype(str).str.strip().str.upper().eq("ACTIVO")]
        if not activos.empty:
            det = activos.iloc[0]
            razon = limpiar_texto(det.get("RAZON SOCIAL", ""))
            nombre = " ".join([
                limpiar_texto(det.get("NOMBRES", det.get("NOMBRE", ""))),
                limpiar_texto(det.get("APELLIDO PATERNO", "")),
                limpiar_texto(det.get("APELLIDO MATERNO", "")),
            ]).strip()
            return False, (
                f"❌ DNI {dni_limpio} ya está ACTIVO en la base.\n"
                f"Empresa: {razon} | Nombre: {nombre}\n"
                "No se puede registrar nuevamente mientras esté activo."
            ), False

    # Buscar última fecha de baja/cese
    columnas_baja = ["FECHA DE CESE", "FECHA CESE", "FECHA_BAJA_REGISTRO", "FECHA BAJA REGISTRO"]
    fechas_baja = []
    for _, row in encontrados.iterrows():
        estado_row = limpiar_texto(row.get("ESTADO", "")).upper()
        for col in columnas_baja:
            if col in encontrados.columns:
                f = parse_fecha(row.get(col))
                if f:
                    fechas_baja.append(f)
        if estado_row == "INACTIVO" and "FECHA MOV" in encontrados.columns:
            f_mov = parse_fecha(row.get("FECHA MOV"))
            if f_mov:
                fechas_baja.append(f_mov)

    if fechas_baja:
        ultima_baja = max(fechas_baja)
        # Fecha de alta debe ser MAYOR a fecha de baja
        if fecha_alta <= ultima_baja:
            return False, (
                f"❌ La fecha de alta ({fecha_alta}) debe ser MAYOR "
                f"a la última fecha de baja/cese del DNI {dni_limpio}: {ultima_baja}.\n"
                "No puede ser igual ni menor."
            ), True
        # Es reingreso válido → advertencia (no bloquea)
        return True, "", True

    return True, "", False


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
def mostrar_formulario(hoja_colaboradores, hoja_ubicaciones, hoja_asistencia=None, hoja_locks=None):
    st.markdown("<span class='wow-section-title'>📋 Alta de Vendedores</span>", unsafe_allow_html=True)

    msg_ok_pendiente = st.session_state.get("mensaje_ok")
    msg_warning_pendiente = st.session_state.get("mensaje_sync_warning")

    if msg_ok_pendiente:
        st.success(msg_ok_pendiente if isinstance(msg_ok_pendiente, str) else "✅ Alta registrada correctamente")
        # Limpiar cachés para que aparezca en Presencialidad inmediatamente
        try:
            from asistencia import _leer_asistencia_cached, leer_colaboradores_drive
            _leer_asistencia_cached.clear()
            leer_colaboradores_drive.clear()
            try:
                from registro_mod import _leer_matriz_cached
                _leer_matriz_cached.clear()
            except Exception:
                pass
            import streamlit as _st2
            for _k in ["asis_loaded", "_sync_auto", "asis_estado_sync"]:
                _st2.session_state.pop(_k, None)
        except Exception:
            pass

    if msg_warning_pendiente:
        st.warning(msg_warning_pendiente)

    usuario_actual = st.session_state.get("usuario", "")
    rol = st.session_state.get("rol", "")
    razon_usuario = st.session_state.get("razon", "")
    # Sub canal fijo opcional (ej. usuarios de ATC o de Outbound): si el usuario
    # lo tiene configurado en usuarios.json, el selector de SUB CANAL queda
    # bloqueado en ese valor más abajo, igual que ya se bloquea la razón social.
    subcanal_fijo = limpiar_texto(st.session_state.get("subcanal_fijo", "")).upper()

    # Versión dinámica de llaves: cuando el alta se guarda correctamente,
    # se incrementa y todos los campos vuelven limpios como si se abriera el módulo desde cero.
    version_form = int(st.session_state.get("alta_form_version", 0))
    k = lambda nombre: f"alta_v{version_form}_{nombre}"

    # Solo ubicación se lee al cargar. Está cacheada 5 minutos para que el formulario no se frizee.
    df_ubi = leer_ubicaciones(hoja_ubicaciones)

    if df_ubi.empty:
        st.error("❌ No se pudo leer la hoja de ubicaciones.")
        return

    # Colaboradores también se lee al cargar (cacheado 60s) para alimentar los
    # desplegables de Supervisor/Coordinador desde los registros reales, en vez
    # de la hoja auxiliar 'ubicaciones'. La relectura FORZADA para validar
    # duplicados sigue ocurriendo solo al guardar (más abajo), sin cambios ahí.
    df_colab_ref = leer_colaboradores(hoja_colaboradores)

    razones = razones_dinamicas()

    departamentos = lista_limpia(df_ubi, "DEPARTAMENTO")

    # Aviso controlado: si DEPARTAMENTO viene vacío, el desplegable mostrará
    # "No results". Avisamos para que no parezca un bug del formulario.
    if not departamentos:
        st.warning(
            "⚠️ La columna **DEPARTAMENTO** de la hoja **ubicaciones** viene vacía o con "
            "otro nombre, por eso su desplegable saldrá como 'No results'. "
            "Revisa que exista y tenga datos en la hoja de referencia."
        )

    # Listas adicionales para canal VENTAS DIRECTAS (mismo worksheet ubicaciones).
    # Si la columna no existe, queda lista vacía y se muestra alerta controlada.
    capacitadores = lista_limpia(df_ubi, "CAPACITADOR")
    origenes_ingreso = lista_limpia(df_ubi, "ORIGEN_INGRESO")
    fuentes_ingreso = lista_limpia(df_ubi, "FUENTE_INGRESO")

    st.caption("Dealers → VENTAS INDIRECTAS | WOW TEL → VENTAS DIRECTAS (D2D / ATC / RETAIL / CEX)")

    col_izq, col_der = st.columns(2)

    with col_izq:
        st.markdown("**Datos del colaborador**")
        nombres = st.text_input("NOMBRES", key=k("nombres"))
        apellido_p = st.text_input("APELLIDO PATERNO", key=k("apellido_p"))
        apellido_m = st.text_input("APELLIDO MATERNO", key=k("apellido_m"))
        celular = st.text_input("CELULAR", max_chars=9, key=k("celular"))
        tipo_doc = st.selectbox("TIPO DE DOC", ["DNI", "CPP", "CEX", "OTROS"], key=k("tipo_doc"))
        dni = st.text_input("DNI", max_chars=(8 if tipo_doc == "DNI" else 20), key=k("dni"))
        correo = st.text_input("CORREO (USUARIO SGC/PRONTO)", key=k("correo"))

    with col_der:
        st.markdown("**Datos comerciales**")
        if rol == "backoffice":
            razon = st.selectbox("RAZÓN SOCIAL", [""] + razones, key=k("razon"))
        elif rol == "capacitacion":
            # Academia solo registra en Directo (WOW TEL): queda fija, sin poder
            # elegir un dealer por error.
            razon = "WOW TEL"
            st.text_input("RAZÓN SOCIAL", value=razon, disabled=True, key=k("razon_academia"))
        else:
            razon = razon_usuario
            st.text_input("RAZÓN SOCIAL", value=razon, disabled=True, key=k("razon_dealer"))

        # Regla comercial:
        # - Dealers (MULTIPLE FORCE, INTERCONEXION, NOGALES, GRUPO CREED) → VENTAS INDIRECTAS
        # - WOW TEL → VENTAS DIRECTAS con sus propios canales
        # - "ALL" (razón de admin/capacitación, no es una empresa real) → NO es Dealer;
        #   cae al mismo bloque que backoffice sin razón, con el selector de CANAL libre.
        razon_norm = limpiar_texto(razon).upper()
        ES_WOW_TEL = razon_norm == "WOW TEL"
        ES_DEALER  = bool(razon_norm) and razon_norm != "ALL" and not ES_WOW_TEL

        if ES_DEALER:
            # ── DEALERS INDIRECTOS ──────────────────────────────────────
            canal = "VENTAS INDIRECTAS"
            st.text_input("CANAL", value=canal, disabled=True, key=k("canal_indirecto_fijo"))
            if subcanal_fijo:
                # Usuario de sub canal fijo (ej. Outbound de Konecta/Salesland/
                # Grupo Creed): no puede cambiarlo a VENTAS INDIRECTAS.
                subcanal = subcanal_fijo
                st.text_input("SUB CANAL", value=subcanal, disabled=True, key=k("subcanal_indirecto_fijo"))
            elif razon_norm in DEALERS_CON_OUTBOUND:
                # Konecta, Grupo Creed y Salesland SON Outbound, no "también
                # pueden" ser Outbound: no se ofrece opción de elegir, queda
                # fijo. Confirmado 02/11/2026.
                subcanal = "OUTBOUND"
                st.text_input("SUB CANAL", value=subcanal, disabled=True, key=k("subcanal_indirecto_out_fijo"))
            else:
                # Solo Konecta, Salesland y Grupo Creed operan OUTBOUND. Para el
                # resto de dealers (Nogales, Interconexión, Multiple Force,
                # Malutech, 2Connect) ni siquiera se ofrece la opción, porque
                # usarla por error saltaba la validación de documentos y
                # certificado que para ellos sí es obligatoria.
                subcanal = "VENTAS INDIRECTAS"
                st.text_input("SUB CANAL", value=subcanal, disabled=True, key=k("subcanal_indirecto_sin_out"))
            tipo_gestion = "CAMPO"

        elif ES_WOW_TEL:
            # ── WOW TEL → VENTAS DIRECTAS ──────────────────────────────
            # Mismo patrón que Dealers (arriba): CANAL = categoría amplia fija,
            # SUB CANAL = el canal específico que elige el usuario. Antes estaba
            # al revés (CANAL=D2D/ATC/..., SUB CANAL="VENTAS DIRECTAS" fijo),
            # lo que no calzaba con el histórico ya guardado en la hoja.
            canal = "VENTAS DIRECTAS"
            st.text_input("CANAL", value=canal, disabled=True, key=k("canal_wowtel_display"))
            if subcanal_fijo:
                # Usuario de sub canal fijo (ej. equipo ATC): no puede cambiarlo
                # a D2D/RETAIL/CEX.
                subcanal = subcanal_fijo
                st.text_input("SUB CANAL", value=subcanal, disabled=True, key=k("subcanal_wowtel_fijo"))
            else:
                subcanal = st.selectbox(
                    "SUB CANAL",
                    ["", "D2D", "ATC", "RETAIL", "CEX"],
                    key=k("subcanal_wowtel"),
                )
            tipo_gestion = ""

        else:
            # ── BACKOFFICE SIN RAZÓN SELECCIONADA ──────────────────────
            canal = st.selectbox("CANAL", ["VENTAS INDIRECTAS", "VENTAS DIRECTAS"], key=k("canal"))
            if canal == "VENTAS DIRECTAS":
                subcanal = "VENTAS DIRECTAS"
                st.text_input("SUB CANAL", value=subcanal, disabled=True, key=k("subcanal_directo_fijo"))
                tipo_gestion = ""
            else:
                subcanal = st.selectbox(
                    "SUB CANAL",
                    ["VENTAS INDIRECTAS", "OUTBOUND"],
                    index=0,
                    key=k("subcanal_indirecto_sin_razon"),
                )
                tipo_gestion = "CAMPO"

        # ── REGIÓN ──────────────────────────────────────────────────────
        region = st.selectbox("REGIÓN", ["", "CENTRAL", "NORORIENTE", "SUR"], key=k("region"))

        # ── CARGO (ROL) ─────────────────────────────────────────────────
        # Lista tomada tal cual de la hoja maestra (columna CARGO (ROL)).
        # Dealers (VENTAS INDIRECTAS) → los que llevan sufijo "- Dealer".
        # WOW TEL / Directas → el resto.
        if canal == "VENTAS INDIRECTAS" and limpiar_texto(subcanal).upper() == "OUTBOUND":
            # Konecta / Grupo Creed / Salesland en OUTBOUND: cargos con sufijo
            # "OUT", no "D2D" (son equipos distintos aunque el canal de fondo
            # sea el mismo). Confirmado 02/11/2026.
            opciones_cargo = [
                "",
                "Promotor OUT - Dealer",
                "Supervisor OUT - Dealer",
                "Coordinador OUT - Dealer",
                "Agente BO OUT - Dealer",
            ]
        elif canal == "VENTAS INDIRECTAS":
            opciones_cargo = [
                "",
                "Promotor D2D - Dealer",
                "Supervisor D2D - Dealer",
                "Coordinador D2D - Dealer",
                "Agente BO D2D - Dealer",
            ]
        else:
            opciones_cargo = [
                "",
                "Agente CEX",
                "Promotor - D2D",
                "Coordinador - D2D",
                "JEFE CEX",
                "Supervisor - D2D",
            ]

        cargo = st.selectbox("CARGO (ROL)", opciones_cargo, key=k("cargo"))

        # ── MODALIDAD / HORARIO (solo OUTBOUND de Konecta y Salesland,
        # y solo cuando el cargo es Promotor) ──
        # Confirmado 03/11/2026: únicamente estos 2 socios piden estos 3
        # campos al registrar personal OUTBOUND. Ningún otro dealer (ni
        # siquiera Grupo Creed, que también es OUTBOUND) debe verlos.
        # Además, dentro de Konecta/Salesland, solo aplica al cargo
        # Promotor — Supervisor/Coordinador/Agente BO quedan exentos.
        modalidad = ""
        horario_laboral = ""
        horario_break = ""
        if (
            canal == "VENTAS INDIRECTAS"
            and limpiar_texto(subcanal).upper() == "OUTBOUND"
            and razon_norm in DEALERS_CON_HORARIO_OUTBOUND
            and cargo in CARGOS_PROMOTOR
        ):
            modalidad = st.selectbox(
                "MODALIDAD", ["", "Presencial", "Remoto"], key=k("modalidad_out")
            )
            horario_laboral = st.selectbox(
                "HORARIO LABORAL", ["", "9:00 - 18:00", "10:00 - 19:00"], key=k("horario_laboral_out")
            )
            horario_break = st.selectbox(
                "HORARIO BREAK", ["", "13:30 a 14:30", "14:30 a 15:30"], key=k("horario_break_out")
            )

        # Fijo en PLANILLA para toda gestión, sin excepción (confirmado
        # 31/10/2026) — ya no se ofrece MEDIA PLANILLA como opción.
        tipo_contrato = "PLANILLA"
        st.text_input("TIPO DE CONTRATO", value=tipo_contrato, disabled=True, key=k("tipo_contrato_display"))
        hoy_alta = datetime.now(zona_peru).date()
        fecha_creacion = st.date_input(
            "FECHA CREACIÓN USUARIO",
            value=hoy_alta,
            min_value=hoy_alta - timedelta(days=1),
            max_value=hoy_alta + timedelta(days=3),
            key=k("fecha_creacion"),
            help="Permite ayer, hoy o hasta 3 días hacia adelante (para cubrir fines de semana)."
        )
        contrato_firmado = st.selectbox("CONTRATO FIRMADO", ["SI"], index=0, key=k("contrato_firmado"))

        # ── DATOS ADICIONALES (solo DIRECTAS / WOW TEL) ─────────────────
        supervisor_directo = ""
        capacitador        = ""
        origen_ingreso     = ""
        fuente_ingreso     = ""

        if canal != "VENTAS INDIRECTAS" and canal:
            st.markdown("**Datos adicionales**")
            # Jefe directo dinámico desde colaboradores: en Directo, tanto
            # Supervisor ("Supervisor - D2D") como Coordinador ("Coordinador -
            # D2D") pueden ser el responsable directo del colaborador, así que
            # ambos cargos entran en un solo listado "SUPERVISOR" (a diferencia
            # de Indirecto, que sí distingue supervisor de coordinador en dos
            # campos separados). Para CEX prioriza responsables cuyo propio
            # registro también sea SUB CANAL=CEX.
            opciones_sup_directo = opciones_supervisor_coordinador(
                df_colab_ref, CARGOS_SUPERVISOR_DIRECTO | CARGOS_COORDINADOR_DIRECTO | CARGOS_JEFE_DIRECTO,
                subcanal=subcanal, mostrar_dni=False,
            )
            hay_supervisor_directo_disponible = True
            if opciones_sup_directo:
                supervisor_directo = st.selectbox("SUPERVISOR", [""] + opciones_sup_directo, key=k("supervisor_directo"))
            elif cargo in (CARGOS_SUPERVISOR_DIRECTO | CARGOS_COORDINADOR_DIRECTO | CARGOS_JEFE_DIRECTO):
                supervisor_directo = ""
            else:
                # Sin nadie registrado todavía en este sub canal: se oculta
                # el desplegable vacío y NO se bloquea el alta — no se puede
                # exigir elegir algo que no existe. Confirmado 02/11/2026.
                supervisor_directo = ""
                hay_supervisor_directo_disponible = False
                st.info(
                    f"ℹ️ Todavía no hay ningún Supervisor/Jefe registrado en {subcanal}. "
                    "Puedes continuar sin asignarlo; se podrá completar más adelante."
                )
            capacitador        = st.selectbox("CAPACITADOR",      [""] + capacitadores,        key=k("capacitador"))
            origen_ingreso     = st.selectbox("ORIGEN INGRESO",   [""] + origenes_ingreso,     key=k("origen_ingreso"))
            fuente_ingreso     = st.selectbox("FUENTE INGRESO",   [""] + fuentes_ingreso,      key=k("fuente_ingreso"))

    # =====================================================
    # DOCUMENTOS (solo Promotor Indirecto, fuera de OUTBOUND)
    # =====================================================
    # Reemplaza la validación contra OneDrive (el VPS no puede leer la
    # carpeta local de cada PC): ahora el contrato y la copia de DNI se
    # suben aquí mismo y se guardan en Drive (subir_archivo_drive), igual
    # que ya se hace en Presencialidad (asistencia.py).
    archivo_contrato = None
    archivo_dni = None
    es_outbound_exento = (
        limpiar_texto(subcanal).upper() == "OUTBOUND"
        and razon_norm in DEALERS_EXENTOS_DOCUMENTOS_OUTBOUND
    )
    requiere_documentos = (
        canal == "VENTAS INDIRECTAS"
        and cargo in CARGOS_PROMOTOR
        and not es_outbound_exento
    )
    if requiere_documentos:
        st.divider()
        st.markdown("**Documentos (obligatorio para Promotor)**")
        col_d1, col_d2 = st.columns(2)
        with col_d1:
            archivo_contrato = st.file_uploader("Contrato firmado (PDF)", type=["pdf"], key=k("archivo_contrato"))
        with col_d2:
            archivo_dni = st.file_uploader("Copia de DNI (PDF)", type=["pdf"], key=k("archivo_dni"))

    # =====================================================
    # UBICACIÓN / JERARQUÍA
    # =====================================================
    departamento = ""
    provincia = ""
    coordinador = ""
    dni_coordinador = ""
    zona_agrupada = ""
    hay_coordinador_disponible = True
    hay_supervisor_disponible = True
    hay_supervisor_directo_disponible = True

    if canal == "VENTAS INDIRECTAS":
        # ── DEALERS: jerarquía completa ────────────────────────────────
        st.divider()
        st.markdown("**Ubicación y jerarquía**")
        col_u1, col_u2 = st.columns(2)

        with col_u1:
            departamento = st.selectbox("DEPARTAMENTO", [""] + departamentos, key=k("departamento"))

            provincias = []
            if departamento and "DEPARTAMENTO" in df_ubi.columns and "PROVINCIA" in df_ubi.columns:
                df_dep = df_ubi[serie_columna(df_ubi, "DEPARTAMENTO").str.upper().str.strip().eq(str(departamento).strip().upper())]
                provincias = lista_limpia(df_dep, "PROVINCIA")

            if st.session_state.get(k("provincia"), "") not in [""] + provincias:
                st.session_state[k("provincia")] = ""
            provincia = st.selectbox("PROVINCIA", [""] + provincias, key=k("provincia"))

            df_prov = df_ubi[serie_columna(df_ubi, "PROVINCIA").str.upper().str.strip().eq(str(provincia).strip().upper())]
            distritos = lista_limpia(df_prov, "DISTRITO") if provincia else []
            if st.session_state.get(k("distrito"), "") not in [""] + distritos:
                st.session_state[k("distrito")] = ""
            distrito = st.selectbox("DISTRITO", [""] + distritos, key=k("distrito"))

            # Zona Agrupada: selector dinámico desde el Excel de ubigeos (data/).
            # st.selectbox ya filtra al escribir (ej. "Lima" muestra LIMA NORTE,
            # LIMA SUR, etc.), no requiere un componente aparte.
            zona_agrupada = st.selectbox("ZONA AGRUPADA", [""] + lista_zonas_agrupadas(), key=k("zona_agrupada"))

            # Jerarquía: Coordinador es el rango más alto, no reporta a nadie
            # — no tiene sentido pedirle que se elija un Coordinador a sí
            # mismo. Para cualquier otro cargo (Supervisor, Promotor, Agente
            # BO), sí se pide. Confirmado 02/11/2026.
            coordinador = ""
            dni_coordinador = ""
            hay_coordinador_disponible = True
            if cargo not in CARGOS_COORDINADOR_INDIRECTO:
                # Coordinador dinámico desde colaboradores (cargo "Coordinador
                # D2D - Dealer" / "Coordinador OUT - Dealer", ACTIVO, del
                # mismo dealer), ya no desde ubicaciones.
                opciones_coord = opciones_supervisor_coordinador(df_colab_ref, CARGOS_COORDINADOR_INDIRECTO, razon=razon)
                hay_coordinador_disponible = bool(opciones_coord)
                if opciones_coord:
                    coordinador_sel = st.selectbox("COORDINADOR", [""] + opciones_coord, key=k("coordinador"))
                    coordinador = nombre_de_opcion(coordinador_sel)
                    dni_coordinador = dni_de_opcion(coordinador_sel)
                    st.text_input("DNI COORDINADOR", value=dni_coordinador, disabled=True, key=k("dni_coordinador"))
                elif razon:
                    # No hay ningún Coordinador registrado todavía para este
                    # socio: no tiene sentido mostrar un desplegable vacío
                    # (genera confusión), y TAMPOCO se bloquea el alta — no
                    # se le puede exigir elegir algo que no existe. Avisa y
                    # deja continuar sin Coordinador asignado; se completa
                    # cuando el socio registre el suyo. Confirmado 02/11/2026.
                    st.info(
                        f"ℹ️ {razon} todavía no tiene ningún Coordinador registrado. "
                        "Puedes continuar sin asignarlo; se podrá completar más adelante."
                    )

        with col_u2:
            # Jerarquía: Supervisor reporta a un Coordinador, no a otro
            # Supervisor — por eso Supervisor y Coordinador NO ven este
            # campo, solo lo ve Promotor/Agente BO. Confirmado 02/11/2026.
            supervisor = ""
            dni_supervisor = ""
            hay_supervisor_disponible = True
            if cargo not in (CARGOS_COORDINADOR_INDIRECTO | CARGOS_SUPERVISOR_INDIRECTO):
                # Supervisor dinámico desde colaboradores (cargo "Supervisor
                # D2D - Dealer" / "Supervisor OUT - Dealer", ACTIVO, del mismo
                # dealer), ya no desde ubicaciones.
                opciones_sup = opciones_supervisor_coordinador(df_colab_ref, CARGOS_SUPERVISOR_INDIRECTO, razon=razon)
                hay_supervisor_disponible = bool(opciones_sup)
                if opciones_sup:
                    supervisor_sel = st.selectbox("SUPERVISOR A CARGO", [""] + opciones_sup, key=k("supervisor"))
                    supervisor = nombre_de_opcion(supervisor_sel)
                    dni_supervisor = dni_de_opcion(supervisor_sel)
                    st.text_input("DNI SUPERVISOR", value=dni_supervisor, disabled=True, key=k("dni_supervisor"))
                elif razon:
                    # Igual que con Coordinador: si no hay ningún Supervisor
                    # registrado para este socio, no se bloquea el alta — se
                    # avisa y se deja continuar sin asignarlo. Confirmado
                    # 02/11/2026.
                    st.info(
                        f"ℹ️ {razon} todavía no tiene ningún Supervisor registrado. "
                        "Puedes continuar sin asignarlo; se podrá completar más adelante."
                    )

    else:
        # ── WOW TEL / VENTAS DIRECTAS: solo ubicación ──────────────────
        supervisor     = supervisor_directo
        dni_supervisor = ""
        coordinador    = ""
        dni_coordinador = ""
        distrito       = ""  # se sobreescribe con el selector de abajo

        st.divider()
        st.markdown("**Ubicación**")
        col_u1d, col_u2d = st.columns(2)
        with col_u1d:
            departamento = st.selectbox("DEPARTAMENTO", [""] + departamentos, key=k("departamento_directo"))
            provincias = []
            if departamento and "DEPARTAMENTO" in df_ubi.columns and "PROVINCIA" in df_ubi.columns:
                df_dep = df_ubi[serie_columna(df_ubi, "DEPARTAMENTO").str.upper().str.strip().eq(str(departamento).strip().upper())]
                provincias = lista_limpia(df_dep, "PROVINCIA")
            if st.session_state.get(k("provincia_directo"), "") not in [""] + provincias:
                st.session_state[k("provincia_directo")] = ""
            provincia = st.selectbox("PROVINCIA", [""] + provincias, key=k("provincia_directo"))

            # DISTRITO también para canal directo (antes faltaba y quedaba vacío).
            df_prov_d = df_ubi[serie_columna(df_ubi, "PROVINCIA").str.upper().str.strip().eq(str(provincia).strip().upper())]
            distritos_d = lista_limpia(df_prov_d, "DISTRITO") if provincia else []
            if st.session_state.get(k("distrito_directo"), "") not in [""] + distritos_d:
                st.session_state[k("distrito_directo")] = ""
            distrito = st.selectbox("DISTRITO", [""] + distritos_d, key=k("distrito_directo"))
        with col_u2d:
            st.text_input("SUPERVISOR", value=supervisor_directo, disabled=True, key=k("sup_directo_display"))

    st.markdown("")
    guardando_key = k("guardando_alta")
    if guardando_key not in st.session_state:
        st.session_state[guardando_key] = False
    submit = st.button(
        "Guardar Alta",
        key=k("btn_guardar_alta"),
        disabled=st.session_state[guardando_key],
    )
    if st.session_state[guardando_key] and not submit:
        st.caption("⏳ Procesando el alta anterior, espera un momento...")

    # Mensaje también cerca del botón porque el navegador suele quedarse abajo luego del guardado.
    if msg_ok_pendiente:
        st.success(msg_ok_pendiente if isinstance(msg_ok_pendiente, str) else "✅ Alta registrada correctamente")
        # Limpiar cachés para que aparezca en Presencialidad inmediatamente
        try:
            from asistencia import _leer_asistencia_cached, leer_colaboradores_drive
            _leer_asistencia_cached.clear()
            leer_colaboradores_drive.clear()
            try:
                from registro_mod import _leer_matriz_cached
                _leer_matriz_cached.clear()
            except Exception:
                pass
            import streamlit as _st2
            for _k in ["asis_loaded", "_sync_auto", "asis_estado_sync"]:
                _st2.session_state.pop(_k, None)
        except Exception:
            pass
        st.session_state.pop("mensaje_ok", None)
    if msg_warning_pendiente:
        st.warning(msg_warning_pendiente)
        st.session_state.pop("mensaje_sync_warning", None)

    if submit:
        st.session_state[guardando_key] = True
        dni_limpio = normalizar_dni(dni)
        celular_limpio = limpiar_celular(celular)
        correo_limpio = limpiar_texto(correo).lower()
        marca_alta = ahora_peru_fecha_hora()

        es_indirecto = canal == "VENTAS INDIRECTAS"

        campos = {
            "FECHA MOV": "",
            "RAZON SOCIAL": razon,
            "CANAL": limpiar_texto(canal),
            "SUB CANAL": limpiar_texto(subcanal),
            "TIPO_GESTION": limpiar_texto(tipo_gestion),
            "TIPO GESTION": limpiar_texto(tipo_gestion),
            "REGION": limpiar_texto(region),
            "DEPARTAMENTO": departamento,
            "PROVINCIA": provincia,
            "DISTRITO": limpiar_texto(distrito),
            "ZONA AGRUPADA": limpiar_texto(zona_agrupada) if es_indirecto else "",
            # ─── SUPERVISOR ────────────────────────────────────────────────
            # INDIRECTAS (Dealers) → SUPERVISOR A CARGO / SUPERVISOR A CARGO FINAL
            # DIRECTAS y WOW TEL   → SUPERVISOR
            "SUPERVISOR A CARGO":       limpiar_texto(supervisor)        if es_indirecto else "",
            "SUPERVISOR A CARGO FINAL": limpiar_texto(supervisor)        if es_indirecto else "",
            "SUPERVISOR":               limpiar_texto(supervisor_directo) if not es_indirecto else "",
            "DNI SUPERVISOR":           limpiar_texto(dni_supervisor)     if es_indirecto else "",
            # ─── CAPACITADOR / ORIGEN / FUENTE (solo DIRECTAS / WOW TEL) ──
            "CAPACITADOR":     limpiar_texto(capacitador)     if not es_indirecto else "",
            "ORIGEN_INGRESO":  limpiar_texto(origen_ingreso)  if not es_indirecto else "",
            "ORIGEN INGRESO":  limpiar_texto(origen_ingreso)  if not es_indirecto else "",
            "FUENTE_INGRESO":  limpiar_texto(fuente_ingreso)  if not es_indirecto else "",
            "FUENTE INGRESO":  limpiar_texto(fuente_ingreso)  if not es_indirecto else "",
            # ─── COORDINADOR (solo INDIRECTAS/Dealers) ─────────────────────
            "COORDINADOR":        limpiar_texto(coordinador)    if es_indirecto else "",
            "COORDINADOR FINAL":  limpiar_texto(coordinador)    if es_indirecto else "",
            "DNI COORDINADOR":    dni_coordinador               if es_indirecto else "",
            # ─── MODALIDAD / HORARIO (solo OUTBOUND Konecta/Salesland) ────
            "MODALIDAD":       limpiar_texto(modalidad),
            "HORARIO_LABORAL": limpiar_texto(horario_laboral),
            "HORARIO_BREAK":   limpiar_texto(horario_break),
            # ─── DATOS PERSONALES ───────────────────────────────────────────
            "CARGO (ROL)": cargo,
            "NOMBRES": limpiar_texto(nombres).upper(),
            "APELLIDO PATERNO": limpiar_texto(apellido_p).upper(),
            "APELLIDO MATERNO": limpiar_texto(apellido_m).upper(),
            "CELULAR": celular_limpio,
            "TIPO DE DOC": tipo_doc,
            # El Drive puede conservarlo como número/texto sin cero inicial;
            # la validación de 8 dígitos ya ocurrió antes de llegar aquí.
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
            "URL CONTRATO": "",
            "URL DNI": "",
            # Claves internas (no se guardan como columna real; valor_por_columna
            # solo escribe las que coinciden con un header de la hoja). Le dicen
            # a validar_formulario si el desplegable de Coordinador/Supervisor
            # tenía opciones o estaba vacío porque el socio aún no registra a
            # nadie en ese cargo — en ese caso NO se exige el campo, no se le
            # puede pedir a alguien elegir algo que no existe. Confirmado
            # 02/11/2026.
            "_HAY_COORDINADOR_DISPONIBLE": hay_coordinador_disponible,
            "_HAY_SUPERVISOR_DISPONIBLE": hay_supervisor_disponible,
            "_HAY_SUPERVISOR_DIRECTO_DISPONIBLE": hay_supervisor_directo_disponible,
        }

        # ── DOCUMENTOS: validar que estén subidos antes de pasar a Sheets ──
        if requiere_documentos and (archivo_contrato is None or archivo_dni is None):
            faltantes_doc = []
            if archivo_contrato is None:
                faltantes_doc.append("contrato firmado")
            if archivo_dni is None:
                faltantes_doc.append("copia de DNI")
            st.error(f"❌ Falta subir: {', '.join(faltantes_doc)}.")
            st.session_state[guardando_key] = False
            return

        # ── BLOQUEO DE DUPLICADOS (punto D) ──────────────────────────────────
        # LOCK_ALTAS serializa este bloque entre todas las sesiones del mismo
        # proceso (doble pestaña, dos usuarios atendidos por el mismo servicio).
        # intentar_lock_sheet agrega además un candado en la propia hoja de
        # cálculo para cubrir el caso de dos procesos distintos. Ninguno de los
        # dos reemplaza las validaciones existentes de abajo: las refuerza.
        #
        # El candado de Sheets se toma RECIÉN cuando el alta ya pasó todas las
        # validaciones (justo antes de escribir). Antes se tomaba primero y
        # quedaba una fila de candado en LOCKS_ALTA aunque el alta fallara por
        # un campo faltante; si el usuario corregía y volvía a guardar el mismo
        # DNI dentro de los 30s del TTL, chocaba con su propia fila anterior y
        # veía "Otro registro... se está procesando" sin que nadie más
        # estuviera registrando ese DNI.
        with LOCK_ALTAS:
            # Colaboradores se lee SOLO al guardar para validar histórico/duplicados.
            # Así no se congela el formulario mientras llenas campos.
            df_colab = leer_colaboradores(hoja_colaboradores, forzar=True)
            errores = validar_formulario(campos, df_colab)

            # Validar reingreso (bloqueo + popup advertencia)
            dni_limpio = normalizar_dni(limpiar_texto(campos.get("DNI", "")))
            fecha_alta = campos.get("FECHA DE CREACION USUARIO")
            ok_reingreso, msg_reingreso, es_reingreso = validar_reingreso(df_colab, dni_limpio, fecha_alta)

            if not ok_reingreso:
                errores.append(msg_reingreso)

            if errores:
                for err in errores:
                    st.error(err)
                st.session_state[guardando_key] = False
                return

            ok_lock, motivo_lock = intentar_lock_sheet(hoja_locks, dni_limpio, usuario_actual)
            if not ok_lock:
                st.error(f"⚠️ {motivo_lock}")
                st.session_state[guardando_key] = False
                return

            # Popup de advertencia de reingreso (no bloquea, solo advierte)
            if es_reingreso and not ok_reingreso is False:
                st.warning(
                    f"⚠️ **REINGRESO DETECTADO** — DNI: {dni_limpio}\n\n"
                    "**Por favor, revisar urgentemente el resultado de indicadores "
                    "de calidad y productividad en los últimos 6 meses:**\n\n"
                    "• BN2 / BN3 (Buena Nota)\n"
                    "• Productividad venta cero\n"
                    "• Indicadores de actividad y cumplimiento\n\n"
                    "Si los indicadores no califican, rechazar el alta antes de confirmar."
                )

            # Guardar documentos directo en el VPS, con la misma estructura de
            # carpetas que OneDrive (RAZON SOCIAL / CONTRATOS NUEVOS USUARIOS
            # y DNI NUEVOS USUARIOS). El script de sincronización inversa
            # (ops/sync_vps_to_onedrive.ps1, cada 20 min) los lleva de vuelta
            # a la carpeta real de OneDrive del socio — ahí quedan, no en
            # Google Drive (se sacó: las cuentas de servicio de Google no
            # tienen cuota de almacenamiento propia y la subida fallaba con
            # "storageQuotaExceeded"). Confirmado 02/11/2026.
            if requiere_documentos:
                razon_carpeta = carpeta_onedrive_dealer(campos.get("RAZON SOCIAL", "")) or "SIN_RAZON"
                try:
                    nombre_doc = f"{dni_limpio} - {campos.get('NOMBRES','')} {campos.get('APELLIDO PATERNO','')}".strip()
                    carpeta_contrato = os.path.join(RUTA_WEB_UPLOADS_ONEDRIVE, razon_carpeta, "CONTRATOS NUEVOS USUARIOS")
                    carpeta_dni = os.path.join(RUTA_WEB_UPLOADS_ONEDRIVE, razon_carpeta, "DNI NUEVOS USUARIOS")
                    os.makedirs(carpeta_contrato, exist_ok=True)
                    os.makedirs(carpeta_dni, exist_ok=True)
                    with open(os.path.join(carpeta_contrato, f"{nombre_doc}.pdf"), "wb") as fh:
                        fh.write(archivo_contrato.getvalue())
                    with open(os.path.join(carpeta_dni, f"{nombre_doc}.pdf"), "wb") as fh:
                        fh.write(archivo_dni.getvalue())
                    campos["URL CONTRATO"] = f"OneDrive: {razon_carpeta}/CONTRATOS NUEVOS USUARIOS/{nombre_doc}.pdf"
                    campos["URL DNI"] = f"OneDrive: {razon_carpeta}/DNI NUEVOS USUARIOS/{nombre_doc}.pdf"
                except Exception as e:
                    st.error(f"❌ No se pudo guardar el contrato/DNI: {e}. Vuelve a intentarlo.")
                    st.session_state[guardando_key] = False
                    return

            try:
                columnas_nuevas = [
                    "TIPO_GESTION",
                    "SUPERVISOR",
                    "CAPACITADOR",
                    "ORIGEN_INGRESO",
                    "FUENTE_INGRESO",
                    "ZONA AGRUPADA",
                    "URL CONTRATO",
                    "URL DNI",
                    "MODALIDAD",
                    "HORARIO_LABORAL",
                    "HORARIO_BREAK",
                ]
                headers = asegurar_columnas_colaboradores(hoja_colaboradores, columnas_nuevas)
                if not headers:
                    st.error("❌ La hoja colaboradores no tiene cabecera. No se puede registrar.")
                    return

                fila = valor_por_columna(headers, campos)
                hoja_colaboradores.append_row(fila, value_input_option="USER_ENTERED")
                # Solo invalida el cache (no lo vuelve a descargar aquí): forzar=True
                # releía inmediatamente las 18,840+ filas de colaboradores una SEGUNDA
                # vez en el mismo guardado (la primera es la de la validación, arriba),
                # haciendo esperar al usuario por una descarga completa que no hacía
                # falta en ese momento — el próximo que lea colaboradores ya la trae
                # fresca por el cache vacío.
                _leer_colaboradores_cached.clear()
                # Limpiar cache de jerarquía para actualización inmediata
                try:
                    from registro_mod import _leer_matriz_cached
                    _leer_matriz_cached.clear()
                except Exception:
                    pass

                if hoja_asistencia is not None:
                    try:
                        # No se ejecuta Sincronizar mes completo aquí porque eso lee toda la base
                        # y hacía lento el alta. Solo se intenta agregar este DNI al periodo actual
                        # de Presencialidad, sin tocar marcajes existentes.
                        from asistencia import registrar_alta_en_asistencia
                        estado_pres = registrar_alta_en_asistencia(hoja_asistencia, campos)
                        st.session_state["mensaje_ok"] = f"✅ Alta registrada correctamente. {estado_pres}"
                    except Exception as e_sync:
                        st.session_state["mensaje_ok"] = "✅ Alta registrada correctamente. Aparecerá en Presencialidad automáticamente."
                        st.session_state["mensaje_sync_warning"] = f"⚠️ No se pudo actualizar presencialidad en automático: {e_sync}"
                else:
                    st.session_state["mensaje_ok"] = "✅ Alta registrada correctamente. Aparecerá en Presencialidad automáticamente."

                # Fuerza que el próximo render use llaves nuevas y todos los campos queden en blanco.
                st.session_state["alta_form_version"] = int(st.session_state.get("alta_form_version", 0)) + 1
                limpiar_form()
                st.rerun()
            except Exception as e:
                st.session_state[guardando_key] = False
                st.error(f"❌ Error al registrar el alta: {e}")
