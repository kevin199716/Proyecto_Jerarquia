"""
asistencia.py v4.0
- Guarda en hoja Asistencia (DIA_1..DIA_31)
- Guarda documentos en hoja Sustentos_Bajas
- Tab Espejo: vista de Sustentos_Bajas
- Tab Documentos: links con metadata completa
- Sin congelamiento (session_state)
"""
import pandas as pd
import streamlit as st
from datetime import datetime, timedelta


def _cargar_df(hoja):
    try:
        vals = hoja.get_all_values()
        if len(vals) < 2:
            return pd.DataFrame()
        df = pd.DataFrame(vals[1:], columns=vals[0])
        df.columns = [c.strip().upper() for c in df.columns]
        return df
    except Exception as e:
        st.error(f"Error cargando datos: {e}")
        return pd.DataFrame()


def _subir_doc(archivo):
    try:
        from sheets import subir_archivo_drive
        url = subir_archivo_drive(
            nombre_archivo=archivo.name,
            contenido_bytes=archivo.read(),
            mime_type=archivo.type or "application/octet-stream",
        )
        return url, None
    except Exception as e:
        return None, str(e)


def mostrar_asistencia(hoja_asistencia, hoja_colaboradores, hoja_sustentos=None, registro_mod=None, razon=None):

    # Init session_state
    for k, v in [("asist_colab", None), ("asist_guardado", None)]:
        if k not in st.session_state:
            st.session_state[k] = v

    st.write("# Gestión de Descansos Médicos y Vacaciones")

    tab_reg, tab_espejo, tab_docs = st.tabs(["📝 Registrar", "📊 Espejo", "📎 Documentos"])

    # ══════════════════════════════════════════════════════
    # TAB 1 — REGISTRAR
    # ══════════════════════════════════════════════════════
    with tab_reg:
        df_colab = _cargar_df(hoja_colaboradores)
        if df_colab.empty:
            st.error("❌ Sin datos de colaboradores")
            return

        st.subheader("1️⃣ Buscar colaborador")
        c1, c2 = st.columns(2)
        with c1:
            dni_in = st.text_input("DNI:", key="asist_dni_in")
        with c2:
            nom_in = st.text_input("Nombre:", key="asist_nom_in")

        if st.button("🔍 Buscar", key="asist_btn_buscar"):
            res = df_colab.copy()
            if dni_in.strip():
                res = res[res.get("DNI", pd.Series(dtype=str)).astype(str).str.contains(dni_in.strip(), na=False)]
            if nom_in.strip():
                res = res[res.get("NOMBRES", pd.Series(dtype=str)).astype(str).str.contains(nom_in.strip(), case=False, na=False)]

            if res.empty:
                st.session_state["asist_colab"] = None
                st.warning("⚠️ No encontrado")
            else:
                st.session_state["asist_colab"] = res.iloc[0].to_dict()
                visibles = ["DNI", "NOMBRES", "RAZON SOCIAL", "ESTADO"]
                st.success(f"✅ {len(res)} resultado(s)")
                st.dataframe(res[[c for c in visibles if c in res.columns]], use_container_width=True, hide_index=True)

        colab = st.session_state.get("asist_colab")
        if colab:
            st.divider()
            st.subheader("2️⃣ Registrar descanso")

            ca, cb, cc = st.columns(3)
            with ca:
                st.text_input("DNI", value=str(colab.get("DNI", "")), disabled=True, key="asist_d_dni")
            with cb:
                st.text_input("Nombre", value=str(colab.get("NOMBRES", "")), disabled=True, key="asist_d_nom")
            with cc:
                st.text_input("Razón Social", value=str(colab.get("RAZON SOCIAL", "")), disabled=True, key="asist_d_rs")

            tipo = st.radio(
                "Tipo de ausencia:",
                ["🏥 Descanso Médico (A-BM)", "✈️ Vacaciones (A-VAC)"],
                key="asist_tipo",
            )
            cf1, cf2 = st.columns(2)
            with cf1:
                f_ini = st.date_input("Fecha inicio:", key="asist_f_ini")
            with cf2:
                f_fin = st.date_input("Fecha fin:", key="asist_f_fin")

            st.subheader("3️⃣ Adjuntar documentos (opcional)")
            docs = st.file_uploader(
                "Certificados, autorizaciones, fotos:",
                accept_multiple_files=True,
                key="asist_docs",
            )

            if st.button("💾 GUARDAR DESCANSO", type="primary", use_container_width=True, key="asist_btn_guardar"):
                if f_fin < f_ini:
                    st.error("❌ La fecha fin no puede ser anterior a la fecha inicio")
                else:
                    marca = "A-BM" if "Médico" in tipo else "A-VAC"
                    motivo_texto = "A-BM (No Asistió por Baja Médica)" if marca == "A-BM" else "A-VAC (Vacaciones)"
                    dias = (f_fin - f_ini).days + 1
                    ahora = datetime.now()
                    periodo = ahora.strftime("%Y-%m")
                    usuario_sesion = st.session_state.get("usuario", "admin")

                    # 1. Subir documentos y guardar en Sustentos_Bajas
                    urls_docs = []
                    errores_docs = []
                    if docs:
                        with st.spinner("📤 Subiendo documentos..."):
                            for doc in docs:
                                url, err = _subir_doc(doc)
                                if url:
                                    urls_docs.append(url)
                                    # Guardar en Sustentos_Bajas
                                    if hoja_sustentos:
                                        try:
                                            fila_sust = [
                                                periodo,
                                                str(f_ini),
                                                str(colab.get("DNI", "")),
                                                str(colab.get("NOMBRES", "")),
                                                str(colab.get("RAZON SOCIAL", "")),
                                                motivo_texto,
                                                url,
                                                ahora.strftime("%Y-%m-%d %H:%M:%S"),
                                                usuario_sesion,
                                            ]
                                            hoja_sustentos.append_row(fila_sust)
                                        except Exception as e:
                                            errores_docs.append(f"Error guardando en Sustentos_Bajas: {e}")
                                else:
                                    errores_docs.append(f"{doc.name}: {err}")

                    # 2. Guardar en Asistencia (DIA_1..DIA_31)
                    try:
                        with st.spinner("💾 Guardando en Google Sheets..."):
                            fila_asist = [
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
                                periodo,
                                periodo,
                            ]
                            fa = f_ini
                            for d in range(1, 32):
                                if fa <= f_fin:
                                    fila_asist.append(marca)
                                    fa += timedelta(days=1)
                                else:
                                    fila_asist.append("")
                            hoja_asistencia.append_row(fila_asist)

                        # 3. Confirmación
                        st.success("✅ ¡Registro guardado correctamente!")
                        st.info(
                            f"**Colaborador:** {colab.get('NOMBRES')} | DNI: {colab.get('DNI')}\n\n"
                            f"**Razón Social:** {colab.get('RAZON SOCIAL')}\n\n"
                            f"**Tipo:** {motivo_texto}\n\n"
                            f"**Período:** {f_ini} → {f_fin} ({dias} día{'s' if dias > 1 else ''})\n\n"
                            f"**Documentos subidos:** {len(urls_docs)}"
                        )

                        if urls_docs:
                            st.write("**🔗 Links de documentos subidos:**")
                            for i, url in enumerate(urls_docs, 1):
                                st.markdown(f"  {i}. [{url}]({url})")

                        if errores_docs:
                            st.warning("⚠️ Errores:\n" + "\n".join(errores_docs))

                        st.session_state["asist_guardado"] = {
                            "nombre": colab.get("NOMBRES"),
                            "dni": colab.get("DNI"),
                            "razon": colab.get("RAZON SOCIAL"),
                            "marca": marca,
                            "motivo": motivo_texto,
                            "desde": str(f_ini),
                            "hasta": str(f_fin),
                            "dias": dias,
                            "docs": urls_docs,
                            "fecha_registro": ahora.strftime("%Y-%m-%d %H:%M:%S"),
                            "usuario": usuario_sesion,
                        }
                        st.session_state["asist_colab"] = None

                    except Exception as e:
                        st.error(f"❌ Error al guardar: {str(e)}")

        # Banner del último guardado
        guardado = st.session_state.get("asist_guardado")
        if guardado and not st.session_state.get("asist_colab"):
            st.success(
                f"✅ Último registro: **{guardado['nombre']}** (DNI: {guardado['dni']}) | "
                f"**{guardado['marca']}** del {guardado['desde']} al {guardado['hasta']} "
                f"({guardado['dias']} días) | Docs: {len(guardado['docs'])} | "
                f"Registrado: {guardado['fecha_registro']}"
            )

    # ══════════════════════════════════════════════════════
    # TAB 2 — ESPEJO
    # ══════════════════════════════════════════════════════
    with tab_espejo:
        st.subheader("📊 Espejo — Sustentos y Registros")

        if st.button("🔄 Actualizar datos", key="esp_reload"):
            st.rerun()

        # Mostrar Sustentos_Bajas (con documentos)
        if hoja_sustentos:
            df_sust = _cargar_df(hoja_sustentos)
            if not df_sust.empty:
                st.write("### Sustentos / Evidencias")
                cf1, cf2, cf3 = st.columns(3)
                with cf1:
                    meses_s = ["TODOS"] + sorted(df_sust.get("PERIODO", pd.Series(dtype=str)).dropna().unique().tolist())
                    mes_s = st.selectbox("Período:", meses_s, key="esp_mes_s")
                with cf2:
                    dni_s = st.text_input("DNI:", key="esp_dni_s")
                with cf3:
                    tipo_s = st.selectbox("Tipo:", ["TODOS", "A-BM", "A-VAC"], key="esp_tipo_s")

                df_fs = df_sust.copy()
                if mes_s != "TODOS" and "PERIODO" in df_fs.columns:
                    df_fs = df_fs[df_fs["PERIODO"].astype(str) == mes_s]
                if dni_s.strip() and "DNI" in df_fs.columns:
                    df_fs = df_fs[df_fs["DNI"].astype(str).str.contains(dni_s.strip(), na=False)]
                if tipo_s != "TODOS" and "MOTIVO" in df_fs.columns:
                    df_fs = df_fs[df_fs["MOTIVO"].astype(str).str.contains(tipo_s, na=False)]

                if not df_fs.empty:
                    cols_vis = ["PERIODO", "FECHA_", "DNI", "NOMBRE", "RAZON SOCIAL", "MOTIVO", "LINK_DOCUMENTO", "FECHA_SUBIDA", "USUARIO_REGISTRO"]
                    st.dataframe(df_fs[[c for c in cols_vis if c in df_fs.columns]], use_container_width=True, hide_index=True)
                    st.success(f"✅ {len(df_fs)} registro(s)")
                else:
                    st.warning("Sin resultados")
            else:
                st.info("Sin sustentos registrados aún")

        # Mostrar Asistencia (días marcados)
        st.write("### Asistencia — Días registrados")
        df_h = _cargar_df(hoja_asistencia)
        if df_h.empty:
            st.info("Sin registros en Asistencia")
        else:
            cf1, cf2 = st.columns(2)
            with cf1:
                meses_a = ["TODOS"] + sorted(df_h.get("MES", pd.Series(dtype=str)).dropna().unique().tolist()) if "MES" in df_h.columns else ["TODOS"]
                mes_a = st.selectbox("Mes:", meses_a, key="esp_mes_a")
            with cf2:
                dni_a = st.text_input("DNI:", key="esp_dni_a")

            df_fa = df_h.copy()
            if mes_a != "TODOS" and "MES" in df_fa.columns:
                df_fa = df_fa[df_fa["MES"].astype(str) == mes_a]
            if dni_a.strip() and "DNI" in df_fa.columns:
                df_fa = df_fa[df_fa["DNI"].astype(str).str.contains(dni_a.strip(), na=False)]

            if not df_fa.empty:
                cols_vis = ["DNI", "NOMBRES", "RAZON SOCIAL", "MES"]
                st.dataframe(df_fa[[c for c in cols_vis if c in df_fa.columns]], use_container_width=True, hide_index=True)

                for _, row in df_fa.iterrows():
                    with st.expander(f"📋 {row.get('DNI','—')} · {row.get('NOMBRES','—')} · {row.get('MES','—')}"):
                        d1, d2 = st.columns(2)
                        with d1:
                            st.write(f"**Razón Social:** {row.get('RAZON SOCIAL','—')}")
                            st.write(f"**Supervisor:** {row.get('SUPERVISOR A CARGO FINAL','—')}")
                        with d2:
                            st.write(f"**Coordinador:** {row.get('COORDINADOR FINAL','—')}")
                            st.write(f"**Estado:** {row.get('ESTADO','—')}")
                        dias_marcados = [(f"Día {i}", row.get(f"DIA_{i}", "")) for i in range(1, 32) if str(row.get(f"DIA_{i}", "")).strip() not in ("", "0")]
                        if dias_marcados:
                            st.write("**Días marcados:** " + " | ".join([f"{d[0]}: {d[1]}" for d in dias_marcados]))
            else:
                st.warning("Sin resultados")

    # ══════════════════════════════════════════════════════
    # TAB 3 — DOCUMENTOS
    # ══════════════════════════════════════════════════════
    with tab_docs:
        st.subheader("📎 Evidencias y Documentos")

        if hoja_sustentos:
            df_d = _cargar_df(hoja_sustentos)
            if df_d.empty:
                st.info("Sin documentos registrados aún")
            else:
                cf1, cf2 = st.columns(2)
                with cf1:
                    dni_d = st.text_input("Buscar por DNI:", key="doc_dni")
                with cf2:
                    per_d = st.text_input("Buscar por Período (ej: 2026-06):", key="doc_per")

                df_fd = df_d.copy()
                if dni_d.strip() and "DNI" in df_fd.columns:
                    df_fd = df_fd[df_fd["DNI"].astype(str).str.contains(dni_d.strip(), na=False)]
                if per_d.strip() and "PERIODO" in df_fd.columns:
                    df_fd = df_fd[df_fd["PERIODO"].astype(str).str.contains(per_d.strip(), na=False)]

                if not df_fd.empty:
                    st.success(f"✅ {len(df_fd)} documento(s) encontrado(s)")
                    for _, row in df_fd.iterrows():
                        with st.expander(f"📄 DNI: {row.get('DNI','—')} | {row.get('NOMBRE','—')} | {row.get('PERIODO','—')} | {row.get('FECHA_SUBIDA','—')}"):
                            d1, d2 = st.columns(2)
                            with d1:
                                st.write(f"**DNI:** {row.get('DNI','—')}")
                                st.write(f"**Nombre:** {row.get('NOMBRE','—')}")
                                st.write(f"**Razón Social:** {row.get('RAZON SOCIAL','—')}")
                                st.write(f"**Período:** {row.get('PERIODO','—')}")
                            with d2:
                                st.write(f"**Fecha registro:** {row.get('FECHA_','—')}")
                                st.write(f"**Motivo:** {row.get('MOTIVO','—')}")
                                st.write(f"**Fecha subida:** {row.get('FECHA_SUBIDA','—')}")
                                st.write(f"**Usuario:** {row.get('USUARIO_REGISTRO','—')}")
                            link = row.get("LINK_DOCUMENTO", "")
                            if link:
                                st.markdown(f"**🔗 Documento:** [{link}]({link})")
                else:
                    st.warning("Sin documentos para esa búsqueda")
        else:
            st.warning("Hoja Sustentos_Bajas no conectada")


def sincronizar_mes(hoja_asistencia, hoja_colaboradores):
    return 0, 0
