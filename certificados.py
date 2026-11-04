import re
from datetime import datetime

import pytz

from sheets import conectar_google_sheets_opcional

# Confirmado por el usuario (30/10/2026): archivo real de evaluaciones del
# canal Indirecto. El nombre dice "ABRIL 2026" pero es un archivo único y
# continuo (no se crea uno nuevo cada mes).
NOMBRE_HOJA_CERTIFICADOS = "INDIRECTOS ABRIL 2026 (respuestas)"
NOMBRE_PESTAÑA_CERTIFICADOS = "Respuestas de formulario 1"
COL_DNI = "DNI O CE"
COL_RESULTADO = "Puntuación"  # formato "20 / 20"
COL_FECHA = "Marca temporal"  # formato "D/M/AAAA HH:MM:SS"
# 80% equivale a 16/20 (el examen se guarda como "X / 20"). Nota mínima
# aprobatoria confirmada 04/11/2026 ("Ajustes adicionales – Website
# Jerarquía", punto 3): 16 puntos o más aprueba. NO usar 90 (equivalente a
# 18/20) como mínimo.
NOTA_MINIMA_APROBATORIA = 80  # % mínimo para aprobar (= 16/20).
VENTANA_VALIDEZ_HORAS = 120  # el examen debe estar rendido dentro de las últimas 120h (5 días). Confirmado 31/10/2026.

zona_peru = pytz.timezone("America/Lima")


def _parse_puntuacion(valor) -> float | None:
    """Convierte "20 / 20" -> 100.0. Retorna None si el formato no se reconoce."""
    m = re.match(r"\s*(\d+(?:[.,]\d+)?)\s*/\s*(\d+(?:[.,]\d+)?)\s*", str(valor))
    if not m:
        return None
    try:
        numerador = float(m.group(1).replace(",", "."))
        denominador = float(m.group(2).replace(",", "."))
        if denominador == 0:
            return None
        return (numerador / denominador) * 100
    except ValueError:
        return None


def _parse_fecha(valor) -> datetime | None:
    try:
        return datetime.strptime(str(valor).strip(), "%d/%m/%Y %H:%M:%S")
    except ValueError:
        return None


def validar_certificado_aprobado(dni: str) -> tuple[bool, str]:
    """
    Verifica que el promotor tenga el certificado de evaluación aprobado
    (>= NOTA_MINIMA_APROBATORIA) y vigente (rendido dentro de las últimas
    VENTANA_VALIDEZ_HORAS horas).

    Si la hoja de certificados no está disponible (no compartida, renombrada,
    etc.), no bloquea el alta: retorna (True, aviso) para no frenar el flujo
    por un problema de configuración ajeno al promotor.
    """
    dni = str(dni).strip()
    hoja, error = conectar_google_sheets_opcional(NOMBRE_HOJA_CERTIFICADOS, NOMBRE_PESTAÑA_CERTIFICADOS)

    if hoja is None:
        return True, (
            "⚠️ No se pudo validar el certificado de evaluación en este momento "
            f"({error}). No bloquea el alta por ahora."
        )

    try:
        valores = hoja.get_all_records()
    except Exception as e:
        return True, f"⚠️ No se pudo leer la hoja de certificados ({e}). No bloquea el alta por ahora."

    def _dni_coincide(valor_celda) -> bool:
        limpio = str(valor_celda).strip().replace(".0", "")
        return limpio == dni or limpio.zfill(8) == dni.zfill(8)

    registros_dni = [r for r in valores if _dni_coincide(r.get(COL_DNI, ""))]
    if not registros_dni:
        return False, f"❌ El DNI {dni} no tiene certificado de evaluación registrado."

    con_fecha = [(r, _parse_fecha(r.get(COL_FECHA, ""))) for r in registros_dni]
    con_fecha = [(r, f) for r, f in con_fecha if f is not None]
    if not con_fecha:
        return False, f"❌ El certificado del DNI {dni} tiene una fecha inválida y no se pudo validar."

    ultimo, fecha_ultimo = max(con_fecha, key=lambda par: par[1])

    ahora = datetime.now(zona_peru).replace(tzinfo=None)
    horas_transcurridas = (ahora - fecha_ultimo).total_seconds() / 3600
    if horas_transcurridas > VENTANA_VALIDEZ_HORAS:
        return False, (
            f"❌ El certificado de evaluación del DNI {dni} está vencido "
            f"(rendido hace {horas_transcurridas:.0f} horas; debe ser dentro de las "
            f"últimas {VENTANA_VALIDEZ_HORAS} horas). Debe rendir el examen nuevamente."
        )

    puntuacion_pct = _parse_puntuacion(ultimo.get(COL_RESULTADO, ""))
    if puntuacion_pct is None:
        return False, f"❌ No se pudo interpretar la nota del certificado del DNI {dni}."

    if puntuacion_pct < NOTA_MINIMA_APROBATORIA:
        return False, (
            f"❌ El certificado de evaluación del DNI {dni} no está aprobado "
            f"(nota: {puntuacion_pct:.0f}%, mínimo {NOTA_MINIMA_APROBATORIA}%)."
        )

    return True, ""
