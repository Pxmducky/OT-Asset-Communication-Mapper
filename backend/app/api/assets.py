from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.models.asset import Asset
from app.schemas.asset import AssetCreate, AssetResponse, AssetUpdate
from app.schemas.communication import CommunicationResponse
from app.services.asset_service import AssetService
from app.services.communication_service import CommunicationService

router = APIRouter(prefix="/api/assets", tags=["Assets"])


def get_asset_or_404(asset_id: int, db: Session = Depends(get_db)) -> Asset:
    asset = AssetService.get_by_id(db, asset_id)
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Activo no encontrado.")
    return asset


@router.get("", response_model=list[AssetResponse])
def get_assets(
    skip: int = Query(0, ge=0),
    limit: int | None = Query(None, ge=1, description="Sin límite si se omite"),
    db: Session = Depends(get_db),
):
    return AssetService.get_all(db, skip=skip, limit=limit)


@router.get("/count")
def get_asset_count(db: Session = Depends(get_db)):
    return {"count": AssetService.count(db)}


@router.get("/{asset_id}", response_model=AssetResponse)
def get_asset(asset: Asset = Depends(get_asset_or_404)):
    return asset


@router.get("/{asset_id}/communications", response_model=list[CommunicationResponse])
def get_asset_communications(asset: Asset = Depends(get_asset_or_404), db: Session = Depends(get_db)):
    return CommunicationService.get_for_asset(db, asset.id)


@router.post("", response_model=AssetResponse, status_code=status.HTTP_201_CREATED)
def create_asset(data: AssetCreate, db: Session = Depends(get_db)):
    try:
        return AssetService.create(db, data)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


@router.put("/{asset_id}", response_model=AssetResponse)
def update_asset(data: AssetUpdate, asset: Asset = Depends(get_asset_or_404), db: Session = Depends(get_db)):
    try:
        return AssetService.update(db, asset, data)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


@router.delete("/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_asset(asset: Asset = Depends(get_asset_or_404), db: Session = Depends(get_db)):
    AssetService.delete(db, asset)