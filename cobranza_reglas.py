"""Reglas de negocio del módulo de Cobranza (sin dependencias de Streamlit)."""
from datetime import date, datetime

import pandas as pd

N_INT = 6
DIA_INICIO_EDICION = 4
DIA_FIN_EDICION = 20

CAMPOS = ["FECHA", "HORARIO", "MEDIO", "TIPO CONTACTO", "ACCIÓN",
          "FECHA COMPROMISO", "MOTIVO DE NO PAGO", "HAY RECLAMO", "CÓDIGO RECLAMO", "OBSERVACIÓN"]
# "HAY RECLAMO" es independiente del resultado elegido (puede haber reclamo con
# cualquier ACCIÓN): "SI" o "" (vacío = no hubo). Nunca es obligatorio.

EFECTIVO, NO_EFECTIVO = "EFECTIVO", "NO EFECTIVO"
ACCIONES = {
    EFECTIVO: [
        "Ya pagó",
        "Genera compromiso de pago",
        "Indica que no pagará",
        "Contesta y cuelga",
        "Contesta y no da razón",
        "Otros: detallar",
    ],
    NO_EFECTIVO: [
        "Teléfono apagado",
        "Teléfono suspendido",
    ],
}
# Resultados de versiones anteriores: se reconocen en registros antiguos pero ya no se pueden registrar.
ACCIONES_LEGADO = {
    "Indica no pagará": EFECTIVO,
    "Teléfono no existe": NO_EFECTIVO,
    "Timbra y no contesta": NO_EFECTIVO,
    "Contesta pero desconoce a titular": NO_EFECTIVO,
}
ACCION_PAGO = "Ya pagó"
ACCION_COMPROMISO = "Genera compromiso de pago"
ACCION_NO_PAGARA = "Indica que no pagará"
REQUIERE_MOTIVO = {ACCION_NO_PAGARA}
REQUIERE_OBSERVACION = {"Otros: detallar"}
ACCIONES_RECONTACTO = {"Contesta y cuelga", "Contesta y no da razón"}

MOTIVOS_CIERRE = [
    "Pagó (confirmado)",
    "Cliente indica que no pagará",
    "Inubicable / teléfono no existe",
    "Cliente desconoce la deuda",
    "Deuda en reclamo / revisión",
    "Otro",
]
MOTIVO_CIERRE_PAGO = "Pagó (confirmado)"

COL_ID = "ID_CASO"
COL_ESTADO = "ESTADO_CASO"
COL_MOTIVO_CIERRE = "MOTIVO_CIERRE"
COL_DETALLE_CIERRE = "DETALLE_CIERRE"
COL_USUARIO_CIERRE = "USUARIO_CIERRE"
COL_FECHA_CIERRE = "FECHA_CIERRE"
COL_ULT_MOD = "ULTIMA_MODIFICACION"
COL_USR_ULT_MOD = "USUARIO_ULTIMA_MODIFICACION"
COL_RESP_BO = "Responsable BO"

E_PENDIENTE = "PENDIENTE"
E_EN_PROCESO = "EN PROCESO"
E_RECONTACTAR = "REQUIERE NUEVA CONTACTABILIDAD"
E_COMPROMISO = "COMPROMISO DE PAGO"
E_COMPROMISO_VENCIDO = "COMPROMISO VENCIDO"
E_PEND_CIERRE = "PENDIENTE DE CIERRE"
E_PAGADO = "FINALIZADO - PAGÓ"
E_SIN_EXITO = "FINALIZADO - SIN ÉXITO"

# (icono, color de fondo, color de texto) — el icono + etiqueta acompañan siempre al color.
ESTILO_ESTADO = {
    E_PENDIENTE:          ("⚪", "#898781", "#ffffff"),
    E_EN_PROCESO:         ("🔵", "#2a78d6", "#ffffff"),
    E_RECONTACTAR:        ("🟠", "#ec835a", "#0b0b0b"),
    E_COMPROMISO:         ("🟣", "#6250d6", "#ffffff"),
    E_COMPROMISO_VENCIDO: ("🔴", "#d03b3b", "#ffffff"),
    E_PEND_CIERRE:        ("🟡", "#fab219", "#0b0b0b"),
    E_PAGADO:             ("🟢", "#0ca30c", "#ffffff"),
    E_SIN_EXITO:          ("⚫", "#52514e", "#ffffff"),
}
ORDEN_ESTADOS = list(ESTILO_ESTADO)
ESTADOS_FINALIZADOS = {E_PAGADO, E_SIN_EXITO}
ESTADOS_RECONTACTO = {E_RECONTACTAR, E_COMPROMISO_VENCIDO}


