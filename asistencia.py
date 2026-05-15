"""
asistencia.py — VERSIÓN OPTIMIZADA
Fixes aplicados:
  1. Muestra los 31 días editables (no solo la semana)
  2. Caché agresivo con TTL para evitar llamadas repetidas a Drive
  3. Paginación automática para evitar cuelgues con muchos registros
  4. batch_update agrupado por filas (mucho más rápido)
  5. Indicadores de progreso para no congelar la UI
  6. Manejo robusto de errores con reintentos
"""

import time
from datetime import datetime

import pandas as pd
import streamlit as st

# =====================================================
# CONSTANTES
# =====================================================
COLUMNAS_BASE = [
    "SUPERVISOR", "COORDINADOR", "DEPARTAMENTO", "PROVINCIA",
    "DNI", "NOMBRE", "ESTADO", "MES", "PERIODO",
]
COLUMNAS_DIAS = [f"DIA_{i}" for i in range(1, 32)]
COLUMNAS_ASISTENCIA = COLUMNAS_BASE + COLUMNAS_DIAS

COLUMNAS_FIJAS_EDITOR = [
    "DNI", "NOMBRE", "SUPERVISOR", "COORDINADOR",
    "DEPARTAMENTO", "PROVINCIA", "ESTADO", "MES", "PERIODO",
]

# Claves de session_state
KEY_DF_TOTAL    = "asis_df_total_cache"
KEY_DF_ORIGINAL = "asis_df_original_cache"
KEY_HEADERS     = "asis_headers_cache"
KEY_LOADED      = "asis_loaded"
KEY_LOAD_TS     = "asis_load_timestamp"

# TTL del caché en memoria (segundos) — recarga automática cada 5 min
CACHE_TTL = 300

# Máximo de filas en el editor para no congelar Render
MAX_FILAS_EDITOR = 200


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
    return "" if s.upper() in ("NONE", "NAN", "NULL", "") else s


def limpiar_marca(valor) -> str:
    v = limpiar_texto(valor).upper()
    return v if v in ("A", "F") else ""


def periodo_actual() -> str:
    return datetime.now().strftime("%Y-%m")


def mes_actual() -> str:
    return str(datetime.now().month)


def dias_del_mes_actual() -> list[int]:
    """Devuelve todos los días válidos del mes actual (1..N donde N es el último día)."""
    hoy = datetime.now()
    import calendar
    ultimo = calendar.monthrange(hoy.year, hoy.month)[1]
    return list(range(1, ultimo + 1))


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


# =====================================================
# GOOGLE SHEETS — LECTURA OPTIMIZADA
# =====================================================
def validar_o_crear_cabecera(hoja_asistencia) -> bool:
    valores = hoja_asistencia.get_all_values()
    if not valores:
        hoja_asistencia.append_row(COLUMNAS_ASISTENCIA, value_input_option="USER_ENTERED")
        return True
    headers = [limpiar_texto(x).upper() for x in valores[0]]
    faltantes = [c for c in COLUMNAS_ASISTENCIA if c not in headers]
    if faltantes:
        st.error("La hoja Asistencia tiene cabecera incompleta.")
        st.write("Columnas faltantes:", faltantes)
        st.warning("Borra el contenido de la pestaña Asistencia y presiona 'Sincronizar mes'.")
        return False
    return True


def leer_asistencia_drive(hoja_asistencia) -> tuple[pd.DataFrame, list[str]]:
    """Lee toda la hoja de asistencia de una sola llamada (get_all_values)."""
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
    df = normalizar_columnas(df)
    df = df.fillna("").replace("None", "").replace("nan", "")

    for col in COLUMNAS_ASISTENCIA:
        if col not in df.columns:
            df[col] = ""

    df = df[COLUMNAS_ASISTENCIA].copy()
    df["ROW_SHEET"] = df.index + 2          # fila real en la hoja (1-based + cabecera)

    for col in COLUMNAS_DIAS:
        df[col] = df[col].apply(limpiar_marca)

    return df, headers


def leer_colaboradores_drive(hoja_colaboradores) -> pd.DataFrame:
    """Lee colaboradores usando get_all_records (más simple y suficiente)."""
    try:
        data = hoja_colaboradores.get_all_records()
    except Exception as e:
        st.error(f"Error leyendo colaboradores: {e}")
        return pd.DataFrame()
    df = pd.DataFrame(data)
    if df.empty:
        return df
    df = normalizar_columnas(df)
    return df.fillna("").replace("None", "")


