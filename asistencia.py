"""
asistencia.py — Presencialidad Dealer
Cambios aplicados:
  1. Módulo visible como Presencialidad Dealer desde app_maestra_vendedores.py.
  2. Filtros: Razón Social, Supervisor, Coordinador, Departamento y Provincia.
  3. La hoja Asistencia conserva histórico mensual y no borra registros anteriores.
  4. Sincroniza activos y también inactivos con cese dentro del mes para respetar historia.
  5. Solo permite editar el día actual. No permite modificar días anteriores ni futuros.
  6. Si un colaborador está inactivo, solo permite marcar hasta su fecha de cese.
  7. Marcajes permitidos: A, A-BM, A-VAC, NA-SA y NA-CA.
  8. Si la hoja tiene cabecera descuadrada, NO agrega columnas al final: obliga a recrear estructura para evitar mazamorra.
"""

import calendar
import os
import time
import pytz
from datetime import datetime, date

import pandas as pd
import streamlit as st
from sheets import subir_archivo_drive, obtener_o_crear_worksheet

# =====================================================
# CONSTANTES
# =====================================================
COLUMNAS_BASE = [
    "RAZON SOCIAL",
    "SUPERVISOR",
    "COORDINADOR",
    "DEPARTAMENTO",
    "PROVINCIA",
    "DNI",
    "NOMBRE",
    "ESTADO",
    "FECHA_ALTA",
    "FECHA_CESE",
    "MES",
    "PERIODO",
]
COLUMNAS_DIAS = [f"DIA_{i}" for i in range(1, 32)]
COLUMNAS_ASISTENCIA = COLUMNAS_BASE + COLUMNAS_DIAS

COLUMNAS_FIJAS_EDITOR = [
    "RAZON SOCIAL",
    "DNI",
    "NOMBRE",
    "SUPERVISOR",
    "COORDINADOR",
    "DEPARTAMENTO",
    "PROVINCIA",
    "ESTADO",
    "FECHA_ALTA",
    "FECHA_CESE",
    "MES",
    "PERIODO",
]

KEY_DF_TOTAL = "asis_df_total_cache"
KEY_DF_ORIGINAL = "asis_df_original_cache"
KEY_HEADERS = "asis_headers_cache"
KEY_LOADED = "asis_loaded"
KEY_LOAD_TS = "asis_load_timestamp"

CACHE_TTL = 600
# Mantener la vista amplia original. Solo pagina si realmente supera este límite.
MAX_FILAS_EDITOR = 300

MARCAS_PRESENCIALIDAD = ["", "A", "A-BM", "A-VAC", "NA-SA", "NA-CA"]
LEYENDA_MARCAS = {
    "A": "Asistió",
    "A-BM": "No Asistió por Baja Médica",
    "A-VAC": "No Asistió por Vacaciones",
    "NA-SA": "No Asistió - Sin aviso",
    "NA-CA": "No Asistió - Con aviso",
}

COLUMNAS_SUSTENTOS_BM = [
    "PERIODO",
    "FECHA_ASISTENCIA",
    "DNI",
    "NOMBRE",
    "RAZON SOCIAL",
    "MOTIVO",
    "LINK_DOCUMENTO",
    "FECHA_SUBIDA",
    "USUARIO_REGISTRO",
]

KEY_SUSTENTOS_PENDIENTES = "sustentos_bm_pendientes"

