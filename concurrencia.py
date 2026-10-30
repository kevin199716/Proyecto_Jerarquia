import threading
from datetime import datetime, timedelta

import pytz

from sheets import _abrir_spreadsheet, conectar_google_sheets_opcional

zona_peru = pytz.timezone("America/Lima")

# Serializa el bloque crítico (validar DNI + append_row) entre todas las sesiones
# que corren dentro de este mismo proceso de Streamlit (el VPS lo despliega como
# un único proceso systemd, así que esto ya cubre doble pestaña / dos usuarios
# atendidos por el mismo servicio).
LOCK_ALTAS = threading.Lock()

TTL_LOCK_SEGUNDOS = 30


def _ahora() -> datetime:
    return datetime.now(zona_peru)


def _parse_timestamp(valor: str):
    try:
        return datetime.strptime(valor, "%Y-%m-%d %H:%M:%S.%f").replace(tzinfo=zona_peru)
    except Exception:
        try:
            return datetime.strptime(valor, "%Y-%m-%d %H:%M:%S").replace(tzinfo=zona_peru)
        except Exception:
            return None


def obtener_hoja_locks(nombre_hoja: str = "maestra_vendedores", nombre_worksheet: str = "LOCKS_ALTA"):
    """
    Abre (o crea si no existe) la pestaña de candados anti-duplicados. A
    diferencia de sheets.obtener_o_crear_worksheet, esta nunca llama a
    st.stop(): el candado de Sheets es un refuerzo (ver intentar_lock_sheet),
    no algo de lo que dependa poder dar altas. Si algo falla, retorna None y
    la app sigue funcionando solo con el lock en memoria (LOCK_ALTAS).
    """
    try:
        hoja, _error = conectar_google_sheets_opcional(nombre_hoja, nombre_worksheet)
        if hoja is not None:
            return hoja

        spreadsheet = _abrir_spreadsheet(nombre_hoja)
        hoja = spreadsheet.add_worksheet(title=nombre_worksheet, rows="2000", cols="3")
        hoja.append_row(["DNI", "USUARIO", "TIMESTAMP"], value_input_option="USER_ENTERED")
        return hoja
    except Exception:
        return None


def intentar_lock_sheet(hoja_locks, dni: str, usuario: str, ttl_segundos: int = TTL_LOCK_SEGUNDOS) -> tuple[bool, str]:
    """
    Candado adicional a nivel de Google Sheets: cubre el caso de varios procesos
    (p. ej. un reinicio del servicio solapado con una petición en curso) que el
    lock en memoria (LOCK_ALTAS) no alcanza a cubrir.

    No se "libera" el lock explícitamente: una fila se considera vigente solo si
    su timestamp está dentro de ttl_segundos; fuera de eso, se ignora. Así no hace
    falta una segunda escritura para liberar y no hay riesgo de dejar un candado
    trabado si la app se cae a mitad de un alta.
    """
    if hoja_locks is None:
        return True, ""

    ahora = _ahora()
    try:
        valores = hoja_locks.get_all_values()
    except Exception:
        # Si Sheets no responde, no se bloquea el alta por esto: el lock en
        # memoria (LOCK_ALTAS) ya cubre el caso más común.
        return True, ""

    filas = valores[1:] if valores else []
    vigentes_mismo_dni = 0
    for fila in filas:
        if len(fila) < 3:
            continue
        fila_dni, _fila_usuario, fila_ts = fila[0], fila[1], fila[2]
        if fila_dni.strip() != dni:
            continue
        ts = _parse_timestamp(fila_ts.strip())
        if ts and (ahora - ts) <= timedelta(seconds=ttl_segundos):
            vigentes_mismo_dni += 1

    if vigentes_mismo_dni > 0:
        return False, (
            f"Otro registro con el DNI {dni} se está procesando en este momento. "
            "Espera unos segundos y vuelve a intentarlo."
        )

    try:
        marca = ahora.strftime("%Y-%m-%d %H:%M:%S.%f")
        hoja_locks.append_row([dni, usuario, marca], value_input_option="USER_ENTERED")
    except Exception:
        # Si falla la escritura del candado, se sigue: el lock en memoria del
        # proceso ya evita la carrera más frecuente y no vale la pena bloquear
        # el alta por un problema puntual de escritura del candado.
        pass

    return True, ""
