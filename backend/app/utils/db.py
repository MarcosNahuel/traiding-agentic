from sqlmodel import SQLModel, create_engine
from sqlalchemy.engine import Engine
from ..config import AppSettings

_engine: Engine | None = None

def init_db(settings: AppSettings) -> None:
    global _engine
    # pool_pre_ping=True ayuda a reciclar conexiones muertas (útil con Supabase)
    _engine = create_engine(settings.database_url, echo=False, pool_pre_ping=True)
    # Para MVP usamos create_all. En producción usar migraciones (Alembic).
    SQLModel.metadata.create_all(_engine)


def get_engine():
    return _engine
