"""Validación de pagos directo contra el servidor (Reporting), de solo lectura.

Cruza COD_CLIENTE contra sales.v_base_gestion_ind_out para saber si una boleta
ya está pagada SIN depender de que alguien lo marque a mano en el Drive.
Nunca escribe en esa base, y nunca rompe Cobranza si el servidor no responde:
ante cualquier falla devuelve un mapa vacío + un aviso.
"""
import os

import pandas as pd
import streamlit as st

HOST = os.getenv("REPORTING_PG_HOST", "10.52.0.134")
PORT = os.getenv("REPORTING_PG_PORT", "5432")
DBNAME = os.getenv("REPORTING_PG_DB", "reporting1_020123")
# Réplica: tiene tb_cierre_facturacion (los cortes reales de facturación, para mapear los
# vintages VN1..VN6). Usa el mismo usuario/clave que Reporting (confirmado con el usuario).
REPLICA_HOST = os.getenv("REPLICA_PG_HOST", "10.251.0.142")
REPLICA_PORT = os.getenv("REPLICA_PG_PORT", "5432")
REPLICA_DBNAME = os.getenv("REPLICA_PG_DB", "prod_26_nov_2021")
# Igual que usuarios.json en auth.py: en el VPS usuario/clave viven en
# /etc/secrets, nunca en el repo. Las variables de entorno son el fallback
# para pruebas locales. Los dos caminos de ejecución (la app web vía systemd,
# y la tarea programada vía cron) leen credenciales igual, sin depender de
# que el entorno de cron herede las variables del servicio de la app.
_RUTA_SECRETO_USUARIO = "/etc/secrets/REPORTING_PG_USER"
_RUTA_SECRETO_CLAVE = "/etc/secrets/REPORTING_PG_PASSWORD"


def _usuario() -> str:
    if os.path.exists(_RUTA_SECRETO_USUARIO):
        try:
            with open(_RUTA_SECRETO_USUARIO, encoding="utf-8") as f:
                return f.read().strip()
        except OSError:
            pass
    return os.getenv("REPORTING_PG_USER", "")

# Cada cuánto se vuelve a consultar el servidor. La vista solo se actualiza 1 vez
# al día, así que consultarla cada pocos minutos no aporta nada: 6 horas alcanza
# para detectar el refresco del día sin golpear Reporting de más.
TTL_PAGOS = 6 * 60 * 60

PAGADO = "Pagado"


def _clave() -> str:
    if os.path.exists(_RUTA_SECRETO_CLAVE):
        try:
            with open(_RUTA_SECRETO_CLAVE, encoding="utf-8") as f:
                return f.read().strip()
        except OSError:
            pass
    return os.getenv("REPORTING_PG_PASSWORD", "")


