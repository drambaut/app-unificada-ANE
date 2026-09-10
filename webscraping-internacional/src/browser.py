"""
browser.py
==========
Gestión del navegador Playwright (Chromium).
Proporciona un contexto de navegador reutilizable con configuración anti-detección.
"""

import asyncio
import logging
import random
from contextlib import asynccontextmanager
from typing import Optional

from playwright.async_api import async_playwright, Browser, BrowserContext, Page

logger = logging.getLogger("telecom_searcher.browser")

# User-Agent real de Chrome para evitar bloqueos
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


@asynccontextmanager
async def get_browser(headless: bool = True):
    """
    Context manager que abre y cierra Playwright + Chromium automáticamente.

    Args:
        headless: Si True, el navegador corre invisible (recomendado para producción).
                  Si False, abre ventana visible (útil para depuración).

    Yields:
        Tupla (browser, context) listos para crear páginas.
    
    Uso:
        async with get_browser(headless=True) as (browser, context):
            page = await context.new_page()
            ...
    """
    async with async_playwright() as playwright:
        logger.info("Iniciando navegador Chromium...")
        browser: Browser = await playwright.chromium.launch(
            headless=headless,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",  # Anti-detección
                "--disable-infobars",
                "--window-size=1366,768",
            ],
        )

        context: BrowserContext = await browser.new_context(
            user_agent=USER_AGENT,
            viewport={"width": 1366, "height": 768},
            locale="es-CO",  # Locale en español (Colombia)
            timezone_id="America/Bogota",
            # Deshabilitar WebDriver flag para evitar detección de bots
            java_script_enabled=True,
        )

        # Eliminar señal de automatización (navigator.webdriver)
        await context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )

        logger.info("Navegador listo.")
        try:
            yield browser, context
        finally:
            logger.info("Cerrando navegador.")
            await browser.close()


async def human_delay(min_sec: float = 1.0, max_sec: float = 3.0):
    """
    Pausa aleatoria para simular comportamiento humano y evitar bloqueos.
    
    Args:
        min_sec: Tiempo mínimo de espera en segundos.
        max_sec: Tiempo máximo de espera en segundos.
    """
    delay = random.uniform(min_sec, max_sec)
    logger.debug(f"Esperando {delay:.1f}s (simulando comportamiento humano)...")
    await asyncio.sleep(delay)


async def safe_goto(page: Page, url: str, timeout: int = 30000) -> bool:
    """
    Navega a una URL con manejo de errores robusto.

    Args:
        page: Página de Playwright.
        url: URL de destino.
        timeout: Timeout en milisegundos.

    Returns:
        True si la navegación fue exitosa, False si falló.
    """
    try:
        logger.info(f"Navegando a: {url}")
        await page.goto(url, timeout=timeout, wait_until="domcontentloaded")
        await human_delay(1.0, 2.0)
        return True
    except Exception as e:
        logger.error(f"Error al navegar a {url}: {e}")
        return False


async def find_element_multi(page: Page, selectors: str, timeout: int = 5000) -> Optional[object]:
    """
    Busca un elemento probando múltiples selectores CSS separados por coma.

    Args:
        page: Página de Playwright.
        selectors: Selectores CSS separados por coma (se prueban en orden).
        timeout: Timeout por selector en milisegundos.

    Returns:
        El primer elemento encontrado, o None si ningún selector funcionó.
    """
    for selector in [s.strip() for s in selectors.split(",")]:
        try:
            element = await page.wait_for_selector(selector, timeout=timeout, state="visible")
            if element:
                logger.debug(f"Elemento encontrado con selector: '{selector}'")
                return element
        except Exception:
            continue
    logger.warning(f"Ningún selector encontró el elemento: {selectors}")
    return None


async def try_search_box(page: Page, site: dict, query: str) -> bool:
    """
    Intenta escribir en la caja de búsqueda y enviar el formulario.

    Args:
        page: Página de Playwright.
        site: Config del sitio con selectores.
        query: Texto a buscar.

    Returns:
        True si la búsqueda fue enviada exitosamente.
    """
    search_box = await find_element_multi(page, site["search_box"])

    if not search_box:
        logger.warning(f"No se encontró barra de búsqueda en {site['name']}")
        return False

    try:
        # Limpiar y escribir con velocidad humana
        await search_box.click(click_count=3)
        await search_box.type(query, delay=random.randint(50, 120))
        await human_delay(0.5, 1.0)

        # Intentar botón de búsqueda, si no hay, usar Enter
        search_button = await find_element_multi(page, site["search_button"], timeout=3000)
        if search_button:
            await search_button.click()
        else:
            await search_box.press("Enter")

        await human_delay(2.0, 3.5)
        return True

    except Exception as e:
        logger.error(f"Error al interactuar con barra de búsqueda: {e}")
        return False
