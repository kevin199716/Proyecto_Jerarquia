"""Tarea programada (cron) — NO es parte de la app web, se corre aparte.

Valida pagos directo contra el servidor (Reporting) y cierra en Cobranza los
casos ya pagados, sin depender de que alguien tenga la app abierta ni de que
alguien actualice el Drive a mano. Pensada para correr justo después de las
horas en que se actualizan los procesos de Reporting.

Uso:          python tarea_validar_pagos_servidor.py
Crontab (hora Perú) — 8am, 5pm, 7pm, 10pm y 12am:
    0 8,17,19,22,0 * * * cd /opt/Proyecto_Jerarquia && /opt/Proyecto_Jerarquia/venv/bin/python tarea_validar_pagos_servidor.py >> /opt/Proyecto_Jerarquia/logs/validar_pagos.log 2>&1
(ajusta la ruta del venv/python a la real del VPS si es otra)
"""
import sys
from datetime import datetime

import cobranza_calidad as C

if __name__ == "__main__":
    ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ahora}] iniciando validación de pagos contra servidor…")
    resultado = C.ejecutar_validacion_pagos_servidor()
    if resultado["aviso"]:
        print(f"[{ahora}] AVISO: {resultado['aviso']}")
    print(f"[{ahora}] casos cerrados automáticamente: {resultado['cerrados']}")
    sys.exit(0)
