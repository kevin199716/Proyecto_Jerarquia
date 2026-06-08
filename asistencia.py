import pandas as pd
import streamlit as st
from datetime import datetime, timedelta

def cargar_colaboradores(hoja_colab):
    try:
        vals = hoja_colab.get_all_values()
        if len(vals) < 2:
            return pd.DataFrame()
        return pd.DataFrame(vals[1:], columns=vals[0])
    except:
        return pd.DataFrame()

def mostrar_asistencia(hoja_asistencia, hoja_colaboradores, registro_mod=None, razon=None):
    st.write("## Gestion de Descansos")
    
    df = cargar_colaboradores(hoja_colaboradores)
    if df.empty:
        st.error("Sin colaboradores")
        return
    
    dni = st.text_input("DNI:")
    
    if st.button("Buscar"):
        if not dni:
            st.warning("Ingresa DNI")
            return
        
        r = df[df.get("DNI", "").astype(str).str.contains(str(dni), na=False)]
        
        if r.empty:
            st.warning("No encontrado")
        else:
            c = r.iloc[0]
            st.write(f"**{c.get('NOMBRES')}** - {c.get('DNI')}")
            
            tipo = st.radio("Tipo:", ["A-BM", "A-VAC"])
            f1 = st.date_input("Desde:")
            f2 = st.date_input("Hasta:")
            
            if st.button("Guardar"):
                if f2 >= f1:
                    try:
                        fila = [c.get("RAZON SOCIAL", ""), c.get("SUPERVISOR", ""), c.get("COORDINADOR", ""), c.get("DEPARTAMENTO", ""), c.get("PROVINCIA", ""), c.get("DISTRITO", ""), c['DNI'], c['NOMBRES'], c.get("ESTADO", ""), c.get("FECHA_ALTA", ""), c.get("FECHA_CESE", ""), datetime.now().strftime("%Y-%m"), datetime.now().strftime("%Y-%m")]
                        
                        fa = f1
                        for d in range(1, 32):
                            if fa <= f2:
                                fila.append(tipo)
                                fa += timedelta(days=1)
                            else:
                                fila.append("")
                        
                        hoja_asistencia.append_row(fila, value_input_option="USER_ENTERED")
                        st.success("Guardado!")
                    except Exception as e:
                        st.error(f"Error: {e}")

def sincronizar_mes(hoja_asistencia, hoja_colaboradores):
    return 0, 0
