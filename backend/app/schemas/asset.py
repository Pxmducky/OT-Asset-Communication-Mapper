import ipaddress
import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

MAC_PATTERN = re.compile(r"^([0-9a-f]{2}:){5}[0-9a-f]{2}$")


class AssetValidators(BaseModel):
    """Validaciones compartidas por el alta y la edición de activos."""

    @field_validator("*", mode="before")
    @classmethod
    def strip_strings(cls, value):
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value

    @field_validator("ip", check_fields=False)
    @classmethod
    def validate_ip(cls, value):
        if value is None:
            return value
        try:
            return str(ipaddress.ip_address(value))
        except ValueError as exc:
            raise ValueError(f"IP inválida: {value}") from exc

    @field_validator("mac", check_fields=False)
    @classmethod
    def validate_mac(cls, value):
        if value is None:
            return value
        value = value.lower().replace("-", ":")
        if not MAC_PATTERN.match(value):
            raise ValueError("MAC inválida, formato esperado aa:bb:cc:dd:ee:ff")
        return value


class AssetCreate(AssetValidators):
    """Alta manual: se exigen todos los datos del inventario.

    asset_code es opcional; si no se envía se genera (AST-001, AST-002...).
    """

    asset_code: str | None = Field(default=None, max_length=50)
    asset_name: str = Field(max_length=255)
    asset_type: str = Field(max_length=100)

    ip: str
    mac: str | None = None
    hostname: str | None = Field(default=None, max_length=255)
    vlan: int = Field(ge=1, le=4094)

    vendor: str | None = Field(default=None, max_length=255)
    product: str | None = Field(default=None, max_length=255)
    description: str | None = None

    plant: str = Field(max_length=150)
    building: str = Field(max_length=150)
    production_line: str = Field(max_length=150)


class AssetUpdate(AssetValidators):
    """Edición parcial: solo se modifican los campos enviados.

    Enviar null en un campo opcional lo deja vacío.
    """

    asset_code: str | None = Field(default=None, max_length=50)
    asset_name: str | None = Field(default=None, max_length=255)
    asset_type: str | None = Field(default=None, max_length=100)

    ip: str | None = None
    mac: str | None = None
    hostname: str | None = Field(default=None, max_length=255)
    vlan: int | None = Field(default=None, ge=1, le=4094)

    vendor: str | None = Field(default=None, max_length=255)
    product: str | None = Field(default=None, max_length=255)
    description: str | None = None

    plant: str | None = Field(default=None, max_length=150)
    building: str | None = Field(default=None, max_length=150)
    production_line: str | None = Field(default=None, max_length=150)


class AssetResponse(BaseModel):
    id: int
    asset_code: str
    asset_name: str
    asset_type: str

    ip: str | None = None
    mac: str | None = None
    hostname: str | None = None
    vlan: int | None = None

    vendor: str | None = None
    product: str | None = None
    description: str | None = None

    plant: str | None = None
    building: str | None = None
    production_line: str | None = None

    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
    