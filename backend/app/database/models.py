import app.models  # noqa: F401  — registra todos los modelos en Base.metadata
from app.database.database import engine
from app.database.migrations import run_lightweight_migrations
from app.models import Asset, Communication  # noqa: F401  — compatibilidad con imports previos


def create_tables() -> None:
    Base_metadata_create_all()
    run_lightweight_migrations(engine)


def Base_metadata_create_all() -> None:
    from app.database.database import Base

    Base.metadata.create_all(bind=engine)