def col(campo: str, n: int) -> str:
    return f"{campo} {n}"


def col_usuario(n: int) -> str:
    return f"USUARIO_INT{n}"


def col_timestamp(n: int) -> str:
    return f"TIMESTAMP_INT{n}"


def columnas_interaccion(n: int) -> list[str]:
    return [col(c, n) for c in CAMPOS] + [col_usuario(n), col_timestamp(n)]


COLUMNAS_CIERRE = [COL_ESTADO, COL_MOTIVO_CIERRE, COL_DETALLE_CIERRE,
                   COL_USUARIO_CIERRE, COL_FECHA_CIERRE]
COLUMNAS_GESTIONADAS = (
    [COL_RESP_BO]
    + [c for n in range(1, N_INT + 1) for c in columnas_interaccion(n)]
    + COLUMNAS_CIERRE
)
COLUMNAS_REQUERIDAS = [COL_ID] + COLUMNAS_GESTIONADAS + [COL_ULT_MOD, COL_USR_ULT_MOD]


def _v(fila, campo) -> str:
    valor = fila.get(campo, "")
    return "" if valor is None else str(valor).strip()


def parse_fecha(valor) -> date | None:
    texto = str(valor or "").strip()[:10]
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(texto, fmt).date()
        except ValueError:
            continue
    return None


def inicio_periodo(periodo: str) -> date | None:
    try:
        return date(int(str(periodo)[:4]), int(str(periodo)[4:6]), 1)
    except (ValueError, TypeError):
        return None


def interacciones_registradas(fila) -> int:
    """Cantidad de interacciones consecutivas (desde la 1) con acción registrada."""
    total = 0
    for n in range(1, N_INT + 1):
        if not _v(fila, col("ACCIÓN", n)):
            break
        total = n
    return total


def estado_caso(fila, hoy: date) -> str:
    motivo_cierre = _v(fila, COL_MOTIVO_CIERRE)
    if motivo_cierre:
        return E_PAGADO if motivo_cierre.startswith(MOTIVO_CIERRE_PAGO) or motivo_cierre.startswith(ACCION_PAGO) else E_SIN_EXITO
    n = interacciones_registradas(fila)
    if n == 0:
        return E_PENDIENTE
    accion = _v(fila, col("ACCIÓN", n))
    tipo = _v(fila, col("TIPO CONTACTO", n))
    if accion == ACCION_PAGO:
        return E_PAGADO
    if accion == ACCION_COMPROMISO:
        f_comp = parse_fecha(_v(fila, col("FECHA COMPROMISO", n)))
        if f_comp is not None and f_comp < hoy:
            return E_COMPROMISO_VENCIDO if n < N_INT else E_PEND_CIERRE
        return E_COMPROMISO
    if n >= N_INT:
        return E_PEND_CIERRE
    if tipo == NO_EFECTIVO or accion in ACCIONES_RECONTACTO:
        return E_RECONTACTAR
    return E_EN_PROCESO


def ventana_edicion(periodo: str, hoy: date, es_backoffice: bool) -> tuple[bool, str]:
    """(editable, mensaje). Partners: solo el periodo vigente, del día 4 al 20."""
    vigente = hoy.strftime("%Y%m")
    if es_backoffice:
        if str(periodo) == vigente and DIA_INICIO_EDICION <= hoy.day <= DIA_FIN_EDICION:
            return True, f"Periodo {periodo} abierto (día {DIA_INICIO_EDICION} al {DIA_FIN_EDICION})."
        return True, (f"Periodo {periodo} fuera de la ventana para partners. Backoffice puede corregir; "
                      "cada cambio queda en el historial.")
    if str(periodo) != vigente:
        return False, f"Periodo {periodo}: histórico en solo lectura."
    if hoy.day < DIA_INICIO_EDICION:
        return False, f"El periodo {periodo} se habilita para registro el día {DIA_INICIO_EDICION}."
    if hoy.day > DIA_FIN_EDICION:
        return False, f"El registro del periodo {periodo} cerró el día {DIA_FIN_EDICION}. Solo lectura."
    return True, f"Periodo {periodo} abierto: registro habilitado del día {DIA_INICIO_EDICION} al {DIA_FIN_EDICION}."


