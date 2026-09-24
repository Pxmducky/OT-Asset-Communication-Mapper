from datetime import datetime

from pydantic import BaseModel, ConfigDict


class CommunicationBase(BaseModel):
    source_asset_id: int
    destination_asset_id: int

    protocol: str

    source_port: str | None = None
    destination_port: str | None = None


class CommunicationCreate(CommunicationBase):
    pass


class CommunicationUpdate(BaseModel):
    source_asset_id: int | None = None
    destination_asset_id: int | None = None

    protocol: str | None = None

    source_port: str | None = None
    destination_port: str | None = None


class CommunicationResponse(CommunicationBase):
    id: int

    source_ip: str | None = None
    destination_ip: str | None = None

    source_name: str | None = None
    destination_name: str | None = None

    description: str | None = None

    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
    )