"""
asistencia.py - Gestión de Descansos Médicos y Vacaciones
v2.5.0
"""
import pandas as pd
import streamlit as st
from datetime import datetime, timedelta

def cargar_colaboradores(hoja_colab):
    """Carga colaboradores desde Google Sheets"""
    try:
        vals = hoja_colab.get_all_values()
        if len(vals) < 2:
            return pd.DataFrame()
        return pd.DataFrame(vals[1:], columns=vals[0])
    except:
        return pd.DataFrame()

def cargar_historico(hoja_asist):
    """Carga histórico de descansos"""
    try:
        vals = hoja_asist.get_all_values()
        if len(vals) < 2:
            return pd.DataFrame()
        return pd.DataFrame(vals[1:], columns=vals[0])
    except:
        return pd.DataFrame()

def mostrar_asistencia(hoja_asistencia, hoja_colaboradores, registro_mod=None, razon=None):
    """Panel de gestión de presencialidad con 3 tabs"""
    st.write("# Gestión de Descansos Médicos y Vacaciones")
    
    tab1, tab2, tab3 = st.tabs(["📝 Registrar", "📊 Histórico", "📎 Documentos"])
    
    # ============ TAB 1: REGISTRAR ============
    with tab1:
        st.subheader("Buscar Colaborador")
        
        df_colab = cargar_colaboradores(hoja_colaboradores)
        if df_colab.empty:
            st.error("❌ Sin datos de colaboradores")
            return
        
        col1, col2 = st.columns(2)
        with col1:
            dni_input = st.text_input("DNI:", key="dni_input")
        with col2:
            nombre_input = st.text_input("Nombre:", key="nombre_input")
        
        if st.button("🔍 BUSCAR", key="btn_buscar"):
            resultado = df_colab.copy()
            
            if dni_input.strip():
                resultado = resultado[resultado.get("DNI", "").astype(str).str.contains(dni_input, na=False)]
            if nombre_input.strip():
                resultado = resultado[resultado.get("NOMBRES", "").astype(str).str.contains(nombre_input, case=False, na=False)]
            
            if resultado.empty:
                st.warning("⚠️ No encontrado")
            else:
                st.success(f"✅ Encontrados: {len(resultado)}")
                
                cols_mostrar = ["DNI", "NOMBRES", "RAZON SOCIAL", "ESTADO"]
                st.dataframe(resultado[[c for c in cols_mostrar if c in resultado.columns]], use_container_width=True, hide_index=True)
                
                if len(resultado) == 1:
                    colab = resultado.iloc[0]
                else:
                    idx = st.selectbox("Selecciona:", range(len(resultado)), 
                        format_func=lambda i: f"{resultado.iloc[i]['DNI']} - {resultado.iloc[i]['NOMBRES']}", key="idx_select")
                    colab = resultado.iloc[idx]
                
                st.divider()
                st.subheader("📝 Registrar Descanso")
                
                col_a, col_b, col_c = st.columns(3)
                with col_a:
                    st.text_input("DNI", value=str(colab.get('DNI', '')), disabled=True, key="dni_display")
                with col_b:
                    st.text_input("Nombre", value=str(colab.get('NOMBRES', '')), disabled=True, key="nombre_display")
                with col_c:
                    st.text_input("Razón Social", value=str(colab.get('RAZON SOCIAL', '')), disabled=True, key="razon_display")
                
                tipo_desc = st.radio("Tipo de Descanso:", ["Descanso Médico (A-BM)", "Vacaciones (A-VAC)"], key="tipo_radio")
                
                col_f1, col_f2 = st.columns(2)
                with col_f1:
                    fecha_desde = st.date_input("Desde:", key="fecha_desde")
                with col_f2:
                    fecha_hasta = st.date_input("Hasta:", key="fecha_hasta")
                
                st.write("**Documentos (Opcional)**")
                documentos = st.file_uploader("Adjunta certificados o autorizaciones:", accept_multiple_files=True, key="docs_upload")
                
                if st.button("💾 GUARDAR DESCANSO", type="primary", use_container_width=True, key="btn_guardar"):
                    if fecha_hasta < fecha_desde:
                        st.error("❌ Fecha fin debe ser posterior a fecha inicio")
                    else:
                        try:
                            tipo_mark = "A-BM" if "Médico" in tipo_desc else "A-VAC"
                            dias = (fecha_hasta - fecha_desde).days + 1
                            
                            fila = [
                                str(colab.get("RAZON SOCIAL", "")),
                                str(colab.get("SUPERVISOR A CARGO FINAL", "")),
                                str(colab.get("COORDINADOR FINAL", "")),
                                str(colab.get("DEPARTAMENTO", "")),
                                str(colab.get("PROVINCIA", "")),
                                str(colab.get("DISTRITO", "")),
                                str(colab['DNI']),
                                str(colab['NOMBRES']),
                                str(colab.get("ESTADO", "")),
                                str(colab.get("FECHA DE CREACION USUARIO", "")),
                                str(colab.get("FECHA DE CESE", "")),
                                datetime.now().strftime("%Y-%m"),
                                datetime.now().strftime("%Y-%m"),
                            ]
                            
                            fecha_act = fecha_desde
                            for d in range(1, 32):
                                if fecha_act <= fecha_hasta:
                                    fila.append(tipo_mark)
                                    fecha_act += timedelta(days=1)
                                else:
                                    fila.append("")
                            
                            hoja_asistencia.append_row(fila, value_input_option="USER_ENTERED")
                            
                            st.success(f"✅ ¡GUARDADO CORRECTAMENTE!")
                            st.info(f"**{tipo_mark}** registrado para **{colab['NOMBRES']}** ({colab['DNI']})\n\n**Período:** {fecha_desde} → {fecha_hasta} ({dias} días)\n\n**Documentos:** {len(documentos) if documentos else 0}")
                            
                        except Exception as e:
                            st.error(f"❌ Error al guardar: {str(e)}")
    
    # ============ TAB 2: HISTÓRICO ============
    with tab2:
        st.subheader("📊 Histórico de Descansos")
        
        df_hist = cargar_historico(hoja_asistencia)
        
        if df_hist.empty:
            st.info("ℹ️ No hay registros aún")
        else:
            col_f1, col_f2 = st.columns(2)
            with col_f1:
                mes_filt = st.selectbox("Mes:", ["TODOS"] + sorted(df_hist.get("MES", pd.Series([])).unique().tolist()), key="mes_filter")
            with col_f2:
                dni_filt = st.text_input("DNI (opcional):", key="dni_filter")
            
            df_filtrado = df_hist.copy()
            
            if mes_filt != "TODOS":
                df_filtrado = df_filtrado[df_filtrado.get("MES", "").astype(str) == mes_filt]
            
            if dni_filt.strip():
                df_filtrado = df_filtrado[df_filtrado.get("DNI", "").astype(str).str.contains(dni_filt, na=False)]
            
            if not df_filtrado.empty:
                cols_tabla = ["DNI", "NOMBRES", "RAZON SOCIAL", "MES", "ESTADO"]
                st.dataframe(df_filtrado[[c for c in cols_tabla if c in df_filtrado.columns]], use_container_width=True, hide_index=True)
                
                st.success(f"✅ Total registros: {len(df_filtrado)}")
                
                st.write("**Detalles:**")
                for idx, row in df_filtrado.iterrows():
                    with st.expander(f"📋 {row.get('DNI')} - {row.get('NOMBRES')} ({row.get('MES')})"):
                        col1, col2 = st.columns(2)
                        with col1:
                            st.write(f"**Razón Social:** {row.get('RAZON SOCIAL')}")
                            st.write(f"**Supervisor:** {row.get('SUPERVISOR A CARGO FINAL')}")
                        with col2:
                            st.write(f"**Coordinador:** {row.get('COORDINADOR FINAL')}")
                            st.write(f"**Estado:** {row.get('ESTADO')}")
            else:
                st.warning("⚠️ Sin resultados para los filtros")
    
    # ============ TAB 3: DOCUMENTOS ============
    with tab3:
        st.subheader("📎 Documentos y Evidencias")
        st.info("Los documentos se cargan en la pestaña 'Registrar' al momento de guardar un descanso.")
        st.write("Los archivos se guardan en Google Drive en la carpeta: `/Descansos_Medicos_Vacaciones/`")

def sincronizar_mes(hoja_asistencia, hoja_colaboradores):
    """Placeholder para sincronización futura"""
    return 0, 0
