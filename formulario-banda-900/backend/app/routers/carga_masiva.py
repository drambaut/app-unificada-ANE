import io

import pandas as pd
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from .. import models
from ..auth import get_current_user
from ..campos_antena import validar_campo
from ..database import get_db
from ..supabase_client import BUCKET_CARGAS, get_supabase

router = APIRouter(
    prefix="/api/estaciones/carga-masiva",
    tags=["carga-masiva"],
    dependencies=[Depends(get_current_user)],
)

COLUMNAS_REQUERIDAS = [
    "latitud",
    "longitud",
    "numero_sector",
    "acimut",
    "tilt",
    "ganancia",
    "angulo_apertura",
    "altura_suelo",
]

COLUMNAS_OPCIONALES = [
    "direccion_estacion",
    "departamento",
    "municipio",
    "ganancia_unidad",
    "potencia_transmision",
    "tipo_estacion",
]


def _leer_dataframe(nombre_archivo: str, contenido: bytes) -> pd.DataFrame:
    ext = nombre_archivo.rsplit(".", 1)[-1].lower()
    if ext == "csv":
        return pd.read_csv(io.BytesIO(contenido))
    if ext in ("xlsx", "xls"):
        return pd.read_excel(io.BytesIO(contenido))
    raise HTTPException(400, "Formato no soportado, sube un archivo .csv o .xlsx")


@router.post("", status_code=201)
async def cargar_archivo(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """RF02 (opcion b): carga masiva de datos tecnicos de estaciones/antenas."""
    contenido = await file.read()
    df = _leer_dataframe(file.filename, contenido)

    faltantes = [c for c in COLUMNAS_REQUERIDAS if c not in df.columns]
    if faltantes:
        raise HTTPException(
            400,
            f"Al archivo le faltan las columnas: {', '.join(faltantes)}. "
            f"Columnas requeridas: {', '.join(COLUMNAS_REQUERIDAS)}",
        )

    # Sube una copia del archivo original a Supabase Storage (no bloqueante si falla).
    ruta_storage = f"cargas/{file.filename}"
    try:
        supabase = get_supabase()
        supabase.storage.from_(BUCKET_CARGAS).upload(
            ruta_storage, contenido, {"upsert": "true"}
        )
    except Exception as exc:  # noqa: BLE001
        ruta_storage = f"(no se pudo subir a storage: {exc})"

    errores = []
    filas_ok = 0
    estaciones_cache: dict[tuple, models.Estacion] = {}
    sectores_cache: dict[tuple, models.Sector] = {}

    for idx, row in df.iterrows():
        fila_num = int(idx) + 2  # +2: encabezado + indice base 1
        fila_errores = []

        try:
            lat = float(row["latitud"])
            lon = float(row["longitud"])
            if not (-90 <= lat <= 90):
                fila_errores.append("latitud fuera de rango (-90 a 90)")
            if not (-180 <= lon <= 180):
                fila_errores.append("longitud fuera de rango (-180 a 180)")
        except (TypeError, ValueError):
            fila_errores.append("latitud/longitud no numericas")
            lat = lon = None

        try:
            numero_sector = int(row["numero_sector"])
        except (TypeError, ValueError):
            fila_errores.append("numero_sector no numerico")
            numero_sector = None

        valores_antena = {}
        for campo in ["acimut", "tilt", "ganancia", "angulo_apertura", "altura_suelo"]:
            try:
                valor = float(row[campo])
            except (TypeError, ValueError):
                fila_errores.append(f"{campo} no numerico")
                continue
            err = validar_campo(campo, valor)
            if err:
                fila_errores.append(err)
            else:
                valores_antena[campo] = valor

        if fila_errores:
            errores.append({"fila": fila_num, "errores": fila_errores})
            continue

        key_estacion = (round(lat, 6), round(lon, 6))
        if key_estacion not in estaciones_cache:
            estacion = models.Estacion(
                origen="red",
                tipo_estacion=str(row.get("tipo_estacion") or "") or None,
                latitud=lat,
                longitud=lon,
                formato_coordenadas="decimal",
                direccion_estacion=str(row.get("direccion_estacion") or "") or None,
                departamento=str(row.get("departamento") or "") or None,
                municipio=str(row.get("municipio") or "") or None,
                cantidad_sectores=1,
                fuente_carga="archivo",
                creado_por=user.get("sub"),
            )
            db.add(estacion)
            db.flush()
            estaciones_cache[key_estacion] = estacion
        else:
            estacion = estaciones_cache[key_estacion]

        key_sector = (key_estacion, numero_sector)
        if key_sector not in sectores_cache:
            sector = models.Sector(estacion_id=estacion.id, numero_sector=numero_sector)
            db.add(sector)
            db.flush()
            sectores_cache[key_sector] = sector
            estacion.cantidad_sectores = len(
                [k for k in sectores_cache if k[0] == key_estacion]
            )
        else:
            sector = sectores_cache[key_sector]

        ganancia_unidad = str(row.get("ganancia_unidad") or "").strip() or None
        if ganancia_unidad not in ("dBi", "dBd"):
            ganancia_unidad = None
        potencia = row.get("potencia_transmision")
        try:
            potencia = float(potencia) if potencia not in (None, "") else None
        except (TypeError, ValueError):
            potencia = None

        antena = models.Antena(
            sector_id=sector.id,
            acimut=valores_antena["acimut"],
            tilt=valores_antena["tilt"],
            ganancia=valores_antena["ganancia"],
            ganancia_unidad=ganancia_unidad,
            angulo_apertura=valores_antena["angulo_apertura"],
            altura_suelo=valores_antena["altura_suelo"],
            potencia_transmision=potencia,
        )
        db.add(antena)
        filas_ok += 1

    estado = "procesado" if not errores else ("error" if filas_ok == 0 else "error_parcial")

    registro = models.ArchivoCarga(
        usuario_id=user.get("sub"),
        nombre_original=file.filename,
        ruta_storage=ruta_storage,
        tipo_archivo="csv" if file.filename.lower().endswith(".csv") else "xlsx",
        estado_procesamiento=estado,
        filas_ok=filas_ok,
        filas_error=len(errores),
        log_errores=errores,
    )
    db.add(registro)
    db.commit()

    return {
        "id": registro.id,
        "estado": estado,
        "filas_ok": filas_ok,
        "filas_error": len(errores),
        "errores": errores,
    }