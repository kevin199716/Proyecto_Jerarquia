import re
import streamlit as st
import pandas as pd
import datetime
import pytz
import pydeck as pdk

# Validadores

def validar_correo(correo: str, cargo: str, dominios_permitidos: list[str]) -> bool:
    correo = str(correo).strip()
    patron_correo = r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"

    if not re.fullmatch(patron_correo, correo):
        st.error("❌ El correo electrónico no tiene un formato válido.")
        return False

    dominio = correo.rsplit("@", 1)[-1].strip().lower()
    dominios_permitidos = [str(d).strip().lower() for d in (dominios_permitidos or [])]

    if dominios_permitidos and dominio not in dominios_permitidos and cargo != "Freelance":
        st.error(f"❌ El dominio '{dominio}' no está permitido.")
        return False

    return True
def validacion_dni(hoja_colaboradores, numero_documento):

    sheet = hoja_colaboradores.get_all_records()
    df = pd.DataFrame(sheet)
    
    df["numero_documento"] = df["numero_documento"].astype(str).str.zfill(8)

    tz = pytz.timezone("America/Lima")
    hoy = datetime.datetime.now(tz).date()

    # Filtrar por DNI
    registros = df[df["numero_documento"] == numero_documento]

    if registros.empty:
        return "nuevo" # no existe en la base

    # Ordenar por timestamp (más reciente primero)
    registros = registros.sort_values("etl_timestamp", ascending=False)

    # Tomar el último registro válido
    registro = registros.iloc[0]

    # Caso 1: activo
    if registro["fecha_baja"] == "" and registro["blacklist"] == "":
        return "activo"

    # Caso 2: en blacklist
    elif registro["blacklist"] != "":
        return "observado"

    # Caso 3: baja reciente (≤ 2 meses)
    elif registro["fecha_baja"] != "" and registro["blacklist"] == "":
        try:
            fecha_baja = pd.to_datetime(registro["fecha_baja"]).date()
            diferencia_meses = (hoy.year - fecha_baja.year) * 12 + (hoy.month - fecha_baja.month)
            if diferencia_meses <= 2:
                return "baja"
        except Exception as e:
            return "error"
        
    return "nuevo"


# Visualizaciones de resumen

def mostrar_resumen(df):
    """Muestra resúmenes y métricas de colaboradores activos en Streamlit"""
    # Filtrar según tus reglas de fecha_baja y fecha_blacklist
    df_filtrado = df[
        (df["fecha_baja"].isna() | (df["fecha_baja"] == "")) &
        (df["fecha_blacklist"].isna() | (df["fecha_blacklist"] == ""))
    ]

    # Resumen por departamento
    resumen_departamento = (
        df_filtrado.groupby("ubicacion_departamento").agg(
            cantidad_vendedores=("cargo", lambda x: (x == "Vendedor").sum()),
            cantidad_freelance=("cargo", lambda x: (x == "Freelance").sum()),
            cantidad_digital=("cargo", lambda x: (x == "Digital").sum()),
            cantidad_dueno=("cargo", lambda x: (x == "Dueño").sum()),
            cantidad_supervisor=("cargo", lambda x: (x == "Supervisor").sum()),
            cantidad_formador=("cargo", lambda x: (x == "Formador").sum()),
            cantidad_backoffice=("cargo", lambda x: (x == "Backoffice").sum())
        )
        .reset_index()
    )

    # 👉 Agregar columna total
    resumen_departamento["total_colaboradores"] = (
        resumen_departamento[
            [
                "cantidad_vendedores",
                "cantidad_freelance",
                "cantidad_digital",
                "cantidad_dueno",
                "cantidad_supervisor",
                "cantidad_formador",
                "cantidad_backoffice",
            ]
        ].sum(axis=1)
    )
    resumen_departamento = resumen_departamento.sort_values(
        by="total_colaboradores", ascending=False
    )

    # Resumen por distribuidor
    resumen_distribuidor = (
        df_filtrado.groupby("distribuidor").agg(
            cantidad_vendedores=("cargo", lambda x: (x == "Vendedor").sum()),
            cantidad_freelance=("cargo", lambda x: (x == "Freelance").sum()),
            cantidad_digital=("cargo", lambda x: (x == "Digital").sum()),
            cantidad_dueno=("cargo", lambda x: (x == "Dueño").sum()),
            cantidad_supervisor=("cargo", lambda x: (x == "Supervisor").sum()),
            cantidad_formador=("cargo", lambda x: (x == "Formador").sum()),
            cantidad_backoffice=("cargo", lambda x: (x == "Backoffice").sum())
        )
        .reset_index()
    )

    resumen_distribuidor["total_colaboradores"] = (
        resumen_distribuidor[
            [
                "cantidad_vendedores",
                "cantidad_freelance",
                "cantidad_digital",
                "cantidad_dueno",
                "cantidad_supervisor",
                "cantidad_formador",
                "cantidad_backoffice",
            ]
        ].sum(axis=1)
    )
    resumen_distribuidor = resumen_distribuidor.sort_values(
        by="total_colaboradores", ascending=False
    )

    # Totales
    totales = resumen_distribuidor.drop(columns="distribuidor").sum().to_dict()
    totales = {k: int(v) for k, v in totales.items()}

    # Mostrar en streamlit
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("📊 Resumen por Departamento")
        st.dataframe(resumen_departamento.reset_index(drop=True), use_container_width=True)
  
    with col2:
        st.subheader("📊 Resumen por Distribuidor")
        st.dataframe(resumen_distribuidor.reset_index(drop=True), use_container_width=True)

    # Métricas
    metrics = [
        ("Vendedores", totales.get("cantidad_vendedores", 0)),
        ("Freelance", totales.get("cantidad_freelance", 0)),
        ("Digital", totales.get("cantidad_digital", 0)),
        ("Dueño", totales.get("cantidad_dueno", 0)),
        ("Supervisor", totales.get("cantidad_supervisor", 0)),
        ("Formador", totales.get("cantidad_formador", 0)),
        ("Backoffice", totales.get("cantidad_backoffice", 0)),
    ]

    for i in range(0, len(metrics), 3):
        rcols = st.columns(3)
        for c, (label, val) in zip(rcols, metrics[i:i+3]):
            c.metric(label, val)

