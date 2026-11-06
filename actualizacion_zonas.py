"""Actualización mensual de Departamento/Provincia/Distrito/Zona Agrupada de promotores
activos. Ventana día 3 al 8 del mes; cada partner edita solo a sus propios promotores,
backoffice ve y corrige todos. Trazabilidad completa en la pestaña Historial_Zonas."""
import html
import threading

import gspread
import pandas as pd
import streamlit as st
from gspread.cell import Cell

import actualizacion_zonas_reglas as AZ
import registro_mod as RM
from formulario import (CARGOS_PROMOTOR, asegurar_columnas_colaboradores, leer_colaboradores,
                        leer_ubicaciones, lista_limpia, serie_columna)
from sheets import _abrir_spreadsheet
from zonas import zona_excepcion, zonas_disponibles

LIBRO = "maestra_vendedores"
PESTANA_HISTORIAL = "Historial_Zonas"
COLUMNAS_HISTORIAL = ["TIMESTAMP", "USUARIO", "ROL", "RAZON_SOCIAL", "DNI", "NOMBRE", "PERIODO",
                      "DEPARTAMENTO_ANTERIOR", "PROVINCIA_ANTERIOR", "DISTRITO_ANTERIOR", "ZONA_ANTERIOR",
                      "DEPARTAMENTO_NUEVO", "PROVINCIA_NUEVO", "DISTRITO_NUEVO", "ZONA_NUEVO"]

_LOCK_ZONAS = threading.Lock()


def _e(s) -> str:
    return html.escape(str(s or ""))


class ConflictoError(Exception):
    pass


@st.cache_resource(show_spinner=False)
def _ws_historial():
    libro = _abrir_spreadsheet(LIBRO)
    try:
        return libro.worksheet(PESTANA_HISTORIAL)
    except gspread.exceptions.WorksheetNotFound:
        ws = libro.add_worksheet(title=PESTANA_HISTORIAL, rows=1000, cols=len(COLUMNAS_HISTORIAL))
        ws.append_row(COLUMNAS_HISTORIAL, value_input_option="USER_ENTERED")
        return ws


def _idx(headers: list[str], *nombres):
    for n in nombres:
        if n in headers:
            return headers.index(n) + 1
    return None


