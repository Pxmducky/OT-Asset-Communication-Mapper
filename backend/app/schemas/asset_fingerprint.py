from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AssetFingerprintResponse(BaseModel):
    id: int
    kind: str
    label: str
    detail: str | None = None
    port: int | None = None
    transport: str | None = None
    source: str | None = None
    first_seen: datetime
    last_seen: datetime

    model_config = ConfigDict(from_attributes=True)