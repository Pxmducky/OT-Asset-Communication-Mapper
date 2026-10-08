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
    created_at: datetime

    @classmethod
    def from_finding(cls, f) -> "FindingResponse":
        data = json.loads(f.raw) if f.raw else {}
        host = data.get("host", data)          # compat con formato viejo
        classification = data.get("classification", {})

        open_ports: list[str] = []
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
            winner_label=classification.get("winner_label"),
            winner_type=classification.get("asset_type"),
            open_ports=open_ports, created_at=f.created_at,
        )