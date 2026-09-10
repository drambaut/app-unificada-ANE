import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from . import settings

bearer_scheme = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> dict:
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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="El backend no tiene configurado SUPABASE_URL / SUPABASE_ANON_KEY",
        )

    token = credentials.credentials
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
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"No se pudo validar la sesion con Supabase: {exc}",
        )

    if resp.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalido o expirado, vuelve a iniciar sesion",
        )

    data = resp.json()
    return {"sub": data.get("id"), "email": data.get("email")}
