from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AssetServiceResponse(BaseModel):
    id: int
    port: int
    transport: str
    state: str
    service: str | None = None
    product: str | None = None
    version: str | None = None
    extra: str | None = None
    first_seen: datetime
    last_seen: datetime

    model_config = ConfigDict(from_attributes=True)