"""
cobranza_calidad.py v9.0 — Ligero y funcional
- KPIs livianos (HTML puro, sin plotly)
- AgGrid solo para edición (sin JsCode para evitar error de serialización)
- Espejo como st.dataframe simple
- Sin gráficos pesados
"""
from datetime import datetime, date
import pandas as pd
import pytz
import streamlit as st
from st_aggrid import AgGrid, GridUpdateMode, DataReturnMode
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
    ".header-client": {"background-color": "#4B0067 !important", "color": "white !important", "font-weight": "700 !important"},
    ".header-contact1": {"background-color": "#1B5E20 !important", "color": "white !important", "font-weight": "700 !important"},
    ".header-contact2": {"background-color": "#E65100 !important", "color": "white !important", "font-weight": "700 !important"},
    ".header-contact3": {"background-color": "#B71C1C !important", "color": "white !important", "font-weight": "700 !important"},
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
        df[c] = df[c].apply(lambda x: "" if x is None or str(x).strip().lower() in ("none","nan") else str(x).strip())
    return df


def _build_grid(df, headers, L, editable, readonly):
    todas_acc = sorted(set(L.get("ac_ef",[]) + L.get("ac_ne",[])))

    def _col(field, header=None, edit=True, editor=None, vals=None, w=120):
        d = {"field":field, "headerName":header or field,
             "editable": editable and edit and field not in readonly,
             "resizable":True, "sortable":True, "filter":True, "width":w}
        if editor == "select" and vals:
            d["cellEditor"] = "agSelectCellEditor"
            d["cellEditorParams"] = {"values": [""] + vals}
        return d

    cl = []
    for c in ["NOMBRE_HOJA","razon_social","dni_creador_lead","nombre_creador_lead",
              "fecha_activacion","cod_cliente","nombre_cliente","celular_cliente",
              "plan","boleta_1_monto","boleta_1_fecha_pago","Estado_Pago",
              "cliente_regularizado","PERIODO"]:
        if c in df.columns:
            cl.append(_col(c, c, False, w=130))
    if "Responsable BO" in df.columns:
        cl.append(_col("Responsable BO","Responsable BO",True,"select",L.get("bo",[]),160))

    groups = []
    colors = ["header-contact1","header-contact2","header-contact3"]
    labels = ["1️⃣ PRIMER CONTACTO","2️⃣ SEGUNDO CONTACTO","3️⃣ TERCER CONTACTO"]
    for n in range(1, N_INT+1):
        ch = []
        for campo in CAMPOS:
            cn = f"{campo} {n}"
            if cn not in df.columns: continue
            if campo == "FECHA":
                ch.append(_col(cn,"Fecha",True,w=110))
            elif campo == "HORARIO":
                ch.append(_col(cn,"Horario",True,"select",L.get("horario",[]),110))
            elif campo == "MEDIO":
                ch.append(_col(cn,"Medio",True,"select",L.get("medio",[]),120))
            elif campo == "TIPO CONTACTO":
                ch.append(_col(cn,"Tipo Contacto",True,"select",L.get("tipo",[]),130))
            elif campo == "ACCIÓN":
                ch.append(_col(cn,"Acción",True,"select",todas_acc,200))
            elif campo == "FECHA COMPROMISO":
                ch.append(_col(cn,"F. Compromiso",True,w=110))
            elif campo == "MOTIVO DE NO PAGO":
                ch.append(_col(cn,"Motivo No Pago",True,"select",L.get("motivo",[]),140))
        if ch:
            groups.append({"headerName":labels[n-1],"headerClass":colors[n-1],"children":ch})

    return {
        "columnDefs": [{"headerName":"📋 DATOS DEL CLIENTE","headerClass":"header-client","children":cl}] + groups,
        "defaultColDef": {"resizable":True,"sortable":True,"filter":True,"editable":False},
        "pagination":True, "paginationPageSize":50,
        "rowHeight":32, "headerHeight":35, "groupHeaderHeight":38,
    }


