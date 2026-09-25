from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import schemas, services
from ..database import get_db

router = APIRouter(prefix="/api/solicitudes", tags=["solicitudes"])


@router.post("", response_model=schemas.SolicitudOut, status_code=201)
def crear_solicitud(payload: schemas.SolicitudIn, db: Session = Depends(get_db)):
    """RF01: recepcion del formulario web de la comunidad."""
    return services.crear_solicitud(db, payload)


@router.get("/{solicitud_id}/reporte")
def obtener_reporte(solicitud_id: int, db: Session = Depends(get_db)):
    """RF01: reporte descargable de lo diligenciado por la comunidad."""
    try:
        return services.obtener_reporte(db, solicitud_id)
    except services.SolicitudNoEncontrada:
        raise HTTPException(404, "Solicitud no encontrada")
