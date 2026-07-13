"""
cobranza_calidad.py v14.0
Fixes: error session_state, filtro en selector cliente, acción siempre visible
"""
from datetime import datetime, date
import pandas as pd
import pytz
import streamlit as st
from gspread.cell import Cell

zona_peru = pytz.timezone("America/Lima")
def _ahora(): return datetime.now(zona_peru)
def _hoy(): return _ahora().date()
def _ts(): return _ahora().strftime("%Y-%m-%d %H:%M:%S")
def _per(): return _ahora().strftime("%Y%m")
def _nr(s): return str(s).strip().upper().replace(".","").replace("-","").replace("  "," ")

CAMPOS = ["FECHA","HORARIO","MEDIO","TIPO CONTACTO","ACCIÓN","FECHA COMPROMISO","MOTIVO DE NO PAGO"]
N_INT = 3

ACCIONES = {
    "EFECTIVO": ["Ya pagó","Genera compromiso de pago","Indica no pagará",
                 "Contesta y cuelga","Contesta y no da razón","Otros: detallar"],
    "NO EFECTIVO": ["Teléfono apagado","Teléfono suspendido","Teléfono no existe",
                    "Timbra y no contesta","Contesta pero desconoce a titular"],
}
TODAS_ACCIONES = sorted(set(sum(ACCIONES.values(),[])))
REQUIERE_FC     = {"Genera compromiso de pago"}
REQUIERE_MOTIVO = {"Indica no pagará","Otros: detallar"}

HEADER = """
<div style="background:linear-gradient(135deg,#4B0067,#7B1FA2 50%,#EC6608);
            border-radius:12px;padding:20px 24px;margin-bottom:16px;">
    <div style="display:flex;align-items:center;gap:12px;">
        <div style="font-size:28px;">💰</div>
        <div>
            <h1 style="color:white;margin:0;font-size:22px;font-weight:800;">
                Cobranza — Seguimiento de Calidad</h1>
            <p style="color:rgba(255,255,255,0.85);margin:2px 0 0;font-size:12px;">
                ✦ WOW Servicios de Internet</p>
        </div>
    </div>
</div>
"""


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
        return {"bo":bos,"medio":u("MEDIO"),"horario":u("HORARIO"),"motivo":u("MOTIVO_NO_PAGO")}
    except: return {}


def _clean(df):
    for c in df.columns:
        df[c] = df[c].apply(
            lambda x: "" if x is None or str(x).strip().lower() in ("none","nan") else str(x).strip()
        )
    return df