def validar_interaccion(datos: dict, n: int, fila, hoy: date, es_correccion: bool = False) -> list[str]:
    """Valida los datos de la interacción n contra el estado actual del caso."""
    errores = []
    registradas = interacciones_registradas(fila)
    estado = estado_caso(fila, hoy)

    if not es_correccion:
        if estado == E_PAGADO:
            errores.append("El cliente ya pagó: la gestión terminó y no admite más contactos.")
        elif estado in ESTADOS_FINALIZADOS:
            errores.append("El caso ya está finalizado; no admite nuevas interacciones.")
        if n != registradas + 1:
            errores.append(f"Corresponde registrar la interacción {registradas + 1}, no la {n}.")
        if n > N_INT:
            errores.append(f"El caso ya tiene las {N_INT} interacciones permitidas.")
    elif n > registradas:
        errores.append(f"La interacción {n} todavía no existe; no se puede corregir.")

    fecha = datos.get("FECHA")
    tipo = datos.get("TIPO CONTACTO", "")
    accion = datos.get("ACCIÓN", "")

    if not isinstance(fecha, date):
        errores.append("Falta la fecha de la interacción.")
    else:
        if fecha > hoy:
            errores.append("La fecha de la interacción no puede ser futura.")
        anterior = parse_fecha(_v(fila, col("FECHA", n - 1))) if n > 1 else None
        if anterior and fecha < anterior:
            errores.append(f"La fecha no puede ser anterior a la interacción {n - 1} ({anterior}).")
        siguiente = parse_fecha(_v(fila, col("FECHA", n + 1))) if es_correccion and n < registradas else None
        if siguiente and fecha > siguiente:
            errores.append(f"La fecha no puede ser posterior a la interacción {n + 1} ({siguiente}).")
        ini = inicio_periodo(_v(fila, "PERIODO"))
        if ini and fecha < ini:
            errores.append(f"La fecha no puede ser anterior al inicio del periodo ({ini}).")

    if not datos.get("HORARIO"):
        errores.append("Falta el horario.")
    if not datos.get("MEDIO"):
        errores.append("Falta el medio de contacto.")
    if tipo not in ACCIONES:
        errores.append("Primero selecciona el tipo de contacto (Efectivo / No efectivo).")
    elif not accion:
        errores.append("Falta el resultado del contacto.")
    elif accion not in ACCIONES[tipo]:
        errores.append(f"'{accion}' no corresponde a un contacto {tipo.lower()}. "
                       f"Opciones válidas: {', '.join(ACCIONES[tipo])}.")

    if accion == ACCION_COMPROMISO:
        f_comp = datos.get("FECHA COMPROMISO")
        if not isinstance(f_comp, date):
            errores.append("Falta la fecha de compromiso de pago.")
        elif isinstance(fecha, date) and f_comp < fecha:
            errores.append("La fecha de compromiso no puede ser anterior a la fecha de la interacción.")
    if accion in REQUIERE_MOTIVO and not datos.get("MOTIVO DE NO PAGO"):
        errores.append("Falta el motivo de no pago.")
    if accion in REQUIERE_OBSERVACION and not str(datos.get("OBSERVACIÓN", "")).strip():
        errores.append("Detalla la observación para 'Otros'.")
    if es_correccion and accion == ACCION_PAGO and n < registradas:
        errores.append("'Ya pagó' solo puede estar en la última interacción registrada.")
    return errores


def _es_si(v) -> bool:
    return str(v or "").strip().upper() == "SI"


def valores_interaccion(datos: dict, n: int, usuario: str, timestamp: str) -> dict:
    """Celdas a escribir para la interacción n (limpia los campos que no aplican)."""
    accion = datos.get("ACCIÓN", "")
    f_comp = datos.get("FECHA COMPROMISO") if accion == ACCION_COMPROMISO else None
    hay_reclamo = _es_si(datos.get("HAY RECLAMO"))
    return {
        col("FECHA", n): datos["FECHA"].isoformat(),
        col("HORARIO", n): datos.get("HORARIO", ""),
        col("MEDIO", n): datos.get("MEDIO", ""),
        col("TIPO CONTACTO", n): datos.get("TIPO CONTACTO", ""),
        col("ACCIÓN", n): accion,
        col("FECHA COMPROMISO", n): f_comp.isoformat() if isinstance(f_comp, date) else "",
        col("MOTIVO DE NO PAGO", n): datos.get("MOTIVO DE NO PAGO", "") if accion in REQUIERE_MOTIVO else "",
        col("HAY RECLAMO", n): "SI" if hay_reclamo else "",
        col("CÓDIGO RECLAMO", n): str(datos.get("CÓDIGO RECLAMO", "")).strip() if hay_reclamo else "",
        col("OBSERVACIÓN", n): str(datos.get("OBSERVACIÓN", "")).strip(),
        col_usuario(n): usuario,
        col_timestamp(n): timestamp,
    }


