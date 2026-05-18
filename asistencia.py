"""
asistencia.py — Presencialidad Dealer
Cambios aplicados:
  1. Módulo visible como Presencialidad Dealer desde app_maestra_vendedores.py.
  2. Filtros: Razón Social, Supervisor, Coordinador, Departamento y Provincia.
  3. La hoja Asistencia conserva histórico mensual y no borra registros anteriores.
  4. Sincroniza activos y también inactivos con cese dentro del mes para respetar historia.
  5. Solo permite editar el día actual. No permite modificar días anteriores ni futuros.
  6. Si un colaborador está inactivo, solo permite marcar hasta su fecha de cese.
  7. Marcajes permitidos: A, F, DM y S.
  8. Si la hoja tiene cabecera descuadrada, NO agrega columnas al final: obliga a recrear estructura para evitar mazamorra.
"""

import calendar
import time
from datetime import datetime, date

import pandas as pd
import streamlit as st

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
# Menos filas visibles para que cada cambio de filtro no congele Render/Chrome.
MAX_FILAS_EDITOR = 80

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
    return v if v in ("A", "F", "DM", "S") else ""


def normalizar_dni(valor) -> str:
    dni = limpiar_texto(valor).replace(".0", "")
    if dni.isdigit() and len(dni) < 8:
        dni = dni.zfill(8)
    return dni


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
    if cese and hoy > cese:
        return False
    if estado == "INACTIVO" and cese and hoy <= cese:
        return True
    return estado == "ACTIVO"


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
    return {
        "RAZON SOCIAL": limpiar_texto(row.get("RAZON SOCIAL", "")),
        "SUPERVISOR": limpiar_texto(row.get("SUPERVISOR A CARGO", row.get("SUPERVISOR", ""))),
        "COORDINADOR": limpiar_texto(row.get("COORDINADOR", "")),
        "DEPARTAMENTO": limpiar_texto(row.get("DEPARTAMENTO", "")),
        "PROVINCIA": limpiar_texto(row.get("PROVINCIA", "")),
        "DNI": normalizar_dni(row.get("DNI", "")),
        "NOMBRE": nombre_completo(row),
        "ESTADO": limpiar_texto(row.get("ESTADO", "")).upper(),
        "FECHA_ALTA": str(parse_fecha(row.get("FECHA DE CREACION USUARIO", row.get("FECHA_CREACION_USUARIO", ""))) or ""),
        "FECHA_CESE": str(parse_fecha(row.get("FECHA DE CESE", row.get("FECHA CESE", ""))) or ""),
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
            existentes[normalizar_dni(r.get("DNI", ""))] = int(r.get("ROW_SHEET"))

    nuevas = []
    updates = []

    for _, row in df_vigentes.iterrows():
        payload = construir_payload_base(row)
        dni = payload["DNI"]
        if not dni:
            continue

        if dni not in existentes:
            fila = {col: "" for col in COLUMNAS_ASISTENCIA}
            fila.update(payload)
            # La fila nueva se arma según el orden REAL de cabeceras de la hoja.
            # Esto evita descuadres si la hoja Asistencia ya existía y se agregaron
            # RAZON SOCIAL / FECHA_ALTA / FECHA_CESE al final.
            headers_orden = [limpiar_texto(h).upper() for h in headers]
            nuevas.append([fila.get(col, "") for col in headers_orden])
        else:
            row_sheet = existentes[dni]
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
    Agrega SOLO el alta recién registrada al periodo actual de Presencialidad.
    Evita ejecutar Sincronizar mes completo desde el formulario de Alta, porque
    eso lee toda la base y hacía que el formulario se frizara.
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
    if not dni:
        return "Presencialidad pendiente: DNI vacío."

    # Revisión rápida contra el periodo actual para no duplicar DNI.
    try:
        idx_dni = headers.index("DNI")
        idx_periodo = headers.index("PERIODO")
        for fila in valores[1:]:
            dni_existente = normalizar_dni(fila[idx_dni] if len(fila) > idx_dni else "")
            periodo_existente = limpiar_texto(fila[idx_periodo] if len(fila) > idx_periodo else "")
            if dni_existente == dni and periodo_existente == periodo:
                return "Presencialidad ya tenía este DNI en el periodo actual; no se duplicó."
    except Exception:
        pass

    fila_base = {col: "" for col in COLUMNAS_ASISTENCIA}
    fila_base.update({
        "RAZON SOCIAL": limpiar_texto(campos.get("RAZON SOCIAL", "")),
        "SUPERVISOR": limpiar_texto(campos.get("SUPERVISOR A CARGO", campos.get("SUPERVISOR", ""))),
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
        "FECHA_ALTA": str(parse_fecha(campos.get("FECHA DE CREACION USUARIO", "")) or ""),
        "FECHA_CESE": "",
        "MES": mes_actual(),
        "PERIODO": periodo,
    })
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
    valores = df[columna].astype(str).str.strip().replace("", pd.NA).dropna().unique().tolist()
    return ["TODOS"] + sorted(valores)


def aplicar_filtro(df: pd.DataFrame, columna: str, valor: str) -> pd.DataFrame:
    if valor == "TODOS" or columna not in df.columns:
        return df
    return df[df[columna].astype(str).str.strip().eq(valor)].copy()


def filtrar_df(df: pd.DataFrame, razon: str, supervisor: str, coordinador: str, departamento: str, provincia: str) -> pd.DataFrame:
    r = df.copy()
    r = aplicar_filtro(r, "RAZON SOCIAL", razon)
    r = aplicar_filtro(r, "SUPERVISOR", supervisor)
    r = aplicar_filtro(r, "COORDINADOR", coordinador)
    r = aplicar_filtro(r, "DEPARTAMENTO", departamento)
    r = aplicar_filtro(r, "PROVINCIA", provincia)
    return r


# =====================================================
# ESTILOS / ESPEJO
# =====================================================
def estilo_asistencia(valor: str) -> str:
    v = limpiar_marca(valor)
    if v == "A":
        return "background-color:#D4EDDA;color:#155724;font-weight:bold;text-align:center;"
    if v == "F":
        return "background-color:#F8D7DA;color:#721C24;font-weight:bold;text-align:center;"
    if v == "DM":
        return "background-color:#FFF3CD;color:#7A5A00;font-weight:bold;text-align:center;"
    if v == "S":
        return "background-color:#E8D8FF;color:#4B0067;font-weight:bold;text-align:center;"
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
        if st.button("🔄 Sincronizar mes", key="btn_sync_asistencia"):
            with st.spinner("Sincronizando con colaboradores…"):
                try:
                    nuevos, actualizados = sincronizar_mes(hoja_asistencia, hoja_colaboradores)
                    cargar_cache_desde_drive(hoja_asistencia, forzar=True)
                    st.success(f"✅ Mes sincronizado. Nuevos: {nuevos} | Datos base actualizados: {actualizados}")
                except Exception as e:
                    st.error(f"Error sincronizando: {e}")
                    return

    with c2:
        if st.button("♻️ Recargar Drive", key="btn_reload_asistencia"):
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
        st.warning("⚠️ No hay registros del periodo actual. Presiona **Sincronizar mes**.")
        return

    # Filtros encadenados: Razón Social > Supervisor > Coordinador > Departamento > Provincia
    f1, f2, f3, f4, f5 = st.columns(5)
    with f1:
        filtro_razon = st.selectbox("Razón Social", lista_opciones(df_mes, "RAZON SOCIAL"), key="asis_razon")
    df_base = aplicar_filtro(df_mes, "RAZON SOCIAL", filtro_razon)

    with f2:
        filtro_supervisor = st.selectbox("Supervisor", lista_opciones(df_base, "SUPERVISOR"), key="asis_supervisor")
    df_base = aplicar_filtro(df_base, "SUPERVISOR", filtro_supervisor)

    with f3:
        filtro_coord = st.selectbox("Coordinador", lista_opciones(df_base, "COORDINADOR"), key="asis_coordinador")
    df_base = aplicar_filtro(df_base, "COORDINADOR", filtro_coord)

    with f4:
        filtro_dep = st.selectbox("Departamento", lista_opciones(df_base, "DEPARTAMENTO"), key="asis_departamento")
    df_base = aplicar_filtro(df_base, "DEPARTAMENTO", filtro_dep)

    with f5:
        filtro_prov = st.selectbox("Provincia", lista_opciones(df_base, "PROVINCIA"), key="asis_provincia")

    df_filtrado = filtrar_df(df_mes, filtro_razon, filtro_supervisor, filtro_coord, filtro_dep, filtro_prov)

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
                f"⚠️ Hay {total_filtrado} registros editables hoy. El editor muestra máximo {MAX_FILAS_EDITOR} "
                "para no congelar la página. Esto NO borra registros; solo pagina la vista. Usa filtros o cambia de página."
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
        st.caption(f"Solo está habilitada la columna **{col_hoy}**. Registra **A** = Asistió · **F** = Faltó · **DM** = Descanso médico · **S** = Seguimiento/Suspensión.")

        columnas_editor = COLUMNAS_FIJAS_EDITOR + [col_hoy, "ROW_SHEET"]
        for col in columnas_editor:
            if col not in df_editor_base.columns:
                df_editor_base[col] = ""

        df_editor = df_editor_base[columnas_editor].copy().fillna("").replace({"None": "", "nan": ""})
        df_editor[col_hoy] = df_editor[col_hoy].apply(limpiar_marca)

        disabled_cols = [col for col in df_editor.columns if col != col_hoy]
        column_config = {
            "ROW_SHEET": None,
            col_hoy: st.column_config.SelectboxColumn(col_hoy, options=["", "A", "F", "DM", "S"], width="small"),
        }

        editado = st.data_editor(
            df_editor,
            use_container_width=True,
            height=min(600, 50 + len(df_editor) * 35),
            hide_index=True,
            disabled=disabled_cols,
            column_config=column_config,
            num_rows="fixed",
            key="editor_presencialidad_dia_actual",
        )

        if st.button("💾 Guardar Presencialidad", key="btn_guardar_asistencia"):
            with st.spinner("Guardando en Google Drive…"):
                try:
                    df_editado = normalizar_para_guardado(pd.DataFrame(editado).fillna(""), col_hoy)
                    if df_editado.empty or "ROW_SHEET" not in df_editado.columns:
                        st.warning("No se pudo leer la tabla del editor. Recarga la página.")
                    else:
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
    df_espejo = filtrar_df(df_mes_actual, filtro_razon, filtro_supervisor, filtro_coord, filtro_dep, filtro_prov)

    ver_espejo = st.checkbox("📊 Ver espejo mensual completo", value=False, key="asis_ver_espejo")
    if ver_espejo:
        st.markdown("<span class='wow-section-title'>📊 Espejo mensual completo</span>", unsafe_allow_html=True)
        mostrar_espejo_mes(df_espejo, dias_validos)
    else:
        st.caption("Espejo mensual oculto para mejorar rendimiento. Actívalo solo cuando necesites revisar el mes completo.")

    if registro_mod is not None:
        st.divider()
        st.markdown("<span class='wow-section-title'>📋 Matriz de jerarquía</span>", unsafe_allow_html=True)
        try:
            registro_mod.mostrar_tabla(hoja_colaboradores, razon)
        except Exception as e:
            st.warning(f"No se pudo cargar la matriz de jerarquía: {e}")
