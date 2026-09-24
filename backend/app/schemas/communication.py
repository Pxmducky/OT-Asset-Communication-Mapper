from datetime import datetime

from pydantic import BaseModel, ConfigDict


class CommunicationBase(BaseModel):
    source_asset_id: int
    destination_asset_id: int

    source: str
    destination: str

    protocol: str

    source_port: str | None = None
    destination_port: str | None = None

    source_name: str | None = None
    destination_name: str | None = None


class CommunicationCreate(CommunicationBase):
    pass


class CommunicationUpdate(BaseModel):
    source_asset_id: int | None = None
    destination_asset_id: int | None = None

    source: str | None = None
    destination: str | None = None

    protocol: str | None = None

    source_port: str | None = None
    destination_port: str | None = None

    source_name: str | None = None
    destination_name: str | None = None


class CommunicationResponse(CommunicationBase):
    id: int

    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
    )