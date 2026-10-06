"""Trabajador interno (modo integrado). Corre hasta MAX_PARALLEL_SCANS carriles
en paralelo: toma escaneos de la cola, corre nmap, respalda y procesa el XML.
"""
import logging
import threading

from app.config import get_scanner_settings
from app.database.database import SessionLocal
from app.scanning.local_scanner import get_or_create_local_scanner
from app.scanning.nmap_runner import ScanError, run_scan
from app.services.scan_service import MAX_PARALLEL_SCANS, ScanService

log = logging.getLogger("ot-scanner")


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
                scan_id, target, args = job
                try:
                    xml = run_scan(settings.nmap_path, args, target, settings.scan_timeout)
                    self._finish(scan_id, "completed", xml, None)
                except ScanError as exc:
                    log.error("Escaneo %s falló: %s", scan_id, exc)
                    self._finish(scan_id, "failed", None, str(exc))
            except Exception:
                log.exception("Error inesperado en el worker de escaneo.")
                self._stop.wait(settings.poll_interval)

    def _claim_next(self) -> tuple[int, str, list[str]] | None:
        # El candado evita que dos carriles tomen el mismo trabajo o rebasen el límite.
        with self._claim_lock:
            db = SessionLocal()
            try:
                agent = get_or_create_local_scanner(db)
                scan = ScanService.claim_next_job(db, agent)
                if scan is None:
                    return None
                return scan.id, scan.target, ScanService.job_args(scan)
            finally:
                db.close()

    def _finish(self, scan_id: int, status: str, xml: str | None, error: str | None) -> None:
        db = SessionLocal()
        try:
            agent = get_or_create_local_scanner(db)
            scan = ScanService.submit_result(db, agent, scan_id, status, xml, error)
            if scan is not None and scan.status == "completed":
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