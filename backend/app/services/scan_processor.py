"""Convierte el XML de un escaneo en activos, clasificando por el MEJOR tipo.

- El tipo lo decide el mayor puntaje entre todos los tipos (no el botón).
- Activo existente (por IP): completa campos vacíos + servicios + last_seen.
- Activo nuevo: se crea solo si el mejor puntaje >= APPLY_THRESHOLD.
  Si no, va a revisión y genera una RECOMENDACIÓN de qué escaneo correr.
- Genera consejos: descubrimiento recomienda tipos; escaneo específico fallido
  avisa que mejor uses 'Descubrir'.
"""
import json
import logging
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Asset, AssetService as AssetServiceRow, Scan, ScanFinding
from app.scanning.confidence import (
    APPLY_THRESHOLD,
    REVIEW_THRESHOLD,
    SUGGEST_THRESHOLD,
    classify_host,
    score_for_profile,
)
from app.scanning.parser import ParsedHost, parse_nmap_xml
from app.scanning.profiles import PROFILES
from app.services.asset_service import AssetService as AssetSvc
from app.scanning.local_scanner import get_or_create_local_scanner
from app.scanning.targets import TargetMalformedError, network_contains_target, parse_target

log = logging.getLogger("ot-scanner")

_DISCOVERY_PROFILES = {"discovery", "general"}


def _host_product(host: ParsedHost) -> str | None:
    """Mejor cadena de producto/versión del host (para el punto 1)."""
    for p in host.ports:
        if p.product:
            return (p.product + (f" {p.version}" if p.version else "")).strip()
    return None


