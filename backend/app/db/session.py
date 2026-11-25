from sqlalchemy import Engine, create_engine

from app.core.config import Settings


def create_database_engine(settings: Settings) -> Engine:
    return create_engine(str(settings.database_url), pool_pre_ping=True, connect_args={"connect_timeout": 5})