def _guardar_zona(hoja_colaboradores, caso: dict, nuevos: dict, ctx: dict) -> None:
    """
    caso: snapshot tomado al abrir el panel — DNI, _FILA (fila estimada), DEPARTAMENTO,
          PROVINCIA, DISTRITO, ZONA_AGRUPADA, RAZON SOCIAL, NOMBRE (valores "antes").
    nuevos: {"DEPARTAMENTO", "PROVINCIA", "DISTRITO", "ZONA_AGRUPADA"} (valores "después").
    Si otro usuario cambió la ubicación desde que se abrió el panel, o el colaborador ya
    no es un promotor activo, no escribe nada y lanza ConflictoError.
    """
    dni_norm = RM.normalizar_dni(caso["DNI"])
    with _LOCK_ZONAS:
        headers = [h.strip().upper() for h in hoja_colaboradores.row_values(1)]
        c_dni = _idx(headers, "DNI")
        c_dep = _idx(headers, "DEPARTAMENTO")
        c_prov = _idx(headers, "PROVINCIA")
        c_dist = _idx(headers, "DISTRITO")
        c_zona = _idx(headers, "ZONA_AGRUPADA")
        c_razon = _idx(headers, "RAZON SOCIAL")
        c_estado = _idx(headers, "ESTADO")
        c_cargo = _idx(headers, "CARGO (ROL)")
        if not all([c_dni, c_dep, c_prov, c_dist, c_zona]):
            raise ConflictoError("Faltan columnas en el Drive (DNI/DEPARTAMENTO/PROVINCIA/DISTRITO/ZONA_AGRUPADA). "
                                 "Actualiza la página.")

        fila = int(caso.get("_FILA") or 0)
        valores_fila = hoja_colaboradores.row_values(fila) if fila >= 2 else []
        actual_dni = RM.normalizar_dni(valores_fila[c_dni - 1]) if len(valores_fila) >= c_dni else ""
        if actual_dni != dni_norm:
            columna_dni = hoja_colaboradores.col_values(c_dni)
            coincidencias = [i + 1 for i, v in enumerate(columna_dni) if RM.normalizar_dni(v) == dni_norm]
            if len(coincidencias) != 1:
                raise ConflictoError("No se pudo ubicar al colaborador de forma única en el Drive "
                                     "(fue dado de baja o duplicado). Actualiza la página.")
            fila = coincidencias[0]
            valores_fila = hoja_colaboradores.row_values(fila)

        def _v(c):
            return valores_fila[c - 1].strip() if c and len(valores_fila) >= c else ""

        if not ctx["es_bo"] and RM._normalizar_razon(_v(c_razon)) != RM._normalizar_razon(ctx["razon"]):
            raise ConflictoError("Este colaborador no pertenece a tu razón social.")
        if _v(c_estado).upper() != "ACTIVO" or (c_cargo and _v(c_cargo) not in CARGOS_PROMOTOR):
            raise ConflictoError("El colaborador ya no figura activo como promotor. Actualiza la página.")

        actuales = {"DEPARTAMENTO": _v(c_dep), "PROVINCIA": _v(c_prov), "DISTRITO": _v(c_dist),
                   "ZONA_AGRUPADA": _v(c_zona)}
        if any(actuales[c] != caso.get(c, "") for c in actuales):
            raise ConflictoError("Otro usuario ya actualizó la ubicación de este colaborador mientras tanto. "
                                 "Se recargaron los datos: revisa y vuelve a guardar.")

        celdas = [Cell(fila, c_dep, nuevos["DEPARTAMENTO"]), Cell(fila, c_prov, nuevos["PROVINCIA"]),
                 Cell(fila, c_dist, nuevos["DISTRITO"]), Cell(fila, c_zona, nuevos["ZONA_AGRUPADA"])]
        hoja_colaboradores.update_cells(celdas, value_input_option="USER_ENTERED")

        ts = RM.ahora_peru_fecha_hora()
        try:
            _ws_historial().append_row(
                [ts, ctx["usuario"], ctx["rol"], _v(c_razon), dni_norm, caso.get("NOMBRE", ""),
                 AZ.periodo_actual(RM.hoy_peru_fecha()),
                 actuales["DEPARTAMENTO"], actuales["PROVINCIA"], actuales["DISTRITO"], actuales["ZONA_AGRUPADA"],
                 nuevos["DEPARTAMENTO"], nuevos["PROVINCIA"], nuevos["DISTRITO"], nuevos["ZONA_AGRUPADA"]],
                value_input_option="USER_ENTERED")
        except Exception as e:
            st.session_state.setdefault("az_flash", []).append(
                ("warning", f"⚠️ Se actualizó la ubicación, pero no se pudo registrar en el historial ({e})."))

    leer_colaboradores(hoja_colaboradores, forzar=True)
    try:
        RM._leer_matriz_cached.clear()
    except Exception:
        pass


def _select_cascada(label: str, opciones: list[str], key: str, valor_inicial: str = "") -> str:
    """Selectbox encadenado: se precarga con valor_inicial la primera vez; si el usuario
    cambia una opción de arriba y el valor ya no es válido, se resetea a vacío (no se queda
    pegado un distrito que ya no corresponde a la nueva provincia)."""
    if key not in st.session_state:
        st.session_state[key] = valor_inicial if valor_inicial in opciones else ""
    elif st.session_state[key] not in [""] + opciones:
        st.session_state[key] = ""
    return st.selectbox(label, [""] + opciones, key=key)


