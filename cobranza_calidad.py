"""Cobranza — gestión secuencial de casos con trazabilidad, control de concurrencia e indicadores."""
import html
import io
import json
import random
import threading
import time
import uuid
from collections import defaultdict
from datetime import date, datetime

import altair as alt
import gspread
import pandas as pd
import pytz
import streamlit as st
from gspread.cell import Cell
from gspread.utils import rowcol_to_a1

import cobranza_reglas as R
import pagos_reporting as PR
import vintage_cobranza as V
from sheets import _abrir_spreadsheet

LIBRO = "Facturas - Calidad"
PESTANA_CASOS = "Consolidado"
PESTANA_LISTAS = "Listas"
PESTANA_HISTORIAL = "Historial_Gestiones"
COLUMNAS_HISTORIAL = ["TIMESTAMP", "USUARIO", "ROL", "RAZON_SOCIAL", "ID_CASO", "PERIODO",
                      "COD_CLIENTE", "OPERACION", "INTERACCION", "ESTADO_RESULTANTE", "DETALLE"]
# Una sola lectura del Sheet cada TTL segundos, compartida por todos los usuarios del proceso.
TTL_CASOS = 60
TTL_LISTAS = 600
TTL_HISTORIAL = 120

HORARIOS_DEFECTO = ["8AM - 12PM", "12PM - 3PM", "3PM - 6PM", "6PM - Cierre"]
MEDIOS_DEFECTO = ["Llamada de voz", "Whatsapp", "Campo"]
MOTIVOS_DEFECTO = ["Problema técnico", "Error en facturación", "Económicos"]

COLOR_EFECTIVO = "#2a78d6"
COLOR_NO_EFECTIVO = "#eb6834"

zona_peru = pytz.timezone("America/Lima")
_LOCK_ESTRUCTURA = threading.Lock()
# Serializa todas las escrituras al Consolidado del proceso (lectura fresca → validación → escritura).
_LOCK_LOTE = threading.Lock()
LIMITE_FILAS_TABLA = 1500


def _ahora():
    return datetime.now(zona_peru)


def _hoy() -> date:
    return _ahora().date()


def _ts() -> str:
    return _ahora().strftime("%Y-%m-%d %H:%M:%S")


def _nr(s) -> str:
    return " ".join(str(s).strip().upper().replace(".", "").replace("-", "").split())


def _txt(fila, campo) -> str:
    valor = fila.get(campo, "")
    return "" if valor is None else str(valor).strip()


def _e(s) -> str:
    return html.escape(str(s or ""))


class ConflictoError(Exception):
    pass


class ValidacionError(Exception):
    def __init__(self, errores):
        super().__init__("; ".join(errores))
        self.errores = errores


# ─────────────────────────── Acceso a Google Sheets ───────────────────────────

def _reintentar(fn, intentos: int = 4):
    """Reintenta con espera exponencial cuando Google responde cuota excedida u ocupado."""
    for i in range(intentos):
        try:
            return fn()
        except gspread.exceptions.APIError as e:
            codigo = getattr(getattr(e, "response", None), "status_code", None)
            if codigo in (429, 500, 502, 503) and i < intentos - 1:
                time.sleep(min(8.0, 1.5 * 2 ** i) + random.random())
                continue
            raise


@st.cache_resource(show_spinner=False)
def _ws(nombre: str):
    return _reintentar(lambda: _abrir_spreadsheet(LIBRO).worksheet(nombre))


@st.cache_resource(show_spinner=False)
def _ws_historial():
    libro = _abrir_spreadsheet(LIBRO)
    try:
        return _reintentar(lambda: libro.worksheet(PESTANA_HISTORIAL))
    except gspread.exceptions.WorksheetNotFound:
        ws = _reintentar(lambda: libro.add_worksheet(title=PESTANA_HISTORIAL, rows=1000,
                                                     cols=len(COLUMNAS_HISTORIAL)))
        _reintentar(lambda: ws.append_row(COLUMNAS_HISTORIAL, value_input_option="RAW"))
        return ws


def _columnas_unicas(headers: list[str]) -> list[str]:
    vistos: dict[str, int] = {}
    salida = []
    for i, h in enumerate(headers):
        nombre = str(h).strip() or f"_SIN_NOMBRE_{i + 1}"
        if nombre in vistos:
            vistos[nombre] += 1
            nombre = f"{nombre} ({vistos[nombre]})"
        else:
            vistos[nombre] = 1
        salida.append(nombre)
    return salida


@st.cache_resource(ttl=TTL_CASOS, show_spinner=False)
def _cargar_casos():
    """Lee el Consolidado una vez por TTL y devuelve (headers, df enriquecido, hora de lectura).
    El DataFrame es compartido entre sesiones: tratarlo como solo lectura."""
    valores = _reintentar(lambda: _ws(PESTANA_CASOS).get_all_values())
    stamp = _ahora().strftime("%H:%M:%S")
    if not valores:
        return [], pd.DataFrame(), stamp
    headers = valores[0]
    columnas = _columnas_unicas(headers)
    ancho = len(columnas)
    filas = [(f + [""] * ancho)[:ancho] for f in valores[1:]]
    df = pd.DataFrame(filas, columns=columnas)
    df = df.apply(lambda s: s.astype(str).str.strip().replace({"None": "", "nan": "", "NaN": ""}))
    df["_FILA"] = range(2, len(df) + 2)
    df = df[(df[columnas] != "").any(axis=1)]
    for c in R.COLUMNAS_REQUERIDAS + ["PERIODO", "razon_social", "cod_cliente", "nombre_cliente",
                                      "celular_cliente", "Estado_Pago"]:
        if c not in df.columns:
            df[c] = ""
    df = R.enriquecer(df, _hoy())
    return headers, df, stamp


def _asegurar_estructura(headers: list[str], df: pd.DataFrame) -> bool:
    """Agrega columnas faltantes y asigna ID_CASO a filas sin ID (o con ID duplicado).
    Devuelve True si modificó el Sheet."""
    faltan = [c for c in R.COLUMNAS_REQUERIDAS if c not in headers]
    sin_id = (not df.empty) and bool(((df[R.COL_ID] == "") | df[R.COL_ID].duplicated()).any())
    if not faltan and not sin_id:
        return False
    with _LOCK_ESTRUCTURA:
        ws = _ws(PESTANA_CASOS)
        valores = _reintentar(ws.get_all_values)
        headers = list(valores[0]) if valores else []
        faltan = [c for c in R.COLUMNAS_REQUERIDAS if c not in headers]
        actualizaciones = []
        if faltan:
            total = len(headers) + len(faltan)
            if ws.col_count < total:
                _reintentar(lambda: ws.add_cols(total - ws.col_count))
            actualizaciones.append({
                "range": f"{rowcol_to_a1(1, len(headers) + 1)}:{rowcol_to_a1(1, total)}",
                "values": [faltan],
            })
            headers = headers + faltan
        idx = headers.index(R.COL_ID)
        ids, vistos, cambio = [], set(), False
        for fila in valores[1:]:
            actual = fila[idx].strip() if idx < len(fila) else ""
            tiene_datos = any(str(v).strip() for v in fila)
            if tiene_datos and (not actual or actual in vistos):
                actual = uuid.uuid4().hex[:12].upper()
                cambio = True
            if actual:
                vistos.add(actual)
            ids.append([actual])
        if cambio and ids:
            actualizaciones.append({
                "range": f"{rowcol_to_a1(2, idx + 1)}:{rowcol_to_a1(len(ids) + 1, idx + 1)}",
                "values": ids,
            })
        if actualizaciones:
            _reintentar(lambda: ws.batch_update(actualizaciones, value_input_option="RAW"))
    _cargar_casos.clear()
    return True


@st.cache_data(ttl=TTL_LISTAS, show_spinner=False)
def _cargar_listas() -> dict:
    try:
        valores = _reintentar(lambda: _ws(PESTANA_LISTAS).get_all_values())
    except Exception:
        valores = []
    if len(valores) < 2:
        return {"bo": {}, "medio": MEDIOS_DEFECTO, "horario": HORARIOS_DEFECTO, "motivo": MOTIVOS_DEFECTO}
    df = pd.DataFrame(valores[1:], columns=_columnas_unicas(valores[0]))

    def unicos(c, defecto):
        if c not in df.columns:
            return defecto
        return sorted({x for x in df[c].astype(str).str.strip() if x}) or defecto

    bo: dict[str, list[str]] = defaultdict(list)
    if "RESPONSABLE_BO" in df.columns:
        for razon, resp in zip(df.get("Listas", pd.Series([""] * len(df))), df["RESPONSABLE_BO"]):
            resp = str(resp).strip()
            if resp and resp not in bo[_nr(razon)]:
                bo[_nr(razon)].append(resp)
    return {"bo": {k: sorted(v) for k, v in bo.items()}, "medio": unicos("MEDIO", MEDIOS_DEFECTO),
            "horario": unicos("HORARIO", HORARIOS_DEFECTO), "motivo": unicos("MOTIVO_NO_PAGO", MOTIVOS_DEFECTO)}


@st.cache_data(ttl=TTL_HISTORIAL, show_spinner=False)
def _cargar_historial() -> pd.DataFrame:
    valores = _reintentar(lambda: _ws_historial().get_all_values())
    if len(valores) < 2:
        return pd.DataFrame(columns=COLUMNAS_HISTORIAL)
    return pd.DataFrame(valores[1:], columns=_columnas_unicas(valores[0]))


OPERACION_CIERRE_SERVIDOR = "CIERRE_AUTOMATICO_SERVIDOR"
USUARIO_SISTEMA = "sistema-reporting"