class ScanProcessor:

    @staticmethod
    def process_scan(db: Session, scan_id: int) -> dict:
        scan = db.scalar(select(Scan).where(Scan.id == scan_id))
        if scan is None or not scan.raw_xml_path or not Path(scan.raw_xml_path).exists():
            return {}

        hosts = parse_nmap_xml(Path(scan.raw_xml_path).read_text(encoding="utf-8"))
        is_discovery = scan.scan_profile in _DISCOVERY_PROFILES
        req_label = PROFILES.get(scan.scan_profile, {}).get("label", scan.scan_profile)

        summary = {
            "hosts_up": len(hosts), "created": 0, "updated": 0, "services": 0,
            "review": 0, "low": 0, "scan_profile": scan.scan_profile,
        }
        recommendations: list[dict] = []
        host_cards: list[dict] = []
        requested_best = 0

        for host in hosts:
            if not host.ip:
                continue
            cls = classify_host(host)
            if not is_discovery:
                requested_best = max(requested_best, score_for_profile(host, scan.scan_profile))

            host_cards.append({
                "ip": host.ip, "winner": cls["winner"], "winner_label": cls["winner_label"],
                "type": cls["asset_type"], "score": cls["score"], "os": cls["os"],
            })

            finding = ScanFinding(
                scan_id=scan.id, ip=host.ip, mac=host.mac, vendor=host.vendor,
                detected_os=cls["os"], confidence=cls["score"],
                raw=json.dumps({"host": host.to_dict(), "classification": cls}),
            )

            existing = AssetSvc.get_by_ip(db, host.ip)
            if existing is not None:
                _, updated = ScanProcessor._apply(db, existing, host, cls)
                summary["updated"] += updated
                summary["services"] += ScanProcessor._upsert_services(db, existing, host)
                finding.matched_asset_id = existing.id
                finding.status, finding.applied = "confirmed", True
            elif cls["score"] >= APPLY_THRESHOLD:
                asset = ScanProcessor._create(db, host, cls)
                summary["created"] += 1
                summary["services"] += ScanProcessor._upsert_services(db, asset, host)
                finding.matched_asset_id = asset.id
                finding.status, finding.applied = "confirmed", True
            else:
                finding.status, finding.applied = "review", False
                summary["review" if cls["score"] >= REVIEW_THRESHOLD else "low"] += 1
                if cls["score"] >= SUGGEST_THRESHOLD:
                    recommendations.append({
                        "ip": host.ip, "suggested_profile": cls["winner"],
                        "suggested_label": cls["winner_label"], "score": cls["score"],
                    })

            db.add(finding)

        # ----- consejos (Caso 1 descubrir / Caso 2 específico fallido) -----
        advice = None
        if is_discovery:
            if recommendations:
                counts = Counter(r["suggested_label"] for r in recommendations)
                parts = ", ".join(f"{label} (x{n})" for label, n in counts.items())
                advice = f"Descubrimiento listo. Te recomiendo escanear específicamente: {parts}."
            elif summary["created"] == 0:
                advice = "Descubrimiento listo, pero no reconocí tipos claros. Revisa los hallazgos."
        elif requested_best < REVIEW_THRESHOLD:
            if recommendations:
                best = max(recommendations, key=lambda r: r["score"])
                advice = (f"Poco probable que sea {req_label}. Se parece más a "
                          f"{best['suggested_label']} ({best['score']}%). Corre 'Descubrir red/IP'.")
            else:
                advice = (f"Poco probable que sea {req_label} y no hay señales claras de otro tipo. "
                          f"Corre 'Descubrir red/IP'.")

        summary["advice"] = advice
        summary["recommendations"] = recommendations
        summary["hosts"] = host_cards
        scan.summary = json.dumps(summary)
        db.commit()
        return summary

    # ---------- aplicar un hallazgo desde la bandeja (manual) ----------

    @staticmethod
    def apply_finding(db: Session, finding: ScanFinding) -> Asset:
        data = json.loads(finding.raw) if finding.raw else {}
        host = ParsedHost.from_dict(data.get("host", data))  # compat con formato viejo
        cls = classify_host(host)

        asset = AssetSvc.get_by_ip(db, host.ip) if host.ip else None
        if asset is None:
            asset = ScanProcessor._create(db, host, cls)
        else:
            ScanProcessor._apply(db, asset, host, cls)
        ScanProcessor._upsert_services(db, asset, host)

        finding.matched_asset_id = asset.id
        finding.status, finding.applied = "confirmed", True
        db.commit()
        return asset

    # ---------- helpers ----------
    @staticmethod
    def _network_for_ip(db: Session, ip: str):
        """La red autorizada MÁS específica que contiene esta IP (para heredar ubicación)."""
        try:
            target = parse_target(ip)
        except TargetMalformedError:
            return None
        agent = get_or_create_local_scanner(db)
        best, best_len = None, -1
        for n in agent.allowed_networks:
            if network_contains_target(n.cidr, target):
                plen = int(n.cidr.split("/")[1]) if "/" in n.cidr else 32
                if plen > best_len:
                    best, best_len = n, plen
        return best

    @staticmethod
    def _apply_location(db: Session, asset: Asset, ip: str) -> None:
        net = ScanProcessor._network_for_ip(db, ip)
        if net is None:
            return
        ScanProcessor._fill_empty(asset, "plant", net.plant)
        ScanProcessor._fill_empty(asset, "building", net.building)
        ScanProcessor._fill_empty(asset, "production_line", net.production_line)
        ScanProcessor._fill_empty(asset, "vlan", net.vlan)

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
    def _create(db: Session, host: ParsedHost, cls: dict) -> Asset:
        asset = Asset(
            asset_code=AssetSvc.next_code(db),
            asset_name=host.hostname or host.ip,
            asset_type=cls["asset_type"],
            ip=host.ip,
            mac=host.mac,
            hostname=host.hostname,
            vendor=host.vendor,
            product=_host_product(host),
            os=cls["os"],
            status="confirmed",
            discovery_source="scan",
            confidence=cls["score"],
            last_seen=datetime.now(timezone.utc),
        )
        db.add(asset)
        db.flush()
        ScanProcessor._apply_location(db, asset, host.ip)
        return asset

    @staticmethod
    def _apply(db: Session, asset: Asset, host: ParsedHost, cls: dict) -> tuple[int, int]:
        changed = False
        changed |= ScanProcessor._fill_empty(asset, "asset_name", host.hostname or host.ip)
        changed |= ScanProcessor._fill_empty(asset, "hostname", host.hostname)
        changed |= ScanProcessor._fill_empty(asset, "mac", host.mac)
        changed |= ScanProcessor._fill_empty(asset, "vendor", host.vendor)
        changed |= ScanProcessor._fill_empty(asset, "product", _host_product(host))
        changed |= ScanProcessor._fill_empty(asset, "os", cls["os"])
        ScanProcessor._apply_location(db, asset, host.ip)
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