CAMPOS_FECHA = {"FECHA", "FECHA COMPROMISO"}
CAMPOS_CIERRE_MOTIVO = [COL_MOTIVO_CIERRE, COL_DETALLE_CIERRE, COL_USUARIO_CIERRE, COL_FECHA_CIERRE]


def normalizar(v) -> str:
    if v is None:
        return ""
    try:
        if pd.isna(v):
            return ""
    except (TypeError, ValueError):
        pass
    if isinstance(v, datetime):
        return v.date().isoformat()
    if isinstance(v, date):
        return v.isoformat()
    return str(v).strip()


def valor_campo(campo: str, v) -> str:
    texto = normalizar(v)
    if campo in CAMPOS_FECHA and texto:
        f = parse_fecha(texto)
        return f.isoformat() if f else texto
    return texto


def tipo_de_accion(accion: str) -> str:
    for tipo, lista in ACCIONES.items():
        if accion in lista:
            return tipo
    return ACCIONES_LEGADO.get(accion, "")


def limpiezas_aplicadas(datos: dict) -> list[str]:
    """Campos condicionales que se descartarán porque no corresponden al resultado elegido."""
    accion = datos.get("ACCIÓN", "")
    notas = []
    if normalizar(datos.get("FECHA COMPROMISO")) and accion != ACCION_COMPROMISO:
        notas.append("se descarta la fecha de compromiso (solo aplica a 'Genera compromiso de pago')")
    if normalizar(datos.get("MOTIVO DE NO PAGO")) and accion not in REQUIERE_MOTIVO:
        notas.append(f"se descarta el motivo de no pago (solo aplica a '{ACCION_NO_PAGARA}')")
    if normalizar(datos.get("CÓDIGO RECLAMO")) and not _es_si(datos.get("HAY RECLAMO")):
        notas.append("se descarta el código de reclamo (solo aplica si marcaste que hubo reclamo)")
    return notas