def ejecutar_validacion_pagos_servidor() -> dict:
    """
    Cierra automáticamente los casos cuyo pago ya está confirmado en el servidor
    (Reporting), aunque nadie lo haya marcado a mano en el Drive. Nunca rompe
    Cobranza si el servidor no responde o no está configurado.
    Devuelve {"cerrados": int, "aviso": str}.

    No se dispara sola dentro de la app (eso dependería de que alguien tenga
    Cobranza abierta, y la vista del servidor solo se refresca 1 vez al día):
    la llama la tarea programada (tarea_validar_pagos_servidor.py, por cron,
    a las horas en que corren los procesos que actualizan esa vista) o el
    botón manual de Backoffice en Cobranza.
    """
    mapa_pagos, aviso_conexion = PR.leer_estado_pagos()
    if not mapa_pagos:
        return {"cerrados": 0, "aviso": aviso_conexion}

    ws = _ws(PESTANA_CASOS)
    requeridas = ["cod_cliente", "Estado_Pago", R.COL_ID, R.COL_ESTADO, R.COL_MOTIVO_CIERRE,
                  R.COL_DETALLE_CIERRE, R.COL_USUARIO_CIERRE, R.COL_FECHA_CIERRE,
                  R.COL_ULT_MOD, R.COL_USR_ULT_MOD]
    with _LOCK_LOTE:
        valores = _reintentar(ws.get_all_values)
        if not valores:
            return {"cerrados": 0, "aviso": ""}
        headers = valores[0]
        if any(c not in headers for c in requeridas):
            return {"cerrados": 0, "aviso": "Faltan columnas en el Drive para validar pagos del servidor."}
        idx = {c: headers.index(c) for c in requeridas}
        ts = _ts()
        celdas, historial_filas, cerrados = [], [], []

        for r, fila in enumerate(valores[1:], start=2):
            fila = (fila + [""] * len(headers))[:len(headers)]
            cod = fila[idx["cod_cliente"]].strip()
            pago = mapa_pagos.get(cod)
            if not pago or pago["estado_pago"] != PR.PAGADO:
                continue
            if fila[idx[R.COL_MOTIVO_CIERRE]].strip():
                continue  # ya cerrado (a mano o por un ciclo anterior): no se toca.
            fecha_pago = pago["boleta_fecha_pago"] or ts[:10]
            monto = pago["boleta_monto"]
            detalle = (f"Pago confirmado en servidor (Reporting) el {fecha_pago}"
                       + (f", monto S/ {monto}" if monto else "") + ".")
            cambios = {
                R.COL_MOTIVO_CIERRE: f"{R.MOTIVO_CIERRE_PAGO} (validado en servidor)",
                R.COL_DETALLE_CIERRE: detalle,
                R.COL_USUARIO_CIERRE: USUARIO_SISTEMA,
                R.COL_FECHA_CIERRE: ts,
                R.COL_ESTADO: R.E_PAGADO,
                R.COL_ULT_MOD: ts,
                R.COL_USR_ULT_MOD: USUARIO_SISTEMA,
                "Estado_Pago": PR.PAGADO,
            }
            for campo, valor in cambios.items():
                celdas.append(Cell(r, headers.index(campo) + 1, valor))
            historial_filas.append([ts, USUARIO_SISTEMA, "sistema", "", fila[idx[R.COL_ID]],
                                     "", cod, OPERACION_CIERRE_SERVIDOR, "", R.E_PAGADO, detalle])
            cerrados.append(cod)

        if not celdas:
            return {"cerrados": 0, "aviso": ""}
        _reintentar(lambda: ws.update_cells(celdas, value_input_option="RAW"))
        try:
            _reintentar(lambda: _ws_historial().append_rows(historial_filas, value_input_option="RAW"))
        except Exception:
            pass
    _cargar_casos.clear()
    _cargar_historial.clear()
    return {"cerrados": len(cerrados), "aviso": ""}


def _guardar_caso(caso: dict, preparar, ctx: dict) -> tuple[str, str]:
    """
    Guarda cambios de un caso de forma segura:
      1. Relee del Sheet (1 llamada) cabeceras, columna ID y la fila del caso.
      2. Ubica la fila por ID_CASO (nunca por posición).
      3. Si otro usuario cambió el caso desde que se cargó, rechaza (ConflictoError).
      4. preparar(fila_actual) valida contra el dato fresco y devuelve los cambios.
      5. Escribe solo las celdas modificadas (1 llamada) y registra el historial.
    """
    id_caso = caso[R.COL_ID]
    ws = _ws(PESTANA_CASOS)
    with _LOCK_LOTE:
        letra = rowcol_to_a1(1, ctx["idx_id"] + 1).rstrip("0123456789")
        fila_hint = int(caso.get("_FILA", 2))
        bloques = _reintentar(lambda: ws.batch_get(["1:1", f"{letra}:{letra}", f"{fila_hint}:{fila_hint}"]))
        headers = list(bloques[0][0]) if bloques[0] else []
        if R.COL_ID not in headers:
            raise ConflictoError("La estructura del Sheet cambió. Actualiza la página e inténtalo de nuevo.")
        if headers.index(R.COL_ID) != ctx["idx_id"]:
            idx = headers.index(R.COL_ID)
            letra = rowcol_to_a1(1, idx + 1).rstrip("0123456789")
            bloques = [bloques[0]] + _reintentar(lambda: ws.batch_get([f"{letra}:{letra}"])) + [[]]
        ids = [r[0].strip() if r else "" for r in bloques[1]]
        filas_id = [i + 1 for i, v in enumerate(ids) if v == id_caso]
        if len(filas_id) != 1:
            raise ConflictoError("No se pudo ubicar el caso de forma única en el Drive "
                                 "(fue eliminado o duplicado). Actualiza la página.")
        fila_real = filas_id[0]
        if fila_real == fila_hint and bloques[2]:
            valores_fila = list(bloques[2][0])
        else:
            valores_fila = _reintentar(lambda: ws.row_values(fila_real))
        valores_fila += [""] * (len(headers) - len(valores_fila))
        actual = {h: str(v).strip() for h, v in zip(headers, valores_fila) if h}

        modificados = [c for c in R.COLUMNAS_GESTIONADAS
                       if _txt(caso, c) != actual.get(c, "")]
        if modificados:
            quien = actual.get(R.COL_USR_ULT_MOD) or "otro usuario o directamente en el Drive"
            cuando = actual.get(R.COL_ULT_MOD, "")
            raise ConflictoError(
                f"Este caso fue actualizado por {quien}{' el ' + cuando if cuando else ''} "
                "después de que lo abriste. Se recargaron los datos: revisa y vuelve a registrar.")
        if not ctx["es_bo"] and _nr(actual.get("razon_social", "")) != _nr(ctx["razon"]):
            raise ConflictoError("Este caso no pertenece a tu razón social.")

        cambios, operacion, n_int = preparar(actual)
        ts = _ts()
        fusion = {**actual, **cambios}
        cambios[R.COL_ESTADO] = R.estado_caso(fusion, _hoy())
        cambios[R.COL_ULT_MOD] = ts
        cambios[R.COL_USR_ULT_MOD] = ctx["usuario"]

        faltantes = [c for c in cambios if c not in headers]
        if faltantes:
            raise ConflictoError(f"Faltan columnas en el Drive: {', '.join(faltantes)}. Actualiza la página.")
        celdas = [Cell(fila_real, headers.index(c) + 1, v) for c, v in cambios.items()
                  if actual.get(c, "") != str(v)]
        _reintentar(lambda: ws.update_cells(celdas, value_input_option="RAW"))

        detalle = {c: [actual.get(c, ""), v] for c, v in cambios.items()
                   if actual.get(c, "") != str(v) and c not in (R.COL_ULT_MOD, R.COL_USR_ULT_MOD)}
        aviso = ""
        try:
            _reintentar(lambda: _ws_historial().append_row(
                [ts, ctx["usuario"], ctx["rol"], actual.get("razon_social", ""), id_caso,
                 actual.get("PERIODO", ""), actual.get("cod_cliente", ""), operacion,
                 n_int or "", cambios[R.COL_ESTADO], json.dumps(detalle, ensure_ascii=False)],
                value_input_option="RAW", insert_data_option="INSERT_ROWS"))
        except Exception as e:
            aviso = f"La gestión se guardó, pero no se pudo registrar en el historial ({e})."
    _cargar_casos.clear()
    _cargar_historial.clear()
    return cambios[R.COL_ESTADO], aviso


def _guardar_lote(ediciones: list[tuple[dict, dict]], ctx: dict) -> tuple[int, list[str], str]:
    """
    Guarda varias filas editadas en la tabla con 1 lectura y 1 escritura al Drive.
    Cada fila se valida contra el dato fresco; las filas con error o conflicto no se guardan.
    """
    ws = _ws(PESTANA_CASOS)
    errores, historial, rangos, guardadas = [], [], [], 0
    with _LOCK_LOTE:
        valores = _reintentar(ws.get_all_values)
        headers = list(valores[0]) if valores else []
        if R.COL_ID not in headers:
            return 0, ["La estructura del Drive cambió. Actualiza la página."], ""
        idx_id = headers.index(R.COL_ID)
        posiciones: dict[str, list[int]] = defaultdict(list)
        for r, fila in enumerate(valores[1:], start=2):
            if idx_id < len(fila) and fila[idx_id].strip():
                posiciones[fila[idx_id].strip()].append(r)
        hoy, ts = _hoy(), _ts()

        for original, editado in ediciones:
            etiqueta = f"{original.get('cod_cliente', '')} · {original.get('nombre_cliente', '')}"
            filas = posiciones.get(original[R.COL_ID], [])
            if len(filas) != 1:
                errores.append(f"{etiqueta}: no se ubicó el caso en el Drive (eliminado o duplicado).")
                continue
            r = filas[0]
            crudo = list(valores[r - 1]) + [""] * len(headers)
            actual = {h: str(v).strip() for h, v in zip(headers, crudo) if h}
            if not ctx["es_bo"] and _nr(actual.get("razon_social", "")) != _nr(ctx["razon"]):
                errores.append(f"{etiqueta}: el caso no pertenece a tu razón social.")
                continue
            if any(_txt(original, c) != actual.get(c, "") for c in R.COLUMNAS_GESTIONADAS):
                quien = actual.get(R.COL_USR_ULT_MOD) or "otro usuario"
                errores.append(f"{etiqueta}: {quien} lo actualizó mientras editabas. Vuelve a ingresarlo.")
                continue
            cambios, operaciones, errs = R.procesar_edicion(original, editado, actual, ctx["es_bo"],
                                                            ctx["usuario"], ts, hoy)
            if errs:
                errores.extend(f"{etiqueta}: {e}" for e in errs)
                continue
            if not cambios:
                continue
            cambios[R.COL_ESTADO] = R.estado_caso({**actual, **cambios}, hoy)
            cambios[R.COL_ULT_MOD] = ts
            cambios[R.COL_USR_ULT_MOD] = ctx["usuario"]
            faltantes = [c for c in cambios if c not in headers]
            if faltantes:
                errores.append(f"{etiqueta}: faltan columnas en el Drive ({', '.join(faltantes)}).")
                continue
            por_col = {headers.index(c) + 1: v for c, v in cambios.items() if actual.get(c, "") != str(v)}
            c_min, c_max = min(por_col), max(por_col)
            rangos.append({"range": f"{rowcol_to_a1(r, c_min)}:{rowcol_to_a1(r, c_max)}",
                           "values": [[por_col.get(c) for c in range(c_min, c_max + 1)]]})
            detalle = {c: [actual.get(c, ""), v] for c, v in cambios.items()
                       if actual.get(c, "") != str(v) and c not in (R.COL_ULT_MOD, R.COL_USR_ULT_MOD)}
            historial.append([ts, ctx["usuario"], ctx["rol"], actual.get("razon_social", ""), original[R.COL_ID],
                              actual.get("PERIODO", ""), actual.get("cod_cliente", ""),
                              " + ".join(op for op, _ in operaciones),
                              ",".join(str(n) for _, n in operaciones if n), cambios[R.COL_ESTADO],
                              json.dumps(detalle, ensure_ascii=False)])
            guardadas += 1

        if rangos:
            # Las celdas None se envían como null: Google las omite y no pisa lo que haya.
            _reintentar(lambda: ws.batch_update(rangos, value_input_option="RAW"))
    aviso = ""
    if historial:
        try:
            _reintentar(lambda: _ws_historial().append_rows(historial, value_input_option="RAW",
                                                            insert_data_option="INSERT_ROWS"))
        except Exception as e:
            aviso = f"Los cambios se guardaron, pero no se pudo escribir el historial ({e})."
        _cargar_casos.clear()
        _cargar_historial.clear()
    return guardadas, errores, aviso


