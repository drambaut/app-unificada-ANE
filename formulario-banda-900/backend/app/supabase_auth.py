"""Validación de sesiones de Supabase Auth, independiente de FastAPI."""
import httpx

from . import settings


class AuthError(Exception):
    """Sesión no válida o no verificable; lleva el status HTTP equivalente."""

    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


def usuario_desde_token(token: str) -> dict:
    """
    Valida la sesion del usuario contra la API de Supabase Auth
    (GET /auth/v1/user), en vez de verificar la firma del JWT localmente.

    Por que asi y no con SUPABASE_JWT_SECRET + PyJWT: Supabase puede firmar
    los tokens con distintos algoritmos segun la configuracion del proyecto
    (HS256 con secreto compartido en proyectos antiguos, o claves asimetricas
    ES256/RS256 en proyectos nuevos con "JWT Signing Keys"). Verificar contra
    la API siempre funciona sin importar el algoritmo, y evita el error
    "Token invalido o expirado" causado por una discrepancia de algoritmo o
    por haber copiado mal el JWT secret.
    """
    if not settings.SUPABASE_URL or not settings.SUPABASE_ANON_KEY:
        raise AuthError(500, "El backend no tiene configurado SUPABASE_URL / SUPABASE_ANON_KEY")

    try:
        resp = httpx.get(
            f"{settings.SUPABASE_URL}/auth/v1/user",
            headers={
                "Authorization": f"Bearer {token}",
                "apikey": settings.SUPABASE_ANON_KEY,
            },
            timeout=10.0,
        )
    except httpx.HTTPError as exc:
        raise AuthError(502, f"No se pudo validar la sesion con Supabase: {exc}")

    if resp.status_code != 200:
        raise AuthError(401, "Token invalido o expirado, vuelve a iniciar sesion")

    data = resp.json()
    return {"sub": data.get("id"), "email": data.get("email")}


# ── Sesión del lado del servidor (equivalente a supabase-js en AdminLogin/AdminPanel) ──
def _cliente_auth():
    """Cliente nuevo por operación con la anon key: la sesión nunca se comparte
    entre usuarios ni se refresca sola en segundo plano."""
    if not settings.SUPABASE_URL or not settings.SUPABASE_ANON_KEY:
        raise AuthError(500, "El backend no tiene configurado SUPABASE_URL / SUPABASE_ANON_KEY")
    # Import diferido: el servicio FastAPI también importa este módulo y no lo usa.
    from supabase import create_client
    try:
        from supabase.lib.client_options import SyncClientOptions as Opciones
    except ImportError:  # versiones antiguas de supabase-py
        from supabase.lib.client_options import ClientOptions as Opciones
    return create_client(
        settings.SUPABASE_URL,
        settings.SUPABASE_ANON_KEY,
        Opciones(auto_refresh_token=False, persist_session=False),
    )


def _datos_sesion(resp) -> dict:
    sesion, usuario = getattr(resp, "session", None), getattr(resp, "user", None)
    if not sesion or not usuario:
        raise AuthError(401, "No fue posible iniciar sesión")
    return {
        "access_token": sesion.access_token,
        "refresh_token": sesion.refresh_token,
        "expires_at": sesion.expires_at,
        "user_id": usuario.id,
        "email": usuario.email,
    }


def iniciar_sesion(email: str, password: str) -> dict:
    """signInWithPassword de Supabase Auth; devuelve tokens y usuario."""
    cliente = _cliente_auth()
    try:
        resp = cliente.auth.sign_in_with_password({"email": email, "password": password})
    except Exception as exc:  # noqa: BLE001 (AuthApiError, errores de red, ...)
        raise AuthError(401, str(exc) or "No fue posible iniciar sesión")
    return _datos_sesion(resp)


def refrescar_sesion(refresh_token: str) -> dict:
    """Renueva una sesión expirada con su refresh token."""
    cliente = _cliente_auth()
    try:
        resp = cliente.auth.refresh_session(refresh_token)
    except Exception as exc:  # noqa: BLE001
        raise AuthError(401, str(exc) or "La sesión expiró, vuelve a iniciar sesión")
    return _datos_sesion(resp)


def cerrar_sesion(access_token: str, refresh_token: str) -> None:
    """signOut de supabase-js (alcance global). Si falla, la sesión local igual se descarta."""
    try:
        cliente = _cliente_auth()
        cliente.auth.set_session(access_token, refresh_token)
        cliente.auth.sign_out({"scope": "global"})
    except Exception:  # noqa: BLE001
        pass
