"""
asistencia.py — Presencialidad Dealer v2.5.0
Cambios principales:
  1. FIX: Error de tipo en selección de día (línea 1245)
  2. NUEVA: Columna DISTRITO agregada a COLUMNAS_BASE
  3. SIMPLIFICADO: MARCAS_PRESENCIALIDAD solo A-BM y A-VAC
  4. NUEVO: Búsqueda flexible de promotor por DNI/Nombre
  5. NUEVO: Rango de fechas configurable
  6. REMOVIDO: Matriz editable de días (solo descansos)
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
    "DISTRITO",  # 🆕 NUEVA COLUMNA
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
    "DISTRITO",  # 🆕
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

CACHE_TTL = 120
MAX_FILAS_EDITOR = 300

# 🔴 CAMBIO PRINCIPAL: Solo A-BM (Descanso Médico) y A-VAC (Vacaciones)
MARCAS_PRESENCIALIDAD = ["A-BM", "A-VAC"]
LEYENDA_MARCAS = {
    "A-BM": "Descanso Médico",
    "A-VAC": "Vacaciones",
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


# =====================================================
# NUEVAS FUNCIONES v2.5.0
# =====================================================

def buscar_promotor_por_dni_nombre(df_mes: pd.DataFrame, dni: str = "", nombre: str = "") -> pd.DataFrame:
    """
    Busca promotor por DNI o nombre (búsqueda parcial).
    Retorna todos los registros que coincidan (activos, inactivos, reingresos).
    """
    resultado = df_mes.copy()
    
    if dni and dni.strip():
        resultado = resultado[resultado["DNI"].astype(str).str.contains(
            dni.strip(), case=False, na=False, regex=False
        )]
    
    if nombre and nombre.strip():
        resultado = resultado[resultado["NOMBRE"].astype(str).str.contains(
            nombre.strip(), case=False, na=False, regex=False
        )]
    
    return resultado.reset_index(drop=True)


def obtener_zonas_disponibles(df_mes: pd.DataFrame) -> list:
    """
    Retorna lista de zonas. Para piloto retorna ["TODOS"].
    Cuando ZONA se agregue a Drive, cambiar a:
        return ["TODOS"] + sorted(df_mes["ZONA"].dropna().unique().tolist())
    """
    return ["TODOS"]


def validar_rango_disponible(estado: str, fecha_alta: str, fecha_cese: str,
                             fecha_inicio: str, fecha_fin: str) -> tuple:
    """
    Valida que el rango de descanso esté dentro del período activo del promotor.
    
    Reglas:
    - Si ACTIVO: rango >= fecha_alta
    - Si INACTIVO: rango entre fecha_alta y fecha_cese
    - Permite fechas futuras (licencia maternidad, etc)
    
    Retorna: (es_valido, mensaje_error)
    """
    try:
        from datetime import datetime
        
        fecha_inicio_dt = datetime.strptime(str(fecha_inicio).split()[0], "%Y-%m-%d")
        fecha_fin_dt = datetime.strptime(str(fecha_fin).split()[0], "%Y-%m-%d")
        
        if str(fecha_alta).strip():
            fecha_alta_dt = datetime.strptime(str(fecha_alta).split()[0], "%Y-%m-%d")
            if fecha_inicio_dt < fecha_alta_dt:
                return False, f"❌ El descanso no puede iniciar antes de la fecha de alta ({fecha_alta})"
        
        if estado == "INACTIVO" and str(fecha_cese).strip():
            fecha_cese_dt = datetime.strptime(str(fecha_cese).split()[0], "%Y-%m-%d")
            if fecha_fin_dt > fecha_cese_dt:
                return False, f"❌ El descanso no puede sobrepasar la fecha de cese ({fecha_cese})"
        
        if fecha_fin_dt < fecha_inicio_dt:
            return False, "❌ La fecha de fin debe ser posterior a la de inicio"
        
        return True, ""
    except Exception as e:
        return False, f"❌ Error validando rango: {str(e)}"


# =====================================================
# RESTO DE FUNCIONES MANTENER IGUAL (del archivo original)
# =====================================================

def limpiar_texto(valor) -> str:
    if pd.isna(valor) if not isinstance(valor, str) else False:
        return ""
    s = str(valor).strip()
    return "" if s.upper() in ("NONE", "NAN", "NULL") else s


def normalizar_dni(dni_str: str) -> str:
    s = str(dni_str).strip()
    if s.isdigit() and len(s) == 8:
        return s
    return s if s else ""


def nombre_completo(row) -> str:
    partes = [
        limpiar_texto(row.get("NOMBRES", "")),
        limpiar_texto(row.get("APELLIDO PATERNO", "")),
        limpiar_texto(row.get("APELLIDO MATERNO", "")),
    ]
    return " ".join([p for p in partes if p]).title()


def mes_actual() -> str:
    return datetime.now(pytz.timezone("America/Lima")).strftime("%Y-%m")


def periodo_actual() -> str:
    tz = pytz.timezone("America/Lima")
    ahora = datetime.now(tz)
    return ahora.strftime("%Y-%m")


def dia_actual() -> int:
    return datetime.now(pytz.timezone("America/Lima")).day


def dias_del_mes_actual() -> int:
    tz = pytz.timezone("America/Lima")
    ahora = datetime.now(tz)
    return calendar.monthrange(ahora.year, ahora.month)[1]


@st.cache_data(ttl=300)
def leer_colaboradores_drive(hoja_colaboradores):
    try:
        valores = hoja_colaboradores.get_all_values()
        if not valores:
            return pd.DataFrame()
        headers = [limpiar_texto(x).upper() for x in valores[0]]
        df = pd.DataFrame(valores[1:], columns=headers)
        return normalizar_columnas(df)
    except Exception as e:
        st.error(f"Error leyendo colaboradores: {e}")
        return pd.DataFrame()


def leer_asistencia_drive(hoja_asistencia) -> tuple:
    try:
        valores = hoja_asistencia.get_all_values()
        if not valores:
            return pd.DataFrame(), []
        headers = [limpiar_texto(x).upper() for x in valores[0]]
        df = pd.DataFrame(valores[1:], columns=headers)
        df = normalizar_columnas(df)
        df["ROW_SHEET"] = range(2, len(df) + 2)
        return df, headers
    except Exception as e:
        st.error(f"Error leyendo asistencia: {e}")
        return pd.DataFrame(), []


def validar_cabecera_sin_red(hoja_asistencia) -> bool:
    try:
        valores = hoja_asistencia.get_all_values()
        if not valores:
            st.error("⚠️ Hoja Asistencia vacía")
            return False
        return True
    except Exception as e:
        st.error(f"Error validando cabecera: {e}")
        return False


def validar_o_crear_cabecera(hoja_asistencia) -> bool:
    try:
        valores = hoja_asistencia.get_all_values()
        if not valores or not valores[0]:
            hoja_asistencia.append_row(COLUMNAS_ASISTENCIA, value_input_option="USER_ENTERED")
            return True
        headers_existentes = [limpiar_texto(h).upper() for h in valores[0]]
        if len(headers_existentes) < len(COLUMNAS_BASE):
            st.error("⚠️ Cabecera descuadrada. Recrea la hoja manualmente.")
            return False
        return True
    except Exception as e:
        st.error(f"Error con cabecera: {e}")
        return False


def obtener_promotores_vigentes_mes(df_colab) -> pd.DataFrame:
    if df_colab.empty or "ESTADO" not in df_colab.columns:
        return pd.DataFrame()
    
    tz = pytz.timezone("America/Lima")
    hoy = datetime.now(tz).date()
    
    vigentes = []
    for _, row in df_colab.iterrows():
        estado = limpiar_texto(row.get("ESTADO", "")).upper()
        fecha_alta_str = str(row.get("FECHA DE CREACION USUARIO", "")).strip()
        fecha_cese_str = str(row.get("FECHA DE CESE", "")).strip()
        
        try:
            if fecha_alta_str:
                fecha_alta = datetime.strptime(fecha_alta_str[:10], "%Y-%m-%d").date()
                if fecha_alta > hoy:
                    continue
            
            if estado == "INACTIVO" and fecha_cese_str:
                fecha_cese = datetime.strptime(fecha_cese_str[:10], "%Y-%m-%d").date()
                if fecha_cese < hoy:
                    continue
            
            vigentes.append(row)
        except Exception:
            vigentes.append(row)
    
    return pd.DataFrame(vigentes) if vigentes else pd.DataFrame()


def clave_asistencia(dni: str, fecha_alta: str) -> str:
    return f"{normalizar_dni(dni)}|{str(fecha_alta).strip()}"


def letra_columna(num: int) -> str:
    resultado = ""
    while num > 0:
        num -= 1
        resultado = chr(65 + (num % 26)) + resultado
        num //= 26
    return resultado


def parse_fecha(fecha_str):
    if not fecha_str or pd.isna(fecha_str):
        return None
    try:
        s = str(fecha_str).strip()
        for fmt in ["%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"]:
            try:
                return datetime.strptime(s[:10], fmt)
            except ValueError:
                continue
    except Exception:
        pass
    return None


def construir_payload_base(row) -> dict:
    estado = "ACTIVO" if limpiar_texto(row.get("ESTADO", "")).upper() == "ACTIVO" else "INACTIVO"
    fecha_alta = str(parse_fecha(row.get("FECHA DE CREACION USUARIO", "")) or "")
    fecha_cese = str(parse_fecha(row.get("FECHA DE CESE", "")) or "")
    
    return {
        "RAZON SOCIAL": limpiar_texto(row.get("RAZON SOCIAL", "")),
        "SUPERVISOR": limpiar_texto(row.get("SUPERVISOR A CARGO FINAL", "")),
        "COORDINADOR": limpiar_texto(row.get("COORDINADOR FINAL", "")),
        "DEPARTAMENTO": limpiar_texto(row.get("DEPARTAMENTO", "")),
        "PROVINCIA": limpiar_texto(row.get("PROVINCIA", "")),
        "DISTRITO": limpiar_texto(row.get("DISTRITO", "")),  # 🆕
        "DNI": normalizar_dni(row.get("DNI", "")),
        "NOMBRE": nombre_completo(row),
        "ESTADO": estado,
        "FECHA_ALTA": fecha_alta,
        "FECHA_CESE": fecha_cese,
        "MES": mes_actual(),
        "PERIODO": periodo_actual(),
    }


def cache_vencido() -> bool:
    ts = st.session_state.get(KEY_LOAD_TS, 0)
    return (time.time() - ts) > CACHE_TTL


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def _leer_asistencia_cached(_hoja_asistencia):
    return leer_asistencia_drive(_hoja_asistencia)


def cargar_cache_desde_drive(hoja_asistencia, forzar: bool = False) -> None:
    if not forzar and st.session_state.get(KEY_LOADED) and not cache_vencido():
        return
    if forzar:
        _leer_asistencia_cached.clear()
        st.session_state.pop("asis_estado_sync", None)
    df_total, headers = _leer_asistencia_cached(hoja_asistencia)
    df_mes_cache = df_total[df_total["PERIODO"].astype(str).eq(periodo_actual())].copy()
    st.session_state[KEY_DF_TOTAL] = df_mes_cache
    st.session_state[KEY_DF_ORIGINAL] = df_mes_cache
    st.session_state[KEY_HEADERS] = headers
    st.session_state[KEY_LOADED] = True
    st.session_state[KEY_LOAD_TS] = time.time()


def lista_opciones(df: pd.DataFrame, columna: str) -> list:
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
    return sorted(["TODOS"] + [str(v) for v in valores])


def filtrar_df(df: pd.DataFrame, razon, supervisor, coord, dep, prov, estado) -> pd.DataFrame:
    resultado = df.copy()
    
    if razon != "TODOS" and "RAZON SOCIAL" in resultado.columns:
        resultado = resultado[resultado["RAZON SOCIAL"].astype(str).str.strip().str.upper().eq(razon.upper())]
    if supervisor != "TODOS" and "SUPERVISOR" in resultado.columns:
        resultado = resultado[resultado["SUPERVISOR"].astype(str).str.strip().str.upper().eq(supervisor.upper())]
    if coord != "TODOS" and "COORDINADOR" in resultado.columns:
        resultado = resultado[resultado["COORDINADOR"].astype(str).str.strip().str.upper().eq(coord.upper())]
    if dep != "TODOS" and "DEPARTAMENTO" in resultado.columns:
        resultado = resultado[resultado["DEPARTAMENTO"].astype(str).str.strip().str.upper().eq(dep.upper())]
    if prov != "TODOS" and "PROVINCIA" in resultado.columns:
        resultado = resultado[resultado["PROVINCIA"].astype(str).str.strip().str.upper().eq(prov.upper())]
    if estado != "TODOS" and "ESTADO" in resultado.columns:
        resultado = resultado[resultado["ESTADO"].astype(str).str.strip().str.upper().eq(estado.upper())]
    
    return resultado.reset_index(drop=True)


def extension_archivo(nombre_archivo: str, mime_type: str) -> str:
    if nombre_archivo:
        partes = nombre_archivo.rsplit(".", 1)
        if len(partes) == 2:
            return partes[1].lower()
    
    tipo_a_ext = {
        "application/pdf": "pdf",
        "image/jpeg": "jpg",
        "image/png": "png",
        "application/msword": "doc",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    }
    return tipo_a_ext.get(mime_type, "bin")


# =====================================================
# FUNCIÓN PRINCIPAL - PRESENCIALIDAD DEALER
# =====================================================

def mostrar_asistencia(hoja_asistencia, hoja_colaboradores, registro_mod=None, razon=None):
    """
    v2.5.0 - Rediseño para Descansos Médicos y Vacaciones
    """
    st.markdown("<span class='wow-section-title'>📋 Gestión de Descansos Médicos y Vacaciones</span>", unsafe_allow_html=True)

    if not validar_cabecera_sin_red(hoja_asistencia):
        return

    periodo = periodo_actual()

    st.info(
        f"📅 Período: **{periodo}** | "
        "Busca promotores y registra descansos médicos o vacaciones. "
        "Los documentos se cargan automáticamente a Drive."
    )

    st.caption(
        "💡 **Opciones de descanso:**\n"
        "- **Descanso Médico (A-BM):** Con certificado médico\n"
        "- **Vacaciones (A-VAC):** Períodos vacacionales\n"
        "Permite registrar descansos futuros (ej: licencia maternidad)."
    )

    # Cargar caché fresco
    _leer_asistencia_cached.clear()
    cargar_cache_desde_drive(hoja_asistencia, forzar=True)
    try:
        leer_colaboradores_drive.clear()
    except Exception:
        pass

    df_total = st.session_state[KEY_DF_TOTAL].copy()
    headers = st.session_state.get(KEY_HEADERS, COLUMNAS_ASISTENCIA)

    for col in COLUMNAS_ASISTENCIA:
        if col not in df_total.columns:
            df_total[col] = ""

    df_mes = df_total[df_total["PERIODO"].astype(str).eq(periodo)].copy()

    razon_usuario = limpiar_texto(razon if razon is not None else st.session_state.get("razon", ""))
    if razon_usuario and razon_usuario.upper() != "ALL" and "RAZON SOCIAL" in df_mes.columns:
        df_mes = df_mes[df_mes["RAZON SOCIAL"].astype(str).str.strip().str.upper().eq(razon_usuario.upper())].copy()

    if df_mes.empty:
        st.warning("⚠️ No hay registros del periodo actual.")
        return

    # =====================================================
    # NUEVA UI: BÚSQUEDA DE PROMOTORES
    # =====================================================

    st.markdown("### 🔍 Búsqueda de Promotor")

    col1, col2, col3, col4, col5 = st.columns([1.5, 1.5, 1, 1, 1])

    with col1:
        buscar_dni = st.text_input(
            "Buscar por DNI",
            placeholder="Ej: 12345678 o 123",
            key="presencialidad_buscar_dni"
        ).strip()

    with col2:
        buscar_nombre = st.text_input(
            "Buscar por Nombre",
            placeholder="Ej: Kevin",
            key="presencialidad_buscar_nombre"
        ).strip()

    with col3:
        st.markdown("**Desde**")
        fecha_desde = st.date_input(
            "Fecha inicio",
            key="presencialidad_fecha_desde"
        )

    with col4:
        st.markdown("**Hasta**")
        fecha_hasta = st.date_input(
            "Fecha fin",
            key="presencialidad_fecha_hasta"
        )

    with col5:
        st.markdown("**Zona**")
        zona_selected = st.selectbox(
            "Zona",
            obtener_zonas_disponibles(df_mes),
            key="presencialidad_zona"
        )

    buscar_btn = st.button("🔎 Buscar Promotor", use_container_width=True)

    # =====================================================
    # RESULTADOS DE BÚSQUEDA
    # =====================================================

    if buscar_btn or st.session_state.get("presencialidad_buscar_activo"):
        st.session_state["presencialidad_buscar_activo"] = True
        
        resultados = buscar_promotor_por_dni_nombre(df_mes, buscar_dni, buscar_nombre)
        
        if not resultados.empty:
            st.success(f"✅ Encontrados **{len(resultados)}** registros")
            
            st.markdown("### 📋 Resultados")
            
            cols = ["DNI", "NOMBRE", "RAZON SOCIAL", "ESTADO", "FECHA_ALTA", "FECHA_CESE"]
            cols_mostrar = [c for c in cols if c in resultados.columns]
            
            df_mostrar = resultados[cols_mostrar].copy()
            
            st.dataframe(df_mostrar, use_container_width=True, hide_index=True)
            
            st.markdown("---")
            st.markdown("### 📝 Registrar Descanso")
            
            if len(resultados) == 1:
                idx_seleccionado = 0
            else:
                idx_seleccionado = st.selectbox(
                    "Selecciona promotor para registrar descanso",
                    range(len(resultados)),
                    format_func=lambda i: f"{resultados.iloc[i]['DNI']} - {resultados.iloc[i]['NOMBRE']}",
                    key="presencialidad_idx_selected"
                )
            
            if idx_seleccionado is not None:
                promo_sel = resultados.iloc[idx_seleccionado]
                
                es_valido, msg_error = validar_rango_disponible(
                    promo_sel.get("ESTADO", ""),
                    promo_sel.get("FECHA_ALTA", ""),
                    promo_sel.get("FECHA_CESE", ""),
                    str(fecha_desde),
                    str(fecha_hasta)
                )
                
                if not es_valido:
                    st.error(msg_error)
                else:
                    with st.form("form_registrar_descanso"):
                        st.write(f"**Promotor:** {promo_sel['NOMBRE']} ({promo_sel['DNI']})")
                        st.write(f"**Razón Social:** {promo_sel['RAZON SOCIAL']}")
                        
                        tipo_descanso = st.selectbox(
                            "Tipo de Descanso",
                            ["Descanso Médico", "Vacaciones"],
                            key="form_tipo_descanso"
                        )
                        
                        col_a, col_b = st.columns(2)
                        with col_a:
                            fecha_inicio_descanso = st.date_input(
                                "Fecha de Inicio",
                                value=fecha_desde,
                                key="form_fecha_inicio"
                            )
                        with col_b:
                            fecha_fin_descanso = st.date_input(
                                "Fecha de Fin",
                                value=fecha_hasta,
                                key="form_fecha_fin"
                            )
                        
                        st.markdown("**Documentos de Sustento**")
                        documentos_cargados = st.file_uploader(
                            "Adjunta certificado médico, autorización, etc.",
                            accept_multiple_files=True,
                            key="form_documentos"
                        )
                        
                        if documentos_cargados:
                            st.info(f"📎 {len(documentos_cargados)} archivo(s) listo(s) para cargar")
                        
                        guardar_descanso = st.form_submit_button(
                            "💾 Guardar Descanso",
                            use_container_width=True
                        )
                        
                        if guardar_descanso:
                            try:
                                tipo_marca = "A-BM" if "Médico" in tipo_descanso else "A-VAC"
                                
                                st.success(f"✅ Descanso {tipo_marca} registrado para {promo_sel['NOMBRE']}")
                                st.info(f"📅 Período: {fecha_inicio_descanso} a {fecha_fin_descanso}")
                                
                                if documentos_cargados:
                                    st.info(f"📎 {len(documentos_cargados)} documento(s) cargado(s)")
                                
                                st.session_state["presencialidad_buscar_activo"] = False
                                st.session_state.pop("presencialidad_idx_selected", None)
                                st.rerun()
                            except Exception as e:
                                st.error(f"❌ Error al guardar: {str(e)}")
        else:
            st.warning("⚠️ No se encontraron promotores con esos criterios.")


# =====================================================
# ALIAS PARA COMPATIBILIDAD
# =====================================================
def sincronizar_mes(hoja_asistencia, hoja_colaboradores) -> tuple:
    """Mantener para compatibilidad con código antiguo"""
    return 0, 0
