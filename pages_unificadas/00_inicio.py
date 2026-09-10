from datetime import datetime

import streamlit as st

from shell.app_registry import APPS, SECTION_ICONS

HEADING_COLOR = "#103783"
GRAY_TEXT_COLOR = "#6B7280"
CARD_BG = "#D6E0EC"

st.markdown(
    f"""
    <style>
    div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] div.ane-card-marker) {{
        background-color: {CARD_BG} !important;
        border: 4px solid #879CB3 !important;
        border-radius: 14px;
        transition: box-shadow 0.15s ease;
    }}
    div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] div.ane-card-marker):hover {{
        box-shadow: 0 6px 16px rgba(16, 55, 131, 0.16);
        border-color: #6D84A0 !important;
    }}
    .block-container {{
        padding-left: 0 !important;
        padding-right: 0 !important;
        padding-top: 0 !important;
        max-width: 100% !important;
    }}
    div[data-testid="stAppViewContainer"] > .main {{
        padding-top: 0 !important;
    }}
    [data-testid="stHeader"] {{
        height: 0 !important;
        min-height: 0 !important;
    }}
    .ane-header-banner {{
        position: relative;
        overflow: hidden;
        background: linear-gradient(90deg, #E7ECEF 0%, #274C77 100%);
        border-radius: 0;
        padding: 3.2rem 3.5rem;
        margin: 0 0 2rem 0;
        width: 100%;
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 2rem;
    }}
    .ane-header-left {{
        position: relative;
        z-index: 1;
        display: flex;
        align-items: center;
        gap: 1.5rem;
    }}
    .ane-header-icon-badge {{
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 160px;
        height: 160px;
        min-width: 160px;
        border-radius: 28px;
        background: rgba(255, 255, 255, 0.85);
        font-size: 6rem;
    }}
    .ane-header-title {{
        font-size: 70px !important;
        font-weight: 700 !important;
        color: {HEADING_COLOR} !important;
        margin: 0 !important;
        line-height: 1.1 !important;
    }}
    .ane-header-subtitle {{
        color: {HEADING_COLOR} !important;
        font-size: 30px !important;
        margin-top: 0.5rem !important;
    }}
    .ane-date-box {{
        position: relative;
        z-index: 1;
        background: #FFFFFF;
        border-radius: 12px;
        padding: 1rem 1.8rem;
        text-align: center;
        font-size: 28px !important;
        color: {GRAY_TEXT_COLOR} !important;
        flex-shrink: 0;
    }}
    .ane-date-box b {{
        display: block;
        font-size: 28px !important;
        color: {HEADING_COLOR} !important;
    }}
    /* Margen de 2cm a la izquierda y derecha del contenido (todo lo que va
       debajo del encabezado: títulos de sección y filas de tarjetas). El
       encabezado (.ane-header-banner) no se toca. */
    .ane-section-title {{
        font-size: 40px !important;
        font-weight: 700 !important;
        color: {HEADING_COLOR} !important;
        margin: 1.8rem 2cm 0.9rem 2cm !important;
        padding-bottom: 0.5rem;
        border-bottom: 2px solid rgba(16, 55, 131, 0.2);
        line-height: 1.3 !important;
    }}
    [data-testid="stHorizontalBlock"]:has(div.ane-card-marker) {{
        margin-left: 2cm;
        margin-right: 2cm;
        width: calc(100% - 4cm);
    }}
    .ane-card-header {{
        display: flex;
        align-items: center;
        gap: 0.8rem;
        margin-bottom: 0.6rem;
    }}
    .ane-icon-badge {{
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 64px;
        height: 64px;
        min-width: 64px;
        border-radius: 14px;
        font-size: 2.2rem !important;
        flex-shrink: 0;
    }}
    .ane-card-title {{
        font-weight: 700 !important;
        font-size: 30px !important;
        color: {HEADING_COLOR} !important;
        margin: 0 !important;
        line-height: 1.25 !important;
    }}
    .ane-card-desc {{
        color: {GRAY_TEXT_COLOR} !important;
        font-size: 25px !important;
        min-height: 3.4rem;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)

_MESES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]
_now = datetime.now()
hoy = f"{_now.day} de {_MESES[_now.month - 1]} de {_now.year}"

st.markdown(
    f"""
    <div class="ane-header-banner">
        <div class="ane-header-left">
            <div class="ane-header-icon-badge">📡</div>
            <div>
                <p class="ane-header-title">¡Bienvenido a ANE — App Unificada!</p>
                <p class="ane-header-subtitle">Selecciona una herramienta para empezar. También puedes navegar desde el menú lateral.</p>
            </div>
        </div>
        <div class="ane-date-box">Hoy es<b>{hoy}</b></div>
    </div>
    """,
    unsafe_allow_html=True,
)

sections: dict[str, list] = {}
for app in APPS:
    sections.setdefault(app.section, []).append(app)

for section, apps in sections.items():
    st.markdown(
        f'<div class="ane-section-title">{SECTION_ICONS.get(section, "")} {section}</div>',
        unsafe_allow_html=True,
    )
    n_cols = 3
    cols = st.columns(n_cols, gap="large")
    for i, app in enumerate(apps):
        with cols[i % n_cols]:
            with st.container(border=True):
                st.markdown('<div class="ane-card-marker"></div>', unsafe_allow_html=True)
                st.markdown(
                    f"""
                    <div class="ane-card-header">
                        <div class="ane-icon-badge" style="background:{app.color};">{app.icon}</div>
                        <p class="ane-card-title">{app.title}</p>
                    </div>
                    <p class="ane-card-desc">{app.description}</p>
                    """,
                    unsafe_allow_html=True,
                )
                st.page_link(app.path, label="Abrir", icon="➡️")
