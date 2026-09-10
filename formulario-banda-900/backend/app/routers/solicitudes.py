from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, selectinload

from .. import models, schemas
from ..database import get_db

router = APIRouter(prefix="/api/solicitudes", tags=["solicitudes"])


@router.post("", response_model=schemas.SolicitudOut, status_code=201)
def crear_solicitud(payload: schemas.SolicitudIn, db: Session = Depends(get_db)):
    """RF01: recepcion del formulario web de la comunidad."""
    solicitud = models.Solicitud(
        razon_social=payload.razon_social,
        nit=payload.nit,
        representante_legal=payload.representante_legal,
        telefono=payload.telefono,
        direccion=payload.direccion,
        correo_electronico=payload.correo_electronico,
        radicado_mintic=payload.radicado_mintic,
    )
    db.add(solicitud)
    db.flush()  # asigna solicitud.id

    for est in payload.estaciones:
        estacion = models.Estacion(
            origen="comunidad",
            solicitud_id=solicitud.id,
            latitud=est.latitud,
            longitud=est.longitud,
            formato_coordenadas=est.formato_coordenadas,
            direccion_estacion=est.direccion_estacion,
            departamento=est.departamento,
            municipio=est.municipio,
            cantidad_sectores=est.cantidad_sectores,
            tipo_estacion=est.tipo_estacion,
            fuente_carga="formulario_comunidad",
        )
        db.add(estacion)
        db.flush()

        for sec in est.sectores:
            sector = models.Sector(
                estacion_id=estacion.id, numero_sector=sec.numero_sector
            )
            db.add(sector)
            db.flush()

            for ant in sec.antenas:
                antena = models.Antena(sector_id=sector.id, **ant.model_dump())
                db.add(antena)

    db.commit()
    db.refresh(solicitud)
    return solicitud


@router.get("/{solicitud_id}/reporte")
def obtener_reporte(solicitud_id: int, db: Session = Depends(get_db)):
    """RF01: reporte descargable de lo diligenciado por la comunidad."""
    solicitud = (
        db.query(models.Solicitud)
        .options(
            selectinload(models.Solicitud.estaciones)
            .selectinload(models.Estacion.sectores)
            .selectinload(models.Sector.antenas)
        )
        .filter(models.Solicitud.id == solicitud_id)
        .first()
    )
    if not solicitud:
        raise HTTPException(404, "Solicitud no encontrada")

    return {
        "id": solicitud.id,
        "razon_social": solicitud.razon_social,
        "nit": solicitud.nit,
        "representante_legal": solicitud.representante_legal,
        "telefono": solicitud.telefono,
        "direccion": solicitud.direccion,
        "correo_electronico": solicitud.correo_electronico,
        "radicado_mintic": solicitud.radicado_mintic,
        "estado": solicitud.estado,
        "created_at": solicitud.created_at,
        "estaciones": [
            {
                "id": e.id,
                "latitud": float(e.latitud),
                "longitud": float(e.longitud),
                "direccion_estacion": e.direccion_estacion,
                "departamento": e.departamento,
                "municipio": e.municipio,
                "sectores": [
                    {
                        "numero_sector": s.numero_sector,
                        "antenas": [
                            {
                                "acimut": float(a.acimut),
                                "tilt": float(a.tilt),
                                "ganancia": float(a.ganancia),
                                "angulo_apertura": float(a.angulo_apertura),
                                "altura_suelo": float(a.altura_suelo),
                            }
                            for a in s.antenas
                        ],
                    }
                    for s in e.sectores
                ],
            }
            for e in solicitud.estaciones
        ],
    }
