"""
asistencia.py v5.0
- Espejo: matriz profesional de días DM/VAC por colaborador
- Documentos: tarjetas profesionales con todos los datos
- Sin congelamiento (session_state)
- Guarda en Asistencia (DIA_1..DIA_31) y Sustentos_Bajas
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


def _normalizar_razon(s: str) -> str:
    """Normaliza razón social: mayúsculas, quita puntos/guiones/espacios extras."""
    return str(s).strip().upper().replace(".", "").replace("-", "").replace("  ", " ")


def _validar_fechas_duplicadas(hoja_asistencia, dni, f_ini, f_fin):
    """
    Verifica si el DNI ya tiene días A-BM o A-VAC registrados
    en el rango de fechas solicitado. Retorna lista de conflictos.
    """
    try:
        df_h = _cargar_df(hoja_asistencia)
        if df_h.empty or "DNI" not in df_h.columns:
            return []

        # Filtrar por DNI
        df_dni = df_h[df_h["DNI"].astype(str).str.strip() == str(dni).strip()]
        if df_dni.empty:
            return []

        # Los días a verificar
        dias_pedidos = set()
        fa = f_ini
        while fa <= f_fin:
            dias_pedidos.add(fa.day)
            fa += timedelta(days=1)

        # Período solicitado (formato YYYY-MM, igual al que escribe la app)
        periodo_pedido = f_ini.strftime("%Y-%m")
        # Mes solo numérico (para tolerar filas viejas donde MES="6")
        mes_num_pedido = str(f_ini.month)

        conflictos = []
        for _, row in df_dni.iterrows():
            # Acepta match contra PERIODO (formato 2026-06) o MES (formato "6" o "06")
            periodo_row = str(row.get("PERIODO", "")).strip()
            mes_row = str(row.get("MES", "")).strip().lstrip("0")
            mismo_periodo = (periodo_row == periodo_pedido) or (mes_row == mes_num_pedido)
            if not mismo_periodo:
                continue
            # Verificar días ocupados
            for dia in dias_pedidos:
                col = f"DIA_{dia}"
                val = str(row.get(col, "")).strip()
                if val in ("A-BM", "A-VAC"):
                    conflictos.append(f"Día {dia}: ya tiene {val}")

        return conflictos
    except Exception:
        return []  # Si falla la validación, no bloquear el registro


def _subir_doc(archivo):
    """Sube un archivo a Drive y retorna (url, error). Si falla, url=None."""
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


def _render_matriz_espejo(df_asist):
    """Renderiza la matriz de días DM/VAC en HTML con colores."""
    cols_base = ["DNI", "NOMBRES", "RAZON SOCIAL", "MES"]
    dias_cols = [f"DIA_{i}" for i in range(1, 32)]

    # Filtrar columnas disponibles
    cols_disp = [c for c in dias_cols if c in df_asist.columns]
    cols_show = [c for c in cols_base if c in df_asist.columns] + cols_disp

    if not cols_disp:
        st.warning("No se encontraron columnas DIA_1..DIA_31")
        return

    df_m = df_asist[cols_show].copy()

    # Construir tabla HTML
    num_dias = len(cols_disp)
    headers_base = "".join(f"<th class='col-base'>{c.replace('RAZON SOCIAL','EMPRESA')}</th>" for c in [c for c in cols_base if c in df_asist.columns])
    headers_dias = "".join(f"<th class='col-dia'>{i}</th>" for i in range(1, num_dias + 1))

    rows_html = ""
    for _, row in df_m.iterrows():
        cells_base = "".join(f"<td class='cell-base'>{row.get(c, '')}</td>" for c in [c for c in cols_base if c in df_asist.columns])
        cells_dias = ""
        for col in cols_disp:
            val = str(row.get(col, "")).strip()
            if val == "A-BM":
                cells_dias += f"<td class='cell-bm' title='Descanso Médico'>DM</td>"
            elif val == "A-VAC":
                cells_dias += f"<td class='cell-vac' title='Vacaciones'>VAC</td>"
            elif val == "P-PJ":
                cells_dias += f"<td class='cell-pj' title='Permiso Justificado'>PJ</td>"
            else:
                cells_dias += "<td class='cell-empty'></td>"
        rows_html += f"<tr>{cells_base}{cells_dias}</tr>"

    html = f"""
