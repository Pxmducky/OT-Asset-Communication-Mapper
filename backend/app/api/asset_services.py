from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.models import Asset, AssetFingerprint, AssetService
from app.schemas.asset_fingerprint import AssetFingerprintResponse
from app.schemas.asset_service import AssetServiceResponse

router = APIRouter(prefix="/api/assets", tags=["Asset Services"])


def _asset_or_404(asset_id: int, db: Session) -> Asset:
    asset = db.scalar(select(Asset).where(Asset.id == asset_id))
    if asset is None:
        raise HTTPException(status_code=404, detail="Activo no encontrado.")
    return asset


@router.get("/{asset_id}/services", response_model=list[AssetServiceResponse])
def list_asset_services(asset_id: int, db: Session = Depends(get_db)):
    _asset_or_404(asset_id, db)
    stmt = select(AssetService).where(AssetService.asset_id == asset_id).order_by(AssetService.port)
    return list(db.scalars(stmt).all())


@router.get("/{asset_id}/fingerprints", response_model=list[AssetFingerprintResponse])
def list_asset_fingerprints(asset_id: int, db: Session = Depends(get_db)):
    _asset_or_404(asset_id, db)
    stmt = (
        select(AssetFingerprint)
        .where(AssetFingerprint.asset_id == asset_id)
        .order_by(AssetFingerprint.kind.desc(), AssetFingerprint.id)
    )
    return list(db.scalars(stmt).all())