import os
from pathlib import Path

from dotenv import dotenv_values

# Dentro de app-unificada todas las apps comparten el mismo proceso, y
# DATABASE_URL / SUPABASE_* también las leen otras apps (observatorio,
# vigilancia). Por eso el .env de Banda se lee sin escribir en os.environ, y
# cada variable se busca primero como B900_<NOMBRE>; el nombre sin prefijo
# queda como respaldo para el servicio FastAPI existente.
_APP_DIR = Path(__file__).resolve().parent
_ENV_PATH = next(
    (d / ".env" for d in (_APP_DIR, _APP_DIR.parent, _APP_DIR.parent.parent) if (d / ".env").is_file()),
    None,
)
_ENV_FILE = dotenv_values(_ENV_PATH) if _ENV_PATH else {}


def _get(nombre: str) -> str:
    for clave in (f"B900_{nombre}", nombre):
        valor = os.environ.get(clave) or _ENV_FILE.get(clave)
        if valor:
            return valor
    return ""


def valor_b900(nombre: str) -> str:
    """Solo B900_<nombre> (entorno o .env de Banda), sin respaldo al nombre
    legacy: dentro de app-unificada DATABASE_URL puede ser de otra app."""
    clave = f"B900_{nombre}"
    return os.environ.get(clave) or _ENV_FILE.get(clave) or ""


DATABASE_URL = _get("DATABASE_URL")
SUPABASE_URL = _get("SUPABASE_URL")
SUPABASE_ANON_KEY = _get("SUPABASE_ANON_KEY")
SUPABASE_SERVICE_ROLE_KEY = _get("SUPABASE_SERVICE_ROLE_KEY")
SUPABASE_JWT_SECRET = _get("SUPABASE_JWT_SECRET")
