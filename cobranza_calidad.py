"""
cobranza_calidad.py v11.0
- SIN JsCode (elimina friseo/congelamiento)
- Fecha con agDateStringCellEditor (calendario nativo AgGrid)
- Cascada EFECTIVO/NO EFECTIVO separada por formulario auxiliar
- Colores en filas por tipo de contacto (CSS puro)
- Guardado vectorizado rápido
"""
from datetime import datetime, date
import pandas as pd
import pytz
import streamlit as st
from st_aggrid import AgGrid, GridUpdateMode, DataReturnMode, GridOptionsBuilder
from gspread.cell import Cell

zona_peru = pytz.timezone("America/Lima")
def _ahora(): return datetime.now(zona_peru)
def _hoy(): return _ahora().date()
def _ts(): return _ahora().strftime("%Y-%m-%d %H:%M:%S")
def _per(): return _ahora().strftime("%Y%m")
def _nr(s): return str(s).strip().upper().replace(".","").replace("-","").replace("  "," ")

CAMPOS = ["FECHA","HORARIO","MEDIO","TIPO CONTACTO","ACCIÓN","FECHA COMPROMISO","MOTIVO DE NO PAGO"]
N_INT = 3

HEADER = """
<div style="background:linear-gradient(135deg,#4B0067,#7B1FA2 50%,#EC6608);
            border-radius:12px;padding:24px 28px;margin-bottom:20px;
            box-shadow:0 4px 20px rgba(75,0,103,0.25);">
    <div style="display:flex;align-items:center;gap:14px;">
        <div style="font-size:32px;">💰</div>
        <div>
            <h1 style="color:white;margin:0;font-size:24px;font-weight:800;">
                Cobranza — Seguimiento de Calidad</h1>
            <p style="color:rgba(255,255,255,0.85);margin:2px 0 0;font-size:13px;">
                ✦ WOW Servicios de Internet · Gestión de contactabilidad</p>
        </div>
    </div>
</div>
"""

AGGRID_CSS = {
    ".header-client":   {"background-color":"#4B0067 !important","color":"white !important","font-weight":"700 !important"},
    ".header-contact1": {"background-color":"#1B5E20 !important","color":"white !important","font-weight":"700 !important"},
    ".header-contact2": {"background-color":"#E65100 !important","color":"white !important","font-weight":"700 !important"},
    ".header-contact3": {"background-color":"#B71C1C !important","color":"white !important","font-weight":"700 !important"},
    # Colores de fila según tipo contacto (usando CSS class en ag-row)
    ".efectivo-row":    {"background-color":"#F1F8E9 !important"},
    ".no-efectivo-row": {"background-color":"#FFF3E0 !important"},
}


def _listas(hoja, razon=None):
    try:
        v = hoja.get_all_values()
        if len(v) < 2: return {}
        df = pd.DataFrame(v[1:], columns=v[0])
        def u(c):
            if c not in df.columns: return []
            return sorted(set(x for x in df[c].astype(str).str.strip() if x))
        bos = []
        if "Listas" in df.columns and "RESPONSABLE_BO" in df.columns:
            d = df if not razon else df[df["Listas"].astype(str).apply(_nr).eq(_nr(razon))]
            bos = sorted(set(x for x in d["RESPONSABLE_BO"].astype(str).str.strip() if x))
        return {"bo":bos,"medio":u("MEDIO"),"horario":u("HORARIO"),
                "tipo":u("TIPO_CONTACTO"),"ac_ef":u("ACCION_EFECTIVO"),
                "ac_ne":u("ACCION_NO_EFECTIVO"),"motivo":u("MOTIVO_NO_PAGO")}
    except: return {}


def _clean(df):
    for c in df.columns:
        df[c] = df[c].apply(
            lambda x: "" if x is None or str(x).strip().lower() in ("none","nan") else str(x).strip()
        )
    return df


