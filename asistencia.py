# asistencia.py
# FIX_ASISTENCIA_SQL_POSTGRES_RENDER_FINAL_20260602
# Versión SQL para Presencialidad. Reemplaza lectura/escritura en Google Sheets.
# Requiere: db.py, sqlalchemy, psycopg2-binary, pandas, streamlit.

from __future__ import annotations

import calendar
from datetime import date, datetime
from typing import Any

import pandas as pd
import streamlit as st

from db import consultar_df, ejecutar_many, ejecutar

try:
    from sheets import subir_archivo_drive
except Exception:
    subir_archivo_drive = None

MARCAS = ["", "A", "A-BM", "A-VAC", "NA-SA", "NA-CA"]
MAX_FILAS_EDITOR = 100  # más alto = más memoria. 100 es estable para Render free.


def _txt(x: Any) -> str:
    if x is None:
        return ""
    s = str(x).strip()
    return "" if s.upper() in ("NONE", "NAN", "NULL") else s


def _periodo_actual() -> str:
    return datetime.now().strftime("%Y-%m")


def _periodos_disponibles(meses_atras: int = 5) -> list[str]:
    hoy = datetime.now()
    salida = []
    y, m = hoy.year, hoy.month
    for i in range(meses_atras + 1):
        yy, mm = y, m - i
        while mm <= 0:
            yy -= 1
            mm += 12
        salida.append(f"{yy}-{mm:02d}")
    return salida


def _dias_periodo(periodo: str) -> list[int]:
    try:
        y, m = [int(x) for x in periodo.split("-")]
        return list(range(1, calendar.monthrange(y, m)[1] + 1))
    except Exception:
        return list(range(1, 32))


def _fecha_asistencia(periodo: str, dia: int) -> date | None:
    try:
        y, m = [int(x) for x in periodo.split("-")]
        return date(y, m, int(dia))
    except Exception:
        return None


def _rol_razon() -> tuple[str, str, str]:
    rol = st.session_state.get("rol", "")
    razon = st.session_state.get("razon", "")
    usuario = st.session_state.get("usuario", st.session_state.get("username", ""))
    return rol, razon, usuario


@st.cache_data(ttl=60, show_spinner=False)
def _opciones_filtros(razon_sesion: str, rol: str) -> dict[str, list[str]]:
    where = "WHERE 1=1"
    params: dict[str, Any] = {}
    if rol != "backoffice" and razon_sesion and razon_sesion.upper() != "ALL":
        where += " AND UPPER(razon_social) = UPPER(:razon)"
        params["razon"] = razon_sesion

    df = consultar_df(f"""
        SELECT
            razon_social, supervisor, coordinador, departamento, provincia
        FROM sales.vw_colaboradores_presencialidad
        {where}
          AND UPPER(COALESCE(estado,'')) = 'ACTIVO'
    """, params)

    def opts(col: str) -> list[str]:
        if df.empty or col not in df.columns:
            return ["TODOS"]
        vals = sorted({_txt(v) for v in df[col].dropna().tolist() if _txt(v)})
        return ["TODOS"] + vals

    return {
        "razon_social": opts("razon_social"),
        "supervisor": opts("supervisor"),
        "coordinador": opts("coordinador"),
        "departamento": opts("departamento"),
        "provincia": opts("provincia"),
    }


def _leer_presencialidad(
    periodo: str,
    dia: int,
    razon_filtro: str,
    supervisor: str,
    coordinador: str,
    departamento: str,
    provincia: str,
    offset: int,
    limit: int,
) -> pd.DataFrame:
    condiciones = ["UPPER(COALESCE(c.estado,'')) = 'ACTIVO'"]
    params: dict[str, Any] = {"periodo": periodo, "dia": int(dia), "limit": limit, "offset": offset}

    if razon_filtro and razon_filtro != "TODOS":
        condiciones.append("UPPER(c.razon_social) = UPPER(:razon)")
        params["razon"] = razon_filtro
    if supervisor and supervisor != "TODOS":
        condiciones.append("UPPER(c.supervisor) = UPPER(:supervisor)")
        params["supervisor"] = supervisor
    if coordinador and coordinador != "TODOS":
        condiciones.append("UPPER(c.coordinador) = UPPER(:coordinador)")
        params["coordinador"] = coordinador
    if departamento and departamento != "TODOS":
        condiciones.append("UPPER(c.departamento) = UPPER(:departamento)")
        params["departamento"] = departamento
    if provincia and provincia != "TODOS":
        condiciones.append("UPPER(c.provincia) = UPPER(:provincia)")
        params["provincia"] = provincia

    where = " AND ".join(condiciones)
    sql = f"""
        SELECT
            c.razon_social AS "RAZON SOCIAL",
            c.dni AS "DNI",
            c.nombre AS "NOMBRE",
            c.supervisor AS "SUPERVISOR",
            c.coordinador AS "COORDINADOR",
            c.departamento AS "DEPARTAMENTO",
            c.provincia AS "PROVINCIA",
            c.estado AS "ESTADO",
            c.fecha_alta AS "FECHA_ALTA",
            c.fecha_cese AS "FECHA_CESE",
            COALESCE(a.marca, '') AS "DIA_{int(dia)}"
        FROM sales.vw_colaboradores_presencialidad c
        LEFT JOIN sales.asistencia_presencialidad a
               ON a.dni = c.dni
              AND a.periodo = :periodo
              AND a.dia = :dia
        WHERE {where}
        ORDER BY c.supervisor NULLS LAST, c.nombre NULLS LAST, c.dni
        LIMIT :limit OFFSET :offset
    """
    return consultar_df(sql, params)


