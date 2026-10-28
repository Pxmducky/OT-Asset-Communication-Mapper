from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.database import Base
from app.models.asset import utc_now


class AssetFingerprint(Base):
    """Identificaciones/servicios detectados en un activo (decisión 2).

    Separado del asset_type: un PLC puede exponer además mGuard/RDP; eso vive aquí
    como evidencia, sin cambiar el tipo principal del activo.
    """

    __tablename__ = "asset_fingerprints"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id", ondelete="CASCADE"), nullable=False)

    kind: Mapped[str] = mapped_column(String(20), nullable=False, default="service")  # identity | service | product
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    port: Mapped[int | None] = mapped_column(Integer, nullable=True)
    transport: Mapped[str | None] = mapped_column(String(10), nullable=True)
    source: Mapped[str | None] = mapped_column(String(60), nullable=True)  # script/banner/cert

    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    asset = relationship("Asset", back_populates="fingerprints")

    __table_args__ = (
        UniqueConstraint("asset_id", "label", name="uq_asset_fingerprint"),
        Index("ix_asset_fingerprints_asset_id", "asset_id"),
    )