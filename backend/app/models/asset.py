from datetime import datetime, timezone

from sqlalchemy import DateTime, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Asset(Base):
    __tablename__ = "assets"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    asset_code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    asset_name: Mapped[str] = mapped_column(String(255), nullable=False)
    asset_type: Mapped[str] = mapped_column(String(100), nullable=False)

    # Identificación de red
    ip: Mapped[str | None] = mapped_column(String(45), nullable=True, unique=True)
    mac: Mapped[str | None] = mapped_column(String(17), nullable=True)
    hostname: Mapped[str | None] = mapped_column(String(255), nullable=True)
    vlan: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Equipo
    vendor: Mapped[str | None] = mapped_column(String(255), nullable=True)
    product: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Ubicación en la planta
    plant: Mapped[str | None] = mapped_column(String(150), nullable=True)
    building: Mapped[str | None] = mapped_column(String(150), nullable=True)
    production_line: Mapped[str | None] = mapped_column(String(150), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    outgoing_communications = relationship(
        "Communication",
        foreign_keys="Communication.source_asset_id",
        back_populates="source_asset",
        cascade="all, delete-orphan",
    )

    incoming_communications = relationship(
        "Communication",
        foreign_keys="Communication.destination_asset_id",
        back_populates="destination_asset",
        cascade="all, delete-orphan",
    )


Index("ix_assets_mac", Asset.mac)
Index("ix_assets_location", Asset.plant, Asset.building, Asset.production_line)
Index("ix_assets_vlan", Asset.vlan)