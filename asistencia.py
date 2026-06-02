# ASISTENCIA_V7_FIXES_20260601
# ─────────────────────────────────────────────────────────────────────────────
# FIXES vs V6:
# 1. Detección de cambios corregida: df_edited[col][i] en lugar de .get()
#    → el botón "Guardar" ahora siempre aparece cuando hay cambios
# 2. None→"" en columna DIA: normalizar con str() + strip antes de comparar
# 3. Filtros SIN st.form → no recargan Drive al cambiar, solo filtran en memoria
# 4. Botón Sincronizar visible SOLO para rol backoffice/admin
# 5. Panel A-BM sin HTML suelto — usa st.container() nativo
# 6. en_rango calculado vectorialmente (sin apply fila a fila)
# 7. df_live cacheado en session_state por periodo+dia para no relerlo al filtrar
# ─────────────────────────────────────────────────────────────────────────────

import calendar
import pytz
from datetime import datetime, date

import pandas as pd
import streamlit as st
from sheets import subir_archivo_drive, obtener_o_crear_worksheet

NOMBRE_LIBRO   = "maestra_vendedores"
HOJA_SUSTENTOS = "Sustentos_Bajas"
TZ_LIMA        = pytz.timezone("America/Lima")
CACHE_TTL      = 90

MARCAS_HOY   = ["", "A", "A-BM", "A-VAC", "NA-SA", "NA-CA"]
MARCAS_RETRO = ["", "A-BM"]

BASE_COLS = [
    "RAZON SOCIAL","SUPERVISOR","COORDINADOR","DEPARTAMENTO","PROVINCIA",
    "DNI","NOMBRE","CARGO","ESTADO","FECHA_ALTA","FECHA_CESE","MES","PERIODO"
]
DAY_COLS = [f"DIA_{i}" for i in range(1, 32)]
ALL_COLS = BASE_COLS + DAY_COLS


# =============================================================================
# Utilitarios
# =============================================================================

def hoy_lima() -> date:
    return datetime.now(TZ_LIMA).date()

def periodo_lima() -> str:
    h = hoy_lima()
    return f"{h.year}-{h.month:02d}"

def nt(x) -> str:
    """normalizar_texto — rápido y seguro"""
    if x is None: return ""
    s = str(x).strip()
    return "" if s.upper() in {"NAN","NONE","NULL"} else " ".join(s.split())

def nr(x) -> str:
    return nt(x).upper().replace(".","")

def nd(x) -> str:
    s = nt(x).replace(".0","").replace(",","").replace(" ","")
    return s.zfill(8) if s.isdigit() and len(s)<8 else s

def pf(x):
    try:
        if not x or str(x).strip()=="": return None
        f = pd.to_datetime(x, errors="coerce")
        return None if pd.isna(f) else f.date()
    except: return None

def fs(x) -> str:
    f = pf(x)
    return str(f) if f else nt(x)

def lm(x) -> str:
    """limpiar_marca — acepta None, nan, string"""
    v = nt(x).upper()
    return v if v in MARCAS_HOY else ""

def wk(ws) -> str:
    try: return f"{ws.spreadsheet.id}:{ws.id}:{ws.title}"
    except: return str(id(ws))

def lc(n: int) -> str:
    out=""
    while n:
        n,rem=divmod(n-1,26); out=chr(65+rem)+out
    return out

def nh(h) -> str:
    return nt(h).upper()


# =============================================================================
# Caché de lectura — batch_get por columnas
# =============================================================================

@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def _hdr(_ws, ck:str):
    try: return [nh(x) for x in _ws.row_values(1)]
    except: return []

def leer_header(ws): return _hdr(ws, wk(ws))

@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def _cols(_ws, ck:str, cols_t:tuple):
    headers = [nh(x) for x in _ws.row_values(1)]
    if not headers: return headers,{}
    h2i = {h:i+1 for i,h in enumerate(headers) if h}
    ranges,sel=[],[]
    for col in cols_t:
        cn=nh(col)
        if cn in h2i:
            l=lc(h2i[cn]); ranges.append(f"{l}2:{l}"); sel.append(cn)
    if not ranges: return headers,{}
    vals=_ws.batch_get(ranges)
    data={}
    for cn,v in zip(sel,vals):
        data[cn]=[nt(r[0]) if r else "" for r in v]
    return headers,data

def limpiar_cache():
    for fn in [_hdr,_cols]:
        try: fn.clear()
        except: pass

def df_cols(data:dict, rs:bool=False) -> pd.DataFrame:
    if not data: return pd.DataFrame()
    ml=max((len(v) for v in data.values()),default=0)
    d={k:v+[""]*(ml-len(v)) for k,v in data.items()}
    df=pd.DataFrame(d)
    if rs: df["ROW_SHEET"]=range(2,len(df)+2)
    return df


# =============================================================================
# Base colaboradores
# =============================================================================

