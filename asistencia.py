from datetime import datetime, timedelta

import pandas as pd
import streamlit as st

# =====================================================
# ASISTENCIA - VERSION ESTABLE
# - Muestra DIA_1 a DIA_31 como espejo del Drive
# - Solo permite editar la semana actual
# - No lee Google Sheets en cada cambio de celda
# - Guarda al Drive solo al presionar Guardar
# - Solo considera cargos que contienen PROMOTOR
# =====================================================

COLUMNAS_BASE = [
    "SUPERVISOR",
    "COORDINADOR",
    "DEPARTAMENTO",
    "PROVINCIA",
    "DNI",
    "NOMBRE",
    "ESTADO",
    "MES",
    "PERIODO",
]

COLUMNAS_DIAS = [f"DIA_{i}" for i in range(1, 32)]
COLUMNAS_ASISTENCIA = COLUMNAS_BASE + COLUMNAS_DIAS

COLUMNAS_BASE_VISTA = [
    "DNI",
    "NOMBRE",
    "SUPERVISOR",
    "COORDINADOR",
    "DEPARTAMENTO",
    "PROVINCIA",
    "ESTADO",
    "PERIODO",
]

KEY_DF_CACHE = "asis_df_total_cache"
KEY_CACHE_PERIODO = "asis_cache_periodo"
KEY_CACHE_OK = "asis_cache_ok"