<style>
.matriz-container {{ overflow-x: auto; margin: 12px 0; }}
.matriz-table {{ border-collapse: collapse; font-size: 11px; font-family: sans-serif; width: 100%; }}
.matriz-table th {{ background: #4B0067; color: white; padding: 6px 4px; text-align: center; position: sticky; top: 0; white-space: nowrap; }}
.matriz-table th.col-base {{ background: #3a0052; min-width: 80px; text-align: left; padding-left: 8px; }}
.matriz-table th.col-dia {{ min-width: 28px; font-size: 10px; }}
.matriz-table td {{ padding: 4px; text-align: center; border: 1px solid #e0e0e0; white-space: nowrap; }}
.cell-base {{ text-align: left; padding-left: 8px; background: #fafafa; color: #222; font-size: 11px; }}
.cell-bm {{ background: #FDECEA; color: #C0392B; font-weight: 700; font-size: 9px; border-radius: 2px; }}
.cell-vac {{ background: #E8F4FD; color: #1A5276; font-weight: 700; font-size: 9px; border-radius: 2px; }}
.cell-pj {{ background: #E9F7EF; color: #1E8449; font-weight: 700; font-size: 9px; border-radius: 2px; }}
.cell-empty {{ background: white; }}
.matriz-table tr:hover td {{ background: #f3e5fa !important; }}
.leyenda {{ display: flex; gap: 16px; margin: 8px 0 16px; font-size: 12px; }}
.leyenda-item {{ display: flex; align-items: center; gap: 6px; }}
.leyenda-box {{ width: 16px; height: 16px; border-radius: 3px; }}
.bm-box {{ background: #FDECEA; border: 1px solid #C0392B; }}
.vac-box {{ background: #E8F4FD; border: 1px solid #1A5276; }}
.pj-box {{ background: #E9F7EF; border: 1px solid #1E8449; }}
</style>
<div class='leyenda'>
  <div class='leyenda-item'><div class='leyenda-box bm-box'></div><span><b>DM</b> = Descanso Médico (A-BM)</span></div>
  <div class='leyenda-item'><div class='leyenda-box vac-box'></div><span><b>VAC</b> = Vacaciones (A-VAC)</span></div>
  <div class='leyenda-item'><div class='leyenda-box pj-box'></div><span><b>PJ</b> = Permiso Justificado (P-PJ)</span></div>
</div>
<div class='matriz-container'>
<table class='matriz-table'>
<thead><tr>{headers_base}{headers_dias}</tr></thead>
<tbody>{rows_html}</tbody>
</table>
</div>
"""
    st.markdown(html, unsafe_allow_html=True)
    st.caption(f"📊 {len(df_m)} colaborador(es) | Días del mes: 1 al {num_dias}")


def _render_tarjetas_docs(df_docs):
    """Renderiza documentos como tarjetas profesionales en HTML."""
    cards_html = ""
    for _, row in df_docs.iterrows():
        link = str(row.get("LINK_DOCUMENTO", "")).strip()
        ext = link.split(".")[-1].upper() if "." in link else "DOC"
        motivo = str(row.get("MOTIVO", "—"))
        tipo_badge = ""
        if "A-BM" in motivo:
            tipo_badge = "<span class='badge badge-bm'>🏥 Descanso Médico</span>"
        elif "A-VAC" in motivo:
            tipo_badge = "<span class='badge badge-vac'>✈️ Vacaciones</span>"
        else:
            tipo_badge = f"<span class='badge badge-other'>{motivo[:20]}</span>"

        btn_link = f"<a href='{link}' target='_blank' class='btn-doc'>🔗 Ver documento ({ext})</a>" if link else "<span class='no-doc'>Sin documento</span>"

        cards_html += f"""
<div class='doc-card'>
  <div class='doc-card-header'>
    <div>
      <div class='doc-dni'>DNI: {row.get('DNI','—')}</div>
      <div class='doc-nombre'>{row.get('NOMBRE','—')}</div>
    </div>
    {tipo_badge}
  </div>
  <div class='doc-card-body'>
    <div class='doc-meta'><span class='meta-label'>🏢 Empresa</span><span>{row.get('RAZON SOCIAL','—')}</span></div>
    <div class='doc-meta'><span class='meta-label'>📅 Período</span><span>{row.get('PERIODO','—')}</span></div>
    <div class='doc-meta'><span class='meta-label'>📆 Fecha registro</span><span>{row.get('FECHA_','—')}</span></div>
    <div class='doc-meta'><span class='meta-label'>⬆️ Subido</span><span>{row.get('FECHA_SUBIDA','—')}</span></div>
    <div class='doc-meta'><span class='meta-label'>👤 Usuario</span><span>{row.get('USUARIO_REGISTRO','—')}</span></div>
  </div>
  <div class='doc-card-footer'>{btn_link}</div>
</div>
"""

    html = f"""
<style>
.docs-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 16px; margin: 16px 0; }}
.doc-card {{ background: white; border: 1px solid #e5e0ea; border-radius: 12px; overflow: hidden; box-shadow: 0 2px 8px rgba(75,0,103,0.08); }}
.doc-card-header {{ background: linear-gradient(135deg, #4B0067, #3a0052); padding: 14px 16px; display: flex; justify-content: space-between; align-items: flex-start; gap: 8px; }}
.doc-dni {{ font-size: 11px; color: rgba(255,255,255,0.7); font-weight: 600; letter-spacing: 0.5px; margin-bottom: 2px; }}
.doc-nombre {{ font-size: 14px; color: white; font-weight: 700; }}
.badge {{ padding: 4px 10px; border-radius: 20px; font-size: 11px; font-weight: 700; white-space: nowrap; }}
.badge-bm {{ background: #FDECEA; color: #C0392B; }}
.badge-vac {{ background: #E8F4FD; color: #1A5276; }}
.badge-other {{ background: rgba(255,255,255,0.15); color: white; }}
.doc-card-body {{ padding: 12px 16px; display: flex; flex-direction: column; gap: 6px; }}
.doc-meta {{ display: flex; gap: 8px; font-size: 12px; color: #444; align-items: center; }}
.meta-label {{ color: #888; min-width: 110px; font-weight: 600; }}
.doc-card-footer {{ padding: 10px 16px; border-top: 1px solid #f0eaf5; }}
.btn-doc {{ display: inline-block; background: #EC6608; color: white; text-decoration: none; padding: 7px 16px; border-radius: 8px; font-size: 12px; font-weight: 700; }}
.btn-doc:hover {{ background: #D45605; }}
.no-doc {{ color: #aaa; font-size: 12px; }}
</style>
<div class='docs-grid'>{cards_html}</div>
"""
    st.markdown(html, unsafe_allow_html=True)


# ─── MÓDULO PRINCIPAL ────────────────────────────────────────────────────────

def mostrar_asistencia(hoja_asistencia, hoja_colaboradores, hoja_sustentos=None, registro_mod=None, razon=None):

    for k, v in [("asist_colab", None), ("asist_guardado", None)]:
        if k not in st.session_state:
            st.session_state[k] = v

    st.write("# Gestión de Descansos Médicos y Vacaciones")

    tab_reg, tab_espejo, tab_docs = st.tabs(["📝 Registrar", "📊 Espejo de Asistencia", "📎 Evidencias"])

    # ══════════════════════════ TAB REGISTRAR ══════════════════════════
    with tab_reg:
        df_colab = _cargar_df(hoja_colaboradores)
        if df_colab.empty:
            st.error("❌ Sin datos de colaboradores")
            return

        # FIX: si el usuario tiene razón social asignada (no es backoffice),
        # solo puede ver y registrar sobre sus propios colaboradores.
        rol_actual = st.session_state.get("rol", "")
        if razon and rol_actual != "backoffice" and "RAZON SOCIAL" in df_colab.columns:
            razon_norm = _normalizar_razon(razon)
            df_colab = df_colab[df_colab["RAZON SOCIAL"].astype(str).apply(_normalizar_razon).eq(razon_norm)]

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
                "Tipo:",
                [
                    "🏥 Descanso Médico (A-BM)",
                    "✈️ Vacaciones (A-VAC)",
                    "📋 Permiso Justificado (P-PJ)",
                ],
                key="asist_tipo"
            )
            cf1, cf2 = st.columns(2)
            with cf1:
                f_ini = st.date_input("Desde:", key="asist_f_ini")
            with cf2:
                f_fin = st.date_input("Hasta:", key="asist_f_fin")

            st.subheader("3️⃣ Adjuntar documentos (OBLIGATORIO)")
            docs = st.file_uploader("Certificados, autorizaciones, fotos (OBLIGATORIO):", accept_multiple_files=True, key="asist_docs")

            if st.button("💾 GUARDAR DESCANSO", type="primary", use_container_width=True, key="asist_btn_guardar"):
                # Parsear FECHA_ALTA y FECHA_CESE del colaborador (varios formatos)
                def _parse_fecha_col(valor):
                    s = str(valor).strip()
                    if not s:
                        return None
                    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d", "%d-%m-%Y"):
                        try:
                            return datetime.strptime(s, fmt).date()
                        except ValueError:
                            continue
                    return None

                fecha_alta_colab = _parse_fecha_col(colab.get("FECHA DE CREACION USUARIO", ""))
                fecha_cese_colab = _parse_fecha_col(colab.get("FECHA DE CESE", ""))

                if not docs:
                    st.error("❌ Debes adjuntar al menos un documento de sustento. No se puede registrar un descanso médico ni vacaciones sin sustento.")
                elif f_fin < f_ini:
                    st.error("❌ La fecha fin no puede ser anterior a la fecha inicio")
                elif fecha_alta_colab and f_ini < fecha_alta_colab:
                    st.error(
                        f"❌ **{colab.get('NOMBRES')}** (DNI: {colab.get('DNI')}) — "
                        f"la fecha inicio **{f_ini}** es anterior a su fecha de alta (**{fecha_alta_colab}**). "
                        "No se puede registrar un descanso antes de que el colaborador exista."
                    )
                elif fecha_cese_colab and f_fin > fecha_cese_colab:
                    st.error(
                        f"❌ **{colab.get('NOMBRES')}** (DNI: {colab.get('DNI')}) — "
                        f"la fecha fin **{f_fin}** supera su fecha de cese (**{fecha_cese_colab}**). "
                        "No se puede registrar un descanso después de la baja del colaborador."
                    )
                else:
                    # Validación de rango OK (alta ≤ rango ≤ cese, o sin tope si no hay cese).
                    # Última restricción: solapamiento con registros existentes.
                    if True:
                        # Validar fechas duplicadas
                        conflictos = _validar_fechas_duplicadas(hoja_asistencia, colab.get("DNI"), f_ini, f_fin)
                        if conflictos:
                            st.error(
                                f"❌ **{colab.get('NOMBRES')}** (DNI: {colab.get('DNI')}) ya tiene registros en esas fechas:\n\n" +
                                "\n".join(f"• {c}" for c in conflictos[:10]) +
                                "\n\n⛔ No se puede registrar un descanso en días ya ocupados."
                            )
                        else:
                            if "Médico" in tipo:
                                marca = "A-BM"
                                motivo_texto = "A-BM (No Asistió por Baja Médica)"
                            elif "Vacaciones" in tipo:
                                marca = "A-VAC"
                                motivo_texto = "A-VAC (Vacaciones)"
                            else:
                                marca = "P-PJ"
                                motivo_texto = "P-PJ (Permiso Justificado)"
                            dias = (f_fin - f_ini).days + 1
                            ahora = datetime.now()
                            periodo = ahora.strftime("%Y-%m")
                            usuario_sesion = st.session_state.get("usuario", "admin")

                            urls_docs, errores_docs = [], []
                            if docs:
                                with st.spinner("📤 Subiendo documentos..."):
                                    for doc in docs:
                                        url, err = _subir_doc(doc)
                                        if url:
                                            urls_docs.append(url)
                                            if hoja_sustentos:
                                                try:
                                                    # ORDEN OFICIAL de Sustentos_Bajas (Evidencias):
                                                    # A=PERIODO, B=FECHA_INICIO, C=FECHA_FIN, D=DNI,
                                                    # E=NOMBRE, F=RAZON SOCIAL, G=MOTIVO,
                                                    # H=LINK_DOCUMENTO, I=FECHA_SUBIDA, J=USUARIO_REGISTRO
                                                    hoja_sustentos.append_row([
                                                        periodo,                                          # A
                                                        str(f_ini),                                       # B = FECHA_INICIO
                                                        str(f_fin),                                       # C = FECHA_FIN
                                                        str(colab.get("DNI", "")),                        # D
                                                        str(colab.get("NOMBRES", "")),                    # E
                                                        str(colab.get("RAZON SOCIAL", "")),               # F
                                                        motivo_texto,                                     # G
                                                        url,                                              # H
                                                        ahora.strftime("%Y-%m-%d %H:%M:%S"),              # I
                                                        usuario_sesion,                                   # J
                                                    ])
                                                except Exception as e:
                                                    errores_docs.append(f"Error Sustentos_Bajas: {e}")
                                        else:
                                            errores_docs.append(f"{doc.name}: {err}")

                            try:
                                with st.spinner("💾 Guardando en Asistencia..."):
                                    # ORDEN OFICIAL de columnas de la hoja Asistencia:
                                    # A=RAZON SOCIAL, B=SUPERVISOR, C=COORDINADOR, D=DEPARTAMENTO,
                                    # E=PROVINCIA, F=DNI, G=NOMBRE, H=ESTADO, I=FECHA_ALTA,
                                    # J=FECHA_CESE, K=MES, L=PERIODO, M..AQ = DIA_1..DIA_31
                                    mes_num = str(f_ini.month)
                                    fila = [
                                        str(colab.get("RAZON SOCIAL", "")),               # A
                                        str(colab.get("SUPERVISOR A CARGO FINAL", "")),   # B
                                        str(colab.get("COORDINADOR FINAL", "")),          # C
                                        str(colab.get("DEPARTAMENTO", "")),               # D
                                        str(colab.get("PROVINCIA", "")),                  # E
                                        str(colab.get("DNI", "")),                        # F
                                        str(colab.get("NOMBRES", "")),                    # G  (cabecera "NOMBRE")
                                        str(colab.get("ESTADO", "")),                     # H
                                        str(colab.get("FECHA DE CREACION USUARIO", "")),  # I  (cabecera "FECHA_ALTA")
                                        str(colab.get("FECHA DE CESE", "")),              # J  (cabecera "FECHA_CESE")
                                        mes_num,                                          # K  (cabecera "MES" — solo número 1..12)
                                        periodo,                                          # L  (cabecera "PERIODO" — YYYY-MM)
                                    ]
                                    # DIA_1..DIA_31: la marca va EN LA COLUMNA DEL NÚMERO DE DÍA.
                                    # Si el rango es del 6 al 11, se marca DIA_6..DIA_11 (no DIA_1..DIA_6).
                                    dias_marcados = set()
                                    fa = f_ini
                                    while fa <= f_fin:
                                        dias_marcados.add(fa.day)
                                        fa += timedelta(days=1)
                                    for dia_num in range(1, 32):
                                        fila.append(marca if dia_num in dias_marcados else "")
                                    hoja_asistencia.append_row(fila)

                                st.success("✅ ¡Registro guardado correctamente!")
                                st.info(
                                    f"**{colab.get('NOMBRES')}** (DNI: {colab.get('DNI')}) — "
                                    f"**{motivo_texto}** | {f_ini} → {f_fin} ({dias} días) | "
                                    f"Docs: {len(urls_docs)} | Registrado: {ahora.strftime('%Y-%m-%d %H:%M')}"
                                )
                                if urls_docs:
                                    st.write("**🔗 Documentos subidos:**")
                                    for i, u in enumerate(urls_docs, 1):
                                        st.markdown(f"{i}. [{u}]({u})")
                                if errores_docs:
                                    st.warning("⚠️ " + " | ".join(errores_docs))

                                st.session_state["asist_guardado"] = {
                                    "nombre": colab.get("NOMBRES"), "dni": colab.get("DNI"),
                                    "marca": marca, "desde": str(f_ini), "hasta": str(f_fin),
                                    "dias": dias, "docs": urls_docs, "ts": ahora.strftime("%Y-%m-%d %H:%M"),
                                }
                                st.session_state["asist_colab"] = None
                            except Exception as e:
                                st.error(f"❌ Error al guardar: {str(e)}")

        g = st.session_state.get("asist_guardado")
        if g and not st.session_state.get("asist_colab"):
            st.success(f"✅ Último: **{g['nombre']}** (DNI: {g['dni']}) | {g['marca']} | {g['desde']} → {g['hasta']} ({g['dias']} días) | {g['ts']}")

    # ══════════════════════════ TAB ESPEJO ══════════════════════════
    with tab_espejo:
        st.subheader("📊 Espejo de Asistencia — Matriz de días")
        st.caption("Vista completa de días marcados por colaborador. 🔴 DM = Descanso Médico | 🔵 VAC = Vacaciones")

        df_h = _cargar_df(hoja_asistencia)
        if df_h.empty:
            st.info("ℹ️ Sin registros en la hoja Asistencia")
        else:
            # FIX: si el usuario tiene razón social asignada (no es backoffice),
            # se filtra automáticamente por su dealer. No puede ver otros socios.
            rol_actual = st.session_state.get("rol", "")
            if razon and rol_actual != "backoffice" and "RAZON SOCIAL" in df_h.columns:
                razon_norm = _normalizar_razon(razon)
                df_h = df_h[df_h["RAZON SOCIAL"].astype(str).apply(_normalizar_razon).eq(razon_norm)]

            cf1, cf2, cf3 = st.columns(3)
            with cf1:
                meses = ["TODOS"] + sorted(df_h["MES"].dropna().unique().tolist()) if "MES" in df_h.columns else ["TODOS"]
                mes_sel = st.selectbox("Mes:", meses, key="esp_mes")
            with cf2:
                dni_esp = st.text_input("DNI:", key="esp_dni")
            with cf3:
                # Backoffice puede filtrar por cualquier empresa. Dealer ve solo la suya.
                if rol_actual == "backoffice":
                    razon_esp = st.text_input("Empresa:", key="esp_razon")
                else:
                    st.text_input("Empresa:", value=razon, disabled=True, key="esp_razon")
                    razon_esp = ""  # Ya filtrado arriba, no aplicar dos veces

            df_f = df_h.copy()
            if mes_sel != "TODOS" and "MES" in df_f.columns:
                df_f = df_f[df_f["MES"].astype(str) == mes_sel]
            if dni_esp.strip() and "DNI" in df_f.columns:
                df_f = df_f[df_f["DNI"].astype(str).str.contains(dni_esp.strip(), na=False)]
            if razon_esp.strip() and "RAZON SOCIAL" in df_f.columns:
                df_f = df_f[df_f["RAZON SOCIAL"].astype(str).str.contains(razon_esp.strip(), case=False, na=False)]

            if df_f.empty:
                st.warning("Sin resultados")
            else:
                _render_matriz_espejo(df_f)

    # ══════════════════════════ TAB DOCUMENTOS ══════════════════════════
    with tab_docs:
        st.subheader("📎 Evidencias y Documentos")

        if not hoja_sustentos:
            st.warning("Hoja Sustentos_Bajas no conectada")
        else:
            df_d = _cargar_df(hoja_sustentos)
            if df_d.empty:
                st.info("Sin documentos registrados aún")
            else:
                # FIX: si el usuario tiene razón social asignada (no es backoffice),
                # filtra automáticamente sus documentos. No puede ver los de otros socios.
                rol_actual = st.session_state.get("rol", "")
                if razon and rol_actual != "backoffice" and "RAZON SOCIAL" in df_d.columns:
                    razon_norm = _normalizar_razon(razon)
                    df_d = df_d[df_d["RAZON SOCIAL"].astype(str).apply(_normalizar_razon).eq(razon_norm)]

                cf1, cf2, cf3 = st.columns(3)
                with cf1:
                    dni_d = st.text_input("Buscar por DNI:", key="doc_dni")
                with cf2:
                    per_d = st.text_input("Período (ej: 2026-06):", key="doc_per")
                with cf3:
                    tipo_d = st.selectbox("Tipo:", ["TODOS", "A-BM", "A-VAC", "P-PJ"], key="doc_tipo")

                df_fd = df_d.copy()
                if dni_d.strip() and "DNI" in df_fd.columns:
                    df_fd = df_fd[df_fd["DNI"].astype(str).str.contains(dni_d.strip(), na=False)]
                if per_d.strip() and "PERIODO" in df_fd.columns:
                    df_fd = df_fd[df_fd["PERIODO"].astype(str).str.contains(per_d.strip(), na=False)]
                if tipo_d != "TODOS" and "MOTIVO" in df_fd.columns:
                    df_fd = df_fd[df_fd["MOTIVO"].astype(str).str.contains(tipo_d, na=False)]

                if df_fd.empty:
                    st.warning("Sin resultados")
                else:
                    st.success(f"✅ {len(df_fd)} documento(s) encontrado(s)")
                    _render_tarjetas_docs(df_fd)


def sincronizar_mes(hoja_asistencia, hoja_colaboradores):
    return 0, 0