def nombre_df(df):
    n =df.get("NOMBRES",pd.Series([""]*len(df))).astype(str).map(nt)
    ap=df.get("APELLIDO PATERNO",pd.Series([""]*len(df))).astype(str).map(nt)
    am=df.get("APELLIDO MATERNO",pd.Series([""]*len(df))).astype(str).map(nt)
    return (n+" "+ap+" "+am).str.replace(r"\s+"," ",regex=True).str.strip()

def _d2d(c): return "PROMOTOR D2D" in str(c).upper().replace("-"," ").replace("  "," ")

def base_cols(hoja_col, periodo:str, razon:str="ALL") -> pd.DataFrame:
    cols=(
        "RAZON SOCIAL","SUPERVISOR A CARGO","SUPERVISOR","COORDINADOR",
        "DEPARTAMENTO","PROVINCIA","DNI","NOMBRES","APELLIDO PATERNO","APELLIDO MATERNO",
        "ESTADO","FECHA DE CREACION USUARIO","FECHA_ALTA","FECHA DE CESE","FECHA_CESE","CARGO (ROL)"
    )
    headers,data=_cols(hoja_col,wk(hoja_col),cols)
    if not headers or not data: return pd.DataFrame(columns=BASE_COLS)
    df=df_cols(data)
    if df.empty: return pd.DataFrame(columns=BASE_COLS)
    if razon and razon.upper()!="ALL" and "RAZON SOCIAL" in df.columns:
        df=df[df["RAZON SOCIAL"].map(nr).eq(nr(razon))].copy()
    if "CARGO (ROL)" in df.columns:
        df=df[df["CARGO (ROL)"].astype(str).apply(_d2d)].copy()
    if df.empty: return pd.DataFrame(columns=BASE_COLS)
    o=pd.DataFrame(index=df.index)
    o["RAZON SOCIAL"]=df.get("RAZON SOCIAL","").map(nt) if "RAZON SOCIAL" in df else ""
    o["SUPERVISOR"]=(df["SUPERVISOR A CARGO"].map(nt) if "SUPERVISOR A CARGO" in df.columns
                     else df.get("SUPERVISOR","").map(nt) if "SUPERVISOR" in df.columns else "")
    o["COORDINADOR"]=df.get("COORDINADOR","").map(nt) if "COORDINADOR" in df else ""
    o["DEPARTAMENTO"]=df.get("DEPARTAMENTO","").map(nt) if "DEPARTAMENTO" in df else ""
    o["PROVINCIA"]=df.get("PROVINCIA","").map(nt) if "PROVINCIA" in df else ""
    o["DNI"]=df.get("DNI","").map(nd) if "DNI" in df else ""
    o["NOMBRE"]=nombre_df(df)
    o["CARGO"]=df.get("CARGO (ROL)","").map(nt) if "CARGO (ROL)" in df else ""
    o["ESTADO"]=df.get("ESTADO","ACTIVO").map(lambda x:nt(x).upper()) if "ESTADO" in df else "ACTIVO"
    o["FECHA_ALTA"]=(df["FECHA DE CREACION USUARIO"].map(fs) if "FECHA DE CREACION USUARIO" in df.columns
                     else df["FECHA_ALTA"].map(fs) if "FECHA_ALTA" in df.columns else "")
    o["FECHA_CESE"]=(df["FECHA DE CESE"].map(fs) if "FECHA DE CESE" in df.columns
                     else df["FECHA_CESE"].map(fs) if "FECHA_CESE" in df.columns else "")
    o["MES"]=str(int(periodo[-2:]))
    o["PERIODO"]=periodo
    o=o[o["DNI"].astype(str).str.strip().ne("")].copy()
    o["KEY"]=o["DNI"]+"|"+o["FECHA_ALTA"]+"|"+periodo
    return o.drop_duplicates("KEY",keep="last")


# =============================================================================
# Lectura asistencia y vista live
# =============================================================================

def leer_asis(hoja_asis, periodo:str, col_dia:str, razon:str="ALL") -> tuple:
    headers=leer_header(hoja_asis)
    if not headers: return pd.DataFrame(columns=ALL_COLS+["ROW_SHEET","KEY"]),ALL_COLS.copy()
    cols=tuple(BASE_COLS+[col_dia])
    _,data=_cols(hoja_asis,wk(hoja_asis),cols)
    df=df_cols(data,rs=True)
    if df.empty: return pd.DataFrame(columns=ALL_COLS+["ROW_SHEET","KEY"]),headers
    for c in BASE_COLS+[col_dia]:
        if c not in df.columns: df[c]=""
    df["DNI"]=df["DNI"].map(nd)
    df["FECHA_ALTA"]=df["FECHA_ALTA"].map(fs)
    df["PERIODO"]=df["PERIODO"].map(nt)
    df=df[df["PERIODO"].eq(periodo)].copy()
    if razon and razon.upper()!="ALL" and "RAZON SOCIAL" in df.columns:
        df=df[df["RAZON SOCIAL"].map(nr).eq(nr(razon))].copy()
    df["KEY"]=df["DNI"]+"|"+df["FECHA_ALTA"]+"|"+df["PERIODO"]
    df[col_dia]=df[col_dia].map(lm)
    return df,headers