# =====================================================
# UTILIDADES
# =====================================================
def normalizar_columnas(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = df.columns.astype(str).str.strip().str.upper()
    return df


def periodo_actual() -> str:
    return datetime.now().strftime("%Y-%m")


def mes_actual() -> str:
    return str(datetime.now().month)


def dias_semana_actual() -> list[int]:
    hoy = datetime.now().date()
    inicio = hoy - timedelta(days=hoy.weekday())
    dias = []
    for i in range(7):
        fecha = inicio + timedelta(days=i)
        if fecha.month == hoy.month:
            dias.append(fecha.day)
    return dias


def limpiar_texto(valor) -> str:
    if pd.isna(valor):
        return ""
    return str(valor).strip()


def limpiar_marca(valor) -> str:
    if pd.isna(valor):
        return ""
    valor = str(valor).strip().upper()
    if valor in ["A", "F"]:
        return valor
    return ""


def letra_columna(numero: int) -> str:
    letras = ""
    while numero:
        numero, resto = divmod(numero - 1, 26)
        letras = chr(65 + resto) + letras
    return letras


def es_promotor(row: pd.Series) -> bool:
    cargo = ""
    for col in ["CARGO (ROL)", "CARGO", "ROL"]:
        if col in row.index:
            cargo = limpiar_texto(row.get(col, "")).upper()
            break

    # Si no existe columna cargo, no bloqueamos para no dejar la vista vacía.
    if not cargo:
        return True

    return "PROMOTOR" in cargo


# =====================================================
# GOOGLE SHEETS
# =====================================================
def validar_o_crear_cabecera(hoja_asistencia) -> bool:
    valores = hoja_asistencia.get_all_values()

    if not valores:
        hoja_asistencia.append_row(COLUMNAS_ASISTENCIA, value_input_option="USER_ENTERED")
        return True

    headers = [str(x).strip().upper() for x in valores[0]]
    faltantes = [c for c in COLUMNAS_ASISTENCIA if c not in headers]

    if faltantes:
        st.error("La hoja Asistencia tiene cabecera incompleta o diferente.")
        st.write("Columnas faltantes:", faltantes)
        st.warning("Solución: borra solo el contenido de la pestaña Asistencia y vuelve a sincronizar mes.")
        return False

    return True


def leer_asistencia_drive(hoja_asistencia) -> pd.DataFrame:
    valores = hoja_asistencia.get_all_values()

    if not valores:
        return pd.DataFrame(columns=COLUMNAS_ASISTENCIA)

    headers = [str(x).strip().upper() for x in valores[0]]
    data = valores[1:]

    filas = []
    for fila in data:
        fila = list(fila)
        if len(fila) < len(headers):
            fila += [""] * (len(headers) - len(fila))
        if len(fila) > len(headers):
            fila = fila[:len(headers)]
        filas.append(fila)

    df = pd.DataFrame(filas, columns=headers).fillna("").replace("None", "")
    df = normalizar_columnas(df)

    for col in COLUMNAS_ASISTENCIA:
        if col not in df.columns:
            df[col] = ""

    df = df[COLUMNAS_ASISTENCIA].copy()
    df["ROW_SHEET"] = df.index + 2

    for col in COLUMNAS_DIAS:
        df[col] = df[col].apply(limpiar_marca)

    return df


def cargar_cache_desde_drive(hoja_asistencia, forzar: bool = False) -> pd.DataFrame:
    periodo = periodo_actual()

    cache_no_existe = KEY_DF_CACHE not in st.session_state
    periodo_cambio = st.session_state.get(KEY_CACHE_PERIODO) != periodo

    if forzar or cache_no_existe or periodo_cambio:
        df = leer_asistencia_drive(hoja_asistencia)
        st.session_state[KEY_DF_CACHE] = df
        st.session_state[KEY_CACHE_PERIODO] = periodo
        st.session_state[KEY_CACHE_OK] = True

    return st.session_state[KEY_DF_CACHE].copy()


def actualizar_cache_celda(row_sheet: int, columna: str, valor: str):
    if KEY_DF_CACHE not in st.session_state:
        return

    df = st.session_state[KEY_DF_CACHE].copy()
    mask = df["ROW_SHEET"].eq(row_sheet)
    if mask.any() and columna in df.columns:
        df.loc[mask, columna] = limpiar_marca(valor)
        st.session_state[KEY_DF_CACHE] = df


def leer_colaboradores(hoja_colaboradores) -> pd.DataFrame:
    data = hoja_colaboradores.get_all_records()
    df = pd.DataFrame(data)
    if df.empty:
        return pd.DataFrame()
    df = normalizar_columnas(df).fillna("").replace("None", "")
    return df


# =====================================================
# PROMOTORES
# =====================================================
def obtener_promotores_activos(df_colab: pd.DataFrame) -> pd.DataFrame:
    if df_colab.empty:
        return pd.DataFrame()

    if "DNI" not in df_colab.columns or "ESTADO" not in df_colab.columns:
        return pd.DataFrame()

    df = df_colab.copy()
    df = df[df["ESTADO"].astype(str).str.strip().str.upper().eq("ACTIVO")].copy()

    if df.empty:
        return df

    df = df[df.apply(es_promotor, axis=1)].copy()
    df["DNI"] = df["DNI"].astype(str).str.strip()
    df = df[df["DNI"].ne("")].copy()
    return df


def dnis_promotores_activos(df_colab: pd.DataFrame) -> set[str]:
    df = obtener_promotores_activos(df_colab)
    if df.empty:
        return set()
    return set(df["DNI"].astype(str).str.strip().tolist())


# =====================================================
# SINCRONIZAR MES
# =====================================================
def construir_registros_nuevos(df_colab: pd.DataFrame, dnis_existentes: set[str]) -> list[list[str]]:
    df_prom = obtener_promotores_activos(df_colab)
    if df_prom.empty:
        return []

    periodo = periodo_actual()
    mes = mes_actual()
    registros = []

    for _, row in df_prom.iterrows():
        dni = limpiar_texto(row.get("DNI", ""))
        if not dni or dni in dnis_existentes:
            continue

        fila = {
            "SUPERVISOR": limpiar_texto(row.get("SUPERVISOR A CARGO", row.get("SUPERVISOR", ""))),
            "COORDINADOR": limpiar_texto(row.get("COORDINADOR", "")),
            "DEPARTAMENTO": limpiar_texto(row.get("DEPARTAMENTO", "")),
            "PROVINCIA": limpiar_texto(row.get("PROVINCIA", "")),
            "DNI": dni,
            "NOMBRE": limpiar_texto(row.get("NOMBRES", row.get("NOMBRE", ""))),
            "ESTADO": "ACTIVO",
            "MES": mes,
            "PERIODO": periodo,
        }
        for col in COLUMNAS_DIAS:
            fila[col] = ""

        registros.append([fila.get(col, "") for col in COLUMNAS_ASISTENCIA])

    return registros


def sincronizar_mes(hoja_asistencia, hoja_colaboradores) -> int:
    if not validar_o_crear_cabecera(hoja_asistencia):
        return 0

    periodo = periodo_actual()
    df_actual = leer_asistencia_drive(hoja_asistencia)

    dnis_existentes = set()
    if not df_actual.empty:
        dnis_existentes = set(
            df_actual.loc[df_actual["PERIODO"].astype(str).eq(periodo), "DNI"]
            .astype(str).str.strip().tolist()
        )

    df_colab = leer_colaboradores(hoja_colaboradores)
    nuevos = construir_registros_nuevos(df_colab, dnis_existentes)

    if nuevos:
        hoja_asistencia.append_rows(nuevos, value_input_option="USER_ENTERED")

    # Después de sincronizar, actualizamos caché para que sea espejo del Drive.
    cargar_cache_desde_drive(hoja_asistencia, forzar=True)

    return len(nuevos)


# =====================================================
# VISUAL
# =====================================================
def estilo_asistencia(valor):
    valor = limpiar_marca(valor)
    if valor == "A":
        return "background-color:#C6EFCE;color:#006100;font-weight:bold;text-align:center;"
    if valor == "F":
        return "background-color:#FFC7CE;color:#9C0006;font-weight:bold;text-align:center;"
    return "text-align:center;"


def mostrar_vista_colores(df: pd.DataFrame):
    if df.empty:
        return

    styler = df.style.applymap(
        estilo_asistencia,
        subset=[c for c in COLUMNAS_DIAS if c in df.columns]
    )
    st.dataframe(styler, use_container_width=True, height=360)


def lista_opciones(df: pd.DataFrame, columna: str) -> list[str]:
    if columna not in df.columns:
        return ["TODOS"]

    valores = (
        df[columna]
        .astype(str)
        .str.strip()
        .replace("", pd.NA)
        .dropna()
        .unique()
        .tolist()
    )
    return ["TODOS"] + sorted(valores)


def aplicar_filtros(df: pd.DataFrame, supervisor: str, coordinador: str, departamento: str) -> pd.DataFrame:
    resultado = df.copy()

    if supervisor != "TODOS":
        resultado = resultado[resultado["SUPERVISOR"].astype(str).str.strip().eq(supervisor)]
    if coordinador != "TODOS":
        resultado = resultado[resultado["COORDINADOR"].astype(str).str.strip().eq(coordinador)]
    if departamento != "TODOS":
        resultado = resultado[resultado["DEPARTAMENTO"].astype(str).str.strip().eq(departamento)]

    return resultado


# =====================================================
# GUARDAR DRIVE
# =====================================================
def guardar_cambios_drive(hoja_asistencia, cambios: dict) -> int:
    """
    cambios = {
      (row_sheet, columna): valor
    }
    """
    if not cambios:
        return 0

    valores = hoja_asistencia.get_all_values()
    if not valores:
        return 0

    headers = [str(x).strip().upper() for x in valores[0]]
    mapa_col = {col: idx + 1 for idx, col in enumerate(headers)}

    updates = []

    for (row_sheet, columna), valor in cambios.items():
        columna = str(columna).strip().upper()
        if columna not in mapa_col:
            continue

        letra = letra_columna(mapa_col[columna])
        updates.append({
            "range": f"{letra}{row_sheet}",
            "values": [[limpiar_marca(valor)]]
        })

    if updates:
        hoja_asistencia.batch_update(updates, value_input_option="USER_ENTERED")

    return len(updates)


# =====================================================
# EDITOR RÁPIDO SIN FREEZE MASIVO
# =====================================================
def mostrar_editor_semana(df_filtrado: pd.DataFrame, cols_editables: list[str]) -> dict:
    cambios = {}

    st.markdown("### Edición semana actual")
    st.caption("Aquí editas solo la semana actual. Abajo se ve todo el mes como espejo del Drive.")

    columnas_mostrar = ["DNI", "NOMBRE", "SUPERVISOR", "COORDINADOR"] + cols_editables + ["ROW_SHEET"]
    df_editar = df_filtrado[columnas_mostrar].copy()

    # Encabezados
    widths = [1.1, 2.2, 1.6, 1.6] + [0.75 for _ in cols_editables]
    header_cols = st.columns(widths)
    headers = ["DNI", "NOMBRE", "SUPERVISOR", "COORDINADOR"] + cols_editables

    for col_obj, titulo in zip(header_cols, headers):
        col_obj.markdown(f"**{titulo}**")

    for _, row in df_editar.iterrows():
        row_sheet = int(row["ROW_SHEET"])
        dni = limpiar_texto(row.get("DNI", ""))

        cols = st.columns(widths)
        cols[0].write(dni)
        cols[1].write(limpiar_texto(row.get("NOMBRE", "")))
        cols[2].write(limpiar_texto(row.get("SUPERVISOR", "")))
        cols[3].write(limpiar_texto(row.get("COORDINADOR", "")))

        for idx, dia_col in enumerate(cols_editables, start=4):
            valor_actual = limpiar_marca(row.get(dia_col, ""))
            opciones = ["", "A", "F"]
            index_default = opciones.index(valor_actual) if valor_actual in opciones else 0

            key = f"asis_sel_{row_sheet}_{dia_col}"

            nuevo = cols[idx].selectbox(
                dia_col,
                opciones,
                index=index_default,
                key=key,
                label_visibility="collapsed"
            )

            nuevo = limpiar_marca(nuevo)
            if nuevo != valor_actual:
                cambios[(row_sheet, dia_col)] = nuevo

    return cambios


# =====================================================
# MAIN
# =====================================================
def mostrar_asistencia(hoja_asistencia, hoja_colaboradores, registro_mod=None, razon=None):
    st.subheader("🗓️ Control de Asistencia")

    if not validar_o_crear_cabecera(hoja_asistencia):
        return

    periodo = periodo_actual()
    dias_editables_num = dias_semana_actual()
    cols_editables = [f"DIA_{d}" for d in dias_editables_num]

    c1, c2 = st.columns([1, 5])

    with c1:
        if st.button("🔄 Sincronizar mes", key="btn_sync_asistencia"):
            try:
                creados = sincronizar_mes(hoja_asistencia, hoja_colaboradores)
                st.success(f"Sincronización correcta. Registros nuevos: {creados}")
            except Exception as e:
                st.error(f"Error sincronizando mes: {e}")
                return

    with c2:
        st.info(
            "Sincronizar mes crea la foto del mes actual desde colaboradores. "
            "Cuando cambia el mes, se presiona una vez y crea el nuevo periodo. "
            "La edición solo guarda al presionar Guardar Asistencia."
        )

    # Carga Drive solo una vez, salvo sincronizar o limpiar caché.
    df_total = cargar_cache_desde_drive(hoja_asistencia, forzar=False)

    df_colab = leer_colaboradores(hoja_colaboradores)
    set_promotores = dnis_promotores_activos(df_colab)

    df_mes = df_total[df_total["PERIODO"].astype(str).eq(periodo)].copy()

    if set_promotores:
        df_mes = df_mes[df_mes["DNI"].astype(str).str.strip().isin(set_promotores)].copy()

    if df_mes.empty:
        st.warning("No hay registros del periodo actual. Presiona Sincronizar mes.")
        return

    # Filtros dependientes
    f1, f2, f3 = st.columns(3)

    with f1:
        filtro_supervisor = st.selectbox(
            "Supervisor",
            lista_opciones(df_mes, "SUPERVISOR"),
            key="asis_filtro_supervisor"
        )

    df_temp = aplicar_filtros(df_mes, filtro_supervisor, "TODOS", "TODOS")

    with f2:
        filtro_coord = st.selectbox(
            "Coordinador",
            lista_opciones(df_temp, "COORDINADOR"),
            key="asis_filtro_coordinador"
        )

    df_temp = aplicar_filtros(df_temp, "TODOS", filtro_coord, "TODOS")

    with f3:
        filtro_dep = st.selectbox(
            "Departamento",
            lista_opciones(df_temp, "DEPARTAMENTO"),
            key="asis_filtro_departamento"
        )

    df_filtrado = aplicar_filtros(df_mes, filtro_supervisor, filtro_coord, filtro_dep)

    if df_filtrado.empty:
        st.warning("No hay registros con los filtros seleccionados.")
        return

    total = len(df_filtrado)

    # Para evitar freeze real, no se editan 1500 filas de golpe.
    # Se ve el mes completo abajo, pero se edita por bloque filtrado.
    if total > 80:
        cantidad = st.slider(
            "Cantidad de promotores a editar en este bloque",
            min_value=20,
            max_value=min(200, total),
            value=min(80, total),
            step=20,
            key="asis_cantidad_bloque"
        )
    else:
        cantidad = total
        st.caption(f"Promotores a editar: {cantidad}")

    df_filtrado = df_filtrado.head(cantidad).copy()

    st.caption("Columnas editables esta semana: " + ", ".join(cols_editables))

    cambios = mostrar_editor_semana(df_filtrado, cols_editables)

    if st.button("💾 Guardar Asistencia", key="btn_guardar_asistencia"):
        try:
            if not cambios:
                st.info("No se detectaron cambios nuevos para guardar.")
            else:
                cantidad_guardada = guardar_cambios_drive(hoja_asistencia, cambios)

                for (row_sheet, dia_col), valor in cambios.items():
                    actualizar_cache_celda(row_sheet, dia_col, valor)

                st.success(f"✅ Asistencia guardada en Drive. Cambios aplicados: {cantidad_guardada}")
        except Exception as e:
            st.error(f"❌ Error guardando asistencia: {e}")

    st.markdown("### Vista espejo del mes completo")
    st.caption("Esta vista muestra DIA_1 a DIA_31. Si necesitas confirmar contra Drive, vuelve a entrar o presiona Sincronizar mes.")
    mostrar_vista_colores(df_filtrado[COLUMNAS_BASE_VISTA + COLUMNAS_DIAS].copy())

    if registro_mod is not None:
        st.divider()
        st.subheader("📋 Matriz de jerarquía")
        try:
            registro_mod.mostrar_tabla(hoja_colaboradores, razon)
        except Exception as e:
            st.warning(f"No se pudo cargar la matriz inferior de jerarquía: {e}")
