# FIX_CONFIRMACION_SUSTENTO_ABM_VISIBLE_20260602
# Presencialidad Dealer - 3 bloques:
# 1) Registrar presencialidad desde hoja Asistencia (rápido)
# 2) Espejo mensual / trazabilidad por día (solo lectura, bajo demanda)
# 3) Jerarquía completa para descarga (bajo demanda)
#
# BOTÓN "Actualizar cambios del Drive":
# - Lee colaboradores.
# - Agrega altas faltantes a Asistencia para el periodo seleccionado.
# - Actualiza datos base de filas existentes: estado, supervisor, coordinador, provincia, fecha cese, etc.
# - NO borra la hoja.
# - NO limpia DIA_1...DIA_31.
# - NO recrea Asistencia.

import calendar
import io
from datetime import datetime, date

import pandas as pd
import pytz
import streamlit as st

from sheets import subir_archivo_drive, obtener_o_crear_worksheet

NOMBRE_LIBRO = "maestra_vendedores"
HOJA_SUSTENTOS = "Sustentos_Bajas"
TZ_LIMA = pytz.timezone("America/Lima")
CACHE_TTL = 300
MAX_FILAS_EDITOR = 200

MARCAS_HOY = ["", "A", "A-BM", "A-VAC", "NA-SA", "NA-CA"]
MARCAS_RETRO = ["", "A-BM"]

BASE_COLS = [
    "RAZON SOCIAL", "DNI", "NOMBRE", "SUPERVISOR", "COORDINADOR",
    "DEPARTAMENTO", "PROVINCIA", "ESTADO", "FECHA_ALTA", "FECHA_CESE",
    "MES", "PERIODO"
]
DAY_COLS = [f"DIA_{i}" for i in range(1, 32)]
ALL_COLS = BASE_COLS + DAY_COLS

SUSTENTO_COLS = [
    "PERIODO", "DIA", "FECHA_ASISTENCIA", "DNI", "NOMBRE", "RAZON SOCIAL",
    "MOTIVO", "LINK_DOCUMENTO", "FECHA_SUBIDA", "USUARIO_REGISTRO"
]

CSS = """
<style>
.leyenda{background:#EFF6FF;border:1px solid #BFDBFE;border-radius:10px;padding:12px 16px;color:#0B4EA2;margin:8px 0 14px 0;font-size:13px}
.alerta{background:#FFF7ED;border:1px solid #FDBA74;border-radius:10px;padding:10px 14px;color:#9A3412;margin:8px 0;font-size:13px}
.okbox{background:#ECFDF5;border:1px solid #86EFAC;border-radius:10px;padding:10px 14px;color:#166534;margin:8px 0;font-size:13px}
.badbox{background:#FEF2F2;border:1px solid #FCA5A5;border-radius:10px;padding:10px 14px;color:#991B1B;margin:8px 0;font-size:13px}
.smallnote{color:#6B7280;font-size:12px;margin-top:4px}
</style>
"""

# =============================================================================
# Utilitarios
# =============================================================================
def hoy_lima() -> date:
    return datetime.now(TZ_LIMA).date()


def periodo_actual() -> str:
    h = hoy_lima()
    return f"{h.year}-{h.month:02d}"


def periodos_disponibles(n=6) -> list[str]:
    h = hoy_lima()
    out = []
    y, m = h.year, h.month
    for i in range(n):
        yy, mm = y, m - i
        while mm <= 0:
            yy -= 1
            mm += 12
        out.append(f"{yy}-{mm:02d}")
    return out


def dias_periodo(periodo: str) -> list[int]:
    y, m = map(int, periodo.split("-"))
    return list(range(1, calendar.monthrange(y, m)[1] + 1))


def fecha_periodo_dia(periodo: str, dia: int) -> date:
    y, m = map(int, periodo.split("-"))
    dia = min(int(dia), calendar.monthrange(y, m)[1])
    return date(y, m, dia)


def nt(v) -> str:
    if v is None:
        return ""
    try:
        if pd.isna(v):
            return ""
    except Exception:
        pass
    s = str(v).strip()
    if s.upper() in {"NAN", "NONE", "NULL"}:
        return ""
    return " ".join(s.split())


def nu(v) -> str:
    return nt(v).upper()


def nr(v) -> str:
    return nu(v).replace(".", "").replace("  ", " ").strip()


def nd(v) -> str:
    s = nt(v).replace(".0", "").replace(",", "").replace(" ", "")
    return s.zfill(8) if s.isdigit() and len(s) < 8 else s


def parse_fecha(v):
    if nt(v) == "":
        return None
    f = pd.to_datetime(v, errors="coerce")
    if pd.isna(f):
        return None
    return f.date()


def fs(v) -> str:
    f = parse_fecha(v)
    return str(f) if f else nt(v)


def limpiar_marca(v) -> str:
    s = nu(v)
    return s if s in {"A", "A-BM", "A-VAC", "NA-SA", "NA-CA"} else ""


def letra_col(n: int) -> str:
    out = ""
    while n:
        n, r = divmod(n - 1, 26)
        out = chr(65 + r) + out
    return out


def normalizar_headers(headers) -> list[str]:
    return [nu(h) for h in headers]


def worksheet_key(ws) -> str:
    try:
        return f"{ws.spreadsheet.id}:{ws.id}:{ws.title}"
    except Exception:
        return str(id(ws))


