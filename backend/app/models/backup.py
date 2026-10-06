from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.database import Base
from app.models.asset import utc_now


class Backup(Base):
    """Respaldo de la base (copia del archivo SQLite) tomado antes de un escaneo
    o de aplicar cambios, o manualmente. Consultable desde la app.
    """

    __tablename__ = "backups"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    reason: Mapped[str] = mapped_column(String(30), nullable=False)  # pre-scan | pre-apply | manual
    path: Mapped[str] = mapped_column(String(500), nullable=False)
    size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)

    scan_id: Mapped[int | None] = mapped_column(ForeignKey("scans.id", ondelete="SET NULL"), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    __table_args__ = (Index("ix_backups_created_at", "created_at"),)