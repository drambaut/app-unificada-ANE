"""Taxonomías controladas y normalización para la capa de datos del dashboard."""
from __future__ import annotations
import ast
import json
import re
import unicodedata
from typing import Any, Mapping

TEMAS_ESTRATEGICOS = ["Disponibilidad de espectro para IMT", "Conectividad satelital, NTN y D2D", "Bandas medias y altas para servicios móviles", "6 GHz, Wi-Fi e IMT", "Spectrum sharing y mecanismos flexibles", "Redes privadas y verticales industriales", "Armonización y gestión internacional", "Necesidades transversales y capacidades institucionales", "Otros temas de seguimiento"]
LINEAS_PMGE = ["Disponibilidad de espectro", "Conectividad satelital", "Innovación en gestión y uso del espectro", "Gestión internacional del espectro", "Necesidades transversales"]
TIPOS_INSUMO_AGENDA = ["Nueva iniciativa", "Ajuste a iniciativa existente", "Nota técnica", "Seguimiento", "No prioritario"]
RELEVANCIA_LABELS = ["Alta", "Media", "Baja"]
TIPOS_EVENTO_REGULATORIO = ["Subasta", "Consulta pública", "Refarming", "Asignación de espectro", "Compartición de espectro", "Renovación", "Topes de espectro", "Tasas / fees", "Condiciones técnicas", "Armonización internacional", "Salud / EMF", "Otro"]