def _contar_registros(periodo: str, dia: int, razon_filtro: str, supervisor: str, coordinador: str, departamento: str, provincia: str) -> int:
    condiciones = ["UPPER(COALESCE(c.estado,'')) = 'ACTIVO'"]
    params: dict[str, Any] = {}
    if razon_filtro and razon_filtro != "TODOS":
        condiciones.append("UPPER(c.razon_social) = UPPER(:razon)")
        params["razon"] = razon_filtro
    if supervisor and supervisor != "TODOS":
        condiciones.append("UPPER(c.supervisor) = UPPER(:supervisor)")
        params["supervisor"] = supervisor
    if coordinador and coordinador != "TODOS":
        condiciones.append("UPPER(c.coordinador) = UPPER(:coordinador)")
        params["coordinador"] = coordinador
    if departamento and departamento != "TODOS":
        condiciones.append("UPPER(c.departamento) = UPPER(:departamento)")
        params["departamento"] = departamento
    if provincia and provincia != "TODOS":
        condiciones.append("UPPER(c.provincia) = UPPER(:provincia)")
        params["provincia"] = provincia
    df = consultar_df(f"SELECT COUNT(*) AS total FROM sales.vw_colaboradores_presencialidad c WHERE {' AND '.join(condiciones)}", params)
    return int(df.iloc[0]["total"]) if not df.empty else 0


def _guardar_lote(cambios: list[dict], usuario: str, periodo: str, dia: int) -> None:
    sql = """
        INSERT INTO sales.asistencia_presencialidad (
            dni, periodo, dia, columna_dia, marca, razon_social, supervisor, coordinador,
            departamento, provincia, usuario_registro, fecha_registro
        ) VALUES (
            :dni, :periodo, :dia, :columna_dia, :marca, :razon_social, :supervisor, :coordinador,
            :departamento, :provincia, :usuario, CURRENT_TIMESTAMP
        )
        ON CONFLICT (dni, periodo, dia)
        DO UPDATE SET
            marca = EXCLUDED.marca,
            razon_social = EXCLUDED.razon_social,
            supervisor = EXCLUDED.supervisor,
            coordinador = EXCLUDED.coordinador,
            departamento = EXCLUDED.departamento,
            provincia = EXCLUDED.provincia,
            usuario_actualizacion = EXCLUDED.usuario_registro,
            fecha_actualizacion = CURRENT_TIMESTAMP
    """
    params = []
    for r in cambios:
        params.append({
            "dni": _txt(r.get("DNI")),
            "periodo": periodo,
            "dia": int(dia),
            "columna_dia": f"DIA_{int(dia)}",
            "marca": _txt(r.get(f"DIA_{int(dia)}")).upper(),
            "razon_social": _txt(r.get("RAZON SOCIAL")),
            "supervisor": _txt(r.get("SUPERVISOR")),
            "coordinador": _txt(r.get("COORDINADOR")),
            "departamento": _txt(r.get("DEPARTAMENTO")),
            "provincia": _txt(r.get("PROVINCIA")),
            "usuario": usuario,
        })
    ejecutar_many(sql, params)