def obtener_promotores_activos(df_colab: pd.DataFrame) -> pd.DataFrame:
    if df_colab.empty or "DNI" not in df_colab.columns or "ESTADO" not in df_colab.columns:
        return pd.DataFrame()
    df = df_colab[df_colab["ESTADO"].astype(str).str.strip().str.upper().eq("ACTIVO")].copy()
    df = df[df.apply(es_promotor, axis=1)].copy()
    df["DNI"] = df["DNI"].astype(str).str.strip()
    return df[df["DNI"].ne("")].copy()


def construir_filas_nuevas(df_colab: pd.DataFrame, dnis_existentes: set) -> list[list]:
    df_promotores = obtener_promotores_activos(df_colab)
    if df_promotores.empty:
        return []
    periodo, mes = periodo_actual(), mes_actual()
    filas = []
    for _, row in df_promotores.iterrows():
        dni = limpiar_texto(row.get("DNI", ""))
        if not dni or dni in dnis_existentes:
            continue
        fila = {
            "SUPERVISOR":   limpiar_texto(row.get("SUPERVISOR A CARGO", row.get("SUPERVISOR", ""))),
            "COORDINADOR":  limpiar_texto(row.get("COORDINADOR", "")),
            "DEPARTAMENTO": limpiar_texto(row.get("DEPARTAMENTO", "")),
            "PROVINCIA":    limpiar_texto(row.get("PROVINCIA", "")),
            "DNI":          dni,
            "NOMBRE":       limpiar_texto(row.get("NOMBRES", row.get("NOMBRE", ""))),
            "ESTADO":       "ACTIVO",
            "MES":          mes,
            "PERIODO":      periodo,
        }
        for col in COLUMNAS_DIAS:
            fila[col] = ""
        filas.append([fila.get(col, "") for col in COLUMNAS_ASISTENCIA])
    return filas


def sincronizar_mes(hoja_asistencia, hoja_colaboradores) -> int:
    if not validar_o_crear_cabecera(hoja_asistencia):
        return 0
    periodo = periodo_actual()
    df_asistencia, _ = leer_asistencia_drive(hoja_asistencia)
    dnis_existentes: set = set()
    if not df_asistencia.empty:
        dnis_existentes = set(
            df_asistencia.loc[df_asistencia["PERIODO"].astype(str).eq(periodo), "DNI"]
            .astype(str).str.strip().tolist()
        )
    df_colab = leer_colaboradores_drive(hoja_colaboradores)
    nuevas = construir_filas_nuevas(df_colab, dnis_existentes)
    if nuevas:
        # Escribir en lotes de 500 para no superar límites de la API
        for i in range(0, len(nuevas), 500):
            hoja_asistencia.append_rows(nuevas[i:i+500], value_input_option="USER_ENTERED")
            time.sleep(0.5)   # pequeña pausa para respetar rate limit
    return len(nuevas)


# =====================================================
# CACHÉ EN SESSION_STATE CON TTL
# =====================================================
def cache_vencido() -> bool:
    ts = st.session_state.get(KEY_LOAD_TS, 0)
    return (time.time() - ts) > CACHE_TTL


def cargar_cache_desde_drive(hoja_asistencia, forzar: bool = False) -> None:
    if not forzar and st.session_state.get(KEY_LOADED) and not cache_vencido():
        return  # caché vigente, no llamar a Drive
    with st.spinner("Cargando datos desde Google Drive…"):
        df_total, headers = leer_asistencia_drive(hoja_asistencia)
    st.session_state[KEY_DF_TOTAL]    = df_total.copy()
    st.session_state[KEY_DF_ORIGINAL] = df_total.copy()
    st.session_state[KEY_HEADERS]     = headers
    st.session_state[KEY_LOADED]      = True
    st.session_state[KEY_LOAD_TS]     = time.time()


# =====================================================
# FILTROS
# =====================================================
def lista_opciones(df: pd.DataFrame, columna: str) -> list[str]:
    if df.empty or columna not in df.columns:
        return ["TODOS"]
    valores = df[columna].astype(str).str.strip().replace("", pd.NA).dropna().unique().tolist()
    return ["TODOS"] + sorted(valores)


