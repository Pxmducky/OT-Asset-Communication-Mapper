from pydantic import BaseModel

from app.schemas.asset import AssetResponse
from app.schemas.communication import CommunicationResponse


class GraphResponse(BaseModel):
    assets: list[AssetResponse]
    communications: list[CommunicationResponse]