@st.cache_data(ttl=TTL_PAGOS, show_spinner=False)
def leer_estado_pagos() -> tuple[dict, str]:
    """
    (mapa, aviso). mapa = {cod_cliente: {"estado_pago", "boleta_fecha_pago", "boleta_monto"}}.
    Si faltan credenciales o el servidor no responde, mapa queda vacío y aviso
    explica por qué — la validación automática simplemente no corre ese ciclo.
    """
    usuario, clave = _usuario(), _clave()
    if not usuario or not clave:
        return {}, "Validación contra servidor no configurada (faltan credenciales de Reporting)."
    try:
        import psycopg2
    except ImportError:
        return {}, "Falta instalar psycopg2-binary para validar pagos contra el servidor."
    try:
        conn = psycopg2.connect(host=HOST, port=PORT, dbname=DBNAME, user=usuario,
                                 password=clave, connect_timeout=6)
    except Exception as e:
        return {}, f"No se pudo conectar al servidor de Reporting: {e}"
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT cod_cliente, estado_pago, boleta_fecha_pago, boleta_monto
                FROM sales.v_base_gestion_ind_out
                WHERE cod_cliente IS NOT NULL
            """)
            filas = cur.fetchall()
    except Exception as e:
        return {}, f"La consulta a Reporting falló: {e}"
    finally:
        conn.close()
    mapa = {
        str(cod).strip(): {
            "estado_pago": (estado or "").strip(),
            "boleta_fecha_pago": fecha.date().isoformat() if fecha else "",
            "boleta_monto": monto,
        }
        for cod, estado, fecha, monto in filas if str(cod or "").strip()
    }
    return mapa, ""


@st.cache_data(ttl=TTL_PAGOS, show_spinner=False)
def leer_base_vintage() -> tuple[pd.DataFrame, str]:
    """
    Base para el análisis por vintage (VN1..VN6): un registro por cod_cliente con su estado
    de pago, fecha de activación (para ubicar su periodo) y el vendedor que lo generó.
    De solo lectura contra Reporting, igual que leer_estado_pagos. Nunca rompe Cobranza:
    si falla, devuelve un DataFrame vacío + aviso.
    """
    usuario, clave = _usuario(), _clave()
    if not usuario or not clave:
        return pd.DataFrame(), "Validación contra servidor no configurada (faltan credenciales de Reporting)."
    try:
        import psycopg2
    except ImportError:
        return pd.DataFrame(), "Falta instalar psycopg2-binary para leer Reporting."
    try:
        conn = psycopg2.connect(host=HOST, port=PORT, dbname=DBNAME, user=usuario,
                                 password=clave, connect_timeout=6)
    except Exception as e:
        return pd.DataFrame(), f"No se pudo conectar al servidor de Reporting: {e}"
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT cod_cliente, estado_pago, fecha_activacion, razon_social,
                       nombre_creador_lead, dni_creador_lead
                FROM sales.v_base_gestion_ind_out
                WHERE cod_cliente IS NOT NULL AND fecha_activacion IS NOT NULL
            """)
            filas = cur.fetchall()
    except Exception as e:
        return pd.DataFrame(), f"La consulta a Reporting falló: {e}"
    finally:
        conn.close()
    df = pd.DataFrame(filas, columns=["cod_cliente", "estado_pago", "fecha_activacion",
                                      "razon_social", "nombre_creador_lead", "dni_creador_lead"])
    df["cod_cliente"] = df["cod_cliente"].astype(str).str.strip()
    df["fecha_activacion"] = pd.to_datetime(df["fecha_activacion"]).dt.date
    return df, ""


@st.cache_data(ttl=TTL_PAGOS, show_spinner=False)
def leer_cierres_facturacion() -> tuple[list[tuple[str, "object"]], str]:
    """
    [(periodo "YYYY-MM", fecha_de_corte), ...] ordenados por fecha, desde
    public.tb_cierre_facturacion en la réplica. El corte real NO es un día fijo del mes
    (se mueve mes a mes), así que los vintages VN1..VN6 se calculan contra esta tabla y
    no contra una fecha fija. Mismo usuario/clave que Reporting.
    """
    usuario, clave = _usuario(), _clave()
    if not usuario or not clave:
        return [], "Validación contra servidor no configurada (faltan credenciales de Reporting)."
    try:
        import psycopg2
    except ImportError:
        return [], "Falta instalar psycopg2-binary para leer la réplica."
    try:
        conn = psycopg2.connect(host=REPLICA_HOST, port=REPLICA_PORT, dbname=REPLICA_DBNAME,
                                 user=usuario, password=clave, connect_timeout=6)
    except Exception as e:
        return [], f"No se pudo conectar a la réplica (tb_cierre_facturacion): {e}"
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT cierre_facturacion_periodo, cierre_facturacion_base
                FROM public.tb_cierre_facturacion
                ORDER BY cierre_facturacion_periodo
            """)
            filas = cur.fetchall()
    except Exception as e:
        return [], f"La consulta a tb_cierre_facturacion falló: {e}"
    finally:
        conn.close()
    return [(str(periodo), base.date()) for periodo, base in filas if periodo and base], ""
