from app.database.database import Base, engine
from app.models import Asset, Communication


def create_tables() -> None:
    Base.metadata.create_all(bind=engine)