def _panel_edicion(fila: dict, df_ubi: pd.DataFrame, hoja_colaboradores, ctx: dict, editable: bool):
    dni = fila.get("DNI", "")
    nombre = " ".join(x for x in [fila.get("NOMBRES") or fila.get("NOMBRE", ""),
                                  fila.get("APELLIDO PATERNO", ""), fila.get("APELLIDO MATERNO", "")] if x).strip()
    dep_ini, prov_ini, dist_ini, zona_ini = (fila.get("DEPARTAMENTO", ""), fila.get("PROVINCIA", ""),
                                             fila.get("DISTRITO", ""), fila.get("ZONA_AGRUPADA", ""))
    st.markdown(f"#### {_e(nombre) or '—'} · DNI {_e(dni)}")
    st.caption(f"{_e(fila.get('RAZON SOCIAL', ''))} · {_e(fila.get('CARGO (ROL)', ''))}  \n"
              f"Ubicación actual: **{_e(dep_ini) or '—'} / {_e(prov_ini) or '—'} / {_e(dist_ini) or '—'}** · "
              f"zona **{_e(zona_ini) or '—'}**")
    if not editable:
        st.info("🔒 Fuera de la ventana de actualización: solo lectura.")
        return

    nonce = st.session_state.get("az_nonce", 0)
    pref = f"az_{RM.normalizar_dni(dni)}_{nonce}"
    departamentos = lista_limpia(df_ubi, "DEPARTAMENTO")
    departamento = _select_cascada("DEPARTAMENTO", departamentos, f"{pref}_dep", dep_ini)

    df_dep = (df_ubi[serie_columna(df_ubi, "DEPARTAMENTO").str.upper().str.strip().eq(departamento.strip().upper())]
             if departamento else df_ubi.iloc[0:0])
    provincias = lista_limpia(df_dep, "PROVINCIA")
    provincia = _select_cascada("PROVINCIA", provincias, f"{pref}_prov", prov_ini)

    df_prov = (df_dep[serie_columna(df_dep, "PROVINCIA").str.upper().str.strip().eq(provincia.strip().upper())]
              if provincia else df_dep.iloc[0:0])
    distritos = lista_limpia(df_prov, "DISTRITO")
    distrito = _select_cascada("DISTRITO", distritos, f"{pref}_dist", dist_ini)

    zona_fija = zona_excepcion(departamento)
    if zona_fija:
        st.session_state[f"{pref}_zona"] = zona_fija
        zona = st.selectbox("ZONA AGRUPADA", [zona_fija], key=f"{pref}_zona", disabled=True,
                            help=f"{departamento} usa siempre la zona {zona_fija} (regla de negocio).")
    else:
        opciones_zona = zonas_disponibles(departamento, provincia, distrito)
        zona = _select_cascada("ZONA AGRUPADA", opciones_zona, f"{pref}_zona", zona_ini)

    cambio = (departamento, provincia, distrito, zona) != (dep_ini, prov_ini, dist_ini, zona_ini)
    if st.button("💾 Guardar nueva ubicación", type="primary", disabled=not cambio, key=f"{pref}_guardar"):
        errores = []
        if not departamento:
            errores.append("Selecciona el departamento.")
        if not provincia:
            errores.append("Selecciona la provincia.")
        if not distrito:
            errores.append("Selecciona el distrito.")
        if not zona:
            errores.append("Selecciona (o confirma) la zona agrupada.")
        if errores:
            for err in errores:
                st.error(f"❌ {err}")
            return
        try:
            with st.spinner("Guardando en el Drive…"):
                _guardar_zona(
                    hoja_colaboradores,
                    {"DNI": dni, "_FILA": fila.get("_FILA"), "DEPARTAMENTO": dep_ini, "PROVINCIA": prov_ini,
                     "DISTRITO": dist_ini, "ZONA_AGRUPADA": zona_ini, "RAZON SOCIAL": fila.get("RAZON SOCIAL", ""),
                     "NOMBRE": nombre},
                    {"DEPARTAMENTO": departamento, "PROVINCIA": provincia, "DISTRITO": distrito,
                     "ZONA_AGRUPADA": zona},
                    ctx)
        except ConflictoError as e:
            st.warning(f"⚠️ {e}")
            return
        except gspread.exceptions.APIError as e:
            st.error(f"❌ Google Drive no respondió a tiempo ({e}). No se guardó nada; inténtalo nuevamente.")
            return
        st.session_state.setdefault("az_flash", []).append(
            ("success", f"✅ Ubicación de {nombre or dni} actualizada: {departamento} / {provincia} / "
                        f"{distrito} / zona {zona}."))
        st.session_state["az_nonce"] = nonce + 1
        st.rerun()


