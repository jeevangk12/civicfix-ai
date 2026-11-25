from alembic import context

from app.core.config import Settings
from app.db import complaint_models, engagement_models, evidence_models, intelligence_models  # noqa: F401
from app.db.models import Base
from app.db.session import create_database_engine

settings = Settings()

if context.is_offline_mode():
    context.configure(
        url=str(settings.database_url),
        target_metadata=Base.metadata,
        literal_binds=True,
    )
    with context.begin_transaction():
        context.run_migrations()
else:
    engine = create_database_engine(settings)
    try:
        with engine.connect() as connection:
            context.configure(connection=connection, target_metadata=Base.metadata)
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()
