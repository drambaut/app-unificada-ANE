from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Numeric,
    ForeignKey,
    TIMESTAMP,
    func,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from .database import Base


class Solicitud(Base):
    __tablename__ = "solicitudes"

    id = Column(Integer, primary_key=True)
    razon_social = Column(Text, nullable=False)
    nit = Column(Text, nullable=False)
    representante_legal = Column(Text, nullable=False)
    telefono = Column(Text, nullable=False)
    direccion = Column(String(43), nullable=False)
    correo_electronico = Column(Text, nullable=False)
    radicado_mintic = Column(Text)
    estado = Column(Text, nullable=False, server_default="pendiente")
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now())

    estaciones = relationship(
        "Estacion", back_populates="solicitud", cascade="all, delete-orphan"
    )


class Estacion(Base):
    __tablename__ = "estaciones"

    id = Column(Integer, primary_key=True)
    origen = Column(Text, nullable=False)  # 'comunidad' | 'red'
    solicitud_id = Column(
        Integer, ForeignKey("solicitudes.id", ondelete="CASCADE"), nullable=True
    )
    tipo_estacion = Column(Text)  # 'nueva' | 'repetidora'
    latitud = Column(Numeric, nullable=False)
    longitud = Column(Numeric, nullable=False)
    formato_coordenadas = Column(Text, nullable=False, server_default="decimal")
    direccion_estacion = Column(Text)
    departamento = Column(Text)
    municipio = Column(Text)
    cantidad_sectores = Column(Integer, nullable=False, server_default="1")
    haat_m = Column(Numeric)
    fuente_carga = Column(Text, nullable=False, server_default="manual")
    creado_por = Column(UUID(as_uuid=True))
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now())

    solicitud = relationship("Solicitud", back_populates="estaciones")
    sectores = relationship(
        "Sector", back_populates="estacion", cascade="all, delete-orphan"
    )


class Sector(Base):
    __tablename__ = "sectores"

    id = Column(Integer, primary_key=True)
    estacion_id = Column(
        Integer, ForeignKey("estaciones.id", ondelete="CASCADE"), nullable=False
    )
    numero_sector = Column(Integer, nullable=False)

    estacion = relationship("Estacion", back_populates="sectores")
    antenas = relationship(
        "Antena", back_populates="sector", cascade="all, delete-orphan"
    )


class Antena(Base):
    __tablename__ = "antenas"

    id = Column(Integer, primary_key=True)
    sector_id = Column(
        Integer, ForeignKey("sectores.id", ondelete="CASCADE"), nullable=False
    )
    acimut = Column(Numeric, nullable=False)
    tilt = Column(Numeric, nullable=False)
    ganancia = Column(Numeric, nullable=False)
    ganancia_unidad = Column(Text)
    angulo_apertura = Column(Numeric, nullable=False)
    altura_suelo = Column(Numeric, nullable=False)
    potencia_transmision = Column(Numeric)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())

    sector = relationship("Sector", back_populates="antenas")


class ArchivoCarga(Base):
    __tablename__ = "archivos_carga"

    id = Column(Integer, primary_key=True)
    usuario_id = Column(UUID(as_uuid=True))
    nombre_original = Column(Text, nullable=False)
    ruta_storage = Column(Text, nullable=False)
    tipo_archivo = Column(Text, nullable=False)
    estado_procesamiento = Column(Text, nullable=False, server_default="pendiente")
    filas_ok = Column(Integer, server_default="0")
    filas_error = Column(Integer, server_default="0")
    log_errores = Column(JSONB)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())