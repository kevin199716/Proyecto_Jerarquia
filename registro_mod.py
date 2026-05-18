from datetime import datetime, timedelta

import pandas as pd
import pytz
import streamlit as st

# =========================
# ZONA HORARIA PERÚ
# =========================
zona_peru = pytz.timezone("America/Lima")


def ahora_peru_fecha_hora():
    return datetime.now(zona_peru).strftime("%Y-%m-%d %H:%M:%S")


def hoy_peru_fecha():
    return datetime.now(zona_peru).date()


# =========================
# UTILIDADES
# =========================
def limpiar_texto(valor) -> str:
    if pd.isna(valor) if not isinstance(valor, str) else False:
        return ""
    s = str(valor).strip()
    return "" if s.upper() in ("NONE", "NAN", "NULL") else s


def limpiar_fecha(valor):
    try:
        if valor in ["", None]:
            return None
        fecha = pd.to_datetime(valor, errors="coerce")
        if pd.isna(fecha):
            return None
        return fecha.date()
    except Exception:
        return None


def normalizar_dni(valor) -> str:
    dni = limpiar_texto(valor).replace(".0", "")
    if dni.isdigit() and len(dni) < 8:
        dni = dni.zfill(8)
    return dni


def normalizar_columnas(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = df.columns.astype(str).str.strip().str.upper()
    return df


def col_idx(df: pd.DataFrame, *nombres):
    for n in nombres:
        if n in df.columns:
            return df.columns.get_loc(n) + 1
    return None


# =========================
# MOTIVOS
# =========================
MOTIVOS = [
    "",
    "Renuncia Laboral",
    "NSPP",
    "Baja por Productividad",
    "Baja por FPD",
    "Baja - VNE3",
    "Baja por politica de Actividad",
    "Abandono Laboral / Faltas Injustificadas",
    "Baja No asistio Campo",
    "Baja por cierre de Operaciones",
]


# =========================
# TABLA
# =========================
def mostrar_tabla(hoja, razon_usuario=None):
    data = hoja.get_all_records()
    if not data:
        st.info("No hay datos")
        return None

    df = normalizar_columnas(pd.DataFrame(data)).fillna("")
    rol = st.session_state.get("rol", "")

    if rol != "backoffice" and razon_usuario and "RAZON SOCIAL" in df.columns:
        df = df[df["RAZON SOCIAL"].astype(str).str.strip().eq(razon_usuario)]

    st.dataframe(df, use_container_width=True)
    return df


# =========================
# DAR DE BAJA
# =========================
def dar_de_baja(df, hoja, razon_usuario=None):
    st.markdown("<span class='wow-section-title'>🔻 Dar de baja</span>", unsafe_allow_html=True)

    df = normalizar_columnas(df).fillna("")
    rol = st.session_state.get("rol", "")
    usuario_actual = st.session_state.get("usuario", "")

    if rol != "backoffice" and razon_usuario and "RAZON SOCIAL" in df.columns:
        df = df[df["RAZON SOCIAL"].astype(str).str.strip().eq(razon_usuario)]

    if "DNI" not in df.columns:
        st.error("❌ La base no tiene columna DNI.")
        return

    dni = st.text_input("DNI", key="dni_baja").strip()
    if not dni:
        return

    dni_limpio = normalizar_dni(dni)
    df["DNI_NORM"] = df["DNI"].apply(normalizar_dni)
    df_filtrado = df[df["DNI_NORM"].eq(dni_limpio)].copy()

    if df_filtrado.empty:
        st.error("❌ No encontrado")
        return

    if "ESTADO" in df_filtrado.columns:
        activos = df_filtrado[df_filtrado["ESTADO"].astype(str).str.strip().str.upper().eq("ACTIVO")].copy()
    else:
        activos = df_filtrado.copy()

    if activos.empty:
        st.warning("⚠️ El DNI existe, pero no tiene registros activos para dar de baja.")
        st.dataframe(df_filtrado.drop(columns=["DNI_NORM"], errors="ignore"), use_container_width=True)
        return

    if len(activos) > 1:
        opciones = activos.reset_index()
        seleccion = st.selectbox(
            "Selecciona registro activo",
            opciones.index,
            format_func=lambda i: (
                f"{limpiar_texto(opciones.loc[i].get('RAZON SOCIAL', ''))} - "
                f"{limpiar_texto(opciones.loc[i].get('CARGO (ROL)', ''))} - "
                f"Alta: {limpiar_texto(opciones.loc[i].get('FECHA DE CREACION USUARIO', ''))}"
            ),
        )
        fila = opciones.loc[seleccion]
        index_global = int(fila["index"])
    else:
        fila = activos.iloc[0]
        index_global = int(fila.name)

    st.info(
        "Registro seleccionado: "
        f"{limpiar_texto(fila.get('RAZON SOCIAL', ''))} / "
        f"{limpiar_texto(fila.get('NOMBRES', fila.get('NOMBRE', '')))} / "
        f"Alta: {limpiar_texto(fila.get('FECHA DE CREACION USUARIO', ''))}"
    )

    fecha_creacion = limpiar_fecha(fila.get("FECHA DE CREACION USUARIO"))
    hoy = hoy_peru_fecha()

    fecha = st.date_input(
        "Fecha de cese",
        value=hoy,
        min_value=hoy - timedelta(days=2),
        max_value=hoy,
        key="fecha_cese_baja",
        help="Solo permite antier, ayer u hoy."
    )

    motivo = st.selectbox("Motivo de baja", MOTIVOS, key="motivo_baja")

    if st.button("Dar de baja", key="btn_dar_baja"):
        if not motivo:
            st.error("❌ Selecciona un motivo de baja.")
            return

        if fecha_creacion and fecha < fecha_creacion:
            st.error("❌ La fecha de cese no puede ser menor a la fecha de creación/alta.")
            return

        try:
            # FECHA MOV: solo fecha de movimiento/cese.
            fecha_mov = str(fecha)
            # FECHA_BAJA_REGISTRO: marcaje con fecha y hora.
            marca_baja = ahora_peru_fecha_hora()

            updates = []
            row_sheet = index_global + 2

            c_estado = col_idx(df, "ESTADO")
            c_cese = col_idx(df, "FECHA DE CESE", "FECHA CESE")
            c_motivo = col_idx(df, "MOTIVO")
            c_fmov = col_idx(df, "FECHA MOV")
            c_fbaja = col_idx(df, "FECHA_BAJA_REGISTRO", "FECHA BAJA REGISTRO")
            c_usuario_baja = col_idx(df, "USUARIO_BAJA", "USUARIO BAJA")

            if c_estado:
                updates.append({"range": f"{row_sheet}:{row_sheet}", "values": None})
                hoja.update_cell(row_sheet, c_estado, "INACTIVO")
            if c_cese:
                hoja.update_cell(row_sheet, c_cese, str(fecha))
            if c_motivo:
                hoja.update_cell(row_sheet, c_motivo, motivo)
            if c_fmov:
                hoja.update_cell(row_sheet, c_fmov, fecha_mov)
            if c_fbaja:
                hoja.update_cell(row_sheet, c_fbaja, marca_baja)
            if c_usuario_baja:
                hoja.update_cell(row_sheet, c_usuario_baja, usuario_actual)

            st.success("✅ Baja aplicada correctamente")
            st.caption(f"FECHA MOV: {fecha_mov} | FECHA_BAJA_REGISTRO: {marca_baja}")
        except Exception as e:
            st.error(f"❌ Error al aplicar la baja: {e}")


# =========================
# EDITAR
# =========================
def editar_registro(df, hoja, hoja_ubi):
    st.markdown("<span class='wow-section-title'>✏️ Editar registro</span>", unsafe_allow_html=True)

    df = normalizar_columnas(df).fillna("")
    if "DNI" not in df.columns:
        st.error("❌ La base no tiene columna DNI.")
        return

    rol = st.session_state.get("rol", "")
    razon_usuario = st.session_state.get("razon", "")

    if rol != "backoffice" and razon_usuario and "RAZON SOCIAL" in df.columns:
        df = df[df["RAZON SOCIAL"].astype(str).str.strip().eq(razon_usuario)]

    dni = st.text_input("DNI a editar", key="dni_edit")
    if not dni:
        return

    dni_limpio = normalizar_dni(dni)
    df["DNI_NORM"] = df["DNI"].apply(normalizar_dni)
    df_filtrado = df[df["DNI_NORM"].eq(dni_limpio)].copy()

    if df_filtrado.empty:
        st.error("❌ No encontrado")
        return

    if len(df_filtrado) > 1:
        opciones = df_filtrado.reset_index()
        seleccion = st.selectbox(
            "Selecciona registro",
            opciones.index,
            format_func=lambda i: f"{opciones.loc[i].get('RAZON SOCIAL', '')} - {opciones.loc[i].get('CARGO (ROL)', '')} - {opciones.loc[i].get('ESTADO', '')}",
        )
        fila = opciones.loc[seleccion]
        index_global = fila["index"]
    else:
        fila = df_filtrado.iloc[0]
        index_global = fila.name

    st.success("Registro seleccionado")
    st.caption(f"Fila en Google Sheets: {int(index_global) + 2}")
    st.info("La lógica completa de edición puede mantenerse como la tenías; este bloque solo corrige búsqueda por DNI normalizado.")
