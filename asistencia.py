"""
asistencia.py v3.0
- session_state: no se congela
- Guarda DM/VAC en hoja Asistencia (días marcados)
- Sube documentos a catbox.moe
- Confirmación visual
- Tab Espejo: historial con filtros
- Tab Documentos: evidencias subidas
"""
import pandas as pd
import streamlit as st
from datetime import datetime, timedelta

# ─── Helpers ──────────────────────────────────────────────────────────────────

def _cargar_df(hoja):
    try:
        vals = hoja.get_all_values()
        if len(vals) < 2:
            return pd.DataFrame()
        return pd.DataFrame(vals[1:], columns=vals[0])
    except Exception as e:
        st.error(f"Error cargando datos: {e}")
        return pd.DataFrame()

def _subir_doc(archivo):
    """Sube archivo a catbox.moe y devuelve URL o mensaje de error."""
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

# ─── Módulo principal ─────────────────────────────────────────────────────────

def mostrar_asistencia(hoja_asistencia, hoja_colaboradores, registro_mod=None, razon=None):

    # Init session_state
    if "asist_colab" not in st.session_state:
        st.session_state["asist_colab"] = None
    if "asist_guardado" not in st.session_state:
        st.session_state["asist_guardado"] = None

    st.write("# Gestión de Descansos Médicos y Vacaciones")

    tab_reg, tab_espejo, tab_docs = st.tabs(["📝 Registrar", "📊 Espejo / Histórico", "📎 Documentos"])

    # ══════════════════════════════════════════════════════
    # TAB 1 — REGISTRAR
    # ══════════════════════════════════════════════════════
    with tab_reg:
        df_colab = _cargar_df(hoja_colaboradores)
        if df_colab.empty:
            st.error("❌ Sin datos de colaboradores")
            return

        # Normalizar columnas
        df_colab.columns = [c.strip().upper() for c in df_colab.columns]

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
                st.warning("⚠️ No se encontró ningún colaborador")
            else:
                st.session_state["asist_colab"] = res.iloc[0].to_dict()
                visibles = ["DNI", "NOMBRES", "RAZON SOCIAL", "ESTADO"]
                st.success(f"✅ {len(res)} resultado(s)")
                st.dataframe(res[[c for c in visibles if c in res.columns]], use_container_width=True, hide_index=True)

        # ── Formulario de registro (persiste con session_state) ──
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
                    dias = (f_fin - f_ini).days + 1

                    # 1. Subir documentos
                    urls_docs = []
                    errores_docs = []
                    if docs:
                        with st.spinner("📤 Subiendo documentos..."):
                            for doc in docs:
                                url, err = _subir_doc(doc)
                                if url:
                                    urls_docs.append(url)
                                else:
                                    errores_docs.append(f"{doc.name}: {err}")

                    # 2. Guardar en Asistencia
                    try:
                        with st.spinner("💾 Guardando en Google Sheets..."):
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
                            fa = f_ini
                            for d in range(1, 32):
                                if fa <= f_fin:
                                    fila.append(marca)
                                    fa += timedelta(days=1)
                                else:
                                    fila.append("")

                            hoja_asistencia.append_row(fila)

                        # 3. Confirmación
                        st.success(f"✅ ¡Registro guardado correctamente!")
                        st.info(
                            f"**Colaborador:** {colab.get('NOMBRES')} ({colab.get('DNI')})\n\n"
                            f"**Tipo:** {marca}\n\n"
                            f"**Período:** {f_ini} → {f_fin} ({dias} día{'s' if dias > 1 else ''})\n\n"
                            f"**Documentos subidos:** {len(urls_docs)}"
                        )

                        if urls_docs:
                            st.write("**🔗 Links de documentos:**")
                            for i, url in enumerate(urls_docs, 1):
                                st.write(f"  {i}. [{url}]({url})")

                        if errores_docs:
                            st.warning("⚠️ Algunos documentos no se pudieron subir:\n" + "\n".join(errores_docs))

                        # Guardar confirmación y limpiar colaborador
                        st.session_state["asist_guardado"] = {
                            "nombre": colab.get("NOMBRES"),
                            "dni": colab.get("DNI"),
                            "marca": marca,
                            "desde": str(f_ini),
                            "hasta": str(f_fin),
                            "dias": dias,
                            "docs": urls_docs,
                        }
                        st.session_state["asist_colab"] = None

                    except Exception as e:
                        st.error(f"❌ Error al guardar en Sheets: {str(e)}")

        # Mostrar último guardado confirmado
        guardado = st.session_state.get("asist_guardado")
        if guardado and not colab:
            st.success(
                f"✅ Último registro: **{guardado['nombre']}** ({guardado['dni']}) | "
                f"**{guardado['marca']}** del {guardado['desde']} al {guardado['hasta']} "
                f"({guardado['dias']} días) | Docs: {len(guardado['docs'])}"
            )

    # ══════════════════════════════════════════════════════
    # TAB 2 — ESPEJO / HISTÓRICO
    # ══════════════════════════════════════════════════════
    with tab_espejo:
        st.subheader("📊 Espejo — Registros de Asistencia")

        if st.button("🔄 Actualizar", key="asist_btn_reload"):
            st.cache_data.clear()

        df_h = _cargar_df(hoja_asistencia)

        if df_h.empty:
            st.info("ℹ️ Sin registros en la hoja Asistencia aún")
        else:
            df_h.columns = [c.strip().upper() for c in df_h.columns]

            # Filtros
            cf1, cf2, cf3 = st.columns(3)
            with cf1:
                meses = ["TODOS"] + sorted(df_h["MES"].dropna().unique().tolist()) if "MES" in df_h.columns else ["TODOS"]
                mes_sel = st.selectbox("Mes:", meses, key="esp_mes")
            with cf2:
                dni_esp = st.text_input("DNI:", key="esp_dni")
            with cf3:
                tipo_esp = st.selectbox("Tipo:", ["TODOS", "A-BM", "A-VAC"], key="esp_tipo")

            df_f = df_h.copy()
            if mes_sel != "TODOS" and "MES" in df_f.columns:
                df_f = df_f[df_f["MES"].astype(str) == mes_sel]
            if dni_esp.strip() and "DNI" in df_f.columns:
                df_f = df_f[df_f["DNI"].astype(str).str.contains(dni_esp.strip(), na=False)]

            if not df_f.empty:
                cols_vis = ["DNI", "NOMBRES", "RAZON SOCIAL", "DEPARTAMENTO", "MES"]
                st.dataframe(
                    df_f[[c for c in cols_vis if c in df_f.columns]],
                    use_container_width=True,
                    hide_index=True,
                )
                st.success(f"✅ Total: {len(df_f)} registro(s)")

                # Detalle por expander
                st.divider()
                st.write("**Detalle de registros:**")
                for _, row in df_f.iterrows():
                    with st.expander(f"📋 {row.get('DNI','—')} · {row.get('NOMBRES','—')} · {row.get('MES','—')}"):
                        d1, d2 = st.columns(2)
                        with d1:
                            st.write(f"**Razón Social:** {row.get('RAZON SOCIAL','—')}")
                            st.write(f"**Supervisor:** {row.get('SUPERVISOR A CARGO FINAL','—')}")
                            st.write(f"**Departamento:** {row.get('DEPARTAMENTO','—')}")
                        with d2:
                            st.write(f"**Coordinador:** {row.get('COORDINADOR FINAL','—')}")
                            st.write(f"**Estado:** {row.get('ESTADO','—')}")
                            st.write(f"**Mes:** {row.get('MES','—')}")

                        # Días marcados
                        dias_marcados = []
                        for i in range(1, 32):
                            col_dia = f"DIA_{i}"
                            val = row.get(col_dia, "")
                            if val and str(val).strip() not in ("", "0"):
                                dias_marcados.append(f"Día {i}: {val}")
                        if dias_marcados:
                            st.write("**Días registrados:**")
                            st.write(" | ".join(dias_marcados))
            else:
                st.warning("⚠️ Sin resultados para esos filtros")

    # ══════════════════════════════════════════════════════
    # TAB 3 — DOCUMENTOS
    # ══════════════════════════════════════════════════════
    with tab_docs:
        st.subheader("📎 Documentos y Evidencias")
        st.info(
            "Los documentos se adjuntan en la pestaña **Registrar** al momento de guardar un descanso. "
            "Los archivos se suben automáticamente y se genera un link permanente."
        )

        guardado = st.session_state.get("asist_guardado")
        if guardado and guardado.get("docs"):
            st.success(f"✅ Documentos del último registro ({guardado['nombre']}):")
            for i, url in enumerate(guardado["docs"], 1):
                st.write(f"**Documento {i}:** [{url}]({url})")
        else:
            st.write("No hay documentos en la sesión actual. Registra un descanso con archivos adjuntos para verlos aquí.")


def sincronizar_mes(hoja_asistencia, hoja_colaboradores):
    return 0, 0