def procesar_edicion(original: dict, editado: dict, actual: dict, es_backoffice: bool,
                     usuario: str, timestamp: str, hoy: date) -> tuple[dict, list, list]:
    """
    Convierte la edición de una fila de la tabla (contactos hacia la derecha) en celdas a escribir.
    Aplica las mismas reglas que el registro guiado. La fila es atómica: si hay un error, no se guarda nada.
    Devuelve (cambios, operaciones[(operacion, n)], errores).
    """
    cambiadas = [n for n in range(1, N_INT + 1)
                 if any(valor_campo(c, editado.get(col(c, n))) != valor_campo(c, original.get(col(c, n)))
                        for c in CAMPOS)]
    resp_nuevo = normalizar(editado.get(COL_RESP_BO, original.get(COL_RESP_BO)))
    cambia_resp = resp_nuevo != normalizar(original.get(COL_RESP_BO))
    if not cambiadas and not cambia_resp:
        return {}, [], []
    if cambiadas and not es_backoffice and estado_caso(actual, hoy) in ESTADOS_FINALIZADOS:
        if estado_caso(actual, hoy) == E_PAGADO:
            return {}, [], ["El cliente ya pagó: la gestión terminó y no admite más contactos."]
        return {}, [], ["El caso está finalizado; no admite cambios."]

    trabajo, cambios, operaciones, errores = dict(actual), {}, [], []
    for n in cambiadas:
        registradas = interacciones_registradas(trabajo)
        crudo = {c: valor_campo(c, editado.get(col(c, n))) for c in CAMPOS}
        if not any(crudo.values()):
            if n <= registradas:
                errores.append(f"Contacto {n}: no se puede borrar un contacto ya registrado.")
            else:
                limpieza = {col(c, n): "" for c in CAMPOS}
                trabajo.update(limpieza)
                cambios.update(limpieza)
            continue
        datos =dict(crudo, **{"FECHA": parse_fecha(crudo["FECHA"]),
                               "FECHA COMPROMISO": parse_fecha(crudo["FECHA COMPROMISO"])})
        if n <= registradas:
            if not es_backoffice:
                errores.append(f"Contacto {n} ya está registrado: solo backoffice puede corregirlo.")
                continue
            errs = validar_interaccion(datos, n, trabajo, hoy, es_correccion=True)
            operacion = "CORRECCION_INTERACCION"
        elif n == registradas + 1:
            errs = validar_interaccion(datos, n, trabajo, hoy)
            operacion = "REGISTRO_INTERACCION"
        else:
            errores.append(f"Contacto {n}: primero completa el contacto {registradas + 1}.")
            continue
        if errs:
            errores.extend(f"Contacto {n}: {e}" for e in errs)
            continue
        valores = valores_interaccion(datos, n, usuario, timestamp)
        if operacion == "CORRECCION_INTERACCION":
            valores.pop(col_usuario(n))
            valores.pop(col_timestamp(n))
        trabajo.update(valores)
        cambios.update(valores)
        operaciones.append((operacion, n))

        motivo = _v(trabajo, COL_MOTIVO_CIERRE)
        ultima = interacciones_registradas(trabajo)
        if datos["ACCIÓN"] == ACCION_PAGO and not motivo:
            cierre = {COL_MOTIVO_CIERRE: f"{ACCION_PAGO} (interacción {n})", COL_DETALLE_CIERRE: "",
                      COL_USUARIO_CIERRE: usuario, COL_FECHA_CIERRE: timestamp}
            trabajo.update(cierre)
            cambios.update(cierre)
        elif motivo.startswith(ACCION_PAGO) and _v(trabajo, col("ACCIÓN", ultima)) != ACCION_PAGO:
            limpio = dict.fromkeys(CAMPOS_CIERRE_MOTIVO, "")
            trabajo.update(limpio)
            cambios.update(limpio)

    if errores:
        return {}, [], errores
    if cambia_resp:
        cambios[COL_RESP_BO] = resp_nuevo
        if not operaciones:
            operaciones.append(("CAMBIO_RESPONSABLE", None))
    return cambios, operaciones, []


def enriquecer(df: pd.DataFrame, hoy: date) -> pd.DataFrame:
    """Agrega columnas derivadas: estado vivo, interacciones y último contacto."""
    df = df.copy()
    registros = df.to_dict("records")
    n_reg = [interacciones_registradas(r) for r in registros]
    df["_N"] = n_reg
    df["_ESTADO"] = [estado_caso(r, hoy) for r in registros]
    df["_ULT_FECHA"] = [_v(r, col("FECHA", n)) if n else "" for r, n in zip(registros, n_reg)]
    df["_ULT_TIPO"] = [_v(r, col("TIPO CONTACTO", n)) if n else "" for r, n in zip(registros, n_reg)]
    df["_ULT_ACCION"] = [_v(r, col("ACCIÓN", n)) if n else "" for r, n in zip(registros, n_reg)]
    df["_COMPROMISO"] = [_v(r, col("FECHA COMPROMISO", n)) if n else "" for r, n in zip(registros, n_reg)]
    df["_CONTACTO_EFECTIVO"] = [
        any(_v(r, col("TIPO CONTACTO", k)) == EFECTIVO for k in range(1, n + 1))
        for r, n in zip(registros, n_reg)
    ]
    df["_RECLAMOS"] = [
        [_v(r, col("CÓDIGO RECLAMO", k)) or "(sin código)" for k in range(1, n + 1)
         if _es_si(_v(r, col("HAY RECLAMO", k)))]
        for r, n in zip(registros, n_reg)
    ]
    df["_TIENE_RECLAMO"] = df["_RECLAMOS"].map(bool)
    return df


