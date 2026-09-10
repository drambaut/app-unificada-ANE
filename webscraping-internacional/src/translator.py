"""
translator.py
=============
Módulo de traducción gratuita usando deep_translator (Google Translate sin API key).
Traduce la query del usuario a inglés, español y coreano automáticamente.
"""

import logging
from typing import Dict, Optional

logger = logging.getLogger("telecom_searcher.translator")


def translate_query(query: str, target_languages: list = None) -> Dict[str, str]:
    """
    Traduce una query a los idiomas especificados.

    Args:
        query: Texto original a traducir.
        target_languages: Lista de códigos de idioma destino. 
                         Por defecto: ['en', 'es', 'ko', 'pt']

    Returns:
        Dict con clave=código_idioma y valor=texto traducido.
        Siempre incluye el texto original bajo la clave 'original'.
    """
    if target_languages is None:
        target_languages = ["en", "es", "ko", "pt"]

    translations = {"original": query}

    try:
        from deep_translator import GoogleTranslator
    except ImportError:
        logger.error(
            "deep_translator no está instalado. "
            "Ejecuta: pip install deep-translator"
        )
        # Devuelve el query original para todos los idiomas como fallback
        for lang in target_languages:
            translations[lang] = query
        return translations

    for lang in target_languages:
        try:
            translated = GoogleTranslator(source="auto", target=lang).translate(query)
            translations[lang] = translated
            logger.debug(f"Traducción [{lang}]: '{query}' → '{translated}'")
        except Exception as e:
            logger.warning(f"No se pudo traducir a [{lang}]: {e}. Usando original.")
            translations[lang] = query  # Fallback al original

    return translations


def get_query_for_site(site: dict, translations: Dict[str, str]) -> str:
    """
    Selecciona la query más apropiada para un sitio dado su idioma.

    Args:
        site: Diccionario de configuración del sitio (de sites.json).
        translations: Dict de traducciones generado por translate_query().

    Returns:
        String con la query en el idioma del sitio, o en inglés como fallback.
    """
    site_lang = site.get("language", "en")

    # Mapa de idiomas del sitio → clave en translations
    lang_map = {
        "en": "en",
        "es": "es",
        "ko": "ko",
        "pt": "pt",
        "fr": "fr",
    }

    preferred_lang = lang_map.get(site_lang, "en")

    # Intentar en el idioma del sitio, luego inglés, luego original
    if preferred_lang in translations:
        return translations[preferred_lang]
    elif "en" in translations:
        return translations["en"]
    else:
        return translations.get("original", "")


def get_all_queries_for_site(site: dict, translations: Dict[str, str]) -> list:
    """
    Retorna TODAS las queries a probar para un sitio (multi-idioma).
    Útil para buscar en múltiples idiomas en el mismo sitio.

    Returns:
        Lista de tuplas (idioma, query), sin duplicados.
    """
    queries = []
    seen = set()

    site_lang = site.get("language", "en")

    # Siempre incluir el idioma del sitio primero
    primary = get_query_for_site(site, translations)
    if primary not in seen:
        queries.append((site_lang, primary))
        seen.add(primary)

    # Añadir inglés y español si son distintos
    for lang in ["en", "es"]:
        q = translations.get(lang, "")
        if q and q not in seen:
            queries.append((lang, q))
            seen.add(q)

    return queries
