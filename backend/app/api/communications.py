
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.schemas.communication import (
    CommunicationCreate,
    CommunicationResponse,
    CommunicationUpdate,
)
from app.services.communication_service import (
    CommunicationService,
)


router = APIRouter(
    prefix="/api/communications",
    tags=["Communications"],
)


@router.get(
    "",
    response_model=list[CommunicationResponse],
)
def get_communications(
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
    return CommunicationService.get_all(
        db,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/count",
)
def get_communication_count(
    db: Session = Depends(get_db),
):
    return {
        "count": CommunicationService.count(db)
    }


@router.get(
    "/{communication_id}",
    response_model=CommunicationResponse,
)
def get_communication(
    communication_id: int,
    db: Session = Depends(get_db),
):
    communication = CommunicationService.get_by_id(
        db,
        communication_id,
    )

    if communication is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Communication not found.",
        )

    return communication


@router.post(
    "",
    response_model=CommunicationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_communication(
    data: CommunicationCreate,
    db: Session = Depends(get_db),
):
    try:
        return CommunicationService.create(
            db,
            data,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )


@router.put(
    "/{communication_id}",
    response_model=CommunicationResponse,
)
def update_communication(
    communication_id: int,
    data: CommunicationUpdate,
    db: Session = Depends(get_db),
):
    communication = CommunicationService.get_by_id(
        db,
        communication_id,
    )

    if communication is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Communication not found.",
        )

    try:
        return CommunicationService.update(
            db,
            communication,
            data,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )


@router.delete(
    "/{communication_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_communication(
    communication_id: int,
    db: Session = Depends(get_db),
):
    communication = CommunicationService.get_by_id(
        db,
        communication_id,
    )

    if communication is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Communication not found.",
        )

    CommunicationService.delete(
        db,
        communication,
    )

