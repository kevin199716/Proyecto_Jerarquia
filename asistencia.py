# FIX_RESTORE_FLUIDO_DIALOGO_ABM_SIN_SYNC_20260602
"""
asistencia.py — Presencialidad Dealer
Cambios aplicados:
  1. Módulo visible como Presencialidad Dealer desde app_maestra_vendedores.py.
  2. Filtros: Razón Social, Supervisor, Coordinador, Departamento y Provincia.
  3. La hoja Asistencia conserva histórico mensual y no borra registros anteriores.
  4. Modo fluido: solo lee Asistencia al abrir; no cruza colaboradores ni sincroniza automáticamente.
  5. Solo permite editar el día actual. No permite modificar días anteriores ni futuros.
  6. Si un colaborador está inactivo, solo permite marcar hasta su fecha de cese.
  7. Marcajes permitidos: A, A-BM, A-VAC, NA-SA y NA-CA.
  8. A-BM vuelve a usar ventana emergente obligatoria para adjuntar sustento.
  9. Sin botones Sincronizar/Recargar dentro del módulo dealer.
"""

import calendar
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
MAX_FILAS_EDITOR = 200

MARCAS_PRESENCIALIDAD = ["", "A", "A-BM", "A-VAC", "NA-SA", "NA-CA"]
LEYENDA_MARCAS = {
    "A": "Asistió",
    "A-BM": "No Asistió por Baja Médica",
    "A-VAC": "No Asistió por Vacaciones",
    "NA-SA": "No Asistió - Sin aviso",
    "NA-CA": "No Asistió - Con aviso",
}

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

        st.info("Por seguridad, desde la app NO se borra ni se recrea la hoja Asistencia. Corrige la cabecera manualmente si corresponde.")
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
        return "Presencialidad pendiente: revisa la cabecera de Asistencia."

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
def mostrar_dialogo_sustento(dni, nombre, row_sheet, col_hoy, df_editor):
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
                periodo = periodo_actual()
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

    periodo = periodo_actual()
    dias_validos = dias_del_mes_actual()
    hoy_dia = dia_actual()
    col_hoy = f"DIA_{hoy_dia}"

    st.info(
        f"📅 Periodo: **{periodo}** | Día editable: **{col_hoy}** | "
        "La vista trabaja desde la hoja Asistencia ya sincronizada. No hay botones de sincronización ni recarga para dealers."
    )

    # Carga estable y rápida: solo lee la hoja Asistencia, como el flujo anterior.
    # No cruza colaboradores al abrir porque eso fue lo que empezó a frizear la pantalla.
    cargar_cache_desde_drive(hoja_asistencia)

    df_total = st.session_state[KEY_DF_TOTAL].copy()
    df_original = st.session_state[KEY_DF_ORIGINAL].copy()
    headers = st.session_state.get(KEY_HEADERS, COLUMNAS_ASISTENCIA)

    for col in COLUMNAS_ASISTENCIA:
        if col not in df_total.columns:
            df_total[col] = ""
        if col not in df_original.columns:
            df_original[col] = ""

    df_mes = df_total[df_total["PERIODO"].astype(str).eq(periodo)].copy()

    # Restricción por usuario: si el usuario tiene una razón social específica,
    # solo verá esa razón. Si razon = ALL, ve todo.
    razon_usuario = limpiar_texto(razon if razon is not None else st.session_state.get("razon", ""))
    if razon_usuario and razon_usuario.upper() != "ALL" and "RAZON SOCIAL" in df_mes.columns:
        df_mes = df_mes[df_mes["RAZON SOCIAL"].astype(str).str.strip().str.upper().eq(razon_usuario.upper())].copy()

    if df_mes.empty:
        st.warning("⚠️ No hay registros activos del periodo actual para este dealer. Revisa la hoja Asistencia o que el alta haya sido registrada correctamente.")
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
    op_estado = ["ACTIVO"]  # Presencialidad solo permite registrar personal activo

    def _valor_guardado(clave, opciones):
        valor = st.session_state.get(clave, "TODOS")
        return valor if valor in opciones else "TODOS"

    with st.form("form_filtros_presencialidad"):
        # IMPORTANTE: etiquetas visibles. No usar label_visibility="collapsed".
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
    # Seguridad operativa: el registro de presencialidad SOLO trabaja ACTIVO.
    # Inactivos no se muestran en el editor ni pueden guardarse por error.
    if "ESTADO" in df_filtrado.columns:
        df_filtrado = df_filtrado[df_filtrado["ESTADO"].astype(str).str.strip().str.upper().eq("ACTIVO")].copy()

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

        st.markdown("<span class='wow-section-title'>✏️ Registrar presencialidad de hoy</span>", unsafe_allow_html=True)
        st.info("**Motivos de validación:** A = Asistió · A-BM = No Asistió por Baja Médica · A-VAC = No Asistió por Vacaciones · NA-SA = No Asistió - Sin aviso · NA-CA = No Asistió - Con aviso")
        st.caption(f"Solo está habilitada la columna **{col_hoy}** para personal ACTIVO. Los INACTIVOS quedan visibles en el espejo histórico, pero no se pueden marcar.")

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
                            mostrar_dialogo_sustento(dni, nombre, row_sheet, col_hoy, df_editor)

        disabled_cols = [col for col in df_editor.columns if col != col_hoy]
        # Mantengo ROW_SHEET visible como FILA técnica para evitar el error React #185
        # que aparece a veces cuando se oculta una columna usada para guardar.
        column_config = {
            "ROW_SHEET": st.column_config.NumberColumn("FILA", width="small", disabled=True),
            col_hoy: st.column_config.SelectboxColumn(col_hoy, options=MARCAS_PRESENCIALIDAD, width="small"),
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
                                nombre_archivo_drive = f"sustento_{dni}_{hoy_actual()}.{extension}"
                                
                                link_drive = subir_archivo_drive(
                                    nombre_archivo=nombre_archivo_drive,
                                    contenido_bytes=datos["contenido_bytes"],
                                    mime_type=datos["mime_type"]
                                )
                                
                                row_vendedor = df_editor[df_editor["DNI"] == dni].iloc[0]
                                razon_social = row_vendedor.get("RAZON SOCIAL", "")
                                
                                filas_nuevas.append([
                                    periodo,
                                    str(hoy_actual()),
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
                            st.session_state["asis_guardado_msg"] = f"✅ Presencialidad guardada. Celdas actualizadas: {len(updates)}"
                            st.rerun()
                except Exception as e:
                    st.error(f"❌ Error guardando presencialidad: {e}")

    if msg := st.session_state.pop("asis_guardado_msg", None):
        st.success(msg)

    # Espejo mensual completo: muestra todo el mes y mantiene histórico.
    df_total_actual = st.session_state[KEY_DF_TOTAL].copy()
    df_mes_actual = df_total_actual[df_total_actual["PERIODO"].astype(str).eq(periodo)].copy()
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
