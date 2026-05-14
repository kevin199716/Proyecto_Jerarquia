def mostrar_asistencia(
    hoja_asistencia,
    hoja_colaboradores
):

    st.subheader("🗓️ Control de Asistencia")

    # =====================================================
    # SOLO CARGA UNA VEZ
    # =====================================================

    if "df_asistencia" not in st.session_state:

        df_drive, df_mes = preparar_data(
            hoja_asistencia,
            hoja_colaboradores
        )

        # LIMPIAR NONE
        df_mes = df_mes.fillna("")

        # LIMPIAR TEXTO NONE
        df_mes = df_mes.replace("None", "")
        df_mes = df_mes.replace("nan", "")

        st.session_state.df_asistencia = df_mes

    # =====================================================
    # DATA
    # =====================================================

    df = st.session_state.df_asistencia.copy()

    # =====================================================
    # FILTROS
    # =====================================================

    col1, col2 = st.columns(2)

    with col1:

        supervisores = ["TODOS"]

        if "SUPERVISOR" in df.columns:

            supervisores += sorted([
                x for x in
                df["SUPERVISOR"].astype(str).unique().tolist()
                if x != ""
            ])

        filtro_sup = st.selectbox(
            "🔎 Supervisor",
            supervisores
        )

    with col2:

        coordinadores = ["TODOS"]

        if "COORDINADOR" in df.columns:

            coordinadores += sorted([
                x for x in
                df["COORDINADOR"].astype(str).unique().tolist()
                if x != ""
            ])

        filtro_coord = st.selectbox(
            "🔎 Coordinador",
            coordinadores
        )

    # =====================================================
    # FILTRAR
    # =====================================================

    if filtro_sup != "TODOS":

        df = df[
            df["SUPERVISOR"] == filtro_sup
        ]

    if filtro_coord != "TODOS":

        df = df[
            df["COORDINADOR"] == filtro_coord
        ]

    # =====================================================
    # COLUMNAS
    # =====================================================

    columnas_visibles = [

        "PROVINCIA",
        "DNI",
        "NOMBRE",
        "ESTADO"

    ] + COLUMNAS_DIAS

    # =====================================================
    # ASEGURAR COLUMNAS
    # =====================================================

    for col in columnas_visibles:

        if col not in df.columns:
            df[col] = ""

    # =====================================================
    # LIMPIAR VALORES
    # =====================================================

    for col in COLUMNAS_DIAS:

        df[col] = (
            df[col]
            .astype(str)
            .replace("None", "")
            .replace("nan", "")
        )

    # =====================================================
    # SOLO DIA ACTUAL
    # =====================================================

    dia_actual = datetime.now().day

    columna_editable = f"DIA_{dia_actual}"

    # =====================================================
    # CONFIG
    # =====================================================

    config = {}

    for col in columnas_visibles:

        # =============================================
        # COLUMNAS DIA
        # =============================================

        if col.startswith("DIA_"):

            config[col] = st.column_config.SelectboxColumn(

                label=col,

                options=["", "A", "F"],

                width="small",

                required=False,

                disabled=(col != columna_editable)

            )

        # =============================================
        # COLUMNAS TEXTO
        # =============================================

        else:

            config[col] = st.column_config.TextColumn(

                label=col,

                width="medium",

                disabled=True

            )

    # =====================================================
    # EDITOR
    # =====================================================

    edited_df = st.data_editor(

        df[columnas_visibles],

        key="EDITOR_ASISTENCIA",

        use_container_width=True,

        hide_index=True,

        num_rows="fixed",

        height=700,

        column_config=config

    )

    # =====================================================
    # GUARDAR
    # =====================================================

    if st.button("💾 Guardar Asistencia"):

        try:

            # =========================================
            # RECUPERAR COLUMNAS OCULTAS
            # =========================================

            for col in df.columns:

                if col not in edited_df.columns:

                    edited_df[col] = df[col].values

            # =========================================
            # LIMPIAR
            # =========================================

            edited_df = edited_df.fillna("")
            edited_df = edited_df.replace("None", "")
            edited_df = edited_df.replace("nan", "")

            # =========================================
            # ORDEN FINAL
            # =========================================

            edited_df = edited_df[COLUMNAS_FINAL]

            # =========================================
            # GUARDAR DRIVE
            # =========================================

            hoja_asistencia.clear()

            hoja_asistencia.update(
                [
                    edited_df.columns.tolist()
                ]
                +
                edited_df.values.tolist()
            )

            # =========================================
            # SESSION
            # =========================================

            st.session_state.df_asistencia = edited_df

            st.success(
                "✅ Asistencia guardada correctamente"
            )

        except Exception as e:

            st.error(f"❌ Error: {e}")