def nombre_completo(row: pd.Series) -> str:
    if nt(row.get("NOMBRE", "")):
        return nt(row.get("NOMBRE", ""))
    partes = [row.get("NOMBRES", ""), row.get("APELLIDO PATERNO", ""), row.get("APELLIDO MATERNO", "")]
    return " ".join([nt(x) for x in partes if nt(x)]).strip()


def es_promotor_d2d(cargo: str) -> bool:
    c = nu(cargo).replace("-", " ")
    return "PROMOTOR D2D" in c


def clave(dni, fecha_alta, periodo) -> str:
    return f"{nd(dni)}|{fs(fecha_alta)}|{periodo}"


def filtrar_razon(df: pd.DataFrame, razon: str) -> pd.DataFrame:
    if not razon or nu(razon) == "ALL" or "RAZON SOCIAL" not in df.columns:
        return df.copy()
    return df[df["RAZON SOCIAL"].map(nr).eq(nr(razon))].copy()

# =============================================================================
# Lectura cacheada
# =============================================================================
@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def _leer_asistencia_cached(_ws, ws_key: str) -> tuple[list[str], pd.DataFrame]:
    values = _ws.get_all_values()
    if not values:
        return ALL_COLS.copy(), pd.DataFrame(columns=ALL_COLS + ["FILA", "KEY"])
    headers = normalizar_headers(values[0])
    rows = values[1:]
    if not headers:
        return ALL_COLS.copy(), pd.DataFrame(columns=ALL_COLS + ["FILA", "KEY"])
    df = pd.DataFrame(rows, columns=headers[:len(rows[0])] if rows else headers) if rows else pd.DataFrame(columns=headers)
    # Si hay filas más cortas, reconstrucción segura:
    if rows:
        max_len = len(headers)
        fixed = [r + [""] * (max_len - len(r)) for r in rows]
        df = pd.DataFrame(fixed, columns=headers)
    df["FILA"] = range(2, len(df) + 2)
    for c in ALL_COLS:
        if c not in df.columns:
            df[c] = ""
    df["DNI"] = df["DNI"].map(nd)
    df["FECHA_ALTA"] = df["FECHA_ALTA"].map(fs)
    df["FECHA_CESE"] = df["FECHA_CESE"].map(fs)
    df["ESTADO"] = df["ESTADO"].map(lambda x: nu(x) or "ACTIVO")
    df["KEY"] = df.apply(lambda r: clave(r.get("DNI", ""), r.get("FECHA_ALTA", ""), r.get("PERIODO", "")), axis=1)
    for d in DAY_COLS:
        df[d] = df[d].map(limpiar_marca)
    return headers, df


def leer_asistencia(ws):
    return _leer_asistencia_cached(ws, worksheet_key(ws))


def limpiar_cache_asistencia():
    try:
        _leer_asistencia_cached.clear()
    except Exception:
        pass


def ensure_headers(ws, headers: list[str]) -> list[str]:
    headers = normalizar_headers(headers)
    if not headers or all(h == "" for h in headers):
        ws.update("A1", [ALL_COLS], value_input_option="USER_ENTERED")
        limpiar_cache_asistencia()
        return ALL_COLS.copy()
    faltantes = [c for c in ALL_COLS if c not in headers]
    if faltantes:
        start = len(headers) + 1
        end = len(headers) + len(faltantes)
        ws.update(f"{letra_col(start)}1:{letra_col(end)}1", [faltantes], value_input_option="USER_ENTERED")
        headers += faltantes
        limpiar_cache_asistencia()
    return headers

# =============================================================================
# Colaboradores y actualización no destructiva
# =============================================================================
def leer_colaboradores_df(hoja_colaboradores) -> pd.DataFrame:
    data = hoja_colaboradores.get_all_records()
    df = pd.DataFrame(data)
    if df.empty:
        return df
    df.columns = df.columns.astype(str).str.strip().str.upper()
    return df


