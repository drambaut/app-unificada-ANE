from supabase import Client, create_client

from . import settings

BUCKET_CARGAS = "cargas-antenas"

_client: Client | None = None


def get_supabase() -> Client:
    global _client
    if _client is None:
        if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_ROLE_KEY:
            raise RuntimeError(
                "Faltan SUPABASE_URL o SUPABASE_SERVICE_ROLE_KEY en las variables de entorno"
            )
        _client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)
    return _client


def ensure_bucket_cargas() -> None:
    """Crea el bucket de storage para cargas masivas si aun no existe. No falla el arranque si algo sale mal."""
    try:
        client = get_supabase()
        buckets = client.storage.list_buckets()
        nombres = [b.name for b in buckets] if buckets else []
        if BUCKET_CARGAS not in nombres:
            client.storage.create_bucket(BUCKET_CARGAS, options={"public": False})
    except Exception:
        # No bloquear el arranque de la app; si falla, el bucket se puede crear
        # manualmente en el dashboard de Supabase (Storage -> New bucket).
        pass