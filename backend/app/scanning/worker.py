"""Trabajador interno (modo integrado). Corre hasta MAX_PARALLEL_SCANS carriles
en paralelo: toma escaneos de la cola, corre nmap (TCP y, si hace falta, UDP),
respalda y procesa el XML.

Regla UDP (segunda opinión): el UDP es lento, así que solo se corre cuando el
objetivo es UNA IP y el TCP quedó por debajo de 70 de confianza.
"""
import ipaddress
import logging
import threading
from pathlib import Path

from app.config import get_scanner_settings
from app.database.database import SessionLocal
from app.scanning.confidence import APPLY_THRESHOLD, classify_host
from app.scanning.local_scanner import get_or_create_local_scanner
from app.scanning.nmap_runner import ScanError, run_scan
from app.scanning.parser import parse_nmap_xml
from app.services.scan_service import MAX_PARALLEL_SCANS, ScanService

log = logging.getLogger("ot-scanner")


def _is_single_ip(target: str) -> bool:
    try:
        return ipaddress.ip_network(target, strict=False).num_addresses == 1
    except ValueError:
        return False


class LocalScanWorker:
    def __init__(self) -> None:
        self._stop = threading.Event()
        self._claim_lock = threading.Lock()
        self._threads: list[threading.Thread] = []

    def start(self) -> None:
        if self._threads and any(t.is_alive() for t in self._threads):
            return
        self._stop.clear()
        self._threads = []
        for i in range(MAX_PARALLEL_SCANS):
            thread = threading.Thread(target=self._run, name=f"scan-lane-{i + 1}", daemon=True)
            thread.start()
            self._threads.append(thread)
        log.info("Worker de escaneo iniciado (%d carriles en paralelo).", MAX_PARALLEL_SCANS)

    def stop(self, timeout: float = 5.0) -> None:
        self._stop.set()
        for thread in self._threads:
            thread.join(timeout=timeout)
        log.info("Worker de escaneo detenido.")

    def _run(self) -> None:
        settings = get_scanner_settings()
        while not self._stop.is_set():
            try:
                job = self._claim_next()
                if job is None:
                    self._stop.wait(settings.poll_interval)
                    continue
                scan_id, target, tcp_args, udp_args = job
                try:
                    xml = run_scan(settings.nmap_path, tcp_args, target, settings.scan_timeout)
                except ScanError as exc:
                    log.error("Escaneo %s (TCP) falló: %s", scan_id, exc)
                    self._finish(scan_id, "failed", None, None, str(exc))
                    continue

                udp_xml = self._maybe_udp(settings, scan_id, target, udp_args, xml)
                self._finish(scan_id, "completed", xml, udp_xml, None)
            except Exception:
                log.exception("Error inesperado en el worker de escaneo.")
                self._stop.wait(settings.poll_interval)

    def _maybe_udp(self, settings, scan_id, target, udp_args, tcp_xml) -> str | None:
        """Corre la pasada UDP solo si: hay udp_args, el objetivo es una IP única,
        y el TCP quedó por debajo del umbral de confirmación (70)."""
        if not udp_args or not _is_single_ip(target):
            return None
        try:
            hosts = parse_nmap_xml(tcp_xml)
            best = max((classify_host(h)["score"] for h in hosts if h.ip), default=0)
        except Exception:
            best = 0
        if best >= APPLY_THRESHOLD:
            return None  # TCP ya fue bueno: no hace falta UDP

        log.info("Escaneo %s: TCP dudoso (%d%%). Segunda opinión por UDP…", scan_id, best)
        try:
            return run_scan(settings.nmap_path, udp_args, target, settings.scan_timeout)
        except ScanError as exc:
            log.warning("Escaneo %s: la pasada UDP falló (%s). Sigo solo con TCP.", scan_id, exc)
            return None

    def _claim_next(self):
        with self._claim_lock:
            db = SessionLocal()
            try:
                agent = get_or_create_local_scanner(db)
                scan = ScanService.claim_next_job(db, agent)
                if scan is None:
                    return None
                return scan.id, scan.target, ScanService.job_args(scan), ScanService.job_udp_args(scan)
            finally:
                db.close()

    def _finish(self, scan_id, status, xml, udp_xml, error) -> None:
        db = SessionLocal()
        try:
            agent = get_or_create_local_scanner(db)
            scan = ScanService.submit_result(db, agent, scan_id, status, xml, error)
            if scan is not None and scan.status == "completed":
                if udp_xml and scan.raw_xml_path:
                    try:
                        p = Path(scan.raw_xml_path)
                        p.with_name(p.stem + "_udp" + p.suffix).write_text(udp_xml, encoding="utf-8")
                    except Exception:
                        log.exception("No se pudo guardar el XML UDP del escaneo %s", scan_id)
                try:
                    from app.services.backup_service import BackupService
                    BackupService.make_backup(db, "pre-scan", scan_id=scan_id)
                except Exception:
                    log.exception("No se pudo respaldar antes de aplicar el escaneo %s", scan_id)
                try:
                    from app.services.scan_processor import ScanProcessor
                    summary = ScanProcessor.process_scan(db, scan_id)
                    log.info("Escaneo %s procesado: %s", scan_id, summary)
                except Exception:
                    log.exception("Fallo al procesar el XML del escaneo %s", scan_id)
        finally:
            db.close()


local_worker = LocalScanWorker()