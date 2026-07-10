"""
cobranza_calidad.py v7.0 — AgGrid
Módulo de Cobranza — Seguimiento de Calidad
- AgGrid: sin friseo, sin None, cabeceras agrupadas con colores
- Desplegables en cascada
- Calendarios para fechas
- Escritura celda por celda
- Timestamps automáticos
"""
from datetime import datetime, date
import pandas as pd
import pytz
import streamlit as st
from st_aggrid import AgGrid, GridUpdateMode, DataReturnMode, JsCode
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

# CSS para cabeceras agrupadas con colores
AGGRID_CSS = {
    ".header-client": {"background-color": "#4B0067 !important", "color": "white !important", "font-weight": "700 !important"},
    ".header-contact1": {"background-color": "#1B5E20 !important", "color": "white !important", "font-weight": "700 !important"},
    ".header-contact2": {"background-color": "#E65100 !important", "color": "white !important", "font-weight": "700 !important"},
    ".header-contact3": {"background-color": "#B71C1C !important", "color": "white !important", "font-weight": "700 !important"},
    ".header-timestamp": {"background-color": "#37474F !important", "color": "white !important", "font-weight": "700 !important"},
}


def _listas(hoja, razon=None):
    try:
        v = hoja.get_all_values()
        if len(v) < 2: return {}
        df = pd.DataFrame(v[1:], columns=v[0])
        def u(c):
            if c not in df.columns: return []
            return sorted(set(x for x in df[c].astype(str).str.strip() if x))
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


