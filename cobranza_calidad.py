"""
cobranza_calidad.py v13.0 — Arquitectura CRM profesional
Tabla solo lectura (rápida) + Formulario lateral para editar
Sin AgGrid editable = Sin friseo = Sin errores de componente
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

# Árbol de tipificaciones
ACCIONES = {
    "EFECTIVO": [
        "Ya pagó",
        "Genera compromiso de pago",
        "Indica no pagará",
        "Contesta y cuelga",
        "Contesta y no da razón",
        "Otros: detallar",
    ],
    "NO EFECTIVO": [
        "Teléfono apagado",
        "Teléfono suspendido",
        "Teléfono no existe",
        "Timbra y no contesta",
        "Contesta pero desconoce a titular",
    ],
}
ACCIONES_REQUIEREN_FC = {"Genera compromiso de pago"}
ACCIONES_REQUIEREN_MOTIVO = {"Indica no pagará", "Otros: detallar"}

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
        return {"bo":bos, "medio":u("MEDIO"), "horario":u("HORARIO"), "motivo":u("MOTIVO_NO_PAGO")}
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
    pa = f"{g/total*100:.1f}%" if total > 0 else "0%"
    pe = f"{ef/total*100:.1f}%" if total > 0 else "0%"
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


def _formulario_contacto(n, fila, L, ok):
    """Formulario dentro de st.form — sin keys explícitas para evitar conflictos."""
    col_fecha = f"FECHA {n}"
    col_hor   = f"HORARIO {n}"
    col_med   = f"MEDIO {n}"
    col_tipo  = f"TIPO CONTACTO {n}"
    col_acc   = f"ACCIÓN {n}"
    col_fc    = f"FECHA COMPROMISO {n}"
    col_mot   = f"MOTIVO DE NO PAGO {n}"

    colors = {1:"#1B5E20", 2:"#E65100", 3:"#B71C1C"}
    labels = {1:"1️⃣ PRIMER CONTACTO", 2:"2️⃣ SEGUNDO CONTACTO", 3:"3️⃣ TERCER CONTACTO"}

    st.markdown(f"""
    <div style="background:{colors[n]};color:white;padding:8px 12px;
                border-radius:6px;margin:12px 0 8px;font-weight:700;font-size:14px;">
        {labels[n]}
    </div>""", unsafe_allow_html=True)

    if not ok:
        c1,c2,c3,c4 = st.columns(4)
        with c1: st.text_input("Fecha",   value=fila.get(col_fecha,""), disabled=True, key=f"vf{n}")
        with c2: st.text_input("Horario", value=fila.get(col_hor,""),   disabled=True, key=f"vh{n}")
        with c3: st.text_input("Medio",   value=fila.get(col_med,""),   disabled=True, key=f"vm{n}")
        with c4: st.text_input("Tipo",    value=fila.get(col_tipo,""),  disabled=True, key=f"vt{n}")
        c5,c6,c7 = st.columns(3)
        with c5: st.text_input("Acción",  value=fila.get(col_acc,""),   disabled=True, key=f"va{n}")
        with c6: st.text_input("F.Comp.", value=fila.get(col_fc,""),    disabled=True, key=f"vfc{n}")
        with c7: st.text_input("Motivo",  value=fila.get(col_mot,""),   disabled=True, key=f"vmo{n}")
        return None

    val_fecha = fila.get(col_fecha,"")
    try:
        fecha_def = datetime.strptime(val_fecha, "%Y-%m-%d").date() if val_fecha else _hoy()
    except:
        fecha_def = _hoy()

    c1,c2,c3 = st.columns(3)
    with c1:
        fecha = st.date_input("📅 Fecha contacto", value=fecha_def,
                              min_value=date(2024,1,1), max_value=date(2030,12,31),
                              key=f"f_fecha_{n}")
    with c2:
        hor_opts = [""] + L.get("horario",["8AM - 12PM","12PM - 3PM","3PM - 6PM","6PM - Cierre"])
        hor_idx  = hor_opts.index(fila.get(col_hor,"")) if fila.get(col_hor,"") in hor_opts else 0
        horario  = st.selectbox("🕐 Horario", hor_opts, index=hor_idx, key=f"f_hor_{n}")
    with c3:
        med_opts = [""] + L.get("medio",["Llamada de voz","Whatsapp","Campo"])
        med_idx  = med_opts.index(fila.get(col_med,"")) if fila.get(col_med,"") in med_opts else 0
        medio    = st.selectbox("📞 Medio", med_opts, index=med_idx, key=f"f_med_{n}")

    tipo_opts = ["", "EFECTIVO", "NO EFECTIVO"]
    tipo_idx  = tipo_opts.index(fila.get(col_tipo,"")) if fila.get(col_tipo,"") in tipo_opts else 0
    tipo      = st.selectbox("🎯 Tipo de contacto", tipo_opts, index=tipo_idx, key=f"f_tipo_{n}")

    accion    = ""
    fc_date   = None
    motivo    = ""

    if tipo:
        acc_list = ACCIONES.get(tipo, [])
        acc_opts = [""] + acc_list
        acc_val  = fila.get(col_acc,"")
        acc_idx  = acc_opts.index(acc_val) if acc_val in acc_opts else 0
        color    = "🟢" if tipo == "EFECTIVO" else "🔴"
        accion   = st.selectbox(f"{color} Acción ({tipo})", acc_opts, index=acc_idx, key=f"f_acc_{n}")

        if accion in ACCIONES_REQUIEREN_FC:
            fc_val = fila.get(col_fc,"")
            try:
                fc_def = datetime.strptime(fc_val, "%Y-%m-%d").date() if fc_val else fecha
            except:
                fc_def = fecha
            fc_date = st.date_input("📆 Fecha compromiso de pago", value=fc_def,
                                    min_value=_hoy(), key=f"f_fc_{n}")
            st.info("💡 Escenario perfecto — el cliente genera compromiso de pago.")

        if accion in ACCIONES_REQUIEREN_MOTIVO:
            mot_opts = [""] + L.get("motivo",["Problema técnico","Error en facturación","Económicos"])
            mot_val  = fila.get(col_mot,"")
            mot_idx  = mot_opts.index(mot_val) if mot_val in mot_opts else 0
            motivo   = st.selectbox("❓ Motivo de no pago", mot_opts, index=mot_idx, key=f"f_mot_{n}")
    else:
        st.caption("Selecciona el tipo de contacto para ver las acciones.")

    return {
        col_fecha: str(fecha),
        col_hor:   horario,
        col_med:   medio,
        col_tipo:  tipo,
        col_acc:   accion,
        col_fc:    str(fc_date) if fc_date else "",
        col_mot:   motivo,
    }


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
        L = {"bo":[], "medio":["Llamada de voz","Whatsapp","Campo"],
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

    # Filtros
    with st.expander("🔍 Filtros", expanded=False):
        f1,f2,f3,f4 = st.columns(4)
        with f1: fn  = st.text_input("Nombre",key="cfn").strip()
        with f2: fc  = st.text_input("Celular",key="cfc").strip()
        with f3: fcd = st.text_input("Código", key="cfcd").strip()
        with f4: fbo = st.selectbox("Responsable BO",["TODOS"]+L.get("bo",[]),key="cfbo")

    dff = dfp.copy()
    if fn  and "nombre_cliente"  in dff.columns: dff = dff[dff["nombre_cliente"].str.contains(fn, case=False, na=False)]
    if fc  and "celular_cliente" in dff.columns: dff = dff[dff["celular_cliente"].str.contains(fc, na=False)]
    if fcd and "cod_cliente"     in dff.columns: dff = dff[dff["cod_cliente"].str.contains(fcd, na=False)]
    if fbo != "TODOS" and "Responsable BO" in dff.columns:
        dff = dff[dff["Responsable BO"].eq(fbo)]
    if dff.empty: st.warning("Sin resultados."); return
    if len(dff) != len(dfp): st.caption(f"**{len(dff)}** de {len(dfp)} registros.")

    # ── TABLA DE SOLO LECTURA (rápida, sin edición) ──
    cols_tabla = [c for c in ["cod_cliente","nombre_cliente","celular_cliente",
                               "Estado_Pago","PERIODO","Responsable BO",
                               "TIPO CONTACTO 1","ACCIÓN 1",
                               "TIPO CONTACTO 2","ACCIÓN 2",
                               "TIPO CONTACTO 3","ACCIÓN 3"]
                  if c in dff.columns]

    # Paginación manual ligera
    PAGE = 25
    total_pag = max(1, -(-len(dff) // PAGE))
    pag = st.number_input(f"Página (de {total_pag})", 1, total_pag, 1, key="pag")
    ini = (pag-1)*PAGE
    df_page = dff.iloc[ini:ini+PAGE].copy()

    # Tabla con color por tipo contacto
    def _color_row(row):
        tipo1 = str(row.get("TIPO CONTACTO 1","")).strip()
        if tipo1 == "EFECTIVO":    return ["background-color:#F1F8E9"]*len(row)
        if tipo1 == "NO EFECTIVO": return ["background-color:#FFF3E0"]*len(row)
        return [""]*len(row)

    styled = df_page[cols_tabla].style.apply(_color_row, axis=1)
    st.dataframe(styled, use_container_width=True, height=380, hide_index=True)

    if not ok:
        st.divider()
        st.markdown('<div style="background:linear-gradient(90deg,#4B0067,#7B1FA2);padding:8px 16px;border-radius:8px;margin-bottom:8px;"><span style="color:white;font-weight:700;">📊 Espejo Consolidado</span></div>', unsafe_allow_html=True)
        cols_esp = [c for c in dfp.columns if not c.startswith("USUARIO_INT") and not c.startswith("TIMESTAMP_INT")]
        st.dataframe(dfp[cols_esp], use_container_width=True, height=300, hide_index=True)
        csv = dfp.to_csv(index=False, encoding="utf-8-sig")
        st.download_button(f"⬇️ Descargar {per} ({len(dfp)} reg.)",
                           data=csv, file_name=f"cobranza_{per}.csv", mime="text/csv", key="cdl")
        return

    # ── FORMULARIO DE EDICIÓN ──
    st.divider()
    st.markdown("""
    <div style="background:linear-gradient(90deg,#4B0067,#7B1FA2);padding:10px 16px;
                border-radius:8px;margin-bottom:12px;">
        <span style="color:white;font-weight:700;font-size:15px;">
            ✏️ Registrar gestión — Selecciona un cliente de la tabla
        </span>
    </div>""", unsafe_allow_html=True)

    # Selector de cliente FUERA del form para que filtre la tabla
    opciones_sel = ["-- Selecciona un cliente --"] + [
        f"{r.get('cod_cliente','')} · {r.get('nombre_cliente','')} · {r.get('celular_cliente','')}"
        for _, r in df_page.iterrows()
    ]
    sel_idx = st.selectbox("Cliente a gestionar", range(len(opciones_sel)),
                           format_func=lambda i: opciones_sel[i], key="sel_cliente")

    if sel_idx == 0:
        st.info("👆 Selecciona un cliente de la lista para registrar su gestión.")
        return

    fila_idx = df_page.index[sel_idx - 1]
    fila = dict(dff.loc[fila_idx])
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

    # ── TODO EL FORMULARIO EN st.form → CERO RECARGAS AL EDITAR ──
    with st.form(key="form_gestion"):
        bo_list = L.get("bo",[])
        bo_idx = bo_list.index(fila.get("Responsable BO","")) + 1 if fila.get("Responsable BO","") in bo_list else 0
        responsable = st.selectbox("👤 Responsable BO", [""] + bo_list, index=bo_idx)

        resultados = {}
        for n in range(1, N_INT+1):
            res = _formulario_contacto(n, fila, L, ok)
            if res:
                resultados.update(res)

        submitted = st.form_submit_button("💾 Guardar gestión", type="primary", use_container_width=True)

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

                # Campos de contacto
                for campo, nuevo_val in resultados.items():
                    orig_val = str(fila.get(campo,"")).strip()
                    if str(nuevo_val).strip() != orig_val:
                        try:
                            ci = headers.index(campo) + 1
                            celdas.append(Cell(row_sheet, ci, nuevo_val))
                        except ValueError: pass

                # Timestamps por intento modificado
                for n in range(1, N_INT+1):
                    cn_ = [f"{c} {n}" for c in CAMPOS if f"{c} {n}" in resultados]
                    if any(str(resultados.get(c,"")).strip() != str(fila.get(c,"")).strip() for c in cn_):
                        for sfx, val in [(f"USUARIO_INT{n}",usr),(f"TIMESTAMP_INT{n}",_ts())]:
                            try:
                                ci = headers.index(sfx) + 1
                                celdas.append(Cell(row_sheet, ci, val))
                            except ValueError: pass

                if celdas:
                    hoja.update_cells(celdas, value_input_option="USER_ENTERED")
                    st.success(f"✅ Gestión guardada — {len(celdas)} celdas actualizadas en Drive.")
                    st.balloons()
                    # Limpiar selección
                    st.session_state["sel_cliente"] = 0
                    st.rerun()
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
    st.download_button(f"⬇️ Descargar {per} ({len(dfp)} reg.)",
                       data=csv, file_name=f"cobranza_{per}.csv", mime="text/csv", key="cdl")
