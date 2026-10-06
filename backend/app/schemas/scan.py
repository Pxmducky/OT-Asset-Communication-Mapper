from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ScanRequestCreate(BaseModel):
    target: str                      # IP o CIDR
    scan_profile: str                # plc | hmi | printers | ...
    params: dict | None = None
    requested_by: str | None = None


class ScanResponse(BaseModel):
    id: int
    agent_id: int
    scan_profile: str
    target: str
    status: str
    request_count: int = 0
    summary: str | None = None
    error: str | None = None
    queued_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_scan(cls, scan) -> "ScanResponse":
        return cls(
            id=scan.id,
            agent_id=scan.agent_id,
            scan_profile=scan.scan_profile,
            target=scan.target,
            status=scan.status,
            request_count=len(scan.requests),
            summary=scan.summary,
            error=scan.error,
            queued_at=scan.queued_at,
            started_at=scan.started_at,
            finished_at=scan.finished_at,
        )


class ScanRequestResult(BaseModel):
    scan: ScanResponse
    coalesced: bool


class ScanProfileResponse(BaseModel):
    value: str
    label: str