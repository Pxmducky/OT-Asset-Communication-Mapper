
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.schemas.asset import (
    AssetCommunicationSummary,
    AssetCreate,
    AssetResponse,
    AssetUpdate,
)
from app.services.asset_service import AssetService
from app.services.communication_service import (
    CommunicationService,
)


router = APIRouter(
    prefix="/api/assets",
    tags=["Assets"],
)


@router.get(
    "",
    response_model=list[AssetResponse],
)
def get_assets(
    skip: int = Query(
        0,
        ge=0,
    ),
    limit: int = Query(
        100,
        ge=1,
        le=1000,
    ),
    db: Session = Depends(get_db),
):
    return AssetService.get_all(
        db,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/count",
)
def get_asset_count(
    db: Session = Depends(get_db),
):
    return {
        "count": AssetService.count(db)
    }


@router.get(
    "/{asset_id}",
    response_model=AssetResponse,
)
def get_asset(
    asset_id: int,
    db: Session = Depends(get_db),
):
    asset = AssetService.get_by_id(
        db,
        asset_id,
    )

    if asset is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Asset not found.",
        )

    return asset


@router.get(
    "/{asset_id}/communications",
    response_model=list[AssetCommunicationSummary],
)
def get_asset_communications(
    asset_id: int,
    db: Session = Depends(get_db),
):
    asset = AssetService.get_by_id(
        db,
        asset_id,
    )

    if asset is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Asset not found.",
        )

    return CommunicationService.get_for_asset(
        db,
        asset_id,
    )


@router.post(
    "",
    response_model=AssetResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_asset(
    data: AssetCreate,
    db: Session = Depends(get_db),
):
    try:
        return AssetService.create(
            db,
            data,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )


@router.put(
    "/{asset_id}",
    response_model=AssetResponse,
)
def update_asset(
    asset_id: int,
    data: AssetUpdate,
    db: Session = Depends(get_db),
):
    asset = AssetService.get_by_id(
        db,
        asset_id,
    )

    if asset is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Asset not found.",
        )

    try:
        return AssetService.update(
            db,
            asset,
            data,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )


@router.delete(
    "/{asset_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_asset(
    asset_id: int,
    db: Session = Depends(get_db),
):
    asset = AssetService.get_by_id(
        db,
        asset_id,
    )

    if asset is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Asset not found.",
        )

    AssetService.delete(
        db,
        asset,
    )
