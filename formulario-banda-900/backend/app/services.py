"""
Lógica de negocio de Banda 900, independiente de FastAPI.

La usan los routers (servicio FastAPI) y puede usarla cualquier otra interfaz
(p. ej. Streamlit dentro de app-unificada). Los errores se reportan con
excepciones de dominio; cada interfaz decide cómo mostrarlos.
"""
from __future__ import annotations

import io
from typing import TYPE_CHECKING

import pandas as pd
from sqlalchemy.orm import Session, selectinload

from . import models
from .campos_antena import validar_campo
from .supabase_client import BUCKET_CARGAS, get_supabase

if TYPE_CHECKING:
    from . import schemas


class SolicitudNoEncontrada(LookupError):
    """No existe una solicitud con el id pedido."""


class ArchivoInvalido(ValueError):
    """El archivo de carga masiva no se puede procesar (formato o columnas)."""


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


# ── Solicitudes (RF01) ───────────────────────────────────────────────────────
def crear_solicitud(db: Session, payload: schemas.SolicitudIn) -> models.Solicitud:
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


def obtener_reporte(db: Session, solicitud_id: int) -> dict:
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
        raise SolicitudNoEncontrada("Solicitud no encontrada")

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


# ── Estaciones de red (RF02) ─────────────────────────────────────────────────
def listar_estaciones_red(db: Session) -> list[models.Estacion]:
    """RF02: estaciones de la red cargadas por el Ingeniero GIE."""
    return db.query(models.Estacion).filter(models.Estacion.origen == "red").all()


def crear_estacion(db: Session, payload: schemas.EstacionIn, user_id) -> models.Estacion:
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
        creado_por=user_id,
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


# ── Carga masiva (RF02, opción b) ────────────────────────────────────────────
def _leer_dataframe(nombre_archivo: str, contenido: bytes) -> pd.DataFrame:
    ext = nombre_archivo.rsplit(".", 1)[-1].lower()
    if ext == "csv":
        return pd.read_csv(io.BytesIO(contenido))
    if ext in ("xlsx", "xls"):
        return pd.read_excel(io.BytesIO(contenido))
    raise ArchivoInvalido("Formato no soportado, sube un archivo .csv o .xlsx")


def procesar_carga_masiva(db: Session, nombre_archivo: str, contenido: bytes, user_id) -> dict:
    """RF02 (opcion b): carga masiva de datos tecnicos de estaciones/antenas."""
    df = _leer_dataframe(nombre_archivo, contenido)

    faltantes = [c for c in COLUMNAS_REQUERIDAS if c not in df.columns]
    if faltantes:
        raise ArchivoInvalido(
            f"Al archivo le faltan las columnas: {', '.join(faltantes)}. "
            f"Columnas requeridas: {', '.join(COLUMNAS_REQUERIDAS)}"
        )

    # Sube una copia del archivo original a Supabase Storage (no bloqueante si falla).
    ruta_storage = f"cargas/{nombre_archivo}"
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
                creado_por=user_id,
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
        usuario_id=user_id,
        nombre_original=nombre_archivo,
        ruta_storage=ruta_storage,
        tipo_archivo="csv" if nombre_archivo.lower().endswith(".csv") else "xlsx",
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
