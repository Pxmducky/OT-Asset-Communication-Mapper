"""Respaldos de la base (copia del archivo SQLite).

Usa la API de backup de SQLite (copia consistente aunque la base esté en uso).
Se toma un respaldo antes de aplicar los resultados de cada escaneo (pre-scan),
antes de aplicar un hallazgo manual (pre-apply), y el usuario puede tomar uno
manual. Consultables, descargables y restaurables.
"""
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.database import DATA_DIR
from app.models import Backup

log = logging.getLogger("ot-scanner")

BACKUPS_DIR = DATA_DIR / "backups"
DB_PATH = DATA_DIR / "mapper.db"


class BackupService:

    @staticmethod
    def _copy(src: Path, dest: Path) -> None:
        src_conn = sqlite3.connect(str(src))
        dest_conn = sqlite3.connect(str(dest))
        try:
            with dest_conn:
                src_conn.backup(dest_conn)   # copia atómica y consistente
        finally:
            src_conn.close()
            dest_conn.close()

    @staticmethod
    def make_backup(db: Session, reason: str, scan_id: int | None = None) -> Backup | None:
        if not DB_PATH.exists():
            return None
        BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        dest = BACKUPS_DIR / f"backup_{ts}_{reason}.db"
        i = 1
        while dest.exists():
            dest = BACKUPS_DIR / f"backup_{ts}_{reason}_{i}.db"
            i += 1
        BackupService._copy(DB_PATH, dest)
        row = Backup(reason=reason, path=str(dest), size_bytes=dest.stat().st_size, scan_id=scan_id)
        db.add(row)
        db.commit()
        db.refresh(row)
        return row

    @staticmethod
    def get_all(db: Session) -> list[Backup]:
        return list(db.scalars(select(Backup).order_by(Backup.id.desc())).all())

    @staticmethod
    def get_by_id(db: Session, backup_id: int) -> Backup | None:
        return db.scalar(select(Backup).where(Backup.id == backup_id))

    @staticmethod
    def restore(db: Session, backup: Backup) -> None:
        src = Path(backup.path)
        if not src.exists():
            raise FileNotFoundError("El archivo de respaldo ya no existe en disco.")
        BackupService.make_backup(db, "pre-restore")  # red de seguridad del estado actual
        BackupService._copy(src, DB_PATH)             # restaura el respaldo sobre la base viva

    @staticmethod
    def delete(db: Session, backup: Backup) -> None:
        path = Path(backup.path)
        if path.exists():
            path.unlink()
        db.delete(backup)
        db.commit()