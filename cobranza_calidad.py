"""
cobranza_calidad.py
Módulo de Gestión de Cobranza y Calidad.

- Fuente: Google Sheet "Facturas - Calidad", pestaña "Consolidado".
- Columnas A..M (13) = SOLO ANALISTA (solo lectura para dealers).
- Columna N (Responsable BO) en adelante hasta el 3er intento = EDITABLE por el dealer.
- Solo 3 intentos habilitados (Intento 4 y 5, si existen en la hoja, se ignoran).
- Columnas boleta_2/boleta_3 (si existen al final) = SOLO ANALISTA.
- Lectura de cabeceras DINÁMICA: si el analista agrega una columna nueva, aparece sola.
- Escritura CELDA A CELDA (gspread Cell / update_cells dirigido a fila+columna exacta):
  nunca se reescribe la hoja completa, así 2+ usuarios editando filas distintas
  jamás se pisan entre sí.
- Bloqueo por fila: una vez guardado un intento, esos campos quedan de solo lectura.
- Corte automático: el período actual (columna PERIODO) es editable solo hasta el
  día 20 de cada mes; desde el día 21 a las 00:00 (hora Perú) pasa a solo lectura
  y descarga. Los períodos anteriores siempre son de solo lectura.
- Árbol de tipificación estandarizado (cascada forzada MEDIO → HORARIO → TIPO
  CONTACTO → ACCIÓN → [FECHA COMPROMISO | MOTIVO DE NO PAGO] según corresponda).
"""
from datetime import datetime, date
import pandas as pd
import pytz
import streamlit as st
from gspread.cell import Cell

zona_peru = pytz.timezone("America/Lima")


def _ahora_peru():
    return datetime.now(zona_peru)


def _hoy_peru() -> date:
    return _ahora_peru().date()


def _periodo_actual() -> str:
    """Formato YYYYMM, ej: 202607."""
    return _ahora_peru().strftime("%Y%m")


def _normalizar_razon(s: str) -> str:
    return str(s).strip().upper().replace(".", "").replace("-", "").replace("  ", " ")


# =========================
# ÁRBOL DE TIPIFICACIÓN ESTANDARIZADO
# =========================
OPCIONES_MEDIO = ["", "Llamada de voz", "Whatsapp", "Campo"]
OPCIONES_HORARIO = ["", "8AM - 12PM", "12PM - 3PM", "3PM - 6PM", "6PM - Cierre"]
OPCIONES_TIPO_CONTACTO = ["", "EFECTIVO", "NO EFECTIVO"]

ACCIONES_POR_TIPO = {
    "EFECTIVO": [
        "",
        "Ya pagó",
        "Genera compromiso de pago",
        "Indica no pagará",
        "Otros: detallar",
        "Contesta y cuelga",
        "Contesta y no da razón",
    ],
    "NO EFECTIVO": [
        "",
        "Teléfono apagado",
        "Teléfono suspendido",
        "Teléfono no existe",
        "Timbra y no contesta",
        "Contesta pero desconoce a titular",
    ],
}

# Acciones que obligan a llenar FECHA COMPROMISO
ACCIONES_REQUIEREN_FECHA_COMPROMISO = {"Genera compromiso de pago"}
# Acciones que obligan a llenar MOTIVO DE NO PAGO
ACCIONES_REQUIEREN_MOTIVO = {"Indica no pagará", "Otros: detallar"}

OPCIONES_MOTIVO_NO_PAGO = ["", "Problema técnico", "Error en facturación", "Económicos"]

# Columnas que arma un bloque de "intento" (en este orden, x3)
CAMPOS_INTENTO = ["FECHA", "HORARIO", "MEDIO", "TIPO CONTACTO", "ACCIÓN", "FECHA COMPROMISO", "MOTIVO DE NO PAGO"]
N_INTENTOS_HABILITADOS = 3

# Columnas que llena SOLO el analista (antes del bloque de intentos)
COLS_ANALISTA_INICIO = [
    "NOMBRE_HOJA", "razon_social", "dni_creador_lead", "nombre_creador_lead",
    "fecha_activacion", "cod_cliente", "nombre_cliente", "celular_cliente",
    "plan", "boleta_1_monto", "boleta_1_fecha_pago", "Estado_Pago",
    "cliente_regularizado", "PERIODO",
]
# Columna donde empieza el bloque editable por el dealer
COL_INICIO_DEALER = "Responsable BO"


