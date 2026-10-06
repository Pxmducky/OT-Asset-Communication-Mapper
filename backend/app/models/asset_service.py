from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.database import Base
from app.models.asset import utc_now


class AssetService(Base):
    """Puerto/servicio propio de un activo (resultado de un escaneo).

    Un puerto abierto es un servicio del host, NO una comunicación entre activos.
    Por eso vive aquí y nunca crea registros en 'communications'.
    """

    __tablename__ = "asset_services"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id", ondelete="CASCADE"), nullable=False)

    port: Mapped[int] = mapped_column(Integer, nullable=False)
    transport: Mapped[str] = mapped_column(String(10), nullable=False, default="tcp")   # tcp | udp
    state: Mapped[str] = mapped_column(String(20), nullable=False, default="open")       # open | filtered | ...

    service: Mapped[str | None] = mapped_column(String(100), nullable=True)   # p. ej. s7comm, http, modbus
    product: Mapped[str | None] = mapped_column(String(255), nullable=True)
    version: Mapped[str | None] = mapped_column(String(255), nullable=True)
    extra: Mapped[str | None] = mapped_column(Text, nullable=True)            # salida de scripts NSE (JSON/texto)

    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    last_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    asset = relationship("Asset", back_populates="services")

    __table_args__ = (
        UniqueConstraint("asset_id", "port", "transport", name="uq_asset_service"),
        Index("ix_asset_services_asset_id", "asset_id"),
    )