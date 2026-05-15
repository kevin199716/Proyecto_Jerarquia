import streamlit as st

def mostrar_bienvenida():
    # Mostrar contenido en la parte principal
    st.markdown(
    """
    <div style='text-align: center;'>
        <img src='https://raw.githubusercontent.com/leocorbur/st_apps/refs/heads/main/images/logo_horizontal_morado.png' width='60%'/>
    </div>
    """,
    unsafe_allow_html=True
    )
    st.markdown("""
        <div style="
            background-color: #FAE8EA;
            border-left: 5px solid #EC6608;
            border-radius: 10px;
            padding: 20px 28px;
            margin: 16px 0 20px 0;
        ">
            <h1 style="color:#4B0067; margin:0 0 8px 0; font-size:1.6em;">
                👋 Bienvenidos al Portal de Gestión de Vendedores Indirectos
            </h1>
            <p style="color:#4B0067; margin:0; font-size:0.95em;">
                Herramienta centralizada para la gestión de la fuerza de ventas indirecta WOW.
            </p>
        </div>
    """, unsafe_allow_html=True)

    st.markdown("""
        Este portal ha sido diseñado para facilitar la gestión de solicitudes relacionadas con vendedores indirectos.

        **Desde aquí podrás:**

        - Registrar nuevas solicitudes de alta de vendedores indirectos
        - Solicitar la baja de vendedores indirectos existentes
        - Hacer seguimiento al estado de tus solicitudes

        Nuestro objetivo es ofrecerte una herramienta ágil y centralizada que simplifique tus gestiones y mejore la comunicación entre tu equipo y el nuestro.

        Si tienes dudas o necesitas asistencia, **no dudes en contactarnos**.

        ¡Gracias por tu colaboración!
    """)
    st.image("https://raw.githubusercontent.com/leocorbur/st_apps/refs/heads/main/images/logo_horizontal_morado.png", width=200) 

    st.markdown(
    """
    <video width="600" autoplay controls>
        <source src="https://raw.githubusercontent.com/leocorbur/st_apps/main/images/wowi.mp4" type="video/mp4">
        Tu navegador no soporta video HTML5.
    </video>
    """,
    unsafe_allow_html=True
)
