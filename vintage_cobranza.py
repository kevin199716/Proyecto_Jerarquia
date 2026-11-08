"""Métricas de Cobranza por vintage (VN1..VN6), por dealer y por vendedor.

Combina dos fuentes:
  - Reporting (sales.v_base_gestion_ind_out): estado_pago, fecha_activacion, razon_social
    (dealer) y nombre_creador_lead (el vendedor que activó la venta — "agente" en este
    reporte, confirmado con el usuario: es el vendedor, no quien cobra en Cobranza).
  - Cobranza (el Consolidado del Drive, ya cargado por cobranza_calidad): si el caso tiene
    contactos registrados, y si alguno fue efectivo.

Sin dependencias de Streamlit: se puede probar con DataFrames armados a mano.
"""
import pandas as pd

import cobranza_reglas as R

METRICAS = {
    "pagado": "% Pagado",
    "contactado": "% Contactado",
    "contactado_efectivo": "% Contactado efectivo",
    "compromiso": "% Compromiso de pago",
    "prom_contactos": "Prom. de contactos",
}
ESTADOS_COMPROMISO = {R.E_COMPROMISO, R.E_COMPROMISO_VENCIDO}


def calcular_metricas_vintage(df_reporting: pd.DataFrame, df_casos: pd.DataFrame,
                              cierres: list[tuple[str, "object"]], hoy) -> pd.DataFrame:
    """
    df_reporting: columnas cod_cliente, estado_pago, fecha_activacion (date), razon_social,
      nombre_creador_lead.
    df_casos: columnas cod_cliente, _N, _CONTACTO_EFECTIVO, _ESTADO (las que ya calcula
      cobranza_reglas.enriquecer sobre el Consolidado). Puede venir vacío: en ese caso
      % pagado sigue saliendo, las otras 4 métricas quedan en 0.
    Devuelve una fila por (razon_social, vendedor, vn) con n_casos y las 5 métricas.
    """
    columnas_salida = ["razon_social", "vendedor", "vn", "n_casos"] + list(METRICAS)
    if df_reporting.empty:
        return pd.DataFrame(columns=columnas_salida)

    base = df_reporting.copy()
    base["periodo"] = base["fecha_activacion"].map(lambda f: R.periodo_de_fecha(f, cierres))
    base["vn"] = base["periodo"].map(lambda p: R.vintage_n(p, cierres, hoy))
    base = base[base["vn"].notna()].copy()
    if base.empty:
        return pd.DataFrame(columns=columnas_salida)
    base["vn"] = base["vn"].astype(int)

    if df_casos is not None and not df_casos.empty:
        casos = df_casos[["cod_cliente", "_N", "_CONTACTO_EFECTIVO", "_ESTADO"]].drop_duplicates("cod_cliente")
        base = base.merge(casos, on="cod_cliente", how="left")
    else:
        base["_N"], base["_CONTACTO_EFECTIVO"], base["_ESTADO"] = 0, False, ""
    base["_N"] = base["_N"].fillna(0).astype(int)
    base["_CONTACTO_EFECTIVO"] = base["_CONTACTO_EFECTIVO"].map(lambda v: bool(v) if pd.notna(v) else False)
    base["_ESTADO"] = base["_ESTADO"].fillna("")

    filas = []
    for (razon, vendedor, vn), g in base.groupby(["razon_social", "nombre_creador_lead", "vn"]):
        n = len(g)
        filas.append({
            "razon_social": razon, "vendedor": vendedor, "vn": vn, "n_casos": n,
            "pagado": (g["estado_pago"] == "Pagado").mean() * 100,
            "contactado": (g["_N"] > 0).mean() * 100,
            "contactado_efectivo": g["_CONTACTO_EFECTIVO"].mean() * 100,
            "compromiso": g["_ESTADO"].isin(ESTADOS_COMPROMISO).mean() * 100,
            "prom_contactos": g["_N"].mean(),
        })
    return pd.DataFrame(filas, columns=columnas_salida)


def ranking_vendedores(metricas: pd.DataFrame) -> pd.DataFrame:
    """Resumen por vendedor sumando todos los VN (no por vintage separado), ordenado de
    mayor a menor % pagado. n_casos pondera el % pagado para no tratar igual a un
    vendedor con 2 casos que a uno con 200."""
    columnas = ["razon_social", "vendedor", "n_casos", "pagado"]
    if metricas.empty:
        return pd.DataFrame(columns=columnas)
    m = metricas.assign(_pagados=metricas["pagado"] * metricas["n_casos"] / 100)
    g = (m.groupby(["razon_social", "vendedor"])
         .agg(n_casos=("n_casos", "sum"), _pagados=("_pagados", "sum"))
         .reset_index())
    g["pagado"] = (g["_pagados"] / g["n_casos"] * 100).where(g["n_casos"] > 0, 0.0)
    return g[columnas].sort_values("pagado", ascending=False).reset_index(drop=True)


def tabla_pivote(metricas: pd.DataFrame, metrica: str) -> pd.DataFrame:
    """Pivotea a (razon_social, vendedor) x VN1..VN6 para la métrica elegida. Celdas sin
    datos para ese VN quedan en NaN (se muestran como 'sin datos' en la UI, no como 0)."""
    if metricas.empty:
        return pd.DataFrame()
    piv = metricas.pivot_table(index=["razon_social", "vendedor"], columns="vn", values=metrica)
    piv = piv.reindex(columns=range(1, 7))
    piv.columns = [f"VN{n}" for n in piv.columns]
    return piv.sort_index()