def _guardar_sustento_sql(item: dict, archivo: Any, usuario: str, periodo: str, dia: int, link_documento: str = "") -> None:
    """Sube el sustento a storage externo y guarda el link en PostgreSQL.

    El archivo NO se guarda en Render, porque su filesystem es efímero.
    Si existe sheets.subir_archivo_drive, se usa ese uploader; si falla, se registra
    el nombre de archivo y se levanta el error para no dejar A-BM sin evidencia.
    """
    nombre_archivo = getattr(archivo, "name", "")
    if archivo is not None and subir_archivo_drive is not None and not link_documento:
        contenido = archivo.getvalue()
        mime = getattr(archivo, "type", None) or "application/octet-stream"
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        dni = _txt(item.get("DNI"))
        nombre_archivo_storage = f"sustento_ABM_{dni}_{periodo}_DIA{int(dia)}_{ts}_{nombre_archivo}"
        link_documento = subir_archivo_drive(nombre_archivo_storage, contenido, mime)

    sql = """
        INSERT INTO sales.sustentos_bajas_medicas (
            periodo, dia, columna_dia, fecha_asistencia, dni, nombre, razon_social,
            motivo, nombre_archivo, link_documento, usuario_registro, fecha_subida
        ) VALUES (
            :periodo, :dia, :columna_dia, :fecha_asistencia, :dni, :nombre, :razon_social,
            'A-BM', :nombre_archivo, :link_documento, :usuario, CURRENT_TIMESTAMP
        )
    """
    ejecutar(sql, {
        "periodo": periodo,
        "dia": int(dia),
        "columna_dia": f"DIA_{int(dia)}",
        "fecha_asistencia": _fecha_asistencia(periodo, dia),
        "dni": _txt(item.get("DNI")),
        "nombre": _txt(item.get("NOMBRE")),
        "razon_social": _txt(item.get("RAZON SOCIAL")),
        "nombre_archivo": nombre_archivo,
        "link_documento": link_documento,
        "usuario": usuario,
    })


