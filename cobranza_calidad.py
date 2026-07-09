"""
cobranza_calidad.py v2.0
Módulo de Cobranza — Seguimiento de Calidad
Diseño profesional con marca WOW.
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
    return _ahora_peru().strftime("%Y%m")

def _normalizar_razon(s: str) -> str:
    return str(s).strip().upper().replace(".", "").replace("-", "").replace("  ", " ")

# =========================
# ÁRBOL DE TIPIFICACIÓN
# =========================
OPCIONES_MEDIO = ["", "Llamada de voz", "Whatsapp", "Campo"]
OPCIONES_HORARIO = ["", "8AM - 12PM", "12PM - 3PM", "3PM - 6PM", "6PM - Cierre"]
OPCIONES_TIPO_CONTACTO = ["", "EFECTIVO", "NO EFECTIVO"]

ACCIONES_POR_TIPO = {
    "EFECTIVO": [
        "", "Ya pagó", "Genera compromiso de pago", "Indica no pagará",
        "Otros: detallar", "Contesta y cuelga", "Contesta y no da razón",
    ],
    "NO EFECTIVO": [
        "", "Teléfono apagado", "Teléfono suspendido", "Teléfono no existe",
        "Timbra y no contesta", "Contesta pero desconoce a titular",
    ],
}
ACCIONES_REQUIEREN_FECHA_COMPROMISO = {"Genera compromiso de pago"}
ACCIONES_REQUIEREN_MOTIVO = {"Indica no pagará", "Otros: detallar"}
OPCIONES_MOTIVO_NO_PAGO = ["", "Problema técnico", "Error en facturación", "Económicos"]

CAMPOS_INTENTO = ["FECHA", "HORARIO", "MEDIO", "TIPO CONTACTO", "ACCIÓN", "FECHA COMPROMISO", "MOTIVO DE NO PAGO"]
N_INTENTOS = 3
COL_INICIO_DEALER = "Responsable BO"

# =========================
# ESTILOS WOW PROFESIONAL
# =========================
HEADER_HTML = """
<div style="background: linear-gradient(135deg, #4B0067 0%, #7B1FA2 50%, #EC6608 100%);
            border-radius: 12px; padding: 28px 32px; margin-bottom: 24px;
            box-shadow: 0 4px 20px rgba(75,0,103,0.25);">
    <div style="display:flex; align-items:center; gap:16px;">
        <div style="font-size:36px;">💰</div>
        <div>
            <h1 style="color:white; margin:0; font-size:28px; font-weight:800;
                       font-family:'Plus Jakarta Sans',sans-serif; letter-spacing:-0.5px;">
                Cobranza — Seguimiento de Calidad
            </h1>
            <p style="color:rgba(255,255,255,0.85); margin:4px 0 0; font-size:14px;
                      font-family:'Plus Jakarta Sans',sans-serif;">
                ✦ WOW Servicios de Internet · Gestión de contactabilidad y recuperación
            </p>
        </div>
    </div>
