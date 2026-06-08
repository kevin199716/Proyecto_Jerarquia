"""
asistencia.py FIXED - Sin file_uploader, sin congelamiento
v2.5.0
"""
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

def cargar_historico(hoja_asist):
    try:
        vals = hoja_asist.get_all_values()
        if len(vals) < 2:
            return pd.DataFrame()
        return pd.DataFrame(vals[1:], columns=vals[0])
    except:
        return pd.DataFrame()

def mostrar_asistencia(hoja_asistencia, hoja_colaboradores, registro_mod=None, razon=None):
    """Presencialidad sin congelamiento"""
    st.write("# Gestión de Descansos Médicos y Vacaciones")
    
    tab1, tab2 = st.tabs(["📝 Registrar", "📊 Histórico"])
    
    # TAB 1: REGISTRAR
    with tab1:
        st.subheader("Buscar Colaborador")
        
        df_colab = cargar_colaboradores(hoja_colaboradores)
        if df_colab.empty:
            st.error("Sin datos")
            return
        
        col1, col2 = st.columns(2)
        with col1:
            dni = st.text_input("DNI:", key="dni1")
        with col2:
            nombre = st.text_input("Nombre:", key="nom1")
        
        if st.button("🔍 Buscar", key="b1"):
            res = df_colab.copy()
            if dni.strip():
                res = res[res.get("DNI", "").astype(str).str.contains(dni, na=False)]
            if nombre.strip():
                res = res[res.get("NOMBRES", "").astype(str).str.contains(nombre, case=False, na=False)]
            
            if res.empty:
                st.warning("No encontrado")
            else:
                st.success(f"✅ {len(res)} encontrados")
                cols = ["DNI", "NOMBRES", "RAZON SOCIAL", "ESTADO"]
                st.dataframe(res[[c for c in cols if c in res.columns]], use_container_width=True, hide_index=True)
                
                if len(res) == 1:
                    c = res.iloc[0]
                else:
                    i = st.selectbox("Selecciona:", range(len(res)), 
                        format_func=lambda x: f"{res.iloc[x]['DNI']} - {res.iloc[x]['NOMBRES']}", key="sel1")
                    c = res.iloc[i]
                
                st.divider()
                st.write(f"**{c['NOMBRES']}** ({c.get('RAZON SOCIAL')})")
                
                tipo = st.radio("Tipo:", ["A-BM (Médico)", "A-VAC (Vacaciones)"], key="t1")
                f1 = st.date_input("Desde:", key="f1")
                f2 = st.date_input("Hasta:", key="f2")
                
                if st.button("💾 GUARDAR", type="primary", use_container_width=True, key="save1"):
                    if f2 < f1:
                        st.error("Fecha inválida")
                    else:
                        try:
                            marca = "A-BM" if "Médico" in tipo else "A-VAC"
                            fila = [
                                c.get("RAZON SOCIAL", ""),
                                c.get("SUPERVISOR A CARGO FINAL", ""),
                                c.get("COORDINADOR FINAL", ""),
                                c.get("DEPARTAMENTO", ""),
                                c.get("PROVINCIA", ""),
                                c.get("DISTRITO", ""),
                                c['DNI'],
                                c['NOMBRES'],
                                c.get("ESTADO", ""),
                                c.get("FECHA DE CREACION USUARIO", ""),
                                c.get("FECHA DE CESE", ""),
                                datetime.now().strftime("%Y-%m"),
                                datetime.now().strftime("%Y-%m"),
                            ]
                            
                            fa = f1
                            for d in range(1, 32):
                                if fa <= f2:
                                    fila.append(marca)
                                    fa += timedelta(days=1)
                                else:
                                    fila.append("")
                            
                            hoja_asistencia.append_row(fila)
                            st.success(f"✅ Guardado: {marca} ({f1} → {f2})")
                            
                        except Exception as e:
                            st.error(f"Error: {str(e)[:100]}")
    
    # TAB 2: HISTÓRICO
    with tab2:
        st.subheader("Histórico")
        df_h = cargar_historico(hoja_asistencia)
        
        if df_h.empty:
            st.info("Sin registros")
        else:
            mes = st.selectbox("Mes:", ["TODOS"] + sorted(df_h.get("MES", pd.Series([])).unique().tolist()), key="mes1")
            dni_f = st.text_input("DNI:", key="dni2")
            
            df_f = df_h.copy()
            if mes != "TODOS":
                df_f = df_f[df_f.get("MES", "").astype(str) == mes]
            if dni_f.strip():
                df_f = df_f[df_f.get("DNI", "").astype(str).str.contains(dni_f, na=False)]
            
            if not df_f.empty:
                cols = ["DNI", "NOMBRES", "RAZON SOCIAL", "MES"]
                st.dataframe(df_f[[c for c in cols if c in df_f.columns]], use_container_width=True, hide_index=True)
                st.write(f"**Total:** {len(df_f)} registros")
            else:
                st.warning("Sin resultados")

def sincronizar_mes(hoja_asistencia, hoja_colaboradores):
    return 0, 0
