"""asistencia.py - SIMPLE Y FUNCIONAL v3"""
import pandas as pd
import streamlit as st
from datetime import datetime, timedelta

@st.cache_data(ttl=60)
def cargar_colaboradores(hoja_colab):
    try:
        valores = hoja_colab.get_all_values()
        if not valores:
            return pd.DataFrame()
        headers = [h.upper().strip() for h in valores[0]]
        return pd.DataFrame(valores[1:], columns=headers)
    except:
        return pd.DataFrame()

def mostrar_asistencia(hoja_asistencia, hoja_colaboradores, registro_mod=None, razon=None):
    st.markdown("### 📋 Gestión de Descansos Médicos y Vacaciones")
    
    df_colab = cargar_colaboradores(hoja_colaboradores)
    if df_colab.empty:
        st.error("❌ Sin datos de colaboradores")
        return
    
    # BÚSQUEDA
    st.markdown("**🔍 Buscar Colaborador**")
    col1, col2 = st.columns(2)
    with col1:
        dni = st.text_input("DNI", placeholder="Ej: 12345678").strip()
    with col2:
        nombre = st.text_input("Nombre", placeholder="Ej: Juan").strip()
    
    if st.button("🔎 BUSCAR"):
        # Buscar en colaboradores
        resultado = df_colab.copy()
        if dni:
            resultado = resultado[resultado.get("DNI", "").astype(str).str.contains(dni, na=False)]
        if nombre:
            resultado = resultado[resultado.get("NOMBRES", "").astype(str).str.contains(nombre, case=False, na=False)]
        
        if not resultado.empty:
            st.success(f"✅ Encontrados: {len(resultado)}")
            
            # Mostrar tabla
            cols = ["DNI", "NOMBRES", "RAZON SOCIAL", "SUPERVISOR A CARGO FINAL", "COORDINADOR FINAL", "ESTADO"]
            df_show = resultado[[c for c in cols if c in resultado.columns]]
            st.dataframe(df_show, use_container_width=True, hide_index=True)
            
            # REGISTRAR DESCANSO
            st.markdown("**📝 Registrar Descanso**")
            
            if len(resultado) == 1:
                colab = resultado.iloc[0]
            else:
                idx = st.selectbox("Selecciona", range(len(resultado)), format_func=lambda i: f"{resultado.iloc[i]['DNI']} - {resultado.iloc[i]['NOMBRES']}")
                colab = resultado.iloc[idx]
            
            # Mostrar datos del colaborador
            st.write(f"**DNI:** {colab.get('DNI')}")
            st.write(f"**Nombre:** {colab.get('NOMBRES')}")
            st.write(f"**Supervisor:** {colab.get('SUPERVISOR A CARGO FINAL')}")
            st.write(f"**Coordinador:** {colab.get('COORDINADOR FINAL')}")
            st.write(f"**Razón Social:** {colab.get('RAZON SOCIAL')}")
            
            # Formulario descanso
            tipo = st.radio("Tipo", ["Descanso Médico (A-BM)", "Vacaciones (A-VAC)"], horizontal=True)
            
            col1, col2 = st.columns(2)
            with col1:
                fecha_ini = st.date_input("Desde")
            with col2:
                fecha_fin = st.date_input("Hasta")
            
            archivos = st.file_uploader("Documentos", accept_multiple_files=True)
            
            if st.button("💾 GUARDAR", type="primary"):
                if fecha_fin < fecha_ini:
                    st.error("❌ Fecha fin debe ser mayor")
                else:
                    # GUARDAR EN ASISTENCIA
                    tipo_mark = "A-BM" if "Médico" in tipo else "A-VAC"
                    
                    fila = [
                        colab.get("RAZON SOCIAL", ""),
                        colab.get("SUPERVISOR A CARGO FINAL", ""),
                        colab.get("COORDINADOR FINAL", ""),
                        colab.get("DEPARTAMENTO", ""),
                        colab.get("PROVINCIA", ""),
                        colab.get("DISTRITO", ""),
                        colab.get("DNI", ""),
                        colab.get("NOMBRES", ""),
                        colab.get("ESTADO", ""),
                        colab.get("FECHA DE CREACION USUARIO", ""),
                        colab.get("FECHA DE CESE", ""),
                        datetime.now().strftime("%Y-%m"),
                        datetime.now().strftime("%Y-%m"),
                    ]
                    
                    # Agregar días (DIA_1 a DIA_31)
                    fecha_act = fecha_ini
                    for d in range(1, 32):
                        if fecha_act <= fecha_fin:
                            fila.append(tipo_mark)
                            fecha_act += timedelta(days=1)
                        else:
                            fila.append("")
                    
                    # Guardar en Asistencia
                    try:
                        hoja_asistencia.append_row(fila, value_input_option="USER_ENTERED")
                        st.success(f"✅ {tipo_mark} guardado")
                        st.info(f"📅 {fecha_ini} → {fecha_fin}")
                        if archivos:
                            st.success(f"📎 {len(archivos)} documento(s)")
                    except Exception as e:
                        st.error(f"❌ Error: {e}")
        else:
            st.warning("⚠️ Sin resultados")

def sincronizar_mes(hoja_asistencia, hoja_colaboradores):
    return 0, 0