def _build_grid_options(df, headers, listas, editable, readonly_cols):
    """Construye gridOptions con cabeceras agrupadas por color."""
    todas_acciones = sorted(set(listas.get("ac_ef",[]) + listas.get("ac_ne",[])))

    def _col_def(field, header=None, editable_col=True, editor=None, values=None, width=120):
        d = {
            "field": field,
            "headerName": header or field,
            "editable": editable and editable_col and field not in readonly_cols,
            "resizable": True,
            "sortable": True,
            "filter": True,
            "width": width,
            "cellStyle": {"fontSize": "12px"},
        }
        if editor == "select" and values:
            d["cellEditor"] = "agSelectCellEditor"
            d["cellEditorParams"] = {"values": [""] + values}
        return d

    # Grupo: Datos del cliente (solo lectura, morado)
    client_cols = []
    for col in ["NOMBRE_HOJA","razon_social","dni_creador_lead","nombre_creador_lead",
                "fecha_activacion","cod_cliente","nombre_cliente","celular_cliente",
                "plan","boleta_1_monto","boleta_1_fecha_pago","Estado_Pago",
                "cliente_regularizado","PERIODO","Responsable BO"]:
        if col in df.columns:
            if col == "Responsable BO":
                client_cols.append(_col_def(col, "Responsable BO", True, "select", listas.get("bo",[]), 160))
            else:
                client_cols.append(_col_def(col, col, False, width=130))

    # Grupos de contacto (verde, naranja, rojo)
    contact_groups = []
    colors = ["header-contact1", "header-contact2", "header-contact3"]
    labels = ["1️⃣ PRIMER CONTACTO", "2️⃣ SEGUNDO CONTACTO", "3️⃣ TERCER CONTACTO"]

    for n in range(1, N_INT + 1):
        children = []
        for campo in CAMPOS:
            col_name = f"{campo} {n}"
            if col_name not in df.columns:
                continue
            if campo == "FECHA":
                children.append(_col_def(col_name, "Fecha", True, width=110))
            elif campo == "HORARIO":
                children.append(_col_def(col_name, "Horario", True, "select", listas.get("horario",[]), 110))
            elif campo == "MEDIO":
                children.append(_col_def(col_name, "Medio", True, "select", listas.get("medio",[]), 120))
            elif campo == "TIPO CONTACTO":
                children.append(_col_def(col_name, "Tipo Contacto", True, "select", listas.get("tipo",[]), 130))
            elif campo == "ACCIÓN":
                children.append(_col_def(col_name, "Acción", True, "select", todas_acciones, 200))
            elif campo == "FECHA COMPROMISO":
                children.append(_col_def(col_name, "F. Compromiso", True, width=110))
            elif campo == "MOTIVO DE NO PAGO":
                children.append(_col_def(col_name, "Motivo No Pago", True, "select", listas.get("motivo",[]), 140))

        if children:
            contact_groups.append({
                "headerName": labels[n-1],
                "headerClass": colors[n-1],
                "children": children,
            })

    # Grupo: Timestamps (gris, solo lectura)
    ts_cols = []
    for n in range(1, N_INT + 1):
        for sfx in [f"USUARIO_INT{n}", f"TIMESTAMP_INT{n}"]:
            if sfx in df.columns:
                ts_cols.append(_col_def(sfx, sfx, False, width=140))

    # Boletas extra (solo lectura)
    boleta_cols = []
    for col in ["boleta_2_monto","boleta_2_fecha_pago","boleta_3_monto","boleta_3_fecha_pago"]:
        if col in df.columns:
            boleta_cols.append(_col_def(col, col, False, width=120))

    column_defs = [
        {"headerName": "📋 DATOS DEL CLIENTE", "headerClass": "header-client", "children": client_cols},
    ] + contact_groups

    if ts_cols:
        column_defs.append({"headerName": "🕐 MARCAJE", "headerClass": "header-timestamp", "children": ts_cols})
    if boleta_cols:
        column_defs.append({"headerName": "📄 BOLETAS EXTRA", "headerClass": "header-client", "children": boleta_cols})

    grid_options = {
        "columnDefs": column_defs,
        "defaultColDef": {
            "resizable": True,
            "sortable": True,
            "filter": True,
            "editable": False,
            "cellStyle": {"fontSize": "12px"},
        },
        "enableRangeSelection": False,
        "suppressRowClickSelection": True,
        "rowHeight": 32,
        "headerHeight": 35,
        "groupHeaderHeight": 38,
        "pagination": True,
        "paginationPageSize": 50,
    }
    return grid_options


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

    st.caption(f"**{len(dfp)}** registros en este período.")

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

    if len(dff) != len(dfp):
        st.caption(f"Mostrando **{len(dff)}** de {len(dfp)} registros.")

    # Columnas de solo lectura
    readonly_cols = {"NOMBRE_HOJA","razon_social","dni_creador_lead","nombre_creador_lead",
                     "fecha_activacion","cod_cliente","nombre_cliente","celular_cliente",
                     "plan","boleta_1_monto","boleta_1_fecha_pago","Estado_Pago",
                     "cliente_regularizado","PERIODO",
                     "boleta_2_monto","boleta_2_fecha_pago","boleta_3_monto","boleta_3_fecha_pago",
                     "USUARIO_INT1","TIMESTAMP_INT1","USUARIO_INT2","TIMESTAMP_INT2",
                     "USUARIO_INT3","TIMESTAMP_INT3"}

    # Grid con AgGrid
    grid_options = _build_grid_options(dff, headers, L, ok_edit, readonly_cols)

    grid_response = AgGrid(
        dff,
        gridOptions=grid_options,
        update_mode=GridUpdateMode.MANUAL,
        data_return_mode=DataReturnMode.AS_INPUT,
        fit_columns_on_grid_load=False,
        height=520,
        allow_unsafe_jscode=True,
        theme="streamlit",
        custom_css=AGGRID_CSS,
        key="aggrid_cobranza",
    )

    if ok_edit:
        if st.button("💾 Guardar cambios", type="primary", use_container_width=True, key="cg"):
            with st.spinner("⏳ Guardando cambios en Drive..."):
                try:
                    df_editado = _clean(pd.DataFrame(grid_response["data"]))
                    df_original = _clean(dff.reset_index(drop=True))

                    editable_cols = [c for c in headers if c not in readonly_cols and c in df_editado.columns]
                    celdas = []
                    nmod = 0

                    for i in range(len(df_editado)):
                        if i >= len(df_original):
                            break
                        idx_real = dff.index[i] if i < len(dff.index) else i
                        row_sheet = int(idx_real) + 2
                        cambios = {}

                        for cn in editable_cols:
                            ov = str(df_original.iloc[i].get(cn, "")).strip()
                            nv = str(df_editado.iloc[i].get(cn, "")).strip()
                            if nv.lower() in ("none","nan"): nv = ""
                            if nv != ov:
                                cambios[cn] = nv

                        if not cambios:
                            continue

                        # Validación secuencial
                        for n in range(2, N_INT + 1):
                            cn_ = [f"{c} {n}" for c in CAMPOS]
                            cp_ = [f"{c} {n-1}" for c in CAMPOS]
                            tiene_n = any(str(df_editado.iloc[i].get(c,"")).strip() for c in cn_ if c in df_editado.columns)
                            tiene_prev = any(str(df_editado.iloc[i].get(c,"")).strip() for c in cp_ if c in df_editado.columns)
                            if tiene_n and not tiene_prev:
                                nom = df_editado.iloc[i].get("nombre_cliente", f"fila {i+1}")
                                st.error(f"❌ {nom}: Completa Contacto {n-1} antes del {n}.")
                                st.stop()

                        nmod += 1
                        for cn, val in cambios.items():
                            try:
                                ci = headers.index(cn) + 1
                                celdas.append(Cell(row_sheet, ci, val))
                            except ValueError:
                                continue

                        # Timestamps
                        for n in range(1, N_INT + 1):
                            cn_ = [f"{c} {n}" for c in CAMPOS]
                            if any(c in cambios for c in cn_):
                                for sfx, val in [(f"USUARIO_INT{n}", usr), (f"TIMESTAMP_INT{n}", _ts())]:
                                    try:
                                        ci = headers.index(sfx) + 1
                                        celdas.append(Cell(row_sheet, ci, val))
                                    except ValueError:
                                        pass

                    if celdas:
                        for b in range(0, len(celdas), 100):
                            hoja.update_cells(celdas[b:b+100], value_input_option="USER_ENTERED")
                        st.success(f"✅ ¡Guardado exitoso! {nmod} fila(s) actualizada(s) · {len(celdas)} celdas escritas en Drive.")
                        st.balloons()
                    else:
                        st.info("ℹ️ No se detectaron cambios en la tabla.")

                except st.runtime.scriptrunner.StopException:
                    raise
                except Exception as e:
                    st.error(f"❌ Error al guardar: {e}")

    # ── ESPEJO CONSOLIDADO ──
    st.divider()
    st.markdown("""
    <div style="background:linear-gradient(90deg,#4B0067,#7B1FA2);padding:10px 16px;
                border-radius:8px;margin-bottom:12px;">
        <span style="color:white;font-weight:700;font-size:15px;">
            📊 Espejo Consolidado — Vista completa del período
        </span>
    </div>
    """, unsafe_allow_html=True)

    # Espejo como tabla de solo lectura con AgGrid
    espejo_options = _build_grid_options(dfp, headers, L, False, set(headers))
    AgGrid(
        dfp,
        gridOptions=espejo_options,
        update_mode=GridUpdateMode.NO_UPDATE,
        fit_columns_on_grid_load=False,
        height=400,
        theme="streamlit",
        custom_css=AGGRID_CSS,
        key="aggrid_espejo",
    )

    csv = dfp.to_csv(index=False, encoding="utf-8-sig")
    st.download_button(f"⬇️ Descargar período {per} ({len(dfp)} registros)",
                       data=csv, file_name=f"cobranza_{per}.csv", mime="text/csv", key="cdl")
