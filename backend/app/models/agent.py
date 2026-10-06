from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.database import Base
from app.models.asset import utc_now


class Agent(Base):
    """Agente de escaneo desplegado dentro de la zona OT.

    Solo hace polling, ejecuta nmap y devuelve XML. El token nunca se guarda en
    claro: se almacena su hash (token_hash) y se muestra una sola vez al crear.
    """

    __tablename__ = "agents"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    agent_uid: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)  # ID público estable
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    token_hash: Mapped[str] = mapped_column(String(128), nullable=False)  # hash del token, nunca el token en claro
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")  # active | revoked

    last_seen: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    allowed_networks = relationship("AllowedNetwork", back_populates="agent", cascade="all, delete-orphan")
    scans = relationship("Scan", back_populates="agent")


class AllowedNetwork(Base):
    """Red autorizada que un agente puede escanear.

    El servidor valida que el objetivo quede contenido en alguna de estas redes
    antes de encolar; el agente vuelve a validar como segunda barrera.
    """

    __tablename__ = "allowed_networks"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"), nullable=False)

    cidr: Mapped[str] = mapped_column(String(50), nullable=False)  # p. ej. 192.168.10.0/24
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    agent = relationship("Agent", back_populates="allowed_networks")

    __table_args__ = (
        UniqueConstraint("agent_id", "cidr", name="uq_allowed_network"),
        Index("ix_allowed_networks_agent_id", "agent_id"),
    )