# Lecturas regulatorias determinísticas. Estos textos son reglas de taxonomía,
# no contenido generado ni datos fijos de presentación en el dashboard.
REGULATORY_PROFILES: dict[str, dict[str, str]] = {
    "6 GHz, Wi-Fi e IMT": {
        "subtema": "Upper 6 GHz / Wi-Fi / IMT",
        "debate": "Definición del uso de la banda 6 GHz entre Wi-Fi, IMT o esquemas compartidos.",
        "implicacion": "Seguimiento técnico sobre coexistencia, armonización internacional y posibles escenarios de decisión regulatoria.",
        "nombre": "Competencia regulatoria por la banda 6 GHz",
        "trata": "La banda 6 GHz aparece como un espacio de disputa regulatoria entre su uso para Wi-Fi avanzado, su posible identificación para IMT y esquemas de uso compartido.",
        "pasando": "Los documentos revisados muestran discusiones sobre si esta banda debe mantenerse para uso no licenciado, abrirse a servicios móviles o gestionarse mediante modelos híbridos.",
        "importa": "La decisión puede afectar la disponibilidad futura de espectro para conectividad de alta capacidad, innovación en redes inalámbricas y armonización regional.",
    },
    "Conectividad satelital, NTN y D2D": {
        "subtema": "Direct-to-device / NTN",
        "debate": "Integración de servicios satelitales con redes móviles y conectividad directa a dispositivos.",
        "implicacion": "Analizar condiciones de autorización, interferencia, coordinación internacional y compatibilidad con atribuciones actuales.",
        "nombre": "Expansión de conectividad satelital directa a dispositivos",
        "trata": "Los servicios satelitales direct-to-device buscan conectar teléfonos o dispositivos IoT directamente con satélites, sin depender completamente de infraestructura terrestre.",
        "pasando": "El mercado y los reguladores están explorando modelos de conectividad satelital integrada con redes móviles, especialmente para cobertura en zonas remotas o de emergencia.",
        "importa": "Puede cambiar la forma en que se entiende la cobertura móvil, la asignación de bandas y la coordinación entre servicios terrestres y satelitales.",
    },
    "Spectrum sharing y mecanismos flexibles": {
        "subtema": "Compartición dinámica del espectro",
        "debate": "Uso de modelos flexibles o compartidos de acceso al espectro, incluyendo bases de datos, licencias locales o uso secundario.",
        "implicacion": "Explorar pilotos regulatorios, reglas de coexistencia y mecanismos de autorización más flexibles.",
        "nombre": "Uso flexible y compartido del espectro",
        "trata": "La gestión del espectro está migrando de esquemas rígidos de asignación exclusiva hacia modelos más flexibles, compartidos o dinámicos.",
        "pasando": "Se observan discusiones sobre licenciamiento local, uso secundario, compartición dinámica, bases de datos de coordinación y esquemas de acceso diferenciado.",
        "importa": "Estos modelos pueden mejorar la eficiencia en el uso del espectro y habilitar nuevos actores o servicios sin esperar grandes procesos de asignación nacional.",
    },
    "Redes privadas y verticales industriales": {
        "subtema": "Espectro local para industria",
        "debate": "Demanda de espectro para redes privadas en sectores productivos e industriales.",
        "implicacion": "Evaluar esquemas de asignación local, permisos sectoriales y condiciones técnicas diferenciadas.",
        "nombre": "Redes privadas para sectores industriales",
        "trata": "Sectores productivos están demandando espectro para redes privadas que soporten automatización, IoT industrial, operación remota y comunicaciones críticas.",
        "pasando": "Los reguladores están explorando esquemas de asignación local, licencias sectoriales o condiciones diferenciadas para verticales industriales.",
        "importa": "Puede ampliar el uso del espectro más allá de operadores móviles tradicionales y exigir reglas específicas para industria, energía, logística o minería.",
    },
    "Disponibilidad de espectro para IMT": {
        "subtema": "Bandas bajas, medias y altas para IMT",
        "debate": "Disponibilidad de espectro para cobertura, capacidad y evolución hacia 5G/5G-Advanced.",
        "implicacion": "Priorizar análisis de disponibilidad, necesidades futuras de espectro y condiciones de armonización.",
        "nombre": "Mayor presión por disponibilidad de espectro para 5G y 5G-Advanced",
        "trata": "La evolución hacia 5G avanzado exige revisar la disponibilidad de bandas bajas, medias y altas para cobertura, capacidad y nuevos casos de uso.",
        "pasando": "Los documentos muestran interés en procesos de asignación, reorganización de bandas, condiciones técnicas y modelos de uso eficiente del espectro móvil.",
        "importa": "La disponibilidad de espectro condiciona el despliegue de redes, la calidad del servicio y la competitividad digital del país.",
    },
    "Bandas medias y altas para servicios móviles": {
        "subtema": "Bandas medias, mmWave y evolución hacia 6G",
        "debate": "Identificación y ordenamiento de bandas medias y altas para capacidad móvil, usos locales y evolución tecnológica.",
        "implicacion": "Evaluar planes de banda, coexistencia y condiciones de asignación para usos nacionales y locales.",
        "nombre": "Reordenamiento de bandas medias y altas para redes avanzadas",
        "trata": "Las bandas medias y milimétricas concentran decisiones sobre capacidad 5G, despliegues locales y preparación de espectro para redes de nueva generación.",
        "pasando": "Los reguladores comparan procesos de asignación, licencias locales y condiciones de coexistencia en bandas con distintos niveles de madurez y ecosistema.",
        "importa": "Estas decisiones definen cuánto espectro de alta capacidad puede movilizarse y bajo qué condiciones técnicas y territoriales.",
    },
    "Armonización y gestión internacional": {
        "subtema": "Seguimiento internacional UIT/CITEL/WRC",
        "debate": "Seguimiento de decisiones internacionales que afectan atribuciones, bandas, límites técnicos y prioridades regionales.",
        "implicacion": "Alinear posiciones nacionales con tendencias internacionales y preparar insumos para agenda regulatoria.",
        "nombre": "Alineación internacional de decisiones sobre espectro",
        "trata": "Las decisiones de organismos y mercados internacionales influyen en la forma en que se definen atribuciones, bandas prioritarias y condiciones técnicas.",
        "pasando": "Los documentos muestran referencias a procesos internacionales, posiciones regionales y seguimiento de decisiones de organismos como UIT, CITEL o WRC.",
        "importa": "La gestión nacional del espectro requiere consistencia con tendencias internacionales para reducir riesgos de fragmentación y facilitar economías de escala.",
    },
}

REGULATORY_FALLBACK = {
    "subtema": "Seguimiento general",
    "debate": "Tema identificado en el corpus que requiere seguimiento técnico adicional.",
    "implicacion": "Evaluar pertinencia para la Agenda ANE según recurrencia, fuente y relevancia.",
    "nombre": "Seguimiento regulatorio de temas transversales",
    "trata": "El corpus identifica un frente de seguimiento que conecta cambios tecnológicos con decisiones de gestión del espectro.",
    "pasando": "Las fuentes revisadas registran actuaciones, consultas o discusiones que requieren consolidación técnica antes de definir una respuesta regulatoria.",
    "importa": "Su recurrencia y relevancia pueden convertirlo en un insumo para priorizar estudios, coordinación institucional o ajustes de agenda.",
}


def regulatory_profile(topic: str) -> dict[str, str]:
    """Devuelve la lectura regulatoria controlada para un tema macro."""
    return REGULATORY_PROFILES.get(str(topic).strip(), REGULATORY_FALLBACK).copy()