def _kpis(dfp):
    total = len(dfp)
    g  = int((dfp["ACCIÓN 1"].astype(str).str.strip() != "").sum()) if "ACCIÓN 1" in dfp.columns else 0
    c3 = int((dfp["ACCIÓN 3"].astype(str).str.strip() != "").sum()) if "ACCIÓN 3" in dfp.columns else 0
    ef = sum(int((dfp[f"TIPO CONTACTO {n}"].astype(str).str.strip() == "EFECTIVO").sum())
             for n in range(1,4) if f"TIPO CONTACTO {n}" in dfp.columns)
    pa = f"{g/total*100:.1f}%" if total>0 else "0%"
    pe = f"{ef/total*100:.1f}%" if total>0 else "0%"
    st.markdown(f"""
    <div style="display:grid;grid-template-columns:repeat(5,1fr);gap:10px;margin:12px 0;">
        <div style="background:white;border:2px solid #4B0067;border-radius:10px;padding:12px;text-align:center;">
            <div style="font-size:24px;font-weight:800;color:#4B0067;">{total}</div>
            <div style="font-size:11px;color:#6B6175;">📋 Total</div></div>
        <div style="background:white;border:2px solid #1B5E20;border-radius:10px;padding:12px;text-align:center;">
            <div style="font-size:24px;font-weight:800;color:#1B5E20;">{g}</div>
            <div style="font-size:11px;color:#6B6175;">📞 Gestionados</div></div>
        <div style="background:white;border:2px solid #E65100;border-radius:10px;padding:12px;text-align:center;">
            <div style="font-size:24px;font-weight:800;color:#E65100;">{pa}</div>
            <div style="font-size:11px;color:#6B6175;">📊 % Avance</div></div>
        <div style="background:white;border:2px solid #B71C1C;border-radius:10px;padding:12px;text-align:center;">
            <div style="font-size:24px;font-weight:800;color:#B71C1C;">{c3}</div>
            <div style="font-size:11px;color:#6B6175;">✅ Completados</div></div>
        <div style="background:white;border:2px solid #F57F17;border-radius:10px;padding:12px;text-align:center;">
            <div style="font-size:24px;font-weight:800;color:#F57F17;">{pe}</div>
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
             "motivo":["Problema técnico","Error en facturación","Económicos"]}

    if rol != "backoffice" and not razon:
        st.error("❌ Sin razón social."); return
    if rol != "backoffice" and razon and "razon_social" in df.columns:
        df = df[df["razon_social"].apply(_nr).eq(_nr(razon))]
        if df.empty: st.warning("Sin registros para tu dealer."); return

    # Período
    if "PERIODO" in df.columns:
        pers = sorted([p for p in df["PERIODO"].unique() if p], reverse=True)
    else: pers = ["sin_periodo"]
    per = st.selectbox("📅 Período", pers, key="cp")
    dfp = df[df["PERIODO"].eq(per)].copy() if "PERIODO" in df.columns else df.copy()
    if dfp.empty: st.info("Sin registros."); return

    ok = str(per) == _per() and _hoy().day <= 20
    if ok:
        st.success(f"✏️ Período {per} abierto — editable hasta día 20 (hoy: día {_hoy().day})")
    elif str(per) == _per():
        st.warning("🔒 Período cerrado.")
    else:
        st.info(f"📁 Histórico ({per}) — solo lectura.")

    _kpis(dfp)

    # ── FILTROS (afectan tabla Y selector de cliente) ──
    with st.expander("🔍 Filtros", expanded=False):
        f1,f2,f3,f4 = st.columns(4)
        with f1: fn  = st.text_input("Nombre",  key="cfn").strip()
        with f2: fc  = st.text_input("Celular",  key="cfc").strip()
        with f3: fcd = st.text_input("Código",   key="cfcd").strip()
        with f4: fbo = st.selectbox("Responsable BO",["TODOS"]+L.get("bo",[]),key="cfbo")

    dff = dfp.copy()
    if fn  and "nombre_cliente"  in dff.columns: dff = dff[dff["nombre_cliente"].str.contains(fn, case=False, na=False)]
    if fc  and "celular_cliente" in dff.columns: dff = dff[dff["celular_cliente"].str.contains(fc, na=False)]
    if fcd and "cod_cliente"     in dff.columns: dff = dff[dff["cod_cliente"].str.contains(fcd, na=False)]
    if fbo != "TODOS" and "Responsable BO" in dff.columns:
        dff = dff[dff["Responsable BO"].eq(fbo)]
    if dff.empty: st.warning("Sin resultados."); return
    if len(dff) != len(dfp): st.caption(f"**{len(dff)}** de {len(dfp)} registros.")

    # ── TABLA RESUMEN (solo lectura, rápida) ──
    cols_tabla = [c for c in ["cod_cliente","nombre_cliente","celular_cliente",
                               "Estado_Pago","PERIODO","Responsable BO",
                               "TIPO CONTACTO 1","ACCIÓN 1",
                               "TIPO CONTACTO 2","ACCIÓN 2",
                               "TIPO CONTACTO 3","ACCIÓN 3"] if c in dff.columns]

    PAGE = 25
    total_pag = max(1,-(-len(dff)//PAGE))
    pag = st.number_input(f"Página (de {total_pag})", 1, total_pag, 1, key="pag")
    ini = (pag-1)*PAGE
    df_page = dff.iloc[ini:ini+PAGE].copy()

    def _color(row):
        t = str(row.get("TIPO CONTACTO 1","")).strip()
        if t == "EFECTIVO":    return ["background-color:#F1F8E9"]*len(row)
        if t == "NO EFECTIVO": return ["background-color:#FFF3E0"]*len(row)
        return [""]*len(row)

    st.dataframe(df_page[cols_tabla].style.apply(_color, axis=1),
                 use_container_width=True, height=360, hide_index=True)

    if not ok:
        st.divider()
        st.markdown('<div style="background:linear-gradient(90deg,#4B0067,#7B1FA2);padding:8px 16px;border-radius:8px;margin-bottom:8px;"><span style="color:white;font-weight:700;">📊 Espejo Consolidado</span></div>', unsafe_allow_html=True)
        cols_esp = [c for c in dfp.columns if not c.startswith("USUARIO_INT") and not c.startswith("TIMESTAMP_INT")]
        st.dataframe(dfp[cols_esp], use_container_width=True, height=300, hide_index=True)
        csv = dfp.to_csv(index=False, encoding="utf-8-sig")
        st.download_button(f"⬇️ Descargar {per} ({len(dfp)} reg.)", data=csv,
                           file_name=f"cobranza_{per}.csv", mime="text/csv", key="cdl")
        return

    # ── SELECTOR DE CLIENTE (de los filtrados en la página actual) ──
    st.divider()
    st.markdown("""
    <div style="background:linear-gradient(90deg,#4B0067,#7B1FA2);padding:10px 16px;
                border-radius:8px;margin-bottom:12px;">
        <span style="color:white;font-weight:700;font-size:15px;">
            ✏️ Registrar gestión
        </span>
    </div>""", unsafe_allow_html=True)

    # Búsqueda rápida en el selector
    busq = st.text_input("🔎 Buscar cliente (nombre, celular o código)",
                         key="busq_sel").strip().lower()
    filas_sel = df_page
    if busq:
        mask = pd.Series(False, index=filas_sel.index)
        for col in ["nombre_cliente","celular_cliente","cod_cliente"]:
            if col in filas_sel.columns:
                mask = mask | filas_sel[col].astype(str).str.lower().str.contains(busq, na=False)
        filas_sel = filas_sel[mask]

    if filas_sel.empty:
        st.info("No hay clientes que coincidan con la búsqueda.")
        return

    opts = [f"{r.get('cod_cliente','')} · {r.get('nombre_cliente','')} · {r.get('celular_cliente','')}"
            for _, r in filas_sel.iterrows()]
    sel  = st.selectbox("Cliente a gestionar", ["-- Selecciona --"] + opts, key="sel_cli")

    if sel == "-- Selecciona --":
        st.info("👆 Selecciona un cliente para registrar su gestión.")
        return

    sel_pos   = opts.index(sel)
    fila_idx  = filas_sel.index[sel_pos]
    fila      = dict(dff.loc[fila_idx])
    row_sheet = int(fila_idx) + 2

    # Info del cliente
    st.markdown(f"""
    <div style="background:white;border:1px solid #E0D5EA;border-radius:10px;
                padding:14px 18px;margin:8px 0;">
        <div style="display:flex;gap:32px;flex-wrap:wrap;">
            <div><span style="color:#6B6175;font-size:11px;">CLIENTE</span><br>
                 <b style="font-size:15px;">{fila.get('nombre_cliente','')}</b></div>
            <div><span style="color:#6B6175;font-size:11px;">CELULAR</span><br>
                 <b>{fila.get('celular_cliente','')}</b></div>
            <div><span style="color:#6B6175;font-size:11px;">CÓDIGO</span><br>
                 <b>{fila.get('cod_cliente','')}</b></div>
            <div><span style="color:#6B6175;font-size:11px;">ESTADO PAGO</span><br>
                 <b style="color:#C62828;">{fila.get('Estado_Pago','')}</b></div>
        </div>
    </div>""", unsafe_allow_html=True)

    # ── FORMULARIO EN st.form → CERO RECARGAS AL EDITAR ──
    with st.form(key=f"form_{fila_idx}"):
        bo_list = L.get("bo",[])
        bo_idx  = bo_list.index(fila.get("Responsable BO","")) + 1 \
                  if fila.get("Responsable BO","") in bo_list else 0
        responsable = st.selectbox("👤 Responsable BO", [""] + bo_list, index=bo_idx)

        resultados = {}
        for n in range(1, N_INT+1):
            colors = {1:"#1B5E20",2:"#E65100",3:"#B71C1C"}
            labels = {1:"1️⃣ PRIMER CONTACTO",2:"2️⃣ SEGUNDO CONTACTO",3:"3️⃣ TERCER CONTACTO"}
            st.markdown(f"""<div style="background:{colors[n]};color:white;padding:8px 12px;
                border-radius:6px;margin:12px 0 8px;font-weight:700;">{labels[n]}</div>""",
                unsafe_allow_html=True)

            col_fecha = f"FECHA {n}"
            col_hor   = f"HORARIO {n}"
            col_med   = f"MEDIO {n}"
            col_tipo  = f"TIPO CONTACTO {n}"
            col_acc   = f"ACCIÓN {n}"
            col_fc    = f"FECHA COMPROMISO {n}"
            col_mot   = f"MOTIVO DE NO PAGO {n}"

            val_fecha = fila.get(col_fecha,"")
            try: fecha_def = datetime.strptime(val_fecha,"%Y-%m-%d").date() if val_fecha else _hoy()
            except: fecha_def = _hoy()

            c1,c2,c3 = st.columns(3)
            with c1:
                fecha = st.date_input("📅 Fecha contacto", value=fecha_def,
                                      min_value=date(2024,1,1), max_value=date(2030,12,31),
                                      key=f"ff{n}")
            with c2:
                hor_o = [""] + L.get("horario",["8AM - 12PM","12PM - 3PM","3PM - 6PM","6PM - Cierre"])
                hor_i = hor_o.index(fila.get(col_hor,"")) if fila.get(col_hor,"") in hor_o else 0
                horario = st.selectbox("🕐 Horario", hor_o, index=hor_i, key=f"fh{n}")
            with c3:
                med_o = [""] + L.get("medio",["Llamada de voz","Whatsapp","Campo"])
                med_i = med_o.index(fila.get(col_med,"")) if fila.get(col_med,"") in med_o else 0
                medio = st.selectbox("📞 Medio", med_o, index=med_i, key=f"fm{n}")

            tipo_o = ["","EFECTIVO","NO EFECTIVO"]
            tipo_i = tipo_o.index(fila.get(col_tipo,"")) if fila.get(col_tipo,"") in tipo_o else 0
            tipo   = st.selectbox("🎯 Tipo de contacto", tipo_o, index=tipo_i, key=f"ft{n}")

            # Acción — siempre visible con todas las opciones
            acc_o = [""] + TODAS_ACCIONES
            acc_v = fila.get(col_acc,"")
            acc_i = acc_o.index(acc_v) if acc_v in acc_o else 0
            accion = st.selectbox("⚡ Acción", acc_o, index=acc_i, key=f"fa{n}")

            # Fecha compromiso
            fc_date = None
            if accion in REQUIERE_FC:
                fc_v = fila.get(col_fc,"")
                try: fc_def = datetime.strptime(fc_v,"%Y-%m-%d").date() if fc_v else _hoy()
                except: fc_def = _hoy()
                fc_date = st.date_input("📆 Fecha compromiso de pago",
                                        value=fc_def, min_value=_hoy(), key=f"ffc{n}")
                st.success("💡 Escenario perfecto — genera compromiso de pago.")

            # Motivo
            motivo = ""
            if accion in REQUIERE_MOTIVO:
                mot_o = [""] + L.get("motivo",["Problema técnico","Error en facturación","Económicos"])
                mot_v = fila.get(col_mot,"")
                mot_i = mot_o.index(mot_v) if mot_v in mot_o else 0
                motivo = st.selectbox("❓ Motivo de no pago", mot_o, index=mot_i, key=f"fmo{n}")

            resultados.update({
                col_fecha: str(fecha),
                col_hor:   horario,
                col_med:   medio,
                col_tipo:  tipo,
                col_acc:   accion,
                col_fc:    str(fc_date) if fc_date else "",
                col_mot:   motivo,
            })

        submitted = st.form_submit_button("💾 Guardar gestión",
                                          type="primary", use_container_width=True)

    if submitted:
        with st.spinner("⏳ Guardando en Drive..."):
            try:
                celdas = []
                # Responsable BO
                if responsable != fila.get("Responsable BO",""):
                    try:
                        ci = headers.index("Responsable BO") + 1
                        celdas.append(Cell(row_sheet, ci, responsable))
                    except ValueError: pass

                for campo, nv in resultados.items():
                    ov = str(fila.get(campo,"")).strip()
                    nv = str(nv).strip()
                    if nv != ov:
                        try:
                            ci = headers.index(campo) + 1
                            celdas.append(Cell(row_sheet, ci, nv))
                        except ValueError: pass

                for n in range(1, N_INT+1):
                    cn_ = [f"{c} {n}" for c in CAMPOS if f"{c} {n}" in resultados]
                    if any(str(resultados.get(c,"")).strip() != str(fila.get(c,"")).strip() for c in cn_):
                        for sfx,val in [(f"USUARIO_INT{n}",usr),(f"TIMESTAMP_INT{n}",_ts())]:
                            try:
                                ci = headers.index(sfx) + 1
                                celdas.append(Cell(row_sheet, ci, val))
                            except ValueError: pass

                if celdas:
                    hoja.update_cells(celdas, value_input_option="USER_ENTERED")
                    st.success(f"✅ Gestión guardada — {len(celdas)} celdas actualizadas en Drive.")
                    st.balloons()
                else:
                    st.info("No se detectaron cambios.")
            except Exception as e:
                st.error(f"❌ Error: {e}")

    # Espejo + Descarga
    st.divider()
    st.markdown('<div style="background:linear-gradient(90deg,#4B0067,#7B1FA2);padding:8px 16px;border-radius:8px;margin-bottom:8px;"><span style="color:white;font-weight:700;">📊 Espejo Consolidado</span></div>', unsafe_allow_html=True)
    cols_esp = [c for c in dfp.columns if not c.startswith("USUARIO_INT") and not c.startswith("TIMESTAMP_INT")]
    st.dataframe(dfp[cols_esp], use_container_width=True, height=300, hide_index=True)
    csv = dfp.to_csv(index=False, encoding="utf-8-sig")
    st.download_button(f"⬇️ Descargar {per} ({len(dfp)} reg.)", data=csv,
                       file_name=f"cobranza_{per}.csv", mime="text/csv", key="cdl")