# =====================================================
# UTILIDADES
# =====================================================
def normalizar_columnas(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = df.columns.astype(str).str.strip().str.upper()
    return df


def limpiar_texto(valor) -> str:
    if pd.isna(valor) if not isinstance(valor, str) else False:
        return ""
    s = str(valor).strip()
    return "" if s.upper() in ("NONE", "NAN", "NULL") else s




def primer_valor(*valores) -> str:
    """Devuelve el primer valor no vacío.

    Se usa para priorizar SUPERVISOR A CARGO en indirectas y SUPERVISOR en directas
    sin romper la sincronización de Presencialidad.
    """
    for valor in valores:
        limpio = limpiar_texto(valor)
        if limpio:
            return limpio
    return ""

def limpiar_marca(valor) -> str:
    v = limpiar_texto(valor).upper()
    return v if v in ("A", "A-BM", "A-VAC", "NA-SA", "NA-CA") else ""


def normalizar_dni(valor) -> str:
    dni = limpiar_texto(valor).replace(".0", "")
    if dni.isdigit() and len(dni) < 8:
        dni = dni.zfill(8)
    return dni


def fecha_key(valor) -> str:
    """Devuelve fecha normalizada YYYY-MM-DD para usarla como parte de la llave."""
    f = parse_fecha(valor)
    return str(f) if f else ""


def clave_asistencia(dni, fecha_alta) -> str:
    """Llave real de asistencia: DNI + FECHA_ALTA.

    Esto permite que un DNI dado de baja y reingresado en el mismo mes tenga
    su nueva fila sin chocar con el registro histórico anterior.
    """
    return f"{normalizar_dni(dni)}|{fecha_key(fecha_alta)}"


def parse_fecha(valor):
    if valor in (None, ""):
        return None
    try:
        f = pd.to_datetime(valor, errors="coerce")
        if pd.isna(f):
            return None
        return f.date()
    except Exception:
        return None


def periodo_actual() -> str:
    return datetime.now().strftime("%Y-%m")


def mes_actual() -> str:
    return str(datetime.now().month)


def hoy_actual() -> date:
    return datetime.now().date()


def dia_actual() -> int:
    return datetime.now().day


def dias_del_mes_actual() -> list[int]:
    hoy = datetime.now()
    ultimo = calendar.monthrange(hoy.year, hoy.month)[1]
    return list(range(1, ultimo + 1))


def primer_dia_mes_actual() -> date:
    h = hoy_actual()
    return date(h.year, h.month, 1)


def ultimo_dia_mes_actual() -> date:
    h = hoy_actual()
    return date(h.year, h.month, calendar.monthrange(h.year, h.month)[1])


def letra_columna(numero: int) -> str:
    letras = ""
    while numero:
        numero, resto = divmod(numero - 1, 26)
        letras = chr(65 + resto) + letras
    return letras


def es_promotor(row: pd.Series) -> bool:
    for col in ("CARGO (ROL)", "CARGO", "ROL"):
        if col in row.index:
            cargo = limpiar_texto(row.get(col, "")).upper()
            if cargo:
                return "PROMOTOR" in cargo
    return True


def nombre_completo(row: pd.Series) -> str:
    if limpiar_texto(row.get("NOMBRE", "")):
        return limpiar_texto(row.get("NOMBRE", ""))
    partes = [
        limpiar_texto(row.get("NOMBRES", "")),
        limpiar_texto(row.get("APELLIDO PATERNO", "")),
        limpiar_texto(row.get("APELLIDO MATERNO", "")),
    ]
    return " ".join([p for p in partes if p]).strip()


def fila_editable_hoy(row: pd.Series) -> bool:
    hoy = hoy_actual()
    alta = parse_fecha(row.get("FECHA_ALTA"))
    cese = parse_fecha(row.get("FECHA_CESE"))
    estado = limpiar_texto(row.get("ESTADO", "")).upper()

    if alta and hoy < alta:
        return False
    if estado != "ACTIVO":
        return False
    if cese and hoy > cese:
        return False
    return True


# =====================================================
# GOOGLE SHEETS — CABECERA / LECTURA
# =====================================================
def validar_o_crear_cabecera(hoja_asistencia) -> bool:
    valores = hoja_asistencia.get_all_values()

    if not valores:
        hoja_asistencia.append_row(COLUMNAS_ASISTENCIA, value_input_option="USER_ENTERED")
        st.success("✅ Se creó la estructura correcta de la hoja Asistencia / Presencialidad.")
        return True

    headers = [limpiar_texto(x).upper() for x in valores[0]]

    # Regla crítica: NO agregar columnas al final si ya existe una estructura antigua.
    # Eso fue lo que descuadró la base (datos de DNI/nombre en columnas incorrectas).
    if headers != COLUMNAS_ASISTENCIA:
        st.error("❌ La hoja Asistencia tiene una estructura distinta a la esperada. Para evitar duplicados o datos cruzados, no se sincronizará hasta recrear la cabecera.")
        st.warning("Si estás probando de cero, puedes borrar/recrear SOLO la pestaña Asistencia. No borres colaboradores ni ubicaciones.")
        st.markdown("**Estructura correcta:**")
        st.code(" | ".join(COLUMNAS_ASISTENCIA), language="text")

        with st.expander("🧹 Recrear estructura de Asistencia desde la app"):
            st.info("Esto borra únicamente la pestaña Asistencia y crea la cabecera correcta. Luego presiona Sincronizar mes para cargar colaboradores vigentes.")
            confirmar = st.checkbox("Confirmo que deseo borrar SOLO la hoja Asistencia y recrear la cabecera", key="confirm_reset_asistencia")
            if confirmar and st.button("🧹 Borrar Asistencia y crear cabecera", key="btn_reset_asistencia"):
                hoja_asistencia.clear()
                hoja_asistencia.append_row(COLUMNAS_ASISTENCIA, value_input_option="USER_ENTERED")
                for k in [KEY_DF_TOTAL, KEY_DF_ORIGINAL, KEY_HEADERS, KEY_LOADED, KEY_LOAD_TS]:
                    if k in st.session_state:
                        del st.session_state[k]
                st.success("✅ Hoja Asistencia recreada. Ahora presiona Sincronizar mes.")
                st.rerun()
        return False

    return True


def _cabecera_ok_en_headers(headers: list[str]) -> bool:
    if not headers:
        return False
    headers_up = [limpiar_texto(x).upper() for x in headers]
    return all(c in headers_up for c in COLUMNAS_ASISTENCIA)


def validar_cabecera_sin_red(hoja_asistencia) -> bool:
    if st.session_state.get(KEY_LOADED) and _cabecera_ok_en_headers(st.session_state.get(KEY_HEADERS) or []):
        return True
    return validar_o_crear_cabecera(hoja_asistencia)


def leer_asistencia_drive(hoja_asistencia) -> tuple[pd.DataFrame, list[str]]:
    valores = hoja_asistencia.get_all_values()
    if not valores:
        return pd.DataFrame(columns=COLUMNAS_ASISTENCIA), COLUMNAS_ASISTENCIA.copy()

    headers = [limpiar_texto(x).upper() for x in valores[0]]
    data = valores[1:]
    n = len(headers)

    filas = []
    for fila in data:
        fila = list(fila)
        if len(fila) < n:
            fila += [""] * (n - len(fila))
        filas.append(fila[:n])

    df = pd.DataFrame(filas, columns=headers)
    df = normalizar_columnas(df).fillna("").replace("None", "").replace("nan", "")

    for col in COLUMNAS_ASISTENCIA:
        if col not in df.columns:
            df[col] = ""

    df = df[COLUMNAS_ASISTENCIA].copy()
    df["ROW_SHEET"] = df.index + 2

    for col in COLUMNAS_DIAS:
        df[col] = df[col].apply(limpiar_marca)

    df["DNI"] = df["DNI"].apply(normalizar_dni)
    return df, headers


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def leer_colaboradores_drive(_hoja_colaboradores) -> pd.DataFrame:
    try:
        valores = _hoja_colaboradores.get_all_values()
    except Exception as e:
        st.error(f"Error leyendo colaboradores: {e}")
        return pd.DataFrame()

    if not valores:
        return pd.DataFrame()

    headers = [limpiar_texto(x).upper() for x in valores[0]]
    n = len(headers)
    filas = []
    for fila in valores[1:]:
        fila = list(fila)
        if len(fila) < n:
            fila += [""] * (n - len(fila))
        filas.append(fila[:n])

    df = pd.DataFrame(filas, columns=headers)
    if df.empty:
        return df
    df = normalizar_columnas(df).fillna("").replace("None", "")
    if "DNI" in df.columns:
        df["DNI"] = df["DNI"].apply(normalizar_dni)
    return df


# =====================================================
# SINCRONIZACIÓN CON COLABORADORES
# =====================================================
def obtener_promotores_vigentes_mes(df_colab: pd.DataFrame) -> pd.DataFrame:
    if df_colab.empty or "DNI" not in df_colab.columns:
        return pd.DataFrame()

    df = df_colab.copy()
    # Se incluye todo colaborador vigente del mes.
    # No se filtra solo PROMOTOR, porque el alta debe reflejarse en Presencialidad Dealer
    # según el registro creado en colaboradores.
    df["DNI"] = df["DNI"].apply(normalizar_dni)
    df = df[df["DNI"].ne("")].copy()

    inicio_mes = primer_dia_mes_actual()
    fin_mes = ultimo_dia_mes_actual()

    filas = []
    for _, row in df.iterrows():
        estado = limpiar_texto(row.get("ESTADO", "")).upper()
        alta = parse_fecha(row.get("FECHA DE CREACION USUARIO", row.get("FECHA_CREACION_USUARIO", "")))
        cese = parse_fecha(row.get("FECHA DE CESE", row.get("FECHA CESE", "")))

        # Activo: entra si ya inició antes/dentro del mes.
        if estado == "ACTIVO":
            if alta and alta > fin_mes:
                continue
            filas.append(row)
            continue

        # Inactivo: se conserva si estuvo vigente algún día del mes.
        if estado == "INACTIVO":
            if cese and cese >= inicio_mes:
                filas.append(row)
            continue

    if not filas:
        return pd.DataFrame(columns=df.columns)
    return pd.DataFrame(filas)


def construir_payload_base(row: pd.Series) -> dict:
    estado = limpiar_texto(row.get("ESTADO", "")).upper()
    fecha_alta = str(parse_fecha(row.get("FECHA DE CREACION USUARIO", row.get("FECHA_CREACION_USUARIO", ""))) or "")
    # Si vuelve a ACTIVO, no se debe seguir arrastrando una fecha de cese antigua
    # porque bloquearía la marcación de presencialidad.
    fecha_cese = "" if estado == "ACTIVO" else str(parse_fecha(row.get("FECHA DE CESE", row.get("FECHA CESE", ""))) or "")
    return {
        "RAZON SOCIAL": limpiar_texto(row.get("RAZON SOCIAL", "")),
        "SUPERVISOR": primer_valor(row.get("SUPERVISOR A CARGO", ""), row.get("SUPERVISOR", "")),
        "COORDINADOR": limpiar_texto(row.get("COORDINADOR", "")),
        "DEPARTAMENTO": limpiar_texto(row.get("DEPARTAMENTO", "")),
        "PROVINCIA": limpiar_texto(row.get("PROVINCIA", "")),
        "DNI": normalizar_dni(row.get("DNI", "")),
        "NOMBRE": nombre_completo(row),
        "ESTADO": estado,
        "FECHA_ALTA": fecha_alta,
        "FECHA_CESE": fecha_cese,
        "MES": mes_actual(),
        "PERIODO": periodo_actual(),
    }


def sincronizar_mes(hoja_asistencia, hoja_colaboradores) -> tuple[int, int]:
    if not validar_o_crear_cabecera(hoja_asistencia):
        return 0, 0

    periodo = periodo_actual()
    df_asistencia, headers = leer_asistencia_drive(hoja_asistencia)
    # La sincronización SIEMPRE debe ver el estado más reciente de colaboradores
    # (altas/bajas recién hechas), por eso limpiamos su caché antes de leer.
    leer_colaboradores_drive.clear()
    df_colab = leer_colaboradores_drive(hoja_colaboradores)
    df_vigentes = obtener_promotores_vigentes_mes(df_colab)

    if df_vigentes.empty:
        return 0, 0

    mapa_col = {limpiar_texto(col).upper(): idx + 1 for idx, col in enumerate(headers)}

    existentes = {}
    if not df_asistencia.empty:
        df_mes = df_asistencia[df_asistencia["PERIODO"].astype(str).eq(periodo)].copy()
        for _, r in df_mes.iterrows():
            key_reg = clave_asistencia(r.get("DNI", ""), r.get("FECHA_ALTA", ""))
            if key_reg.strip("|"):
                existentes[key_reg] = int(r.get("ROW_SHEET"))

    nuevas = []
    updates = []

    for _, row in df_vigentes.iterrows():
        payload = construir_payload_base(row)
        dni = payload["DNI"]
        if not dni:
            continue

        key_reg = clave_asistencia(dni, payload.get("FECHA_ALTA", ""))

        if key_reg not in existentes:
            fila = {col: "" for col in COLUMNAS_ASISTENCIA}
            fila.update(payload)
            # La fila nueva se arma según el orden REAL de cabeceras de la hoja.
            headers_orden = [limpiar_texto(h).upper() for h in headers]
            nuevas.append([fila.get(col, "") for col in headers_orden])
        else:
            row_sheet = existentes[key_reg]
            # Actualiza datos base del mes sin tocar días ya marcados.
            for col, valor in payload.items():
                if col in mapa_col:
                    updates.append({
                        "range": f"{letra_columna(mapa_col[col])}{row_sheet}",
                        "values": [[valor]],
                    })

    if nuevas:
        for i in range(0, len(nuevas), 500):
            hoja_asistencia.append_rows(nuevas[i:i + 500], value_input_option="USER_ENTERED")
            time.sleep(0.25)

    if updates:
        for i in range(0, len(updates), 100):
            hoja_asistencia.batch_update(updates[i:i + 100], value_input_option="USER_ENTERED")
            if i + 100 < len(updates):
                time.sleep(0.10)

    return len(nuevas), len(updates)


def registrar_alta_en_asistencia(hoja_asistencia, campos: dict) -> str:
    """
    Agrega o actualiza SOLO el alta recién registrada al periodo actual de Presencialidad.

    Llave usada: DNI + FECHA_ALTA. Esto evita el problema de reingresos:
    si el mismo DNI tuvo una baja y vuelve a ingresar en el mismo mes, se crea
    una nueva fila para la nueva alta en lugar de bloquearse por DNI repetido.
    """
    if not validar_o_crear_cabecera(hoja_asistencia):
        return "Presencialidad pendiente: recrea la cabecera o presiona Sincronizar mes."

    valores = hoja_asistencia.get_all_values()
    if not valores:
        hoja_asistencia.append_row(COLUMNAS_ASISTENCIA, value_input_option="USER_ENTERED")
        valores = [COLUMNAS_ASISTENCIA]

    headers = [limpiar_texto(x).upper() for x in valores[0]]
    periodo = periodo_actual()
    dni = normalizar_dni(campos.get("DNI", ""))
    fecha_alta = str(parse_fecha(campos.get("FECHA DE CREACION USUARIO", "")) or "")
    key_nueva = clave_asistencia(dni, fecha_alta)

    if not dni:
        return "Presencialidad pendiente: DNI vacío."

    fila_base = {col: "" for col in COLUMNAS_ASISTENCIA}
    fila_base.update({
        "RAZON SOCIAL": limpiar_texto(campos.get("RAZON SOCIAL", "")),
        "SUPERVISOR": primer_valor(campos.get("SUPERVISOR A CARGO", ""), campos.get("SUPERVISOR", "")),
        "COORDINADOR": limpiar_texto(campos.get("COORDINADOR", "")),
        "DEPARTAMENTO": limpiar_texto(campos.get("DEPARTAMENTO", "")),
        "PROVINCIA": limpiar_texto(campos.get("PROVINCIA", "")),
        "DNI": dni,
        "NOMBRE": " ".join([
            limpiar_texto(campos.get("NOMBRES", "")),
            limpiar_texto(campos.get("APELLIDO PATERNO", "")),
            limpiar_texto(campos.get("APELLIDO MATERNO", "")),
        ]).strip(),
        "ESTADO": "ACTIVO",
        "FECHA_ALTA": fecha_alta,
        "FECHA_CESE": "",
        "MES": mes_actual(),
        "PERIODO": periodo,
    })

    mapa_col = {limpiar_texto(col).upper(): idx + 1 for idx, col in enumerate(headers)}

    # Si ya existe la misma alta exacta, se actualizan datos base y no se duplica.
    try:
        idx_dni = headers.index("DNI")
        idx_periodo = headers.index("PERIODO")
        idx_alta = headers.index("FECHA_ALTA")
        for pos, fila in enumerate(valores[1:], start=2):
            dni_existente = normalizar_dni(fila[idx_dni] if len(fila) > idx_dni else "")
            periodo_existente = limpiar_texto(fila[idx_periodo] if len(fila) > idx_periodo else "")
            alta_existente = fila[idx_alta] if len(fila) > idx_alta else ""
            if periodo_existente == periodo and clave_asistencia(dni_existente, alta_existente) == key_nueva:
                updates = []
                for col, valor in fila_base.items():
                    if col in mapa_col:
                        updates.append({"range": f"{letra_columna(mapa_col[col])}{pos}", "values": [[valor]]})
                if updates:
                    hoja_asistencia.batch_update(updates, value_input_option="USER_ENTERED")
                for k in [KEY_DF_TOTAL, KEY_DF_ORIGINAL, KEY_HEADERS, KEY_LOADED, KEY_LOAD_TS]:
                    if k in st.session_state:
                        del st.session_state[k]
                return "Presencialidad actualizada; el DNI ya existía con la misma fecha de alta y no se duplicó."
    except Exception:
        pass

    hoja_asistencia.append_row([fila_base.get(h, "") for h in headers], value_input_option="USER_ENTERED")

    # Limpia cache local para que al entrar/cambiar a Presencialidad se vea actualizado.
    for k in [KEY_DF_TOTAL, KEY_DF_ORIGINAL, KEY_HEADERS, KEY_LOADED, KEY_LOAD_TS]:
        if k in st.session_state:
            del st.session_state[k]
    return "Presencialidad actualizada con este alta."


# =====================================================
# CACHÉ
# =====================================================
def cache_vencido() -> bool:
    ts = st.session_state.get(KEY_LOAD_TS, 0)
    return (time.time() - ts) > CACHE_TTL


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def _leer_asistencia_cached(_hoja_asistencia):
    """Lee y normaliza la hoja de Asistencia UNA sola vez y la comparte entre
    todas las sesiones (antes cada usuario leía Drive y guardaba 2 copias)."""
    return leer_asistencia_drive(_hoja_asistencia)


def cargar_cache_desde_drive(hoja_asistencia, forzar: bool = False) -> None:
    if not forzar and st.session_state.get(KEY_LOADED) and not cache_vencido():
        return
    if forzar:
        _leer_asistencia_cached.clear()
        st.session_state.pop("asis_estado_sync", None)
    df_total, headers = _leer_asistencia_cached(hoja_asistencia)
    # Una sola copia de trabajo por sesión. El "original" referencia el mismo
    # objeto; el diff de guardado ya hace su propia copia cuando la necesita.
    # Solo mes actual en session_state — ahorra RAM (historia en cache global)
    df_mes_cache = df_total[df_total["PERIODO"].astype(str).eq(periodo_actual())].copy()
    st.session_state[KEY_DF_TOTAL] = df_mes_cache
    st.session_state[KEY_DF_ORIGINAL] = df_mes_cache
    st.session_state[KEY_HEADERS] = headers
    st.session_state[KEY_LOADED] = True
    st.session_state[KEY_LOAD_TS] = time.time()


# =====================================================
# FILTROS
# =====================================================
def lista_opciones(df: pd.DataFrame, columna: str) -> list[str]:
    if df.empty or columna not in df.columns:
        return ["TODOS"]
    valores = (
        df[columna]
        .astype(str)
        .str.strip()
        .replace(["", "None", "NONE", "nan", "NaN", "NULL", "null"], pd.NA)
        .dropna()
        .unique()
        .tolist()
    )
    return ["TODOS"] + sorted([v for v in valores if str(v).strip()])


def aplicar_filtro(df: pd.DataFrame, columna: str, valor: str) -> pd.DataFrame:
    if valor == "TODOS" or columna not in df.columns:
        return df
    return df[df[columna].astype(str).str.strip().eq(valor)].copy()


def filtrar_df(df: pd.DataFrame, razon: str, supervisor: str, coordinador: str, departamento: str, provincia: str, estado: str = "TODOS") -> pd.DataFrame:
    r = df.copy()
    r = aplicar_filtro(r, "RAZON SOCIAL", razon)
    r = aplicar_filtro(r, "SUPERVISOR", supervisor)
    r = aplicar_filtro(r, "COORDINADOR", coordinador)
    r = aplicar_filtro(r, "DEPARTAMENTO", departamento)
    r = aplicar_filtro(r, "PROVINCIA", provincia)
    r = aplicar_filtro(r, "ESTADO", estado)
    return r


# =====================================================
# ESTILOS / ESPEJO
# =====================================================
def estilo_asistencia(valor: str) -> str:
    v = limpiar_marca(valor)
    if v == "A":
        return "background-color:#D4EDDA;color:#155724;font-weight:bold;text-align:center;"
    if v == "A-BM":
        return "background-color:#FFF3CD;color:#7A5A00;font-weight:bold;text-align:center;"
    if v == "A-VAC":
        return "background-color:#E8D8FF;color:#4B0067;font-weight:bold;text-align:center;"
    if v == "NA-SA":
        return "background-color:#F8D7DA;color:#721C24;font-weight:bold;text-align:center;"
    if v == "NA-CA":
        return "background-color:#FFE5CC;color:#8A3D00;font-weight:bold;text-align:center;"
    return "text-align:center;"

def mostrar_espejo_mes(df: pd.DataFrame, dias_validos: list[int]) -> None:
    if df.empty:
        st.info("No hay datos para mostrar.")
        return
    cols_dias_validos = [f"DIA_{d}" for d in dias_validos]
    columnas = COLUMNAS_FIJAS_EDITOR + cols_dias_validos
    for c in columnas:
        if c not in df.columns:
            df[c] = ""
    df_vista = df[columnas].copy()
    styler = df_vista.style.applymap(estilo_asistencia, subset=cols_dias_validos)
    st.dataframe(styler, use_container_width=True, height=400)


# =====================================================
# GUARDADO SOLO DÍA ACTUAL
# =====================================================
def normalizar_para_guardado(df: pd.DataFrame, col_hoy: str) -> pd.DataFrame:
    out = df.copy()
    if "ROW_SHEET" not in out.columns:
        return pd.DataFrame()
    out["ROW_SHEET"] = pd.to_numeric(out["ROW_SHEET"], errors="coerce")
    out = out.dropna(subset=["ROW_SHEET"])
    if out.empty:
        return out
    out["ROW_SHEET"] = out["ROW_SHEET"].astype(int)
    if col_hoy in out.columns:
        out[col_hoy] = out[col_hoy].map(limpiar_marca)
    return out


def preparar_updates(df_editado: pd.DataFrame, df_original: pd.DataFrame, headers: list[str], col_hoy: str) -> list[dict]:
    df_e = normalizar_para_guardado(df_editado, col_hoy)
    df_o = normalizar_para_guardado(df_original, col_hoy)
    if df_e.empty or df_o.empty or col_hoy not in headers:
        return []

    mapa_col = {limpiar_texto(col).upper(): idx + 1 for idx, col in enumerate(headers)}
    col_num = mapa_col.get(col_hoy)
    if not col_num:
        return []

    orig_idx = df_o.drop_duplicates(subset=["ROW_SHEET"], keep="last").set_index("ROW_SHEET")
    updates = []

    for _, row in df_e.iterrows():
        row_sheet = int(row["ROW_SHEET"])
        if row_sheet not in orig_idx.index:
            continue

        nuevo = limpiar_marca(row.get(col_hoy, ""))
        anterior = limpiar_marca(orig_idx.loc[row_sheet].get(col_hoy, ""))
        if nuevo != anterior:
            updates.append({
                "range": f"{letra_columna(col_num)}{row_sheet}",
                "values": [[nuevo]],
            })

    return updates


def actualizar_cache_con_editado(df_editado: pd.DataFrame, col_hoy: str) -> None:
    if KEY_DF_TOTAL not in st.session_state:
        return

    df_editado = normalizar_para_guardado(df_editado, col_hoy)
    if df_editado.empty:
        return

    patch = df_editado[["ROW_SHEET", col_hoy]].drop_duplicates(subset=["ROW_SHEET"], keep="last")
    patch = patch.set_index("ROW_SHEET")

    df_total = st.session_state[KEY_DF_TOTAL].copy()
    df_total["_rk"] = pd.to_numeric(df_total["ROW_SHEET"], errors="coerce")
    mapped = df_total["_rk"].map(patch[col_hoy])
    ok = mapped.notna()
    if ok.any():
        df_total.loc[ok, col_hoy] = mapped[ok].values
    df_total = df_total.drop(columns=["_rk"])

    st.session_state[KEY_DF_TOTAL] = df_total
    st.session_state[KEY_DF_ORIGINAL] = df_total
    st.session_state[KEY_LOAD_TS] = time.time()



# =====================================================
# SUSTENTOS BAJA MÉDICA — HISTÓRICO, NO REEMPLAZA
# =====================================================
def clave_sustento_bm(row_sheet, dni: str) -> str:
    """Llave temporal por fila real + fecha. Evita que un DNI reemplace otro sustento."""
    return f"{periodo_actual()}|{hoy_actual()}|{int(row_sheet)}|{normalizar_dni(dni)}"


def extension_archivo(nombre: str, mime_type: str) -> str:
    ext = os.path.splitext(str(nombre or ""))[1].replace(".", "").lower()
    if ext in ("pdf", "png", "jpg", "jpeg"):
        return ext
    if mime_type == "application/pdf":
        return "pdf"
    if mime_type == "image/png":
        return "png"
    return "jpg"


@st.dialog("📋 Sustento obligatorio para A-BM")
def dialogo_sustento_bm(clave, dni, nombre, razon_social, row_sheet):
    st.write(f"Colaborador: **{nombre}**")
    st.write(f"DNI: **{dni}** · Fila: **{row_sheet}**")
    st.warning("Para registrar **A-BM (No Asistió por Baja Médica)** debes adjuntar PDF o imagen. El registro se guardará como una fila histórica nueva en Sustentos_Bajas.")

    archivo = st.file_uploader(
        "Adjuntar sustento médico",
        type=["pdf", "png", "jpg", "jpeg"],
        key=f"uploader_bm_{clave}",
    )

    c1, c2 = st.columns(2)
    with c1:
        validar = st.button("✅ Validar sustento", use_container_width=True, key=f"btn_val_bm_{clave}")
    with c2:
        cancelar = st.button("Cancelar", use_container_width=True, key=f"btn_cancel_bm_{clave}")

    if validar:
        if archivo is None:
            st.error("❌ Adjunta el sustento para continuar.")
            return
        pendientes = st.session_state.get(KEY_SUSTENTOS_PENDIENTES, {})
        pendientes[clave] = {
            "dni": normalizar_dni(dni),
            "nombre": limpiar_texto(nombre),
            "razon_social": limpiar_texto(razon_social),
            "row_sheet": int(row_sheet),
            "nombre_archivo": archivo.name,
            "mime_type": archivo.type,
            "contenido_bytes": archivo.read(),
            "periodo": periodo_actual(),
            "fecha_asistencia": str(hoy_actual()),
        }
        st.session_state[KEY_SUSTENTOS_PENDIENTES] = pendientes
        st.success("✅ Sustento validado. Ahora presiona Guardar Presencialidad para registrar la marca y el histórico.")
        time.sleep(0.8)
        st.rerun()

    if cancelar:
        st.info("No se validó sustento. Cambia la marca o adjunta el archivo antes de guardar.")


def detectar_abm_sin_sustento(df_editor: pd.DataFrame, df_original: pd.DataFrame, col_hoy: str) -> list[dict]:
    """Devuelve cambios nuevos a A-BM que todavía necesitan sustento."""
    pendientes = st.session_state.get(KEY_SUSTENTOS_PENDIENTES, {})
    if df_editor.empty or col_hoy not in df_editor.columns:
        return []

    orig = normalizar_para_guardado(df_original.copy(), col_hoy)
    if not orig.empty and "ROW_SHEET" in orig.columns:
        orig = orig.drop_duplicates(subset=["ROW_SHEET"], keep="last").set_index("ROW_SHEET")
    else:
        orig = pd.DataFrame()

    faltantes = []
    for _, row in df_editor.iterrows():
        try:
            row_sheet = int(row.get("ROW_SHEET"))
        except Exception:
            continue
        nuevo = limpiar_marca(row.get(col_hoy, ""))
        if nuevo != "A-BM":
            continue
        anterior = ""
        if not orig.empty and row_sheet in orig.index:
            anterior = limpiar_marca(orig.loc[row_sheet].get(col_hoy, ""))
        if anterior == "A-BM":
            continue
        dni = normalizar_dni(row.get("DNI", ""))
        clave = clave_sustento_bm(row_sheet, dni)
        if clave not in pendientes:
            faltantes.append({
                "clave": clave,
                "dni": dni,
                "nombre": limpiar_texto(row.get("NOMBRE", "")),
                "razon_social": limpiar_texto(row.get("RAZON SOCIAL", "")),
                "row_sheet": row_sheet,
            })
    return faltantes


def guardar_sustentos_bm_en_historico(df_editado: pd.DataFrame, col_hoy: str) -> int:
    """Sube todos los sustentos pendientes y los APPEND al log. Nunca limpia ni reemplaza histórico."""
    pendientes = st.session_state.get(KEY_SUSTENTOS_PENDIENTES, {})
    if not pendientes:
        return 0

    editado = normalizar_para_guardado(df_editado.copy(), col_hoy)
    row_sheets_abm = set()
    if not editado.empty and col_hoy in editado.columns:
        row_sheets_abm = set(editado.loc[editado[col_hoy].eq("A-BM"), "ROW_SHEET"].astype(int).tolist())

    hoja_sustentos = obtener_o_crear_worksheet(
        "maestra_vendedores",
        "Sustentos_Bajas",
        COLUMNAS_SUSTENTOS_BM,
    )

    tz_lima = pytz.timezone("America/Lima")
    usuario = st.session_state.get("usuario", "")
    filas = []
    procesadas = []

    for clave, datos in list(pendientes.items()):
        row_sheet = int(datos.get("row_sheet", 0))
        if row_sheet not in row_sheets_abm:
            # Si el usuario cambió la marca a otra opción antes de guardar, no subimos el archivo.
            continue

        dni = normalizar_dni(datos.get("dni", ""))
        ext = extension_archivo(datos.get("nombre_archivo", ""), datos.get("mime_type", ""))
        stamp = datetime.now(tz_lima).strftime("%Y%m%d_%H%M%S")
        nombre_drive = f"sustento_bm_{dni}_{datos.get('fecha_asistencia')}_fila{row_sheet}_{stamp}.{ext}"
        link = subir_archivo_drive(nombre_drive, datos.get("contenido_bytes", b""), datos.get("mime_type", "application/octet-stream"))

        filas.append([
            datos.get("periodo", periodo_actual()),
            datos.get("fecha_asistencia", str(hoy_actual())),
            dni,
            datos.get("nombre", ""),
            datos.get("razon_social", ""),
            "A-BM (No Asistió por Baja Médica)",
            link,
            datetime.now(tz_lima).strftime("%Y-%m-%d %H:%M:%S"),
            usuario,
        ])
        procesadas.append(clave)

    if filas:
        hoja_sustentos.append_rows(filas, value_input_option="USER_ENTERED")

    for clave in procesadas:
        pendientes.pop(clave, None)
    st.session_state[KEY_SUSTENTOS_PENDIENTES] = pendientes
    return len(filas)


def mostrar_log_sustentos_bm(periodo_defecto: str):
    columnas_defecto = COLUMNAS_SUSTENTOS_BM
    hoja_sustentos = obtener_o_crear_worksheet("maestra_vendedores", "Sustentos_Bajas", columnas_defecto)
    datos = hoja_sustentos.get_all_records()
    if not datos:
        st.info("ℹ️ No hay sustentos registrados todavía.")
        return
    df = pd.DataFrame(datos).fillna("")
    df.columns = df.columns.astype(str).str.strip().str.upper()
    if "PERIODO" in df.columns:
        periodos = ["TODOS"] + sorted(df["PERIODO"].astype(str).str.strip().replace("", pd.NA).dropna().unique().tolist(), reverse=True)
        idx = periodos.index(periodo_defecto) if periodo_defecto in periodos else 0
        periodo_sel = st.selectbox("Periodo del log", periodos, index=idx, key="periodo_log_sustentos_bm")
        if periodo_sel != "TODOS":
            df = df[df["PERIODO"].astype(str).eq(periodo_sel)].copy()
    if "FECHA_SUBIDA" in df.columns:
        df = df.sort_values("FECHA_SUBIDA", ascending=False)
    st.caption(f"Sustentos mostrados: **{len(df)}**")
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={"LINK_DOCUMENTO": st.column_config.LinkColumn("LINK_DOCUMENTO")},
    )