def infer_regulatory_subtopic(topic: str, technologies: Any, bands: Any, signal: str = "") -> str:
    """Refina el segundo nivel del mapa con evidencia presente en cada registro."""
    profile = regulatory_profile(topic)
    haystack = _key(" ".join(
        [str(topic), str(signal)] + parse_list_field(technologies) + parse_list_field(bands)
    ))
    if topic == "Conectividad satelital, NTN y D2D":
        if any(term in haystack for term in ("d2d", "direct-to-device", "direct to device", "scs")):
            return "Conectividad directa a dispositivos"
        if any(term in haystack for term in ("leo", "meo", "geo", "ngso", "constelacion")):
            return "Constelaciones y coordinación satelital"
    if topic == "Disponibilidad de espectro para IMT":
        if any(term in haystack for term in ("600 mhz", "700 mhz", "800 mhz", "900 mhz")):
            return "Bandas bajas para cobertura IMT"
        if any(term in haystack for term in ("2.3 ghz", "2.6 ghz", "3.5 ghz", "3.3-3.8 ghz")):
            return "Bandas medias para capacidad IMT"
    if topic == "Bandas medias y altas para servicios móviles":
        if any(term in haystack for term in ("26 ghz", "28 ghz", "37 ghz", "40 ghz", "mmwave")):
            return "Bandas milimétricas para alta capacidad"
    if topic == "Spectrum sharing y mecanismos flexibles":
        if any(term in haystack for term in ("local", "licencia local", "private", "privada")):
            return "Licenciamiento local y acceso diferenciado"
    return profile["subtema"]

