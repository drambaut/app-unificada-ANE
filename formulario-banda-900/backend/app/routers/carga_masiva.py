from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from .. import services
from ..auth import get_current_user
from ..database import get_db

router = APIRouter(
    prefix="/api/estaciones/carga-masiva",
    tags=["carga-masiva"],
    dependencies=[Depends(get_current_user)],
)


@router.post("", status_code=201)
async def cargar_archivo(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """RF02 (opcion b): carga masiva de datos tecnicos de estaciones/antenas."""
    contenido = await file.read()
    try:
        return services.procesar_carga_masiva(db, file.filename, contenido, user.get("sub"))
    except services.ArchivoInvalido as exc:
        raise HTTPException(400, str(exc))
