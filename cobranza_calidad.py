"""cobranza_calidad.py v15 — Lógica correcta, cascada real, fechas validadas"""
from datetime import datetime, date
import pandas as pd, pytz, streamlit as st
from gspread.cell import Cell

zona_peru = pytz.timezone("America/Lima")
def _ahora(): return datetime.now(zona_peru)
def _hoy(): return _ahora().date()
def _ts(): return _ahora().strftime("%Y-%m-%d %H:%M:%S")
def _per(): return _ahora().strftime("%Y%m")
def _nr(s): return str(s).strip().upper().replace(".","").replace("-","").replace("  "," ")

CAMPOS = ["FECHA","HORARIO","MEDIO","TIPO CONTACTO","ACCIÓN","FECHA COMPROMISO","MOTIVO DE NO PAGO"]
N_INT  = 3

# Árbol de tipificaciones — SEPARADO por tipo
ACCIONES_EFECTIVO = [
    "Ya pagó",
    "Genera compromiso de pago",
    "Indica no pagará",
    "Contesta y cuelga",
    "Contesta y no da razón",
    "Otros: detallar",
]
ACCIONES_NO_EFECTIVO = [
    "Teléfono apagado",
    "Teléfono suspendido",
    "Teléfono no existe",
    "Timbra y no contesta",
    "Contesta pero desconoce a titular",
]
# Acciones que cierran el flujo (no se registran más contactos)
CIERRE_FLUJO = {"Ya pagó", "Genera compromiso de pago"}
REQUIERE_FC     = {"Genera compromiso de pago"}
REQUIERE_MOTIVO = {"Indica no pagará", "Otros: detallar"}

HEADER = """<div style="background:linear-gradient(135deg,#4B0067,#7B1FA2 50%,#EC6608);
border-radius:12px;padding:20px 24px;margin-bottom:16px;">
<div style="display:flex;align-items:center;gap:12px;">
<div style="font-size:28px;">💰</div>
<div><h1 style="color:white;margin:0;font-size:22px;font-weight:800;">Cobranza — Seguimiento de Calidad</h1>
<p style="color:rgba(255,255,255,0.85);margin:2px 0 0;font-size:12px;">✦ WOW Servicios de Internet</p>
</div></div></div>"""


def _listas(hoja, razon=None):
    try:
        v  = hoja.get_all_values()
        if len(v) < 2: return {}
        df = pd.DataFrame(v[1:], columns=v[0])
        def u(c): return sorted(set(x for x in df[c].astype(str).str.strip() if x)) if c in df.columns else []
        bos = []
        if "Listas" in df.columns and "RESPONSABLE_BO" in df.columns:
            d   = df if not razon else df[df["Listas"].astype(str).apply(_nr).eq(_nr(razon))]
            bos = sorted(set(x for x in d["RESPONSABLE_BO"].astype(str).str.strip() if x))
        return {"bo":bos,"medio":u("MEDIO"),"horario":u("HORARIO"),"motivo":u("MOTIVO_NO_PAGO")}
    except: return {}


def _clean(df):
    for c in df.columns:
        df[c] = df[c].apply(lambda x: "" if x is None or str(x).strip().lower() in ("none","nan") else str(x).strip())
    return df