def construir_base_desde_colaboradores(df_col: pd.DataFrame, periodo: str, razon: str) -> pd.DataFrame:
    if df_col.empty:
        return pd.DataFrame(columns=BASE_COLS + ["KEY"])
    df = df_col.copy()
    if "RAZON SOCIAL" in df.columns:
        df = filtrar_razon(df, razon)
    # Presencialidad solo promotores D2D. La descarga de jerarquía puede mostrar todo aparte.
    col_cargo = "CARGO (ROL)" if "CARGO (ROL)" in df.columns else "CARGO" if "CARGO" in df.columns else None
    if col_cargo:
        df = df[df[col_cargo].astype(str).map(es_promotor_d2d)].copy()
    out = pd.DataFrame(index=df.index)
    out["RAZON SOCIAL"] = df.get("RAZON SOCIAL", "").map(nt) if "RAZON SOCIAL" in df.columns else ""
    out["DNI"] = df.get("DNI", "").map(nd) if "DNI" in df.columns else ""
    out["NOMBRE"] = df.apply(nombre_completo, axis=1)
    out["SUPERVISOR"] = (
        df["SUPERVISOR A CARGO"].map(nt) if "SUPERVISOR A CARGO" in df.columns
        else df["SUPERVISOR"].map(nt) if "SUPERVISOR" in df.columns else ""
    )
    out["COORDINADOR"] = df.get("COORDINADOR", "").map(nt) if "COORDINADOR" in df.columns else ""
    out["DEPARTAMENTO"] = df.get("DEPARTAMENTO", "").map(nt) if "DEPARTAMENTO" in df.columns else ""
    out["PROVINCIA"] = df.get("PROVINCIA", "").map(nt) if "PROVINCIA" in df.columns else ""
    out["ESTADO"] = df.get("ESTADO", "ACTIVO").map(lambda x: nu(x) or "ACTIVO") if "ESTADO" in df.columns else "ACTIVO"
    out["FECHA_ALTA"] = (
        df["FECHA DE CREACION USUARIO"].map(fs) if "FECHA DE CREACION USUARIO" in df.columns
        else df["FECHA_ALTA"].map(fs) if "FECHA_ALTA" in df.columns else ""
    )
    out["FECHA_CESE"] = (
        df["FECHA DE CESE"].map(fs) if "FECHA DE CESE" in df.columns
        else df["FECHA_CESE"].map(fs) if "FECHA_CESE" in df.columns else ""
    )
    out["MES"] = str(int(periodo[-2:]))
    out["PERIODO"] = periodo
    out = out[out["DNI"].astype(str).str.strip().ne("")].copy()
    out["KEY"] = out.apply(lambda r: clave(r["DNI"], r["FECHA_ALTA"], periodo), axis=1)
    return out.drop_duplicates("KEY", keep="last")


def actualizar_asistencia_desde_colaboradores(hoja_asistencia, hoja_colaboradores, periodo: str, razon: str) -> tuple[int, int]:
    """Upsert no destructivo: agrega faltantes y actualiza datos base. Nunca toca DIA_1..DIA_31."""
    headers, df_asis = leer_asistencia(hoja_asistencia)
    headers = ensure_headers(hoja_asistencia, headers)
    h2i = {h: i + 1 for i, h in enumerate(headers)}

    df_col = leer_colaboradores_df(hoja_colaboradores)
    df_base = construir_base_desde_colaboradores(df_col, periodo, razon)
    if df_base.empty:
        return 0, 0

    df_exist = df_asis[df_asis["PERIODO"].astype(str).eq(periodo)].copy()
    if razon and nu(razon) != "ALL":
        df_exist = filtrar_razon(df_exist, razon)
    exist_map = {r["KEY"]: int(r["FILA"]) for _, r in df_exist.iterrows() if nt(r.get("KEY", ""))}
    exist_rows = {r["KEY"]: r for _, r in df_exist.iterrows() if nt(r.get("KEY", ""))}

    append_rows = []
    updates = []
    base_update_cols = ["RAZON SOCIAL", "DNI", "NOMBRE", "SUPERVISOR", "COORDINADOR", "DEPARTAMENTO", "PROVINCIA", "ESTADO", "FECHA_ALTA", "FECHA_CESE", "MES", "PERIODO"]

    for _, r in df_base.iterrows():
        k = r["KEY"]
        if k not in exist_map:
            new_row = []
            for h in headers:
                if h in base_update_cols:
                    new_row.append(nt(r.get(h, "")))
                elif h in DAY_COLS:
                    new_row.append("")
                else:
                    new_row.append("")
            append_rows.append(new_row)
        else:
            fila = exist_map[k]
            old = exist_rows[k]
            for c in base_update_cols:
                if c not in h2i:
                    continue
                new_val = nt(r.get(c, ""))
                old_val = nt(old.get(c, ""))
                if new_val != old_val:
                    col = letra_col(h2i[c])
                    updates.append({"range": f"{col}{fila}", "values": [[new_val]]})

    if append_rows:
        hoja_asistencia.append_rows(append_rows, value_input_option="USER_ENTERED")
    if updates:
        # En bloques para no superar tamaño de request
        for i in range(0, len(updates), 100):
            hoja_asistencia.batch_update(updates[i:i+100], value_input_option="USER_ENTERED")
    if append_rows or updates:
        limpiar_cache_asistencia()
    return len(append_rows), len(updates)

# =============================================================================
# Guardados
# =============================================================================
def asegurar_cabeceras_sustentos(hoja):
    """Asegura que Sustentos_Bajas tenga cabeceras.
    Evita que el primer registro se guarde en la fila 1 como si fuera encabezado.
    """
    try:
        primera = hoja.row_values(1)
    except Exception:
        primera = []
    primera_norm = [str(x).strip().upper() for x in primera]
    esperadas = [str(x).strip().upper() for x in SUSTENTO_COLS]
    if primera_norm[:len(esperadas)] != esperadas:
        hoja.update("A1:J1", [SUSTENTO_COLS], value_input_option="USER_ENTERED")