# Mapa Perú
def mostrar_mapa(df):
      df_filtrado = df[
        (df["fecha_baja"].isna() | (df["fecha_baja"] == "")) &
        (df["fecha_blacklist"].isna() | (df["fecha_blacklist"] == "")) &
        df["cargo"].isin(["Vendedor", "Freelance"])
    ] [["nombre_colaborador_agencia","ubicacion_departamento", "coordenadas", "cargo"]]
      
    # Vendedores y freelance por departamento
      df_pivot = (
            df_filtrado
            .pivot_table(
                index="ubicacion_departamento",
                columns="cargo",
                values="nombre_colaborador_agencia",
                aggfunc="count",
                fill_value=0
            )
            .reset_index()
        )
      
      df_coordenadas = (
            df_filtrado[["ubicacion_departamento", "coordenadas"]]
            .drop_duplicates(subset=["ubicacion_departamento"])
        )
      
      df_mapa = (
            df_pivot
            .merge(df_coordenadas, on="ubicacion_departamento", how="left")
        )
      df_mapa[['lat', 'lon']] = df_mapa['coordenadas'].str.split(', ', expand=True).astype(float)
      df_mapa = df_mapa.drop(columns=['coordenadas'])

      # Normalizar Freelance para color (evitar división por cero)
      max_colabs = df_mapa['Freelance'].max() if df_mapa['Freelance'].max() > 0 else 1
      df_mapa['color_intensidad'] = (df_mapa['Freelance'] / max_colabs * 255).astype(int)

      # Ajuste del tamaño de los círculos (metros)
      # Si hay muchos vendedores, reduce el factor (p.ej. 800), si pocos, súbelo (p.ej. 2000)
      df_mapa['radio'] = df_mapa['Vendedor'] * 1500 + 5000

      # Crear capa
      layer = pdk.Layer(
            'ScatterplotLayer',
            data=df_mapa,
            get_position='[lon, lat]',
            get_fill_color='[color_intensidad, 50, 255 - color_intensidad, 180]',  # de azul a rojo
            get_radius='radio',  # tamaño según vendedores
            pickable=True,
        )
      
    # Vista centrada en Perú 🇵🇪
      view_state = pdk.ViewState(
            latitude=-9.19,   # Centro geográfico de Perú
            longitude=-75.015,
            zoom=5,
            pitch=0,
        )
      
      # Mapa
      st.pydeck_chart(pdk.Deck(
            layers=[layer],
            initial_view_state=view_state,
            tooltip={"text": "{ubicacion_departamento}\nVendedores: {Vendedor}\nFreelances: {Freelance}"}
        ))

      

      
    