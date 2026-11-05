from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.database import Base
from app.models.asset import utc_now


class ExcelImport(Base):
    """Registro de cada importación de Excel. Los activos y comunicaciones que
    crea guardan su import_id, para poder borrar esa importación completa."""

    __tablename__ = "excel_imports"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    assets_created: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    assets_updated: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    communications_created: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    backup_id: Mapped[int | None] = mapped_column(Integer, nullable=True)