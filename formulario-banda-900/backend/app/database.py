import re

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError, NoSuchModuleError
from sqlalchemy.orm import sessionmaker, declarative_base

from . import settings


def crear_engine(database_url: str):
    """Valida la connection string y crea el engine de SQLAlchemy."""
    if not database_url:
        raise RuntimeError(
            "Falta la variable de entorno DATABASE_URL (connection string de Supabase Postgres)."
        )

    if re.search(r"db\.[a-z0-9]+\.supabase\.co", database_url):
        raise RuntimeError(
            "DATABASE_URL apunta a la conexion DIRECTA de Supabase (db.<ref>.supabase.co:5432), "
            "que en muchas redes (incluyendo Codespaces/algunos ISP) solo resuelve por IPv6 y falla "
            "con 'Network is unreachable'. Ve a Supabase -> Project Settings -> Database -> "
            "Connection string -> elige el modo 'Transaction pooler' (puerto 6543, host tipo "
            "aws-0-<region>.pooler.supabase.com) y usa esa URL en su lugar."
        )

    # Los mensajes de error nunca incluyen la URL (lleva la contraseña).
    try:
        url = make_url(database_url)
    except ArgumentError:
        raise RuntimeError(
            "DATABASE_URL no tiene un formato valido; se espera "
            "postgresql://usuario:contrasena@host:puerto/base_de_datos."
        ) from None

    # SQLAlchemy 2.1 usa psycopg (v3) por defecto para "postgresql://"; el
    # proyecto usa psycopg2-binary, así que se fija ese driver explícitamente.
    # Se pasa el objeto URL (no un string) para no alterar ningún componente.
    if url.drivername == "postgresql":
        url = url.set(drivername="postgresql+psycopg2")

    try:
        return create_engine(url, pool_pre_ping=True)
    except NoSuchModuleError:
        raise RuntimeError(
            f"DATABASE_URL usa un tipo de base de datos no soportado ({url.drivername}); "
            "se espera postgresql://usuario:contrasena@host:puerto/base_de_datos."
        ) from None


# Engine del servicio FastAPI. Sin URL configurada queda en None para que
# models/services se puedan importar; main.py falla al arrancar en ese caso.
engine = crear_engine(settings.DATABASE_URL) if settings.DATABASE_URL else None
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