def guardar_sustento(row: dict, periodo: str, dia: int, archivo) -> str:
    contenido = archivo.getvalue()
    mime = archivo.type or "application/octet-stream"
    ext = "pdf" if "pdf" in mime else "jpg"
    dni = nd(row.get("DNI", ""))
    ts = datetime.now(TZ_LIMA).strftime("%Y%m%d_%H%M%S")
    fname = f"sustento_ABM_{dni}_{periodo}_DIA{dia}_{ts}.{ext}"
    link = subir_archivo_drive(fname, contenido, mime)
    hoja = obtener_o_crear_worksheet(NOMBRE_LIBRO, HOJA_SUSTENTOS, SUSTENTO_COLS)
    asegurar_cabeceras_sustentos(hoja)
    hoja.append_row([
        periodo, f"DIA_{dia}", str(fecha_periodo_dia(periodo, dia)), dni,
        row.get("NOMBRE", ""), row.get("RAZON SOCIAL", ""), "A-BM", link,
        datetime.now(TZ_LIMA).strftime("%Y-%m-%d %H:%M:%S"),
        st.session_state.get("usuario", "")
    ], value_input_option="USER_ENTERED")
    return link


def guardar_sustento_payload(row: dict, periodo: str, dia: int, payload: dict) -> str:
    """Guarda sustento A-BM desde bytes guardados temporalmente en session_state.
    Esto permite que el popup capture el documento sin perder el botón principal Guardar Presencialidad.
    """
    contenido = payload.get("content", b"")
    mime = payload.get("mime", "application/octet-stream") or "application/octet-stream"
    nombre_original = nt(payload.get("name", "sustento"))
    if not contenido:
        raise ValueError("Sustento vacío")
    if "pdf" in mime.lower() or nombre_original.lower().endswith(".pdf"):
        ext = "pdf"
    elif nombre_original.lower().endswith(".png"):
        ext = "png"
    else:
        ext = "jpg"
    dni = nd(row.get("DNI", ""))
    ts = datetime.now(TZ_LIMA).strftime("%Y%m%d_%H%M%S")
    fname = f"sustento_ABM_{dni}_{periodo}_DIA{dia}_{ts}.{ext}"
    link = subir_archivo_drive(fname, contenido, mime)
    hoja = obtener_o_crear_worksheet(NOMBRE_LIBRO, HOJA_SUSTENTOS, SUSTENTO_COLS)
    asegurar_cabeceras_sustentos(hoja)
    hoja.append_row([
        periodo, f"DIA_{dia}", str(fecha_periodo_dia(periodo, dia)), dni,
        row.get("NOMBRE", ""), row.get("RAZON SOCIAL", ""), "A-BM", link,
        datetime.now(TZ_LIMA).strftime("%Y-%m-%d %H:%M:%S"),
        st.session_state.get("usuario", "")
    ], value_input_option="USER_ENTERED")
    return link


def guardar_marca(hoja_asistencia, headers: list[str], row: dict, col_dia: str, marca: str):
    headers = ensure_headers(hoja_asistencia, headers)
    h2i = {h: i + 1 for i, h in enumerate(headers)}
    fila = int(row.get("FILA"))
    col = letra_col(h2i[col_dia])
    hoja_asistencia.update_acell(f"{col}{fila}", marca)
    limpiar_cache_asistencia()

# =============================================================================
# UI helper
# =============================================================================
def opts(df: pd.DataFrame, col: str) -> list[str]:
    if col not in df.columns:
        return ["TODOS"]
    vals = sorted([v for v in df[col].astype(str).map(nt).unique() if v])
    return ["TODOS"] + vals


def aplicar_filtros(df, f_razon, f_sup, f_coord, f_dep, f_prov, q=""):
    out = df.copy()
    for c, v in [("RAZON SOCIAL", f_razon), ("SUPERVISOR", f_sup), ("COORDINADOR", f_coord), ("DEPARTAMENTO", f_dep), ("PROVINCIA", f_prov)]:
        if v and v != "TODOS" and c in out.columns:
            out = out[out[c].astype(str).map(nt).eq(v)]
    q = nu(q)
    if q:
        mask = pd.Series(False, index=out.index)
        for c in ["DNI", "NOMBRE", "SUPERVISOR", "COORDINADOR", "DEPARTAMENTO", "PROVINCIA"]:
            if c in out.columns:
                mask |= out[c].astype(str).str.upper().str.contains(q, na=False)
        out = out[mask]
    return out.copy()


def es_editable_fila(row, fecha_sel: date) -> bool:
    if nu(row.get("ESTADO", "")) != "ACTIVO":
        return False
    alta = parse_fecha(row.get("FECHA_ALTA", ""))
    cese = parse_fecha(row.get("FECHA_CESE", ""))
    if alta and fecha_sel < alta:
        return False
    if cese and fecha_sel > cese:
        return False
    return True


def df_to_excel_bytes(df: pd.DataFrame) -> bytes:
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Jerarquia")
    return output.getvalue()

# =============================================================================
# Bloques
# =============================================================================
def mostrar_espejo(df_base: pd.DataFrame, col_dia: str):
    st.markdown("### 📊 Espejo / trazabilidad del mes")
    st.caption("Vista solo lectura. Muestra las marcas registradas por día del mes; no edita ni escribe nada.")
    cols = ["DNI", "NOMBRE", "SUPERVISOR", "COORDINADOR", "DEPARTAMENTO", "PROVINCIA", "ESTADO"] + DAY_COLS
    cols = [c for c in cols if c in df_base.columns]
    df_view = df_base[cols].copy()
    # Solo filas con al menos una marca en el mes para que no pese demasiado.
    mask = pd.Series(False, index=df_view.index)
    for d in DAY_COLS:
        if d in df_view.columns:
            mask |= df_view[d].astype(str).map(limpiar_marca).ne("")
    df_view = df_view[mask].copy()
    if df_view.empty:
        st.info("Aún no hay marcaciones registradas en el mes para los filtros actuales.")
        return
    st.dataframe(df_view.reset_index(drop=True), use_container_width=True, hide_index=True, height=380)