# ──────────────────────────────── Presentación ────────────────────────────────

# Todo el HTML va en una sola línea: un salto de línea dentro de una etiqueta hace que Streamlit
# muestre el código como texto.
HEADER = (
    '<div class="cob-header"><div class="cob-header-ico">💰</div><div>'
    '<div class="cob-header-t">Cobranza — Gestión y Seguimiento</div>'
    '<div class="cob-header-s">Registro secuencial de contactabilidad · trazabilidad completa · indicadores</div>'
    '</div></div>'
)

CSS = """<style>
.cob-header{background:linear-gradient(135deg,#4B0067,#7B1FA2 55%,#EC6608);border-radius:14px;padding:16px 22px;margin-bottom:14px;display:flex;align-items:center;gap:14px;position:relative;overflow:hidden;}
.cob-header::before{content:"";position:absolute;right:-40px;top:-40px;width:180px;height:180px;border-radius:50%;background:radial-gradient(circle,rgba(255,255,255,.18),transparent 65%);pointer-events:none;}
.cob-header-ico{font-size:28px;position:relative;}
.cob-header-t{color:#fff;font-size:21px;font-weight:800;line-height:1.2;position:relative;}
.cob-header-s{color:rgba(255,255,255,.85);font-size:12px;margin-top:2px;position:relative;}
.cob-kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin:6px 0 12px;}
.cob-kpi{background:linear-gradient(165deg,#fff 70%,#FAF8FC);border:1px solid #E5E0EA;border-top:4px solid var(--c);border-radius:12px;padding:12px 14px;box-shadow:0 1px 3px rgba(75,0,103,.06);transition:transform .15s ease,box-shadow .15s ease;}
.cob-kpi:hover{transform:translateY(-2px);box-shadow:0 8px 18px rgba(75,0,103,.14);}
.cob-kpi .v{font-size:26px;font-weight:800;color:#1A1521;line-height:1.1;}
.cob-kpi .l{font-size:12px;color:#4A4153;margin-top:3px;font-weight:600;}
.cob-kpi .s{font-size:11px;color:#8F8898;margin-top:2px;}
.cob-kpi .bar{height:6px;background:#EFEBF2;border-radius:99px;margin-top:8px;overflow:hidden;}
.cob-kpi .bar i{display:block;height:100%;background:var(--c);border-radius:99px;transition:width .3s ease;}
.cob-dash{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:12px;margin:0 0 14px;}
.cob-panel{background:#fff;border:1px solid #E5E0EA;border-radius:12px;padding:12px 16px;transition:box-shadow .15s ease;}
.cob-panel:hover{box-shadow:0 6px 16px rgba(75,0,103,.1);}
.cob-panel h4{margin:0 0 10px;font-size:13px;color:#4B0067;font-weight:800;}
.cob-stack{display:flex;height:14px;border-radius:99px;overflow:hidden;gap:2px;background:#EFEBF2;}
.cob-stack i{display:block;height:100%;transition:width .3s ease;}
.cob-leg{display:flex;flex-wrap:wrap;gap:6px 14px;margin-top:9px;font-size:11.5px;color:#4A4153;}
.cob-leg span{display:inline-flex;align-items:center;gap:5px;}
.cob-leg b{color:#1A1521;}
.cob-dot{width:9px;height:9px;border-radius:3px;display:inline-block;}
.cob-row{display:grid;grid-template-columns:34px 1fr 70px;align-items:center;gap:8px;font-size:12px;color:#4A4153;margin:5px 0;}
.cob-row .t{height:10px;background:#EFEBF2;border-radius:99px;overflow:hidden;display:flex;gap:2px;}
.cob-row .t i{display:block;height:100%;}
.cob-row .n{text-align:right;color:#1A1521;font-weight:700;}
.cob-pill{display:inline-block;padding:3px 10px;border-radius:999px;font-size:12px;font-weight:700;}
.cob-card{background:#fff;border:1px solid #E5E0EA;border-radius:12px;padding:14px 16px;margin:8px 0;transition:box-shadow .15s ease;}
.cob-card:hover{box-shadow:0 6px 16px rgba(75,0,103,.08);}
.cob-grid{display:flex;gap:28px;flex-wrap:wrap;}
.cob-grid .k{color:#6B6175;font-size:11px;text-transform:uppercase;letter-spacing:.03em;}
.cob-grid .x{font-weight:700;font-size:14px;color:#1A1521;}
.cob-steps{display:flex;gap:6px;flex-wrap:wrap;margin:10px 0 4px;}
.cob-step{flex:1 1 90px;min-width:90px;border-radius:9px;padding:7px 8px;font-size:11.5px;text-align:center;
  border:2px solid var(--c);background:var(--bg);color:var(--t);font-weight:700;transition:transform .15s ease;}
.cob-step:hover{transform:translateY(-1px);}
.cob-int{border:1px solid #E5E0EA;border-left:5px solid var(--c);border-radius:10px;padding:9px 12px;margin:6px 0;
  background:#FCFBFD;font-size:13px;color:#3D3548;transition:box-shadow .15s ease;}
.cob-int:hover{box-shadow:0 4px 12px rgba(75,0,103,.08);}
.cob-int b{color:#1A1521;}
.cob-int .meta{font-size:11px;color:#8F8898;margin-top:3px;}
.cob-reclamo{display:inline-block;background:#FFF4EA;color:#D45605;border:1px solid #FDE6D2;border-radius:999px;padding:2px 10px;font-size:11px;font-weight:700;}
.cob-sec{background:linear-gradient(90deg,#4B0067,#7B1FA2);padding:8px 14px;border-radius:8px;margin:14px 0 8px;
  color:#fff;font-weight:700;font-size:14px;}
@media (max-width:640px){
  .cob-header{padding:14px 16px;gap:10px;}
  .cob-header-ico{font-size:22px;}
  .cob-header-t{font-size:16px;}
  .cob-header-s{font-size:11px;}
  .cob-kpis{grid-template-columns:repeat(auto-fit,minmax(130px,1fr));}
  .cob-kpi .v{font-size:21px;}
  .cob-grid{gap:16px;}
  .cob-step{flex:1 1 70px;min-width:70px;font-size:10.5px;padding:6px;}
}
</style>"""


def _pill(estado: str) -> str:
    icono, fondo, texto = R.ESTILO_ESTADO.get(estado, ("", "#898781", "#fff"))
    return f'<span class="cob-pill" style="background:{fondo};color:{texto};">{icono} {_e(estado)}</span>'


def _etiqueta_estado(estado: str) -> str:
    return f"{R.ESTILO_ESTADO.get(estado, ('',))[0]} {estado}"


def _kpi(valor, etiqueta, color, sub="", pct=None):
    sub_html = f'<div class="s">{_e(sub)}</div>' if sub else ""
    barra = (f'<div class="bar"><i style="width:{max(0.0, min(100.0, pct)):.1f}%"></i></div>'
             if pct is not None else "")
    return (f'<div class="cob-kpi" style="--c:{color};"><div class="v">{_e(valor)}</div>'
            f'<div class="l">{_e(etiqueta)}</div>{sub_html}{barra}</div>')


def _pct(a, b) -> float:
    return a / b * 100 if b else 0.0


def _render_kpis(k: dict):
    t = k["total"]
    est = R.ESTILO_ESTADO
    tarjetas = [
        _kpi(t, "Casos del periodo", "#4B0067", f"{k['interacciones']} contactos registrados"),
        _kpi(f"{k['pct_avance']:.1f}%", "Avance de la gestión", "#EC6608",
             f"{k['gestionados']} gestionados de {t}", k["pct_avance"]),
        _kpi(k["pendientes"], "⚪ Pendientes", est[R.E_PENDIENTE][1], "sin ningún contacto",
             _pct(k["pendientes"], t)),
        _kpi(k["en_proceso"] + k["recontactar"] + k["pend_cierre"], "🔵 En proceso", est[R.E_EN_PROCESO][1],
             f"{k['recontactar']} por recontactar · {k['pend_cierre']} por cerrar",
             _pct(k["en_proceso"] + k["recontactar"] + k["pend_cierre"], t)),
        _kpi(k["compromisos"] + k["compromisos_vencidos"], "🟣 Compromisos de pago", est[R.E_COMPROMISO][1],
             f"{k['compromisos']} vigentes · {k['compromisos_vencidos']} vencidos"),
        _kpi(k["pagados"], "🟢 Ya pagaron", est[R.E_PAGADO][1], f"{k['pct_recupero']:.1f}% de recupero",
             k["pct_recupero"]),
        _kpi(k["finalizados"], "🏁 Finalizados", est[R.E_SIN_EXITO][1],
             f"{k['pagados']} pagaron · {k['sin_exito']} sin éxito", _pct(k["finalizados"], t)),
        _kpi(f"{k['pct_contactabilidad']:.1f}%", "Contactabilidad", COLOR_EFECTIVO,
             f"{k['contactados']} con contacto efectivo", k["pct_contactabilidad"]),
        _kpi(k["con_reclamo"], "📌 Con reclamo",
             "#D45605" if k["con_reclamo"] else "#C8C2CE",
             f"{_pct(k['con_reclamo'], t):.1f}% de los casos" if k["con_reclamo"] else "ningún caso con reclamo"),
    ]
    st.markdown(f'<div class="cob-kpis">{"".join(tarjetas)}</div>', unsafe_allow_html=True)