def _kpis(dfp):
    t  = len(dfp)
    g  = int((dfp["ACCIÓN 1"].astype(str).str.strip() != "").sum()) if "ACCIÓN 1" in dfp.columns else 0
    c3 = int((dfp["ACCIÓN 3"].astype(str).str.strip() != "").sum()) if "ACCIÓN 3" in dfp.columns else 0
    ef = sum(int((dfp[f"TIPO CONTACTO {n}"].astype(str).str.strip() == "EFECTIVO").sum()) for n in range(1,4) if f"TIPO CONTACTO {n}" in dfp.columns)
    pa = f"{g/t*100:.1f}%" if t>0 else "0%"
    pe = f"{ef/t*100:.1f}%" if t>0 else "0%"
    st.markdown(f"""<div style="display:grid;grid-template-columns:repeat(5,1fr);gap:10px;margin:12px 0;">
<div style="background:white;border:2px solid #4B0067;border-radius:10px;padding:12px;text-align:center;"><div style="font-size:24px;font-weight:800;color:#4B0067;">{t}</div><div style="font-size:11px;color:#6B6175;">📋 Total</div></div>
<div style="background:white;border:2px solid #1B5E20;border-radius:10px;padding:12px;text-align:center;"><div style="font-size:24px;font-weight:800;color:#1B5E20;">{g}</div><div style="font-size:11px;color:#6B6175;">📞 Gestionados</div></div>
<div style="background:white;border:2px solid #E65100;border-radius:10px;padding:12px;text-align:center;"><div style="font-size:24px;font-weight:800;color:#E65100;">{pa}</div><div style="font-size:11px;color:#6B6175;">📊 % Avance</div></div>
<div style="background:white;border:2px solid #B71C1C;border-radius:10px;padding:12px;text-align:center;"><div style="font-size:24px;font-weight:800;color:#B71C1C;">{c3}</div><div style="font-size:11px;color:#6B6175;">✅ Completados</div></div>
<div style="background:white;border:2px solid #F57F17;border-radius:10px;padding:12px;text-align:center;"><div style="font-size:24px;font-weight:800;color:#F57F17;">{pe}</div><div style="font-size:11px;color:#6B6175;">🎯 Efectivo</div></div>
</div>""", unsafe_allow_html=True)


