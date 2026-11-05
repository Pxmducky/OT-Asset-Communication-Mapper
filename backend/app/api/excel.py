from datetime import datetime

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.exporters.excel_exporter import ExcelExporter
from app.importers.excel_importer import ExcelImporter, ExcelImportError
from app.models import Asset, Communication, ExcelImport, ScanFinding
from app.schemas.excel import ExcelImportResponse
from app.services.backup_service import BackupService
from app.services import network_location

router = APIRouter(prefix="/api/excel", tags=["Excel"])

XLSX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@router.post("/import", response_model=ExcelImportResponse)
async def import_excel(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Agrega activos y comunicaciones nuevas; omite las que ya existen.
    Cada importación queda registrada para poder borrarla después."""
    if not (file.filename or "").lower().endswith((".xlsx", ".xlsm")):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El archivo debe ser .xlsx o .xlsm")

    content = await file.read()
    backup = BackupService.make_backup(db, "pre-excel-import")

    record = ExcelImport(filename=file.filename or "excel.xlsx", backup_id=backup.id if backup else None)
    db.add(record)
    db.flush()  # obtiene record.id para marcar lo que se cree

    try:
        result = ExcelImporter(db, import_id=record.id).import_bytes(content)
    except ExcelImportError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except Exception:
        db.rollback()
        raise

        # import_bytes ya hizo commit; actualiza el registro con los conteos
    import_id = None
    record = db.get(ExcelImport, record.id)
    if record is not None:
        if result.assets_created == 0 and result.communications_created == 0 and result.assets_updated == 0:
            db.delete(record)  # no agregó nada: no se lista
        else:
            record.assets_created = result.assets_created
            record.assets_updated = result.assets_updated
            record.communications_created = result.communications_created
            import_id = record.id
        db.commit()

    # Ubica los activos según los segmentos de red dados de alta
    placed = network_location.assign(db)
    db.commit()
    if placed:
        result.notes.append(f"{placed} activos ubicados según los segmentos de red dados de alta.")

    return ExcelImportResponse(**vars(result), import_id=import_id)

@router.get("/export")
def export_excel(db: Session = Depends(get_db)):
    buffer = ExcelExporter(db).export()
    filename = f"ot_inventory_{datetime.now():%Y%m%d_%H%M}.xlsx"
    return StreamingResponse(
        buffer,
        media_type=XLSX_MEDIA_TYPE,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ---------- historial de importaciones ----------

def _legacy_assets(db: Session) -> list[Asset]:
    """Activos marcados como Excel pero importados antes de existir el historial."""
    return db.scalars(
        select(Asset).where(Asset.discovery_source == "excel", Asset.import_id.is_(None))
    ).all()


def _delete_assets(db: Session, assets: list[Asset]) -> int:
    ids = [a.id for a in assets]
    for asset in assets:
        db.delete(asset)  # uno por uno: el cascade borra comunicaciones, servicios y fingerprints
    if ids:
        for finding in db.scalars(select(ScanFinding).where(ScanFinding.matched_asset_id.in_(ids))).all():
            finding.matched_asset_id = None
    return len(ids)


@router.get("/imports")
def list_imports(db: Session = Depends(get_db)):
    rows = db.scalars(select(ExcelImport).order_by(ExcelImport.id.desc())).all()
    imports = []
    for r in rows:
        remaining = db.scalar(select(Asset.id).where(Asset.import_id == r.id).limit(1))
        imports.append({
            "id": r.id,
            "filename": r.filename,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "assets_created": r.assets_created,
            "assets_updated": r.assets_updated,
            "communications_created": r.communications_created,
            "has_assets": remaining is not None,
        })
    return {"imports": imports, "legacy_assets": len(_legacy_assets(db))}


@router.delete("/imports/legacy")
def delete_legacy_imports(db: Session = Depends(get_db)):
    assets = _legacy_assets(db)
    if not assets:
        return {"deleted_assets": 0, "deleted_communications": 0}
    BackupService.make_backup(db, "pre-excel-delete")
    n = _delete_assets(db, assets)
    db.commit()
    return {"deleted_assets": n, "deleted_communications": 0}


@router.delete("/imports/{import_id}")
def delete_import(import_id: int, db: Session = Depends(get_db)):
    record = db.get(ExcelImport, import_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Importación no encontrada.")

    BackupService.make_backup(db, "pre-excel-delete")

    assets = db.scalars(select(Asset).where(Asset.import_id == import_id)).all()
    deleted_assets = _delete_assets(db, assets)
    db.flush()

    # Comunicaciones que la importación creó entre activos que ya existían
    comms = db.scalars(select(Communication).where(Communication.import_id == import_id)).all()
    for c in comms:
        db.delete(c)

    db.delete(record)
    db.commit()
    return {"deleted_assets": deleted_assets, "deleted_communications": len(comms)}