def _render_dashboard(dfp: pd.DataFrame, k: dict):
    """Paneles visuales: distribución por estado, efectivo vs no efectivo y avance por contacto."""
    t = k["total"] or 1
    segmentos = "".join(
        f'<i style="width:{_pct(k["estados"].get(e, 0), t):.2f}%;background:{R.ESTILO_ESTADO[e][1]}" '
        f'title="{_e(e)}: {k["estados"].get(e, 0)}"></i>'
        for e in R.ORDEN_ESTADOS if k["estados"].get(e, 0))
    leyenda = "".join(
        f'<span><span class="cob-dot" style="background:{R.ESTILO_ESTADO[e][1]}"></span>'
        f'{R.ESTILO_ESTADO[e][0]} {_e(e.title())} <b>{k["estados"].get(e, 0)}</b></span>'
        for e in R.ORDEN_ESTADOS if k["estados"].get(e, 0))
    panel_estados = (f'<div class="cob-panel"><h4>Estado de la cartera</h4>'
                     f'<div class="cob-stack">{segmentos}</div><div class="cob-leg">{leyenda}</div></div>')

    avance = R.avance_por_interaccion(dfp)
    efect, no_efect = int(avance["Efectivo"].sum()), int(avance["No efectivo"].sum())
    total_c = efect + no_efect
    panel_contacto = (
        f'<div class="cob-panel"><h4>Contactos efectivos vs no efectivos</h4>'
        f'<div class="cob-stack"><i style="width:{_pct(efect, total_c):.2f}%;background:{COLOR_EFECTIVO}"></i>'
        f'<i style="width:{_pct(no_efect, total_c):.2f}%;background:{COLOR_NO_EFECTIVO}"></i></div>'
        f'<div class="cob-leg"><span><span class="cob-dot" style="background:{COLOR_EFECTIVO}"></span>'
        f'Efectivo <b>{efect}</b> ({_pct(efect, total_c):.0f}%)</span>'
        f'<span><span class="cob-dot" style="background:{COLOR_NO_EFECTIVO}"></span>'
        f'No efectivo <b>{no_efect}</b> ({_pct(no_efect, total_c):.0f}%)</span>'
        f'<span>Total contactos <b>{total_c}</b></span></div></div>')

    filas = "".join(
        f'<div class="cob-row"><span>C{int(r["n"])}</span><div class="t">'
        f'<i style="width:{_pct(r["Efectivo"], t):.2f}%;background:{COLOR_EFECTIVO}"></i>'
        f'<i style="width:{_pct(r["No efectivo"], t):.2f}%;background:{COLOR_NO_EFECTIVO}"></i></div>'
        f'<span class="n">{int(r["Total"])} · {_pct(r["Total"], t):.0f}%</span></div>'
        for r in avance.to_dict("records"))
    panel_avance = (f'<div class="cob-panel"><h4>Avance por contacto (casos que llegaron a cada contacto)</h4>'
                    f'{filas}</div>')
    st.markdown(f'<div class="cob-dash">{panel_estados}{panel_contacto}{panel_avance}</div>',
                unsafe_allow_html=True)


def _flash():
    for tipo, msg in st.session_state.pop("cob_flash", []):
        getattr(st, tipo)(msg)


def _push_flash(tipo, msg):
    st.session_state.setdefault("cob_flash", []).append((tipo, msg))


def _opciones(lista, actual=""):
    opciones = [""] + [x for x in lista if x]
    if actual and actual not in opciones:
        opciones.append(actual)
    return opciones, opciones.index(actual) if actual in opciones else 0


def _form_interaccion(prefijo: str, n: int, base: dict, fila: dict, listas: dict,
                      min_fecha: date, max_fecha: date) -> dict:
    """Campos de una interacción con cascada Tipo → Acción → campos condicionales."""
    hoy = _hoy()
    max_fecha = min(max_fecha, hoy)
    min_fecha = min(min_fecha, max_fecha)
    fecha_ini = R.parse_fecha(base.get("FECHA", "")) or max_fecha
    fecha_ini = min(max(fecha_ini, min_fecha), max_fecha)

    c1, c2, c3 = st.columns(3)
    with c1:
        fecha = st.date_input("📅 Fecha de la gestión", value=fecha_ini, min_value=min_fecha,
                              max_value=max_fecha, format="DD/MM/YYYY", key=f"{prefijo}_fecha")
    with c2:
        op, i = _opciones(listas["horario"], base.get("HORARIO", ""))
        horario = st.selectbox("🕐 Horario", op, index=i, key=f"{prefijo}_horario")
    with c3:
        op, i = _opciones(listas["medio"], base.get("MEDIO", ""))
        medio = st.selectbox("📞 Medio", op, index=i, key=f"{prefijo}_medio")

    c4, c5 = st.columns(2)
    with c4:
        op_tipo = ["", R.EFECTIVO, R.NO_EFECTIVO]
        t_ini = base.get("TIPO CONTACTO", "")
        tipo = st.selectbox("🎯 Tipo de contacto", op_tipo,
                            index=op_tipo.index(t_ini) if t_ini in op_tipo else 0,
                            format_func=lambda x: {"": "— Selecciona —", R.EFECTIVO: "🟦 EFECTIVO",
                                                   R.NO_EFECTIVO: "🟧 NO EFECTIVO"}[x],
                            key=f"{prefijo}_tipo")
    accion = ""
    with c5:
        if tipo:
            op, i = _opciones(R.ACCIONES[tipo], base.get("ACCIÓN", "") if base.get("TIPO CONTACTO") == tipo else "")
            accion = st.selectbox("📝 Resultado / acción", op, index=i, key=f"{prefijo}_accion_{tipo}")
        else:
            st.selectbox("📝 Resultado / acción", ["Primero elige el tipo de contacto"], disabled=True,
                         key=f"{prefijo}_accion_vacio")

    f_comp, motivo = None, ""
    if accion == R.ACCION_COMPROMISO:
        fc_ini = R.parse_fecha(base.get("FECHA COMPROMISO", "")) or fecha
        f_comp = st.date_input("📆 Fecha de compromiso de pago (obligatoria)", value=max(fc_ini, fecha), min_value=fecha,
                               format="DD/MM/YYYY", key=f"{prefijo}_fcomp")
        st.caption("🟣 El caso queda en **Compromiso de pago**. Si vence sin pago, pasa a requerir nuevo contacto.")
    if accion in R.REQUIERE_MOTIVO:
        op, i = _opciones(listas["motivo"], base.get("MOTIVO DE NO PAGO", ""))
        motivo = st.selectbox("❓ Motivo de no pago (obligatorio)", op, index=i, key=f"{prefijo}_motivo")
    if accion == R.ACCION_PAGO:
        st.caption("🟢 **Ya pagó** finaliza el caso automáticamente: no se habilitan más contactos.")
    c6, c7 = st.columns([1, 2])
    with c6:
        hay_reclamo = st.checkbox("📌 ¿Hubo reclamo?", value=R._es_si(base.get("HAY RECLAMO")),
                                   key=f"{prefijo}_reclamo")
    codigo_reclamo = ""
    with c7:
        if hay_reclamo:
            codigo_reclamo = st.text_input("Código de reclamo (opcional, si lo tienes)",
                                           value=base.get("CÓDIGO RECLAMO", ""), max_chars=60,
                                           key=f"{prefijo}_reclamo_cod")

    obs_label = "🗒️ Detalle (obligatorio)" if accion in R.REQUIERE_OBSERVACION else "🗒️ Observación (opcional)"
    observacion = st.text_area(obs_label, value=base.get("OBSERVACIÓN", ""), max_chars=500, height=70,
                               key=f"{prefijo}_obs")
    return {"FECHA": fecha, "HORARIO": horario, "MEDIO": medio, "TIPO CONTACTO": tipo, "ACCIÓN": accion,
            "FECHA COMPROMISO": f_comp, "MOTIVO DE NO PAGO": motivo,
            "HAY RECLAMO": "SI" if hay_reclamo else "", "CÓDIGO RECLAMO": codigo_reclamo,
            "OBSERVACIÓN": observacion}


def _datos_interaccion(fila: dict, n: int) -> dict:
    return {c: _txt(fila, R.col(c, n)) for c in R.CAMPOS}


def _render_pasos(fila: dict, n_reg: int, estado: str):
    pasos = []
    for n in range(1, R.N_INT + 1):
        if n <= n_reg:
            efectivo = _txt(fila, R.col("TIPO CONTACTO", n)) == R.EFECTIVO
            c = COLOR_EFECTIVO if efectivo else COLOR_NO_EFECTIVO
            pasos.append((f"{'✔' if efectivo else '✖'} Int. {n}", c, c, "#fff"))
        elif estado in R.ESTADOS_FINALIZADOS:
            pasos.append((f"Int. {n} · no requerida", "#E5E0EA", "#F8F6FA", "#8F8898"))
        elif n == n_reg + 1:
            pasos.append((f"➜ Int. {n} · siguiente", "#7B1FA2", "#F3E5FA", "#4B0067"))
        else:
            pasos.append((f"🔒 Int. {n}", "#E5E0EA", "#F8F6FA", "#8F8898"))
    st.markdown('<div class="cob-steps">' + "".join(
        f'<div class="cob-step" style="--c:{c};--bg:{bg};--t:{t};">{_e(lbl)}</div>' for lbl, c, bg, t in pasos
    ) + "</div>", unsafe_allow_html=True)


def _render_interacciones(fila: dict, n_reg: int):
    for n in range(1, n_reg + 1):
        d = _datos_interaccion(fila, n)
        color = COLOR_EFECTIVO if d["TIPO CONTACTO"] == R.EFECTIVO else COLOR_NO_EFECTIVO
        extras = []
        if d["FECHA COMPROMISO"]:
            extras.append(f"Compromiso: <b>{_e(d['FECHA COMPROMISO'])}</b>")
        if d["MOTIVO DE NO PAGO"]:
            extras.append(f"Motivo: <b>{_e(d['MOTIVO DE NO PAGO'])}</b>")
        if R._es_si(d.get("HAY RECLAMO")):
            cod = d.get("CÓDIGO RECLAMO") or "sin código"
            extras.append(f'<span class="cob-reclamo">📌 Reclamo: {_e(cod)}</span>')
        if d["OBSERVACIÓN"]:
            extras.append(f"Obs.: {_e(d['OBSERVACIÓN'])}")
        usuario = _txt(fila, R.col_usuario(n)) or "—"
        momento = _txt(fila, R.col_timestamp(n)) or "—"
        st.markdown(
            f'<div class="cob-int" style="--c:{color};"><b>Interacción {n}</b> · {_e(d["FECHA"])} · '
            f'{_e(d["HORARIO"])} · {_e(d["MEDIO"])} · <b>{_e(d["TIPO CONTACTO"])}</b> → <b>{_e(d["ACCIÓN"])}</b>'
            f'{"<br>" + " · ".join(extras) if extras else ""}'
            f'<div class="meta">Registrado por {_e(usuario)} · {_e(momento)}</div></div>',
            unsafe_allow_html=True)


def _ejecutar_guardado(caso, preparar, ctx, mensaje_ok):
    try:
        with st.spinner("Guardando en el Drive…"):
            estado, aviso = _guardar_caso(caso, preparar, ctx)
    except ValidacionError as e:
        for err in e.errores:
            st.error(f"❌ {err}")
        return
    except ConflictoError as e:
        _cargar_casos.clear()
        st.warning(f"⚠️ {e}")
        return
    except gspread.exceptions.APIError as e:
        st.error(f"❌ Google Drive no respondió a tiempo ({e}). No se guardó nada; inténtalo nuevamente.")
        return
    _push_flash("success", f"✅ {mensaje_ok} Estado del caso: {_etiqueta_estado(estado)}.")
    if aviso:
        _push_flash("warning", f"⚠️ {aviso}")
    st.session_state["cob_nonce"] = st.session_state.get("cob_nonce", 0) + 1
    st.rerun()


