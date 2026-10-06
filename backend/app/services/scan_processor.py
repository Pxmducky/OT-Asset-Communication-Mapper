"""Convierte el XML de un escaneo en activos del inventario.

Reglas:
- Activo YA existente (por IP): solo se completan campos vacíos + se adjuntan
  servicios + last_seen. Nunca se sobrescribe lo capturado a mano/Excel.
- Activo NUEVO: se crea solo si la confianza >= APPLY_THRESHOLD (queda confirmado).
  Si no, se guarda como hallazgo en la bandeja de revisión.
- Los puertos abiertos son SERVICIOS del equipo (asset_services), nunca comunicaciones.
"""
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Asset, AssetService as AssetServiceRow, Scan, ScanFinding
from app.scanning.confidence import APPLY_THRESHOLD, score_host
from app.scanning.parser import ParsedHost, parse_nmap_xml
from app.services.asset_service import AssetService as AssetSvc

log = logging.getLogger("ot-scanner")


class ScanProcessor:

    @staticmethod
    def process_scan(db: Session, scan_id: int) -> dict:
        scan = db.scalar(select(Scan).where(Scan.id == scan_id))
        if scan is None or not scan.raw_xml_path or not Path(scan.raw_xml_path).exists():
            return {}

        xml_text = Path(scan.raw_xml_path).read_text(encoding="utf-8")
        hosts = parse_nmap_xml(xml_text)

        summary = {"hosts_up": len(hosts), "created": 0, "updated": 0,
                   "services": 0, "review": 0, "low": 0}

        for host in hosts:
            if not host.ip:
                continue
            verdict = score_host(host, scan.scan_profile)
            finding = ScanFinding(
                scan_id=scan.id, ip=host.ip, mac=host.mac, vendor=host.vendor,
                detected_os=verdict["os"], confidence=verdict["score"],
                raw=json.dumps(host.to_dict()),
            )

            existing = AssetSvc.get_by_ip(db, host.ip)
            if existing is not None:
                # Identidad segura por IP: aplicar siempre (completar + servicios).
                created, updated = ScanProcessor._apply(db, existing, host, verdict, scan)
                summary["updated"] += updated
                summary["services"] += ScanProcessor._upsert_services(db, existing, host)
                finding.matched_asset_id = existing.id
                finding.status, finding.applied = "confirmed", True
            elif verdict["score"] >= APPLY_THRESHOLD:
                asset = ScanProcessor._create(db, host, verdict, scan)
                summary["created"] += 1
                summary["services"] += ScanProcessor._upsert_services(db, asset, host)
                finding.matched_asset_id = asset.id
                finding.status, finding.applied = "confirmed", True
            else:
                finding.status, finding.applied = "review", False
                summary["review" if verdict["score"] >= 40 else "low"] += 1

            db.add(finding)

        scan.summary = json.dumps(summary)
        db.commit()
        return summary

    # ---------- aplicar un hallazgo desde la bandeja (manual) ----------

    @staticmethod
    def apply_finding(db: Session, finding: ScanFinding) -> Asset:
        host = ParsedHost.from_dict(json.loads(finding.raw))
        scan = db.scalar(select(Scan).where(Scan.id == finding.scan_id))
        verdict = score_host(host, scan.scan_profile) if scan else {
            "score": finding.confidence, "os": finding.detected_os, "asset_type": "Desconocido", "reasons": []}

        asset = AssetSvc.get_by_ip(db, host.ip) if host.ip else None
        if asset is None:
            asset = ScanProcessor._create(db, host, verdict, scan)
        else:
            ScanProcessor._apply(db, asset, host, verdict, scan)
        ScanProcessor._upsert_services(db, asset, host)

        finding.matched_asset_id = asset.id
        finding.status, finding.applied = "confirmed", True
        db.commit()
        return asset

    # ---------- helpers ----------

    @staticmethod
    def _fill_empty(asset: Asset, field: str, value) -> bool:
        if not value:
            return False
        current = getattr(asset, field)
        is_empty = current in (None, "") or (field == "asset_name" and current == asset.ip)
        if is_empty and current != value:
            setattr(asset, field, value)
            return True
        return False

    @staticmethod
    def _create(db: Session, host: ParsedHost, verdict: dict, scan: Scan | None) -> Asset:
        asset = Asset(
            asset_code=AssetSvc.next_code(db),
            asset_name=host.hostname or host.ip,
            asset_type=verdict["asset_type"],
            ip=host.ip,
            mac=host.mac,
            hostname=host.hostname,
            vendor=host.vendor,
            os=verdict["os"],
            status="confirmed",
            discovery_source="scan",
            confidence=verdict["score"],
            last_seen=datetime.now(timezone.utc),
        )
        db.add(asset)
        db.flush()  # para que next_code vea el nuevo código en el mismo lote
        return asset

    @staticmethod
    def _apply(db: Session, asset: Asset, host: ParsedHost, verdict: dict, scan: Scan | None) -> tuple[int, int]:
        changed = False
        changed |= ScanProcessor._fill_empty(asset, "asset_name", host.hostname or host.ip)
        changed |= ScanProcessor._fill_empty(asset, "hostname", host.hostname)
        changed |= ScanProcessor._fill_empty(asset, "mac", host.mac)
        changed |= ScanProcessor._fill_empty(asset, "vendor", host.vendor)
        changed |= ScanProcessor._fill_empty(asset, "os", verdict["os"])
        asset.last_seen = datetime.now(timezone.utc)
        return (0, 1 if changed else 0)

    @staticmethod
    def _upsert_services(db: Session, asset: Asset, host: ParsedHost) -> int:
        count = 0
        now = datetime.now(timezone.utc)
        for p in host.ports:
            if p.state != "open":
                continue
            row = db.scalar(
                select(AssetServiceRow).where(
                    AssetServiceRow.asset_id == asset.id,
                    AssetServiceRow.port == p.port,
                    AssetServiceRow.transport == p.transport,
                )
            )
            extra = json.dumps(p.scripts) if p.scripts else None
            if row is None:
                db.add(AssetServiceRow(
                    asset_id=asset.id, port=p.port, transport=p.transport, state=p.state,
                    service=p.service, product=p.product, version=p.version, extra=extra,
                    first_seen=now, last_seen=now,
                ))
            else:
                row.state, row.service, row.product, row.version = p.state, p.service, p.product, p.version
                if extra:
                    row.extra = extra
                row.last_seen = now
            count += 1
        return count