def mostrar_asistencia(hoja_asistencia=None, hoja_colaboradores=None, razon: str | None = None):
    """Firma compatible con app_maestra_vendedores.py. Los parámetros de Google Sheets ya no se usan."""
    rol, razon_sesion, usuario = _rol_razon()
    razon_base = razon or razon_sesion

    st.subheader("🗓️ Presencialidad Dealer")
    st.caption("Modo SQL: lee colaboradores desde sales.ventas_unificada y guarda marcas en sales.asistencia_presencialidad.")

    c1, c2 = st.columns([2, 1])
    with c1:
        periodo = st.selectbox("Periodo", _periodos_disponibles(), index=0, key="sql_periodo")
    with c2:
        dia = st.selectbox("Día", _dias_periodo(periodo), index=max(0, datetime.now().day - 1), key="sql_dia")

    opciones = _opciones_filtros(razon_base, rol)
    f1, f2, f3, f4, f5 = st.columns(5)
    with f1:
        if rol == "backoffice" or str(razon_base).upper() == "ALL":
            razon_filtro = st.selectbox("Razón Social", opciones["razon_social"], key="sql_f_razon")
        else:
            st.selectbox("Razón Social", [razon_base], index=0, disabled=True, key="sql_f_razon_fixed")
            razon_filtro = razon_base
    with f2:
        supervisor = st.selectbox("Supervisor", opciones["supervisor"], key="sql_f_supervisor")
    with f3:
        coordinador = st.selectbox("Coordinador", opciones["coordinador"], key="sql_f_coordinador")
    with f4:
        departamento = st.selectbox("Departamento", opciones["departamento"], key="sql_f_departamento")
    with f5:
        provincia = st.selectbox("Provincia", opciones["provincia"], key="sql_f_provincia")

    total = _contar_registros(periodo, int(dia), razon_filtro, supervisor, coordinador, departamento, provincia)
    paginas = max(1, (total + MAX_FILAS_EDITOR - 1) // MAX_FILAS_EDITOR)
    pagina = st.selectbox("Bloque de registros", list(range(1, paginas + 1)), key="sql_pagina")
    offset = (int(pagina) - 1) * MAX_FILAS_EDITOR

    with st.spinner("Cargando registros desde PostgreSQL..."):
        df = _leer_presencialidad(periodo, int(dia), razon_filtro, supervisor, coordinador, departamento, provincia, offset, MAX_FILAS_EDITOR)

    st.info(f"Registros encontrados: {total}. Mostrando {len(df)} en este bloque. No se carga toda la base en memoria.")

    if df.empty:
        st.warning("No hay registros activos con los filtros seleccionados.")
        return

    col_dia = f"DIA_{int(dia)}"
    df_original = df.copy()

    with st.form("form_sql_presencialidad", clear_on_submit=False):
        editado = st.data_editor(
            df,
            hide_index=True,
            use_container_width=True,
            num_rows="fixed",
            column_config={
                col_dia: st.column_config.SelectboxColumn(
                    col_dia,
                    options=MARCAS,
                    required=False,
                    help="Marca del día seleccionado",
                )
            },
            disabled=[c for c in df.columns if c != col_dia],
            key="editor_sql_presencialidad",
        )
        guardar = st.form_submit_button("💾 Guardar Presencialidad", use_container_width=True)

    if guardar:
        cambios = []
        for i in range(len(editado)):
            antes = _txt(df_original.iloc[i][col_dia]).upper()
            despues = _txt(editado.iloc[i][col_dia]).upper()
            if antes != despues:
                if despues not in MARCAS:
                    continue
                cambios.append(editado.iloc[i].to_dict())

        if not cambios:
            st.success("✅ Sin cambios pendientes.")
            return

        # Si hay A-BM, se exige documento. Para estabilidad, se solicita después de detectar cambios.
        pendientes_bm = [r for r in cambios if _txt(r.get(col_dia)).upper() == "A-BM"]
        if pendientes_bm:
            st.session_state["sql_pendientes_guardado"] = cambios
            st.session_state["sql_pendientes_bm"] = pendientes_bm
            st.warning(f"Hay {len(pendientes_bm)} baja(s) médica(s). Adjunta sustento antes de confirmar guardado.")
            st.rerun()

        _guardar_lote(cambios, usuario, periodo, int(dia))
        st.success(f"✅ {len(cambios)} registro(s) guardado(s) correctamente.")
        st.cache_data.clear()

    # Bloque de sustentos pendientes, estable y liviano.
    pendientes = st.session_state.get("sql_pendientes_bm", [])
    cambios_pend = st.session_state.get("sql_pendientes_guardado", [])
    if pendientes:
        st.divider()
        st.subheader("📎 Sustento obligatorio A-BM")
        st.caption("Adjunta sustento para cada baja médica. Luego confirma el guardado completo.")
        archivos_ok = {}
        for idx, item in enumerate(pendientes, start=1):
            dni = _txt(item.get("DNI"))
            nombre = _txt(item.get("NOMBRE"))
            st.markdown(f"**{idx}. {dni} - {nombre}**")
            archivo = st.file_uploader(
                "PDF o imagen",
                type=["pdf", "png", "jpg", "jpeg"],
                key=f"sql_file_bm_{dni}_{periodo}_{dia}",
            )
            if archivo:
                st.success(f"✅ Documento cargado correctamente: {archivo.name}")
                archivos_ok[dni] = archivo

        if st.button("✅ Confirmar guardado con sustentos", use_container_width=True):
            faltantes = [r for r in pendientes if _txt(r.get("DNI")) not in archivos_ok]
            if faltantes:
                st.error(f"Faltan {len(faltantes)} sustento(s). No se guardó el lote.")
                return
            _guardar_lote(cambios_pend, usuario, periodo, int(dia))
            for r in pendientes:
                dni = _txt(r.get("DNI"))
                _guardar_sustento_sql(r, archivos_ok[dni], usuario, periodo, int(dia), link_documento="")
            st.session_state.pop("sql_pendientes_bm", None)
            st.session_state.pop("sql_pendientes_guardado", None)
            st.success(f"✅ {len(cambios_pend)} registro(s) guardado(s) correctamente. Sustentos A-BM registrados: {len(pendientes)}.")
            st.cache_data.clear()
            st.rerun()

    # Espejo mensual resumido, no carga todo por defecto.
    with st.expander("📊 Ver resumen del día seleccionado", expanded=False):
        resumen = consultar_df("""
            SELECT marca, COUNT(*) AS cantidad
            FROM sales.asistencia_presencialidad
            WHERE periodo = :periodo
              AND dia = :dia
              AND (:razon = 'TODOS' OR UPPER(razon_social) = UPPER(:razon))
            GROUP BY marca
            ORDER BY marca
        """, {"periodo": periodo, "dia": int(dia), "razon": razon_filtro or "TODOS"})
        st.dataframe(resumen, use_container_width=True, hide_index=True)

    with st.expander("📥 Descargar jerarquía actual", expanded=False):
        if st.button("Cargar jerarquía para descarga", key="sql_cargar_jerarquia"):
            where = "WHERE 1=1"
            params = {}
            if rol != "backoffice" and razon_base and razon_base.upper() != "ALL":
                where += " AND UPPER(razon_social) = UPPER(:razon)"
                params["razon"] = razon_base
            jer = consultar_df(f"""
                SELECT *
                FROM sales.ventas_unificada
                {where}
                ORDER BY razon_social, supervisor_a_cargo, nombres
            """, params)
            st.dataframe(jer, use_container_width=True, hide_index=True)
            st.download_button(
                "⬇️ Descargar jerarquía CSV",
                data=jer.to_csv(index=False).encode("utf-8-sig"),
                file_name=f"jerarquia_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                mime="text/csv",
                use_container_width=True,
            )
