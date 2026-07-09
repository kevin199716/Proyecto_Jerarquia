"""
cobranza_calidad.py v4.0
Módulo de Cobranza — Seguimiento de Calidad
Matriz editable profesional con franjas de color por intento.
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

CAMPOS_INTENTO = ["FECHA", "HORARIO", "MEDIO", "TIPO CONTACTO", "ACCIÓN", "FECHA COMPROMISO", "MOTIVO DE NO PAGO"]
N_INTENTOS = 3

HEADER_HTML = """
<div style="background: linear-gradient(135deg, #4B0067 0%, #7B1FA2 50%, #EC6608 100%);
            border-radius: 12px; padding: 24px 28px; margin-bottom: 20px;
            box-shadow: 0 4px 20px rgba(75,0,103,0.25);">
    <div style="display:flex; align-items:center; gap:14px;">
        <div style="font-size:32px;">💰</div>
        <div>
            <h1 style="color:white; margin:0; font-size:24px; font-weight:800;
                       font-family:'Plus Jakarta Sans',sans-serif;">
                Cobranza — Seguimiento de Calidad
            </h1>
            <p style="color:rgba(255,255,255,0.85); margin:2px 0 0; font-size:13px;">
                ✦ WOW Servicios de Internet · Gestión de contactabilidad y recuperación
            </p>
        </div>
    </div>