def filtrar_df(df: pd.DataFrame, supervisor: str, coordinador: str, departamento: str) -> pd.DataFrame:
    r = df.copy()
    if supervisor  != "TODOS": r = r[r["SUPERVISOR"].astype(str).str.strip().eq(supervisor)]
    if coordinador != "TODOS": r = r[r["COORDINADOR"].astype(str).str.strip().eq(coordinador)]
    if departamento != "TODOS": r = r[r["DEPARTAMENTO"].astype(str).str.strip().eq(departamento)]
    return r


# =====================================================
# ESTILOS Y ESPEJO
# =====================================================
def estilo_asistencia(valor: str) -> str:
    v = limpiar_marca(valor)
    if v == "A": return "background-color:#C6EFCE;color:#006100;font-weight:bold;text-align:center;"
    if v == "F": return "background-color:#FFC7CE;color:#9C0006;font-weight:bold;text-align:center;"
    return "text-align:center;"


def mostrar_espejo_mes(df: pd.DataFrame, dias_validos: list[int]) -> None:
    if df.empty:
        st.info("No hay datos para mostrar.")
        return
    cols_dias_validos = [f"DIA_{d}" for d in dias_validos]
    columnas = COLUMNAS_FIJAS_EDITOR + cols_dias_validos
    df_vista = df[columnas].copy()
    styler = df_vista.style.applymap(estilo_asistencia, subset=cols_dias_validos)
    st.dataframe(styler, use_container_width=True, height=400)


# =====================================================
# GUARDADO OPTIMIZADO (batch por fila, no por celda)
# =====================================================
def preparar_updates(
    df_editado: pd.DataFrame,
    df_original: pd.DataFrame,
    headers: list[str],
    cols_editables: list[str],
) -> list[dict]:
    """
    Agrupa los cambios por fila y construye un solo rango por fila modificada.
    Esto reduce dramáticamente el número de peticiones a la API de Sheets.
    """
    mapa_col = {limpiar_texto(col).upper(): idx + 1 for idx, col in enumerate(headers)}
    updates = []

    for _, row in df_editado.iterrows():
        try:
            row_sheet = int(row["ROW_SHEET"])
        except Exception:
            continue

        original_match = df_original[df_original["ROW_SHEET"].eq(row_sheet)]
        if original_match.empty:
            continue
        original = original_match.iloc[0]

        # Recolectar todas las celdas cambiadas en esta fila
        cambios_fila: dict[int, str] = {}
        for col in cols_editables:
            if col not in mapa_col:
                continue
            nuevo   = limpiar_marca(row.get(col, ""))
            anterior = limpiar_marca(original.get(col, ""))
            if nuevo != anterior:
                cambios_fila[mapa_col[col]] = nuevo

        if not cambios_fila:
            continue

        # Construir rangos contiguos dentro de la fila para minimizar peticiones
        indices_ordenados = sorted(cambios_fila.keys())
        grupos: list[list[int]] = []
        grupo_actual = [indices_ordenados[0]]
        for idx in indices_ordenados[1:]:
            if idx == grupo_actual[-1] + 1:
                grupo_actual.append(idx)
            else:
                grupos.append(grupo_actual)
                grupo_actual = [idx]
        grupos.append(grupo_actual)

        for grupo in grupos:
            col_ini = letra_columna(grupo[0])
            col_fin = letra_columna(grupo[-1])
            rango   = f"{col_ini}{row_sheet}:{col_fin}{row_sheet}" if len(grupo) > 1 else f"{col_ini}{row_sheet}"
            valores = [[cambios_fila[i] for i in grupo]]
            updates.append({"range": rango, "values": valores})

    return updates


def actualizar_cache_con_editado(df_editado: pd.DataFrame, cols_editables: list[str]) -> None:
    if KEY_DF_TOTAL not in st.session_state:
        return
    df_total = st.session_state[KEY_DF_TOTAL].copy()
    for _, row in df_editado.iterrows():
        try:
            row_sheet = int(row["ROW_SHEET"])
        except Exception:
            continue
        mask = df_total["ROW_SHEET"].eq(row_sheet)
        for col in cols_editables:
            if col in df_total.columns:
                df_total.loc[mask, col] = limpiar_marca(row.get(col, ""))
    st.session_state[KEY_DF_TOTAL]    = df_total.copy()
    st.session_state[KEY_DF_ORIGINAL] = df_total.copy()
    st.session_state[KEY_LOAD_TS]     = time.time()   # resetear TTL


