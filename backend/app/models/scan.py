from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.database import Base
from app.models.asset import utc_now


class Scan(Base):
    """Trabajo de escaneo (job) en la cola.

    coalesce_key agrupa peticiones equivalentes (agent_id + target + scan_profile
    + params). No es UNIQUE: un mismo objetivo se puede volver a escanear más
    tarde; la coalescencia solo aplica a jobs pending/running (lógica de Fase 2).
    """

    __tablename__ = "scans"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"), nullable=False)

    scan_profile: Mapped[str] = mapped_column(String(50), nullable=False)   # plc | hmi | printers | mes | cnc | ...
    target: Mapped[str] = mapped_column(String(50), nullable=False)         # IP o CIDR
    params: Mapped[str | None] = mapped_column(Text, nullable=True)         # JSON de parámetros relevantes
    coalesce_key: Mapped[str] = mapped_column(String(255), nullable=False)

    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")  # pending|running|completed|failed|canceled

    raw_xml_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)   # JSON: hosts encontrados/nuevos/actualizados
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    queued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    agent = relationship("Agent", back_populates="scans")
    requests = relationship("ScanRequest", back_populates="scan", cascade="all, delete-orphan")
    findings = relationship("ScanFinding", back_populates="scan", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_scans_status", "status"),
        Index("ix_scans_agent_id", "agent_id"),
        Index("ix_scans_coalesce_key", "coalesce_key"),
    )


class ScanRequest(Base):
    """Quién pidió un escaneo. Varias peticiones equivalentes se enganchan al
    mismo Scan (coalescencia) y aquí queda el registro para auditoría.
    """

    __tablename__ = "scan_requests"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    scan_id: Mapped[int] = mapped_column(ForeignKey("scans.id", ondelete="CASCADE"), nullable=False)

    requested_by: Mapped[str | None] = mapped_column(String(150), nullable=True)  # usuario; sin auth aún
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    scan = relationship("Scan", back_populates="requests")

    __table_args__ = (Index("ix_scan_requests_scan_id", "scan_id"),)


class ScanFinding(Base):
    """Host detectado por un escaneo, con su confianza y estado de revisión.

    No se aplica a ciegas: según la confianza queda 'confirmed' (automático) o
    'review' (candidato por aprobar). matched_asset_id apunta al activo existente
    si hubo coincidencia; si no, es un activo nuevo.
    """

    __tablename__ = "scan_findings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    scan_id: Mapped[int] = mapped_column(ForeignKey("scans.id", ondelete="CASCADE"), nullable=False)
    matched_asset_id: Mapped[int | None] = mapped_column(ForeignKey("assets.id", ondelete="SET NULL"), nullable=True)

    ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    mac: Mapped[str | None] = mapped_column(String(17), nullable=True)
    vendor: Mapped[str | None] = mapped_column(String(255), nullable=True)
    detected_os: Mapped[str | None] = mapped_column(String(255), nullable=True)

    confidence: Mapped[int] = mapped_column(Integer, nullable=False, default=0)        # 0-100
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="review")  # confirmed|review|discarded
    applied: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    raw: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON del host parseado (puertos, scripts)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    scan = relationship("Scan", back_populates="findings")

    __table_args__ = (
        Index("ix_scan_findings_scan_id", "scan_id"),
        Index("ix_scan_findings_status", "status"),
    )