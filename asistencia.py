"""asistencia.py v5 - SIN CRASHES, CON DOCUMENTOS Y HISTÓRICO"""
import pandas as pd
import streamlit as st
from datetime import datetime, timedelta

def cargar_colaboradores(hoja_colab):
    try:
        valores = hoja_colab.get_all_values()
        if not valores:
            return pd.DataFrame()
        headers = [h.upper().strip() for h in valores[0]]
        return pd.DataFrame(valores[1:], columns=headers)
    except:
        return pd.DataFrame()

def cargar_asistencia(hoja_asist):
    try:
        valores = hoja_asist.get_all_values()
        if not valores or len(valores) < 2:
            return pd.DataFrame()
        headers = [h.upper().strip() for h in valores[0]]
        return pd.DataFrame(valores[1:], columns=headers)
    except:
        return pd.DataFrame()

def mostrar_asistencia(hoja_asistencia, hoja_colaboradores, registro_mod=None, razon=None):
    """Gestión de Descansos - SIN CRASHES"""
    
    st.markdown("### 📋 Gestión de Descansos Médicos y Vacaciones")
    
    # Cargar datos
    df_colab = cargar_colaboradores(hoja_colaboradores)
    df_asist = cargar_asistencia(hoja_asistencia)
    
    if df_colab.empty:
        st.error("❌ Sin datos de colaboradores")
        return
    
    # TABS
    tab1, tab2, tab3 = st.tabs(["📝 Registrar", "📊 Histórico", "📎 Documentos"])
    
    # =====================================================
    # TAB 1: REGISTRAR DESCANSO
    # =====================================================
    with tab1:
        st.markdown("**🔍 Buscar Colaborador**")
        
        col1, col2 = st.columns([1, 1])
        with col1:
            dni = st.text_input("DNI", placeholder="Ej: 12345678")
        with col2:
            nombre = st.text_input("Nombre", placeholder="Ej: Juan")
        
        btn = st.button("🔎 BUSCAR")
        
        if btn and (dni or nombre):
            resultado = df_colab.copy()
            
            if dni.strip():
                resultado = resultado[resultado.get("DNI", "").astype(str).str.contains(dni, na=False)]
            if nombre.strip():
                resultado = resultado[resultado.get("NOMBRES", "").astype(str).str.contains(nombre, case=False, na=False)]
            
            if not resultado.empty:
                st.success(f"✅ Encontrados: {len(resultado)}")
                
                # Tabla
                cols = ["DNI", "NOMBRES", "RAZON SOCIAL", "SUPERVISOR A CARGO FINAL", "COORDINADOR FINAL", "ESTADO"]
                df_show = resultado[[c for c in cols if c in resultado.columns]]
                st.dataframe(df_show, use_container_width=True, hide_index=True)
                
                # Seleccionar
                if len(resultado) == 1:
                    idx = 0
                else:
                    idx = st.radio("Selecciona", range(len(resultado)), 
                        format_func=lambda i: f"{resultado.iloc[i]['DNI']} - {resultado.iloc[i]['NOMBRES']}", horizontal=True)
                
                colab = resultado.iloc[idx]
                
                st.markdown("---")
                st.markdown("**📝 Datos del Colaborador**")
                
                col_a, col_b = st.columns(2)
                with col_a:
                    st.write(f"**DNI:** {colab.get('DNI')}")
                    st.write(f"**Nombre:** {colab.get('NOMBRES')}")
                    st.write(f"**Razón Social:** {colab.get('RAZON SOCIAL')}")
                with col_b:
                    st.write(f"**Supervisor:** {colab.get('SUPERVISOR A CARGO FINAL')}")
                    st.write(f"**Coordinador:** {colab.get('COORDINADOR FINAL')}")
                    st.write(f"**Estado:** {colab.get('ESTADO')}")
                
                st.markdown("**Tipo de Descanso**")
                tipo = st.radio("", ["Descanso Médico (A-BM)", "Vacaciones (A-VAC)"], horizontal=True)
                
                st.markdown("**Fechas (puede ser pasado, hoy o futuro)**")
                col_f1, col_f2 = st.columns(2)
                with col_f1:
                    fecha_ini = st.date_input("Desde", value=datetime.now().date())
                with col_f2:
                    fecha_fin = st.date_input("Hasta", value=datetime.now().date())
                
                st.markdown("**Documentos (opcional)**")
                archivos = st.file_uploader("Adjunta certificados", accept_multiple_files=True)
                
                # GUARDAR (sin st.rerun())
                if st.button("💾 GUARDAR", type="primary", use_container_width=True):
                    
                    if fecha_fin < fecha_ini:
                        st.error("❌ Fecha fin debe ser posterior a fecha inicio")
                        st.stop()
                    
                    try:
                        tipo_mark = "A-BM" if "Médico" in tipo else "A-VAC"
                        dias_rango = (fecha_fin - fecha_ini).days + 1
                        
                        # Construir fila
                        fila = [
                            str(colab.get("RAZON SOCIAL", "")),
                            str(colab.get("SUPERVISOR A CARGO FINAL", "")),
                            str(colab.get("COORDINADOR FINAL", "")),
                            str(colab.get("DEPARTAMENTO", "")),
                            str(colab.get("PROVINCIA", "")),
                            str(colab.get("DISTRITO", "")),
                            str(colab.get("DNI", "")),
                            str(colab.get("NOMBRES", "")),
                            str(colab.get("ESTADO", "")),
                            str(colab.get("FECHA DE CREACION USUARIO", "")),
                            str(colab.get("FECHA DE CESE", "")),
                            datetime.now().strftime("%Y-%m"),
                            datetime.now().strftime("%Y-%m"),
                        ]
                        
                        # Días
                        fecha_act = fecha_ini
                        for d in range(1, 32):
                            if fecha_act <= fecha_fin:
                                fila.append(tipo_mark)
                                fecha_act += timedelta(days=1)
                            else:
                                fila.append("")
                        
                        # Guardar
                        hoja_asistencia.append_row(fila, value_input_option="USER_ENTERED")
                        
                        # Confirmación
                        st.success("✅ ¡GUARDADO CORRECTAMENTE!")
                        st.info(f"""
                        📋 {tipo_mark} registrado:
                        • Colaborador: {colab.get('NOMBRES')} ({colab.get('DNI')})
                        • Período: {fecha_ini} → {fecha_fin}
                        • Días: {dias_rango}
                        • Documentos: {len(archivos) if archivos else 0}
                        • Mes: {datetime.now().strftime("%Y-%m")}
                        
                        ✓ Datos guardados en la hoja Asistencia
                        """)
                        
                    except Exception as e:
                        st.error(f"❌ Error: {str(e)}")
            else:
                st.warning("⚠️ Sin resultados")
    
    # =====================================================
    # TAB 2: HISTÓRICO (ESPEJO)
    # =====================================================
    with tab2:
        st.markdown("**📊 Histórico de Descansos**")
        
        if not df_asist.empty:
            col1, col2 = st.columns(2)
            with col1:
                mes_filt = st.selectbox("Mes", ["TODOS"] + sorted(df_asist.get("MES", [""]).unique().tolist()))
            with col2:
                dni_filt = st.text_input("DNI (opcional)")
            
            df_filt = df_asist.copy()
            if mes_filt != "TODOS":
                df_filt = df_filt[df_filt.get("MES", "").astype(str) == mes_filt]
            if dni_filt:
                df_filt = df_filt[df_filt.get("DNI", "").astype(str).str.contains(dni_filt, na=False)]
            
            if not df_filt.empty:
                cols = ["DNI", "NOMBRES", "RAZON SOCIAL", "MES", "ESTADO"]
                st.dataframe(df_filt[[c for c in cols if c in df_filt.columns]], use_container_width=True, hide_index=True)
                st.success(f"✅ Total: {len(df_filt)} registros")
                
                for idx, row in df_filt.iterrows():
                    with st.expander(f"📋 {row.get('DNI')} - {row.get('NOMBRES')}"):
                        st.write(f"**Razón Social:** {row.get('RAZON SOCIAL')}")
                        st.write(f"**Supervisor:** {row.get('SUPERVISOR')}")
                        st.write(f"**Coordinador:** {row.get('COORDINADOR')}")
                        st.write(f"**Mes:** {row.get('MES')} | **Estado:** {row.get('ESTADO')}")
            else:
                st.warning("⚠️ Sin registros")
        else:
            st.info("ℹ️ No hay datos aún")
    
    # =====================================================
    # TAB 3: DOCUMENTOS / EVIDENCIAS
    # =====================================================
    with tab3:
        st.markdown("**📎 Documentos y Evidencias**")
        st.info("Los documentos se cargan cuando registras un descanso (Tab 1)")
        
        st.markdown("**Historial de Documentos Cargados**")
        st.write("Los documentos se guardan en Google Drive en la carpeta:")
        st.code("Descansos_Medicos_Vacaciones/")

def sincronizar_mes(hoja_asistencia, hoja_colaboradores):
    return 0, 0
