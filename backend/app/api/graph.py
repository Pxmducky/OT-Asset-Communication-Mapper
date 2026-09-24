from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.schemas.graph import GraphResponse
from app.services.asset_service import AssetService
from app.services.communication_service import CommunicationService

router = APIRouter(prefix="/api/graph", tags=["Graph"])


@router.get("", response_model=GraphResponse)
def get_graph(db: Session = Depends(get_db)):
    """Todos los activos y TODAS las comunicaciones en una sola llamada."""
    return {
        "assets": AssetService.get_all(db),
        "communications": CommunicationService.get_all(db),
    }