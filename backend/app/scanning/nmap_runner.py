"""Ejecuta nmap EN EL PROPIO SERVIDOR (modo integrado).

El servidor controla siempre su salida XML y descarta flags peligrosos de
salida/entrada que pudieran colarse en los args del perfil.
"""
import subprocess

_CONSUMING_DROP = {"-oX", "-oN", "-oG", "-oA", "-oS", "-oJ", "-iL", "-iR", "--resume", "--stylesheet"}
_STANDALONE_DROP = {"--webxml"}
_PREFIX_DROP = ("-oX", "-oN", "-oG", "-oA", "-oS", "-oJ", "-iL", "--stylesheet=")


class ScanError(Exception):
    pass


def sanitize_args(args: list[str]) -> list[str]:
    cleaned: list[str] = []
    skip_next = False
    for token in args:
        if skip_next:
            skip_next = False
            continue
        if token in _CONSUMING_DROP:
            skip_next = True
            continue
        if token in _STANDALONE_DROP:
            continue
        if token.startswith(_PREFIX_DROP):
            continue
        cleaned.append(token)
    return cleaned


def build_command(nmap_path: str, nmap_args: list[str], target: str) -> list[str]:
    return [nmap_path, *sanitize_args(nmap_args), "-oX", "-", target]


def run_scan(nmap_path: str, nmap_args: list[str], target: str, timeout: int) -> str:
    """Corre nmap y devuelve el XML (stdout). Lanza ScanError si falla."""
    command = build_command(nmap_path, nmap_args, target)
    try:
        completed = subprocess.run(
            command, capture_output=True, text=True, timeout=timeout, check=False
        )
    except FileNotFoundError as exc:
        raise ScanError(f"No se encontró nmap en '{nmap_path}'. ¿Está instalado?") from exc
    except subprocess.TimeoutExpired as exc:
        raise ScanError(f"El escaneo superó el tiempo máximo ({timeout}s).") from exc

    xml = completed.stdout or ""
    if "<nmaprun" in xml:
        return xml
    detail = (completed.stderr or "").strip() or f"nmap terminó con código {completed.returncode}."
    raise ScanError(detail)