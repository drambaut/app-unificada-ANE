from fastapi import APIRouter

from .. import settings
from ..campos_antena import CAMPOS_ANTENA

router = APIRouter(prefix="/api/config", tags=["config"])


@router.get("/campos-antena")
def campos_antena():
    """Rangos y tooltips (doc 'Rangos / Tooltip') que consume el formulario y el panel admin."""
    return CAMPOS_ANTENA


@router.get("/public")
def public_config():
    """
    Config publica minima para que el frontend pueda inicializar el cliente de
    Supabase Auth sin tener que hornear la URL/anon key en el build de Vite.
    La anon key esta disenada para ser publica (las tablas estan protegidas con RLS).
    """
    return {
        "supabase_url": settings.SUPABASE_URL,
        "supabase_anon_key": settings.SUPABASE_ANON_KEY,
    }
