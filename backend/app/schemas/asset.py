from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AssetBase(BaseModel):
    asset_code: str
    asset_name: str
    asset_type: str

    ip: str | None = None
    mac: str | None = None
    hostname: str | None = None
    vendor: str | None = None
    product: str | None = None


class AssetCreate(AssetBase):
    pass


class AssetUpdate(BaseModel):
    asset_code: str | None = None
    asset_name: str | None = None
    asset_type: str | None = None

    ip: str | None = None
    mac: str | None = None
    hostname: str | None = None
    vendor: str | None = None
    product: str | None = None


class AssetResponse(AssetBase):
    id: int

    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
    )


class AssetCommunicationSummary(BaseModel):
    id: int

    source_asset_id: int
    destination_asset_id: int

    source: str
    destination: str

    protocol: str

    source_port: str | None = None
    destination_port: str | None = None

    source_name: str | None = None
    destination_name: str | None = None

    model_config = ConfigDict(
        from_attributes=True,
    )