def vista_live(hoja_col, hoja_asis, periodo:str, col_dia:str, razon:str="ALL") -> tuple:
    base=base_cols(hoja_col,periodo,razon)
    asis,headers=leer_asis(hoja_asis,periodo,col_dia,razon)
    marcas=(asis[["KEY","ROW_SHEET",col_dia]].drop_duplicates("KEY",keep="last")
            if not asis.empty else pd.DataFrame(columns=["KEY","ROW_SHEET",col_dia]))
    live=base.merge(marcas,on="KEY",how="left",suffixes=("","_A"))
    live[col_dia]=live.get(col_dia,"").map(lm)
    live["ROW_SHEET"]=live.get("ROW_SHEET","").fillna("").astype(str)
    return live,headers


# =============================================================================
# Filtros — vectorizados, sin apply
# =============================================================================

def _opts(df, col):
    if col not in df.columns: return ["TODOS"]
    vals=sorted([v for v in df[col].dropna().astype(str).map(nt).unique() if v])
    return ["TODOS"]+vals

def _fil(df, sup, coord, dep, prov, estado):
    r=df
    for col,val in [("SUPERVISOR",sup),("COORDINADOR",coord),
                    ("DEPARTAMENTO",dep),("PROVINCIA",prov),("ESTADO",estado)]:
        if val and val!="TODOS" and col in r.columns:
            r=r[r[col].astype(str).map(nt).eq(val)]
    return r.copy()

def _en_rango_vec(df: pd.DataFrame, fecha_sel: date) -> pd.Series:
    """Vectorizado — mucho más rápido que apply fila a fila"""
    estado = df["ESTADO"].astype(str).str.upper() if "ESTADO" in df.columns else pd.Series("ACTIVO", index=df.index)
    alta   = pd.to_datetime(df["FECHA_ALTA"], errors="coerce").dt.date if "FECHA_ALTA" in df.columns else pd.Series([None]*len(df), index=df.index)
    cese   = pd.to_datetime(df["FECHA_CESE"], errors="coerce").dt.date if "FECHA_CESE" in df.columns else pd.Series([None]*len(df), index=df.index)

    ok = pd.Series(True, index=df.index)
    # antes del alta → fuera
    mask_alta = alta.notna() & alta.apply(lambda a: a is not None and fecha_sel < a if a else False)
    ok = ok & ~mask_alta
    # después del cese → fuera
    mask_cese = cese.notna() & cese.apply(lambda c: c is not None and fecha_sel > c if c else False)
    ok = ok & ~mask_cese
    # inactivo sin cese → fuera
    inactivo_sin_cese = (estado != "ACTIVO") & cese.isna()
    inactivo_post_cese = (estado != "ACTIVO") & cese.notna() & cese.apply(lambda c: c is not None and fecha_sel > c if c else False)
    ok = ok & ~inactivo_sin_cese & ~inactivo_post_cese
    return ok

def periodos_disp():
    h=hoy_lima()
    out=[]
    y,m=h.year,h.month
    for i in range(6):
        yy,mm=y,m-i
        while mm<=0: yy-=1; mm+=12
        out.append(f"{yy}-{mm:02d}")
    return out

def fecha_pd(periodo:str,dia:int) -> date:
    y,m=map(int,periodo.split("-"))
    return date(y,m,min(dia,calendar.monthrange(y,m)[1]))


# =============================================================================
# Escritura
# =============================================================================

def guardar_sustento(row, periodo, dia, archivo) -> str:
    if not archivo: return ""
    contenido=archivo.getvalue()
    mime=archivo.type or "application/octet-stream"
    ext="pdf" if "pdf" in mime else "jpg"
    dni=nd(row.get("DNI",""))
    ts=datetime.now(TZ_LIMA).strftime("%Y%m%d_%H%M%S")
    fname=f"sustento_ABM_{dni}_{periodo}_DIA{dia}_{ts}.{ext}"
    link=subir_archivo_drive(fname,contenido,mime)
    cols=["PERIODO","DIA","FECHA","DNI","NOMBRE","RAZON SOCIAL","MOTIVO","LINK","FECHA_SUBIDA","USUARIO"]
    hoja=obtener_o_crear_worksheet(NOMBRE_LIBRO,HOJA_SUSTENTOS,cols)
    hoja.append_row([
        periodo,f"DIA_{dia}",str(fecha_pd(periodo,dia)),
        dni,row.get("NOMBRE",""),row.get("RAZON SOCIAL",""),
        "A-BM",link,datetime.now(TZ_LIMA).strftime("%Y-%m-%d %H:%M:%S"),
        st.session_state.get("usuario","")
    ],value_input_option="USER_ENTERED")
    return link

