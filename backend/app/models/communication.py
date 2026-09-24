from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.database import Base
from app.models.asset import utc_now


class Communication(Base):
    """Comunicación dirigida entre dos activos.

    La IP y el nombre de cada extremo NO se guardan aquí: se leen del activo
    relacionado, así nunca se desincronizan cuando se edita un activo.
    """

    __tablename__ = "communications"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    source_asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id", ondelete="CASCADE"), nullable=False)
    destination_asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id", ondelete="CASCADE"), nullable=False)

    protocol: Mapped[str] = mapped_column(String(100), nullable=False)

    # Cadena vacía = sin puerto. No se usa NULL para que la restricción UNIQUE
    # funcione en SQLite (NULL nunca es igual a NULL).
    source_port: Mapped[str] = mapped_column(String(1000), nullable=False, default="")
    destination_port: Mapped[str] = mapped_column(String(1000), nullable=False, default="")

    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    source_asset = relationship("Asset", foreign_keys=[source_asset_id], back_populates="outgoing_communications")
    destination_asset = relationship(
        "Asset", foreign_keys=[destination_asset_id], back_populates="incoming_communications"
    )

    __table_args__ = (
        UniqueConstraint(
            "source_asset_id",
            "destination_asset_id",
            "protocol",
            "source_port",
            "destination_port",
            name="uq_communication",
        ),
        Index("ix_communications_source_asset_id", "source_asset_id"),
        Index("ix_communications_destination_asset_id", "destination_asset_id"),
        Index("ix_communications_protocol", "protocol"),
    )

    @property
    def source_ip(self) -> str | None:
        return self.source_asset.ip if self.source_asset else None

    @property
    def source_name(self) -> str | None:
        return self.source_asset.asset_name if self.source_asset else None

    @property
    def destination_ip(self) -> str | None:
        return self.destination_asset.ip if self.destination_asset else None

    @property
    def destination_name(self) -> str | None:
        return self.destination_asset.asset_name if self.destination_asset else None