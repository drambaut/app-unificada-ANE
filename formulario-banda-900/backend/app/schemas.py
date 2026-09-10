from typing import List, Optional, Literal

from pydantic import BaseModel, EmailStr, Field, field_validator

from .campos_antena import validar_campo


class AntenaIn(BaseModel):
    acimut: float
    tilt: float
    ganancia: float
    ganancia_unidad: Optional[Literal["dBi", "dBd"]] = None
    angulo_apertura: float
    altura_suelo: float
    potencia_transmision: Optional[float] = None

    @field_validator("acimut")
    @classmethod
    def _v_acimut(cls, v):
        err = validar_campo("acimut", v)
        if err:
            raise ValueError(err)
        return v

    @field_validator("tilt")
    @classmethod
    def _v_tilt(cls, v):
        err = validar_campo("tilt", v)
        if err:
            raise ValueError(err)
        return v

    @field_validator("ganancia")
    @classmethod
    def _v_ganancia(cls, v):
        err = validar_campo("ganancia", v)
        if err:
            raise ValueError(err)
        return v

    @field_validator("angulo_apertura")
    @classmethod
    def _v_angulo(cls, v):
        err = validar_campo("angulo_apertura", v)
        if err:
            raise ValueError(err)
        return v

    @field_validator("altura_suelo")
    @classmethod
    def _v_altura(cls, v):
        err = validar_campo("altura_suelo", v)
        if err:
            raise ValueError(err)
        return v


class SectorIn(BaseModel):
    numero_sector: int
    antenas: List[AntenaIn]


class EstacionIn(BaseModel):
    latitud: float = Field(ge=-90, le=90)
    longitud: float = Field(ge=-180, le=180)
    formato_coordenadas: Literal["decimal", "gms"] = "decimal"
    direccion_estacion: Optional[str] = None
    departamento: Optional[str] = None
    municipio: Optional[str] = None
    cantidad_sectores: int = Field(ge=1)
    tipo_estacion: Optional[Literal["nueva", "repetidora"]] = None
    sectores: List[SectorIn]


class SolicitudIn(BaseModel):
    razon_social: str
    # Solo digitos, sin signo. Se valida como texto para no perder ceros a la
    # izquierda ni tratarlo como una cantidad aritmetica.
    nit: str = Field(pattern=r"^\d{5,15}$")
    representante_legal: str
    # El frontend envia "+57" + hasta 10 digitos (el prefijo no es editable
    # por el usuario, ver componente CampoTelefono).
    telefono: str = Field(pattern=r"^\+57\d{7,10}$")
    direccion: str = Field(max_length=43)
    correo_electronico: EmailStr
    radicado_mintic: Optional[str] = None
    estaciones: List[EstacionIn]


class SolicitudOut(BaseModel):
    id: int
    estado: str

    class Config:
        from_attributes = True


class EstacionOut(BaseModel):
    id: int
    origen: str
    latitud: float
    longitud: float
    departamento: Optional[str] = None
    municipio: Optional[str] = None
    cantidad_sectores: int
    fuente_carga: str

    class Config:
        from_attributes = True
