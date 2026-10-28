"""Convierte el XML en activos, clasificando por evidencias.

- Clasifica por el tipo con más evidencia (no por el botón).
- Separa el tipo del activo de sus servicios/fingerprints (se guardan en
  asset_fingerprints; decisión 2).
- Las evidencias que justifican el tipo van en el hallazgo (detalle del escaneo).
- Recomendaciones por host y agregadas por subred.
"""
import json
import logging
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Asset, AssetFingerprint, AssetService as AssetServiceRow, Scan, ScanFinding,
)
from app.scanning.confidence import APPLY_THRESHOLD, REVIEW_THRESHOLD, SUGGEST_THRESHOLD, classify_host
from app.scanning.parser import ParsedHost, merge_hosts, parse_nmap_xml
from app.scanning.profiles import PROFILES
from app.services.asset_service import AssetService as AssetSvc

log = logging.getLogger("ot-scanner")

_DISCOVERY = {"discovery", "general"}


def _host_product(host: ParsedHost) -> str | None:
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
        main = Path(scan.raw_xml_path)
        udp = main.with_name(main.stem + "_udp" + main.suffix)
        if udp.exists():
            try:
                hosts = merge_hosts(hosts, parse_nmap_xml(udp.read_text(encoding="utf-8")))
            except Exception:
                log.exception("No se pudo fusionar el XML UDP del escaneo %s", scan_id)

        is_discovery = scan.scan_profile in _DISCOVERY
        req_label = PROFILES.get(scan.scan_profile, {}).get("label", scan.scan_profile)

        summary = {"hosts_up": len(hosts), "created": 0, "updated": 0, "services": 0,
                   "review": 0, "low": 0, "scan_profile": scan.scan_profile}
        recommendations, host_cards = [], []
        winners = Counter()
        requested_best = 0

        for host in hosts:
            if not host.ip:
                continue
            cls = classify_host(host)
            if not is_discovery:
                requested_best = max(requested_best, cls["scores"].get(scan.scan_profile, 0))
            if cls["winner"] and cls["score"] >= SUGGEST_THRESHOLD:
                winners[cls["winner_label"]] += 1

            host_cards.append({"ip": host.ip, "winner": cls["winner"], "winner_label": cls["winner_label"],
                               "type": cls["asset_type"], "score": cls["score"], "os": cls["os"]})

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
                ScanProcessor._upsert_fingerprints(db, existing, cls)
                finding.matched_asset_id = existing.id
                finding.status, finding.applied = "confirmed", True
            elif cls["score"] >= APPLY_THRESHOLD:
                asset = ScanProcessor._create(db, host, cls)
                summary["created"] += 1
                summary["services"] += ScanProcessor._upsert_services(db, asset, host)
                ScanProcessor._upsert_fingerprints(db, asset, cls)
                finding.matched_asset_id = asset.id
                finding.status, finding.applied = "confirmed", True
            else:
                finding.status, finding.applied = "review", False
                summary["review" if cls["score"] >= REVIEW_THRESHOLD else "low"] += 1
                if cls["score"] >= SUGGEST_THRESHOLD and cls["winner"]:
                    recommendations.append({"ip": host.ip, "suggested_profile": cls["winner"],
                                            "suggested_label": cls["winner_label"], "score": cls["score"]})
            db.add(finding)

        summary["breakdown"] = [{"label": lbl, "count": n} for lbl, n in winners.most_common()]
        summary["advice"] = ScanProcessor._advice(is_discovery, req_label, requested_best, winners, recommendations)
        summary["recommendations"] = recommendations
        summary["hosts"] = host_cards
        scan.summary = json.dumps(summary)
        db.commit()
        return summary

    @staticmethod
    def _advice(is_discovery, req_label, requested_best, winners, recommendations):
        if is_discovery:
            if winners:
                parts = ", ".join(f"{lbl} ({n})" for lbl, n in winners.most_common())
                return (f"La red presenta: {parts}. Se recomienda ejecutar el descubrimiento "
                        f"especializado de los tipos detectados.")
            return "Descubrimiento listo, pero no reconocí tipos claros. Revisa los hallazgos."
        if requested_best < REVIEW_THRESHOLD:
            if recommendations:
                best = max(recommendations, key=lambda r: r["score"])
                return (f"Poco probable que sea {req_label}. Se parece más a "
                        f"{best['suggested_label']} ({best['score']}%). Corre 'Descubrir red/IP'.")
            return f"Poco probable que sea {req_label} y sin señales claras de otro tipo. Corre 'Descubrir red/IP'."
        return None

    # ---------- aplicar un hallazgo manual ----------

    @staticmethod
    def apply_finding(db: Session, finding: ScanFinding) -> Asset:
        data = json.loads(finding.raw) if finding.raw else {}
        host = ParsedHost.from_dict(data.get("host", data))
        cls = classify_host(host)
        asset = AssetSvc.get_by_ip(db, host.ip) if host.ip else None
        if asset is None:
            asset = ScanProcessor._create(db, host, cls)
        else:
            ScanProcessor._apply(db, asset, host, cls)
        ScanProcessor._upsert_services(db, asset, host)
        ScanProcessor._upsert_fingerprints(db, asset, cls)
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
    def _create(db: Session, host: ParsedHost, cls: dict) -> Asset:
        asset = Asset(
            asset_code=AssetSvc.next_code(db), asset_name=host.hostname or host.ip,
            asset_type=cls["asset_type"], ip=host.ip, mac=host.mac, hostname=host.hostname,
            vendor=host.vendor, product=_host_product(host), os=cls["os"],
            status="confirmed", discovery_source="scan", confidence=cls["score"],
            last_seen=datetime.now(timezone.utc),
        )
        db.add(asset)
        db.flush()
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
        asset.last_seen = datetime.now(timezone.utc)
        return (0, 1 if changed else 0)

    @staticmethod
    def _upsert_fingerprints(db: Session, asset: Asset, cls: dict) -> None:
        now = datetime.now(timezone.utc)
        for fp in cls.get("fingerprints", []):
            row = db.scalar(
                select(AssetFingerprint).where(
                    AssetFingerprint.asset_id == asset.id, AssetFingerprint.label == fp["label"]
                )
            )
            if row is None:
                db.add(AssetFingerprint(
                    asset_id=asset.id, kind=fp["kind"], label=fp["label"], detail=fp.get("detail"),
                    port=fp.get("port"), transport=fp.get("transport"), source=fp.get("source"),
                    first_seen=now, last_seen=now,
                ))
            else:
                row.last_seen = now
                if fp.get("detail"):
                    row.detail = fp["detail"]

    @staticmethod
    def _upsert_services(db: Session, asset: Asset, host: ParsedHost) -> int:
        count = 0
        now = datetime.now(timezone.utc)
        for p in host.ports:
            if p.state != "open":
                continue
            row = db.scalar(
                select(AssetServiceRow).where(
                    AssetServiceRow.asset_id == asset.id, AssetServiceRow.port == p.port,
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