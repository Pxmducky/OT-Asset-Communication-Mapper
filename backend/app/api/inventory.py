"""Reinicio del inventario: borra activos (Excel, escaneo y manuales),
comunicaciones, servicios, fingerprints, escaneos, hallazgos e historial de
importaciones. Conserva la configuración (agentes, redes permitidas) y los
respaldos. Siempre hace un respaldo antes."""
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.models import (
    Asset, AssetFingerprint, AssetService, Backup, Communication, ExcelImport,
    Scan, ScanFinding, ScanRequest,
)
from app.services.backup_service import BackupService

router = APIRouter(prefix="/api/inventory", tags=["Inventory"])

CONFIRM_WORD = "BORRAR"


@router.delete("", response_model=dict)
def reset_inventory(confirm: str, db: Session = Depends(get_db)):
    if confirm != CONFIRM_WORD:
        raise HTTPException(status_code=400, detail=f"Confirmación inválida: escribe {CONFIRM_WORD}.")

    active = db.scalar(select(func.count()).select_from(Scan).where(Scan.status.in_(("pending", "running"))))
    if active:
        raise HTTPException(status_code=409, detail="Hay escaneos en curso o en cola. Espera a que terminen o cancélalos.")

    backup = BackupService.make_backup(db, "pre-reset")

    counts = {
        "assets": db.scalar(select(func.count()).select_from(Asset)) or 0,
        "communications": db.scalar(select(func.count()).select_from(Communication)) or 0,
        "scans": db.scalar(select(func.count()).select_from(Scan)) or 0,
    }
    xml_paths = [p for p in db.scalars(select(Scan.raw_xml_path)).all() if p]

    db.execute(update(Backup).values(scan_id=None))
    for model in (ScanFinding, ScanRequest, Scan, Communication, AssetService,
                  AssetFingerprint, Asset, ExcelImport):
        db.execute(delete(model))
    db.commit()

    # Archivos XML crudos de los escaneos (y su pasada UDP)
    for raw in xml_paths:
        path = Path(raw)
        for f in (path, path.with_name(path.stem + "_udp" + path.suffix)):
            try:
                f.unlink(missing_ok=True)
            except OSError:
                pass

    return {"deleted": counts, "backup_id": backup.id if backup else None}