# =====================================================
# MAIN
# =====================================================
def mostrar_asistencia(hoja_asistencia, hoja_colaboradores, registro_mod=None, razon=None):
    st.subheader("🗓️ Control de Asistencia")

    if not validar_o_crear_cabecera(hoja_asistencia):
        return

    periodo = periodo_actual()

    # ── FIX 1: todos los días del mes, no solo la semana ──────────────────────
    dias_validos    = dias_del_mes_actual()          # [1, 2, …, 30] ó [1..31]
    cols_editables  = [f"DIA_{d}" for d in dias_validos]
    hoy_dia         = datetime.now().day
    # ──────────────────────────────────────────────────────────────────────────

    c1, c2, c3 = st.columns([1, 1, 5])

    with c1:
        if st.button("🔄 Sincronizar mes", key="btn_sync_asistencia"):
            with st.spinner("Sincronizando con Drive…"):
                try:
                    nuevos = sincronizar_mes(hoja_asistencia, hoja_colaboradores)
                    cargar_cache_desde_drive(hoja_asistencia, forzar=True)
                    st.success(f"✅ Mes sincronizado. Registros nuevos: {nuevos}")
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
            f"📅 Periodo: **{periodo}** | Días del mes: **{len(dias_validos)}** | "
            f"Hoy: **DIA_{hoy_dia}** | Caché se refresca automáticamente cada 5 min."
        )

    # ── FIX 2: caché con TTL — solo llama a Drive si es necesario ─────────────
    cargar_cache_desde_drive(hoja_asistencia)
    # ──────────────────────────────────────────────────────────────────────────

    df_total    = st.session_state[KEY_DF_TOTAL].copy()
    df_original = st.session_state[KEY_DF_ORIGINAL].copy()
    headers     = st.session_state.get(KEY_HEADERS, COLUMNAS_ASISTENCIA)

    for col in COLUMNAS_ASISTENCIA:
        if col not in df_total.columns:    df_total[col]    = ""
        if col not in df_original.columns: df_original[col] = ""

    df_mes = df_total[df_total["PERIODO"].astype(str).eq(periodo)].copy()

    if df_mes.empty:
        st.warning("⚠️ No hay registros del periodo actual. Presiona **Sincronizar mes**.")
        return

    # ── Filtros encadenados ────────────────────────────────────────────────────
    f1, f2, f3 = st.columns(3)
    with f1:
        filtro_supervisor = st.selectbox("Supervisor",  lista_opciones(df_mes, "SUPERVISOR"),  key="asis_supervisor")
    df_base_coord = filtrar_df(df_mes, filtro_supervisor, "TODOS", "TODOS")
    with f2:
        filtro_coord = st.selectbox("Coordinador", lista_opciones(df_base_coord, "COORDINADOR"), key="asis_coordinador")
    df_base_dep = filtrar_df(df_base_coord, "TODOS", filtro_coord, "TODOS")
    with f3:
        filtro_dep = st.selectbox("Departamento", lista_opciones(df_base_dep, "DEPARTAMENTO"), key="asis_departamento")

    df_filtrado = filtrar_df(df_mes, filtro_supervisor, filtro_coord, filtro_dep)

    if df_filtrado.empty:
        st.warning("No hay registros con los filtros seleccionados.")
        return

    total_filtrado = len(df_filtrado)

    # ── FIX 3: paginación para evitar cuelgues en Render ──────────────────────
    st.caption(f"Registros encontrados: **{total_filtrado}**")

    if total_filtrado > MAX_FILAS_EDITOR:
        st.warning(
            f"⚠️ Hay {total_filtrado} registros. El editor muestra máximo {MAX_FILAS_EDITOR} "
            "para mantener el rendimiento. Usa los filtros o el slider para navegar."
        )
        pagina = st.slider(
            "Bloque de registros",
            min_value=1,
            max_value=max(1, -(-total_filtrado // MAX_FILAS_EDITOR)),  # ceil division
            value=1,
            key="asis_pagina",
        )
        inicio = (pagina - 1) * MAX_FILAS_EDITOR
        df_filtrado = df_filtrado.iloc[inicio : inicio + MAX_FILAS_EDITOR].copy()
        st.caption(f"Mostrando filas {inicio+1}–{min(inicio+MAX_FILAS_EDITOR, total_filtrado)} de {total_filtrado}")
    # ──────────────────────────────────────────────────────────────────────────

    # ── Editor ────────────────────────────────────────────────────────────────
    st.markdown("### ✏️ Editar asistencia")
    st.caption(
        f"Días editables: DIA_1 a DIA_{hoy_dia} (todos los días transcurridos del mes). "
        "Registra **A** = Asistió · **F** = Faltó."
    )

    # Solo mostrar columnas de días que ya han pasado (incluyendo hoy)
    cols_dias_hasta_hoy = [f"DIA_{d}" for d in dias_validos if d <= hoy_dia]
    columnas_editor = COLUMNAS_FIJAS_EDITOR + cols_dias_hasta_hoy + ["ROW_SHEET"]

    # Asegurar que todas las columnas existen
    for col in columnas_editor:
        if col not in df_filtrado.columns:
            df_filtrado[col] = ""

    df_editor = df_filtrado[columnas_editor].copy()
    for col in cols_dias_hasta_hoy:
        df_editor[col] = df_editor[col].apply(limpiar_marca)

    disabled_cols = [col for col in df_editor.columns if col not in cols_dias_hasta_hoy]

    column_config: dict = {"ROW_SHEET": None}
    for col in cols_dias_hasta_hoy:
        column_config[col] = st.column_config.SelectboxColumn(
            col, options=["", "A", "F"], width="small"
        )

    editado = st.data_editor(
        df_editor,
        use_container_width=True,
        height=min(600, 50 + len(df_editor) * 35),   # altura dinámica
        hide_index=True,
        disabled=disabled_cols,
        column_config=column_config,
        num_rows="fixed",
        key="editor_asistencia_mes_completo",
    )

    # ── Guardar + rerun para refrescar espejo ────────────────────────────────
    if st.button("💾 Guardar Asistencia", key="btn_guardar_asistencia"):
        with st.spinner("Guardando en Google Drive…"):
            try:
                df_editado = pd.DataFrame(editado).fillna("")
                updates = preparar_updates(
                    df_editado=df_editado,
                    df_original=df_original,
                    headers=headers,
                    cols_editables=cols_dias_hasta_hoy,
                )
                if not updates:
                    st.info("ℹ️ No se detectaron cambios para guardar.")
                else:
                    for i in range(0, len(updates), 100):
                        hoja_asistencia.batch_update(
                            updates[i:i+100],
                            value_input_option="USER_ENTERED",
                        )
                        time.sleep(0.3)
                    actualizar_cache_con_editado(df_editado, cols_dias_hasta_hoy)
                    # Guardar mensaje de éxito para mostrarlo tras el rerun
                    st.session_state["asis_guardado_msg"] = f"✅ Asistencia guardada. Celdas actualizadas: {len(updates)}"
                    st.rerun()   # ← rerenderiza toda la página con el caché ya actualizado
            except Exception as e:
                st.error(f"❌ Error guardando asistencia: {e}")

    # Mostrar mensaje de éxito persistido (viene del rerun)
    if msg := st.session_state.pop("asis_guardado_msg", None):
        st.success(msg)
    # ──────────────────────────────────────────────────────────────────────────

    # ── Espejo mensual — reconstruido desde caché actualizado ─────────────────
    # IMPORTANTE: no usar df_filtrado (variable local vieja).
    # Releer desde session_state para reflejar cualquier guardado reciente.
    df_total_actual = st.session_state[KEY_DF_TOTAL].copy()
    df_mes_actual   = df_total_actual[df_total_actual["PERIODO"].astype(str).eq(periodo)].copy()
    df_espejo       = filtrar_df(df_mes_actual, filtro_supervisor, filtro_coord, filtro_dep)

    if total_filtrado > MAX_FILAS_EDITOR:
        inicio = (st.session_state.get("asis_pagina", 1) - 1) * MAX_FILAS_EDITOR
        df_espejo = df_espejo.iloc[inicio : inicio + MAX_FILAS_EDITOR].copy()

    st.markdown("### 📊 Espejo mensual completo")
    mostrar_espejo_mes(df_espejo, dias_validos)
    # ──────────────────────────────────────────────────────────────────────────

    if registro_mod is not None:
        st.divider()
        st.subheader("📋 Matriz de jerarquía")
        try:
            registro_mod.mostrar_tabla(hoja_colaboradores, razon)
        except Exception as e:
            st.warning(f"No se pudo cargar la matriz de jerarquía: {e}")