def _cab(hoja_asis,headers):
    if headers: return headers
    hoja_asis.append_row(ALL_COLS,value_input_option="USER_ENTERED")
    limpiar_cache(); return ALL_COLS.copy()

def guardar_marca(hoja_asis,row,headers,col_dia,marca) -> str:
    headers=[nh(h) for h in headers]
    headers=_cab(hoja_asis,headers)
    if col_dia not in headers:
        hoja_asis.update_cell(1,len(headers)+1,col_dia)
        headers.append(col_dia); limpiar_cache()
    rs=nt(row.get("ROW_SHEET",""))
    ci=headers.index(col_dia)+1; cl=lc(ci)
    if rs.isdigit():
        hoja_asis.update_acell(f"{cl}{int(rs)}",marca)
        limpiar_cache(); return "actualizado"
    nueva=[row.get(h,"") if h in BASE_COLS else (marca if h==col_dia else "") for h in headers]
    hoja_asis.append_row(nueva,value_input_option="USER_ENTERED")
    limpiar_cache(); return "nuevo"

def registrar_alta_en_asistencia(hoja_asis, campos:dict) -> str:
    try:
        limpiar_cache()
        return f"Colaborador DNI {campos.get('DNI','')} disponible en Presencialidad."
    except Exception as e:
        return f"Recarga Presencialidad ({e})."


# =============================================================================
# CSS
# =============================================================================

_CSS = """
<style>
.asis-leyenda{display:flex;flex-wrap:wrap;gap:6px;margin:4px 0 10px}
.asis-chip{padding:3px 11px;border-radius:20px;font-size:11px;font-weight:600;white-space:nowrap;border:1px solid rgba(0,0,0,.06)}
.chip-A{background:#D1FAE5;color:#065F46}
.chip-BM{background:#DBEAFE;color:#1E40AF}
.chip-VAC{background:#FEF9C3;color:#854D0E}
.chip-NASA{background:#FEE2E2;color:#991B1B}
.chip-NACA{background:#FFE4BA;color:#92400E}

.asis-metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:10px 0}
.asis-metric{background:white;border:1px solid #E5E0EA;border-radius:12px;padding:12px 16px 10px;text-align:center;box-shadow:0 1px 3px rgba(75,0,103,.06)}
.asis-metric .v{font-size:26px;font-weight:800;color:#4B0067;line-height:1}
.asis-metric .l{font-size:11px;color:#6B6175;margin-top:4px}
.asis-metric.m-ok .v{color:#065F46}
.asis-metric.m-pen .v{color:#92400E}
.asis-metric.m-tot .v{color:#1E40AF}

.retro-banner{background:#FFF7ED;border:1.5px solid #FED7AA;border-radius:10px;padding:10px 16px;font-size:12.5px;color:#92400E;margin:6px 0 10px;display:flex;align-items:center;gap:8px}
.bm-panel{background:#EFF6FF;border:1.5px solid #BFDBFE;border-radius:12px;padding:14px 18px;margin:8px 0}
.bm-title{font-size:12.5px;font-weight:700;color:#1E40AF;margin-bottom:10px}

.jer-stats{display:flex;flex-wrap:wrap;gap:10px;margin:10px 0 14px}
.jer-stat{flex:1;min-width:120px;background:white;border:1px solid #E5E0EA;border-radius:12px;padding:12px 16px 10px;text-align:center;box-shadow:0 1px 4px rgba(75,0,103,.07)}
.jer-stat .sv{font-size:22px;font-weight:800;color:#4B0067;line-height:1.1}
.jer-stat .sl{font-size:10.5px;color:#6B6175;margin-top:4px;font-weight:600;text-transform:uppercase;letter-spacing:.4px}

.jer-wrap{width:100%;overflow-x:auto;overflow-y:auto;max-height:500px;border-radius:10px;border:1px solid #E5E0EA;margin:4px 0;box-shadow:0 2px 8px rgba(75,0,103,.06)}
.jer-table{width:100%;border-collapse:collapse;font-size:12.5px;font-family:inherit}
.jer-table thead th{position:sticky;top:0;z-index:2;background:linear-gradient(135deg,#4B0067,#3a0052);color:white;padding:10px 12px;text-align:left;font-size:11px;font-weight:700;letter-spacing:.5px;white-space:nowrap}
.jer-table tbody tr{border-bottom:1px solid #F2EEF5}
.jer-table tbody tr:nth-child(even){background:#FDFAFF}
.jer-table tbody tr:hover{background:#F3E5FA}
.jer-table tbody td{padding:8px 12px;color:#1A1521;white-space:nowrap;vertical-align:middle}
.jer-table tbody td.nm{white-space:normal;min-width:160px;max-width:260px}
.jr-a{background:#D1FAE5;color:#065F46;padding:2px 9px;border-radius:10px;font-size:10.5px;font-weight:700}
.jr-i{background:#FEE2E2;color:#991B1B;padding:2px 9px;border-radius:10px;font-size:10.5px;font-weight:700}
.sync-info{background:#EFF6FF;border:1px solid #BFDBFE;border-radius:10px;padding:8px 14px;font-size:12px;color:#1E40AF;margin:4px 0}
.cambios-box{background:#F0FDF4;border:1.5px solid #BBF7D0;border-radius:12px;padding:12px 16px;margin:8px 0;font-size:12.5px;color:#065F46}
</style>
"""

