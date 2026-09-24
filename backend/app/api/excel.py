from datetime import datetime

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.exporters.excel_exporter import ExcelExporter
from app.importers.excel_importer import ExcelImporter, ExcelImportError
from app.schemas.excel import ExcelImportResponse

router = APIRouter(prefix="/api/excel", tags=["Excel"])

XLSX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@router.post("/import", response_model=ExcelImportResponse)
async def import_excel(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Agrega activos y comunicaciones nuevas; omite las que ya existen."""
    if not (file.filename or "").lower().endswith((".xlsx", ".xlsm")):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El archivo debe ser .xlsx o .xlsm")

    content = await file.read()
    try:
        result = ExcelImporter(db).import_bytes(content)
    except ExcelImportError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    return ExcelImportResponse(**vars(result))


@router.get("/export")
def export_excel(db: Session = Depends(get_db)):
    buffer = ExcelExporter(db).export()
    filename = f"ot_inventory_{datetime.now():%Y%m%d_%H%M}.xlsx"
    return StreamingResponse(
        buffer,
        media_type=XLSX_MEDIA_TYPE,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )