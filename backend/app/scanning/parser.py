"""Parsea el XML de nmap a una estructura limpia.

Maneja los casos reales observados: sin MAC (escaneo ruteado), puertos
'filtered' (no son servicios), y <osmatch> con basura de NAT/bridge (se ignora;
el SO confiable sale de los servicios y de smb-os-discovery).
"""
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, field


class NmapParseError(Exception):
    pass


@dataclass
class ParsedPort:
    port: int
    transport: str
    state: str
    service: str | None = None
    product: str | None = None
    version: str | None = None
    ostype: str | None = None
    cpe: list[str] = field(default_factory=list)
    scripts: dict[str, str] = field(default_factory=dict)


@dataclass
class ParsedHost:
    ip: str | None
    hostname: str | None = None
    mac: str | None = None
    vendor: str | None = None
    up: bool = True
    ports: list[ParsedPort] = field(default_factory=list)
    host_scripts: dict[str, str] = field(default_factory=dict)
    osmatches: list[dict] = field(default_factory=list)

    @property
    def open_ports(self) -> set[int]:
        return {p.port for p in self.ports if p.state == "open"}

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "ParsedHost":
        ports = [ParsedPort(**p) for p in data.get("ports", [])]
        return cls(**{**data, "ports": ports})


def parse_nmap_xml(xml_text: str) -> list[ParsedHost]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise NmapParseError(f"XML de nmap inválido: {exc}") from exc

    hosts: list[ParsedHost] = []
    for host_el in root.findall("host"):
        status = host_el.find("status")
        if status is not None and status.get("state") != "up":
            continue

        ip = mac = vendor = hostname = None
        for addr in host_el.findall("address"):
            kind = addr.get("addrtype")
            if kind == "ipv4" or (kind == "ipv6" and ip is None):
                ip = addr.get("addr")
            elif kind == "mac":
                mac = (addr.get("addr") or "").lower() or None
                vendor = addr.get("vendor") or None

        hn = host_el.find("hostnames/hostname")
        if hn is not None:
            hostname = hn.get("name")

        ports: list[ParsedPort] = []
        for port_el in host_el.findall("ports/port"):
            state_el = port_el.find("state")
            svc = port_el.find("service")
            scripts = {
                s.get("id"): (s.get("output") or "").strip()
                for s in port_el.findall("script")
                if s.get("id")
            }
            cpes = [c.text for c in (svc.findall("cpe") if svc is not None else []) if c.text]
            ports.append(
                ParsedPort(
                    port=int(port_el.get("portid")),
                    transport=port_el.get("protocol", "tcp"),
                    state=state_el.get("state") if state_el is not None else "unknown",
                    service=svc.get("name") if svc is not None else None,
                    product=svc.get("product") if svc is not None else None,
                    version=svc.get("version") if svc is not None else None,
                    ostype=svc.get("ostype") if svc is not None else None,
                    cpe=cpes,
                    scripts=scripts,
                )
            )

        host_scripts = {
            s.get("id"): (s.get("output") or "").strip()
            for s in host_el.findall("hostscript/script")
            if s.get("id")
        }

        osmatches = []
        for om in host_el.findall("os/osmatch"):
            cls = om.find("osclass")
            osmatches.append({
                "name": om.get("name"),
                "accuracy": int(om.get("accuracy", "0")),
                "family": (cls.get("osfamily") if cls is not None else None),
                "vendor": (cls.get("vendor") if cls is not None else None),
            })

        hosts.append(ParsedHost(
            ip=ip, hostname=hostname, mac=mac, vendor=vendor,
            ports=ports, host_scripts=host_scripts, osmatches=osmatches,
        ))
    return hosts