import json
from datetime import datetime

from pydantic import BaseModel


class FindingResponse(BaseModel):
    id: int
    scan_id: int
    ip: str | None = None
    hostname: str | None = None
    mac: str | None = None
    vendor: str | None = None
    detected_os: str | None = None
    confidence: int
    status: str
    applied: bool
    matched_asset_id: int | None = None
    winner_label: str | None = None
    winner_type: str | None = None
    open_ports: list[str] = []
    evidences: list[dict] = []
    fingerprints: list[dict] = []
    ranking: list[dict] = []
    created_at: datetime

    @classmethod
    def from_finding(cls, f) -> "FindingResponse":
        data = json.loads(f.raw) if f.raw else {}
        host = data.get("host", data)
        c = data.get("classification", {})
        open_ports = []
        for p in host.get("ports", []):
            if p.get("state") == "open":
                label = f"{p['port']}/{p.get('transport', 'tcp')}"
                if p.get("service"):
                    label += f" {p['service']}"
                open_ports.append(label)
        return cls(
            id=f.id, scan_id=f.scan_id, ip=f.ip, hostname=host.get("hostname"), mac=f.mac,
            vendor=f.vendor, detected_os=f.detected_os, confidence=f.confidence,
            status=f.status, applied=f.applied, matched_asset_id=f.matched_asset_id,
            winner_label=c.get("winner_label"), winner_type=c.get("asset_type"),
            open_ports=open_ports, evidences=c.get("evidences", []),
            fingerprints=c.get("fingerprints", []), ranking=c.get("ranking", []),
            created_at=f.created_at,
        )