def mostrar_jerarquia_descarga(hoja_colaboradores, razon: str, registro_mod=None):
    st.markdown("### 📋 Estado actual de la jerarquía")
    st.caption("Carga bajo demanda desde colaboradores. No afecta la presencialidad.")

    # Usar el mismo módulo de matriz que ya tenías: filtros, orden visual y descarga.
    # Si registro_mod está disponible desde app_maestra_vendedores.py, se conserva esa vista
    # y se elimina el bloque duplicado de "Descarga de jerarquía".
    if registro_mod is not None and hasattr(registro_mod, "mostrar_tabla"):
        try:
            registro_mod.mostrar_tabla(hoja_colaboradores, razon_usuario=razon)
            return
        except Exception as e:
            st.warning(f"No se pudo cargar la matriz estándar: {e}")

    # Respaldo mínimo si por algún motivo registro_mod no llega al módulo.
    if not st.button("♻️ Cargar / recargar matriz", use_container_width=False):
        return
    with st.spinner("Cargando jerarquía desde Drive..."):
        df = leer_colaboradores_df(hoja_colaboradores)
    if df.empty:
        st.warning("No se encontró data en colaboradores.")
        return
    if razon and nu(razon) != "ALL" and "RAZON SOCIAL" in df.columns:
        df = filtrar_razon(df, razon)
    orden = [
        "FECHA MOV", "RAZON SOCIAL", "CANAL", "SUB CANAL", "REGION", "DEPARTAMENTO", "PROVINCIA",
        "SUPERVISOR A CARGO", "DNI SUPERVISOR", "COORDINADOR", "DNI COORDINADOR", "CARGO (ROL)",
        "NOMBRES", "APELLIDO PATERNO", "APELLIDO MATERNO", "CELULAR", "TIPO DE DOC", "DNI",
        "CORREO (USUARIO SGC/PRONTO)", "ESTADO", "TIPO DE CONTRATO", "FECHA DE CREACION USUARIO",
        "FECHA DE CESE", "MOTIVO", "CONTRATO FIRMADO", "TIPO_GESTION", "CAPACITADOR",
        "ORIGEN_INGRESO", "FUENTE_INGRESO", "FECHA_ALTA_REGISTRO", "FECHA_BAJA_REGISTRO", "USUARIO_ALTA",
        "USUARIO_BAJA", "REACTIVACIONES", "USUARIO ZYTRUST", "ID (SGC/PRONTO)", "NUEVO_GERENTE", "ZONA_1", "NUEVA_REGION", "EQUIPOS"
    ]
    cols = [c for c in orden if c in df.columns] + [c for c in df.columns if c not in orden]
    df = df[cols].copy()
    st.success(f"Jerarquía cargada: {len(df)} registros.")
    st.dataframe(df.head(300), use_container_width=True, hide_index=True, height=520)
    st.download_button(
        "⬇️ Descargar jerarquía en Excel",
        data=df_to_excel_bytes(df),
        file_name=f"jerarquia_{nt(razon).replace(' ', '_') or 'ALL'}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )


# =============================================================================
# Diálogo A-BM inmediato
# =============================================================================
def _abm_key(row: dict, periodo: str, dia: int) -> str:
    return f"{nd(row.get('DNI',''))}|{periodo}|DIA_{dia}|{nt(row.get('FILA',''))}"


def _abrir_dialogo_abm(row: dict, periodo: str, dia: int, reset_key: str):
    """Popup inmediato para capturar sustento A-BM.
    El archivo se guarda en memoria apenas se adjunta. No escribe en Drive todavía.
    La marcación final se confirma con el botón principal Guardar Presencialidad.
    """
    if "abm_sustentos" not in st.session_state:
        st.session_state["abm_sustentos"] = {}

    key_abm = _abm_key(row, periodo, dia)

    def _contenido_dialogo():
        st.markdown("**Baja médica detectada.** Adjunta PDF o imagen para sustentar la marcación.")
        st.caption("Sin sustento no se permitirá guardar A-BM. Tamaño máximo referencial: 200 MB según configuración de Streamlit/servidor.")
        st.info(f"DNI: {row.get('DNI','')} | {row.get('NOMBRE','')} | {periodo} - DIA_{dia}")

        upload_key = f"upload_abm_dialog_{key_abm}_{int(st.session_state.get(reset_key,0))}"
        archivo = st.file_uploader(
            "📎 Sustento de baja médica",
            type=["pdf", "png", "jpg", "jpeg"],
            key=upload_key,
        )

        # Streamlit a veces muestra el archivo en el componente antes de que el valor
        # retornado sea visible en la misma ejecución del diálogo. Por eso también
        # revisamos st.session_state[upload_key].
        archivo_state = st.session_state.get(upload_key)
        if archivo is None and archivo_state is not None:
            archivo = archivo_state

        # Guarda el sustento temporal apenas se adjunta. No sube a Drive hasta Guardar Presencialidad.
        if archivo is not None:
            contenido = archivo.getvalue()
            st.session_state.setdefault("abm_sustentos", {})[key_abm] = {
                "name": archivo.name,
                "mime": archivo.type or "application/octet-stream",
                "content": contenido,
                "dni": nd(row.get("DNI", "")),
                "periodo": periodo,
                "dia": dia,
                "fila": nt(row.get("FILA", "")),
            }
            st.success(f"✅ Documento cargado correctamente: {archivo.name}")
            st.info("Sustento listo. Cierra esta ventana y luego presiona Guardar Presencialidad para confirmar la marca A-BM.")
        else:
            ya = st.session_state.get("abm_sustentos", {}).get(key_abm)
            if ya:
                st.success(f"✅ Documento cargado correctamente: {ya.get('name','archivo')}")
                st.info("Sustento listo. Cierra esta ventana y luego presiona Guardar Presencialidad para confirmar la marca A-BM.")
            else:
                st.warning("Aún falta adjuntar el sustento. La marca A-BM no se podrá guardar sin documento.")

        c1, c2 = st.columns(2)
        with c1:
            if st.button("✅ Cerrar ventana", type="primary", use_container_width=True):
                st.session_state.pop("abm_dialog_data", None)
                st.rerun()
        with c2:
            if st.button("Cancelar", use_container_width=True):
                # No guarda sustento ni asistencia. La validación del botón principal bloqueará A-BM si falta documento.
                st.session_state.pop("abm_dialog_data", None)
                st.rerun()

    if hasattr(st, "dialog"):
        @st.dialog("🏥 Sustento obligatorio - A-BM")
        def _dlg():
            _contenido_dialogo()
        _dlg()
    else:
        st.markdown("### 🏥 Sustento obligatorio - A-BM")
        _contenido_dialogo()

# =============================================================================
# UI principal
# =============================================================================
def mostrar_asistencia(hoja_asistencia, hoja_colaboradores, registro_mod=None, razon=None):
    st.markdown(CSS, unsafe_allow_html=True)
    razon_usuario = nt(razon if razon is not None else st.session_state.get("razon", "ALL")) or "ALL"
    es_dealer = nu(razon_usuario) != "ALL"

    titulo = f"🗓️ Presencialidad Dealer" + (f": {razon_usuario}" if es_dealer else "")
    st.markdown(f"### {titulo}")

    periodo = st.selectbox("Periodo", periodos_disponibles(), index=0, key="asis_periodo")
    dias = dias_periodo(periodo)
    default_dia = hoy_lima().day if periodo == periodo_actual() and hoy_lima().day in dias else 1
    dia = st.selectbox("Día", dias, index=dias.index(default_dia), key="asis_dia")
    col_dia = f"DIA_{dia}"
    fecha_sel = fecha_periodo_dia(periodo, dia)

    st.markdown(
        f"<div class='leyenda'>📅 Periodo: <b>{periodo}</b> | Día editable: <b>{col_dia}</b> | "
        "La vista trabaja desde Asistencia. Usa <b>Actualizar cambios del Drive</b> solo si agregaste altas/bajas en colaboradores.</div>",
        unsafe_allow_html=True,
    )

    col_a, col_b = st.columns([1, 3])
    with col_a:
        if st.button("🔁 Actualizar cambios del Drive", use_container_width=True, help="Agrega altas faltantes y actualiza bajas/estado sin borrar marcaciones."):
            with st.spinner("Actualizando altas/bajas desde colaboradores sin borrar histórico..."):
                try:
                    nuevos, cambios = actualizar_asistencia_desde_colaboradores(hoja_asistencia, hoja_colaboradores, periodo, razon_usuario)
                    st.success(f"Actualización lista: {nuevos} altas agregadas y {cambios} campos base actualizados. No se borró ninguna marcación.")
                    st.rerun()
                except Exception as e:
                    st.error(f"No se pudo actualizar desde Drive: {e}")

    headers, df_all = leer_asistencia(hoja_asistencia)
    headers = ensure_headers(hoja_asistencia, headers)
    df_mes = df_all[df_all["PERIODO"].astype(str).eq(periodo)].copy()
    if es_dealer:
        df_mes = filtrar_razon(df_mes, razon_usuario)

    if df_mes.empty:
        st.warning("No hay registros en Asistencia para este periodo/dealer. Presiona Actualizar cambios del Drive para traer altas desde colaboradores sin borrar histórico.")
        mostrar_jerarquia_descarga(hoja_colaboradores, razon_usuario, registro_mod)
        return

    # Filtros visibles
    st.markdown("### 🔎 Filtros")
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        if es_dealer:
            # Siempre mostrar la etiqueta Razón Social para que el usuario sepa qué filtro aplica.
            st.selectbox("Razón Social", [razon_usuario], index=0, key="asis_f_razon_dealer", disabled=True)
            f_razon = "TODOS"
        else:
            f_razon = st.selectbox("Razón Social", opts(df_mes, "RAZON SOCIAL"), key="asis_f_razon")
    with c2:
        f_sup = st.selectbox("Supervisor", opts(df_mes, "SUPERVISOR"), key="asis_f_sup")
    with c3:
        f_coord = st.selectbox("Coordinador", opts(df_mes, "COORDINADOR"), key="asis_f_coord")
    with c4:
        f_dep = st.selectbox("Departamento", opts(df_mes, "DEPARTAMENTO"), key="asis_f_dep")
    with c5:
        f_prov = st.selectbox("Provincia", opts(df_mes, "PROVINCIA"), key="asis_f_prov")
    buscar = st.text_input("Buscar DNI / nombre", placeholder="Ej: 76043772", key="asis_buscar")

    df_f = aplicar_filtros(df_mes, f_razon, f_sup, f_coord, f_dep, f_prov, buscar)
    if df_f.empty:
        st.warning("Sin resultados con los filtros aplicados.")
        return

    # Solo activos y en rango para registrar
    df_edit = df_f[df_f.apply(lambda r: es_editable_fila(r, fecha_sel), axis=1)].copy()
    # Inactivo no entra al editor. Queda en espejo/jerarquía si se requiere.

    st.markdown("### ✏️ Registrar presencialidad de hoy")
    st.markdown(
        "<div class='leyenda'><b>Motivos:</b> A = Asistió · A-BM = Baja Médica · A-VAC = Vacaciones · NA-SA = No asistió sin aviso · NA-CA = No asistió con aviso</div>",
        unsafe_allow_html=True,
    )

    if fecha_sel > hoy_lima():
        st.warning("Día futuro bloqueado. No se puede registrar asistencia futura.")
    elif df_edit.empty:
        st.warning("No hay colaboradores activos editables para el día seleccionado.")
    else:
        marcas = MARCAS_RETRO if fecha_sel < hoy_lima() else MARCAS_HOY
        if fecha_sel < hoy_lima():
            st.markdown("<div class='alerta'>Fecha anterior: solo se permite registrar A-BM con sustento obligatorio.</div>", unsafe_allow_html=True)
        cols_editor = ["RAZON SOCIAL", "DNI", "NOMBRE", "SUPERVISOR", "COORDINADOR", "DEPARTAMENTO", "PROVINCIA", "ESTADO", "FECHA_ALTA", "FECHA_CESE", "MES", "PERIODO", col_dia, "FILA"]
        for c in cols_editor:
            if c not in df_edit.columns:
                df_edit[c] = ""
        df_edit[col_dia] = df_edit[col_dia].map(limpiar_marca)
        df_edit = df_edit[cols_editor].head(MAX_FILAS_EDITOR).reset_index(drop=True)
        original = df_edit[col_dia].tolist()

        reset_key = f"asis_editor_version_{periodo}_{dia}_{razon_usuario}"
        editor_version = int(st.session_state.get(reset_key, 0))
        editor_key = f"editor_{periodo}_{dia}_{razon_usuario}_{editor_version}"

        # Flujo estable:
        # - IMPORTANTE: el editor va dentro de st.form.
        # - Así seleccionar A / A-VAC / A-BM NO vuelve a ejecutar toda la pantalla.
        # - Solo procesa cuando se presiona Guardar Presencialidad.
        # - Si hay A-BM sin sustento, abre ventana emergente y bloquea el guardado.
        with st.form(key=f"form_pres_{periodo}_{dia}_{razon_usuario}_{editor_version}", clear_on_submit=False):
            df_new = st.data_editor(
                df_edit,
                hide_index=True,
                use_container_width=True,
                height=min(560, 48 + 34 * len(df_edit)),
                num_rows="fixed",
                column_config={
                    col_dia: st.column_config.SelectboxColumn(col_dia, options=marcas, required=False),
                    "FILA": st.column_config.NumberColumn("FILA", disabled=True),
                    "DNI": st.column_config.TextColumn("DNI", disabled=True),
                    "NOMBRE": st.column_config.TextColumn("NOMBRE", disabled=True, width="large"),
                    "RAZON SOCIAL": st.column_config.TextColumn("RAZON SOCIAL", disabled=True),
                    "SUPERVISOR": st.column_config.TextColumn("SUPERVISOR", disabled=True),
                    "COORDINADOR": st.column_config.TextColumn("COORDINADOR", disabled=True),
                    "DEPARTAMENTO": st.column_config.TextColumn("DEPARTAMENTO", disabled=True),
                    "PROVINCIA": st.column_config.TextColumn("PROVINCIA", disabled=True),
                    "ESTADO": st.column_config.TextColumn("ESTADO", disabled=True),
                    "FECHA_ALTA": st.column_config.TextColumn("FECHA_ALTA", disabled=True),
                    "FECHA_CESE": st.column_config.TextColumn("FECHA_CESE", disabled=True),
                    "MES": st.column_config.TextColumn("MES", disabled=True),
                    "PERIODO": st.column_config.TextColumn("PERIODO", disabled=True),
                },
                key=editor_key,
            )
            st.caption("Selecciona las marcas necesarias. La página no procesará cambios hasta presionar Guardar Presencialidad.")
            guardar_click = st.form_submit_button(
                f"💾 Guardar Presencialidad",
                type="primary",
                use_container_width=True,
            )

        # Solo se llega aquí con cambios reales cuando se presiona el botón del formulario.
        cambios = []
        if guardar_click:
            for i in range(len(df_new)):
                old = limpiar_marca(original[i])
                new = limpiar_marca(df_new.at[i, col_dia])
                if old != new:
                    if fecha_sel < hoy_lima() and new != "A-BM":
                        continue
                    cambios.append((i, old, new, df_new.iloc[i].to_dict()))

            if cambios:
                resumen = ", ".join([f"{c[3].get('DNI','')}→{c[2]}" for c in cambios[:8]])
                st.markdown(f"<div class='okbox'>📝 Cambios detectados: {resumen}</div>", unsafe_allow_html=True)

            bm = [c for c in cambios if c[2] == "A-BM"]
            pendientes_bm = []
            for _, _, _, row_bm in bm:
                key_abm = _abm_key(row_bm, periodo, dia)
                if not st.session_state.get("abm_sustentos", {}).get(key_abm):
                    pendientes_bm.append(row_bm)

            if not cambios:
                st.info("No hay cambios para guardar. Selecciona una marca en la columna del día y vuelve a presionar Guardar Presencialidad.")
            elif pendientes_bm:
                # Guardamos temporalmente los cambios para que no se pierdan mientras se adjunta el sustento.
                st.session_state["asis_cambios_pendientes"] = cambios
                row_bm = pendientes_bm[0]
                st.session_state["abm_dialog_data"] = {
                    "periodo": periodo,
                    "dia": dia,
                    "col_dia": col_dia,
                    "row": row_bm,
                }
                st.error("Hay A-BM sin sustento. Adjunta el documento en la ventana emergente. Sin documento NO se guarda A-BM.")
                _abrir_dialogo_abm(row_bm, periodo, dia, reset_key)
            else:
                ok, err = 0, []
                with st.spinner("Guardando presencialidad..."):
                    for _, _, new, row in cambios:
                        try:
                            if new == "A-BM":
                                key_abm = _abm_key(row, periodo, dia)
                                payload = st.session_state.get("abm_sustentos", {}).get(key_abm)
                                if not payload:
                                    err.append(f"{row.get('DNI','')}: falta sustento A-BM.")
                                    continue
                                guardar_sustento_payload(row, periodo, dia, payload)
                            guardar_marca(hoja_asistencia, headers, row, col_dia, new)
                            ok += 1
                        except Exception as e:
                            err.append(f"{row.get('DNI','')}: {e}")
                if ok:
                    for _, _, new, row in cambios:
                        if new == "A-BM":
                            st.session_state.get("abm_sustentos", {}).pop(_abm_key(row, periodo, dia), None)
                    st.session_state.pop("asis_cambios_pendientes", None)
                    st.session_state[reset_key] = int(st.session_state.get(reset_key, 0)) + 1
                    limpiar_cache_asistencia()
                    st.success(f"✅ Se guardaron {ok} marcaciones correctamente.")
                    st.rerun()
                for e in err:
                    st.error(e)
        else:
            st.caption(f"✔ Edita la columna {col_dia} y presiona Guardar Presencialidad.")

        # Si hay cambios pendientes por A-BM, permitir guardarlos después de cargar sustento.
        pendientes_guardado = st.session_state.get("asis_cambios_pendientes", [])
        if pendientes_guardado:
            faltan = []
            for _, _, new, row in pendientes_guardado:
                if new == "A-BM" and not st.session_state.get("abm_sustentos", {}).get(_abm_key(row, periodo, dia)):
                    faltan.append(row)
            if faltan:
                st.warning("Hay A-BM pendiente de sustento. Carga el documento en la ventana emergente y luego confirma el guardado.")
                if st.button("🏥 Abrir ventana de sustento pendiente", use_container_width=True):
                    _abrir_dialogo_abm(faltan[0], periodo, dia, reset_key)
            else:
                if st.button("✅ Confirmar guardado pendiente con sustento", type="primary", use_container_width=True):
                    ok, err = 0, []
                    with st.spinner("Guardando presencialidad pendiente..."):
                        for _, _, new, row in pendientes_guardado:
                            try:
                                if new == "A-BM":
                                    payload = st.session_state.get("abm_sustentos", {}).get(_abm_key(row, periodo, dia))
                                    guardar_sustento_payload(row, periodo, dia, payload)
                                guardar_marca(hoja_asistencia, headers, row, col_dia, new)
                                ok += 1
                            except Exception as e:
                                err.append(f"{row.get('DNI','')}: {e}")
                    if ok:
                        for _, _, new, row in pendientes_guardado:
                            if new == "A-BM":
                                st.session_state.get("abm_sustentos", {}).pop(_abm_key(row, periodo, dia), None)
                        st.session_state.pop("asis_cambios_pendientes", None)
                        st.session_state[reset_key] = int(st.session_state.get(reset_key, 0)) + 1
                        limpiar_cache_asistencia()
                        st.success(f"✅ Se guardaron {ok} marcaciones correctamente.")
                        st.rerun()
                    for e in err:
                        st.error(e)

    # Bloque 2
    st.divider()
    if st.checkbox("📊 Ver espejo mensual / trazabilidad", value=False):
        mostrar_espejo(df_f, col_dia)

    # Bloque 3
    st.divider()
    mostrar_jerarquia_descarga(hoja_colaboradores, razon_usuario, registro_mod)


def registrar_alta_en_asistencia(hoja_asis, campos: dict) -> str:
    # La fila se materializa con el botón Actualizar cambios del Drive o desde proceso de Alta si se quiere extender.
    limpiar_cache_asistencia()
    return f"DNI {campos.get('DNI','')} disponible para actualizar en Presencialidad."
