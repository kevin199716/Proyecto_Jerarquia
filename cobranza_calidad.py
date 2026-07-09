"""
cobranza_calidad.py v6.0
Módulo de Cobranza — Seguimiento de Calidad
- Columna A de Listas = "Listas" (razón social del BO)
- Regla: EFECTIVO + Genera compromiso + Fecha compromiso = escenario perfecto (fin)
- Fechas como calendario
- Sin None
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

BANDAS = """
<div style="display:flex;gap:0;margin:8px 0 4px;border-radius:8px;overflow:hidden;
            font-size:12px;font-weight:700;font-family:sans-serif;">
    <div style="background:#4B0067;color:white;padding:8px 16px;flex:2;">
        📋 DATOS DEL CLIENTE (solo lectura)</div>
    <div style="background:#1B5E20;color:white;padding:8px 16px;flex:1;">
        1️⃣ PRIMER CONTACTO</div>
    <div style="background:#E65100;color:white;padding:8px 16px;flex:1;">
        2️⃣ SEGUNDO CONTACTO</div>
    <div style="background:#B71C1C;color:white;padding:8px 16px;flex:1;">
        3️⃣ TERCER CONTACTO</div>
</div>
"""


def _listas(hoja, razon=None):
    """Lee la pestaña Listas. Columna A = 'Listas' (razón social del BO)."""
    try:
        v = hoja.get_all_values()
        if len(v) < 2: return {}
        df = pd.DataFrame(v[1:], columns=v[0])
        def u(c):
            if c not in df.columns: return []
            return sorted(set(x for x in df[c].astype(str).str.strip() if x))
        # Columna A se llama "Listas" en el Drive (razón social del BO)
        col_razon = "Listas"
        col_bo = "RESPONSABLE_BO"
        bos = []
        if col_razon in df.columns and col_bo in df.columns:
            d = df if not razon else df[df[col_razon].astype(str).apply(_nr).eq(_nr(razon))]
            bos = sorted(set(x for x in d[col_bo].astype(str).str.strip() if x))
        return {"bo": bos, "medio": u("MEDIO"), "horario": u("HORARIO"),
                "tipo": u("TIPO_CONTACTO"), "ac_ef": u("ACCION_EFECTIVO"),
                "ac_ne": u("ACCION_NO_EFECTIVO"), "motivo": u("MOTIVO_NO_PAGO")}
    except Exception as e:
        st.warning(f"Error leyendo Listas: {e}")
        return {}


def _clean(df):
    for c in df.columns:
        df[c] = df[c].apply(lambda x: "" if x is None or str(x).strip().lower() in ("none","nan") else str(x).strip())
    return df


def _opts(standard, col_data):
    existing = set(str(v).strip() for v in col_data if str(v).strip() and str(v).strip().lower() not in ("none","nan"))
    combined = sorted(set(standard) | existing)
    if "" not in combined: combined.insert(0, "")
    return combined


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
    bo_std = L.get("bo",[])
    medio_std = L.get("medio",["Llamada de voz","Whatsapp","Campo"])
    horario_std = L.get("horario",["8AM - 12PM","12PM - 3PM","3PM - 6PM","6PM - Cierre"])
    tipo_std = L.get("tipo",["EFECTIVO","NO EFECTIVO"])
    acciones_std = sorted(set(L.get("ac_ef",[]) + L.get("ac_ne",[])))
    motivo_std = L.get("motivo",["Problema técnico","Error en facturación","Económicos"])

    if rol != "backoffice" and not razon:
        st.error("❌ Sin razón social asignada."); return
    if rol != "backoffice" and razon and "razon_social" in df.columns:
        df = df[df["razon_social"].apply(_nr).eq(_nr(razon))]
        if df.empty: st.warning("Sin registros para tu dealer."); return

    # Período
    if "PERIODO" in df.columns:
        pers = sorted([p for p in df["PERIODO"].unique() if p], reverse=True)
    else:
        pers = ["sin_periodo"]
    per = st.selectbox("📅 Período", pers, key="cp")
    dfp = df[df["PERIODO"].eq(per)].copy() if "PERIODO" in df.columns else df.copy()
    if dfp.empty: st.info("Sin registros."); return

    ok_edit = str(per) == _per() and _hoy().day <= 20
    if ok_edit:
        st.success(f"✏️ Período {per} abierto (hoy: día {_hoy().day}, cierre: día 20)")
    elif str(per) == _per():
        st.warning(f"🔒 Período {per} cerrado — superó el día 20.")
    else:
        st.info(f"📁 Histórico ({per}) — solo lectura.")

    # Filtros
    with st.expander("🔍 Filtros", expanded=False):
        f1,f2,f3,f4 = st.columns(4)
        with f1: fn = st.text_input("Nombre",key="cfn").strip()
        with f2: fc = st.text_input("Celular",key="cfc").strip()
        with f3: fcd = st.text_input("Código",key="cfcd").strip()
        with f4:
            fbo = st.selectbox("Responsable BO",["TODOS"]+bo_std,key="cfbo")
    dff = dfp.copy()
    if fn and "nombre_cliente" in dff.columns: dff = dff[dff["nombre_cliente"].str.contains(fn,case=False,na=False)]
    if fc and "celular_cliente" in dff.columns: dff = dff[dff["celular_cliente"].str.contains(fc,na=False)]
    if fcd and "cod_cliente" in dff.columns: dff = dff[dff["cod_cliente"].str.contains(fcd,na=False)]
    if fbo != "TODOS" and "Responsable BO" in dff.columns: dff = dff[dff["Responsable BO"].eq(fbo)]
    if dff.empty: st.warning("Sin resultados."); return

    st.caption(f"**{len(dff)}** registros" + (f" (filtrados de {len(dfp)})" if len(dff)!=len(dfp) else ""))

    # Paginación
    PG = 50
    np_ = max(1,-(-len(dff)//PG))
    pg = st.number_input(f"Página (de {np_})",1,np_,1,key="cpg")
    dfpg = dff.iloc[(pg-1)*PG:(pg-1)*PG+PG].copy()
    dfpg = _clean(dfpg)

    # Todas las columnas del Drive, en orden original
    cols = [c for c in headers if c in dfpg.columns]

    readonly = {"NOMBRE_HOJA","razon_social","dni_creador_lead","nombre_creador_lead",
                "fecha_activacion","cod_cliente","nombre_cliente","celular_cliente",
                "plan","boleta_1_monto","boleta_1_fecha_pago","Estado_Pago",
                "cliente_regularizado","PERIODO","Responsable BO",
                "boleta_2_monto","boleta_2_fecha_pago","boleta_3_monto","boleta_3_fecha_pago",
                "USUARIO_INT1","TIMESTAMP_INT1","USUARIO_INT2","TIMESTAMP_INT2",
                "USUARIO_INT3","TIMESTAMP_INT3"}

    # Config columnas con opciones dinámicas
    cc = {}
    for c in cols:
        if c in readonly:
            cc[c] = st.column_config.TextColumn(c, disabled=True)
        elif c == "Responsable BO":
            cc[c] = st.column_config.SelectboxColumn(c, options=_opts(bo_std, dfpg.get(c,[])), width="medium")
        elif c.startswith("HORARIO"):
            cc[c] = st.column_config.SelectboxColumn(c, options=_opts(horario_std, dfpg.get(c,[])), width="small")
        elif c.startswith("MEDIO"):
            cc[c] = st.column_config.SelectboxColumn(c, options=_opts(medio_std, dfpg.get(c,[])), width="small")
        elif c.startswith("TIPO CONTACTO"):
            cc[c] = st.column_config.SelectboxColumn(c, options=_opts(tipo_std, dfpg.get(c,[])), width="small")
        elif c.startswith("ACCIÓN"):
            cc[c] = st.column_config.SelectboxColumn(c, options=_opts(acciones_std, dfpg.get(c,[])), width="medium")
        elif c.startswith("MOTIVO DE NO PAGO"):
            cc[c] = st.column_config.SelectboxColumn(c, options=_opts(motivo_std, dfpg.get(c,[])), width="small")

    if not ok_edit:
        st.dataframe(dfpg[cols], use_container_width=True, height=520, hide_index=True)
    else:
        st.markdown(BANDAS, unsafe_allow_html=True)
        editado = st.data_editor(dfpg[cols], column_config=cc, use_container_width=True,
                                  height=min(550,45+len(dfpg)*35), num_rows="fixed",
                                  hide_index=True, key="ced")

        if st.button("💾 Guardar cambios", type="primary", use_container_width=True, key="cg"):
            with st.spinner("⏳ Guardando..."):
                try:
                    orig = _clean(dfpg[cols].reset_index(drop=True))
                    edit = pd.DataFrame(editado).reset_index(drop=True)
                    edit = _clean(edit)
                    editable_cols = [c for c in cols if c not in readonly]
                    celdas = []
                    nmod = 0

                    for i in range(len(edit)):
                        idx_real = dfpg.index[i]
                        row = int(idx_real) + 2
                        cambios = {}
                        for cn in editable_cols:
                            ov = orig.iloc[i].get(cn,"")
                            nv = edit.iloc[i].get(cn,"")
                            if nv != ov:
                                cambios[cn] = nv
                        if not cambios: continue

                        # Validación secuencial: no llenar intento N sin completar N-1
                        for n in range(2, N_INT+1):
                            cn_ = [f"{c} {n}" for c in CAMPOS]
                            cp_ = [f"{c} {n-1}" for c in CAMPOS]
                            tiene_n = any(edit.iloc[i].get(c,"") for c in cn_ if c in edit.columns)
                            tiene_prev = any(edit.iloc[i].get(c,"") for c in cp_ if c in edit.columns)
                            if tiene_n and not tiene_prev:
                                nom = edit.iloc[i].get("nombre_cliente",f"fila {i+1}")
                                st.error(f"❌ {nom}: Completa el Contacto {n-1} antes del {n}.")
                                st.stop()

                        # Regla escenario perfecto: si Contacto N tiene "Genera compromiso de pago"
                        # con fecha compromiso, los intentos siguientes son innecesarios.
                        # No bloqueamos la edición, pero mostramos un aviso.

                        nmod += 1
                        for cn, val in cambios.items():
                            try:
                                ci = headers.index(cn) + 1
                                celdas.append(Cell(row, ci, val))
                            except ValueError:
                                continue

                        # Timestamps automáticos
                        for n in range(1, N_INT+1):
                            cn_ = [f"{c} {n}" for c in CAMPOS]
                            if any(c in cambios for c in cn_):
                                for sfx, val in [(f"USUARIO_INT{n}", usr), (f"TIMESTAMP_INT{n}", _ts())]:
                                    try:
                                        ci = headers.index(sfx) + 1
                                        celdas.append(Cell(row, ci, val))
                                    except ValueError:
                                        pass

                    if celdas:
                        for b in range(0, len(celdas), 100):
                            hoja.update_cells(celdas[b:b+100], value_input_option="USER_ENTERED")
                        st.success(f"✅ {nmod} fila(s) guardada(s) · {len(celdas)} celdas escritas.")
                        st.rerun()
                    else:
                        st.info("No se detectaron cambios.")
                except st.runtime.scriptrunner.StopException:
                    raise
                except Exception as e:
                    st.error(f"❌ Error: {e}")

    # Descarga
    st.divider()
    csv = dfp.to_csv(index=False, encoding="utf-8-sig")
    st.download_button(f"⬇️ Descargar período {per} ({len(dfp)} registros)",
                       data=csv, file_name=f"cobranza_{per}.csv", mime="text/csv", key="cdl")