@st.fragment
def _panel_caso(id_caso: str, ctx: dict):
    headers, df, _ = _cargar_casos()
    sel = df[df[R.COL_ID] == id_caso]
    if sel.empty:
        st.info("El caso seleccionado ya no está disponible. Actualiza la página.")
        return
    caso = sel.iloc[0].to_dict()
    hoy = _hoy()
    n_reg = int(caso["_N"])
    estado = caso["_ESTADO"]
    editable, _ = R.ventana_edicion(_txt(caso, "PERIODO"), hoy, ctx["es_bo"])
    finalizado = estado in R.ESTADOS_FINALIZADOS
    listas = ctx["listas"]
    nonce = st.session_state.get("cob_nonce", 0)
    pref = f"cob_{id_caso}_{nonce}"

    st.markdown('<div class="cob-sec">✏️ Gestión del caso</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="cob-card"><div class="cob-grid">'
        f'<div><div class="k">Cliente</div><div class="x">{_e(caso.get("nombre_cliente"))}</div></div>'
        f'<div><div class="k">Código</div><div class="x">{_e(caso.get("cod_cliente"))}</div></div>'
        f'<div><div class="k">Celular</div><div class="x">{_e(caso.get("celular_cliente"))}</div></div>'
        f'<div><div class="k">Estado de pago</div><div class="x">{_e(caso.get("Estado_Pago"))}</div></div>'
        f'<div><div class="k">Partner</div><div class="x">{_e(caso.get("razon_social"))}</div></div>'
        f'<div><div class="k">Estado del caso</div><div class="x">{_pill(estado)}</div></div>'
        f'<div><div class="k">Interacciones</div><div class="x">{n_reg} de {R.N_INT}</div></div>'
        + (f'<div><div class="k">Reclamos</div><div class="x">'
           + " ".join(f'<span class="cob-reclamo">📌 {_e(c)}</span>' for c in caso.get("_RECLAMOS", []))
           + '</div></div>' if caso.get("_RECLAMOS") else "")
        + '</div></div>', unsafe_allow_html=True)
    if finalizado and _txt(caso, R.COL_MOTIVO_CIERRE):
        st.caption(f"🏁 Cerrado por {_txt(caso, R.COL_USUARIO_CIERRE) or '—'} el "
                   f"{_txt(caso, R.COL_FECHA_CIERRE) or '—'} · Motivo: {_txt(caso, R.COL_MOTIVO_CIERRE)}"
                   f"{' · ' + _txt(caso, R.COL_DETALLE_CIERRE) if _txt(caso, R.COL_DETALLE_CIERRE) else ''}")

    _render_pasos(caso, n_reg, estado)
    _render_interacciones(caso, n_reg)

    if not editable:
        st.info("🔒 Este caso está en solo lectura fuera de la ventana de registro.")
        return

    if not finalizado and n_reg < R.N_INT:
        n = n_reg + 1
        st.markdown(f"#### ➜ Registrar interacción {n} de {R.N_INT}")
        min_f = R.parse_fecha(_txt(caso, R.col("FECHA", n - 1))) if n > 1 else None
        min_f = min_f or R.inicio_periodo(_txt(caso, "PERIODO")) or date(2024, 1, 1)
        datos = _form_interaccion(f"{pref}_n{n}", n, {}, caso, listas, min_f, hoy)
        if st.button(f"💾 Registrar interacción {n}", type="primary", use_container_width=True,
                     key=f"{pref}_guardar"):
            errores = R.validar_interaccion(datos, n, caso, hoy)
            if errores:
                for err in errores:
                    st.error(f"❌ {err}")
            else:
                def preparar(actual, datos=datos, n=n):
                    errs = R.validar_interaccion(datos, n, actual, _hoy())
                    if errs:
                        raise ValidacionError(errs)
                    cambios = R.valores_interaccion(datos, n, ctx["usuario"], _ts())
                    if datos["ACCIÓN"] == R.ACCION_PAGO:
                        cambios.update({R.COL_MOTIVO_CIERRE: f"{R.ACCION_PAGO} (interacción {n})",
                                        R.COL_DETALLE_CIERRE: "", R.COL_USUARIO_CIERRE: ctx["usuario"],
                                        R.COL_FECHA_CIERRE: _ts()})
                    return cambios, "REGISTRO_INTERACCION", n
                _ejecutar_guardado(caso, preparar, ctx, f"Interacción {n} registrada.")
    elif not finalizado:
        st.warning(f"🟡 El caso completó las {R.N_INT} interacciones. Debe finalizarse indicando el motivo de cierre.")

    if not finalizado:
        with st.expander("🏁 Finalizar caso", expanded=n_reg >= R.N_INT):
            st.caption("Cierra el flujo cuando ya no corresponde seguir gestionando. Un caso finalizado queda bloqueado.")
            motivo = st.selectbox("Motivo de cierre", [""] + R.MOTIVOS_CIERRE, key=f"{pref}_cierre_motivo")
            detalle = st.text_input("Detalle del cierre", max_chars=300, key=f"{pref}_cierre_det")
            confirma = st.checkbox("Confirmo que el caso debe finalizarse", key=f"{pref}_cierre_ok")
            if st.button("🏁 Finalizar caso", key=f"{pref}_cierre_btn", disabled=not confirma):
                if not motivo:
                    st.error("❌ Selecciona el motivo de cierre.")
                elif motivo == "Otro" and not detalle.strip():
                    st.error("❌ Detalla el motivo de cierre.")
                else:
                    def preparar(actual, motivo=motivo, detalle=detalle):
                        if R.estado_caso(actual, _hoy()) in R.ESTADOS_FINALIZADOS:
                            raise ValidacionError(["El caso ya fue finalizado."])
                        return ({R.COL_MOTIVO_CIERRE: motivo, R.COL_DETALLE_CIERRE: detalle.strip(),
                                 R.COL_USUARIO_CIERRE: ctx["usuario"], R.COL_FECHA_CIERRE: _ts()},
                                "FINALIZAR_CASO", None)
                    _ejecutar_guardado(caso, preparar, ctx, "Caso finalizado.")

    if ctx["es_bo"]:
        _herramientas_bo(caso, n_reg, ctx, listas, pref)


def _herramientas_bo(caso: dict, n_reg: int, ctx: dict, listas: dict, pref: str):
    with st.expander("🛠️ Corrección backoffice"):
        st.caption("Solo backoffice. Cada corrección conserva al gestor original y queda registrada en el historial.")
        if _txt(caso, R.COL_MOTIVO_CIERRE):
            if st.button("🔓 Reabrir caso", key=f"{pref}_reabrir"):
                def preparar(actual):
                    if not actual.get(R.COL_MOTIVO_CIERRE):
                        raise ValidacionError(["El caso no está cerrado."])
                    return ({c: "" for c in [R.COL_MOTIVO_CIERRE, R.COL_DETALLE_CIERRE,
                                              R.COL_USUARIO_CIERRE, R.COL_FECHA_CIERRE]},
                            "REABRIR_CASO", None)
                _ejecutar_guardado(caso, preparar, ctx, "Caso reabierto.")
        if n_reg == 0:
            st.caption("El caso no tiene interacciones para corregir.")
            return
        k = st.selectbox("Interacción a corregir", list(range(1, n_reg + 1)), index=n_reg - 1,
                         format_func=lambda x: f"Interacción {x}", key=f"{pref}_corr_n")
        hoy = _hoy()
        min_f = R.parse_fecha(_txt(caso, R.col("FECHA", k - 1))) if k > 1 else None
        min_f = min_f or R.inicio_periodo(_txt(caso, "PERIODO")) or date(2024, 1, 1)
        max_f = (R.parse_fecha(_txt(caso, R.col("FECHA", k + 1))) if k < n_reg else None) or hoy
        datos = _form_interaccion(f"{pref}_corr{k}", k, _datos_interaccion(caso, k), caso, listas, min_f, max_f)
        if st.button(f"💾 Guardar corrección de la interacción {k}", key=f"{pref}_corr_btn"):
            errores = R.validar_interaccion(datos, k, caso, hoy, es_correccion=True)
            if errores:
                for err in errores:
                    st.error(f"❌ {err}")
                return

            def preparar(actual, datos=datos, k=k):
                errs = R.validar_interaccion(datos, k, actual, _hoy(), es_correccion=True)
                if errs:
                    raise ValidacionError(errs)
                cambios = R.valores_interaccion(datos, k, "", "")
                cambios.pop(R.col_usuario(k))
                cambios.pop(R.col_timestamp(k))
                motivo_cierre = actual.get(R.COL_MOTIVO_CIERRE, "")
                if datos["ACCIÓN"] == R.ACCION_PAGO and not motivo_cierre:
                    cambios.update({R.COL_MOTIVO_CIERRE: f"{R.ACCION_PAGO} (interacción {k})",
                                    R.COL_USUARIO_CIERRE: ctx["usuario"], R.COL_FECHA_CIERRE: _ts()})
                elif datos["ACCIÓN"] != R.ACCION_PAGO and motivo_cierre.startswith(R.ACCION_PAGO):
                    cambios.update({c: "" for c in [R.COL_MOTIVO_CIERRE, R.COL_DETALLE_CIERRE,
                                                     R.COL_USUARIO_CIERRE, R.COL_FECHA_CIERRE]})
                return cambios, "CORRECCION_INTERACCION", k
            _ejecutar_guardado(caso, preparar, ctx, f"Interacción {k} corregida.")


COLUMNAS_FIJAS_TABLA = ["Estado", "Avance", "Siguiente", "Código", "Cliente", "Celular", "Estado pago", "Partner"]


def _siguiente(estado: str, n: int, motivo_cierre: str = "") -> str:
    if estado == R.E_PAGADO:
        if "validado en servidor" in motivo_cierre:
            return "🔒 Pagado (servidor)"
        return "🏁 Pagó · cerrado"
    if estado in R.ESTADOS_FINALIZADOS:
        return "🏁 Cerrado"
    if n >= R.N_INT:
        return "🟡 Finalizar caso"
    return f"➜ Completar C{n + 1}"
COLUMNAS_EDITABLES_TABLA = [R.COL_RESP_BO] + [R.col(c, n) for n in range(1, R.N_INT + 1) for c in R.CAMPOS]
ETIQUETAS_CAMPO = {"FECHA": "Fecha", "HORARIO": "Horario", "MEDIO": "Medio", "TIPO CONTACTO": "Tipo",
                   "ACCIÓN": "Resultado", "FECHA COMPROMISO": "F. compromiso",
                   "MOTIVO DE NO PAGO": "Motivo no pago", "HAY RECLAMO": "¿Reclamo?",
                   "CÓDIGO RECLAMO": "Cód. reclamo", "OBSERVACIÓN": "Observación"}
