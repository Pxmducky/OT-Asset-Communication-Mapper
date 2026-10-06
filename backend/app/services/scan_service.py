import hashlib
import json
from datetime import datetime, timedelta, timezone

from app.config import get_scanner_settings
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.config import get_scanner_settings
from app.database.database import DATA_DIR
from app.models import Agent, Scan, ScanRequest
from app.scanning.local_scanner import get_or_create_local_scanner
from app.scanning.profiles import get_profile_args, profile_exists
from app.scanning.targets import (
    TargetNotAuthorizedError,
    network_contains_target,
    parse_target,
)
from app.schemas.scan import ScanRequestCreate

SCANS_DIR = DATA_DIR / "scans"

STALE_RUNNING_MINUTES = 90
ACTIVE_STATUSES = ("pending", "running")
MAX_PARALLEL_SCANS = 2   # tu punto 9: no más de 2 redes escaneando a la vez

class ScanService:

    # ---------- lectura ----------

    @staticmethod
    def _base_query():
        return select(Scan).options(selectinload(Scan.requests))

    @staticmethod
    def get_all(db: Session, status: str | None = None) -> list[Scan]:
        statement = ScanService._base_query().order_by(Scan.id.desc())
        if status:
            statement = statement.where(Scan.status == status)
        return list(db.scalars(statement).all())

    @staticmethod
    def get_by_id(db: Session, scan_id: int) -> Scan | None:
        return db.scalar(ScanService._base_query().where(Scan.id == scan_id))

    # ---------- coalescencia ----------

    @staticmethod
    def _coalesce_key(agent_id: int, profile: str, target: str, params: dict | None) -> str:
        norm = json.dumps(params or {}, sort_keys=True, separators=(",", ":"))
        base = f"{agent_id}|{profile}|{target}|{norm}"
        return hashlib.sha256(base.encode("utf-8")).hexdigest()

    # ---------- alta de escaneo (usuario) ----------

    @staticmethod
    def request_scan(db: Session, data: ScanRequestCreate) -> tuple[Scan, bool]:
        """Valida contra las redes del config y encola para el escáner local.

        Puede lanzar:
          - ValueError               perfil desconocido
          - TargetMalformedError     objetivo mal formado (192.168.440.0/24)
          - TargetNotAuthorizedError objetivo fuera de toda red autorizada (8.8.8.8)
        """
        if not profile_exists(data.scan_profile):
            raise ValueError(f"Perfil de escaneo desconocido: {data.scan_profile}")

        target_net = parse_target(data.target)  # puede lanzar TargetMalformedError
        target = str(target_net)

        agent = get_or_create_local_scanner(db)
        allowed = any(
            network_contains_target(net.cidr, target_net) for net in agent.allowed_networks
        )
        if not allowed:
            raise TargetNotAuthorizedError("El objetivo no pertenece a una red autorizada.")
            
        key = ScanService._coalesce_key(agent.id, data.scan_profile, target, data.params)

        existing = db.scalar(
            ScanService._base_query()
            .where(
                Scan.agent_id == agent.id,
                Scan.coalesce_key == key,
                Scan.status.in_(ACTIVE_STATUSES),
            )
            .order_by(Scan.id)
        )
        if existing is not None:
            existing.requests.append(ScanRequest(requested_by=data.requested_by))
            db.commit()
            db.refresh(existing)
            return existing, True

        scan = Scan(
            agent_id=agent.id,
            scan_profile=data.scan_profile,
            target=target,
            params=json.dumps(data.params) if data.params else None,
            coalesce_key=key,
            status="pending",
        )
        scan.requests.append(ScanRequest(requested_by=data.requested_by))
        db.add(scan)
        db.commit()
        db.refresh(scan)
        return scan, False

    # ---------- entrega de trabajo (lo llama el worker interno) ----------

    @staticmethod
    def _reclaim_stale(db: Session, agent_id: int) -> None:
        threshold = datetime.now(timezone.utc) - timedelta(minutes=STALE_RUNNING_MINUTES)
        stale = db.scalars(
            select(Scan).where(
                Scan.agent_id == agent_id,
                Scan.status == "running",
                Scan.started_at.is_not(None),
                Scan.started_at < threshold,
            )
        ).all()
        for scan in stale:
            scan.status = "failed"
            scan.error = "Reclamado por timeout: el escaneo no devolvió resultado."
            scan.finished_at = datetime.now(timezone.utc)
        if stale:
            db.commit()

    @staticmethod
    def claim_next_job(db: Session, agent: Agent) -> Scan | None:
        """Entrega un escaneo pendiente mientras haya menos de MAX_PARALLEL_SCANS
        corriendo. Así nunca se escanean más de 2 redes al mismo tiempo (punto 9)."""
        ScanService._reclaim_stale(db, agent.id)

        running = db.scalar(
            select(func.count()).select_from(Scan).where(
                Scan.agent_id == agent.id, Scan.status == "running"
            )
        )
        if running >= MAX_PARALLEL_SCANS:
            return None

        scan = db.scalar(
            select(Scan)
            .where(Scan.agent_id == agent.id, Scan.status == "pending")
            .order_by(Scan.id)
            .limit(1)
        )
        if scan is None:
            return None

        scan.status = "running"
        scan.started_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(scan)
        return scan

    @staticmethod
    def job_args(scan: Scan) -> list[str]:
        return get_profile_args(scan.scan_profile)

    # ---------- resultado (lo llama el worker interno) ----------

    @staticmethod
    def submit_result(
        db: Session,
        agent: Agent,
        scan_id: int,
        status: str,
        raw_xml: str | None,
        error: str | None,
    ) -> Scan | None:
        scan = ScanService.get_by_id(db, scan_id)
        if scan is None or scan.agent_id != agent.id:
            return None
        if scan.status != "running":
            return scan

        if status == "completed":
            if raw_xml:
                SCANS_DIR.mkdir(parents=True, exist_ok=True)
                path = SCANS_DIR / f"scan_{scan.id}.xml"
                path.write_text(raw_xml, encoding="utf-8")
                scan.raw_xml_path = str(path)
            scan.status = "completed"
            # El parseo del XML y los findings son de la Fase 4.
        else:
            scan.status = "failed"
            scan.error = error or "Error desconocido en el escaneo."

        scan.finished_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(scan)
        return scan