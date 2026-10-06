from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, computed_field


class BackupResponse(BaseModel):
    id: int
    reason: str
    path: str
    size_bytes: int | None = None
    scan_id: int | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @computed_field
    @property
    def filename(self) -> str:
        return Path(self.path).name