AYUDA_CAMPO = {
    "TIPO CONTACTO": "Elige primero el tipo: define qué resultados son válidos.",
    "ACCIÓN": (f"EFECTIVO: {', '.join(R.ACCIONES[R.EFECTIVO])}. "
               f"NO EFECTIVO: {', '.join(R.ACCIONES[R.NO_EFECTIVO])}. 'Ya pagó' cierra el caso."),
    "FECHA COMPROMISO": f"Solo para '{R.ACCION_COMPROMISO}' (obligatoria). En otro resultado se descarta.",
    "MOTIVO DE NO PAGO": f"Solo para '{R.ACCION_NO_PAGARA}' (obligatorio). En otro resultado se descarta.",
    "HAY RECLAMO": "Nunca es obligatorio. Marca si el cliente puso un reclamo en este contacto.",
    "CÓDIGO RECLAMO": "Opcional, solo si hubo reclamo y ya tienes el código. Si no hay reclamo, se descarta.",
    "OBSERVACIÓN": "Obligatoria para 'Otros: detallar'.",
}


def _tabla_contactos(base: pd.DataFrame) -> pd.DataFrame:
    """Una fila por cliente y, hacia la derecha, los contactos 1 a 6 (igual que el Drive)."""
    g = pd.DataFrame({
        "Estado": base["_ESTADO"].map(_etiqueta_estado).values,
        "Avance": base["_N"].astype(int).values,
        "Siguiente": [_siguiente(e, int(n), m) for e, n, m in
                      zip(base["_ESTADO"], base["_N"], base[R.COL_MOTIVO_CIERRE])],
        "Código": base["cod_cliente"].values,
        "Cliente": base["nombre_cliente"].values,
        "Celular": base["celular_cliente"].values,
        "Estado pago": base["Estado_Pago"].values,
        "Partner": base["razon_social"].values,
        R.COL_RESP_BO: base[R.COL_RESP_BO].values,
    })
    for n in range(1, R.N_INT + 1):
        for c in R.CAMPOS:
            serie = base[R.col(c, n)]
            if c in R.CAMPOS_FECHA:
                serie = pd.to_datetime(serie.map(R.parse_fecha), errors="coerce")
            g[R.col(c, n)] = serie.values
    return g


def _config_tabla(base: pd.DataFrame, listas: dict, responsables: list[str]) -> dict:
    def opciones(lista, campo):
        existentes = {v for n in range(1, R.N_INT + 1) for v in base[R.col(campo, n)].unique() if v}
        return list(dict.fromkeys(list(lista) + sorted(existentes - set(lista))))

    # Los resultados de versiones anteriores solo aparecen si ya existen en el Drive (por opciones()).
    acciones = R.ACCIONES[R.EFECTIVO] + R.ACCIONES[R.NO_EFECTIVO]
    opciones_campo = {"HORARIO": opciones(listas["horario"], "HORARIO"),
                      "MEDIO": opciones(listas["medio"], "MEDIO"),
                      "TIPO CONTACTO": opciones([R.EFECTIVO, R.NO_EFECTIVO], "TIPO CONTACTO"),
                      "ACCIÓN": opciones(acciones, "ACCIÓN"),
                      "MOTIVO DE NO PAGO": opciones(listas["motivo"], "MOTIVO DE NO PAGO")}
    cfg = {
        "Estado": st.column_config.TextColumn("Estado", width="medium"),
        "Siguiente": st.column_config.TextColumn("Siguiente paso", width="small"),
        "Avance": st.column_config.ProgressColumn("Avance", min_value=0, max_value=R.N_INT, format=f"%d/{R.N_INT}"),
        "Cliente": st.column_config.TextColumn("Cliente", width="medium"),
        R.COL_RESP_BO: st.column_config.SelectboxColumn("Responsable BO", options=responsables),
    }
    for n in range(1, R.N_INT + 1):
        for c in R.CAMPOS:
            etiqueta = f"C{n} · {ETIQUETAS_CAMPO[c]}"
            ayuda = AYUDA_CAMPO.get(c)
            if c in R.CAMPOS_FECHA:
                cfg[R.col(c, n)] = st.column_config.DateColumn(etiqueta, format="DD/MM/YYYY", help=ayuda)
            elif c in ("OBSERVACIÓN", "CÓDIGO RECLAMO"):
                limite = 500 if c == "OBSERVACIÓN" else 60
                cfg[R.col(c, n)] = st.column_config.TextColumn(etiqueta, max_chars=limite, help=ayuda)
            elif c == "HAY RECLAMO":
                cfg[R.col(c, n)] = st.column_config.SelectboxColumn(etiqueta, options=["", "SI"],
                                                                    width="small", help=ayuda)
            else:
                cfg[R.col(c, n)] = st.column_config.SelectboxColumn(
                    etiqueta, options=opciones_campo[c], width="medium" if c == "ACCIÓN" else "small", help=ayuda)
    return cfg


def _revisar_ediciones(base: pd.DataFrame, editado: pd.DataFrame, pendientes: dict, ctx: dict,
                       cols_visibles: list[str]) -> dict:
    """Revisión en vivo (sin tocar el Drive): {pos: (etiqueta, errores, avisos)} por fila editada.
    `cols_visibles` son las columnas editables que están en pantalla (según el selector de
    columnas); las que no están visibles se toman del dato original, nunca como vacías."""
    hoy, revision = _hoy(), {}
    for pos in sorted(int(p) for p in pendientes):
        original = base.iloc[pos].to_dict()
        fila = editado.iloc[pos]
        nuevo = {**original, **{c: fila[c] for c in cols_visibles}}
        _, _, errores = R.procesar_edicion(original, nuevo, original, ctx["es_bo"], ctx["usuario"], "", hoy)
        avisos = []
        for n in range(1, R.N_INT + 1):
            datos = {c: R.valor_campo(c, nuevo.get(R.col(c, n))) for c in R.CAMPOS}
            if any(datos[c] != R.valor_campo(c, original.get(R.col(c, n))) for c in R.CAMPOS):
                avisos += [f"Contacto {n}: {a}" for a in R.limpiezas_aplicadas(datos)]
        etiqueta = f"{original.get('cod_cliente', '')} · {original.get('nombre_cliente', '')}"
        revision[pos] = (etiqueta, errores, avisos)
    return revision


def _tab_gestion(dfp: pd.DataFrame, ctx: dict, periodo: str, editable: bool):
    k = R.kpis(dfp)
    _render_kpis(k)
    _render_dashboard(dfp, k)

    f1, f2, f3 = st.columns([2, 2, 1.4])
    with f1:
        buscar = st.text_input("🔎 Buscar cliente", placeholder="Nombre, celular o código",
                               key="cob_buscar").strip().lower()
    with f2:
        estados = st.multiselect("Estado del caso", R.ORDEN_ESTADOS, format_func=_etiqueta_estado,
                                 placeholder="Todos los estados", key="cob_estados")
    with f3:
        responsables = sorted(x for x in dfp[R.COL_RESP_BO].unique() if x)
        resp = st.selectbox("Responsable BO", ["TODOS"] + responsables, key="cob_resp")

    dfv = dfp
    if buscar:
        texto = (dfv["nombre_cliente"].str.lower() + " " + dfv["celular_cliente"] + " "
                 + dfv["cod_cliente"].str.lower())
        dfv = dfv[texto.str.contains(buscar, regex=False, na=False)]
    if estados:
        dfv = dfv[dfv["_ESTADO"].isin(estados)]
    if resp != "TODOS":
        dfv = dfv[dfv[R.COL_RESP_BO] == resp]
    orden = {e: i for i, e in enumerate([R.E_COMPROMISO_VENCIDO, R.E_RECONTACTAR, R.E_PENDIENTE,
                                         R.E_PEND_CIERRE, R.E_EN_PROCESO, R.E_COMPROMISO,
                                         R.E_PAGADO, R.E_SIN_EXITO])}
    dfv = dfv.assign(_ORD=dfv["_ESTADO"].map(orden)).sort_values(["_ORD", "nombre_cliente"])

    if dfv.empty:
        st.info("No hay casos con esos filtros.")
        return
    total = len(dfv)
    if total > LIMITE_FILAS_TABLA:
        dfv = dfv.head(LIMITE_FILAS_TABLA)
        st.warning(f"Se muestran los {LIMITE_FILAS_TABLA} casos más prioritarios de {total}. "
                   "Usa los filtros para ver el resto.")

    # La tabla trabaja sobre una foto fija hasta guardar/actualizar: así las ediciones nunca se
    # corren de fila aunque otro usuario cambie el orden de los casos mientras tanto.
    nonce = st.session_state.get("cob_nonce", 0)
    firma = abs(hash((periodo, ctx.get("partner"), buscar, tuple(estados), resp, nonce)))
    clave_foto = f"cob_foto_{firma}"
    if clave_foto not in st.session_state:
        for k in [k for k in st.session_state if str(k).startswith("cob_foto_")]:
            del st.session_state[k]
        st.session_state[clave_foto] = (dfv.reset_index(drop=True), _ahora().strftime("%H:%M:%S"))
    base, hora_foto = st.session_state[clave_foto]

    if editable:
        st.caption(f"**{len(base)}** de {len(dfp)} casos, ordenados por prioridad. Completa los contactos "
                   "hacia la derecha (C1 → C6) con las listas desplegables y pulsa **Guardar cambios**. "
                   f"Vista tomada a las {hora_foto}.")
    else:
        st.caption(f"**{len(base)}** de {len(dfp)} casos · 🔒 solo lectura.")

    cc1, cc2 = st.columns([1, 2])
    with cc1:
        contactos_mostrar = st.multiselect(
            "🔢 Contactos a mostrar", list(range(1, R.N_INT + 1)), default=list(range(1, R.N_INT + 1)),
            format_func=lambda n: f"C{n}", key=f"cob_cols_n_{firma}")
    with cc2:
        campos_mostrar = st.multiselect(
            "📋 Campos a mostrar", R.CAMPOS,
            default=["FECHA", "TIPO CONTACTO", "ACCIÓN", "FECHA COMPROMISO", "HAY RECLAMO"],
            format_func=lambda c: ETIQUETAS_CAMPO.get(c, c), key=f"cob_cols_c_{firma}")
    st.caption("Esto solo cambia qué se ve en la tabla — los contactos y campos que no eliges "
               "seguir viendo no se tocan ni se pierden al guardar.")

    razones = {_nr(r) for r in base["razon_social"].unique()}
    responsables = sorted({b for r in razones for b in ctx["listas"]["bo"].get(r, [])}
                          | {x for x in base[R.COL_RESP_BO].unique() if x})
    columnas_grid = [R.col(c, n) for n in contactos_mostrar for c in campos_mostrar]
    columnas_tabla = COLUMNAS_FIJAS_TABLA + [R.COL_RESP_BO] + columnas_grid
    tabla_completa = _tabla_contactos(base)
    cfg_completo = _config_tabla(base, ctx["listas"], responsables)
    clave_editor = f"cob_tabla_{firma}"
    editado = st.data_editor(
        tabla_completa[columnas_tabla], key=clave_editor, hide_index=True, use_container_width=True, height=460,
        num_rows="fixed", disabled=True if not editable else COLUMNAS_FIJAS_TABLA,
        column_config={k: v for k, v in cfg_completo.items() if k in columnas_tabla},
    )
    # editado solo trae las columnas visibles: para no perder ni pisar los contactos/campos
    # ocultos, cada fila a guardar se construye sobre el dato original y solo se superponen
    # las columnas que de verdad están en pantalla.
    cols_visibles_editables = [c for c in COLUMNAS_EDITABLES_TABLA if c in editado.columns]

    if editable:
        pendientes = st.session_state.get(clave_editor, {}).get("edited_rows", {})
        revision = _revisar_ediciones(base, editado, pendientes, ctx, cols_visibles_editables) if pendientes else {}
        con_error = {p: r for p, r in revision.items() if r[1]}
        if revision:
            listos = len(revision) - len(con_error)
            with st.container(border=True):
                st.markdown(f"**Revisión antes de guardar** · ✅ {listos} listo(s) · "
                            f"{'❌ ' + str(len(con_error)) + ' por corregir' if con_error else 'sin observaciones'}")
                for etiqueta, errores, avisos in revision.values():
                    for err in errores:
                        st.error(f"❌ {etiqueta} — {err}")
                    for av in avisos:
                        st.info(f"🧹 {etiqueta} — {av}")
                if con_error:
                    st.caption("Las filas con ❌ no se guardan hasta corregirlas; las demás sí.")
        b1, b2 = st.columns([3, 1])
        guardar = b1.button(f"💾 Guardar cambios ({len(pendientes)} caso(s) editado(s))", type="primary",
                            disabled=not pendientes, use_container_width=True, key=f"cob_guardar_{firma}")
        if b2.button("↩️ Descartar cambios", disabled=not pendientes, use_container_width=True,
                     key=f"cob_descartar_{firma}"):
            st.session_state["cob_nonce"] = nonce + 1
            st.rerun()
        if guardar:
            ediciones = []
            for pos in sorted(int(p) for p in pendientes):
                original = base.iloc[pos].to_dict()
                fila_editada = editado.iloc[pos]
                editado_fila = {**original, **{c: fila_editada[c] for c in cols_visibles_editables}}
                ediciones.append((original, editado_fila))
            try:
                with st.spinner("Validando y guardando en el Drive…"):
                    guardadas, errores, aviso = _guardar_lote(ediciones, ctx)
            except gspread.exceptions.APIError as e:
                st.error(f"❌ Google Drive no respondió a tiempo ({e}). No se guardó nada; inténtalo nuevamente.")
                return
            if guardadas:
                _push_flash("success", f"✅ {guardadas} caso(s) guardado(s) en el Drive.")
                for err in errores:
                    _push_flash("error", f"❌ No se guardó — {err}")
                if aviso:
                    _push_flash("warning", f"⚠️ {aviso}")
                st.session_state["cob_nonce"] = nonce + 1
                st.rerun()
            for err in errores:
                st.error(f"❌ No se guardó — {err}")

    st.markdown('<div class="cob-sec">🔍 Detalle del caso</div>', unsafe_allow_html=True)
    etiquetas = {i: f"{c} · {nm} · {_etiqueta_estado(e)}"
                 for i, c, nm, e in zip(base[R.COL_ID], base["cod_cliente"], base["nombre_cliente"], base["_ESTADO"])}
    elegido = st.selectbox("Ver historial, registrar con ayuda guiada o finalizar un caso",
                           [""] + list(etiquetas), format_func=lambda i: etiquetas.get(i, "— Selecciona un caso —"),
                           key=f"cob_detalle_{firma}")
    if elegido:
        _panel_caso(elegido, ctx)