# =====================================================
# MAIN
# =====================================================
def mostrar_asistencia(hoja_asistencia, hoja_colaboradores, registro_mod=None, razon=None):
    st.markdown("<span class='wow-section-title'>🗓️ Presencialidad Dealer</span>", unsafe_allow_html=True)

    if not validar_cabecera_sin_red(hoja_asistencia):
        return

    periodo = periodo_actual()
    dias_validos = dias_del_mes_actual()
    hoy_dia = dia_actual()
    col_hoy = f"DIA_{hoy_dia}"

    c1, c2, c3 = st.columns([1.25, 1.15, 5])

    with c1:
        if False and st.button("🔄 Sincronizar mes", key="btn_sync_asistencia"):
            with st.spinner("Sincronizando con colaboradores…"):
                try:
                    nuevos, actualizados = sincronizar_mes(hoja_asistencia, hoja_colaboradores)
                    cargar_cache_desde_drive(hoja_asistencia, forzar=True)
                    st.success(f"✅ Mes sincronizado. Nuevos: {nuevos} | Datos base actualizados: {actualizados}")
                except Exception as e:
                    st.error(f"Error sincronizando: {e}")
                    return

    with c2:
        if False and st.button("♻️ Recargar Drive", key="btn_reload_asistencia"):
            with st.spinner("Recargando desde Drive…"):
                try:
                    cargar_cache_desde_drive(hoja_asistencia, forzar=True)
                    st.success("✅ Datos actualizados.")
                except Exception as e:
                    st.error(f"Error recargando: {e}")
                    return

    with c3:
        st.info(
            f"📅 Periodo: **{periodo}** | Día editable: **{col_hoy}** | "
            "Los días anteriores y futuros quedan bloqueados."
        )

    cargar_cache_desde_drive(hoja_asistencia)

    df_total = st.session_state[KEY_DF_TOTAL].copy()
    df_original = df_total
    headers = st.session_state.get(KEY_HEADERS, COLUMNAS_ASISTENCIA)
    # Historia completa para espejo y BM retroactivo
    df_historico, _ = _leer_asistencia_cached(hoja_asistencia)

    # Auto-sync ESTADO una vez por sesión (no en cada render)
    if not st.session_state.get("asis_estado_sync"):
        try:
            _dc = leer_colaboradores_drive(hoja_colaboradores)
            if not _dc.empty and "DNI" in _dc.columns and "ESTADO" in _dc.columns:
                _dc["DNI"] = _dc["DNI"].apply(normalizar_dni)
                _em = _dc.drop_duplicates("DNI").set_index("DNI")["ESTADO"].to_dict()
                df_total["ESTADO"] = df_total["DNI"].apply(
                    lambda d: _em.get(normalizar_dni(str(d)), "ACTIVO")
                ).str.strip().str.upper()
                # CRÍTICO: guardar de vuelta en session_state
                st.session_state[KEY_DF_TOTAL] = df_total
                st.session_state[KEY_DF_ORIGINAL] = df_total
                del _dc, _em
        except Exception:
            pass
        st.session_state["asis_estado_sync"] = True

    for col in COLUMNAS_ASISTENCIA:
        if col not in df_total.columns:
            df_total[col] = ""

    df_mes = df_total[df_total["PERIODO"].astype(str).eq(periodo)].copy()

    # Restricción por usuario: si el usuario tiene una razón social específica,
    # solo verá esa razón. Si razon = ALL, ve todo.
    razon_usuario = limpiar_texto(razon if razon is not None else st.session_state.get("razon", ""))
    if razon_usuario and razon_usuario.upper() != "ALL" and "RAZON SOCIAL" in df_mes.columns:
        df_mes = df_mes[df_mes["RAZON SOCIAL"].astype(str).str.strip().str.upper().eq(razon_usuario.upper())].copy()

    if df_mes.empty:
        st.warning("⚠️ No hay registros del periodo actual. Presiona **Sincronizar mes**.")
        return

    # =====================================================
    # FILTROS EFICIENTES EN MEMORIA
    # =====================================================
    # Los filtros trabajan contra el caché local. Además están dentro de un form
    # para que cambiar un desplegable NO recargue toda la vista hasta presionar Aplicar filtros.
    op_razon = lista_opciones(df_mes, "RAZON SOCIAL")
    op_supervisor = lista_opciones(df_mes, "SUPERVISOR")
    op_coordinador = lista_opciones(df_mes, "COORDINADOR")
    op_departamento = lista_opciones(df_mes, "DEPARTAMENTO")
    op_provincia = lista_opciones(df_mes, "PROVINCIA")
    op_estado = lista_opciones(df_mes, "ESTADO")

    def _valor_guardado(clave, opciones):
        valor = st.session_state.get(clave, "TODOS")
        return valor if valor in opciones else "TODOS"

    # Botón recargar: fuerza lectura fresca de Drive
    col_reload, col_info = st.columns([1, 4])
    with col_reload:
        if st.button("🔄 Recargar datos Drive", key="btn_recargar_datos_drive"):
            _leer_asistencia_cached.clear()
            leer_colaboradores_drive.clear()
            st.session_state.pop("asis_estado_sync", None)
            st.session_state.pop(KEY_LOADED, None)
            st.rerun()
    with col_info:
        st.caption("Presiona si hiciste cambios en la hoja colaboradores y quieres verlos reflejados aquí inmediatamente.")

    with st.form("form_filtros_presencialidad"):
        f1, f2, f3, f4, f5, f6 = st.columns(6)
        with f1:
            tmp_razon = st.selectbox("Razón Social", op_razon, index=op_razon.index(_valor_guardado("asis_filtro_razon", op_razon)), key="asis_tmp_razon")
        with f2:
            tmp_supervisor = st.selectbox("Supervisor", op_supervisor, index=op_supervisor.index(_valor_guardado("asis_filtro_supervisor", op_supervisor)), key="asis_tmp_supervisor")
        with f3:
            tmp_coord = st.selectbox("Coordinador", op_coordinador, index=op_coordinador.index(_valor_guardado("asis_filtro_coord", op_coordinador)), key="asis_tmp_coord")
        with f4:
            tmp_dep = st.selectbox("Departamento", op_departamento, index=op_departamento.index(_valor_guardado("asis_filtro_dep", op_departamento)), key="asis_tmp_dep")
        with f5:
            tmp_prov = st.selectbox("Provincia", op_provincia, index=op_provincia.index(_valor_guardado("asis_filtro_prov", op_provincia)), key="asis_tmp_prov")
        with f6:
            tmp_estado = st.selectbox("Estado", op_estado, index=op_estado.index(_valor_guardado("asis_filtro_estado", op_estado)), key="asis_tmp_estado")

        aplicar_filtros = st.form_submit_button("🔎 Aplicar filtros", use_container_width=True)

    if aplicar_filtros:
        st.session_state["asis_filtro_razon"] = tmp_razon
        st.session_state["asis_filtro_supervisor"] = tmp_supervisor
        st.session_state["asis_filtro_coord"] = tmp_coord
        st.session_state["asis_filtro_dep"] = tmp_dep
        st.session_state["asis_filtro_prov"] = tmp_prov
        st.session_state["asis_filtro_estado"] = tmp_estado

    filtro_razon = _valor_guardado("asis_filtro_razon", op_razon)
    filtro_supervisor = _valor_guardado("asis_filtro_supervisor", op_supervisor)
    filtro_coord = _valor_guardado("asis_filtro_coord", op_coordinador)
    filtro_dep = _valor_guardado("asis_filtro_dep", op_departamento)
    filtro_prov = _valor_guardado("asis_filtro_prov", op_provincia)
    filtro_estado = _valor_guardado("asis_filtro_estado", op_estado)

    df_filtrado = filtrar_df(df_mes, filtro_razon, filtro_supervisor, filtro_coord, filtro_dep, filtro_prov, filtro_estado)

    if df_filtrado.empty:
        st.warning("No hay registros con los filtros seleccionados.")
        return

    # Editor solo para personas vigentes hoy.
    df_editor_base = df_filtrado[df_filtrado.apply(fila_editable_hoy, axis=1)].copy()
    total_filtrado = len(df_editor_base)

    st.caption(f"Registros editables hoy: **{total_filtrado}** | Registros en espejo mensual: **{len(df_filtrado)}**")

    if df_editor_base.empty:
        st.warning("⚠️ No hay personal vigente para marcar asistencia el día de hoy con los filtros seleccionados.")
    else:
        if total_filtrado > MAX_FILAS_EDITOR:
            st.warning(
                f"⚠️ Hay {total_filtrado} registros editables hoy. Se mantiene el límite de {MAX_FILAS_EDITOR} por vista "
                "para proteger el navegador. Esto NO borra registros; solo pagina la vista cuando supera el límite."
            )
            total_paginas = max(1, -(-total_filtrado // MAX_FILAS_EDITOR))
            pagina = st.selectbox(
                "Bloque de registros (solo divide la vista, no borra nada)",
                list(range(1, total_paginas + 1)),
                index=0,
                key="asis_pagina",
            )
            inicio = (int(pagina) - 1) * MAX_FILAS_EDITOR
            df_editor_base = df_editor_base.iloc[inicio: inicio + MAX_FILAS_EDITOR].copy()
            st.caption(f"Mostrando filas {inicio + 1}–{min(inicio + MAX_FILAS_EDITOR, total_filtrado)} de {total_filtrado}")

        # ======= BM RETROACTIVO: ARRIBA DEL EDITOR =======
        st.divider()
        st.markdown("<span class=\'wow-section-title\'>📋 Cargar Sustento A-BM (cualquier fecha)</span>", unsafe_allow_html=True)
        st.caption("Adjunta documento A-BM para cualquier período y día. Solo se permite A-BM.")
        _col_p, _col_d = st.columns(2)
        with _col_p:
            _periodos = sorted([str(p) for p in df_historico["PERIODO"].unique() if str(p).strip()], reverse=True)
            _per_bm = st.selectbox("📅 Período", _periodos, key="bm_retro_periodo")
        with _col_d:
            _dia_bm = st.selectbox("📆 Día", list(range(1, 32)), key="bm_retro_dia")
        _col_bm = f"DIA_{_dia_bm}"
        _df_bm = df_historico[df_historico["PERIODO"].astype(str).eq(_per_bm)].copy()
        if _col_bm in _df_bm.columns:
            _df_bm = _df_bm[_df_bm[_col_bm].astype(str).str.contains("A-BM", na=False)]
        else:
            _df_bm = pd.DataFrame()
        if filtro_razon and filtro_razon != op_razon[0] and not _df_bm.empty:
            _df_bm = _df_bm[_df_bm.get("RAZON SOCIAL", pd.Series()).astype(str).str.strip().eq(filtro_razon)]
        if _df_bm.empty:
            st.info(f"ℹ️ Sin registros A-BM en {_per_bm} / DÍA {_dia_bm}")
        else:
            st.write(f"**{len(_df_bm)} colaborador(es)** con A-BM")
            for _, _fb in _df_bm.iterrows():
                _dni = normalizar_dni(str(_fb.get("DNI", "")))
                _nom = limpiar_texto(str(_fb.get("NOMBRE", "")))
                _raz = limpiar_texto(str(_fb.get("RAZON SOCIAL", "")))
                with st.expander(f"📎 {_nom} — DNI {_dni} ({_raz})"):
                    _arch = st.file_uploader(f"Sustento: {_nom}", type=["pdf","png","jpg","jpeg"], key=f"bm_{_dni}_{_per_bm}_{_dia_bm}")
                    if st.button("✅ Guardar sustento", key=f"sbm_{_dni}_{_per_bm}_{_dia_bm}"):
                        if not _arch:
                            st.error("❌ Adjunta el documento primero.")
                        else:
                            with st.spinner("⏳ Subiendo..."):
                                try:
                                    _tz = pytz.timezone("America/Lima")
                                    _usr = st.session_state.get("usuario","")
                                    _st = datetime.now(_tz).strftime("%Y%m%d_%H%M%S")
                                    _ext = extension_archivo(_arch.name, _arch.type)
                                    _url = subir_archivo_drive(f"bm_{_dni}_{_per_bm}_d{_dia_bm}_{_st}.{_ext}", _arch.read(), _arch.type)
                                    _hs = obtener_o_crear_worksheet("maestra_vendedores","Sustentos_Bajas",COLUMNAS_SUSTENTOS_BM)
                                    _hs.append_row([_per_bm, f"{_per_bm}-{str(_dia_bm).zfill(2)}", _dni, _nom, _raz,
                                        "A-BM (No Asistió por Baja Médica)", _url,
                                        datetime.now(_tz).strftime("%Y-%m-%d %H:%M:%S"), _usr], value_input_option="USER_ENTERED")
                                    st.success(f"✅ Guardado: {_nom} | {_per_bm}/DÍA {_dia_bm} | [Ver documento]({_url})")
                                except Exception as _e:
                                    st.error(f"❌ Error: {_e}")
        st.divider()
        # ======= FIN BM RETROACTIVO =======

        st.markdown("<span class='wow-section-title'>✏️ Registrar presencialidad de hoy</span>", unsafe_allow_html=True)
        st.info("**Motivos de validación:** A = Asistió · A-BM = No Asistió por Baja Médica · A-VAC = No Asistió por Vacaciones · NA-SA = No Asistió - Sin aviso · NA-CA = No Asistió - Con aviso")
        st.caption(f"Solo está habilitada la columna **{col_hoy}** para personal ACTIVO. Los INACTIVOS quedan visibles en el espejo histórico, pero no se pueden marcar.")

        # OPTIMIZACIÓN: Editor dentro de un form() para evitar rererenderizado en cada clic.
        # Mostrar solo columnas esenciales: RAZON SOCIAL, DNI, NOMBRE, DIA_HOY, ROW_SHEET.
        columnas_editor_min = ["RAZON SOCIAL", "DNI", "NOMBRE", col_hoy, "ROW_SHEET"]
        df_editor_build = df_editor_base[["RAZON SOCIAL", "DNI", "NOMBRE", "ROW_SHEET"] + ([col_hoy] if col_hoy in df_editor_base.columns else [])].copy()
        for col in columnas_editor_min:
            if col not in df_editor_build.columns:
                df_editor_build[col] = ""

        df_editor = df_editor_build[columnas_editor_min].fillna("").replace({"None": "", "nan": ""})
        if col_hoy in df_editor.columns:
            df_editor[col_hoy] = df_editor[col_hoy].apply(limpiar_marca)

        disabled_cols = [col for col in df_editor.columns if col != col_hoy]
        column_config = {
            "ROW_SHEET": st.column_config.NumberColumn("FILA", width="small", disabled=True),
            col_hoy: st.column_config.SelectboxColumn(col_hoy, options=MARCAS_PRESENCIALIDAD, width="small"),
        }

        editado = st.data_editor(
            df_editor,
            use_container_width=True,
            height=min(520, 50 + len(df_editor) * 35),
            hide_index=True,
            disabled=disabled_cols,
            column_config=column_config,
            num_rows="fixed",
            key="editor_presencialidad_dia_actual",
        )

        faltantes_sustento = detectar_abm_sin_sustento(pd.DataFrame(editado).fillna(""), df_original, col_hoy)
        if faltantes_sustento:
            primero = faltantes_sustento[0]
            st.warning(f"⚠️ {len(faltantes_sustento)} A-BM pendiente(s) sin sustento — **{primero['nombre']}** (DNI {primero['dni']})")
            if st.button("📎 Adjuntar sustento A-BM", key="btn_abrir_dialogo_sustento_bm"):
                dialogo_sustento_bm(
                    primero["clave"],
                    primero["dni"],
                    primero["nombre"],
                    primero["razon_social"],
                    primero["row_sheet"],
                )

        guardar_pres = st.button("💾 Guardar Presencialidad", key="btn_guardar_presencialidad", use_container_width=True)

        if guardar_pres:
            with st.spinner("Guardando en Google Drive…"):
                try:
                    df_editado = normalizar_para_guardado(pd.DataFrame(editado).fillna(""), col_hoy)
                    if df_editado.empty or "ROW_SHEET" not in df_editado.columns:
                        st.warning("No se pudo leer la tabla del editor. Recarga la página.")
                    else:
                        faltantes = detectar_abm_sin_sustento(df_editado, df_original, col_hoy)
                        if faltantes:
                            st.error("❌ Hay marcas A-BM sin sustento. Adjunta el archivo antes de guardar presencialidad.")
                            st.stop()

                        sustentos_guardados = guardar_sustentos_bm_en_historico(df_editado, col_hoy)

                        updates = preparar_updates(
                            df_editado=df_editado,
                            df_original=df_original,
                            headers=headers,
                            col_hoy=col_hoy,
                        )
                        if not updates:
                            st.info("ℹ️ No se detectaron cambios para guardar.")
                        else:
                            for i in range(0, len(updates), 100):
                                hoja_asistencia.batch_update(updates[i:i + 100], value_input_option="USER_ENTERED")
                                if i + 100 < len(updates):
                                    time.sleep(0.10)
                            actualizar_cache_con_editado(df_editado, col_hoy)
                            _leer_asistencia_cached.clear()
                            st.session_state["asis_guardado_msg"] = f"✅ Presencialidad guardada. Celdas actualizadas: {len(updates)} | Sustentos BM registrados: {sustentos_guardados}"
                            st.rerun()
                except Exception as e:
                    st.error(f"❌ Error guardando presencialidad: {e}")

    if msg := st.session_state.pop("asis_guardado_msg", None):
        st.success(msg)

    # Espejo mensual completo: muestra todo el mes y mantiene histórico.
    df_total_actual = st.session_state[KEY_DF_TOTAL]
    df_mes_actual = df_total_actual[df_total_actual["PERIODO"].astype(str).eq(periodo)].copy()
    df_espejo = filtrar_df(df_mes_actual, filtro_razon, filtro_supervisor, filtro_coord, filtro_dep, filtro_prov, filtro_estado)

    ver_espejo = st.checkbox("📊 Ver espejo mensual completo", value=False, key="asis_ver_espejo")
    if ver_espejo:
        st.markdown("<span class='wow-section-title'>📊 Espejo mensual completo</span>", unsafe_allow_html=True)
        mostrar_espejo_mes(df_espejo, dias_validos)
    else:
        st.caption("Espejo mensual oculto para mejorar rendimiento. Actívalo solo cuando necesites revisar el mes completo.")

    ver_sustentos = st.checkbox("📋 Ver histórico de sustentos A-BM", value=False, key="asis_ver_log_sustentos_bm")
    if ver_sustentos:
        st.markdown("<span class='wow-section-title'>📋 Histórico de Sustentos de Baja Médica</span>", unsafe_allow_html=True)
        try:
            mostrar_log_sustentos_bm(periodo)
        except Exception as e:
            st.error(f"Error cargando histórico de sustentos: {e}")

    if registro_mod is not None:
        st.divider()
        st.markdown("<span class='wow-section-title'>📋 Matriz de jerarquía</span>", unsafe_allow_html=True)
        try:
            registro_mod.mostrar_tabla(hoja_colaboradores, razon)
        except Exception as e:
            st.warning(f"No se pudo cargar la matriz de jerarquía: {e}")