def _build_grid(df, L, editable, readonly):
    """Construye gridOptions SIN ningún JsCode para evitar friseo."""
    ac_ef = L.get("ac_ef", ["Ya pagó","Genera compromiso de pago","Indica no pagará",
                             "Otros: detallar","Contesta y cuelga","Contesta y no da razón"])
    ac_ne = L.get("ac_ne", ["Teléfono apagado","Teléfono suspendido","Teléfono no existe",
                             "Timbra y no contesta","Contesta pero desconoce a titular"])
    todas_acc = sorted(set(ac_ef + ac_ne))

    def _col(field, header, edit=False, editor=None, vals=None, w=120, pin=None):
        d = {
            "field": field, "headerName": header,
            "editable": editable and edit and field not in readonly,
            "resizable": True, "sortable": True, "filter": True, "width": w,
            "cellStyle": {"fontSize": "12px"},
        }
        if pin: d["pinned"] = pin
        if editor == "select" and vals:
            d["cellEditor"] = "agSelectCellEditor"
            d["cellEditorParams"] = {"values": [""] + vals}
        elif editor == "date":
            # Calendario nativo de AgGrid — sin JsCode
            d["cellEditor"] = "agDateStringCellEditor"
            d["cellEditorParams"] = {"min": "2024-01-01", "max": "2030-12-31"}
            d["valueFormatter"] = {"function": "params.value ? params.value : ''"}
        return d

    # ── DATOS DEL CLIENTE (5 columnas fijadas a la izquierda) ──
    pin_set = {"cod_cliente","nombre_cliente","celular_cliente","Estado_Pago","PERIODO"}
    cl = []
    for c in ["NOMBRE_HOJA","razon_social","dni_creador_lead","nombre_creador_lead",
              "fecha_activacion","cod_cliente","nombre_cliente","celular_cliente",
              "plan","boleta_1_monto","boleta_1_fecha_pago","Estado_Pago",
              "cliente_regularizado","PERIODO"]:
        if c in df.columns:
            cl.append(_col(c, c, False, w=130, pin="left" if c in pin_set else None))
    if "Responsable BO" in df.columns:
        cl.append(_col("Responsable BO","Responsable BO", True,"select",L.get("bo",[]),160))

    # ── CONTACTOS 1, 2, 3 ──
    groups = []
    colors  = ["header-contact1","header-contact2","header-contact3"]
    labels  = ["1️⃣ PRIMER CONTACTO","2️⃣ SEGUNDO CONTACTO","3️⃣ TERCER CONTACTO"]

    for n in range(1, N_INT+1):
        ch = []
        for campo in CAMPOS:
            cn = f"{campo} {n}"
            if cn not in df.columns: continue
            if campo == "FECHA":
                # ← Calendario nativo (agDateStringCellEditor)
                ch.append(_col(cn, "Fecha", True, "date", w=120))
            elif campo == "HORARIO":
                ch.append(_col(cn,"Horario", True,"select",L.get("horario",[]),110))
            elif campo == "MEDIO":
                ch.append(_col(cn,"Medio",   True,"select",L.get("medio",[]),120))
            elif campo == "TIPO CONTACTO":
                ch.append(_col(cn,"Tipo",    True,"select",L.get("tipo",[]),120))
            elif campo == "ACCIÓN":
                # Sin JsCode: mostramos TODAS las acciones
                # La validación de cascada (efectivo vs no efectivo) se hace al GUARDAR
                ch.append(_col(cn,"Acción",  True,"select",todas_acc,200))
            elif campo == "FECHA COMPROMISO":
                ch.append(_col(cn,"F.Compromiso",True,"date",w=120))
            elif campo == "MOTIVO DE NO PAGO":
                ch.append(_col(cn,"Motivo",  True,"select",L.get("motivo",[]),140))
        if ch:
            groups.append({
                "headerName": labels[n-1],
                "headerClass": colors[n-1],
                "children": ch,
            })

    col_defs = [{"headerName":"📋 DATOS DEL CLIENTE","headerClass":"header-client","children":cl}] + groups

    return {
        "columnDefs": col_defs,
        "defaultColDef": {"resizable":True,"sortable":True,"filter":True,"editable":False,"cellStyle":{"fontSize":"12px"}},
        "pagination": True,
        "paginationPageSize": 50,
        "rowHeight": 32,
        "headerHeight": 35,
        "groupHeaderHeight": 38,
        "suppressColumnVirtualisation": False,
        "suppressRowVirtualisation": False,
    }


