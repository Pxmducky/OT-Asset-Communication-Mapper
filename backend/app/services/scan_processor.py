"""Convierte el XML en activos, clasificando por evidencias.

- Clasifica por el tipo con más evidencia (no por el botón).
- Separa el tipo del activo de sus servicios/fingerprints (se guardan en
  asset_fingerprints; decisión 2).
- Las evidencias que justifican el tipo van en el hallazgo (detalle del escaneo).
- Recomendaciones por host y agregadas por subred.

V2 — aprobación obligatoria:
- Ningún escaneo escribe en el inventario por sí solo. Cada host queda como
  hallazgo 'review' (pendiente) hasta que el usuario lo APRUEBA o lo RECHAZA.
- Si el host ya existe (por IP, o por MAC si la IP no coincide; p. ej. un activo
  importado del Excel), el hallazgo queda ligado a ese activo y al aprobarse
  solo COMPLEMENTA: llena campos vacíos, nunca sobrescribe datos guardados.
- Rechazar elimina el hallazgo (ver api/findings.py).
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
from app.scanning.attributes import DESCRIPTION_FIELDS, as_dict
from app.scanning.parser import ParsedHost, merge_hosts, parse_nmap_xml
from app.scanning.profiles import PROFILES
from app.services import network_location
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

        summary = {"hosts_up": len(hosts), "pending": 0, "matched": 0, "low": 0,
                   "created": 0, "updated": 0, "review": 0,   # compat. con la UI anterior
                   "scan_profile": scan.scan_profile}
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

            attrs = as_dict(cls.get("attributes"))
            finding = ScanFinding(
                scan_id=scan.id, ip=host.ip, mac=attrs.get("mac") or host.mac, vendor=attrs.get("vendor") or host.vendor,
                detected_os=cls["os"], confidence=cls["score"],
                raw=json.dumps({"host": host.to_dict(), "classification": cls}),
            )

            existing = ScanProcessor._match_asset(db, host)
            finding.matched_asset_id = existing.id if existing is not None else None
            finding.status, finding.applied = "review", False
            summary["pending"] += 1
            if existing is not None:
                summary["matched"] += 1
            if cls["score"] < REVIEW_THRESHOLD:
                summary["low"] += 1
            if existing is None and cls["score"] < APPLY_THRESHOLD and cls["score"] >= SUGGEST_THRESHOLD and cls["winner"]:
                recommendations.append({"ip": host.ip, "suggested_profile": cls["winner"],
                                        "suggested_label": cls["winner_label"], "score": cls["score"]})
            db.add(finding)

        summary["breakdown"] = [{"label": lbl, "count": n} for lbl, n in winners.most_common()]
        summary["advice"] = ScanProcessor._advice(is_discovery, req_label, requested_best, winners, recommendations)
        summary["review"] = summary["pending"]
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
                        f"{best['suggested_label']} (puntuación {best['score']}). Corre 'Descubrir red/IP'.")
            return f"Poco probable que sea {req_label} y sin señales claras de otro tipo. Corre 'Descubrir red/IP'."
        return None

    # ---------- aplicar un hallazgo manual ----------

    @staticmethod
    def apply_finding(db: Session, finding: ScanFinding) -> Asset:
        data = json.loads(finding.raw) if finding.raw else {}
        host = ParsedHost.from_dict(data.get("host", data))
        cls = classify_host(host)
        asset = None
        if finding.matched_asset_id:
            asset = AssetSvc.get_by_id(db, finding.matched_asset_id)
        if asset is None:
            asset = ScanProcessor._match_asset(db, host)
        if asset is None:
            asset = ScanProcessor._create(db, host, cls)
        else:
            ScanProcessor._apply(db, asset, host, cls)
        ScanProcessor._upsert_services(db, asset, host)
        ScanProcessor._upsert_fingerprints(db, asset, cls)
        network_location.assign_one(db, asset)
        finding.matched_asset_id = asset.id
        finding.status, finding.applied = "confirmed", True
        db.commit()
        return asset

    # ---------- helpers ----------

    @staticmethod
    def _match_asset(db: Session, host: ParsedHost) -> Asset | None:
        """Busca el activo existente: primero por IP, luego por MAC."""
        if host.ip:
            asset = AssetSvc.get_by_ip(db, host.ip)
            if asset is not None:
                return asset
        if host.mac:
            return db.scalar(select(Asset).where(Asset.mac.ilike(host.mac)))
        return None

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
        a = as_dict(cls.get("attributes"))
        asset = Asset(
            asset_code=AssetSvc.next_code(db),
            asset_name=a.get("asset_name") or a.get("hostname") or host.ip,
            asset_type=cls["asset_type"], ip=host.ip, mac=a.get("mac"), hostname=a.get("hostname"),
            vendor=a.get("vendor"), product=a.get("product"), os=a.get("os") or cls["os"],
            description=" · ".join(f"{lbl}: {a[k]}" for k, lbl in DESCRIPTION_FIELDS if a.get(k)) or None,
            status="confirmed", discovery_source="scan", confidence=cls["score"],
            last_seen=datetime.now(timezone.utc),
        )
        db.add(asset)
        db.flush()
        return asset

    @staticmethod
    def _apply(db: Session, asset: Asset, host: ParsedHost, cls: dict) -> tuple[int, int]:
        """Complementa el activo con lo detectado: solo llena lo vacío; nunca sobrescribe."""
        a = as_dict(cls.get("attributes"))
        changed = False
        changed |= ScanProcessor._fill_empty(asset, "asset_name", a.get("asset_name") or a.get("hostname") or host.ip)
        changed |= ScanProcessor._fill_empty(asset, "ip", host.ip)
        for field in ("hostname", "mac", "vendor", "product"):
            changed |= ScanProcessor._fill_empty(asset, field, a.get(field))
        changed |= ScanProcessor._fill_empty(asset, "os", a.get("os") or cls["os"])
        for key, lbl in DESCRIPTION_FIELDS:
            if a.get(key) and a[key] not in (asset.description or ""):
                asset.description = " · ".join(x for x in (asset.description, f"{lbl}: {a[key]}") if x)
                changed = True
        # Tipo: solo si estaba vacío o 'unknown' y el escaneo trae uno claro
        new_type = cls.get("asset_type")
        if new_type and new_type != "unknown" and asset.asset_type in (None, "", "unknown"):
            asset.asset_type = new_type
            changed = True
        if asset.confidence in (None, 0) and cls.get("score"):
            asset.confidence = cls["score"]
            changed = True
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
                row.state = p.state
                row.service = row.service or p.service
                row.product = row.product or p.product
                row.version = row.version or p.version
                row.extra = row.extra or extra
                row.last_seen = now
            count += 1
        return count