def _barras(df, x, y, titulo, color=None, escala=None, horizontal=False, alto=260):
    enc_x = alt.X(f"{x}:Q", title=None) if horizontal else alt.X(f"{x}:N", title=None, sort=None)
    enc_y = alt.Y(f"{y}:N", title=None, sort="-x") if horizontal else alt.Y(f"{y}:Q", title=None)
    encode = {"x": enc_x, "y": enc_y, "tooltip": list(df.columns)}
    if color:
        encode["color"] = alt.Color(f"{color}:N", title=None, scale=escala,
                                    legend=alt.Legend(orient="top"))
    else:
        encode["color"] = alt.value(COLOR_EFECTIVO)
    chart = alt.Chart(df, title=titulo).mark_bar().encode(**encode).properties(height=alto)
    st.altair_chart(chart, use_container_width=True)


def _tab_indicadores(dfp: pd.DataFrame, dfa: pd.DataFrame, ctx: dict):
    if dfp.empty:
        st.info("Sin casos en el periodo.")
        return
    k = R.kpis(dfp)
    _render_kpis(k)
    _render_dashboard(dfp, k)

    cols_cliente = {"cod_cliente": "Código", "nombre_cliente": "Cliente", "celular_cliente": "Celular",
                    "razon_social": "Partner", R.COL_RESP_BO: "Responsable BO"}
    s1, s2 = st.columns(2)
    with s1:
        st.markdown('<div class="cob-sec">🟣 Seguimiento de compromisos de pago</div>', unsafe_allow_html=True)
        comp = dfp[dfp["_ESTADO"].isin([R.E_COMPROMISO, R.E_COMPROMISO_VENCIDO])]
        if comp.empty:
            st.caption("Sin compromisos de pago abiertos.")
        else:
            hoy = _hoy()
            tabla = comp[list(cols_cliente)].rename(columns=cols_cliente)
            fechas = comp["_COMPROMISO"].map(R.parse_fecha)
            tabla.insert(0, "Situación", comp["_ESTADO"].map(_etiqueta_estado).values)
            tabla.insert(1, "Fecha compromiso", pd.to_datetime(fechas, errors="coerce").values)
            tabla.insert(2, "Días", [(f - hoy).days if f else None for f in fechas])
            st.dataframe(tabla.sort_values("Fecha compromiso"), hide_index=True, use_container_width=True,
                         height=min(320, 38 + 35 * len(tabla)),
                         column_config={"Fecha compromiso": st.column_config.DateColumn(format="DD/MM/YYYY"),
                                        "Días": st.column_config.NumberColumn(
                                            help="Días para el compromiso (negativo = vencido)")})
    with s2:
        st.markdown('<div class="cob-sec">🟢 Clientes que ya pagaron</div>', unsafe_allow_html=True)
        pag = dfp[dfp["_ESTADO"] == R.E_PAGADO]
        if pag.empty:
            st.caption("Aún no hay clientes con pago registrado.")
        else:
            tabla = pag[list(cols_cliente)].rename(columns=cols_cliente)
            tabla.insert(0, "Pagó en", [f"Contacto {int(n)}" if n else "—" for n in pag["_N"]])
            tabla.insert(1, "Fecha", pag["_ULT_FECHA"].values)
            st.dataframe(tabla, hide_index=True, use_container_width=True,
                         height=min(320, 38 + 35 * len(tabla)))

    c1, c2 = st.columns(2)
    with c1:
        avance = R.avance_por_interaccion(dfp)
        largo = avance.melt(id_vars=["Interacción"], value_vars=["Efectivo", "No efectivo"],
                            var_name="Tipo", value_name="Casos")
        _barras(largo, "Interacción", "Casos", "Avance por interacción", color="Tipo",
                escala=alt.Scale(domain=["Efectivo", "No efectivo"], range=[COLOR_EFECTIVO, COLOR_NO_EFECTIVO]))
    with c2:
        est = pd.DataFrame([{"Estado": _etiqueta_estado(e), "Casos": k["estados"].get(e, 0), "_e": e}
                            for e in R.ORDEN_ESTADOS])
        chart = alt.Chart(est, title="Casos por estado").mark_bar().encode(
            x=alt.X("Casos:Q", title=None),
            y=alt.Y("Estado:N", title=None, sort=None),
            color=alt.Color("_e:N", legend=None, scale=alt.Scale(
                domain=R.ORDEN_ESTADOS, range=[R.ESTILO_ESTADO[e][1] for e in R.ORDEN_ESTADOS])),
            tooltip=["Estado", "Casos"]).properties(height=260)
        st.altair_chart(chart, use_container_width=True)

    dist = R.distribucion_acciones(dfp)
    if not dist.empty:
        dist = dist.assign(Tipo=dist["Tipo"].replace({R.EFECTIVO: "Efectivo", R.NO_EFECTIVO: "No efectivo"}))
        _barras(dist, "Casos", "Acción", "Distribución por tipología y resultado (todas las interacciones)",
                color="Tipo", horizontal=True, alto=max(220, 26 * len(dist)),
                escala=alt.Scale(domain=["Efectivo", "No efectivo", "Sin tipo"],
                                 range=[COLOR_EFECTIVO, COLOR_NO_EFECTIVO, "#898781"]))

    evo = R.evolucion_mensual(dfa)
    if not evo.empty:
        c3, c4 = st.columns(2)
        with c3:
            largo = evo.melt(id_vars=["Periodo"], value_vars=["% Avance", "% Contactabilidad", "% Recupero"],
                             var_name="Indicador", value_name="%")
            chart = alt.Chart(largo, title="Evolución mensual (%)").mark_line(point=True, strokeWidth=2).encode(
                x=alt.X("Periodo:N", title=None), y=alt.Y("%:Q", title=None, scale=alt.Scale(domain=[0, 100])),
                color=alt.Color("Indicador:N", title=None, legend=alt.Legend(orient="top"),
                                scale=alt.Scale(range=["#2a78d6", "#eb6834", "#1baf7a"])),
                tooltip=["Periodo", "Indicador", "%"]).properties(height=260)
            st.altair_chart(chart, use_container_width=True)
        with c4:
            _barras(evo[["Periodo", "Casos", "Gestionados", "Pagados"]], "Periodo", "Casos",
                    "Casos por periodo")
        st.dataframe(evo, hide_index=True, use_container_width=True)

    por_partner = ctx["es_bo"] and not ctx.get("partner")
    agrupador, etiqueta = ("razon_social", "Partner") if por_partner else (R.COL_RESP_BO, "Responsable BO")
    titulo = f"Resultados por {etiqueta.lower() if por_partner else etiqueta}"
    filas = []
    for clave, sub in dfp.groupby(agrupador):
        kk = R.kpis(sub)
        filas.append({etiqueta: clave or "(sin asignar)", "Casos": kk["total"],
                      "Gestionados": kk["gestionados"], "% Avance": round(kk["pct_avance"], 1),
                      "% Contactabilidad": round(kk["pct_contactabilidad"], 1),
                      "Recontactar": kk["recontactar"], "Pendientes de cierre": kk["pend_cierre"],
                      "Pagaron": kk["pagados"], "Finalizados": kk["finalizados"]})
    if filas:
        st.markdown(f"**{titulo}**")
        st.dataframe(pd.DataFrame(filas).sort_values("Casos", ascending=False), hide_index=True,
                     use_container_width=True)

    if ctx["es_bo"]:
        _render_vintage(dfp)