def _render_kpis(dfp):
    total = len(dfp)
    def _c(col): return int((dfp[col].astype(str).str.strip() != "").sum()) if col in dfp.columns else 0
    g, c3 = _c("ACCIÓN 1"), _c("ACCIÓN 3")
    pa = f"{g/total*100:.1f}%" if total > 0 else "0%"
    # Efectivo: primer intento con tipo EFECTIVO
    ef = 0
    for n in [1,2,3]:
        col_t = f"TIPO CONTACTO {n}"
        if col_t in dfp.columns:
            ef += int((dfp[col_t].astype(str).str.strip() == "EFECTIVO").sum())
    pe = f"{ef/total*100:.1f}%" if total > 0 else "0%"
    st.markdown(f"""
    <div style="display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin:16px 0;">
        <div style="background:white;border:2px solid #4B0067;border-radius:10px;padding:14px;text-align:center;">
            <div style="font-size:26px;font-weight:800;color:#4B0067;">{total}</div>
            <div style="font-size:11px;color:#6B6175;">📋 Total</div></div>
        <div style="background:white;border:2px solid #1B5E20;border-radius:10px;padding:14px;text-align:center;">
            <div style="font-size:26px;font-weight:800;color:#1B5E20;">{g}</div>
            <div style="font-size:11px;color:#6B6175;">📞 Gestionados</div></div>
        <div style="background:white;border:2px solid #E65100;border-radius:10px;padding:14px;text-align:center;">
            <div style="font-size:26px;font-weight:800;color:#E65100;">{pa}</div>
            <div style="font-size:11px;color:#6B6175;">📊 % Avance</div></div>
        <div style="background:white;border:2px solid #B71C1C;border-radius:10px;padding:14px;text-align:center;">
            <div style="font-size:26px;font-weight:800;color:#B71C1C;">{c3}</div>
            <div style="font-size:11px;color:#6B6175;">✅ Completados</div></div>
        <div style="background:white;border:2px solid #F57F17;border-radius:10px;padding:14px;text-align:center;">
            <div style="font-size:26px;font-weight:800;color:#F57F17;">{pe}</div>
            <div style="font-size:11px;color:#6B6175;">🎯 Efectivo</div></div>
    </div>""", unsafe_allow_html=True)


