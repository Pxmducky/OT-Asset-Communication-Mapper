from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.schemas.backup import BackupResponse
from app.services.backup_service import BackupService

router = APIRouter(prefix="/api/backups", tags=["Backups"])


@router.get("", response_model=list[BackupResponse])
def list_backups(db: Session = Depends(get_db)):
    return BackupService.get_all(db)


@router.post("", response_model=BackupResponse)
def create_backup(db: Session = Depends(get_db)):
    backup = BackupService.make_backup(db, "manual")
    if backup is None:
        raise HTTPException(status_code=500, detail="No se pudo crear el respaldo.")
    return backup


@router.get("/{backup_id}/download")
def download_backup(backup_id: int, db: Session = Depends(get_db)):
    backup = BackupService.get_by_id(db, backup_id)
    if backup is None or not Path(backup.path).exists():
        raise HTTPException(status_code=404, detail="Respaldo no encontrado.")
    return FileResponse(backup.path, filename=Path(backup.path).name, media_type="application/octet-stream")


@router.post("/{backup_id}/restore", response_model=dict)
def restore_backup(backup_id: int, db: Session = Depends(get_db)):
    backup = BackupService.get_by_id(db, backup_id)
    if backup is None:
        raise HTTPException(status_code=404, detail="Respaldo no encontrado.")
    try:
        BackupService.restore(db, backup)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=410, detail=str(exc))
    return {"restored_from": backup.id,
            "note": "Base restaurada. Reinicia el backend para asegurar un estado limpio."}


@router.delete("/{backup_id}", response_model=dict)
def delete_backup(backup_id: int, db: Session = Depends(get_db)):
    backup = BackupService.get_by_id(db, backup_id)
    if backup is None:
        raise HTTPException(status_code=404, detail="Respaldo no encontrado.")
    BackupService.delete(db, backup)
    return {"deleted": backup_id}