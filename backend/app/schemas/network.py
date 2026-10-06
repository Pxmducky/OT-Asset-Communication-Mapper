from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator

from app.scanning.targets import TargetMalformedError, parse_network


class NetworkResponse(BaseModel):
    id: int
    cidr: str
    description: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class NetworkCreate(BaseModel):
    cidr: str
    description: str | None = None

    @field_validator("cidr")
    @classmethod
    def normalize(cls, value: str) -> str:
        try:
            return str(parse_network(value))   # rechaza 192.168.440.0/24 y similares
        except TargetMalformedError as exc:
            raise ValueError(str(exc)) from exc