"""Catálogo único de las 8 apps: título, ícono, descripción corta y sección.

Lo usan tanto main.py (para construir la navegación) como la página de
inicio (para pintar las tarjetas), así solo hay que editar esta lista para
cambiar nombres/descripciones en toda la app.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class AppEntry:
    path: str
    title: str
    icon: str
    description: str
    section: str
    color: str = "#EEF2FF"


SECTION_ICONS = {
    "IA generativa": "✨",
    "Datos y reportes": "📊",
    "Formularios y scraping": "📄",
}

APPS: list[AppEntry] = [
    AppEntry(
        path="pages_unificadas/01_analisis_comentarios.py",
        title="Análisis de comentarios",
        icon="💬",
        description="Convierte un Excel de comentarios de consulta pública en un informe ejecutivo con IA.",
        section="IA generativa",
        color="#E0EDFF",
    ),
    AppEntry(
        path="pages_unificadas/02_chatbot_pqrs.py",
        title="Chatbot PQRs",
        icon="🤖",
        description="Asistente conversacional que redacta respuestas formales a PQRs y genera el documento Word.",
        section="IA generativa",
        color="#EDE4FF",
    ),
    AppEntry(
        path="pages_unificadas/03_hoja_ruta.py",
        title="Hoja de Ruta SGP",
        icon="🗺️",
        description="Dashboard de cobertura: qué proyectos cubren cada actividad de la Hoja de Ruta SGP.",
        section="Datos y reportes",
        color="#DFF5F1",
    ),
    AppEntry(
        path="pages_unificadas/04_observatorio_espectro.py",
        title="Observatorio del espectro",
        icon="🔭",
        description="Observatorio de reguladores internacionales sobre uso libre del espectro radioeléctrico.",
        section="Datos y reportes",
        color="#E0EDFF",
    ),
    AppEntry(
        path="pages_unificadas/05_separacion_informacion.py",
        title="Cruce de estaciones base",
        icon="🏢",
        description="Cruza estaciones base de COLOMBIA MÓVIL y COLOMBIA TELECOMUNICACIONES y genera los Excel de salida.",
        section="Datos y reportes",
        color="#DFF5F1",
    ),
    AppEntry(
        path="pages_unificadas/06_vigilancia_tecnologica.py",
        title="Vigilancia tecnológica",
        icon="📡",
        description="Vigilancia tecnológica del espectro: tendencias regulatorias y señales emergentes vía LLM.",
        section="Datos y reportes",
        color="#EDE4FF",
    ),
    AppEntry(
        path="pages_unificadas/07_formulario_banda_900.py",
        title="Formulario Banda 900",
        icon="📋",
        description="Formulario público y panel administrativo para solicitudes de la banda 900 MHz.",
        section="Formularios y scraping",
        color="#E0EDFF",
    ),
    AppEntry(
        path="pages_unificadas/08_webscraping_internacional.py",
        title="Web Searcher internacional",
        icon="🌐",
        description="Búsqueda automatizada de un tema en los 10 principales reguladores internacionales.",
        section="Formularios y scraping",
        color="#DFF5F1",
    ),
]