def _cargar_df(hoja):
    """Lee la hoja completa. Cabeceras dinámicas: si el analista agrega
    una columna nueva, se detecta sola sin tocar código."""
    try:
        vals = hoja.get_all_values()
        if len(vals) < 2:
            return pd.DataFrame(), []
        headers = vals[0]
        df = pd.DataFrame(vals[1:], columns=headers)
        return df, headers
    except Exception as e:
        st.error(f"Error cargando Cobranza_Calidad: {e}")
        return pd.DataFrame(), []


def _col_letra(headers: list, nombre: str) -> int:
    """Índice de columna (1-based) según el nombre de cabecera. None si no existe."""
    try:
        return headers.index(nombre) + 1
    except ValueError:
        return None


def _columnas_intento(headers: list, n_intento: int) -> dict:
    """Devuelve {campo: nombre_columna_real} para el intento N,
    soportando el sufijo ' N' que usa la hoja (ej: 'FECHA 1', 'ACCIÓN 2')."""
    out = {}
    for campo in CAMPOS_INTENTO:
        nombre_col = f"{campo} {n_intento}"
        if nombre_col in headers:
            out[campo] = nombre_col
    return out


def mostrar_cobranza(hoja_cobranza, razon_usuario=None):
    st.markdown("## 💰 Cobranza y Calidad")

    if hoja_cobranza is None:
        st.error("❌ No se pudo conectar con la hoja de Cobranza_Calidad. Verifica que el Sheet esté compartido con la cuenta de servicio.")
        return

    df, headers = _cargar_df(hoja_cobranza)
    if df.empty:
        st.info("Sin registros en la hoja de Cobranza.")
        return

    rol = st.session_state.get("rol", "")

    # ── VALIDACIÓN: dealer sin razón asignada ──────────────────────────
    if rol != "backoffice" and not razon_usuario:
        st.error("❌ Tu usuario no tiene razón social asignada. Contacta al administrador.")
        return

    # ── FILTRO por dealer (igual que Presencialidad y Bajas) ───────────
    if rol != "backoffice" and razon_usuario and "razon_social" in df.columns:
        razon_norm = _normalizar_razon(razon_usuario)
        df = df[df["razon_social"].astype(str).apply(_normalizar_razon).eq(razon_norm)]
        if df.empty:
            st.warning(f"No hay registros de cobranza para tu razón social '{razon_usuario}'.")
            return

    if "PERIODO" not in df.columns:
        st.warning(
            "⚠️ La hoja todavía no tiene la columna **PERIODO**. Pídele al analista que la agregue "
            "(formato: 202607) para poder filtrar por mes y aplicar el corte automático del día 20."
        )
        periodos_disponibles = ["(sin período)"]
    else:
        periodos_disponibles = sorted(df["PERIODO"].astype(str).unique(), reverse=True)

    periodo_sel = st.selectbox("📅 Período", periodos_disponibles, key="cob_periodo_sel")
    if "PERIODO" in df.columns:
        df_periodo = df[df["PERIODO"].astype(str) == str(periodo_sel)].copy()
    else:
        df_periodo = df.copy()

    if df_periodo.empty:
        st.info("Sin registros para ese período.")
        return

    # ── ¿Es el período actual y sigue dentro de la ventana de edición? ──
    periodo_actual = _periodo_actual()
    es_periodo_actual = (str(periodo_sel) == periodo_actual)
    dia_hoy = _hoy_peru().day
    ventana_abierta = es_periodo_actual and dia_hoy <= 20
    puede_editar = ventana_abierta  # backoffice y dealers respetan el mismo corte

    if es_periodo_actual and not ventana_abierta:
        st.warning(
            f"🔒 El período {periodo_sel} ya superó el día 20. Quedó **bloqueado para edición** "
            "(solo lectura y descarga). El próximo período se habilita cuando el analista cargue la nueva data."
        )
    elif not es_periodo_actual:
        st.info(f"📁 Estás viendo un período **histórico** ({periodo_sel}) — solo lectura y descarga.")
    else:
        st.success(f"✏️ Período {periodo_sel} abierto para edición hasta el día 20 (hoy: día {dia_hoy}).")

    st.caption(f"**{len(df_periodo)} registros** en este período.")

    # ── Selector de columnas a mostrar (como en otros módulos) ──────────
    cols_disponibles = list(df_periodo.columns)
    cols_default = [c for c in ["razon_social", "nombre_cliente", "celular_cliente", "cod_cliente",
                                 "Estado_Pago", "Responsable BO", "FECHA 1", "ACCIÓN 1",
                                 "FECHA 2", "ACCIÓN 2", "FECHA 3", "ACCIÓN 3"] if c in cols_disponibles]
    cols_mostrar = st.multiselect(
        "Columnas a mostrar en la tabla", cols_disponibles,
        default=cols_default or cols_disponibles[:12], key="cob_cols_mostrar"
    )
    if cols_mostrar:
        st.dataframe(df_periodo[cols_mostrar], use_container_width=True, height=380)

    # ── Descarga (siempre disponible, edite o no) ───────────────────────
    csv = df_periodo.to_csv(index=False, encoding="utf-8-sig")
    st.download_button(
        f"⬇️ Descargar período {periodo_sel} ({len(df_periodo)} registros)",
        data=csv, file_name=f"cobranza_calidad_{periodo_sel}.csv", mime="text/csv",
        key="cob_descarga"
    )

    if not puede_editar:
        return  # Solo lectura: no se muestra el formulario de registro

    st.divider()
    st.subheader("📋 Registrar gestión de contacto")

    # ── Buscar cliente por código o celular ─────────────────────────────
    c1, c2 = st.columns(2)
    with c1:
        buscar_cod = st.text_input("Código de cliente", key="cob_buscar_cod").strip()
    with c2:
        buscar_cel = st.text_input("Celular", key="cob_buscar_cel").strip()

    df_busq = df_periodo.copy()
    if buscar_cod and "cod_cliente" in df_busq.columns:
        df_busq = df_busq[df_busq["cod_cliente"].astype(str).str.contains(buscar_cod, na=False)]
    if buscar_cel and "celular_cliente" in df_busq.columns:
        df_busq = df_busq[df_busq["celular_cliente"].astype(str).str.contains(buscar_cel, na=False)]

    if not (buscar_cod or buscar_cel):
        st.info("Ingresa código de cliente o celular para buscar el registro a gestionar.")
        return
    if df_busq.empty:
        st.error("❌ No se encontró ningún cliente con esos datos en este período.")
        return

    opciones_idx = df_busq.index.tolist()
    idx_sel = st.selectbox(
        "Cliente encontrado",
        opciones_idx,
        format_func=lambda i: (
            f"{df_busq.loc[i].get('nombre_cliente','')} — "
            f"Cod: {df_busq.loc[i].get('cod_cliente','')} — "
            f"Cel: {df_busq.loc[i].get('celular_cliente','')}"
        ),
        key="cob_cliente_sel"
    )
    fila = df_busq.loc[idx_sel]
    row_sheet = int(idx_sel) + 2  # +1 por índice 0-based, +1 por la fila de cabecera

    st.info(
        f"**{fila.get('nombre_cliente','')}** · Plan: {fila.get('plan','')} · "
        f"Boleta: S/ {fila.get('boleta_1_monto','')} · Estado: {fila.get('Estado_Pago','')}"
    )

    # ── Determinar en qué intento va (bloqueo por fila) ─────────────────
    intento_libre = None
    for n in range(1, N_INTENTOS_HABILITADOS + 1):
        cols_n = _columnas_intento(headers, n)
        col_fecha = cols_n.get("FECHA")
        ya_lleno = col_fecha and str(fila.get(col_fecha, "")).strip() != ""
        if not ya_lleno:
            intento_libre = n
            break

    # Mostrar los intentos ya guardados como solo lectura
    for n in range(1, N_INTENTOS_HABILITADOS + 1):
        cols_n = _columnas_intento(headers, n)
        if not cols_n:
            continue
        col_fecha = cols_n.get("FECHA")
        ya_lleno = col_fecha and str(fila.get(col_fecha, "")).strip() != ""
        if ya_lleno:
            with st.expander(f"✅ Intento {n} — ya registrado (bloqueado)", expanded=False):
                for campo, col in cols_n.items():
                    st.text(f"{campo}: {fila.get(col, '')}")

    if intento_libre is None:
        st.warning(f"⚠️ Este cliente ya agotó los {N_INTENTOS_HABILITADOS} intentos disponibles en este período.")
        return

    st.markdown(f"### ➕ Registrar Intento {intento_libre}")
    cols_n = _columnas_intento(headers, intento_libre)
    if not cols_n:
        st.error(f"❌ La hoja no tiene las columnas del Intento {intento_libre} (revisa cabeceras 'FECHA {intento_libre}', 'ACCIÓN {intento_libre}', etc.)")
        return

    # Responsable BO (solo si la columna existe y aún está vacía)
    responsable_bo_actual = str(fila.get(COL_INICIO_DEALER, "")).strip()
    if COL_INICIO_DEALER in headers:
        responsable_bo = st.text_input(
            "Responsable BO (quién de tu equipo gestiona este caso)",
            value=responsable_bo_actual, key=f"cob_resp_bo_{row_sheet}"
        )
    else:
        responsable_bo = None

    fc1, fc2, fc3 = st.columns(3)
    with fc1:
        fecha_contacto = st.date_input("Fecha de contacto", value=_hoy_peru(), key=f"cob_fecha_{row_sheet}_{intento_libre}")
    with fc2:
        horario = st.selectbox("Horario", OPCIONES_HORARIO, key=f"cob_horario_{row_sheet}_{intento_libre}")
    with fc3:
        medio = st.selectbox("Medio", OPCIONES_MEDIO, key=f"cob_medio_{row_sheet}_{intento_libre}")

    tipo_contacto = st.selectbox("Tipo de contacto", OPCIONES_TIPO_CONTACTO, key=f"cob_tipo_{row_sheet}_{intento_libre}")

    accion = ""
    fecha_compromiso = None
    motivo_no_pago = ""
    if tipo_contacto in ACCIONES_POR_TIPO:
        accion = st.selectbox("Acción", ACCIONES_POR_TIPO[tipo_contacto], key=f"cob_accion_{row_sheet}_{intento_libre}")
        if accion in ACCIONES_REQUIEREN_FECHA_COMPROMISO:
            fecha_compromiso = st.date_input("Fecha compromiso de pago", key=f"cob_fc_{row_sheet}_{intento_libre}")
        if accion in ACCIONES_REQUIEREN_MOTIVO:
            motivo_no_pago = st.selectbox("Motivo de no pago", OPCIONES_MOTIVO_NO_PAGO, key=f"cob_motivo_{row_sheet}_{intento_libre}")

    if st.button(f"💾 Guardar Intento {intento_libre}", type="primary", key=f"cob_guardar_{row_sheet}_{intento_libre}"):
        errores = []
        if not medio:
            errores.append("Selecciona el Medio")
        if not tipo_contacto:
            errores.append("Selecciona el Tipo de contacto")
        if tipo_contacto and not accion:
            errores.append("Selecciona la Acción")
        if accion in ACCIONES_REQUIEREN_FECHA_COMPROMISO and not fecha_compromiso:
            errores.append("Esta acción requiere Fecha compromiso de pago")
        if accion in ACCIONES_REQUIEREN_MOTIVO and not motivo_no_pago:
            errores.append("Esta acción requiere Motivo de no pago")

        if errores:
            for e in errores:
                st.error(f"❌ {e}")
            return

        try:
            celdas = []
            valores = {
                "FECHA": str(fecha_contacto),
                "HORARIO": horario,
                "MEDIO": medio,
                "TIPO CONTACTO": tipo_contacto,
                "ACCIÓN": accion,
                "FECHA COMPROMISO": str(fecha_compromiso) if fecha_compromiso else "",
                "MOTIVO DE NO PAGO": motivo_no_pago,
            }
            for campo, col_nombre in cols_n.items():
                col_idx = _col_letra(headers, col_nombre)
                if col_idx:
                    celdas.append(Cell(row_sheet, col_idx, valores.get(campo, "")))

            if responsable_bo is not None and responsable_bo != responsable_bo_actual:
                col_idx_resp = _col_letra(headers, COL_INICIO_DEALER)
                if col_idx_resp:
                    celdas.append(Cell(row_sheet, col_idx_resp, responsable_bo))

            if celdas:
                # UNA sola llamada a la API, dirigida a la fila y columnas exactas.
                # No se reescribe la hoja completa -> sin choques entre usuarios.
                hoja_cobranza.update_cells(celdas, value_input_option="USER_ENTERED")

            st.success(f"✅ Intento {intento_libre} guardado. Fila bloqueada para edición futura.")
            st.rerun()
        except Exception as e:
            st.error(f"❌ Error al guardar: {e}")
