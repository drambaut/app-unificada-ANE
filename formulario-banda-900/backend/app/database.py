import re

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from . import settings

if not settings.DATABASE_URL:
    raise RuntimeError(
        "Falta la variable de entorno DATABASE_URL (connection string de Supabase Postgres)."
    )

if re.search(r"db\.[a-z0-9]+\.supabase\.co", settings.DATABASE_URL):
    raise RuntimeError(
        "DATABASE_URL apunta a la conexion DIRECTA de Supabase (db.<ref>.supabase.co:5432), "
        "que en muchas redes (incluyendo Codespaces/algunos ISP) solo resuelve por IPv6 y falla "
        "con 'Network is unreachable'. Ve a Supabase -> Project Settings -> Database -> "
        "Connection string -> elige el modo 'Transaction pooler' (puerto 6543, host tipo "
        "aws-0-<region>.pooler.supabase.com) y usa esa URL en su lugar."
    )

engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()