def _ley():
    return """<div class='asis-leyenda'>
<span class='asis-chip chip-A'>✅ A — Asistió</span>
<span class='asis-chip chip-BM'>🏥 A-BM — Baja Médica</span>
<span class='asis-chip chip-VAC'>🌴 A-VAC — Vacaciones</span>
<span class='asis-chip chip-NASA'>❌ NA-SA — Sin aviso</span>
<span class='asis-chip chip-NACA'>⚠️ NA-CA — Con aviso</span>
</div>"""

def _mets(total,editables,marcados,pendientes):
    return f"""<div class='asis-metrics'>
<div class='asis-metric m-tot'><div class='v'>{total}</div><div class='l'>👥 Total filtrado</div></div>
<div class='asis-metric'><div class='v'>{editables}</div><div class='l'>✏️ Editables</div></div>
<div class='asis-metric m-ok'><div class='v'>{marcados}</div><div class='l'>✅ Marcados</div></div>
<div class='asis-metric m-pen'><div class='v'>{pendientes}</div><div class='l'>⏳ Pendientes</div></div>
</div>"""

def _jer_stats(df):
    total=len(df)
    act=int((df.get("ESTADO",pd.Series()).astype(str).str.upper()=="ACTIVO").sum()) if "ESTADO" in df.columns else 0
    sups=df["SUPERVISOR"].nunique() if "SUPERVISOR" in df.columns else 0
    deps=df["DEPARTAMENTO"].nunique() if "DEPARTAMENTO" in df.columns else 0
    return f"""<div class='jer-stats'>
<div class='jer-stat'><div class='sv'>{total}</div><div class='sl'>Total</div></div>
<div class='jer-stat'><div class='sv' style='color:#065F46'>{act}</div><div class='sl'>Activos</div></div>
<div class='jer-stat'><div class='sv' style='color:#991B1B'>{total-act}</div><div class='sl'>Inactivos</div></div>
<div class='jer-stat'><div class='sv'>{sups}</div><div class='sl'>Supervisores</div></div>
<div class='jer-stat'><div class='sv'>{deps}</div><div class='sl'>Departamentos</div></div>
</div>"""

def _jer_tabla(df,max_f=500):
    pref=["RAZON SOCIAL","DNI","NOMBRE","SUPERVISOR","COORDINADOR",
          "DEPARTAMENTO","PROVINCIA","ESTADO","FECHA_ALTA","FECHA_CESE"]
    cols=[c for c in pref if c in df.columns]
    labels={"RAZON SOCIAL":"Socio","DNI":"DNI","NOMBRE":"Nombre","SUPERVISOR":"Supervisor",
            "COORDINADOR":"Coordinador","DEPARTAMENTO":"Depto","PROVINCIA":"Provincia",
            "ESTADO":"Estado","FECHA_ALTA":"Alta","FECHA_CESE":"Cese"}
    thead="".join(f"<th>{labels.get(c,c)}</th>" for c in cols)
    rows=[]
    for _,r in df.head(max_f).iterrows():
        cells=[]
        for c in cols:
            v=str(r.get(c,"") or "").strip()
            if c=="ESTADO":
                cls="jr-a" if v.upper()=="ACTIVO" else "jr-i"
                cells.append(f"<td><span class='{cls}'>{v or '—'}</span></td>")
            elif c=="NOMBRE": cells.append(f"<td class='nm'>{v or '—'}</td>")
            else: cells.append(f"<td>{v or '—'}</td>")
        rows.append("<tr>"+"".join(cells)+"</tr>")
    return (f"<div class='jer-wrap'><table class='jer-table'>"
            f"<thead><tr>{thead}</tr></thead><tbody>{''.join(rows)}</tbody>"
            f"</table></div>")


# =============================================================================
# UI Principal
# =============================================================================

