"""Bandeja de revisión + reclasificación de activos existentes."""
import json
from app.scanning.confidence import classify_host
from app.scanning.parser import ParsedHost
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.models import ScanFinding
from app.schemas.finding import FindingResponse
from app.services.asset_service import AssetService
from app.services.backup_service import BackupService
from app.services.scan_processor import ScanProcessor

router = APIRouter(prefix="/api", tags=["Findings"])

RECLASSIFY_MIN_CONFIDENCE = 70  # opción (a): solo reclasifica con confianza alta


def _get_finding_or_404(finding_id: int, db: Session) -> ScanFinding:
    finding = db.scalar(select(ScanFinding).where(ScanFinding.id == finding_id))
    if finding is None:
        raise HTTPException(status_code=404, detail="Hallazgo no encontrado.")
    return finding


@router.get("/findings", response_model=list[FindingResponse])
def list_findings(status: str | None = Query(None), db: Session = Depends(get_db)):
    stmt = select(ScanFinding).order_by(ScanFinding.id.desc())
    if status:
        stmt = stmt.where(ScanFinding.status == status)
    return [FindingResponse.from_finding(f) for f in db.scalars(stmt).all()]


@router.get("/scans/{scan_id}/findings", response_model=list[FindingResponse])
def findings_for_scan(scan_id: int, db: Session = Depends(get_db)):
    stmt = select(ScanFinding).where(ScanFinding.scan_id == scan_id).order_by(ScanFinding.id)
    return [FindingResponse.from_finding(f) for f in db.scalars(stmt).all()]


@router.post("/findings/{finding_id}/apply", response_model=dict)
def apply_finding(finding_id: int, db: Session = Depends(get_db)):
    finding = _get_finding_or_404(finding_id, db)
    if finding.applied:
        return {"finding_id": finding.id, "status": finding.status, "asset_id": finding.matched_asset_id}
    BackupService.make_backup(db, "pre-apply")
    asset = ScanProcessor.apply_finding(db, finding)
    return {"finding_id": finding.id, "status": finding.status, "asset_id": asset.id}


@router.post("/findings/{finding_id}/discard", response_model=dict)
def discard_finding(finding_id: int, db: Session = Depends(get_db)):
    finding = _get_finding_or_404(finding_id, db)
    finding.status = "discarded"
    db.commit()
    return {"finding_id": finding.id, "status": finding.status}


@router.post("/findings/{finding_id}/reclassify", response_model=dict)
def reclassify_asset(finding_id: int, db: Session = Depends(get_db)):
    """Actualiza el tipo del activo asociado al tipo detectado por el escaneo.
    Solo si la confianza es alta (>=70) y el tipo difiere. Respalda antes."""
    finding = _get_finding_or_404(finding_id, db)
    if not finding.matched_asset_id:
        raise HTTPException(status_code=400, detail="El hallazgo no está asociado a un activo.")

    data = json.loads(finding.raw) if finding.raw else {}
    host = ParsedHost.from_dict(data.get("host", data))
    classification = classify_host(host)   # re-evalúa con el clasificador ACTUAL
    new_type = classification.get("asset_type")
    score = classification.get("score", finding.confidence)

    if not new_type or new_type == "unknown" or score < RECLASSIFY_MIN_CONFIDENCE:
        raise HTTPException(status_code=400, detail="Confianza insuficiente para reclasificar.")

    asset = AssetService.get_by_id(db, finding.matched_asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="Activo no encontrado.")
    if asset.asset_type == new_type:
        return {"asset_id": asset.id, "asset_type": asset.asset_type, "changed": False}

    BackupService.make_backup(db, "pre-apply")
    asset.asset_type = new_type
    db.commit()
    return {"asset_id": asset.id, "asset_type": new_type, "changed": True}