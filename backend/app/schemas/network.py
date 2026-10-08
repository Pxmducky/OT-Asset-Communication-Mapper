from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.scanning.targets import TargetMalformedError, parse_network


class NetworkLocation(BaseModel):
    plant: str | None = None
    building: str | None = None
    production_line: str | None = None
    vlan: int | None = Field(default=None, ge=1, le=4094)


class NetworkCreate(NetworkLocation):
    cidr: str
    description: str | None = None

    @field_validator("cidr")
    @classmethod
    def normalize(cls, value: str) -> str:
        try:
            return str(parse_network(value))
        except TargetMalformedError as exc:
            raise ValueError(str(exc)) from exc


class NetworkUpdate(NetworkLocation):
    description: str | None = None


class NetworkResponse(BaseModel):
    id: int
    cidr: str
    description: str | None = None
    plant: str | None = None
    building: str | None = None
    production_line: str | None = None
    vlan: int | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)