</div>
"""

TABLE_CSS = """
<style>
.cobranza-table {
    font-family: 'Plus Jakarta Sans', sans-serif;
    font-size: 12px;
    border-collapse: collapse;
    width: 100%;
    margin: 12px 0;
}
.cobranza-table thead th {
    background: linear-gradient(180deg, #4B0067 0%, #5C1187 100%);
    color: white;
    font-weight: 700;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.3px;
    padding: 10px 8px;
    text-align: left;
    position: sticky;
    top: 0;
    white-space: nowrap;
    border: none;
}
.cobranza-table tbody tr { border-bottom: 1px solid #E5E0EA; }
.cobranza-table tbody tr:nth-child(even) { background: #FAF3FE; }
.cobranza-table tbody tr:hover { background: #F3E5FA !important; }
.cobranza-table td {
    padding: 7px 8px;
    color: #1A1521;
    white-space: nowrap;
    max-width: 220px;
    overflow: hidden;
    text-overflow: ellipsis;
}
.cobranza-table td.efectivo { background: #E8F5E9; color: #2E7D32; font-weight: 600; }
.cobranza-table td.no-efectivo { background: #FDE6D2; color: #D45605; font-weight: 600; }
.cobranza-table td.pago { background: #C8E6C9; color: #1B5E20; font-weight: 700; }
.cobranza-badge {
    display: inline-block; padding: 3px 10px; border-radius: 12px;
    font-size: 11px; font-weight: 600;
}
.cobranza-badge.abierto { background: #E8F5E9; color: #2E7D32; }
.cobranza-badge.cerrado { background: #FDE6D2; color: #BF360C; }
.cobranza-badge.historico { background: #E5E0EA; color: #4B0067; }
.cobranza-kpi {
    background: white; border: 1px solid #E5E0EA; border-radius: 10px;
    padding: 16px; text-align: center; box-shadow: 0 2px 8px rgba(0,0,0,0.04);
}
.cobranza-kpi .num { font-size: 28px; font-weight: 800; color: #4B0067; }
.cobranza-kpi .label { font-size: 12px; color: #6B6175; margin-top: 4px; }
</style>
"""

INTENTO_BLOQUEADO_CSS = """
<div style="background:#F2EEF5; border-left:4px solid #4B0067; border-radius:0 8px 8px 0;
            padding:12px 16px; margin:6px 0; font-size:13px; font-family:'Plus Jakarta Sans',sans-serif;">
    <span style="color:#4B0067; font-weight:700;">✅ Intento {n}</span>
    <span style="color:#6B6175;"> — {fecha} · {medio} · {tipo} · {accion}</span>
</div>
"""


def _cargar_df(hoja):
    try:
        vals = hoja.get_all_values()
        if len(vals) < 2:
            return pd.DataFrame(), []
        return pd.DataFrame(vals[1:], columns=vals[0]), vals[0]
    except Exception as e:
        st.error(f"Error cargando datos: {e}")
        return pd.DataFrame(), []


def _col_letra(headers, nombre):
    try:
        return headers.index(nombre) + 1
    except ValueError:
        return None


def _columnas_intento(headers, n):
    out = {}
    for campo in CAMPOS_INTENTO:
        nombre_col = f"{campo} {n}"
        if nombre_col in headers:
            out[campo] = nombre_col
    return out


def _render_tabla_html(df, cols):
    """Renderiza tabla HTML profesional con colores WOW."""
    html = TABLE_CSS + "<div style='overflow-x:auto; max-height:480px;'><table class='cobranza-table'><thead><tr>"
    for c in cols:
        html += f"<th>{c}</th>"
    html += "</tr></thead><tbody>"
    for _, row in df[cols].iterrows():
        html += "<tr>"
        for c in cols:
            val = str(row.get(c, ""))
            css_class = ""
            if val == "EFECTIVO":
                css_class = " class='efectivo'"
            elif val == "NO EFECTIVO":
                css_class = " class='no-efectivo'"
            elif val == "Ya pagó":
                css_class = " class='pago'"
            html += f"<td{css_class}>{val}</td>"
        html += "</tr>"
    html += "</tbody></table></div>"
    return html


def mostrar_cobranza(hoja_cobranza, razon_usuario=None):
    st.markdown(HEADER_HTML, unsafe_allow_html=True)

    if hoja_cobranza is None:
        return

    df, headers = _cargar_df(hoja_cobranza)
    if df.empty:
        st.info("Sin registros en la hoja de Cobranza.")
        return

    rol = st.session_state.get("rol", "")
    usuario_actual = st.session_state.get("usuario", "admin")

    if rol != "backoffice" and not razon_usuario:
        st.error("❌ Tu usuario no tiene razón social asignada. Contacta al administrador.")
        return

    if rol != "backoffice" and razon_usuario and "razon_social" in df.columns:
        razon_norm = _normalizar_razon(razon_usuario)
        df = df[df["razon_social"].astype(str).apply(_normalizar_razon).eq(razon_norm)]
        if df.empty:
            st.warning(f"No hay registros de cobranza para tu razón social.")
            return

    # ── PERÍODO ──
    if "PERIODO" not in df.columns:
        st.warning("⚠️ Falta la columna **PERIODO** en la hoja. El analista debe agregarla (formato: 202607).")
        periodos = ["(sin período)"]
    else:
        periodos = sorted(df["PERIODO"].astype(str).str.strip().unique(), reverse=True)
        periodos = [p for p in periodos if p and p != ""]

    periodo_sel = st.selectbox("📅 Período", periodos, key="cob_per")
    if "PERIODO" in df.columns:
        df_p = df[df["PERIODO"].astype(str).str.strip() == str(periodo_sel)].copy()
    else:
        df_p = df.copy()

    if df_p.empty:
        st.info("Sin registros para ese período.")
        return

    periodo_actual = _periodo_actual()
    es_actual = (str(periodo_sel).strip() == periodo_actual)
    dia_hoy = _hoy_peru().day
    puede_editar = es_actual and dia_hoy <= 20

    # ── BADGE DE ESTADO ──
    if es_actual and puede_editar:
        badge = f"<span class='cobranza-badge abierto'>✏️ ABIERTO — editable hasta el día 20 (hoy: día {dia_hoy})</span>"
    elif es_actual:
        badge = "<span class='cobranza-badge cerrado'>🔒 CERRADO — superó el día 20, solo lectura y descarga</span>"
    else:
        badge = f"<span class='cobranza-badge historico'>📁 HISTÓRICO ({periodo_sel}) — solo lectura y descarga</span>"
    st.markdown(TABLE_CSS + badge, unsafe_allow_html=True)

    # ── KPIs ──
    total = len(df_p)
    with_accion1 = sum(1 for _, r in df_p.iterrows() if str(r.get("ACCIÓN 1", "")).strip() != "") if "ACCIÓN 1" in df_p.columns else 0
    with_accion2 = sum(1 for _, r in df_p.iterrows() if str(r.get("ACCIÓN 2", "")).strip() != "") if "ACCIÓN 2" in df_p.columns else 0
    with_accion3 = sum(1 for _, r in df_p.iterrows() if str(r.get("ACCIÓN 3", "")).strip() != "") if "ACCIÓN 3" in df_p.columns else 0
    pct1 = f"{with_accion1/total*100:.0f}%" if total > 0 else "0%"
    pct2 = f"{with_accion2/total*100:.0f}%" if total > 0 else "0%"
    pct3 = f"{with_accion3/total*100:.0f}%" if total > 0 else "0%"

    k1, k2, k3, k4 = st.columns(4)
    for col, num, label in [(k1, str(total), "Total registros"), (k2, f"{with_accion1} ({pct1})", "Intento 1"), (k3, f"{with_accion2} ({pct2})", "Intento 2"), (k4, f"{with_accion3} ({pct3})", "Intento 3")]:
        col.markdown(f"<div class='cobranza-kpi'><div class='num'>{num}</div><div class='label'>{label}</div></div>", unsafe_allow_html=True)

    # ── SELECTOR DE COLUMNAS ──
    cols_disponibles = list(df_p.columns)
    cols_default = [c for c in ["razon_social", "nombre_cliente", "celular_cliente", "cod_cliente",
                                 "Estado_Pago", "Responsable BO", "FECHA 1", "TIPO CONTACTO 1", "ACCIÓN 1",
                                 "FECHA 2", "TIPO CONTACTO 2", "ACCIÓN 2", "FECHA 3", "TIPO CONTACTO 3", "ACCIÓN 3"] if c in cols_disponibles]
    cols_mostrar = st.multiselect("Columnas visibles", cols_disponibles,
                                  default=cols_default or cols_disponibles[:12], key="cob_cols")

    if cols_mostrar:
        st.markdown(_render_tabla_html(df_p.head(200), cols_mostrar), unsafe_allow_html=True)
        if len(df_p) > 200:
            st.caption(f"Mostrando 200 de {len(df_p)} registros. Descarga el CSV para ver todo.")

    csv = df_p.to_csv(index=False, encoding="utf-8-sig")
    st.download_button(f"⬇️ Descargar período {periodo_sel} ({total} registros)",
                       data=csv, file_name=f"cobranza_{periodo_sel}.csv", mime="text/csv", key="cob_dl")

    if not puede_editar:
        return

    # ═══════════════════════════════════════════════════════════
    # FORMULARIO DE REGISTRO (solo si período abierto)
    # ═══════════════════════════════════════════════════════════
    st.divider()
    st.markdown("""
    <div style="background:linear-gradient(90deg,#4B0067,#7B1FA2); padding:12px 20px;
                border-radius:8px; margin-bottom:16px;">
        <h3 style="color:white; margin:0; font-size:18px; font-weight:700;
                   font-family:'Plus Jakarta Sans',sans-serif;">
            📋 Registrar gestión de contacto
        </h3>
    </div>
    """, unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    with c1:
        buscar_cod = st.text_input("🔍 Código de cliente", key="cob_bcod").strip()
    with c2:
        buscar_cel = st.text_input("📱 Celular", key="cob_bcel").strip()

    if not (buscar_cod or buscar_cel):
        st.info("Ingresa código de cliente o celular para buscar el registro a gestionar.")
        return

    df_busq = df_p.copy()
    if buscar_cod and "cod_cliente" in df_busq.columns:
        df_busq = df_busq[df_busq["cod_cliente"].astype(str).str.contains(buscar_cod, na=False)]
    if buscar_cel and "celular_cliente" in df_busq.columns:
        df_busq = df_busq[df_busq["celular_cliente"].astype(str).str.contains(buscar_cel, na=False)]

    if df_busq.empty:
        st.error("❌ No se encontró ningún cliente con esos datos.")
        return

    opciones_idx = df_busq.index.tolist()
    idx_sel = st.selectbox(
        "Cliente encontrado", opciones_idx,
        format_func=lambda i: (
            f"{df_busq.loc[i].get('nombre_cliente','')} — "
            f"Cod: {df_busq.loc[i].get('cod_cliente','')} — "
            f"Cel: {df_busq.loc[i].get('celular_cliente','')}"
        ), key="cob_csel"
    )
    fila = df_busq.loc[idx_sel]
    row_sheet = int(idx_sel) + 2

    # ── INFO DEL CLIENTE (card profesional) ──
    st.markdown(f"""
    <div style="background:white; border:1px solid #E5E0EA; border-radius:10px; padding:16px 20px;
                margin:12px 0; box-shadow:0 2px 8px rgba(0,0,0,0.04);">
        <div style="display:flex; justify-content:space-between; flex-wrap:wrap; gap:12px;">
            <div><span style="color:#6B6175; font-size:11px;">CLIENTE</span><br>
                 <span style="font-weight:700; color:#1A1521;">{fila.get('nombre_cliente','')}</span></div>
            <div><span style="color:#6B6175; font-size:11px;">CÓDIGO</span><br>
                 <span style="font-weight:600;">{fila.get('cod_cliente','')}</span></div>
            <div><span style="color:#6B6175; font-size:11px;">CELULAR</span><br>
                 <span style="font-weight:600;">{fila.get('celular_cliente','')}</span></div>
            <div><span style="color:#6B6175; font-size:11px;">PLAN</span><br>
                 <span style="font-weight:600;">{fila.get('plan','')}</span></div>
            <div><span style="color:#6B6175; font-size:11px;">BOLETA</span><br>
                 <span style="font-weight:700; color:#D45605;">S/ {fila.get('boleta_1_monto','')}</span></div>
            <div><span style="color:#6B6175; font-size:11px;">ESTADO</span><br>
                 <span style="font-weight:700; color:#C62828;">{fila.get('Estado_Pago','')}</span></div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── INTENTOS YA REGISTRADOS (bloqueados, solo vista) ──
    intento_libre = None
    for n in range(1, N_INTENTOS + 1):
        cols_n = _columnas_intento(headers, n)
        col_fecha = cols_n.get("FECHA")
        ya_lleno = col_fecha and str(fila.get(col_fecha, "")).strip() != ""
        if ya_lleno:
            fecha_r = fila.get(cols_n.get("FECHA", ""), "")
            medio_r = fila.get(cols_n.get("MEDIO", ""), "")
            tipo_r = fila.get(cols_n.get("TIPO CONTACTO", ""), "")
            accion_r = fila.get(cols_n.get("ACCIÓN", ""), "")
            st.markdown(
                INTENTO_BLOQUEADO_CSS.format(n=n, fecha=fecha_r, medio=medio_r, tipo=tipo_r, accion=accion_r),
                unsafe_allow_html=True
            )
        else:
            if intento_libre is None:
                intento_libre = n

    if intento_libre is None:
        st.warning(f"⚠️ Este cliente ya agotó los {N_INTENTOS} intentos en este período.")
        return

    cols_n = _columnas_intento(headers, intento_libre)
    if not cols_n:
        st.error(f"❌ Faltan columnas del Intento {intento_libre} en la hoja (FECHA {intento_libre}, ACCIÓN {intento_libre}, etc.)")
        return

    st.markdown(f"""
    <div style="background:#EC6608; padding:8px 16px; border-radius:6px; margin:12px 0 8px;">
        <span style="color:white; font-weight:700; font-size:15px;">➕ Registrar Intento {intento_libre}</span>
    </div>
    """, unsafe_allow_html=True)

    # Responsable BO
    resp_actual = str(fila.get(COL_INICIO_DEALER, "")).strip()
    if COL_INICIO_DEALER in headers:
        responsable_bo = st.text_input("👤 Responsable BO", value=resp_actual, key=f"cob_resp_{row_sheet}")
    else:
        responsable_bo = None

    fc1, fc2, fc3 = st.columns(3)
    with fc1:
        fecha_contacto = st.date_input("📅 Fecha de contacto", value=_hoy_peru(), key=f"cob_f_{row_sheet}_{intento_libre}")
    with fc2:
        horario = st.selectbox("🕐 Horario", OPCIONES_HORARIO, key=f"cob_h_{row_sheet}_{intento_libre}")
    with fc3:
        medio = st.selectbox("📞 Medio", OPCIONES_MEDIO, key=f"cob_m_{row_sheet}_{intento_libre}")

    tipo_contacto = st.selectbox("🎯 Tipo de contacto", OPCIONES_TIPO_CONTACTO, key=f"cob_t_{row_sheet}_{intento_libre}")

    accion = ""
    fecha_compromiso = None
    motivo_no_pago = ""
    if tipo_contacto in ACCIONES_POR_TIPO:
        accion = st.selectbox("⚡ Acción", ACCIONES_POR_TIPO[tipo_contacto], key=f"cob_a_{row_sheet}_{intento_libre}")
        if accion in ACCIONES_REQUIEREN_FECHA_COMPROMISO:
            fecha_compromiso = st.date_input("📆 Fecha compromiso de pago", key=f"cob_fc_{row_sheet}_{intento_libre}")
        if accion in ACCIONES_REQUIEREN_MOTIVO:
            motivo_no_pago = st.selectbox("❓ Motivo de no pago", OPCIONES_MOTIVO_NO_PAGO, key=f"cob_mnp_{row_sheet}_{intento_libre}")

    if st.button(f"💾 Guardar Intento {intento_libre}", type="primary", use_container_width=True, key=f"cob_g_{row_sheet}_{intento_libre}"):
        errores = []
        if not medio:
            errores.append("Selecciona el Medio")
        if not tipo_contacto:
            errores.append("Selecciona el Tipo de contacto")
        if tipo_contacto and not accion:
            errores.append("Selecciona la Acción")
        if accion in ACCIONES_REQUIEREN_FECHA_COMPROMISO and not fecha_compromiso:
            errores.append("Fecha compromiso de pago es obligatoria para esta acción")
        if accion in ACCIONES_REQUIEREN_MOTIVO and not motivo_no_pago:
            errores.append("Motivo de no pago es obligatorio para esta acción")

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

            if responsable_bo is not None and responsable_bo != resp_actual:
                col_resp = _col_letra(headers, COL_INICIO_DEALER)
                if col_resp:
                    celdas.append(Cell(row_sheet, col_resp, responsable_bo))

            if celdas:
                hoja_cobranza.update_cells(celdas, value_input_option="USER_ENTERED")

            st.success(f"✅ Intento {intento_libre} guardado correctamente. Fila bloqueada.")
            st.balloons()
            st.rerun()
        except Exception as e:
            st.error(f"❌ Error al guardar: {e}")