def _render_vintage(dfp: pd.DataFrame):
    st.markdown('<div class="cob-sec">📊 Por vintage (VN1–VN6), por dealer y vendedor</div>',
               unsafe_allow_html=True)
    st.caption("VN1 es el periodo más reciente ya cerrado según el corte real de facturación "
               "(tb_cierre_facturacion, no un día fijo del mes), VN2 el anterior, y así hasta VN6. "
               "\"Vendedor\" es quien activó la venta (Reporting), no quien gestiona el caso en Cobranza.")
    df_rep, aviso_rep = PR.leer_base_vintage()
    cierres, aviso_cierres = PR.leer_cierres_facturacion()
    if aviso_rep or aviso_cierres:
        st.info(f"🛰️ Vintage no disponible: {aviso_rep or aviso_cierres}")
        return
    metricas = V.calcular_metricas_vintage(df_rep, dfp, cierres, _hoy())
    if metricas.empty:
        st.caption("Sin activaciones que caigan dentro de VN1–VN6 todavía.")
        return
    metrica = st.selectbox("📊 Métrica", list(V.METRICAS), format_func=lambda k: V.METRICAS[k],
                           key="cob_vn_metrica")
    piv = V.tabla_pivote(metricas, metrica)
    fmt = "{:.1f}" if metrica == "prom_contactos" else "{:.1f}%"
    estilo = piv.style.format(fmt, na_rep="—")
    try:
        estilo = estilo.background_gradient(
            cmap="Purples", axis=None, vmin=0, vmax=piv.max().max() if piv.notna().any().any() else 1)
    except ImportError:
        pass  # sin matplotlib instalado: se ve la tabla igual, solo sin el degradado de color.
    st.dataframe(estilo, use_container_width=True)
    st.caption("VN5/VN6 salen vacíos (—) hasta que haya suficiente historia en Reporting para esos periodos.")

    st.markdown("**🏆 Ranking de vendedores por % pagado**")
    st.caption("Mismo origen que la tabla de arriba: suma todos los VN de este vendedor (respeta el "
               "ciclo real de facturación) — no es un cálculo aparte ni otra fuente de datos.")
    ranking = V.ranking_vendedores(metricas)
    st.dataframe(
        ranking.rename(columns={"razon_social": "Dealer", "vendedor": "Vendedor",
                                "n_casos": "Casos (VN1–VN4)", "pagado": "% Pagado"}),
        hide_index=True, use_container_width=True,
        column_config={"% Pagado": st.column_config.ProgressColumn("% Pagado", min_value=0, max_value=100,
                                                                    format="%.1f%%")},
    )


def _df_exportable(df: pd.DataFrame) -> pd.DataFrame:
    base = df.drop(columns=[c for c in df.columns if c.startswith("_")], errors="ignore").copy()
    base.insert(0, "ESTADO ACTUAL", df["_ESTADO"].values)
    base.insert(1, "INTERACCIONES", df["_N"].values)
    return base


@st.cache_data(ttl=TTL_CASOS, max_entries=8, show_spinner=False)
def _excel(clave: tuple, _df: pd.DataFrame, _resumen: pd.DataFrame) -> bytes:
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        _df.to_excel(writer, sheet_name="Casos", index=False)
        if not _resumen.empty:
            _resumen.to_excel(writer, sheet_name="Resumen mensual", index=False)
        for hoja in writer.sheets.values():
            hoja.freeze_panes = "A2"
            for columna in hoja.columns:
                ancho = max(len(str(c.value or "")) for c in columna[:200])
                hoja.column_dimensions[columna[0].column_letter].width = min(max(10, ancho + 2), 45)
    return buffer.getvalue()


def _tab_descargas(dfp: pd.DataFrame, dfa: pd.DataFrame, ctx: dict, periodo: str, stamp: str):
    alcance = ctx.get("partner") or ("todos los partners" if ctx["es_bo"] else ctx["razon"])
    st.caption(f"Las descargas respetan tu alcance ({alcance}) y los datos leídos a las {stamp}.")
    xmime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    opciones = {
        "p": (f"Periodo {periodo} ({len(dfp)} casos)", dfp, f"cobranza_{periodo}.xlsx", (periodo, alcance)),
        "a": (f"Todos los periodos ({len(dfa)} casos)", dfa, "cobranza_historico.xlsx", (alcance,)),
    }
    for col_ui, (tipo, (etiqueta, datos_df, archivo, clave)) in zip(st.columns(2), opciones.items()):
        with col_ui:
            listo = st.session_state.get(f"cob_xls_{tipo}") == (clave, stamp)
            if not listo:
                if st.button(f"📦 Preparar Excel · {etiqueta}", use_container_width=True, key=f"cob_prep_{tipo}"):
                    st.session_state[f"cob_xls_{tipo}"] = (clave, stamp)
                    st.rerun()
                continue
            with st.spinner("Generando Excel…"):
                contenido = _excel((tipo, clave, stamp), _df_exportable(datos_df), R.evolucion_mensual(datos_df))
            st.download_button(f"⬇️ Descargar · {etiqueta}", data=contenido, file_name=archivo, mime=xmime,
                               use_container_width=True, type="primary", key=f"cob_dl_{tipo}")

    st.markdown('<div class="cob-sec">🕓 Historial de modificaciones</div>', unsafe_allow_html=True)
    if not st.session_state.get("cob_ver_historial"):
        if st.button("Ver historial del periodo", key="cob_btn_hist"):
            st.session_state["cob_ver_historial"] = True
            st.rerun()
        return
    try:
        hist = _cargar_historial()
    except Exception as e:
        st.error(f"❌ No se pudo leer el historial: {e}")
        return
    hist = hist[hist["PERIODO"].astype(str) == str(periodo)]
    if not ctx["es_bo"]:
        hist = hist[hist["RAZON_SOCIAL"].map(_nr) == _nr(ctx["razon"])]
    elif ctx.get("partner"):
        hist = hist[hist["RAZON_SOCIAL"].map(_nr) == _nr(ctx["partner"])]
    hist = hist.sort_values("TIMESTAMP", ascending=False)
    if hist.empty:
        st.info("Sin modificaciones registradas en este periodo.")
        return
    st.dataframe(hist, hide_index=True, use_container_width=True, height=320)
    st.download_button("⬇️ Descargar historial", data=hist.to_csv(index=False, encoding="utf-8-sig"),
                       file_name=f"historial_cobranza_{periodo}.csv", mime="text/csv", key="cob_dl_hist")


def mostrar_cobranza(razon=None):
    st.markdown(CSS, unsafe_allow_html=True)
    st.markdown(HEADER, unsafe_allow_html=True)
    rol = st.session_state.get("rol", "")
    usuario = st.session_state.get("usuario", "") or "sin_usuario"
    es_bo = rol == "backoffice"
    if not es_bo and not razon:
        st.error("❌ Tu usuario no tiene una razón social asignada. Contacta a backoffice.")
        return

    try:
        with st.spinner("Cargando casos…"):
            headers, df, stamp = _cargar_casos()
            if _asegurar_estructura(headers, df):
                headers, df, stamp = _cargar_casos()
    except gspread.exceptions.APIError as e:
        st.error(f"❌ Google Drive está saturado o no respondió ({e}). Espera unos segundos y actualiza.")
        return
    except Exception as e:
        st.error(f"❌ No se pudo abrir '{LIBRO}' / '{PESTANA_CASOS}': {e}")
        return
    if df.empty:
        st.info("Sin casos registrados en el Drive.")
        return

    if not es_bo:
        df = df[df["razon_social"].map(_nr) == _nr(razon)]
        if df.empty:
            st.warning(f"No hay casos asignados a {razon}.")
            return

    _flash()
    periodos = sorted({p for p in df["PERIODO"].unique() if p}, reverse=True)
    if not periodos:
        st.warning("Los casos no tienen PERIODO asignado en el Drive.")
        return
    vigente = _hoy().strftime("%Y%m")
    c1, c2, c3 = st.columns([1.3, 2, 1.2])
    with c1:
        periodo = st.selectbox("📅 Periodo", periodos,
                               index=periodos.index(vigente) if vigente in periodos else 0, key="cob_periodo")
    partner = None
    with c2:
        if es_bo:
            partners = sorted({p for p in df["razon_social"].unique() if p})
            elegido = st.selectbox("🏢 Partner", ["TODOS"] + partners, key="cob_partner")
            partner = None if elegido == "TODOS" else elegido
        else:
            st.text_input("🏢 Partner", value=razon, disabled=True, key="cob_partner_fijo")
    with c3:
        st.write("")
        if st.button("🔄 Actualizar datos", use_container_width=True, key="cob_refresh"):
            _cargar_casos.clear()
            _cargar_listas.clear()
            _cargar_historial.clear()
            st.session_state["cob_nonce"] = st.session_state.get("cob_nonce", 0) + 1
            st.rerun()
        st.caption(f"Datos al {stamp} · se refrescan cada {TTL_CASOS}s")

    if es_bo:
        with st.expander("🛰️ Validación de pagos contra el servidor (Reporting)"):
            st.caption("Corre sola por tarea programada a las horas en que se actualiza la vista del "
                       "servidor (8am, 5pm, 7pm, 10pm, 12am). Este botón es solo para forzarla ahora.")
            if st.button("🔄 Validar pagos contra servidor ahora", key="cob_validar_servidor_manual"):
                PR.leer_estado_pagos.clear()
                resultado_servidor = ejecutar_validacion_pagos_servidor()
                if resultado_servidor["cerrados"]:
                    st.success(f"🟢 {resultado_servidor['cerrados']} caso(s) cerrados: pago confirmado "
                               "directo en el servidor.")
                    st.rerun()
                elif resultado_servidor["aviso"]:
                    st.warning(resultado_servidor["aviso"])
                else:
                    st.info("Sin casos nuevos para cerrar: nada pagado en el servidor que no estuviera "
                            "ya reflejado en el Drive.")

    dfa = df if not partner else df[df["razon_social"] == partner]
    dfp = dfa[dfa["PERIODO"] == periodo]

    editable, mensaje = R.ventana_edicion(periodo, _hoy(), es_bo)
    (st.success if editable and "abierto" in mensaje else st.warning if editable else st.info)(
        ("✏️ " if editable else "🔒 ") + mensaje)

    ctx = {"usuario": usuario, "rol": rol, "razon": razon, "es_bo": es_bo, "partner": partner,
           "listas": _cargar_listas(), "idx_id": headers.index(R.COL_ID) if R.COL_ID in headers else 0}

    t1, t2, t3 = st.tabs(["📋 Gestión de casos", "📊 Indicadores", "⬇️ Descargas e historial"])
    with t1:
        if dfp.empty:
            st.info("Sin casos en este periodo.")
        else:
            _tab_gestion(dfp, ctx, periodo, editable)
    with t2:
        _tab_indicadores(dfp, dfa, ctx)
    with t3:
        _tab_descargas(dfp, dfa, ctx, periodo, stamp)
