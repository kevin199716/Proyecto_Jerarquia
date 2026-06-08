import pandas as pd
import streamlit as st
from datetime import datetime, timedelta

def cargar_colaboradores(hoja_colab):
    try:
        valores = hoja_colab.get_all_values()
        if not valores:
            return pd.DataFrame()
        headers = [str(h).upper().strip() for h in valores[0]]
        df = pd.DataFrame(valores[1:], columns=headers)
        return df
    except:
        return pd.DataFrame()

def mostrar_asistencia(hoja_asistencia, hoja_colaboradores, registro_mod=None, razon=None):
    st.title("Gestion de Descansos")
    df_colab = cargar_colaboradores(hoja_colaboradores)
    if df_colab.empty:
        st.error("Sin datos")
        return
    st.write("Busca colaborador")
    dni = st.text_input("DNI:")
    if st.button("BUSCAR"):
        resultado = df_colab.copy()
        if dni:
            resultado = resultado[resultado.get("DNI", "").astype(str).str.contains(dni, na=False)]
        if resultado.empty:
            st.warning("Sin resultados")
        else:
            st.success(f"Encontrados: {len(resultado)}")
            cols = ["DNI", "NOMBRES", "RAZON SOCIAL"]
            st.dataframe(resultado[[c for c in cols if c in resultado.columns]])
            colab = resultado.iloc[0]
            st.write(f"DNI: {colab['DNI']}")
            st.write(f"Nombre: {colab['NOMBRES']}")
            tipo = st.radio("Tipo:", ["Descanso Medico", "Vacaciones"])
            fecha_ini = st.date_input("Desde:")
            fecha_fin = st.date_input("Hasta:")
            if st.button("GUARDAR"):
                if fecha_fin >= fecha_ini:
                    try:
                        tipo_mark = "A-BM" if "Medico" in tipo else "A-VAC"
                        fila = [str(colab.get("RAZON SOCIAL", "")), str(colab.get("SUPERVISOR A CARGO FINAL", "")), str(colab.get("COORDINADOR FINAL", "")), str(colab.get("DEPARTAMENTO", "")), str(colab.get("PROVINCIA", "")), str(colab.get("DISTRITO", "")), str(colab['DNI']), str(colab['NOMBRES']), str(colab.get("ESTADO", "")), str(colab.get("FECHA DE CREACION USUARIO", "")), str(colab.get("FECHA DE CESE", "")), datetime.now().strftime("%Y-%m"), datetime.now().strftime("%Y-%m")]
                        fecha_act = fecha_ini
                        for d in range(1, 32):
                            if fecha_act <= fecha_fin:
                                fila.append(tipo_mark)
                                fecha_act += timedelta(days=1)
                            else:
                                fila.append("")
                        hoja_asistencia.append_row(fila, value_input_option="USER_ENTERED")
                        st.success("GUARDADO CORRECTAMENTE")
                    except Exception as e:
                        st.error(f"Error: {e}")
                else:
                    st.error("Fecha invalida")

def sincronizar_mes(hoja_asistencia, hoja_colaboradores):
    return 0, 0
