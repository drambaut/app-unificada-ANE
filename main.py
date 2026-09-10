"""Shell único de la app unificada ANE.

Punto de entrada: `streamlit run main.py` desde la raíz de app_unificada.
Aquí, y solo aquí, se llama st.set_page_config() y se define la navegación
entre las 8 herramientas (6 en el mismo proceso Streamlit, 2 embebidas por
iframe vía subproceso local).
"""
import streamlit as st

from shell.app_registry import APPS

st.set_page_config(page_title="ANE — App Unificada", layout="wide", page_icon="📡")

# Paleta forzada en toda la app. Se inyecta DESPUÉS de pg.run() (ver abajo)
# para que siempre quede al final del documento y gane sobre el CSS propio
# de cada sub-app (algunas, como vigilancia-tecnologica, inyectan su propio
# tema con !important también; en un empate de especificidad gana el que
# aparece más tarde en el HTML).
PALETTE_CSS = """
<style>
html, body,
[data-testid="stAppViewContainer"],
[data-testid="stAppViewContainer"] > .main,
[data-testid="stHeader"],
.block-container {
    background-color: #E7ECEF !important;
    color: #111111 !important;
}
/* Marco lateral: el contenido no queda pegado a los bordes */
.block-container {
    padding-left: 3.5rem !important;
    padding-right: 3.5rem !important;
}
/* Campos de texto (text_input / text_area): más anchos/altos, a juego con
   el recuadro de subir archivos, y con la letra de adentro más grande */
input, textarea,
input::placeholder, textarea::placeholder,
[data-testid="stChatInput"] textarea,
[data-testid="stChatInput"] textarea::placeholder {
    font-size: 24px !important;
}
[data-testid="stTextInput"] input,
[data-testid="stTextArea"] textarea {
    padding: 1.4rem 1.2rem !important;
    min-height: 4.5rem !important;
}
/* El contenedor interno de baseweb tiene una altura fija que recorta el
   input más alto de arriba; hay que liberarlo también. */
[data-testid="stTextInputRootElement"],
[data-testid="stTextInputRootElement"] > div {
    height: auto !important;
    min-height: 4.5rem !important;
}
/* Texto de ayuda del subir archivo (ej. "200MB per file - XLSX"), al
   mismo tamaño que el placeholder de los campos de texto */
[data-testid="stFileUploaderDropzoneInstructions"] span {
    font-size: 24px !important;
}
/* Tablas (st.dataframe / st.table): letra más grande */
[data-testid="stDataFrame"],
[data-testid="stTable"] {
    font-size: 25px !important;
}
/* Texto dentro de selects / multiselect (ej. "Choose options") */
[data-baseweb="select"] * {
    font-size: 16px !important;
}
/* Barra de menú lateral */
[data-testid="stSidebar"] {
    background-color: #274C77 !important;
}
[data-testid="stSidebar"] * {
    color: #FFFFFF !important;
    background-color: transparent !important;
}
/* Algunas sub-apps (ej. vigilancia-tecnologica) traen una regla más
   específica para el texto del menú; esta iguala esa especificidad y,
   al ir al final del documento, gana siempre. */
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {
    color: #FFFFFF !important;
}
[data-testid="stSidebar"] [data-testid="stSidebarNavLink"]:hover,
[data-testid="stSidebar"] a:hover {
    background-color: rgba(255, 255, 255, 0.12) !important;
}
/* Títulos de cada apartado del menú (Inicio, IA generativa, ...) */
[data-testid="stNavSectionHeader"] p {
    font-size: 30px !important;
}
/* Resto del menú: los enlaces a cada app */
[data-testid="stSidebarNavLink"] p {
    font-size: 25px !important;
}
/* Espacio entre el último enlace de un apartado y el título del siguiente */
[data-testid="stNavSectionHeader"] {
    margin-top: 2em;
}
/* Las tarjetas y contenedores con borde quedan en blanco para contraste */
div[data-testid="stVerticalBlockBorderWrapper"] {
    background-color: #FFFFFF !important;
}
/* Texto explicativo (párrafos y captions) dentro de las 8 apps */
[data-testid="stMarkdownContainer"] p,
[data-testid="stCaptionContainer"],
[data-testid="stCaptionContainer"] p,
[data-testid="stText"] {
    font-size: 25px;
}
/* Encabezados internos de cada app (###, ####, #####) */
[data-testid="stMarkdownContainer"] h3,
[data-testid="stMarkdownContainer"] h4,
[data-testid="stMarkdownContainer"] h5 {
    font-size: 25px !important;
}
/* Enlace "Abrir" de las tarjetas de Inicio */
[data-testid="stPageLink"],
[data-testid="stPageLink"] p,
[data-testid="stPageLink"] span {
    font-size: 20px !important;
}
</style>
"""

PAGES = {
    "Inicio": [
        st.Page("pages_unificadas/00_inicio.py", title="Inicio", icon="🏠", default=True),
    ],
    "IA generativa": [
        st.Page(app.path, title=app.title, icon=app.icon)
        for app in APPS
        if app.section == "IA generativa"
    ],
    "Datos y reportes": [
        st.Page(app.path, title=app.title, icon=app.icon)
        for app in APPS
        if app.section == "Datos y reportes"
    ],
    "Formularios y scraping": [
        st.Page(app.path, title=app.title, icon=app.icon)
        for app in APPS
        if app.section == "Formularios y scraping"
    ],
}

pg = st.navigation(PAGES)
pg.run()

# Se inyecta al final para ganarle a cualquier CSS que la sub-app haya
# metido durante pg.run() (ver comentario de PALETTE_CSS arriba).
st.markdown(PALETTE_CSS, unsafe_allow_html=True)

# En Inicio no se muestra el menú lateral: aparece solo al entrar a una app.
if pg.title == "Inicio":
    st.markdown(
        """
        <style>
        [data-testid="stSidebar"] {display: none;}
        </style>
        """,
        unsafe_allow_html=True,
    )