def mostrar_actualizacion_zonas(hoja_colaboradores, hoja_ubicaciones, razon=None):
    st.markdown('<span class="wow-section-title">🗺️ Actualización de Zonas</span>', unsafe_allow_html=True)
    st.caption("Actualiza Departamento, Provincia, Distrito y Zona Agrupada de tus promotores activos. "
              "Ventana habilitada del día 3 al 8 de cada mes.")

    for tipo, msg in st.session_state.pop("az_flash", []):
        getattr(st, tipo)(msg)

    rol = st.session_state.get("rol", "")
    usuario = st.session_state.get("usuario", "") or "sin_usuario"
    es_bo = rol == "backoffice"
    if not es_bo and not razon:
        st.error("❌ Tu usuario no tiene una razón social asignada. Contacta a backoffice.")
        return

    hoy = RM.hoy_peru_fecha()
    editable, mensaje = AZ.ventana_actualizacion(hoy, es_bo)
    (st.success if editable and "abierta" in mensaje else st.warning if editable else st.info)(
        ("✏️ " if editable else "🔒 ") + mensaje)

    try:
        asegurar_columnas_colaboradores(hoja_colaboradores, AZ.CAMPOS)
    except Exception:
        pass  # no bloquea la lectura si falla; el guardado ya valida que las columnas existan

    df = leer_colaboradores(hoja_colaboradores)
    if df.empty:
        st.info("Sin colaboradores registrados en el Drive.")
        return
    for c in ["DNI", "ESTADO", "CARGO (ROL)", "RAZON SOCIAL", "DEPARTAMENTO", "PROVINCIA", "DISTRITO",
             "ZONA_AGRUPADA", "NOMBRES", "NOMBRE", "APELLIDO PATERNO", "APELLIDO MATERNO"]:
        if c not in df.columns:
            df[c] = ""

    if not es_bo:
        df = df[df["RAZON SOCIAL"].astype(str).apply(RM._normalizar_razon) == RM._normalizar_razon(razon)]
        if df.empty:
            st.warning(f"No hay colaboradores registrados para {razon}.")
            return

    partner = None
    if es_bo:
        partners = sorted({p for p in df["RAZON SOCIAL"].astype(str) if p.strip()})
        elegido = st.selectbox("🏢 Partner", ["TODOS"] + partners, key="az_partner")
        partner = None if elegido == "TODOS" else elegido
        if partner:
            df = df[df["RAZON SOCIAL"] == partner]

    elegibles = df[df["CARGO (ROL)"].isin(CARGOS_PROMOTOR)
                  & (df["ESTADO"].astype(str).str.strip().str.upper() == "ACTIVO")].copy()
    if elegibles.empty:
        st.warning("No hay promotores activos elegibles para actualizar su ubicación "
                   "(cargo Promotor + estado Activo).")
        return
    elegibles["_FILA"] = elegibles.index + 2
    elegibles["NOMBRE_MOSTRAR"] = (
        elegibles["NOMBRES"].where(elegibles["NOMBRES"].astype(str) != "", elegibles["NOMBRE"]).astype(str) + " "
        + elegibles["APELLIDO PATERNO"].astype(str) + " " + elegibles["APELLIDO MATERNO"].astype(str)
    ).str.replace(r"\s+", " ", regex=True).str.strip()
    sin_ubicacion = int((elegibles["DEPARTAMENTO"].astype(str).str.strip() == "").sum())

    k1, k2, k3 = st.columns(3)
    k1.metric("Promotores activos elegibles", len(elegibles))
    k2.metric("Sin ubicación registrada", sin_ubicacion)
    k3.metric("Partners distintos", elegibles["RAZON SOCIAL"].nunique())

    buscar = st.text_input("🔎 Buscar por DNI o nombre", key="az_buscar").strip().upper()
    vista = elegibles
    if buscar:
        texto = vista["DNI"].astype(str).str.upper() + " " + vista["NOMBRE_MOSTRAR"].str.upper()
        vista = vista[texto.str.contains(buscar, regex=False, na=False)]

    cols_tabla = ["DNI", "NOMBRE_MOSTRAR", "RAZON SOCIAL", "DEPARTAMENTO", "PROVINCIA", "DISTRITO", "ZONA_AGRUPADA"]
    st.dataframe(
        vista[cols_tabla].rename(columns={"NOMBRE_MOSTRAR": "NOMBRE", "ZONA_AGRUPADA": "ZONA AGRUPADA"}),
        hide_index=True, use_container_width=True, height=min(420, 46 + 35 * max(1, len(vista))))

    if vista.empty:
        return

    # Se selecciona por DNI (no por posición en la tabla): así `set_value`/pruebas y
    # cualquier reordenamiento de `vista` no dependen de un índice posicional frágil.
    etiquetas = {r["DNI"]: f"{r['DNI']} · {r['NOMBRE_MOSTRAR'] or '—'} · {r['RAZON SOCIAL']}"
                for _, r in vista.iterrows()}
    elegido_dni = st.selectbox("Selecciona un promotor para actualizar su ubicación",
                               [None] + list(etiquetas),
                               format_func=lambda d: etiquetas.get(d, "— Selecciona un promotor —"),
                               key="az_elegido")
    if elegido_dni is not None:
        st.divider()
        df_ubi = leer_ubicaciones(hoja_ubicaciones)
        ctx = {"usuario": usuario, "rol": rol, "razon": razon, "es_bo": es_bo}
        fila = elegibles[elegibles["DNI"] == elegido_dni].iloc[0].to_dict()
        _panel_edicion(fila, df_ubi, hoja_colaboradores, ctx, editable)