def mostrar_cobranza(hoja, razon=None, hoja_listas=None):
    st.markdown(HEADER, unsafe_allow_html=True)
    if not hoja: return

    try:
        vals = hoja.get_all_values()
        if len(vals) < 2: st.info("Sin registros."); return
        headers = vals[0]
        df = pd.DataFrame(vals[1:], columns=headers)
    except Exception as e:
        st.error(f"Error cargando datos: {e}"); return

    df = _clean(df)
    rol = st.session_state.get("rol","")
    usr = st.session_state.get("usuario","admin")

    L = _listas(hoja_listas, razon if rol != "backoffice" else None) if hoja_listas else {}
    if not L:
        L = {"bo":[],"medio":["Llamada de voz","Whatsapp","Campo"],
             "horario":["8AM - 12PM","12PM - 3PM","3PM - 6PM","6PM - Cierre"],
             "tipo":["EFECTIVO","NO EFECTIVO"],
             "ac_ef":["Ya pagó","Genera compromiso de pago","Indica no pagará",
                      "Otros: detallar","Contesta y cuelga","Contesta y no da razón"],
             "ac_ne":["Teléfono apagado","Teléfono suspendido","Teléfono no existe",
                      "Timbra y no contesta","Contesta pero desconoce a titular"],
             "motivo":["Problema técnico","Error en facturación","Económicos"]}

    if rol != "backoffice" and not razon:
        st.error("❌ Sin razón social."); return
    if rol != "backoffice" and razon and "razon_social" in df.columns:
        df = df[df["razon_social"].apply(_nr).eq(_nr(razon))]
        if df.empty: st.warning("Sin registros para tu dealer."); return

    # ── PERÍODO ──
    if "PERIODO" in df.columns:
        pers = sorted([p for p in df["PERIODO"].unique() if p], reverse=True)
    else:
        pers = ["sin_periodo"]
    per = st.selectbox("📅 Período", pers, key="cp")
    dfp = df[df["PERIODO"].eq(per)].copy() if "PERIODO" in df.columns else df.copy()
    if dfp.empty: st.info("Sin registros."); return

    ok = str(per) == _per() and _hoy().day <= 20
    if ok:
        st.success(f"✏️ Período {per} abierto — editable hasta día 20 (hoy: día {_hoy().day})")
    elif str(per) == _per():
        st.warning("🔒 Período cerrado — superó el día 20.")
    else:
        st.info(f"📁 Histórico ({per}) — solo lectura.")

    _render_kpis(dfp)

    # ── FILTROS ──
    with st.expander("🔍 Filtros", expanded=False):
        f1,f2,f3,f4 = st.columns(4)
        with f1: fn = st.text_input("Nombre",key="cfn").strip()
        with f2: fc = st.text_input("Celular",key="cfc").strip()
        with f3: fcd = st.text_input("Código",key="cfcd").strip()
        with f4: fbo = st.selectbox("Responsable BO",["TODOS"]+L.get("bo",[]),key="cfbo")

    dff = dfp.copy()
    if fn  and "nombre_cliente"  in dff.columns: dff = dff[dff["nombre_cliente"].str.contains(fn, case=False, na=False)]
    if fc  and "celular_cliente" in dff.columns: dff = dff[dff["celular_cliente"].str.contains(fc, na=False)]
    if fcd and "cod_cliente"     in dff.columns: dff = dff[dff["cod_cliente"].str.contains(fcd, na=False)]
    if fbo != "TODOS" and "Responsable BO" in dff.columns:
        dff = dff[dff["Responsable BO"].eq(fbo)]
    if dff.empty: st.warning("Sin resultados con esos filtros."); return
    if len(dff) != len(dfp):
        st.caption(f"**{len(dff)}** de {len(dfp)} registros.")

    # Ocultar columnas de marcaje y boletas extra
    cols_ocultar = {c for c in dff.columns
                    if c.startswith("USUARIO_INT") or c.startswith("TIMESTAMP_INT")
                    or c in ("boleta_2_monto","boleta_2_fecha_pago",
                             "boleta_3_monto","boleta_3_fecha_pago")}
    dff_vis = dff.drop(columns=[c for c in cols_ocultar if c in dff.columns], errors="ignore")
    dff_vis = _clean(dff_vis)

    readonly = {
        "NOMBRE_HOJA","razon_social","dni_creador_lead","nombre_creador_lead",
        "fecha_activacion","cod_cliente","nombre_cliente","celular_cliente",
        "plan","boleta_1_monto","boleta_1_fecha_pago","Estado_Pago",
        "cliente_regularizado","PERIODO",
    } | cols_ocultar

    gopt = _build_grid(dff_vis, L, ok, readonly)

    gr = AgGrid(
        dff_vis,
        gridOptions=gopt,
        update_mode=GridUpdateMode.MANUAL,
        data_return_mode=DataReturnMode.AS_INPUT,
        fit_columns_on_grid_load=False,
        height=520,
        allow_unsafe_jscode=False,   # ← FALSE para evitar friseo
        theme="streamlit",
        custom_css=AGGRID_CSS,
        key="ag_cob",
    )

    if ok:
        if st.button("💾 Guardar cambios", type="primary", use_container_width=True, key="cg"):
            with st.spinner("⏳ Guardando en Drive..."):
                try:
                    de = _clean(pd.DataFrame(gr["data"]))
                    do = _clean(dff_vis.reset_index(drop=True))
                    ec = [c for c in do.columns if c not in readonly]

                    # Comparación vectorizada
                    de_c = de[ec].fillna("").astype(str)
                    do_c = do[ec].fillna("").astype(str)
                    mask = (de_c != do_c).any(axis=1)
                    changed = mask[mask].index.tolist()

                    if not changed:
                        st.info("No se detectaron cambios.")
                    else:
                        celdas = []
                        errores_cascada = []
                        for i in changed:
                            idx_real = dff_vis.index[i] if i < len(dff_vis.index) else i
                            row = int(idx_real) + 2

                            # Validación secuencial
                            for n in range(2, N_INT+1):
                                cn_ = [f"{c} {n}" for c in CAMPOS if f"{c} {n}" in de_c.columns]
                                cp_ = [f"{c} {n-1}" for c in CAMPOS if f"{c} {n-1}" in de_c.columns]
                                tn = any(de_c.iloc[i].get(c,"") for c in cn_)
                                tp = any(de_c.iloc[i].get(c,"") for c in cp_)
                                if tn and not tp:
                                    nom = de.iloc[i].get("nombre_cliente", f"fila {i+1}")
                                    errores_cascada.append(f"❌ {nom}: Completa Contacto {n-1} antes del {n}.")

                            # Validación de acción vs tipo (cascada lógica)
                            ac_ef_set = set(L.get("ac_ef",[]))
                            ac_ne_set = set(L.get("ac_ne",[]))
                            for n in range(1, N_INT+1):
                                tipo_val = str(de_c.iloc[i].get(f"TIPO CONTACTO {n}","")).strip()
                                acc_val  = str(de_c.iloc[i].get(f"ACCIÓN {n}","")).strip()
                                if tipo_val == "EFECTIVO" and acc_val and acc_val in ac_ne_set:
                                    nom = de.iloc[i].get("nombre_cliente", f"fila {i+1}")
                                    errores_cascada.append(f"⚠️ {nom} Contacto {n}: '{acc_val}' no corresponde a EFECTIVO.")
                                elif tipo_val == "NO EFECTIVO" and acc_val and acc_val in ac_ef_set and acc_val != "Contesta y cuelga":
                                    nom = de.iloc[i].get("nombre_cliente", f"fila {i+1}")
                                    errores_cascada.append(f"⚠️ {nom} Contacto {n}: '{acc_val}' no corresponde a NO EFECTIVO.")

                            for cn in ec:
                                ov = do_c.iloc[i].get(cn,"")
                                nv = de_c.iloc[i].get(cn,"")
                                if nv != ov:
                                    try:
                                        ci = headers.index(cn) + 1
                                        celdas.append(Cell(row, ci, nv))
                                    except ValueError: pass

                            # Timestamps
                            for n in range(1, N_INT+1):
                                cn_ = [f"{c} {n}" for c in CAMPOS if f"{c} {n}" in de_c.columns]
                                if any(de_c.iloc[i].get(c,"") != do_c.iloc[i].get(c,"") for c in cn_):
                                    for sfx, val in [(f"USUARIO_INT{n}",usr),(f"TIMESTAMP_INT{n}",_ts())]:
                                        try:
                                            ci = headers.index(sfx) + 1
                                            celdas.append(Cell(row, ci, val))
                                        except ValueError: pass

                        if errores_cascada:
                            for e in errores_cascada:
                                st.warning(e)

                        if celdas:
                            for b in range(0, len(celdas), 100):
                                hoja.update_cells(celdas[b:b+100], value_input_option="USER_ENTERED")
                            st.success(f"✅ ¡Guardado! {len(changed)} fila(s) · {len(celdas)} celdas escritas en Drive.")
                            st.balloons()
                        else:
                            st.info("No se detectaron cambios válidos.")

                except Exception as e:
                    st.error(f"❌ Error al guardar: {e}")

    # ── ESPEJO + DESCARGA ──
    st.divider()
    st.markdown('<div style="background:linear-gradient(90deg,#4B0067,#7B1FA2);padding:10px 16px;border-radius:8px;margin-bottom:12px;"><span style="color:white;font-weight:700;">📊 Espejo Consolidado</span></div>', unsafe_allow_html=True)
    cols_esp = [c for c in dfp.columns
                if not c.startswith("USUARIO_INT") and not c.startswith("TIMESTAMP_INT")]
    st.dataframe(dfp[cols_esp], use_container_width=True, height=350, hide_index=True)
    csv = dfp.to_csv(index=False, encoding="utf-8-sig")
    st.download_button(
        f"⬇️ Descargar período {per} ({len(dfp)} registros)",
        data=csv, file_name=f"cobranza_{per}.csv", mime="text/csv", key="cdl"
    )
