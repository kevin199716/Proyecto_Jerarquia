"""

FIX_QUOTA_NO_AUTO_WRITE_FINAL_20260601
- Este archivo NO escribe en Google Sheets al abrir/refrescar la página.
- Solo escribe al presionar Guardar Presencialidad.
- Evita error Google Sheets quota write_requests per minute.
FIX_VISTA_LIVE_SIN_SINCRONIZAR_NO_BORRA_20260601
FIX_DEALER_NO_BLANCO_RAZON_NORMALIZADA_20260601
FIX_AUTO_UPSERT_SIN_BOTON_NO_DESTRUCTIVO_20260601
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
import time
import re
import unicodedata
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
MAX_FILAS_EDITOR = 200

MARCAS_PRESENCIALIDAD = ["", "A", "A-BM", "A-VAC", "NA-SA", "NA-CA"]
LEYENDA_MARCAS = {
    "A": "Asistió",
    "A-BM": "No Asistió por Baja Médica",
    "A-VAC": "No Asistió por Vacaciones",
    "NA-SA": "No Asistió - Sin aviso",
    "NA-CA": "No Asistió - Con aviso",
}

ZONA_PERU = pytz.timezone("America/Lima")
MARCAS_SOLO_BAJA_MEDICA = ["", "A-BM"]

def ahora_lima() -> datetime:
    return datetime.now(ZONA_PERU)


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


def normalizar_comparacion(valor) -> str:
    """Normaliza texto para comparar razón social, nombres y filtros sin romper visualmente.

    Ejemplo:
    INTERCONEXION 360 S.A.C. == INTERCONEXION 360 SAC
    MULTIPLE  FORCE  SAC == MULTIPLE FORCE SAC
    """
    txt = limpiar_texto(valor).upper()
    if not txt:
        return ""
    txt = unicodedata.normalize("NFKD", txt)
    txt = "".join(ch for ch in txt if not unicodedata.combining(ch))
    txt = re.sub(r"[^A-Z0-9]+", " ", txt)
    txt = re.sub(r"\s+", " ", txt).strip()
    return txt


def filtrar_por_razon_usuario(df: pd.DataFrame, razon_usuario: str) -> pd.DataFrame:
    """Filtro seguro para usuarios de socio/dealer.

    No depende de puntos o dobles espacios en la razón social.
    Si la razón es ALL, retorna todo.
    """
    razon_limpia = limpiar_texto(razon_usuario)
    if df.empty or not razon_limpia or razon_limpia.upper() == "ALL" or "RAZON SOCIAL" not in df.columns:
        return df.copy()

    objetivo = normalizar_comparacion(razon_limpia)
    if not objetivo:
        return df.copy()

    serie_norm = df["RAZON SOCIAL"].apply(normalizar_comparacion)
    filtrado = df[serie_norm.eq(objetivo)].copy()

    # Fallback: por si en Drive quedó con algún texto adicional o formato antiguo.
    if filtrado.empty:
        filtrado = df[serie_norm.str.contains(re.escape(objetivo), na=False) | serie_norm.apply(lambda x: objetivo in x if x else False)].copy()

    return filtrado


def primer_valor(*valores) -> str:
    for v in valores:
        txt = limpiar_texto(v)
        if txt:
            return txt
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
    return ahora_lima().strftime("%Y-%m")


def mes_actual() -> str:
    return str(ahora_lima().month)


def hoy_actual() -> date:
    return ahora_lima().date()


def dia_actual() -> int:
    return ahora_lima().day


def parse_periodo(periodo: str) -> tuple[int, int]:
    try:
        anio, mes = str(periodo).split("-")
        return int(anio), int(mes)
    except Exception:
        h = hoy_actual()
        return h.year, h.month


def fecha_desde_periodo_dia(periodo: str, dia: int) -> date:
    anio, mes = parse_periodo(periodo)
    ultimo = calendar.monthrange(anio, mes)[1]
    dia = max(1, min(int(dia), ultimo))
    return date(anio, mes, dia)


def mes_desde_periodo(periodo: str) -> str:
    _, mes = parse_periodo(periodo)
    return str(mes)


def dias_del_periodo(periodo: str) -> list[int]:
    anio, mes = parse_periodo(periodo)
    ultimo = calendar.monthrange(anio, mes)[1]
    return list(range(1, ultimo + 1))


def dias_del_mes_actual() -> list[int]:
    return dias_del_periodo(periodo_actual())


def primer_dia_periodo(periodo: str) -> date:
    anio, mes = parse_periodo(periodo)
    return date(anio, mes, 1)


def ultimo_dia_periodo(periodo: str) -> date:
    anio, mes = parse_periodo(periodo)
    return date(anio, mes, calendar.monthrange(anio, mes)[1])


def primer_dia_mes_actual() -> date:
    return primer_dia_periodo(periodo_actual())


def ultimo_dia_mes_actual() -> date:
    return ultimo_dia_periodo(periodo_actual())


def periodos_recientes(n: int = 4) -> list[str]:
    h = hoy_actual()
    out = []
    y, m = h.year, h.month
    for _ in range(n):
        out.append(f"{y:04d}-{m:02d}")
        m -= 1
        if m == 0:
            m = 12
            y -= 1
    return out


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


def fila_editable_fecha(row: pd.Series, fecha_edicion: date) -> bool:
    alta = parse_fecha(row.get("FECHA_ALTA"))
    cese = parse_fecha(row.get("FECHA_CESE"))
    estado = limpiar_texto(row.get("ESTADO", "")).upper()

    if alta and fecha_edicion < alta:
        return False
    if cese and fecha_edicion > cese:
        return False
    if estado == "ACTIVO":
        return True
    # Si ya está INACTIVO, solo deja corregir una baja médica dentro de su vigencia histórica.
    if estado == "INACTIVO" and cese and fecha_edicion <= cese:
        return True
    return False


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
            st.info("Operación deshabilitada: por seguridad no se borra ni recrea Asistencia desde la app.")
            confirmar = st.checkbox("Confirmo que deseo borrar SOLO la hoja Asistencia y recrear la cabecera", key="confirm_reset_asistencia")
            if confirmar and st.button("🧹 Opción deshabilitada", key="btn_reset_asistencia"):
                # DESHABILITADO: no se borra Asistencia desde la app.
                st.error("Operación bloqueada: no se permite borrar la hoja Asistencia desde la app.")
                for k in [KEY_DF_TOTAL, KEY_DF_ORIGINAL, KEY_HEADERS, KEY_LOADED, KEY_LOAD_TS]:
                    if k in st.session_state:
                        del st.session_state[k]
                st.success("Operación deshabilitada por seguridad.")
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


def leer_colaboradores_drive(hoja_colaboradores) -> pd.DataFrame:
    try:
        data = hoja_colaboradores.get_all_records()
    except Exception as e:
        st.error(f"Error leyendo colaboradores: {e}")
        return pd.DataFrame()

    df = pd.DataFrame(data)
    if df.empty:
        return df
    df = normalizar_columnas(df).fillna("").replace("None", "")
    if "DNI" in df.columns:
        df["DNI"] = df["DNI"].apply(normalizar_dni)
    return df


# =====================================================
# SINCRONIZACIÓN CON COLABORADORES
# =====================================================
def obtener_promotores_vigentes_mes(df_colab: pd.DataFrame, periodo_ref: str | None = None) -> pd.DataFrame:
    if df_colab.empty or "DNI" not in df_colab.columns:
        return pd.DataFrame()

    df = df_colab.copy()
    # Se incluye todo colaborador vigente del mes.
    # No se filtra solo PROMOTOR, porque el alta debe reflejarse en Presencialidad Dealer
    # según el registro creado en colaboradores.
    df["DNI"] = df["DNI"].apply(normalizar_dni)
    df = df[df["DNI"].ne("")].copy()

    periodo_ref = periodo_ref or periodo_actual()
    inicio_mes = primer_dia_periodo(periodo_ref)
    fin_mes = ultimo_dia_periodo(periodo_ref)

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


def construir_payload_base(row: pd.Series, periodo_ref: str | None = None) -> dict:
    periodo_ref = periodo_ref or periodo_actual()
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
        "MES": mes_desde_periodo(periodo_ref),
        "PERIODO": periodo_ref,
    }


def sincronizar_mes(hoja_asistencia, hoja_colaboradores, periodo_ref: str | None = None) -> tuple[int, int]:
    if not validar_o_crear_cabecera(hoja_asistencia):
        return 0, 0

    periodo = periodo_ref or periodo_actual()
    df_asistencia, headers = leer_asistencia_drive(hoja_asistencia)
    df_colab = leer_colaboradores_drive(hoja_colaboradores)
    df_vigentes = obtener_promotores_vigentes_mes(df_colab, periodo)

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
        payload = construir_payload_base(row, periodo)
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


def cargar_cache_desde_drive(hoja_asistencia, forzar: bool = False) -> None:
    if not forzar and st.session_state.get(KEY_LOADED) and not cache_vencido():
        return
    with st.spinner("Cargando datos desde Google Drive…"):
        df_total, headers = leer_asistencia_drive(hoja_asistencia)
    st.session_state[KEY_DF_TOTAL] = df_total.copy()
    st.session_state[KEY_DF_ORIGINAL] = df_total.copy()
    st.session_state[KEY_HEADERS] = headers
    st.session_state[KEY_LOADED] = True
    st.session_state[KEY_LOAD_TS] = time.time()


# =====================================================
# VISTA LIVE SIN SINCRONIZAR NI BORRAR
# =====================================================
def construir_vista_live_sin_escribir(hoja_asistencia, hoja_colaboradores, periodo_ref: str):
    """Construye la vista de Presencialidad desde colaboradores + Asistencia.

    IMPORTANTE:
    - No escribe en Google Sheets.
    - No borra nada.
    - No usa clear().
    - Si aparecen altas/bajas/cambios en colaboradores, se ven al refrescar la página.
    - Si el registro ya existe en Asistencia, conserva DIA_1..DIA_31.
    - Si el registro aún no existe en Asistencia, aparece en pantalla con ROW_SHEET vacío;
      si el usuario lo marca y guarda, recién se agrega esa fila puntual.
    """
    if not validar_o_crear_cabecera(hoja_asistencia):
        return pd.DataFrame(columns=COLUMNAS_ASISTENCIA + ["ROW_SHEET"]), pd.DataFrame(columns=COLUMNAS_ASISTENCIA + ["ROW_SHEET"]), COLUMNAS_ASISTENCIA.copy()

    df_asistencia, headers = leer_asistencia_drive(hoja_asistencia)
    df_colab = leer_colaboradores_drive(hoja_colaboradores)
    df_vigentes = obtener_promotores_vigentes_mes(df_colab, periodo_ref)

    # Mapa de histórico existente de asistencia por DNI + FECHA_ALTA + PERIODO.
    df_as_mes = df_asistencia[df_asistencia["PERIODO"].astype(str).eq(str(periodo_ref))].copy() if not df_asistencia.empty else pd.DataFrame(columns=COLUMNAS_ASISTENCIA + ["ROW_SHEET"])
    existentes = {}
    if not df_as_mes.empty:
        for _, r in df_as_mes.iterrows():
            key_reg = clave_asistencia(r.get("DNI", ""), r.get("FECHA_ALTA", ""))
            if key_reg.strip("|"):
                existentes[key_reg] = r.to_dict()

    filas = []
    vistos = set()

    if not df_vigentes.empty:
        for _, row in df_vigentes.iterrows():
            payload = construir_payload_base(row, periodo_ref)
            dni = payload.get("DNI", "")
            if not dni:
                continue
            key_reg = clave_asistencia(dni, payload.get("FECHA_ALTA", ""))
            vistos.add(key_reg)

            if key_reg in existentes:
                # Toma días y ROW_SHEET del histórico, pero refresca datos base desde colaboradores.
                base = {col: existentes[key_reg].get(col, "") for col in COLUMNAS_ASISTENCIA}
                base.update(payload)
                base["ROW_SHEET"] = existentes[key_reg].get("ROW_SHEET", "")
            else:
                # Nueva alta/cambio visto en colaboradores, todavía no existe en Asistencia.
                # Se muestra en vivo, sin prellenar/escribir 800 filas.
                base = {col: "" for col in COLUMNAS_ASISTENCIA}
                base.update(payload)
                base["ROW_SHEET"] = ""
            filas.append(base)

    # Mantener registros históricos del periodo que ya están en Asistencia aunque ya no aparezcan en colaboradores.
    # Esto protege el histórico y evita que desaparezcan filas antiguas.
    if not df_as_mes.empty:
        for _, r in df_as_mes.iterrows():
            key_reg = clave_asistencia(r.get("DNI", ""), r.get("FECHA_ALTA", ""))
            if key_reg and key_reg not in vistos:
                filas.append(r.to_dict())

    if filas:
        df_live = pd.DataFrame(filas)
    else:
        df_live = pd.DataFrame(columns=COLUMNAS_ASISTENCIA + ["ROW_SHEET"])

    for col in COLUMNAS_ASISTENCIA + ["ROW_SHEET"]:
        if col not in df_live.columns:
            df_live[col] = ""
    df_live = df_live[COLUMNAS_ASISTENCIA + ["ROW_SHEET"]].copy().fillna("")
    df_live["DNI"] = df_live["DNI"].apply(normalizar_dni)
    for col in COLUMNAS_DIAS:
        if col in df_live.columns:
            df_live[col] = df_live[col].apply(limpiar_marca)

    st.session_state[KEY_DF_TOTAL] = df_live.copy()
    st.session_state[KEY_DF_ORIGINAL] = df_live.copy()
    st.session_state[KEY_HEADERS] = headers
    st.session_state[KEY_LOADED] = True
    st.session_state[KEY_LOAD_TS] = time.time()
    return df_live.copy(), df_live.copy(), headers


def guardar_cambios_live(hoja_asistencia, df_editado: pd.DataFrame, df_original: pd.DataFrame, headers: list[str], col_hoy: str) -> tuple[int, int]:
    """Guarda cambios del editor soportando filas nuevas que aún no existen en Asistencia.

    Retorna: (celdas_actualizadas, filas_agregadas)
    """
    df_e = pd.DataFrame(df_editado).fillna("").copy()
    df_o = pd.DataFrame(df_original).fillna("").copy()
    if df_e.empty or col_hoy not in df_e.columns:
        return 0, 0

    headers_orden = [limpiar_texto(h).upper() for h in headers]
    if not headers_orden:
        headers_orden = COLUMNAS_ASISTENCIA.copy()
    mapa_col = {col: idx + 1 for idx, col in enumerate(headers_orden)}
    col_num = mapa_col.get(col_hoy)
    if not col_num:
        return 0, 0

    # Index original por llave real, porque las filas nuevas no tienen ROW_SHEET.
    def _key_row(r):
        return clave_asistencia(r.get("DNI", ""), r.get("FECHA_ALTA", ""))

    original_por_key = {}
    for _, r in df_o.iterrows():
        k = _key_row(r)
        if k:
            original_por_key[k] = r

    updates = []
    appends = []

    for _, row in df_e.iterrows():
        k = _key_row(row)
        if not k:
            continue
        nuevo = limpiar_marca(row.get(col_hoy, ""))
        original = original_por_key.get(k)
        anterior = limpiar_marca(original.get(col_hoy, "")) if original is not None else ""
        if nuevo == anterior:
            continue

        row_sheet_raw = limpiar_texto(row.get("ROW_SHEET", ""))
        row_sheet = None
        try:
            if row_sheet_raw:
                row_sheet = int(float(row_sheet_raw))
        except Exception:
            row_sheet = None

        if row_sheet:
            updates.append({"range": f"{letra_columna(col_num)}{row_sheet}", "values": [[nuevo]]})
        else:
            # Fila nueva vista en vivo desde colaboradores: se agrega una sola vez al guardar.
            fila = {col: "" for col in COLUMNAS_ASISTENCIA}
            for col in COLUMNAS_ASISTENCIA:
                fila[col] = limpiar_texto(row.get(col, ""))
            fila[col_hoy] = nuevo
            appends.append([fila.get(col, "") for col in headers_orden])

    if appends:
        hoja_asistencia.append_rows(appends, value_input_option="USER_ENTERED")
        time.sleep(0.15)

    if updates:
        for i in range(0, len(updates), 100):
            hoja_asistencia.batch_update(updates[i:i + 100], value_input_option="USER_ENTERED")
            if i + 100 < len(updates):
                time.sleep(0.10)

    return len(updates), len(appends)


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

    st.session_state[KEY_DF_TOTAL] = df_total.copy()
    st.session_state[KEY_DF_ORIGINAL] = df_total.copy()
    st.session_state[KEY_LOAD_TS] = time.time()


# =====================================================
# MODAL DE CARGA DE SUSTENTO OBLIGATORIO (A-BM)
# =====================================================
@st.dialog("📋 Carga de Sustento Obligatorio: Baja Médica")
def mostrar_dialogo_sustento(dni, nombre, row_sheet, col_hoy, df_editor, periodo_sel, fecha_asistencia):
    st.write(f"Colaborador: **{nombre}** (DNI: {dni})")
    st.warning("⚠️ Para registrar **A-BM (Baja Médica)**, es obligatorio subir el sustento o certificado médico correspondiente.")
    
    archivo = st.file_uploader(
        "Subir certificado médico (PDF o Imagen)",
        type=["pdf", "png", "jpg", "jpeg"],
        key=f"file_uploader_{dni}"
    )
    
    st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
    col_c1, col_c2 = st.columns(2)
    with col_c1:
        guardar = st.button("✅ Subir y Validar", use_container_width=True, key=f"btn_val_sustento_{dni}")
    with col_c2:
        cancelar = st.button("❌ Cancelar y Revertir", use_container_width=True, key=f"btn_canc_sustento_{dni}")
        
    if guardar:
        if not archivo:
            st.error("❌ Debes seleccionar y subir un archivo válido para registrar la baja médica.")
        else:
            if "sustentos_pendientes" not in st.session_state:
                st.session_state["sustentos_pendientes"] = {}
                
            st.session_state["sustentos_pendientes"][dni] = {
                "nombre_archivo": archivo.name,
                "contenido_bytes": archivo.read(),
                "mime_type": archivo.type,
                "dni": dni,
                "nombre": nombre,
                "row_sheet": row_sheet
            }
            
            # Forzar la marcación "A-BM" en el caché del DataFrame actual para evitar que se pierda en el rerun
            if KEY_DF_TOTAL in st.session_state:
                df_total = st.session_state[KEY_DF_TOTAL].copy()
                periodo = periodo_sel
                mask = (df_total["DNI"].astype(str) == str(dni)) & (df_total["PERIODO"].astype(str) == str(periodo))
                if mask.any():
                    df_total.loc[mask, col_hoy] = "A-BM"
                    st.session_state[KEY_DF_TOTAL] = df_total.copy()
                    
            st.success("✅ Sustento cargado y validado en memoria. Se subirá a Drive al guardar la asistencia.")
            time.sleep(1.2)
            st.rerun()
            
    if cancelar:
        # Revertir la selección de A-BM en el data editor
        if "editor_presencialidad_dia_actual" in st.session_state:
            edited_rows = st.session_state["editor_presencialidad_dia_actual"].get("edited_rows", {})
            for r_str in list(edited_rows.keys()):
                r_idx = int(r_str)
                if r_idx < len(df_editor):
                    row_dni = df_editor.iloc[r_idx]["DNI"]
                    if row_dni == dni:
                        # Revertimos a vacío
                        edited_rows[r_str][col_hoy] = ""
                        
        st.warning("Marcación revertida.")
        time.sleep(1.2)
        st.rerun()


# =====================================================
# MAIN
# =====================================================
def mostrar_asistencia(hoja_asistencia, hoja_colaboradores, registro_mod=None, razon=None):
    st.markdown("<span class='wow-section-title'>🗓️ Presencialidad Dealer</span>", unsafe_allow_html=True)

    if not validar_cabecera_sin_red(hoja_asistencia):
        return

    # Período y día: no hay botón de sincronizar para el socio.
    # Al cargar o refrescar la página, se actualiza automáticamente de forma NO destructiva.
    periodos = sorted(set(periodos_recientes(4)), reverse=True)
    periodo = st.selectbox("PERIODO", periodos, index=0, key="asis_periodo_sel")
    dias_validos = dias_del_periodo(periodo)
    hoy = hoy_actual()
    dia_default = hoy.day if periodo == periodo_actual() and hoy.day in dias_validos else dias_validos[-1]
    dia_sel = st.selectbox("DÍA", dias_validos, index=dias_validos.index(dia_default), key="asis_dia_sel")
    fecha_edicion = fecha_desde_periodo_dia(periodo, dia_sel)
    col_hoy = f"DIA_{dia_sel}"
    es_dia_actual = fecha_edicion == hoy

    st.info(
        f"📅 Periodo: **{periodo}** | Día seleccionado: **{col_hoy}** | "
        "La información se lee al abrir/refrescar la página. Solo se escribe al presionar Guardar Presencialidad. A-BM permite sustento histórico."
    )

    # VISTA LIVE: lee colaboradores + asistencia y arma la pantalla sin escribir ni borrar.
    # Si hay 20 altas o 50 bajas manuales en colaboradores, aparecen al refrescar la página.
    # No prellena 800 filas en Asistencia; solo guarda la fila puntual cuando el usuario marca algo.
    df_total, df_original, headers = construir_vista_live_sin_escribir(hoja_asistencia, hoja_colaboradores, periodo)

    for col in COLUMNAS_ASISTENCIA:
        if col not in df_total.columns:
            df_total[col] = ""
        if col not in df_original.columns:
            df_original[col] = ""

    df_mes = df_total[df_total["PERIODO"].astype(str).eq(periodo)].copy()

    # Restricción por usuario: si el usuario tiene una razón social específica,
    # solo verá esa razón. Si razon = ALL, ve todo.
    razon_usuario = limpiar_texto(razon if razon is not None else st.session_state.get("razon", ""))
    df_mes_total_antes_filtro_usuario = df_mes.copy()
    df_mes = filtrar_por_razon_usuario(df_mes, razon_usuario)

    if df_mes.empty:
        # No dejar pantalla en blanco: mostrar diagnóstico operativo claro.
        if razon_usuario and razon_usuario.upper() != "ALL":
            razones_disponibles = []
            if "RAZON SOCIAL" in df_mes_total_antes_filtro_usuario.columns and not df_mes_total_antes_filtro_usuario.empty:
                razones_disponibles = sorted([x for x in df_mes_total_antes_filtro_usuario["RAZON SOCIAL"].astype(str).str.strip().unique().tolist() if x])[:20]
            st.warning(
                f"⚠️ No hay registros visibles para la razón social del usuario: **{razon_usuario}** en el periodo **{periodo}**. "
                "La app leyó colaboradores y asistencia sin escribir ni borrar histórico. "
                "Valida que en usuarios.json la razón sea igual a la razón del Drive."
            )
            if razones_disponibles:
                st.caption("Razones sociales encontradas en Asistencia para este periodo:")
                st.code("\n".join(razones_disponibles), language="text")
        else:
            st.warning("⚠️ No hay registros para el periodo seleccionado. La app leyó colaboradores y asistencia sin escribir. Si sigue vacío, valida que existan colaboradores vigentes en ese mes.")
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
    df_editor_base = df_filtrado[df_filtrado.apply(lambda r: fila_editable_fecha(r, fecha_edicion), axis=1)].copy()
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

        st.markdown("<span class='wow-section-title'>✏️ Registrar presencialidad de hoy</span>", unsafe_allow_html=True)
        st.info("**Motivos de validación:** A = Asistió · A-BM = No Asistió por Baja Médica · A-VAC = No Asistió por Vacaciones · NA-SA = No Asistió - Sin aviso · NA-CA = No Asistió - Con aviso")
        st.caption(f"Columna habilitada: **{col_hoy}**. Si el día no es hoy, solo se permite **A-BM** con sustento. Los INACTIVOS solo se respetan hasta su fecha de cese.")

        columnas_editor = COLUMNAS_FIJAS_EDITOR + [col_hoy, "ROW_SHEET"]
        for col in columnas_editor:
            if col not in df_editor_base.columns:
                df_editor_base[col] = ""

        df_editor = df_editor_base[columnas_editor].copy().fillna("").replace({"None": "", "nan": ""})
        df_editor[col_hoy] = df_editor[col_hoy].apply(limpiar_marca)

        # =====================================================
        # DETECCIÓN EN TIEMPO REAL: marca A-BM sin sustento
        # =====================================================
        cambios = st.session_state.get("editor_presencialidad_dia_actual", {}).get("edited_rows", {})
        if cambios:
            # Limpiar sustentos huérfanos si cambiaron de A-BM a otra cosa
            sustentos_cargados = st.session_state.get("sustentos_pendientes", {})
            if sustentos_cargados:
                dni_en_baja = set()
                for r_str, cols in cambios.items():
                    r_idx = int(r_str)
                    if col_hoy in cols and cols[col_hoy] == "A-BM":
                        if r_idx < len(df_editor):
                            dni_en_baja.add(df_editor.iloc[r_idx]["DNI"])
                for dni in list(sustentos_cargados.keys()):
                    if dni not in dni_en_baja:
                        del st.session_state["sustentos_pendientes"][dni]

            # Verificar si hay alguna selección nueva de A-BM que requiera sustento
            for r_str, cols in cambios.items():
                r_idx = int(r_str)
                if col_hoy in cols and cols[col_hoy] == "A-BM":
                    if r_idx < len(df_editor):
                        row_data = df_editor.iloc[r_idx]
                        dni = row_data["DNI"]
                        nombre = row_data["NOMBRE"]
                        row_sheet = row_data["ROW_SHEET"]
                        
                        if dni not in st.session_state.get("sustentos_pendientes", {}):
                            mostrar_dialogo_sustento(dni, nombre, row_sheet, col_hoy, df_editor, periodo, fecha_edicion)

        disabled_cols = [col for col in df_editor.columns if col != col_hoy]
        # Mantengo ROW_SHEET visible como FILA técnica para evitar el error React #185
        # que aparece a veces cuando se oculta una columna usada para guardar.
        opciones_marca = MARCAS_PRESENCIALIDAD if es_dia_actual else MARCAS_SOLO_BAJA_MEDICA
        column_config = {
            "ROW_SHEET": st.column_config.NumberColumn("FILA", width="small", disabled=True),
            col_hoy: st.column_config.SelectboxColumn(col_hoy, options=opciones_marca, width="small"),
        }

        editado = st.data_editor(
            df_editor,
            use_container_width=True,
            height=min(460, 50 + len(df_editor) * 32),
            hide_index=True,
            disabled=disabled_cols,
            column_config=column_config,
            num_rows="fixed",
            key="editor_presencialidad_dia_actual",
        )

        guardar_pres = st.button("💾 Guardar Presencialidad", key="btn_guardar_presencialidad")

        if guardar_pres:
            with st.spinner("Guardando en Google Drive…"):
                try:
                    df_editado = normalizar_para_guardado(pd.DataFrame(editado).fillna(""), col_hoy)
                    if df_editado.empty or "ROW_SHEET" not in df_editado.columns:
                        st.warning("No se pudo leer la tabla del editor. Recarga la página.")
                    else:
                        # 1. Validación de seguridad final para marcas A-BM sin sustento
                        cambios_actuales = st.session_state.get("editor_presencialidad_dia_actual", {}).get("edited_rows", {})
                        for r_str, cols in cambios_actuales.items():
                            r_idx = int(r_str)
                            if col_hoy in cols and cols[col_hoy] == "A-BM":
                                if r_idx < len(df_editor):
                                    dni = df_editor.iloc[r_idx]["DNI"]
                                    if dni not in st.session_state.get("sustentos_pendientes", {}):
                                        st.error(f"❌ Falta el sustento médico obligatorio para {df_editor.iloc[r_idx]['NOMBRE']}.")
                                        st.stop()

                        # 2. Subida de certificados a Google Drive y registro de auditoría en Sheets
                        sustentos = st.session_state.get("sustentos_pendientes", {})
                        if sustentos:
                            columnas_defecto = [
                                "PERIODO",
                                "FECHA_ASISTENCIA",
                                "DNI",
                                "NOMBRE",
                                "RAZON SOCIAL",
                                "MOTIVO",
                                "LINK_DOCUMENTO",
                                "FECHA_SUBIDA",
                                "USUARIO_REGISTRO"
                            ]
                            hoja_sustentos = obtener_o_crear_worksheet("maestra_vendedores", "Sustentos_Bajas", columnas_defecto)
                            
                            filas_nuevas = []
                            user_activo = st.session_state.get("usuario", "desconocido")
                            tz_lima = pytz.timezone("America/Lima")
                            timestamp_lima = datetime.now(tz_lima).strftime("%Y-%m-%d %H:%M:%S")
                            
                            for dni, datos in list(sustentos.items()):
                                extension = "pdf" if datos["mime_type"] == "application/pdf" else "jpg"
                                nombre_archivo_drive = f"sustento_{dni}_{fecha_edicion}_{int(time.time())}.{extension}"
                                
                                link_drive = subir_archivo_drive(
                                    nombre_archivo=nombre_archivo_drive,
                                    contenido_bytes=datos["contenido_bytes"],
                                    mime_type=datos["mime_type"]
                                )
                                
                                row_vendedor = df_editor[df_editor["DNI"] == dni].iloc[0]
                                razon_social = row_vendedor.get("RAZON SOCIAL", "")
                                
                                filas_nuevas.append([
                                    periodo,
                                    str(fecha_edicion),
                                    dni,
                                    datos["nombre"],
                                    razon_social,
                                    "A-BM (Baja Médica)",
                                    link_drive,
                                    timestamp_lima,
                                    user_activo
                                ])
                            
                            if filas_nuevas:
                                hoja_sustentos.append_rows(filas_nuevas, value_input_option="USER_ENTERED")
                            
                            # Limpiar memoria de sustentos procesados
                            st.session_state["sustentos_pendientes"] = {}

                        actualizadas, agregadas = guardar_cambios_live(
                            hoja_asistencia=hoja_asistencia,
                            df_editado=df_editado,
                            df_original=df_original,
                            headers=headers,
                            col_hoy=col_hoy,
                        )
                        if actualizadas == 0 and agregadas == 0:
                            st.info("ℹ️ No se detectaron cambios para guardar.")
                        else:
                            # Recarga live para tomar ROW_SHEET real de filas nuevas y mostrar lo último.
                            for k in [KEY_DF_TOTAL, KEY_DF_ORIGINAL, KEY_HEADERS, KEY_LOADED, KEY_LOAD_TS]:
                                if k in st.session_state:
                                    del st.session_state[k]
                            st.session_state["asis_guardado_msg"] = f"✅ Presencialidad guardada. Celdas actualizadas: {actualizadas}. Filas nuevas agregadas: {agregadas}."
                            st.rerun()
                except Exception as e:
                    st.error(f"❌ Error guardando presencialidad: {e}")

    if msg := st.session_state.pop("asis_guardado_msg", None):
        st.success(msg)

    # Espejo mensual completo: muestra todo el mes y mantiene histórico.
    df_total_actual = st.session_state[KEY_DF_TOTAL].copy()
    df_mes_actual = df_total_actual[df_total_actual["PERIODO"].astype(str).eq(periodo)].copy()
    df_mes_actual = filtrar_por_razon_usuario(df_mes_actual, razon_usuario)
    df_espejo = filtrar_df(df_mes_actual, filtro_razon, filtro_supervisor, filtro_coord, filtro_dep, filtro_prov, filtro_estado)

    ver_espejo = st.checkbox("📊 Ver espejo mensual completo", value=False, key="asis_ver_espejo")
    if ver_espejo:
        st.markdown("<span class='wow-section-title'>📊 Espejo mensual completo</span>", unsafe_allow_html=True)
        mostrar_espejo_mes(df_espejo, dias_validos)
    else:
        st.caption("Espejo mensual oculto para mejorar rendimiento. Actívalo solo cuando necesites revisar el mes completo.")

    st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
    ver_sustentos = st.checkbox("📋 Ver log de sustentos de Bajas Médicas", value=False, key="asis_ver_sustentos")
    if ver_sustentos:
        st.markdown("<span class='wow-section-title'>📋 Registro de Sustentos de Bajas Médicas</span>", unsafe_allow_html=True)
        with st.spinner("Cargando sustentos desde Google Sheets..."):
            try:
                columnas_defecto = [
                    "PERIODO",
                    "FECHA_ASISTENCIA",
                    "DNI",
                    "NOMBRE",
                    "RAZON SOCIAL",
                    "MOTIVO",
                    "LINK_DOCUMENTO",
                    "FECHA_SUBIDA",
                    "USUARIO_REGISTRO"
                ]
                # Obtenemos o creamos la hoja
                hoja_sustentos = obtener_o_crear_worksheet("maestra_vendedores", "Sustentos_Bajas", columnas_defecto)
                # Leemos todos los registros
                datos_sustentos = hoja_sustentos.get_all_records()
                if not datos_sustentos:
                    st.info("ℹ️ No hay sustentos de bajas médicas registrados en este periodo.")
                else:
                    df_sustentos = pd.DataFrame(datos_sustentos)
                    # Filtrar por periodo actual para mostrar solo lo relevante
                    if "PERIODO" in df_sustentos.columns:
                        df_sustentos = df_sustentos[df_sustentos["PERIODO"].astype(str) == periodo]
                    
                    if df_sustentos.empty:
                        st.info("ℹ️ No hay sustentos de bajas médicas registrados para el periodo actual.")
                    else:
                        # Ordenar por fecha de subida descendente (más recientes primero)
                        if "FECHA_SUBIDA" in df_sustentos.columns:
                            df_sustentos = df_sustentos.sort_values(by="FECHA_SUBIDA", ascending=False)
                            
                        # Configurar columna de link como LinkColumn para que sea directamente cliqueable
                        st.dataframe(
                            df_sustentos,
                            use_container_width=True,
                            hide_index=True,
                            column_config={
                                "LINK_DOCUMENTO": st.column_config.LinkColumn("Link de Documento", width="medium"),
                                "FECHA_ASISTENCIA": st.column_config.Column("Fecha Asistencia", width="small"),
                                "DNI": st.column_config.Column("DNI", width="small"),
                                "NOMBRE": st.column_config.Column("Colaborador", width="medium"),
                                "FECHA_SUBIDA": st.column_config.Column("Fecha Subida", width="medium"),
                            }
                        )
            except Exception as e:
                st.error(f"Error al cargar log de sustentos: {e}")

    if registro_mod is not None:
        st.divider()
        st.markdown("<span class='wow-section-title'>📋 Matriz de jerarquía</span>", unsafe_allow_html=True)
        try:
            registro_mod.mostrar_tabla(hoja_colaboradores, razon)
        except Exception as e:
            st.warning(f"No se pudo cargar la matriz de jerarquía: {e}")
