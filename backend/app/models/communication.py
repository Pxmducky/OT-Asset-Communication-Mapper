from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.database import Base


class Communication(Base):
    __tablename__ = "communications"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )

    source_asset_id: Mapped[int] = mapped_column(
        ForeignKey("assets.id", ondelete="CASCADE"),
        nullable=False,
    )

    destination_asset_id: Mapped[int] = mapped_column(
        ForeignKey("assets.id", ondelete="CASCADE"),
        nullable=False,
    )

    source: Mapped[str] = mapped_column(
        String(45),
        nullable=False,
    )

    destination: Mapped[str] = mapped_column(
        String(45),
        nullable=False,
    )

    protocol: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    source_port: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    destination_port: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    source_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    destination_name: Mapped[str | None] = mapped_column(
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

    source_asset = relationship(
        "Asset",
        foreign_keys=[source_asset_id],
        back_populates="outgoing_communications",
    )

    destination_asset = relationship(
        "Asset",
        foreign_keys=[destination_asset_id],
        back_populates="incoming_communications",
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
        Index(
            "ix_communications_source_asset_id",
            "source_asset_id",
        ),
        Index(
            "ix_communications_destination_asset_id",
            "destination_asset_id",
        ),
        Index(
            "ix_communications_protocol",
            "protocol",
        ),
    )