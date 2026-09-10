from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import models, schemas
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
    return db.query(models.Estacion).filter(models.Estacion.origen == "red").all()


@router.post("", response_model=schemas.EstacionOut, status_code=201)
def crear_estacion(
    payload: schemas.EstacionIn,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """RF02: alta manual de una estacion de red y sus antenas por sector."""
    estacion = models.Estacion(
        origen="red",
        tipo_estacion=payload.tipo_estacion,
        latitud=payload.latitud,
        longitud=payload.longitud,
        formato_coordenadas=payload.formato_coordenadas,
        direccion_estacion=payload.direccion_estacion,
        departamento=payload.departamento,
        municipio=payload.municipio,
        cantidad_sectores=payload.cantidad_sectores,
        fuente_carga="manual",
        creado_por=user.get("sub"),
    )
    db.add(estacion)
    db.flush()

    for sec in payload.sectores:
        sector = models.Sector(estacion_id=estacion.id, numero_sector=sec.numero_sector)
        db.add(sector)
        db.flush()
        for ant in sec.antenas:
            antena = models.Antena(sector_id=sector.id, **ant.model_dump())
            db.add(antena)

    db.commit()
    db.refresh(estacion)
    return estacion