def _key(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    return re.sub(r"\s+", " ", "".join(c for c in text if not unicodedata.combining(c)).strip().casefold())

TECHNOLOGY_NORMALIZATION = {
    "5g": "5G", "5g sa": "5G", "5g stand alone": "5G", "5g-advanced": "5G-Advanced", "5g advanced": "5G-Advanced", "6g": "6G",
    "d2d": "D2D", "direct-to-device": "D2D", "direct to device": "D2D", "ntn": "NTN", "non-terrestrial networks": "NTN", "redes no terrestres": "NTN",
    "iot": "IoT", "nb-iot": "NB-IoT", "nb iot": "NB-IoT", "wi-fi": "Wi-Fi", "wifi": "Wi-Fi", "wi fi": "Wi-Fi", "wi-fi 6e": "Wi-Fi 6E", "wifi 6e": "Wi-Fi 6E", "wi-fi 7": "Wi-Fi 7", "wifi 7": "Wi-Fi 7",
    "open ran": "Open RAN", "open-ran": "Open RAN", "haps": "HAPS", "leo": "LEO", "meo": "MEO", "geo": "GEO", "tvws": "TVWS",
    "ia": "IA", "ai": "IA", "inteligencia artificial": "IA", "artificial intelligence": "IA", "mmwave": "mmWave", "mm wave": "mmWave",
    "redes privadas": "Redes privadas", "private networks": "Redes privadas", "spectrum sharing": "Spectrum sharing", "comparticion de espectro": "Spectrum sharing",
}
BAND_NORMALIZATION = {
    "600 mhz": "600 MHz", "700 mhz": "700 MHz", "800 mhz": "800 MHz", "900 mhz": "900 MHz", "1800 mhz": "1800 MHz",
    "2.1 ghz": "2.1 GHz", "2,1 ghz": "2.1 GHz", "2.3 ghz": "2.3 GHz", "2,3 ghz": "2.3 GHz", "2.6 ghz": "2.6 GHz", "2,6 ghz": "2.6 GHz",
    "3.3-3.8 ghz": "3.3-3.8 GHz", "3,3-3,8 ghz": "3.3-3.8 GHz", "3.5 ghz": "3.5 GHz", "3,5 ghz": "3.5 GHz", "6 ghz": "6 GHz", "upper 6 ghz": "upper 6 GHz", "6 ghz superior": "upper 6 GHz",
    "26 ghz": "26 GHz", "28 ghz": "28 GHz", "37 ghz": "37 GHz", "40 ghz": "40 GHz", "mmwave": "mmWave", "mm wave": "mmWave", "uhf": "UHF", "vhf": "VHF",
    "banda ka": "banda Ka", "ka-band": "banda Ka", "ka band": "banda Ka", "banda ku": "banda Ku", "ku-band": "banda Ku", "ku band": "banda Ku",
}

def normalize_text_label(value: str) -> str:
    text = re.sub(r"\s+", " ", str(value or "").strip())
    return text[:1].upper() + text[1:] if text else ""

def parse_list_field(value: Any) -> list[str]:
    if value is None or (isinstance(value, float) and value != value): return []
    if isinstance(value, (list, tuple, set)): return [str(x).strip() for x in value if str(x).strip()]
    text = str(value).strip()
    if not text or text.casefold() in {"nan", "none", "null", "[]"}: return []
    for parser in (json.loads, ast.literal_eval):
        try:
            parsed = parser(text)
            if isinstance(parsed, (list, tuple, set)): return [str(x).strip() for x in parsed if str(x).strip()]
        except (ValueError, SyntaxError, TypeError, json.JSONDecodeError): pass
    return [x.strip() for x in re.split(r"[;,|]", text) if x.strip()]

def normalize_list(values: Any, normalization_dict: Mapping[str, str]) -> list[str]:
    lookup = {_key(k): v for k, v in normalization_dict.items()}
    result: list[str] = []
    for raw in parse_list_field(values):
        key = _key(raw)
        canonical = lookup.get(key)
        if canonical is None:
            matches = [(len(alias), value) for alias, value in lookup.items() if re.search(rf"(?<!\w){re.escape(alias)}(?!\w)", key)]
            canonical = max(matches, default=(0, normalize_text_label(raw)))[1]
        if canonical and canonical not in result: result.append(canonical)
    return result

def normalize_technologies(values: Any) -> list[str]: return normalize_list(values, TECHNOLOGY_NORMALIZATION)
def normalize_bands(values: Any) -> list[str]: return normalize_list(values, BAND_NORMALIZATION)

def infer_tema_estrategico(tecnologias: Any, bandas: Any, senal_regulatoria: Any, tema_principal: str = "", resumen: str = "") -> str:
    haystack = " " + _key(" ".join(normalize_technologies(tecnologias) + normalize_bands(bandas) + [str(senal_regulatoria), tema_principal, resumen])) + " "
    rules = [
        (["d2d", "ntn", "satelit", "leo", "meo", "geo", "haps"], TEMAS_ESTRATEGICOS[1]),
        (["700 mhz", "3.5 ghz", "imt", "5g", "5g-advanced"], TEMAS_ESTRATEGICOS[0]),
        (["26 ghz", "28 ghz", "37 ghz", "40 ghz", "mmwave"], TEMAS_ESTRATEGICOS[2]),
        (["6 ghz", "wi-fi", "wifi", "wi fi 6e", "wi fi 7"], TEMAS_ESTRATEGICOS[3]),
        (["spectrum sharing", "comparticion", "dynamic sharing", " ia ", " ai ", "inteligencia artificial"], TEMAS_ESTRATEGICOS[4]),
        (["redes privadas", "private networks", "verticales industriales"], TEMAS_ESTRATEGICOS[5]),
        (["armonizacion", "wrc", "cmr", "uit", "citel", "itu"], TEMAS_ESTRATEGICOS[6]),
    ]
    for needles, topic in rules:
        if any(n in haystack for n in needles): return topic
    return TEMAS_ESTRATEGICOS[-1]

def map_tema_to_linea_pmge(tema_estrategico: str) -> str:
    mapping = {TEMAS_ESTRATEGICOS[0]: LINEAS_PMGE[0], TEMAS_ESTRATEGICOS[2]: LINEAS_PMGE[0], TEMAS_ESTRATEGICOS[3]: LINEAS_PMGE[0], TEMAS_ESTRATEGICOS[1]: LINEAS_PMGE[1], TEMAS_ESTRATEGICOS[4]: LINEAS_PMGE[2], TEMAS_ESTRATEGICOS[5]: LINEAS_PMGE[2], TEMAS_ESTRATEGICOS[6]: LINEAS_PMGE[3], TEMAS_ESTRATEGICOS[7]: LINEAS_PMGE[4], TEMAS_ESTRATEGICOS[8]: LINEAS_PMGE[4]}
    return mapping.get(tema_estrategico, LINEAS_PMGE[4])

def infer_tipo_evento_regulatorio(text: str) -> list[str]:
    haystack = _key(text)
    rules = [("Subasta", ["subasta", "auction"]), ("Consulta pública", ["consulta publica", "public consultation"]), ("Refarming", ["refarming", "reordenamiento"]), ("Asignación de espectro", ["asignacion", "licenciamiento", "assignment"]), ("Compartición de espectro", ["comparticion", "spectrum sharing"]), ("Renovación", ["renovacion", "renewal"]), ("Topes de espectro", ["tope de espectro", "spectrum cap"]), ("Tasas / fees", ["tasa", "tarifa", "fee", "pricing"]), ("Condiciones técnicas", ["condiciones tecnicas", "technical condition"]), ("Armonización internacional", ["armonizacion", "wrc", "cmr", "uit", "itu", "citel"]), ("Salud / EMF", ["emf", "campo electromagnet", "salud"])]
    found = [label for label, terms in rules if any(term in haystack for term in terms)]
    return found or ["Otro"]