def mostrar_cobranza(hoja, razon=None, hoja_listas=None):
    st.markdown(HEADER, unsafe_allow_html=True)
    if not hoja: return

    try:
        vals    = hoja.get_all_values()
        if len(vals) < 2: st.info("Sin registros."); return
        headers = vals[0]
        df      = pd.DataFrame(vals[1:], columns=headers)
    except Exception as e:
        st.error(f"Error cargando: {e}"); return

    df  = _clean(df)
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
        if df.empty: st.warning("Sin registros."); return

    # Período
    pers = sorted([p for p in df["PERIODO"].unique() if p], reverse=True) if "PERIODO" in df.columns else ["sin_periodo"]
    per  = st.selectbox("📅 Período", pers, key="cp")
    dfp  = df[df["PERIODO"].eq(per)].copy() if "PERIODO" in df.columns else df.copy()
    if dfp.empty: st.info("Sin registros."); return

    ok = str(per) == _per() and _hoy().day <= 20
    if ok: st.success(f"✏️ Período {per} abierto — editable hasta día 20 (hoy: día {_hoy().day})")
    elif str(per) == _per(): st.warning("🔒 Cerrado.")
    else: st.info(f"📁 Histórico ({per}) — solo lectura.")

    _kpis(dfp)

    # Filtros — afectan tabla Y selector
    with st.expander("🔍 Filtros", expanded=False):
        f1,f2,f3,f4 = st.columns(4)
        with f1: fn  = st.text_input("Nombre",  key="cfn").strip()
        with f2: fce = st.text_input("Celular",  key="cfc").strip()
        with f3: fcd = st.text_input("Código",   key="cfcd").strip()
        with f4: fbo = st.selectbox("Responsable BO",["TODOS"]+L.get("bo",[]),key="cfbo")

    dff = dfp.copy()
    if fn  and "nombre_cliente"  in dff.columns: dff = dff[dff["nombre_cliente"].str.contains(fn, case=False, na=False)]
    if fce and "celular_cliente" in dff.columns: dff = dff[dff["celular_cliente"].str.contains(fce, na=False)]
    if fcd and "cod_cliente"     in dff.columns: dff = dff[dff["cod_cliente"].str.contains(fcd, na=False)]
    if fbo != "TODOS" and "Responsable BO" in dff.columns: dff = dff[dff["Responsable BO"].eq(fbo)]
    if dff.empty: st.warning("Sin resultados."); return
    if len(dff) != len(dfp): st.caption(f"**{len(dff)}** de {len(dfp)} registros.")

    # Tabla de resumen — sin paginación, toda la data filtrada
    cols_t = [c for c in ["cod_cliente","nombre_cliente","celular_cliente","Estado_Pago",
                           "Responsable BO","TIPO CONTACTO 1","ACCIÓN 1",
                           "TIPO CONTACTO 2","ACCIÓN 2","TIPO CONTACTO 3","ACCIÓN 3"] if c in dff.columns]
    def _color(row):
        t = str(row.get("TIPO CONTACTO 1","")).strip()
        if t == "EFECTIVO":    return ["background-color:#F1F8E9"]*len(row)
        if t == "NO EFECTIVO": return ["background-color:#FFF3E0"]*len(row)
        return [""]*len(row)
    st.dataframe(dff[cols_t].style.apply(_color,axis=1), use_container_width=True, height=380, hide_index=True)

    if not ok:
        st.divider()
        st.markdown('<div style="background:linear-gradient(90deg,#4B0067,#7B1FA2);padding:8px 16px;border-radius:8px;margin-bottom:8px;"><span style="color:white;font-weight:700;">📊 Espejo Consolidado</span></div>', unsafe_allow_html=True)
        cols_e = [c for c in dfp.columns if not c.startswith("USUARIO_INT") and not c.startswith("TIMESTAMP_INT")]
        st.dataframe(dfp[cols_e], use_container_width=True, height=300, hide_index=True)
        st.download_button(f"⬇️ Descargar {per} ({len(dfp)} reg.)",
                           data=dfp.to_csv(index=False,encoding="utf-8-sig"),
                           file_name=f"cobranza_{per}.csv", mime="text/csv", key="cdl")
        return

    # Selector de cliente — campos SEPARADOS
    st.divider()
    st.markdown('<div style="background:linear-gradient(90deg,#4B0067,#7B1FA2);padding:10px 16px;border-radius:8px;margin-bottom:12px;"><span style="color:white;font-weight:700;font-size:15px;">✏️ Registrar gestión</span></div>', unsafe_allow_html=True)

    s1,s2,s3 = st.columns(3)
    with s1: sb_nom = st.text_input("Buscar por nombre",  key="sb_nom").strip().lower()
    with s2: sb_cel = st.text_input("Buscar por celular", key="sb_cel").strip()
    with s3: sb_cod = st.text_input("Buscar por código",  key="sb_cod").strip()

    fs = dff.copy()
    if sb_nom and "nombre_cliente"  in fs.columns: fs = fs[fs["nombre_cliente"].str.lower().str.contains(sb_nom, na=False)]
    if sb_cel and "celular_cliente" in fs.columns: fs = fs[fs["celular_cliente"].str.contains(sb_cel, na=False)]
    if sb_cod and "cod_cliente"     in fs.columns: fs = fs[fs["cod_cliente"].str.contains(sb_cod, na=False)]

    if fs.empty: st.info("No hay clientes con esa búsqueda."); return

    opts = [f"{r.get('nombre_cliente','')}  |  {r.get('celular_cliente','')}  |  Cód: {r.get('cod_cliente','')}"
            for _,r in fs.iterrows()]
    sel  = st.selectbox("Cliente", ["-- Selecciona --"] + opts, key="sel_cli")
    if sel == "-- Selecciona --": st.info("👆 Selecciona un cliente para registrar."); return

    pos       = opts.index(sel)
    fila_idx  = fs.index[pos]
    fila      = dict(dff.loc[fila_idx])
    row_sheet = int(fila_idx) + 2

    # Info del cliente
    st.markdown(f"""<div style="background:white;border:1px solid #E0D5EA;border-radius:10px;padding:14px 18px;margin:8px 0;">
<div style="display:flex;gap:32px;flex-wrap:wrap;">
<div><span style="color:#6B6175;font-size:11px;">CLIENTE</span><br><b style="font-size:15px;">{fila.get('nombre_cliente','')}</b></div>
<div><span style="color:#6B6175;font-size:11px;">CELULAR</span><br><b>{fila.get('celular_cliente','')}</b></div>
<div><span style="color:#6B6175;font-size:11px;">CÓDIGO</span><br><b>{fila.get('cod_cliente','')}</b></div>
<div><span style="color:#6B6175;font-size:11px;">ESTADO PAGO</span><br><b style="color:#C62828;">{fila.get('Estado_Pago','')}</b></div>
</div></div>""", unsafe_allow_html=True)

    # Detectar si ya tiene un escenario de cierre de flujo
    flujo_cerrado_en = None
    for n in range(1, N_INT+1):
        acc_n = str(fila.get(f"ACCIÓN {n}","")).strip()
        if acc_n in CIERRE_FLUJO:
            flujo_cerrado_en = n
            break

    if flujo_cerrado_en:
        st.success(f"✅ Flujo completado en Contacto {flujo_cerrado_en} — '{fila.get(f'ACCIÓN {flujo_cerrado_en}','')}'. No se requieren más contactos.")

    # FORMULARIO — todo en st.form para CERO recargas
    with st.form(key=f"fg_{fila_idx}"):
        bo_o  = [""] + L.get("bo",[])
        bo_i  = bo_o.index(fila.get("Responsable BO","")) if fila.get("Responsable BO","") in bo_o else 0
        resp  = st.selectbox("👤 Responsable BO", bo_o, index=bo_i)

        res   = {}
        col_colors = {1:"#1B5E20",2:"#E65100",3:"#B71C1C"}
        col_labels = {1:"1️⃣ PRIMER CONTACTO",2:"2️⃣ SEGUNDO CONTACTO",3:"3️⃣ TERCER CONTACTO"}

        fecha_anterior = None  # para validar que fecha N >= fecha N-1

        for n in range(1, N_INT+1):
            # Si el flujo ya cerró en un contacto anterior, mostrar solo lectura
            if flujo_cerrado_en and n > flujo_cerrado_en:
                st.markdown(f'<div style="background:#E5E0EA;color:#6B6175;padding:8px 12px;border-radius:6px;margin:12px 0 8px;font-weight:700;">{col_labels[n]} — No requerido (flujo cerrado)</div>', unsafe_allow_html=True)
                continue

            st.markdown(f'<div style="background:{col_colors[n]};color:white;padding:8px 12px;border-radius:6px;margin:12px 0 8px;font-weight:700;">{col_labels[n]}</div>', unsafe_allow_html=True)

            cf = f"FECHA {n}"; ch = f"HORARIO {n}"; cm = f"MEDIO {n}"
            ct = f"TIPO CONTACTO {n}"; ca = f"ACCIÓN {n}"; cfc = f"FECHA COMPROMISO {n}"; cmo = f"MOTIVO DE NO PAGO {n}"

            vf = fila.get(cf,"")
            try: fd = datetime.strptime(vf,"%Y-%m-%d").date() if vf else (fecha_anterior or _hoy())
            except: fd = fecha_anterior or _hoy()

            # min_value de fecha = fecha del contacto anterior (o 2024-01-01)
            min_f = fecha_anterior if fecha_anterior else date(2024,1,1)

            c1,c2,c3 = st.columns(3)
            with c1: fecha = st.date_input("📅 Fecha", value=fd, min_value=min_f, max_value=date(2030,12,31), key=f"ff{n}")
            with c2:
                ho = [""] + L.get("horario",["8AM - 12PM","12PM - 3PM","3PM - 6PM","6PM - Cierre"])
                hi = ho.index(fila.get(ch,"")) if fila.get(ch,"") in ho else 0
                horario = st.selectbox("🕐 Horario", ho, index=hi, key=f"fh{n}")
            with c3:
                mo = [""] + L.get("medio",["Llamada de voz","Whatsapp","Campo"])
                mi = mo.index(fila.get(cm,"")) if fila.get(cm,"") in mo else 0
                medio = st.selectbox("📞 Medio", mo, index=mi, key=f"fm{n}")

            to = ["","EFECTIVO","NO EFECTIVO"]
            ti = to.index(fila.get(ct,"")) if fila.get(ct,"") in to else 0
            tipo = st.selectbox("🎯 Tipo de contacto", to, index=ti, key=f"ft{n}")

            # Acciones SEPARADAS por tipo — cascada correcta
            tipo_actual = fila.get(ct,"")  # tipo guardado en Drive
            if tipo_actual == "EFECTIVO":
                acc_list = ACCIONES_EFECTIVO
                color_acc = "🟢"
            elif tipo_actual == "NO EFECTIVO":
                acc_list = ACCIONES_NO_EFECTIVO
                color_acc = "🔴"
            else:
                # Sin tipo guardado: mostrar todas
                acc_list = ACCIONES_EFECTIVO + ACCIONES_NO_EFECTIVO
                color_acc = "⚪"

            ao = [""] + acc_list
            ai = ao.index(fila.get(ca,"")) if fila.get(ca,"") in ao else 0
            accion = st.selectbox(f"{color_acc} Acción", ao, index=ai, key=f"fa{n}")

            fc_date = None
            if accion in REQUIERE_FC:
                fcv = fila.get(cfc,"")
                try: fcd2 = datetime.strptime(fcv,"%Y-%m-%d").date() if fcv else fecha
                except: fcd2 = fecha
                fc_date = st.date_input("📆 Fecha compromiso de pago", value=fcd2, min_value=_hoy(), key=f"ffc{n}")
                st.success("💡 Escenario perfecto — genera compromiso de pago. Flujo cierra aquí.")

            motivo = ""
            if accion in REQUIERE_MOTIVO:
                mto = [""] + L.get("motivo",["Problema técnico","Error en facturación","Económicos"])
                mti = mto.index(fila.get(cmo,"")) if fila.get(cmo,"") in mto else 0
                motivo = st.selectbox("❓ Motivo de no pago", mto, index=mti, key=f"fmo{n}")

            res.update({cf:str(fecha), ch:horario, cm:medio, ct:tipo, ca:accion,
                        cfc:str(fc_date) if fc_date else "", cmo:motivo})
            fecha_anterior = fecha  # próximo contacto no puede ser anterior a este

            # Si esta acción cierra el flujo, no mostrar más contactos
            if accion in CIERRE_FLUJO:
                st.info(f"✅ Flujo cerrado aquí con '{accion}'. Los contactos siguientes no son necesarios.")
                break

        submitted = st.form_submit_button("💾 Guardar gestión", type="primary", use_container_width=True)

    if submitted:
        with st.spinner("⏳ Guardando en Drive..."):
            try:
                celdas = []
                if resp != fila.get("Responsable BO",""):
                    try: celdas.append(Cell(row_sheet, headers.index("Responsable BO")+1, resp))
                    except ValueError: pass

                for campo, nv in res.items():
                    ov = str(fila.get(campo,"")).strip()
                    if str(nv).strip() != ov:
                        try: celdas.append(Cell(row_sheet, headers.index(campo)+1, nv))
                        except ValueError: pass

                for n in range(1, N_INT+1):
                    cn_ = [f"{c} {n}" for c in CAMPOS if f"{c} {n}" in res]
                    if any(str(res.get(c,"")).strip() != str(fila.get(c,"")).strip() for c in cn_):
                        for sfx,val in [(f"USUARIO_INT{n}",usr),(f"TIMESTAMP_INT{n}",_ts())]:
                            try: celdas.append(Cell(row_sheet, headers.index(sfx)+1, val))
                            except ValueError: pass

                if celdas:
                    hoja.update_cells(celdas, value_input_option="USER_ENTERED")
                    st.success(f"✅ Guardado — {len(celdas)} celdas actualizadas en Drive.")
                    st.balloons()
                else:
                    st.info("No se detectaron cambios.")
            except Exception as e:
                st.error(f"❌ Error: {e}")

    # Espejo
    st.divider()
    st.markdown('<div style="background:linear-gradient(90deg,#4B0067,#7B1FA2);padding:8px 16px;border-radius:8px;margin-bottom:8px;"><span style="color:white;font-weight:700;">📊 Espejo Consolidado</span></div>', unsafe_allow_html=True)
    cols_e = [c for c in dfp.columns if not c.startswith("USUARIO_INT") and not c.startswith("TIMESTAMP_INT")]
    st.dataframe(dfp[cols_e], use_container_width=True, height=300, hide_index=True)
    st.download_button(f"⬇️ Descargar {per} ({len(dfp)} reg.)",
                       data=dfp.to_csv(index=False,encoding="utf-8-sig"),
                       file_name=f"cobranza_{per}.csv", mime="text/csv", key="cdl")
