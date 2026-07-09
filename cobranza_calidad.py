"""
cobranza_calidad.py v3.0
Módulo de Cobranza — Seguimiento de Calidad
Matriz editable directa con filtros, desplegables en cascada,
escritura celda-por-celda, timestamps automáticos.
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

def _ahora_peru_str():
    return _ahora_peru().strftime("%Y-%m-%d %H:%M:%S")

def _periodo_actual() -> str:
    return _ahora_peru().strftime("%Y%m")

def _normalizar_razon(s: str) -> str:
    return str(s).strip().upper().replace(".", "").replace("-", "").replace("  ", " ")

# =========================
# CAMPOS POR INTENTO
# =========================
CAMPOS_INTENTO = ["FECHA", "HORARIO", "MEDIO", "TIPO CONTACTO", "ACCIÓN", "FECHA COMPROMISO", "MOTIVO DE NO PAGO"]
CAMPOS_TIMESTAMP = ["USUARIO_INT", "TIMESTAMP_INT"]
N_INTENTOS = 3

# Columnas del analista (solo lectura para dealers)
COLS_SOLO_LECTURA = {
    "NOMBRE_HOJA", "razon_social", "dni_creador_lead", "nombre_creador_lead",
    "fecha_activacion", "cod_cliente", "nombre_cliente", "celular_cliente",
    "plan", "boleta_1_monto", "boleta_1_fecha_pago", "Estado_Pago",
    "cliente_regularizado", "PERIODO",
    "boleta_2_monto", "boleta_2_fecha_pago", "boleta_3_monto", "boleta_3_fecha_pago",
}

# =========================
# ESTILOS
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
.cobranza-badge {
    display: inline-block; padding: 3px 10px; border-radius: 12px;
    font-size: 11px; font-weight: 600; font-family:'Plus Jakarta Sans',sans-serif;
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


def _cargar_listas(hoja_listas, razon_usuario=None):
    """Lee la pestaña Listas y devuelve las opciones de cada desplegable.
    Responsable BO se filtra por razón social del usuario."""
    try:
        vals = hoja_listas.get_all_values()
        if len(vals) < 2:
            return {}
        df = pd.DataFrame(vals[1:], columns=vals[0])

        def _col_unica(col):
            if col not in df.columns:
                return []
            return [v for v in df[col].dropna().unique() if str(v).strip()]

        # Responsable BO filtrado por dealer
        responsables = []
        if "RAZON_SOCIAL_BO" in df.columns and "RESPONSABLE_BO" in df.columns:
            if razon_usuario:
                razon_norm = _normalizar_razon(razon_usuario)
                df_r = df[df["RAZON_SOCIAL_BO"].astype(str).apply(_normalizar_razon).eq(razon_norm)]
            else:
                df_r = df
            responsables = [v for v in df_r["RESPONSABLE_BO"].dropna().unique() if str(v).strip()]

        return {
            "responsables": [""] + sorted(responsables),
            "medios": [""] + _col_unica("MEDIO"),
            "horarios": [""] + _col_unica("HORARIO"),
            "tipos_contacto": [""] + _col_unica("TIPO_CONTACTO"),
            "acciones_efectivo": [""] + _col_unica("ACCION_EFECTIVO"),
            "acciones_no_efectivo": [""] + _col_unica("ACCION_NO_EFECTIVO"),
            "motivos": [""] + _col_unica("MOTIVO_NO_PAGO"),
        }
    except Exception as e:
        st.warning(f"No se pudo leer la hoja Listas: {e}. Usando opciones por defecto.")
        return {}


def _cargar_df(hoja):
    try:
        vals = hoja.get_all_values()
        if len(vals) < 2:
            return pd.DataFrame(), []
        return pd.DataFrame(vals[1:], columns=vals[0]), vals[0]
    except Exception as e:
        st.error(f"Error cargando datos: {e}")
        return pd.DataFrame(), []


def _col_idx_1based(headers, nombre):
    try:
        return headers.index(nombre) + 1
    except ValueError:
        return None


def mostrar_cobranza(hoja_cobranza, razon_usuario=None, hoja_listas=None):
    st.markdown(HEADER_HTML, unsafe_allow_html=True)
    st.markdown(TABLE_CSS, unsafe_allow_html=True)

    if hoja_cobranza is None:
        return

    df, headers = _cargar_df(hoja_cobranza)
    if df.empty:
        st.info("Sin registros en la hoja de Cobranza.")
        return

    rol = st.session_state.get("rol", "")
    usuario_actual = st.session_state.get("usuario", "admin")

    # Cargar listas de desplegables desde la hoja Listas
    listas = {}
    if hoja_listas:
        razon_para_listas = razon_usuario if rol != "backoffice" else None
        listas = _cargar_listas(hoja_listas, razon_para_listas)

    # Defaults si Listas no cargó
    if not listas:
        listas = {
            "responsables": ["", "MARIETTE MEDINA", "MICHELLI SEGURA", "CLAUDIA CALISAYA"],
            "medios": ["", "Llamada de voz", "Whatsapp", "Campo"],
            "horarios": ["", "8AM - 12PM", "12PM - 3PM", "3PM - 6PM", "6PM - Cierre"],
            "tipos_contacto": ["", "EFECTIVO", "NO EFECTIVO"],
            "acciones_efectivo": ["", "Ya pagó", "Genera compromiso de pago", "Indica no pagará",
                                  "Otros: detallar", "Contesta y cuelga", "Contesta y no da razón"],
            "acciones_no_efectivo": ["", "Teléfono apagado", "Teléfono suspendido", "Teléfono no existe",
                                     "Timbra y no contesta", "Contesta pero desconoce a titular"],
            "motivos": ["", "Problema técnico", "Error en facturación", "Económicos"],
        }

    # Todas las acciones combinadas para el editor (la validación de cascada va al guardar)
    todas_acciones = sorted(set(listas.get("acciones_efectivo", []) + listas.get("acciones_no_efectivo", [])))
    if "" not in todas_acciones:
        todas_acciones.insert(0, "")

    if rol != "backoffice" and not razon_usuario:
        st.error("❌ Tu usuario no tiene razón social asignada.")
        return

    # Filtro por dealer
    if rol != "backoffice" and razon_usuario and "razon_social" in df.columns:
        razon_norm = _normalizar_razon(razon_usuario)
        df = df[df["razon_social"].astype(str).apply(_normalizar_razon).eq(razon_norm)]
        if df.empty:
            st.warning("No hay registros de cobranza para tu razón social.")
            return

    # ── PERÍODO ──
    if "PERIODO" not in df.columns:
        st.warning("⚠️ Falta la columna PERIODO en la hoja.")
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

    if es_actual and puede_editar:
        badge = f"<span class='cobranza-badge abierto'>✏️ ABIERTO — editable hasta el día 20 (hoy: día {dia_hoy})</span>"
    elif es_actual:
        badge = "<span class='cobranza-badge cerrado'>🔒 CERRADO — superó el día 20</span>"
    else:
        badge = f"<span class='cobranza-badge historico'>📁 HISTÓRICO ({periodo_sel})</span>"
    st.markdown(badge, unsafe_allow_html=True)

    # ── KPIs ──
    total = len(df_p)
    def _contar(col):
        return sum(1 for _, r in df_p.iterrows() if str(r.get(col, "")).strip() != "") if col in df_p.columns else 0
    c1, c2, c3, c4 = _contar("ACCIÓN 1"), _contar("ACCIÓN 2"), _contar("ACCIÓN 3"), total
    pct = lambda n: f"{n/total*100:.0f}%" if total > 0 else "0%"
    k1, k2, k3, k4 = st.columns(4)
    for col, num, lbl in [(k1, str(c4), "Total registros"), (k2, f"{c1} ({pct(c1)})", "Intento 1"),
                           (k3, f"{c2} ({pct(c2)})", "Intento 2"), (k4, f"{c3} ({pct(c3)})", "Intento 3")]:
        col.markdown(f"<div class='cobranza-kpi'><div class='num'>{num}</div><div class='label'>{lbl}</div></div>",
                     unsafe_allow_html=True)

    # ── FILTROS ──
    st.markdown("---")
    st.markdown("**🔍 Filtros**")
    f1, f2, f3, f4, f5 = st.columns(5)
    with f1:
        filtro_nombre = st.text_input("Nombre cliente", key="cob_fn").strip()
    with f2:
        filtro_celular = st.text_input("Celular", key="cob_fcel").strip()
    with f3:
        filtro_cod = st.text_input("Código cliente", key="cob_fcod").strip()
    with f4:
        ops_bo = ["TODOS"] + [v for v in listas.get("responsables", []) if v]
        filtro_bo = st.selectbox("Responsable BO", ops_bo, key="cob_fbo")
    with f5:
        ops_estado = ["TODOS"] + sorted(df_p["Estado_Pago"].dropna().unique().tolist()) if "Estado_Pago" in df_p.columns else ["TODOS"]
        filtro_estado = st.selectbox("Estado Pago", ops_estado, key="cob_fest")

    df_f = df_p.copy()
    if filtro_nombre and "nombre_cliente" in df_f.columns:
        df_f = df_f[df_f["nombre_cliente"].astype(str).str.contains(filtro_nombre, case=False, na=False)]
    if filtro_celular and "celular_cliente" in df_f.columns:
        df_f = df_f[df_f["celular_cliente"].astype(str).str.contains(filtro_celular, na=False)]
    if filtro_cod and "cod_cliente" in df_f.columns:
        df_f = df_f[df_f["cod_cliente"].astype(str).str.contains(filtro_cod, na=False)]
    if filtro_bo != "TODOS" and "Responsable BO" in df_f.columns:
        df_f = df_f[df_f["Responsable BO"].astype(str).str.strip().eq(filtro_bo)]
    if filtro_estado != "TODOS" and "Estado_Pago" in df_f.columns:
        df_f = df_f[df_f["Estado_Pago"].astype(str).str.strip().eq(filtro_estado)]

    st.caption(f"**{len(df_f)}** registros filtrados de **{total}** totales.")

    if df_f.empty:
        st.warning("Sin resultados con esos filtros.")
        return

    # ── PAGINACIÓN ──
    PAGE_SIZE = 50
    n_pages = max(1, -(-len(df_f) // PAGE_SIZE))
    page = st.selectbox(f"Página (de {n_pages})", range(1, n_pages + 1), key="cob_page") if n_pages > 1 else 1
    start = (page - 1) * PAGE_SIZE
    df_page = df_f.iloc[start:start + PAGE_SIZE].copy()

    # ── COLUMNAS A MOSTRAR EN EL EDITOR ──
    # Info del cliente (solo lectura) + campos editables de los 3 intentos
    cols_info = [c for c in ["nombre_cliente", "celular_cliente", "cod_cliente", "Estado_Pago", "Responsable BO"]
                 if c in df_page.columns]

    cols_intentos = []
    for n in range(1, N_INTENTOS + 1):
        for campo in CAMPOS_INTENTO:
            col = f"{campo} {n}"
            if col in df_page.columns:
                cols_intentos.append(col)

    cols_editor = cols_info + cols_intentos
    cols_editor = [c for c in cols_editor if c in df_page.columns]

    if not puede_editar:
        # Solo lectura: mostrar tabla estática
        st.dataframe(df_page[cols_editor], use_container_width=True, height=450)
    else:
        # ── EDITOR DE MATRIZ EDITABLE ──
        st.markdown("""
        <div style="background:linear-gradient(90deg,#4B0067,#7B1FA2); padding:8px 16px;
                    border-radius:6px; margin:8px 0;">
            <span style="color:white; font-weight:700; font-size:14px;">
                ✏️ Edita directamente en la tabla — los desplegables aparecen al hacer clic en cada celda
            </span>
        </div>
        """, unsafe_allow_html=True)

        # Configurar columnas: info=disabled, intentos=selectbox
        col_config = {}
        for c in cols_info:
            col_config[c] = st.column_config.TextColumn(c, disabled=True)

        for n in range(1, N_INTENTOS + 1):
            # Determinar si este intento ya estaba completado ANTES de editar
            col_fecha = f"FECHA {n}"
            col_horario = f"HORARIO {n}"
            col_medio = f"MEDIO {n}"
            col_tipo = f"TIPO CONTACTO {n}"
            col_accion = f"ACCIÓN {n}"
            col_fc = f"FECHA COMPROMISO {n}"
            col_motivo = f"MOTIVO DE NO PAGO {n}"

            if col_fecha in df_page.columns:
                col_config[col_fecha] = st.column_config.TextColumn(f"📅 FECHA {n}", width="small")
            if col_horario in df_page.columns:
                col_config[col_horario] = st.column_config.SelectboxColumn(
                    f"🕐 HORARIO {n}", options=listas.get("horarios", []), width="small")
            if col_medio in df_page.columns:
                col_config[col_medio] = st.column_config.SelectboxColumn(
                    f"📞 MEDIO {n}", options=listas.get("medios", []), width="small")
            if col_tipo in df_page.columns:
                col_config[col_tipo] = st.column_config.SelectboxColumn(
                    f"🎯 TIPO {n}", options=listas.get("tipos_contacto", []), width="small")
            if col_accion in df_page.columns:
                col_config[col_accion] = st.column_config.SelectboxColumn(
                    f"⚡ ACCIÓN {n}", options=todas_acciones, width="medium")
            if col_fc in df_page.columns:
                col_config[col_fc] = st.column_config.TextColumn(f"📆 F.COMP {n}", width="small")
            if col_motivo in df_page.columns:
                col_config[col_motivo] = st.column_config.SelectboxColumn(
                    f"❓ MOTIVO {n}", options=listas.get("motivos", []), width="small")

        if "Responsable BO" in df_page.columns:
            col_config["Responsable BO"] = st.column_config.SelectboxColumn(
                "👤 Responsable BO", options=listas.get("responsables", []), width="medium")

        editado = st.data_editor(
            df_page[cols_editor],
            column_config=col_config,
            use_container_width=True,
            height=min(500, 50 + len(df_page) * 35),
            num_rows="fixed",
            hide_index=False,
            key="cob_editor",
        )

        if st.button("💾 Guardar cambios", type="primary", use_container_width=True, key="cob_guardar"):
            with st.spinner("⏳ Guardando cambios celda por celda..."):
                try:
                    df_orig = df_page[cols_editor].reset_index(drop=True)
                    df_edit = pd.DataFrame(editado).reset_index(drop=True)
                    celdas_total = []
                    filas_modificadas = 0

                    for i in range(len(df_edit)):
                        idx_real = df_page.index[i]
                        row_sheet = int(idx_real) + 2  # +1 por 0-based, +1 por header

                        cambios_fila = {}
                        for col_name in cols_intentos:
                            orig_val = str(df_orig.iloc[i].get(col_name, "")).strip()
                            new_val = str(df_edit.iloc[i].get(col_name, "")).strip()
                            if new_val != orig_val:
                                cambios_fila[col_name] = new_val

                        # Responsable BO
                        if "Responsable BO" in cols_editor:
                            orig_bo = str(df_orig.iloc[i].get("Responsable BO", "")).strip()
                            new_bo = str(df_edit.iloc[i].get("Responsable BO", "")).strip()
                            if new_bo != orig_bo:
                                cambios_fila["Responsable BO"] = new_bo

                        if not cambios_fila:
                            continue

                        filas_modificadas += 1
                        for col_name, valor in cambios_fila.items():
                            col_1based = _col_idx_1based(headers, col_name)
                            if col_1based:
                                celdas_total.append(Cell(row_sheet, col_1based, valor))

                        # Auto-rellenar TIMESTAMP y USUARIO por cada intento modificado
                        for n in range(1, N_INTENTOS + 1):
                            intento_cols = [f"{c} {n}" for c in CAMPOS_INTENTO]
                            if any(c in cambios_fila for c in intento_cols):
                                col_usr = f"USUARIO_INT{n}"
                                col_ts = f"TIMESTAMP_INT{n}"
                                col_usr_idx = _col_idx_1based(headers, col_usr)
                                col_ts_idx = _col_idx_1based(headers, col_ts)
                                if col_usr_idx:
                                    celdas_total.append(Cell(row_sheet, col_usr_idx, usuario_actual))
                                if col_ts_idx:
                                    celdas_total.append(Cell(row_sheet, col_ts_idx, _ahora_peru_str()))

                    if celdas_total:
                        # Escribir en batches de 100 para no saturar la API
                        BATCH = 100
                        for b in range(0, len(celdas_total), BATCH):
                            hoja_cobranza.update_cells(celdas_total[b:b+BATCH], value_input_option="USER_ENTERED")
                        st.success(f"✅ {filas_modificadas} fila(s) actualizada(s) · {len(celdas_total)} celdas escritas.")
                        st.rerun()
                    else:
                        st.info("No se detectaron cambios.")
                except Exception as e:
                    st.error(f"❌ Error al guardar: {e}")

    # ── ESPEJO / DESCARGA ──
    st.divider()
    st.markdown("""
    <div style="background:#F2EEF5; padding:12px 16px; border-radius:8px; margin:8px 0;">
        <span style="color:#4B0067; font-weight:700; font-size:14px;">
            📊 Espejo del período — Vista consolidada para descarga
        </span>
    </div>
    """, unsafe_allow_html=True)

    cols_espejo = st.multiselect("Columnas del espejo", list(df_p.columns),
                                  default=[c for c in ["razon_social", "nombre_cliente", "celular_cliente",
                                           "cod_cliente", "Estado_Pago", "Responsable BO",
                                           "FECHA 1", "TIPO CONTACTO 1", "ACCIÓN 1",
                                           "FECHA 2", "TIPO CONTACTO 2", "ACCIÓN 2",
                                           "FECHA 3", "TIPO CONTACTO 3", "ACCIÓN 3",
                                           "USUARIO_INT1", "TIMESTAMP_INT1"] if c in df_p.columns],
                                  key="cob_espejo_cols")
    if cols_espejo:
        st.dataframe(df_p[cols_espejo], use_container_width=True, height=350)

    csv = df_p.to_csv(index=False, encoding="utf-8-sig")
    st.download_button(f"⬇️ Descargar período {periodo_sel} ({total} registros)",
                       data=csv, file_name=f"cobranza_{periodo_sel}.csv", mime="text/csv", key="cob_dl")