def _render_kpis(dfp):
    total = len(dfp)
    def _c(col): return sum(1 for v in dfp.get(col,[]) if str(v).strip() and str(v).strip().lower() not in ("none","nan")) if col in dfp.columns else 0
    g = _c("ACCIÓN 1")
    c2 = _c("ACCIÓN 2")
    c3 = _c("ACCIÓN 3")
    pa = f"{g/total*100:.1f}%" if total > 0 else "0%"
    ef = 0
    for _, r in dfp.iterrows():
        for n in [3,2,1]:
            tc = str(r.get(f"TIPO CONTACTO {n}","")).strip()
            if tc:
                if tc == "EFECTIVO": ef += 1
                break
    pe = f"{ef/total*100:.1f}%" if total > 0 else "0%"

    st.markdown(f"""
    <div style="display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin:16px 0;">
        <div style="background:white;border:2px solid #4B0067;border-radius:10px;padding:16px;text-align:center;">
            <div style="font-size:28px;font-weight:800;color:#4B0067;">{total}</div>
            <div style="font-size:11px;color:#6B6175;">📋 Total Registros</div></div>
        <div style="background:white;border:2px solid #1B5E20;border-radius:10px;padding:16px;text-align:center;">
            <div style="font-size:28px;font-weight:800;color:#1B5E20;">{g}</div>
            <div style="font-size:11px;color:#6B6175;">📞 Gestionados</div></div>
        <div style="background:white;border:2px solid #E65100;border-radius:10px;padding:16px;text-align:center;">
            <div style="font-size:28px;font-weight:800;color:#E65100;">{pa}</div>
            <div style="font-size:11px;color:#6B6175;">📊 % Avance</div></div>
        <div style="background:white;border:2px solid #B71C1C;border-radius:10px;padding:16px;text-align:center;">
            <div style="font-size:28px;font-weight:800;color:#B71C1C;">{c3}</div>
            <div style="font-size:11px;color:#6B6175;">✅ Completados (3 int.)</div></div>
        <div style="background:white;border:2px solid #F57F17;border-radius:10px;padding:16px;text-align:center;">
            <div style="font-size:28px;font-weight:800;color:#F57F17;">{pe}</div>
            <div style="font-size:11px;color:#6B6175;">🎯 Contacto Efectivo</div></div>
    </div>
    """, unsafe_allow_html=True)


