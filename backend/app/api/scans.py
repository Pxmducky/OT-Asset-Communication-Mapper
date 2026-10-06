from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.scanning.profiles import list_profiles
from app.scanning.targets import TargetMalformedError, TargetNotAuthorizedError
from app.schemas.scan import (
    ScanProfileResponse,
    ScanRequestCreate,
    ScanRequestResult,
    ScanResponse,
)
from app.services.scan_service import ScanService

router = APIRouter(prefix="/api/scans", tags=["Scans"])


@router.get("/profiles", response_model=list[ScanProfileResponse])
def get_profiles():
    return list_profiles()


@router.get("", response_model=list[ScanResponse])
def list_scans(status: str | None = Query(None), db: Session = Depends(get_db)):
    return [ScanResponse.from_scan(scan) for scan in ScanService.get_all(db, status=status)]


@router.get("/{scan_id}", response_model=ScanResponse)
def get_scan(scan_id: int, db: Session = Depends(get_db)):
    scan = ScanService.get_by_id(db, scan_id)
    if scan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Escaneo no encontrado.")
    return ScanResponse.from_scan(scan)


@router.post("/request", response_model=ScanRequestResult, status_code=status.HTTP_201_CREATED)
def request_scan(data: ScanRequestCreate, db: Session = Depends(get_db)):
    try:
        scan, coalesced = ScanService.request_scan(db, data)
    except TargetMalformedError as exc:
        # Objetivo mal formado (p. ej. 192.168.440.0/24)
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    except TargetNotAuthorizedError as exc:
        # Fuera de toda red autorizada (p. ej. 8.8.8.8)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except ValueError as exc:
        # Perfil desconocido
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    return ScanRequestResult(scan=ScanResponse.from_scan(scan), coalesced=coalesced)