from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.models.communication import Communication
from app.schemas.communication import CommunicationCreate, CommunicationResponse, CommunicationUpdate
from app.services.communication_service import CommunicationService

router = APIRouter(prefix="/api/communications", tags=["Communications"])


def get_communication_or_404(communication_id: int, db: Session = Depends(get_db)) -> Communication:
    communication = CommunicationService.get_by_id(db, communication_id)
    if communication is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comunicación no encontrada.")
    return communication


@router.get("", response_model=list[CommunicationResponse])
def get_communications(
    skip: int = Query(0, ge=0),
    limit: int | None = Query(None, ge=1, description="Sin límite si se omite"),
    db: Session = Depends(get_db),
):
    return CommunicationService.get_all(db, skip=skip, limit=limit)


@router.get("/count")
def get_communication_count(db: Session = Depends(get_db)):
    return {"count": CommunicationService.count(db)}


@router.get("/{communication_id}", response_model=CommunicationResponse)
def get_communication(communication: Communication = Depends(get_communication_or_404)):
    return communication


@router.post("", response_model=CommunicationResponse, status_code=status.HTTP_201_CREATED)
def create_communication(data: CommunicationCreate, db: Session = Depends(get_db)):
    try:
        return CommunicationService.create(db, data)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


@router.put("/{communication_id}", response_model=CommunicationResponse)
def update_communication(
    data: CommunicationUpdate,
    communication: Communication = Depends(get_communication_or_404),
    db: Session = Depends(get_db),
):
    try:
        return CommunicationService.update(db, communication, data)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


@router.delete("/{communication_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_communication(
    communication: Communication = Depends(get_communication_or_404),
    db: Session = Depends(get_db),
):
    CommunicationService.delete(db, communication)