def mostrar_asistencia(hoja_asistencia, hoja_colaboradores, registro_mod=None, razon=None):
    st.markdown(_CSS, unsafe_allow_html=True)
    st.markdown("<span class='wow-section-title'>🗓️ Presencialidad Dealer</span>", unsafe_allow_html=True)

    usuario_razon = nt(razon if razon is not None else st.session_state.get("razon","ALL"))
    es_dealer     = bool(usuario_razon and usuario_razon.upper()!="ALL")
    rol_actual    = st.session_state.get("rol","")
    es_admin      = rol_actual in ("backoffice","admin","editor")

    # ── Control: Periodo · Día · (Sincronizar solo admin) ───────────────────
    cols_top = [1.6, 1.6, 0.8] if es_admin else [1.8, 1.8]
    if es_admin:
        c1,c2,c3 = st.columns(cols_top)
    else:
        c1,c2 = st.columns(cols_top)

    with c1:
        periodo = st.selectbox("📅 Periodo", periodos_disp(), index=0, key="asis_periodo")
    y,m = map(int,periodo.split("-"))
    dias = list(range(1, calendar.monthrange(y,m)[1]+1))
    dd   = hoy_lima().day if periodo==periodo_lima() and hoy_lima().day in dias else 1
    with c2:
        dia = st.selectbox("📆 Día", dias, index=dias.index(dd), key="asis_dia")

    if es_admin:
        with c3:
            st.markdown("<div style='height:26px'></div>", unsafe_allow_html=True)
            if st.button("🔄 Sincronizar", key="btn_sync",
                         help="Fuerza relectura desde Drive (solo backoffice)"):
                limpiar_cache()
                # limpiar live cacheado
                for k in [k for k in st.session_state if k.startswith("_live_")]:
                    del st.session_state[k]
                st.rerun()

    col_dia   = f"DIA_{dia}"
    fecha_sel = fecha_pd(periodo,dia)
    es_retro  = fecha_sel < hoy_lima()

    st.markdown(_ley(), unsafe_allow_html=True)
    if es_retro:
        st.markdown(
            "<div class='retro-banner'>⚠️ <b>Fecha retroactiva</b> — "
            "Solo se permite <b>A-BM</b> con sustento adjunto.</div>",
            unsafe_allow_html=True
        )

    # ── Carga — cacheada en session_state por clave periodo+dia+razon ────────
    live_key = f"_live_{periodo}_{dia}_{usuario_razon}"
    hdr_key  = f"_hdr_{periodo}_{dia}_{usuario_razon}"

    if live_key not in st.session_state:
        with st.spinner("⏳ Cargando datos desde Drive…"):
            try:
                df_live, headers = vista_live(
                    hoja_colaboradores, hoja_asistencia, periodo, col_dia,
                    usuario_razon if es_dealer else "ALL"
                )
                st.session_state[live_key] = df_live
                st.session_state[hdr_key]  = headers
            except Exception as e:
                st.error(f"Error al cargar presencialidad: {e}")
                if es_admin:
                    st.markdown("<div class='sync-info'>💡 Usa <b>🔄 Sincronizar</b> para forzar relectura.</div>", unsafe_allow_html=True)
                return
    else:
        df_live = st.session_state[live_key]
        headers = st.session_state.get(hdr_key, ALL_COLS.copy())

    if df_live.empty:
        st.warning("No hay promotores D2D para este usuario/periodo.")
        return

    # ── Filtros — SIN st.form → instant, solo filtran en memoria ────────────
    st.markdown("**🔍 Filtros**")
    fa,fb,fc = st.columns([1.5,1,1])
    with fa:
        buscar  = st.text_input("DNI / nombre", placeholder="Ej: 76043772",
                                key="asis_buscar", label_visibility="collapsed")
    with fb:
        f_sup   = st.selectbox("Supervisor",   _opts(df_live,"SUPERVISOR"),   key="asis_sup",   label_visibility="collapsed")
    with fc:
        f_coord = st.selectbox("Coordinador",  _opts(df_live,"COORDINADOR"),  key="asis_coord", label_visibility="collapsed")
    fd,fe,ff = st.columns(3)
    with fd:
        f_dep   = st.selectbox("Departamento", _opts(df_live,"DEPARTAMENTO"), key="asis_dep",   label_visibility="collapsed")
    with fe:
        f_prov  = st.selectbox("Provincia",    _opts(df_live,"PROVINCIA"),    key="asis_prov",  label_visibility="collapsed")
    with ff:
        f_est   = st.selectbox("Estado",       _opts(df_live,"ESTADO"),       key="asis_est",   label_visibility="collapsed")

    # Aplicar filtros en memoria (vectorizado, <5ms incluso con 10k filas)
    df_f = _fil(df_live, f_sup, f_coord, f_dep, f_prov, f_est)
    q = nt(buscar).upper()
    if q:
        mask = pd.Series(False, index=df_f.index)
        for c in ["DNI","NOMBRE","SUPERVISOR","COORDINADOR","DEPARTAMENTO","PROVINCIA"]:
            if c in df_f.columns:
                mask |= df_f[c].astype(str).str.upper().str.contains(q, na=False)
        df_f = df_f[mask].copy()

    if df_f.empty:
        st.warning("Sin resultados con los filtros aplicados.")
        return

    # en_rango vectorizado
    df_f = df_f.copy()
    df_f["_er"] = _en_rango_vec(df_f, fecha_sel)

    total     = len(df_f)
    er_mask   = df_f["_er"]
    editables = int(er_mask.sum())
    marcados  = int((df_f.loc[er_mask, col_dia].ne("")).sum()) if editables else 0
    pendientes= editables - marcados

    st.markdown(_mets(total,editables,marcados,pendientes), unsafe_allow_html=True)

    # ═══════════════════════════════════════════════════════════════════════
    # BLOQUE 1 — data_editor con SelectboxColumn inline en columna DIA_X
    # ═══════════════════════════════════════════════════════════════════════
    st.markdown(
        f"<span class='wow-section-title'>📋 Lista de personal — marcación <b>{col_dia}</b> inline</span>",
        unsafe_allow_html=True
    )
    st.caption(
        f"Edita la columna **{col_dia}** directamente en la tabla. "
        + ("Solo A-BM está disponible (fecha pasada)." if es_retro
           else "Selecciona el tipo de marcación por fila.")
        + " El botón **💾 Guardar** aparece automáticamente cuando detecta cambios."
    )

    cols_ed = ["DNI","NOMBRE","SUPERVISOR","COORDINADOR",
               "DEPARTAMENTO","PROVINCIA","ESTADO","FECHA_ALTA","FECHA_CESE",col_dia]
    for c in cols_ed:
        if c not in df_f.columns: df_f[c] = ""

    marcas_sel = MARCAS_RETRO if es_retro else MARCAS_HOY

    df_ed    = df_f[cols_ed].copy()
    # Normalizar DIA para evitar None nativo
    df_ed[col_dia] = df_ed[col_dia].apply(lm)
    keys_s   = df_f["KEY"].reset_index(drop=True)
    rs_s     = df_f["ROW_SHEET"].reset_index(drop=True)
    er_s     = df_f["_er"].reset_index(drop=True)
    df_ed    = df_ed.reset_index(drop=True)

    LIMITE = 300
    if len(df_ed) > LIMITE:
        st.caption(f"Mostrando {LIMITE} de {len(df_ed)}. Usa filtros para acotar.")
        df_ed  = df_ed.iloc[:LIMITE].copy()
        keys_s = keys_s.iloc[:LIMITE]
        rs_s   = rs_s.iloc[:LIMITE]
        er_s   = er_s.iloc[:LIMITE]

    # Guardar snapshot del DIA antes de editar para detectar cambios
    snap_key = f"snap_{periodo}_{dia}"
    if snap_key not in st.session_state:
        st.session_state[snap_key] = df_ed[col_dia].tolist()

    col_cfg = {
        "DNI":          st.column_config.TextColumn("DNI",          disabled=True, width="small"),
        "NOMBRE":       st.column_config.TextColumn("Nombre",       disabled=True, width="large"),
        "SUPERVISOR":   st.column_config.TextColumn("Supervisor",   disabled=True),
        "COORDINADOR":  st.column_config.TextColumn("Coordinador",  disabled=True),
        "DEPARTAMENTO": st.column_config.TextColumn("Departamento", disabled=True),
        "PROVINCIA":    st.column_config.TextColumn("Provincia",    disabled=True),
        "ESTADO":       st.column_config.TextColumn("Estado",       disabled=True, width="small"),
        "FECHA_ALTA":   st.column_config.TextColumn("Alta",         disabled=True, width="small"),
        "FECHA_CESE":   st.column_config.TextColumn("Cese",         disabled=True, width="small"),
        col_dia: st.column_config.SelectboxColumn(
            col_dia, options=marcas_sel, required=False, width="small"
        ),
    }

    editor_key = f"asis_editor_{periodo}_{dia}"
    df_edited  = st.data_editor(
        df_ed,
        column_config=col_cfg,
        use_container_width=True,
        hide_index=True,
        height=min(560, 56 + len(df_ed)*35),
        key=editor_key,
        num_rows="fixed",
    )

    # ── Detección de cambios (FIX: acceso correcto a DataFrame editado) ──────
    cambios = []
    snap    = st.session_state.get(snap_key, [])

    for i in range(len(df_ed)):
        # FIX: usar indexación directa en lugar de .get()
        val_orig  = lm(df_ed[col_dia].iloc[i])
        val_nuevo = lm(df_edited[col_dia].iloc[i]) if df_edited is not None else val_orig

        if val_nuevo == val_orig: continue
        if not er_s.iloc[i]: continue
        if es_retro and val_nuevo not in MARCAS_RETRO: continue

        row_data = df_live[df_live["KEY"]==keys_s.iloc[i]]
        cambios.append({
            "i":          i,
            "key":        str(keys_s.iloc[i]),
            "row_sheet":  str(rs_s.iloc[i]),
            "dni":        str(df_ed["DNI"].iloc[i]),
            "nombre":     nt(df_ed["NOMBRE"].iloc[i]),
            "val_orig":   val_orig,
            "val_nuevo":  val_nuevo,
            "row_data":   row_data.iloc[0].to_dict() if not row_data.empty else {},
        })

    # ── Panel de guardado ────────────────────────────────────────────────────
    if cambios:
        bm_cambios = [c for c in cambios if c["val_nuevo"]=="A-BM"]
        ot_cambios = [c for c in cambios if c["val_nuevo"]!="A-BM"]

        # Resumen de cambios detectados
        resumen = ", ".join(f"{c['dni']}→{c['val_nuevo']}" for c in cambios[:8])
        if len(cambios)>8: resumen += f" (+{len(cambios)-8} más)"
        st.markdown(
            f"<div class='cambios-box'>📝 <b>{len(cambios)}</b> cambio(s) detectado(s): {resumen}</div>",
            unsafe_allow_html=True
        )

        # Panel A-BM con upload por persona
        archivos_bm = {}
        if bm_cambios:
            with st.container():
                st.markdown(
                    f"<div class='bm-panel'>"
                    f"<div class='bm-title'>🏥 {len(bm_cambios)} marcación(es) A-BM — adjunta el sustento (obligatorio)</div>"
                    f"</div>",
                    unsafe_allow_html=True
                )
                for c in bm_cambios:
                    archivo = st.file_uploader(
                        f"📎 Sustento A-BM — {c['dni']} | {c['nombre']}",
                        type=["pdf","png","jpg","jpeg"],
                        key=f"abm_{periodo}_{dia}_{c['dni']}",
                        help="Adjunta el certificado médico o constancia (PDF o imagen)"
                    )
                    archivos_bm[c["key"]] = archivo

        col_btn1, col_btn2 = st.columns([3,1])
        with col_btn1:
            guardar_ok = st.button(
                f"💾 Guardar {len(cambios)} marcación(es)",
                key="btn_guardar", type="primary", use_container_width=True
            )
        with col_btn2:
            cancelar = st.button("✖ Cancelar", key="btn_cancelar", use_container_width=True)

        if cancelar:
            # Limpiar snap para resetear el editor
            if snap_key in st.session_state: del st.session_state[snap_key]
            if live_key in st.session_state: del st.session_state[live_key]
            st.rerun()

        if guardar_ok:
            errores, exitos = [], []
            barra = st.progress(0, text="Guardando…")
            total_c = len(cambios)

            for idx_c, c in enumerate(cambios):
                try:
                    if c["val_nuevo"]=="A-BM":
                        arx = archivos_bm.get(c["key"])
                        if not arx:
                            errores.append(f"⛔ {c['dni']}: falta sustento A-BM.")
                            continue
                        guardar_sustento(c["row_data"], periodo, dia, arx)

                    row_s = pd.Series(c["row_data"])
                    row_s["ROW_SHEET"] = c["row_sheet"]
                    res = guardar_marca(hoja_asistencia, row_s, headers, col_dia, c["val_nuevo"])
                    exitos.append(f"✅ {c['dni']} → **{c['val_nuevo']}** ({res})")
                except Exception as e:
                    errores.append(f"❌ {c['dni']}: {e}")

                barra.progress((idx_c+1)/total_c, text=f"Guardando {idx_c+1}/{total_c}…")

            barra.empty()
            for msg in exitos:   st.success(msg)
            for msg in errores:  st.error(msg)

            if exitos:
                # Limpiar caché de sesión para releer datos frescos
                for k in [k for k in st.session_state if k.startswith("_live_") or k.startswith("snap_")]:
                    del st.session_state[k]
                st.rerun()
    else:
        st.caption(f"✔ Sin cambios — edita la columna **{col_dia}** en la tabla y el botón Guardar aparecerá aquí.")

    # ═══════════════════════════════════════════════════════════════════════
    # BLOQUE 2 — Espejo marcaciones del día
    # ═══════════════════════════════════════════════════════════════════════
    ya_m = df_f[df_f[col_dia].ne("")].copy() if col_dia in df_f.columns else pd.DataFrame()
    with st.expander(f"📊 Marcaciones registradas — {col_dia} ({len(ya_m)} de {total})", expanded=False):
        if ya_m.empty:
            st.info("Aún no hay marcaciones para este día.")
        else:
            cesp=["DNI","NOMBRE","SUPERVISOR","DEPARTAMENTO","PROVINCIA","ESTADO",col_dia]
            cesp=[c for c in cesp if c in ya_m.columns]
            st.dataframe(
                ya_m[cesp].reset_index(drop=True),
                use_container_width=True, hide_index=True, height=360,
                column_config={
                    "DNI":    st.column_config.TextColumn("DNI"),
                    "NOMBRE": st.column_config.TextColumn("Nombre",width="large"),
                    col_dia:  st.column_config.TextColumn(col_dia, width="small"),
                }
            )

    # ═══════════════════════════════════════════════════════════════════════
    # BLOQUE 3 — Jerarquía rediseñada
    # ═══════════════════════════════════════════════════════════════════════
    st.divider()
    st.markdown("<span class='wow-section-title'>📋 Jerarquía completa de promotores D2D</span>", unsafe_allow_html=True)
    st.caption("Datos ya en memoria — sin llamada adicional a Drive.")
    st.markdown(_jer_stats(df_live), unsafe_allow_html=True)
    st.markdown(_jer_tabla(df_live), unsafe_allow_html=True)
    st.caption(f"Total: **{len(df_live)}** promotores D2D.")
