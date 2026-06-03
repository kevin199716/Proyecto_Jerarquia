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


def limpiar_numero_texto(valor, zfill_dni=False) -> str:
    """Convierte DNI/celulares/IDs a texto para evitar formato con comas en st.dataframe."""
    v = limpiar_texto(valor).replace(".0", "").replace(",", "")
    if v == "":
        return ""
    # Si vino como 76043772.0 o 76,043,772, deja solo dígitos.
    import re
    digitos = re.sub(r"\D", "", v)
    if digitos:
        if zfill_dni and len(digitos) < 8:
            digitos = digitos.zfill(8)
        return digitos
    return v.strip()


def normalizar_columnas(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = df.columns.astype(str).str.strip().str.upper()
    return df


def forzar_columnas_texto(df: pd.DataFrame) -> pd.DataFrame:
    """Evita que DNI/CELULAR/ID se muestren con separador de miles en la matriz."""
    df = df.copy()
    for c in df.columns:
        cu = str(c).upper()
        if "DNI" in cu:
            df[c] = df[c].apply(lambda x: limpiar_numero_texto(x, zfill_dni=True)).astype(str)
        elif "CELULAR" in cu or cu.startswith("ID") or "ID " in cu or "(SGC/PRONTO)" in cu:
            df[c] = df[c].apply(lambda x: limpiar_numero_texto(x, zfill_dni=False)).astype(str)
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
def _opciones_filtro(df: pd.DataFrame, columna: str) -> list[str]:
    if df.empty or columna not in df.columns:
        return ["TODOS"]
    valores = (
        df[columna].astype(str).str.strip()
        .replace(["", "None", "NONE", "nan", "NaN", "NULL", "null"], pd.NA)
        .dropna().unique().tolist()
    )
    return ["TODOS"] + sorted([v for v in valores if str(v).strip()])


def _aplicar_select(df: pd.DataFrame, columna: str, valor: str) -> pd.DataFrame:
    if valor == "TODOS" or columna not in df.columns:
        return df
    return df[df[columna].astype(str).str.strip().eq(valor)].copy()


def _headers_unicos(headers):
    vistos = {}
    salida = []
    for h in headers:
        h = str(h).strip().upper()
        if h in vistos:
            vistos[h] += 1
            salida.append(f"{h}_{vistos[h]}")
        else:
            vistos[h] = 0
            salida.append(h)
    return salida


@st.cache_data(ttl=180, show_spinner=False)
def _leer_matriz_cached(_hoja):
    """Lee la hoja con get_all_values (liviano) y devuelve un DataFrame YA limpio
    y con DNI/celulares como texto. Se hace UNA sola vez y se comparte entre
    todas las sesiones, en vez de leer y copiar en cada interacción."""
    valores = _hoja.get_all_values()
    if not valores:
        return pd.DataFrame()
    headers = _headers_unicos(valores[0])
    n = len(headers)
    filas = []
    for fila in valores[1:]:
        fila = list(fila)
        if len(fila) < n:
            fila += [""] * (n - len(fila))
        filas.append(fila[:n])
    df = pd.DataFrame(filas, columns=headers).fillna("")
    return forzar_columnas_texto(df)


def mostrar_tabla(hoja, razon_usuario=None):
    df = _leer_matriz_cached(hoja)
    if df.empty:
        st.info("No hay datos")
        return None

    rol = st.session_state.get("rol", "")

    if rol != "backoffice" and razon_usuario and "RAZON SOCIAL" in df.columns:
        df = df[df["RAZON SOCIAL"].astype(str).str.strip().eq(razon_usuario)]

    st.caption("Filtros rápidos sobre la matriz cargada. No vuelve a leer Drive mientras filtras dentro de esta vista.")
    f1, f2, f3, f4 = st.columns([1.3, 1, 1, 1])
    with f1:
        buscar = st.text_input("Buscar DNI / nombre / apellido", key="matriz_buscar_texto").strip()
    with f2:
        filtro_estado = st.selectbox("Estado", _opciones_filtro(df, "ESTADO"), key="matriz_filtro_estado")
    with f3:
        filtro_razon = st.selectbox("Razón social", _opciones_filtro(df, "RAZON SOCIAL"), key="matriz_filtro_razon")
    with f4:
        filtro_canal = st.selectbox("Canal", _opciones_filtro(df, "CANAL"), key="matriz_filtro_canal")

    f5, f6, f7 = st.columns(3)
    with f5:
        col_region = "NUEVA_REGION" if "NUEVA_REGION" in df.columns else "REGION"
        filtro_region = st.selectbox("Nueva Región", _opciones_filtro(df, col_region), key="matriz_filtro_region")
    with f6:
        filtro_dep = st.selectbox("Departamento", _opciones_filtro(df, "DEPARTAMENTO"), key="matriz_filtro_dep")
    with f7:
        filtro_prov = st.selectbox("Provincia", _opciones_filtro(df, "PROVINCIA"), key="matriz_filtro_prov")

    df_vista = df
    for columna, valor in [
        ("ESTADO", filtro_estado),
        ("RAZON SOCIAL", filtro_razon),
        ("CANAL", filtro_canal),
        (col_region, filtro_region),
        ("DEPARTAMENTO", filtro_dep),
        ("PROVINCIA", filtro_prov),
    ]:
        df_vista = _aplicar_select(df_vista, columna, valor)

    if buscar:
        cols_busqueda = [c for c in ["DNI", "NOMBRES", "NOMBRE", "APELLIDO PATERNO", "APELLIDO MATERNO", "CORREO (USUARIO SGC/PRONTO)"] if c in df_vista.columns]
        if cols_busqueda:
            patron = buscar.upper()
            mask = pd.Series(False, index=df_vista.index)
            for c in cols_busqueda:
                mask = mask | df_vista[c].astype(str).str.upper().str.contains(patron, na=False, regex=False)
            df_vista = df_vista[mask]

    total = len(df_vista)
    st.caption(f"Registros mostrados: **{total}** de **{len(df)}**")

    # Descarga siempre exporta TODOS los registros filtrados (no solo la página)
    import io as _io
    _buf = _io.StringIO()
    df_vista.to_csv(_buf, index=False, encoding="utf-8-sig")
    st.download_button(
        label=f"⬇️ Descargar todo ({total} registros)",
        data=_buf.getvalue().encode("utf-8-sig"),
        file_name="jerarquia_completa.csv",
        mime="text/csv",
        key="dl_jerarquia_all",
    )

    cols_texto = {
        c: st.column_config.TextColumn(c)
        for c in df_vista.columns
        if "DNI" in str(c).upper() or "CELULAR" in str(c).upper() or str(c).upper().startswith("ID")
    }

    abierto = bool(buscar) or any(
        v != "TODOS" for v in [filtro_estado, filtro_razon, filtro_canal, filtro_region, filtro_dep, filtro_prov]
    )

    # Paginación: máximo 300 filas por vista para no freezear el navegador
    MAX_VISTA = 300
    if total > MAX_VISTA:
        n_pags = -(-total // MAX_VISTA)
        pag = st.selectbox(f"Página (mostrando {MAX_VISTA} de {total})", list(range(1, n_pags + 1)), key="matriz_pag")
        inicio = (pag - 1) * MAX_VISTA
        df_pag = df_vista.iloc[inicio:inicio + MAX_VISTA]
    else:
        df_pag = df_vista

    with st.expander("📋 Ver matriz de jerarquía", expanded=abierto):
        st.dataframe(df_pag, use_container_width=True, height=480, column_config=cols_texto)
        import io as _io
        _buf = _io.StringIO()
        df_vista.to_csv(_buf, index=False, encoding="utf-8-sig")
        st.download_button(
            "⬇️ Descargar TODOS los registros (CSV)",
            data=_buf.getvalue().encode("utf-8-sig"),
            file_name="jerarquia_completa.csv",
            mime="text/csv",
            key="dl_full_csv"
        )
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
            from gspread.cell import Cell

            # FECHA MOV: solo fecha de movimiento/cese.
            fecha_mov = str(fecha)
            # FECHA_BAJA_REGISTRO: marcaje con fecha y hora.
            marca_baja = ahora_peru_fecha_hora()

            row_sheet = index_global + 2

            c_estado = col_idx(df, "ESTADO")
            c_cese = col_idx(df, "FECHA DE CESE", "FECHA CESE")
            c_motivo = col_idx(df, "MOTIVO")
            c_fmov = col_idx(df, "FECHA MOV")
            c_fbaja = col_idx(df, "FECHA_BAJA_REGISTRO", "FECHA BAJA REGISTRO")
            c_usuario_baja = col_idx(df, "USUARIO_BAJA", "USUARIO BAJA")

            celdas = []
            for col, valor in [
                (c_estado, "INACTIVO"),
                (c_cese, str(fecha)),
                (c_motivo, motivo),
                (c_fmov, fecha_mov),
                (c_fbaja, marca_baja),
                (c_usuario_baja, usuario_actual),
            ]:
                if col:
                    celdas.append(Cell(row_sheet, col, valor))

            if celdas:
                # UNA sola llamada a la API en vez de seis update_cell.
                hoja.update_cells(celdas, value_input_option="USER_ENTERED")

            # Limpiar todos los cachés para que el cambio se refleje inmediatamente
            # en Presencialidad (ESTADO) y en la Matriz de jerarquía.
            _leer_matriz_cached.clear()
            try:
                # Limpiar caché de colaboradores y asistencia
                from asistencia import leer_colaboradores_drive, _leer_asistencia_cached
                leer_colaboradores_drive.clear()
                _leer_asistencia_cached.clear()
                # Forzar re-sync de ESTADO en próxima visita a Presencialidad
                import streamlit as _st
                _st.session_state.pop("asis_estado_sync", None)
                _st.session_state.pop("asis_loaded", None)
            except Exception:
                pass

            st.success("✅ Baja aplicada. Los cambios se reflejarán en Presencialidad al instante.")
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
