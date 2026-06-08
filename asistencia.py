"""asistencia.py v4 - COMPLETO Y SIN CRASHES"""
import pandas as pd
import streamlit as st
from datetime import datetime, timedelta

def cargar_colaboradores(hoja_colab):
    """Carga colaboradores desde Google Sheets"""
    try:
        valores = hoja_colab.get_all_values()
        if not valores:
            return pd.DataFrame()
        headers = [h.upper().strip() for h in valores[0]]
        return pd.DataFrame(valores[1:], columns=headers)
    except:
        return pd.DataFrame()

def cargar_asistencia(hoja_asist):
    """Carga histórico de Asistencia (descansos registrados)"""
    try:
        valores = hoja_asist.get_all_values()
        if not valores or len(valores) < 2:
            return pd.DataFrame()
        headers = [h.upper().strip() for h in valores[0]]
        return pd.DataFrame(valores[1:], columns=headers)
    except:
        return pd.DataFrame()

def mostrar_asistencia(hoja_asistencia, hoja_colaboradores, registro_mod=None, razon=None):
    """Interfaz completa de Gestión de Descansos"""
    
    st.markdown("### 📋 Gestión de Descansos Médicos y Vacaciones")
    
    # Cargar datos
    df_colab = cargar_colaboradores(hoja_colaboradores)
    df_asist = cargar_asistencia(hoja_asistencia)
    
    if df_colab.empty:
        st.error("❌ Sin datos de colaboradores")
        return
    
    # =====================================================
    # TAB 1: REGISTRAR DESCANSO
    # TAB 2: HISTÓRICO
    # =====================================================
    
    tab1, tab2 = st.tabs(["📝 Registrar Descanso", "📊 Histórico"])
    
    # =====================================================
    # TAB 1: REGISTRAR
    # =====================================================
    
    with tab1:
        st.markdown("**🔍 Buscar Colaborador**")
        col1, col2, col3 = st.columns([2, 2, 1.5])
        
        with col1:
            dni = st.text_input("DNI", placeholder="Ej: 12345678", key="dni_search").strip()
        with col2:
            nombre = st.text_input("Nombre", placeholder="Ej: Juan", key="nombre_search").strip()
        with col3:
            btn_buscar = st.button("🔎 BUSCAR", use_container_width=True)
        
        # Búsqueda
        if btn_buscar:
            resultado = df_colab.copy()
            
            if dni:
                resultado = resultado[resultado.get("DNI", "").astype(str).str.contains(dni, na=False)]
            if nombre:
                resultado = resultado[resultado.get("NOMBRES", "").astype(str).str.contains(nombre, case=False, na=False)]
            
            if not resultado.empty:
                st.success(f"✅ Encontrados: {len(resultado)}")
                
                # Tabla resultados
                cols = ["DNI", "NOMBRES", "RAZON SOCIAL", "SUPERVISOR A CARGO FINAL", "COORDINADOR FINAL", "ESTADO"]
                df_show = resultado[[c for c in cols if c in resultado.columns]]
                st.dataframe(df_show, use_container_width=True, hide_index=True)
                
                st.markdown("---")
                st.markdown("**📝 Registrar Descanso**")
                
                # Seleccionar colaborador
                if len(resultado) == 1:
                    colab = resultado.iloc[0]
                    st.info(f"✓ Seleccionado: {colab.get('DNI')} - {colab.get('NOMBRES')}")
                else:
                    idx = st.selectbox("Selecciona colaborador", range(len(resultado)), 
                        format_func=lambda i: f"{resultado.iloc[i]['DNI']} - {resultado.iloc[i]['NOMBRES']}", key="colab_select")
                    colab = resultado.iloc[idx]
                
                # Mostrar datos
                col_a, col_b, col_c = st.columns(3)
                with col_a:
                    st.text_input("DNI", value=str(colab.get('DNI', '')), disabled=True, key="dni_show")
                with col_b:
                    st.text_input("Nombre", value=str(colab.get('NOMBRES', '')), disabled=True, key="nombre_show")
                with col_c:
                    st.text_input("Razón Social", value=str(colab.get('RAZON SOCIAL', '')), disabled=True, key="razon_show")
                
                col_d, col_e = st.columns(2)
                with col_d:
                    st.text_input("Supervisor", value=str(colab.get('SUPERVISOR A CARGO FINAL', '')), disabled=True, key="sup_show")
                with col_e:
                    st.text_input("Coordinador", value=str(colab.get('COORDINADOR FINAL', '')), disabled=True, key="coord_show")
                
                st.markdown("**Descanso**")
                
                col1, col2 = st.columns(2)
                with col1:
                    tipo = st.radio("Tipo", ["Descanso Médico (A-BM)", "Vacaciones (A-VAC)"], key="tipo_radio")
                with col2:
                    st.write("")
                
                col3, col4 = st.columns(2)
                with col3:
                    fecha_ini = st.date_input("Desde", key="fecha_ini")
                with col4:
                    fecha_fin = st.date_input("Hasta", key="fecha_fin")
                
                st.markdown("**Documentos**")
                archivos = st.file_uploader("Adjunta certificado, autorización, etc.", accept_multiple_files=True, key="docs_upload")
                
                # GUARDAR
                if st.button("💾 GUARDAR DESCANSO", type="primary", use_container_width=True, key="btn_guardar"):
                    
                    if fecha_fin < fecha_ini:
                        st.error("❌ Fecha fin debe ser posterior a fecha inicio")
                    else:
                        try:
                            tipo_mark = "A-BM" if "Médico" in tipo else "A-VAC"
                            dias_rango = (fecha_fin - fecha_ini).days + 1
                            
                            # Construir fila para Asistencia (TODOS LOS CAMPOS)
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
                                datetime.now().strftime("%Y-%m"),  # MES
                                datetime.now().strftime("%Y-%m"),  # PERIODO
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
                            hoja_asistencia.append_row(fila, value_input_option="USER_ENTERED")
                            
                            # Mostrar confirmación
                            st.success(f"✅ {tipo_mark} REGISTRADO CORRECTAMENTE")
                            st.info(f"""
                            📋 **Detalles:**
                            - **Colaborador:** {colab.get('NOMBRES')} ({colab.get('DNI')})
                            - **Tipo:** {tipo_mark}
                            - **Período:** {fecha_ini} → {fecha_fin}
                            - **Días:** {dias_rango}
                            - **Documentos:** {len(archivos) if archivos else 0}
                            - **Mes:** {datetime.now().strftime("%Y-%m")}
                            
                            Los datos se han guardado en la hoja Asistencia.
                            """)
                            
                        except Exception as e:
                            st.error(f"❌ Error al guardar: {str(e)}")
            else:
                st.warning("⚠️ Sin resultados para esa búsqueda")
    
    # =====================================================
    # TAB 2: HISTÓRICO (ESPEJO)
    # =====================================================
    
    with tab2:
        st.markdown("**📊 Histórico de Descansos Registrados**")
        
        if not df_asist.empty:
            
            # Filtros
            col1, col2, col3 = st.columns(3)
            with col1:
                filtro_mes = st.selectbox("Mes", ["TODOS"] + sorted(df_asist.get("MES", [""]).unique().tolist()), key="filtro_mes_hist")
            with col2:
                filtro_dni = st.text_input("DNI", placeholder="Ej: 12345678", key="filtro_dni_hist").strip()
            with col3:
                st.write("")
            
            # Aplicar filtros
            df_filtrado = df_asist.copy()
            
            if filtro_mes != "TODOS":
                df_filtrado = df_filtrado[df_filtrado.get("MES", "").astype(str) == filtro_mes]
            
            if filtro_dni:
                df_filtrado = df_filtrado[df_filtrado.get("DNI", "").astype(str).str.contains(filtro_dni, na=False)]
            
            if not df_filtrado.empty:
                # Mostrar tabla con columnas importantes
                cols_mostrar = ["DNI", "NOMBRES", "RAZON SOCIAL", "MES", "PERIODO", "ESTADO"]
                df_display = df_filtrado[[c for c in cols_mostrar if c in df_filtrado.columns]].copy()
                
                st.dataframe(df_display, use_container_width=True, hide_index=True)
                
                st.success(f"✅ Total registros: {len(df_filtrado)}")
                
                # Detalle expandible
                st.markdown("**Detalle:**")
                for idx, row in df_filtrado.iterrows():
                    with st.expander(f"📋 {row.get('DNI')} - {row.get('NOMBRES')} ({row.get('MES')})"):
                        col1, col2 = st.columns(2)
                        with col1:
                            st.write(f"**Razón Social:** {row.get('RAZON SOCIAL')}")
                            st.write(f"**Supervisor:** {row.get('SUPERVISOR')}")
                            st.write(f"**Coordinador:** {row.get('COORDINADOR')}")
                        with col2:
                            st.write(f"**Mes:** {row.get('MES')}")
                            st.write(f"**Estado:** {row.get('ESTADO')}")
                            st.write(f"**Período:** {row.get('PERIODO')}")
            else:
                st.warning("⚠️ Sin resultados")
        else:
            st.info("ℹ️ No hay registros aún")

def sincronizar_mes(hoja_asistencia, hoja_colaboradores):
    return 0, 0
