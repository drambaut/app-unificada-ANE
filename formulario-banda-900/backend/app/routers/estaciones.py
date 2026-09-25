from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import schemas, services
from ..auth import get_current_user
from ..database import get_db

router = APIRouter(
    prefix="/api/estaciones",
    tags=["estaciones"],
    dependencies=[Depends(get_current_user)],
)


@router.get("", response_model=list[schemas.EstacionOut])
def listar_estaciones(db: Session = Depends(get_db)):
    """RF02: estaciones de la red cargadas por el Ingeniero GIE."""
    return services.listar_estaciones_red(db)


@router.post("", response_model=schemas.EstacionOut, status_code=201)
def crear_estacion(
    payload: schemas.EstacionIn,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """RF02: alta manual de una estacion de red y sus antenas por sector."""
    return services.crear_estacion(db, payload, user.get("sub"))
