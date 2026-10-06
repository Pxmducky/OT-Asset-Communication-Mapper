"""Bandeja de revisión: ver hallazgos de escaneos y aplicar/descartar los
que quedaron 'por revisar'.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.models import ScanFinding
from app.schemas.finding import FindingResponse
from app.services.scan_processor import ScanProcessor

router = APIRouter(prefix="/api", tags=["Findings"])


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
    from app.services.backup_service import BackupService
    BackupService.make_backup(db, "pre-apply")
    asset = ScanProcessor.apply_finding(db, finding)
    return {"finding_id": finding.id, "status": finding.status, "asset_id": asset.id}


@router.post("/findings/{finding_id}/discard", response_model=dict)
def discard_finding(finding_id: int, db: Session = Depends(get_db)):
    finding = _get_finding_or_404(finding_id, db)
    finding.status = "discarded"
    db.commit()
    return {"finding_id": finding.id, "status": finding.status}