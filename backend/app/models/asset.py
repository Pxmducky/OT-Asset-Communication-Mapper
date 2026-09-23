from datetime import datetime

from sqlalchemy import DateTime, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.database import Base


class Asset(Base):
    __tablename__ = "assets"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )

    asset_code: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        unique=True,
        index=True,
    )

    asset_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    asset_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    ip: Mapped[str | None] = mapped_column(
        String(45),
        nullable=True,
    )

    mac: Mapped[str | None] = mapped_column(
        String(17),
        nullable=True,
    )

    hostname: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    vendor: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    product: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
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


Index("ix_assets_ip", Asset.ip)
Index("ix_assets_mac", Asset.mac)