def mostrar_cobranza(hoja, razon=None, hoja_listas=None):
    st.markdown(HEADER, unsafe_allow_html=True)
    if not hoja: return

    try:
        vals = hoja.get_all_values()
        if len(vals) < 2: st.info("Sin registros."); return
        headers = vals[0]
        df = pd.DataFrame(vals[1:], columns=headers)
    except Exception as e:
        st.error(f"Error: {e}"); return

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

    if "PERIODO" in df.columns:
        pers = sorted([p for p in df["PERIODO"].unique() if p], reverse=True)
    else:
        pers = ["sin_periodo"]
    per = st.selectbox("📅 Período", pers, key="cp")
    dfp = df[df["PERIODO"].eq(per)].copy() if "PERIODO" in df.columns else df.copy()
    if dfp.empty: st.info("Sin registros."); return

    ok = str(per) == _per() and _hoy().day <= 20
    if ok:
        st.success(f"✏️ Período {per} abierto (hoy: día {_hoy().day}, cierre: día 20)")
    elif str(per) == _per():
        st.warning(f"🔒 Período {per} cerrado.")
    else:
        st.info(f"📁 Histórico ({per}).")

    # KPIs livianos
    _render_kpis(dfp)

    # Filtros
    with st.expander("🔍 Filtros", expanded=False):
        f1,f2,f3,f4 = st.columns(4)
        with f1: fn = st.text_input("Nombre",key="cfn").strip()
        with f2: fc = st.text_input("Celular",key="cfc").strip()
        with f3: fcd = st.text_input("Código",key="cfcd").strip()
        with f4: fbo = st.selectbox("Responsable BO",["TODOS"]+L.get("bo",[]),key="cfbo")
    dff = dfp.copy()
    if fn and "nombre_cliente" in dff.columns: dff = dff[dff["nombre_cliente"].str.contains(fn,case=False,na=False)]
    if fc and "celular_cliente" in dff.columns: dff = dff[dff["celular_cliente"].str.contains(fc,na=False)]
    if fcd and "cod_cliente" in dff.columns: dff = dff[dff["cod_cliente"].str.contains(fcd,na=False)]
    if fbo != "TODOS" and "Responsable BO" in dff.columns: dff = dff[dff["Responsable BO"].eq(fbo)]
    if dff.empty: st.warning("Sin resultados."); return
    if len(dff) != len(dfp): st.caption(f"Mostrando **{len(dff)}** de {len(dfp)}.")

    readonly = {"NOMBRE_HOJA","razon_social","dni_creador_lead","nombre_creador_lead",
                "fecha_activacion","cod_cliente","nombre_cliente","celular_cliente",
                "plan","boleta_1_monto","boleta_1_fecha_pago","Estado_Pago",
                "cliente_regularizado","PERIODO",
                "boleta_2_monto","boleta_2_fecha_pago","boleta_3_monto","boleta_3_fecha_pago",
                "USUARIO_INT1","TIMESTAMP_INT1","USUARIO_INT2","TIMESTAMP_INT2",
                "USUARIO_INT3","TIMESTAMP_INT3"}

    go = _build_grid(dff, headers, L, ok, readonly)
    gr = AgGrid(dff, gridOptions=go, update_mode=GridUpdateMode.MANUAL,
                data_return_mode=DataReturnMode.AS_INPUT, fit_columns_on_grid_load=False,
                height=520, theme="streamlit", custom_css=AGGRID_CSS, key="ag_cob")

    if ok:
        if st.button("💾 Guardar cambios", type="primary", use_container_width=True, key="cg"):
            with st.spinner("⏳ Guardando..."):
                try:
                    de = _clean(pd.DataFrame(gr["data"]))
                    do = _clean(dff.reset_index(drop=True))
                    ec = [c for c in headers if c not in readonly and c in de.columns]
                    celdas = []
                    nmod = 0
                    for i in range(min(len(de), len(do))):
                        idx = dff.index[i] if i < len(dff.index) else i
                        row = int(idx) + 2
                        cambios = {}
                        for cn in ec:
                            ov = str(do.iloc[i].get(cn,"")).strip()
                            nv = str(de.iloc[i].get(cn,"")).strip()
                            if nv.lower() in ("none","nan"): nv = ""
                            if nv != ov: cambios[cn] = nv
                        if not cambios: continue
                        for n in range(2, N_INT+1):
                            cn_ = [f"{c} {n}" for c in CAMPOS]
                            cp_ = [f"{c} {n-1}" for c in CAMPOS]
                            tn = any(str(de.iloc[i].get(c,"")).strip() for c in cn_ if c in de.columns)
                            tp = any(str(de.iloc[i].get(c,"")).strip() for c in cp_ if c in de.columns)
                            if tn and not tp:
                                nm = de.iloc[i].get("nombre_cliente",f"fila {i+1}")
                                st.error(f"❌ {nm}: Completa Contacto {n-1} antes del {n}.")
                                st.stop()
                        nmod += 1
                        for cn,val in cambios.items():
                            try:
                                ci = headers.index(cn) + 1
                                celdas.append(Cell(row, ci, val))
                            except ValueError: pass
                        for n in range(1, N_INT+1):
                            cn_ = [f"{c} {n}" for c in CAMPOS]
                            if any(c in cambios for c in cn_):
                                for sfx,val in [(f"USUARIO_INT{n}",usr),(f"TIMESTAMP_INT{n}",_ts())]:
                                    try:
                                        ci = headers.index(sfx) + 1
                                        celdas.append(Cell(row, ci, val))
                                    except ValueError: pass
                    if celdas:
                        for b in range(0,len(celdas),100):
                            hoja.update_cells(celdas[b:b+100], value_input_option="USER_ENTERED")
                        st.success(f"✅ ¡Guardado! {nmod} fila(s) · {len(celdas)} celdas escritas.")
                        st.balloons()
                    else:
                        st.info("No se detectaron cambios.")
                except st.runtime.scriptrunner.StopException: raise
                except Exception as e: st.error(f"❌ Error: {e}")

    # Espejo + Descarga (simple, sin AgGrid)
    st.divider()
    st.markdown('<div style="background:linear-gradient(90deg,#4B0067,#7B1FA2);padding:10px 16px;border-radius:8px;margin-bottom:12px;"><span style="color:white;font-weight:700;">📊 Espejo Consolidado</span></div>', unsafe_allow_html=True)
    # Excluir columnas de marcaje del espejo visual
    cols_espejo = [c for c in dfp.columns if not c.startswith("USUARIO_INT") and not c.startswith("TIMESTAMP_INT")]
    st.dataframe(dfp[cols_espejo], use_container_width=True, height=400, hide_index=True)
    csv = dfp.to_csv(index=False, encoding="utf-8-sig")
    st.download_button(f"⬇️ Descargar período {per} ({len(dfp)} registros)",
                       data=csv, file_name=f"cobranza_{per}.csv", mime="text/csv", key="cdl")
