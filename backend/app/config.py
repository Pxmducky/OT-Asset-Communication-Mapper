"""Configuración del escáner (modo integrado).

El usuario solo define aquí (vía variables de entorno) sus redes permitidas y la
ruta de nmap. No hay token ni agentes.
"""
import os
from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class ScannerSettings:
    mode: str                          # "integrado"
    allowed_networks: tuple[str, ...]  # redes de planta que SÍ se pueden escanear
    nmap_path: str
    scan_timeout: int
    poll_interval: float


@lru_cache
def get_scanner_settings() -> ScannerSettings:
    raw = os.getenv("SCANNER_ALLOWED_NETWORKS", "")
    networks = tuple(n.strip() for n in raw.split(",") if n.strip())
    return ScannerSettings(
        mode=os.getenv("SCANNER_MODE", "integrado").strip().lower(),
        allowed_networks=networks,
        nmap_path=os.getenv("NMAP_PATH", "nmap").strip(),
        scan_timeout=int(os.getenv("SCANNER_SCAN_TIMEOUT", "7200")),
        poll_interval=float(os.getenv("SCANNER_POLL_INTERVAL", "5")),
    )