def kpis(df: pd.DataFrame) -> dict:
    total = len(df)
    gestionados = int((df["_N"] > 0).sum()) if total else 0
    contactados = int(df["_CONTACTO_EFECTIVO"].sum()) if total else 0
    estados = df["_ESTADO"].value_counts().to_dict() if total else {}
    finalizados = sum(estados.get(e, 0) for e in ESTADOS_FINALIZADOS)
    return {
        "total": total,
        "gestionados": gestionados,
        "pendientes": estados.get(E_PENDIENTE, 0),
        "en_proceso": estados.get(E_EN_PROCESO, 0) + estados.get(E_COMPROMISO, 0),
        "recontactar": sum(estados.get(e, 0) for e in ESTADOS_RECONTACTO),
        "compromisos": estados.get(E_COMPROMISO, 0),
        "compromisos_vencidos": estados.get(E_COMPROMISO_VENCIDO, 0),
        "contactados": contactados,
        "interacciones": int(df["_N"].sum()) if total else 0,
        "con_reclamo": int(df["_TIENE_RECLAMO"].sum()) if total else 0,
        "pend_cierre": estados.get(E_PEND_CIERRE, 0),
        "pagados": estados.get(E_PAGADO, 0),
        "sin_exito": estados.get(E_SIN_EXITO, 0),
        "finalizados": finalizados,
        "pct_avance": gestionados / total * 100 if total else 0.0,
        "pct_contactabilidad": contactados / gestionados * 100 if gestionados else 0.0,
        "pct_recupero": estados.get(E_PAGADO, 0) / total * 100 if total else 0.0,
        "estados": estados,
    }


def avance_por_interaccion(df: pd.DataFrame) -> pd.DataFrame:
    filas = []
    for n in range(1, N_INT + 1):
        registradas = df[df["_N"] >= n]
        tipos = registradas[col("TIPO CONTACTO", n)] if col("TIPO CONTACTO", n) in registradas.columns else pd.Series(dtype=str)
        filas.append({"Interacción": f"Int. {n}", "n": n,
                      "Efectivo": int((tipos == EFECTIVO).sum()),
                      "No efectivo": int((tipos == NO_EFECTIVO).sum()),
                      "Total": len(registradas)})
    return pd.DataFrame(filas)


def distribucion_acciones(df: pd.DataFrame) -> pd.DataFrame:
    filas = []
    for n in range(1, N_INT + 1):
        c_t, c_a = col("TIPO CONTACTO", n), col("ACCIÓN", n)
        if c_a not in df.columns:
            continue
        sub = df[df["_N"] >= n]
        for tipo, accion in zip(sub.get(c_t, ""), sub[c_a]):
            filas.append({"Tipo": tipo or "Sin tipo", "Acción": accion})
    if not filas:
        return pd.DataFrame(columns=["Tipo", "Acción", "Casos"])
    return (pd.DataFrame(filas).value_counts(["Tipo", "Acción"]).rename("Casos")
            .reset_index().sort_values("Casos", ascending=False))


def periodo_de_fecha(fecha: date, cierres: list[tuple[str, date]]) -> str | None:
    """Ubica `fecha` en su periodo de facturación real: el primer corte (de
    tb_cierre_facturacion) que no haya pasado todavía para esa fecha. `cierres` debe venir
    ordenado por fecha de corte ascendente. None si `fecha` es posterior a todos los cortes
    conocidos (periodo futuro, aún sin corte definido)."""
    for periodo, corte in cierres:
        if fecha <= corte:
            return periodo
    return None


def vintage_n(periodo_caso: str | None, cierres: list[tuple[str, date]], hoy: date) -> int | None:
    """VN del periodo_caso respecto al periodo más reciente YA CERRADO a `hoy`. VN1 = ese
    periodo más reciente, VN2 el anterior, etc. None si periodo_caso no está en `cierres`,
    si es posterior al último periodo cerrado (todavía no cerró su propio ciclo), o si cae
    fuera de VN1..VN6."""
    if not periodo_caso:
        return None
    periodos = [p for p, _ in cierres]
    if periodo_caso not in periodos:
        return None
    cerrados = [i for i, (_, corte) in enumerate(cierres) if corte <= hoy]
    if not cerrados:
        return None
    idx_vn1 = max(cerrados)
    idx_caso = periodos.index(periodo_caso)
    vn = idx_vn1 - idx_caso + 1
    return vn if 1 <= vn <= 6 else None


def evolucion_mensual(df: pd.DataFrame) -> pd.DataFrame:
    filas = []
    for periodo, sub in df.groupby("PERIODO"):
        if not str(periodo).strip():
            continue
        k = kpis(sub)
        filas.append({"Periodo": str(periodo), "Casos": k["total"], "Gestionados": k["gestionados"],
                      "Pagados": k["pagados"], "% Avance": round(k["pct_avance"], 1),
                      "% Contactabilidad": round(k["pct_contactabilidad"], 1),
                      "% Recupero": round(k["pct_recupero"], 1)})
    return pd.DataFrame(filas).sort_values("Periodo") if filas else pd.DataFrame()
