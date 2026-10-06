"""Validación de objetivos de escaneo.

Un objetivo puede ser una IP suelta (172.16.99.89) o un CIDR (172.16.99.0/24).
Se rechaza:
  - lo mal formado (p. ej. 192.168.440.0/24, octeto > 255)  -> TargetMalformedError
  - lo que no cae en ninguna red autorizada (p. ej. 8.8.8.8) -> TargetNotAuthorizedError
"""
import ipaddress

Network = ipaddress.IPv4Network | ipaddress.IPv6Network


class TargetMalformedError(ValueError):
    """La IP o el CIDR no son válidos."""


class TargetNotAuthorizedError(ValueError):
    """El objetivo no está dentro de ninguna red autorizada."""


def parse_target(value: str) -> Network:
    """Normaliza el objetivo a una red (una IP suelta se vuelve /32 o /128)."""
    text = (value or "").strip()
    if not text:
        raise TargetMalformedError("El objetivo está vacío.")
    try:
        return ipaddress.ip_network(text, strict=False)
    except ValueError as exc:
        raise TargetMalformedError(f"Objetivo inválido: {value}") from exc


def parse_network(value: str) -> Network:
    try:
        return ipaddress.ip_network((value or "").strip(), strict=False)
    except ValueError as exc:
        raise TargetMalformedError(f"Red inválida: {value}") from exc


def _contains(allowed: Network, target: Network) -> bool:
    if allowed.version != target.version:
        return False
    return target == allowed or target.subnet_of(allowed)


def network_contains_target(allowed_cidr: str, target: Network) -> bool:
    try:
        allowed = parse_network(allowed_cidr)
    except TargetMalformedError:
        return False
    return _contains(allowed, target)