</div>
"""


def _cargar_listas(hoja_listas, razon_usuario=None):
    try:
        vals = hoja_listas.get_all_values()
        if len(vals) < 2:
            return {}
        df = pd.DataFrame(vals[1:], columns=vals[0])
        def _col(col):
            if col not in df.columns: return []
            return [v for v in df[col].dropna().unique() if str(v).strip()]
        responsables = []
        if "RAZON_SOCIAL_BO" in df.columns and "RESPONSABLE_BO" in df.columns:
            if razon_usuario:
                rn = _normalizar_razon(razon_usuario)
                df_r = df[df["RAZON_SOCIAL_BO"].astype(str).apply(_normalizar_razon).eq(rn)]
            else:
                df_r = df
            responsables = [v for v in df_r["RESPONSABLE_BO"].dropna().unique() if str(v).strip()]
        return {
            "responsables": [""] + sorted(responsables),
            "medios": [""] + _col("MEDIO"),
            "horarios": [""] + _col("HORARIO"),
            "tipos_contacto": [""] + _col("TIPO_CONTACTO"),
            "acciones_efectivo": [""] + _col("ACCION_EFECTIVO"),
            "acciones_no_efectivo": [""] + _col("ACCION_NO_EFECTIVO"),
            "motivos": [""] + _col("MOTIVO_NO_PAGO"),
        }
    except Exception:
        return {}


def _cargar_df(hoja):
    try:
        vals = hoja.get_all_values()
        if len(vals) < 2:
            return pd.DataFrame(), []
        df = pd.DataFrame(vals[1:], columns=vals[0])
        # Limpiar None y nan → cadena vacía
        df = df.fillna("").astype(str).replace({"None": "", "nan": "", "none": ""})
        return df, vals[0]
    except Exception as e:
        st.error(f"Error cargando datos: {e}")
        return pd.DataFrame(), []


def _col_idx(headers, nombre):
    try: return headers.index(nombre) + 1
    except ValueError: return None


def mostrar_cobranza(hoja_cobranza, razon_usuario=None, hoja_listas=None):
    st.markdown(HEADER_HTML, unsafe_allow_html=True)
    if hoja_cobranza is None:
        return

    df, headers = _cargar_df(hoja_cobranza)
    if df.empty:
        st.info("Sin registros.")
        return

    rol = st.session_state.get("rol", "")
    usuario_actual = st.session_state.get("usuario", "admin")

    # Listas de desplegables
    listas = {}
    if hoja_listas:
        listas = _cargar_listas(hoja_listas, razon_usuario if rol != "backoffice" else None)
    if not listas:
        listas = {
            "responsables": [""], "medios": ["", "Llamada de voz", "Whatsapp", "Campo"],
            "horarios": ["", "8AM - 12PM", "12PM - 3PM", "3PM - 6PM", "6PM - Cierre"],
            "tipos_contacto": ["", "EFECTIVO", "NO EFECTIVO"],
            "acciones_efectivo": ["", "Ya pagó", "Genera compromiso de pago", "Indica no pagará",
                                  "Otros: detallar", "Contesta y cuelga", "Contesta y no da razón"],
            "acciones_no_efectivo": ["", "Teléfono apagado", "Teléfono suspendido", "Teléfono no existe",
                                     "Timbra y no contesta", "Contesta pero desconoce a titular"],
            "motivos": ["", "Problema técnico", "Error en facturación", "Económicos"],
        }
    todas_acciones = sorted(set(listas.get("acciones_efectivo", []) + listas.get("acciones_no_efectivo", [])))
    if "" not in todas_acciones: todas_acciones.insert(0, "")

    if rol != "backoffice" and not razon_usuario:
        st.error("❌ Tu usuario no tiene razón social asignada.")
        return

    if rol != "backoffice" and razon_usuario and "razon_social" in df.columns:
        rn = _normalizar_razon(razon_usuario)
        df = df[df["razon_social"].astype(str).apply(_normalizar_razon).eq(rn)]
        if df.empty:
            st.warning("No hay registros para tu razón social.")
            return

    # ── PERÍODO ──
    if "PERIODO" in df.columns:
        periodos = sorted([p for p in df["PERIODO"].str.strip().unique() if p], reverse=True)
    else:
        periodos = ["(sin período)"]

    periodo_sel = st.selectbox("📅 Período", periodos, key="cob_per")
    if "PERIODO" in df.columns:
        df_p = df[df["PERIODO"].str.strip() == str(periodo_sel)].copy()
    else:
        df_p = df.copy()

    if df_p.empty:
        st.info("Sin registros para ese período.")
        return

    periodo_actual = _periodo_actual()
    es_actual = str(periodo_sel).strip() == periodo_actual
    puede_editar = es_actual and _hoy_peru().day <= 20

    # Badge de estado
    if es_actual and puede_editar:
        st.success(f"✏️ Período **{periodo_sel}** abierto para edición (hoy: día {_hoy_peru().day}, cierre: día 20)")
    elif es_actual:
        st.warning(f"🔒 Período **{periodo_sel}** cerrado — superó el día 20. Solo lectura y descarga.")
    else:
        st.info(f"📁 Período histórico **{periodo_sel}** — solo lectura y descarga.")

    st.caption(f"**{len(df_p)}** registros en este período.")

    # ── FILTROS ──
    with st.expander("🔍 Filtros", expanded=True):
        f1, f2, f3, f4, f5 = st.columns(5)
        with f1: filtro_nombre = st.text_input("Nombre", key="cob_fn").strip()
        with f2: filtro_cel = st.text_input("Celular", key="cob_fc").strip()
        with f3: filtro_cod = st.text_input("Código", key="cob_fcd").strip()
        with f4:
            ops_bo = ["TODOS"] + [v for v in listas.get("responsables", []) if v]
            filtro_bo = st.selectbox("Responsable BO", ops_bo, key="cob_fbo")
        with f5:
            ops_est = ["TODOS"] + sorted([v for v in df_p["Estado_Pago"].unique() if v]) if "Estado_Pago" in df_p.columns else ["TODOS"]
            filtro_est = st.selectbox("Estado Pago", ops_est, key="cob_fe")

    df_f = df_p.copy()
    if filtro_nombre and "nombre_cliente" in df_f.columns:
        df_f = df_f[df_f["nombre_cliente"].str.contains(filtro_nombre, case=False, na=False)]
    if filtro_cel and "celular_cliente" in df_f.columns:
        df_f = df_f[df_f["celular_cliente"].str.contains(filtro_cel, na=False)]
    if filtro_cod and "cod_cliente" in df_f.columns:
        df_f = df_f[df_f["cod_cliente"].str.contains(filtro_cod, na=False)]
    if filtro_bo != "TODOS" and "Responsable BO" in df_f.columns:
        df_f = df_f[df_f["Responsable BO"].str.strip().eq(filtro_bo)]
    if filtro_est != "TODOS" and "Estado_Pago" in df_f.columns:
        df_f = df_f[df_f["Estado_Pago"].str.strip().eq(filtro_est)]

    if df_f.empty:
        st.warning("Sin resultados con esos filtros.")
        return

    st.caption(f"Mostrando **{len(df_f)}** de {len(df_p)} registros.")

    # ── PAGINACIÓN ──
    PAGE = 50
    n_pag = max(1, -(-len(df_f) // PAGE))
    pag = st.number_input(f"Página (de {n_pag})", min_value=1, max_value=n_pag, value=1, key="cob_pag")
    ini = (pag - 1) * PAGE
    df_page = df_f.iloc[ini:ini + PAGE].copy()

    # ── PREPARAR COLUMNAS DEL EDITOR ──
    # Todas las columnas que existan, en el orden original de la hoja
    cols_todas = [c for c in headers if c in df_page.columns]

    # Columnas del analista (solo lectura)
    cols_readonly = {"NOMBRE_HOJA", "razon_social", "dni_creador_lead", "nombre_creador_lead",
                     "fecha_activacion", "cod_cliente", "nombre_cliente", "celular_cliente",
                     "plan", "boleta_1_monto", "boleta_1_fecha_pago", "Estado_Pago",
                     "cliente_regularizado", "PERIODO",
                     "boleta_2_monto", "boleta_2_fecha_pago", "boleta_3_monto", "boleta_3_fecha_pago",
                     "USUARIO_INT1", "TIMESTAMP_INT1", "USUARIO_INT2", "TIMESTAMP_INT2",
                     "USUARIO_INT3", "TIMESTAMP_INT3"}

    # Configurar cada columna
    col_config = {}
    for c in cols_todas:
        if c in cols_readonly:
            col_config[c] = st.column_config.TextColumn(c, disabled=True)
        elif c == "Responsable BO":
            col_config[c] = st.column_config.SelectboxColumn("Responsable BO", options=listas.get("responsables", []), width="medium")
        elif c.startswith("HORARIO"):
            col_config[c] = st.column_config.SelectboxColumn(c, options=listas.get("horarios", []), width="small")
        elif c.startswith("MEDIO"):
            col_config[c] = st.column_config.SelectboxColumn(c, options=listas.get("medios", []), width="small")
        elif c.startswith("TIPO CONTACTO"):
            col_config[c] = st.column_config.SelectboxColumn(c, options=listas.get("tipos_contacto", []), width="small")
        elif c.startswith("ACCIÓN"):
            col_config[c] = st.column_config.SelectboxColumn(c, options=todas_acciones, width="medium")
        elif c.startswith("MOTIVO DE NO PAGO"):
            col_config[c] = st.column_config.SelectboxColumn(c, options=listas.get("motivos", []), width="small")
        elif c.startswith("FECHA COMPROMISO"):
            col_config[c] = st.column_config.TextColumn(c, width="small")
        elif c.startswith("FECHA") and not c.startswith("FECHA_"):
            col_config[c] = st.column_config.TextColumn(c, width="small")

    if not puede_editar:
        # SOLO LECTURA
        st.dataframe(df_page[cols_todas], use_container_width=True, height=500, hide_index=True)
    else:
        # ── FRANJAS DE COLOR POR SECCIÓN ──
        st.markdown("""
        <div style="display:flex; gap:0; margin:8px 0 4px; border-radius:8px; overflow:hidden; font-family:'Plus Jakarta Sans',sans-serif; font-size:12px; font-weight:700;">
            <div style="background:#4B0067; color:white; padding:8px 16px; flex:2;">📋 DATOS DEL CLIENTE (solo lectura)</div>
            <div style="background:#1B5E20; color:white; padding:8px 16px; flex:1;">1️⃣ PRIMER CONTACTO</div>
            <div style="background:#E65100; color:white; padding:8px 16px; flex:1;">2️⃣ SEGUNDO CONTACTO</div>
            <div style="background:#B71C1C; color:white; padding:8px 16px; flex:1;">3️⃣ TERCER CONTACTO</div>
        </div>
        """, unsafe_allow_html=True)

        editado = st.data_editor(
            df_page[cols_todas],
            column_config=col_config,
            use_container_width=True,
            height=min(550, 45 + len(df_page) * 35),
            num_rows="fixed",
            hide_index=True,
            key="cob_editor",
        )

        if st.button("💾 Guardar cambios", type="primary", use_container_width=True, key="cob_guardar"):
            with st.spinner("⏳ Guardando..."):
                try:
                    df_orig = df_page[cols_todas].reset_index(drop=True)
                    df_edit = pd.DataFrame(editado).fillna("").astype(str).replace({"None": "", "nan": ""}).reset_index(drop=True)
                    celdas = []
                    filas_mod = 0

                    # Columnas editables (no readonly)
                    cols_editables = [c for c in cols_todas if c not in cols_readonly]

                    for i in range(len(df_edit)):
                        idx_real = df_page.index[i]
                        row_sheet = int(idx_real) + 2

                        cambios = {}
                        for cn in cols_editables:
                            ov = str(df_orig.iloc[i].get(cn, "")).strip()
                            nv = str(df_edit.iloc[i].get(cn, "")).strip()
                            if nv == "None": nv = ""
                            if nv != ov:
                                cambios[cn] = nv

                        if not cambios:
                            continue

                        # Validación secuencial: no puede llenar intento 2 sin completar intento 1
                        for n in range(2, N_INTENTOS + 1):
                            campos_n = [f"{c} {n}" for c in CAMPOS_INTENTO]
                            campos_prev = [f"{c} {n-1}" for c in CAMPOS_INTENTO]
                            tiene_datos_n = any(str(df_edit.iloc[i].get(c, "")).strip() not in ("", "None") for c in campos_n if c in df_edit.columns)
                            prev_completo = any(str(df_edit.iloc[i].get(c, "")).strip() not in ("", "None") for c in campos_prev if c in df_edit.columns)
                            if tiene_datos_n and not prev_completo:
                                nombre = df_edit.iloc[i].get("nombre_cliente", f"fila {i+1}")
                                st.error(f"❌ **{nombre}**: No puedes llenar el Intento {n} sin completar el Intento {n-1} primero.")
                                st.stop()

                        filas_mod += 1
                        for cn, val in cambios.items():
                            ci = _col_idx(headers, cn)
                            if ci:
                                celdas.append(Cell(row_sheet, ci, val))

                        # Timestamps automáticos
                        for n in range(1, N_INTENTOS + 1):
                            campos_n = [f"{c} {n}" for c in CAMPOS_INTENTO]
                            if any(c in cambios for c in campos_n):
                                ci_usr = _col_idx(headers, f"USUARIO_INT{n}")
                                ci_ts = _col_idx(headers, f"TIMESTAMP_INT{n}")
                                if ci_usr: celdas.append(Cell(row_sheet, ci_usr, usuario_actual))
                                if ci_ts: celdas.append(Cell(row_sheet, ci_ts, _ahora_peru_str()))

                    if celdas:
                        BATCH = 100
                        for b in range(0, len(celdas), BATCH):
                            hoja_cobranza.update_cells(celdas[b:b+BATCH], value_input_option="USER_ENTERED")
                        st.success(f"✅ {filas_mod} fila(s) guardada(s) · {len(celdas)} celdas escritas en Drive.")
                        st.rerun()
                    else:
                        st.info("No se detectaron cambios.")
                except st.runtime.scriptrunner.StopException:
                    raise
                except Exception as e:
                    st.error(f"❌ Error: {e}")

    # ── ESPEJO + DESCARGA ──
    st.divider()
    st.markdown("""
    <div style="background:#F2EEF5; padding:10px 16px; border-radius:8px;">
        <span style="color:#4B0067; font-weight:700;">📊 Espejo consolidado — Descarga</span>
    </div>
    """, unsafe_allow_html=True)

    csv = df_p.to_csv(index=False, encoding="utf-8-sig")
    st.download_button(f"⬇️ Descargar período {periodo_sel} ({len(df_p)} registros)",
                       data=csv, file_name=f"cobranza_{periodo_sel}.csv", mime="text/csv", key="cob_dl")
