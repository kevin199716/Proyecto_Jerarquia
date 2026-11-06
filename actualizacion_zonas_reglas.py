"""Reglas puras del módulo de Actualización de Zonas (sin dependencias de Streamlit)."""
from datetime import date

# Ventana mensual de actualización: día 3 00:00 al día 6 23:59. Confirmado 06/11/2026
# (ajustado de día 8 a día 6 el mismo día).
DIA_INICIO = 3
DIA_FIN = 6

CAMPOS = ["DEPARTAMENTO", "PROVINCIA", "DISTRITO", "ZONA_AGRUPADA"]


def periodo_actual(hoy: date) -> str:
    return hoy.strftime("%Y%m")


def ventana_actualizacion(hoy: date, es_backoffice: bool) -> tuple[bool, str]:
    """(editable, mensaje). Partners: solo del día 3 al 8 del mes vigente.
    Backoffice siempre puede corregir; fuera de ventana queda marcado en el historial."""
    if es_backoffice:
        if DIA_INICIO <= hoy.day <= DIA_FIN:
            return True, f"Ventana abierta (día {DIA_INICIO} al {DIA_FIN})."
        return True, ("Fuera de la ventana para partners. Backoffice puede corregir igual; "
                      "cada cambio queda en el historial.")
    if hoy.day < DIA_INICIO:
        return False, f"La actualización de zonas se habilita el día {DIA_INICIO} de cada mes."
    if hoy.day > DIA_FIN:
        return False, (f"La actualización de zonas cerró el día {DIA_FIN}. "
                       f"Vuelve a abrirse el día {DIA_INICIO} del próximo mes.")
    return True, f"Ventana abierta: puedes actualizar del día {DIA_INICIO} al {DIA_FIN} de este mes."
