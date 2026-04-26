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
    #st.title("👋 Bienvenidos al Portal de Gestión de Vendedores Indirectos")
    st.markdown("""
        <h1 style='text-align: center; margin-bottom: 0.5em;'>👋 Bienvenidos al Portal de Gestión de Vendedores Indirectos</h1>
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
