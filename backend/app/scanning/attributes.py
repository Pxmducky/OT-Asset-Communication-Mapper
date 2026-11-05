"""Datos del equipo que un escaneo puede aportar al inventario.

Cada atributo trae su valor y de dónde salió (fuente auditable). El usuario
los ve en el hallazgo y, si lo aprueba, se guardan en el activo (solo llenan
campos vacíos; nunca sobrescriben).

Campos: mac, hostname, asset_name, vendor, product, os (SO o firmware), serial.
Prioridad por campo: la fuente más directa primero.
"""
import ipaddress
import re

from app.scanning.parser import ParsedHost

LABELS = {
    "mac": "MAC", "hostname": "Hostname", "asset_name": "Nombre", "vendor": "Fabricante",
    "product": "Modelo / producto", "platform": "Plataforma / controlador", "os": "SO / firmware",
    "serial": "Número de serie",
}

# Campos sin columna propia en el activo: se guardan en la descripción
DESCRIPTION_FIELDS = (("platform", "Plataforma"), ("serial", "Serie"))


def _s7_platform(module: str | None, mtype: str | None) -> str | None:
    """Familia S7 a partir del tipo de CPU o del número de pedido."""
    text = f"{mtype or ''} {module or ''}"
    family = None
    cpu = re.search(r"CPU\s?(\d{3,4})", text, re.IGNORECASE)
    order = re.search(r"6ES7\s?(\d)", text, re.IGNORECASE)
    if cpu:
        n = cpu.group(1)
        family = {"3": "S7-300", "4": "S7-400"}.get(n[0]) if len(n) == 3 else \
                 {"12": "S7-1200", "15": "S7-1500"}.get(n[:2])
    elif order:
        family = {"2": "S7-1200", "3": "S7-300", "4": "S7-400", "5": "S7-1500"}.get(order.group(1))
    if not family:
        return None
    out = f"Siemens {family}"
    if re.search(r"CPU\s?\d{3,4}F\b|\bF-CPU\b", text, re.IGNORECASE):
        out += " (CPU de seguridad F)"
    if re.search(r"\b6FC5\b", text, re.IGNORECASE):
        out += " · integrada en SINUMERIK (CNC)"
    return out

_GENERIC_ORGS = re.compile(r"internet widgits|default company|self[- ]?signed|localhost|example|^\s*$", re.I)
_GENERIC_TITLES = re.compile(
    r"unauthori[sz]ed|forbidden|log ?in|sign ?in|index of|welcome|error|not found|redirect|loading|^\s*\d{3}\b", re.I)
_HOSTNAME = re.compile(r"^(?=.*[a-z])[a-z0-9][a-z0-9-]{0,62}(\.[a-z0-9][a-z0-9-]{0,62})*$", re.I)
_MAC_ANY = re.compile(r"\b([0-9a-f]{2})[:\-_ ]?([0-9a-f]{2})[:\-_ ]?([0-9a-f]{2})[:\-_ ]?"
                      r"([0-9a-f]{2})[:\-_ ]?([0-9a-f]{2})[:\-_ ]?([0-9a-f]{2})\b", re.I)


def _scripts(host: ParsedHost) -> dict[str, str]:
    d: dict[str, str] = {}
    for k, v in host.host_scripts.items():
        d[k] = (d.get(k, "") + "\n" + (v or "")).strip()
    for p in host.ports:
        for k, v in p.scripts.items():
            d[k] = (d.get(k, "") + "\n" + (v or "")).strip()
    return d


def _kv(text: str, *keys: str) -> str | None:
    """Valor de 'Clave: valor' (sin importar mayúsculas)."""
    for line in (text or "").splitlines():
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        if k.strip().lower() in keys and v.strip():
            return v.strip()
    return None


def _norm_mac(text: str | None) -> str | None:
    if not text:
        return None
    m = _MAC_ANY.search(text)
    if not m:
        return None
    mac = ":".join(g.lower() for g in m.groups())
    if mac in ("00:00:00:00:00:00", "ff:ff:ff:ff:ff:ff"):
        return None
    return mac


def _is_ip(text: str) -> bool:
    try:
        ipaddress.ip_address(text)
        return True
    except ValueError:
        return False


def _cert_fields(text: str) -> dict[str, str]:
    out = {}
    subject = next((l for l in text.splitlines() if l.strip().lower().startswith("subject:")), "")
    cn = re.search(r"commonName=([^/\n]+)", subject)
    org = re.search(r"organizationName=([^/\n]+)", subject)
    if cn:
        out["cn"] = cn.group(1).strip()
    if org:
        out["org"] = org.group(1).strip()
    return out


def extract_attributes(host: ParsedHost, cls: dict | None = None) -> list[dict]:
    scripts = _scripts(host)
    found: dict[str, list[tuple[str, str]]] = {f: [] for f in LABELS}

    def add(field: str, value: str | None, source: str) -> None:
        value = (value or "").replace("\\x00", "").replace("\x00", "").strip()
        if value and value not in (v for v, _ in found[field]):
            found[field].append((value, source))

    smb = scripts.get("smb-os-discovery", "")
    nbstat = scripts.get("nbstat", "")
    s7 = scripts.get("s7-info", "")
    enip = scripts.get("enip-info", "")
    cert = _cert_fields(scripts.get("ssl-cert", ""))
    snmp_if = scripts.get("snmp-interfaces", "")
    snmp_desc = scripts.get("snmp-sysdescr", "")

    # --- MAC ---
    add("mac", _norm_mac(host.mac), "nmap (capa 2 / ARP)")
    nb_mac = re.search(r"NetBIOS MAC:\s*([0-9a-f:]{17})", nbstat, re.I)
    add("mac", _norm_mac(nb_mac.group(1)) if nb_mac else None, "NetBIOS (nbstat)")
    if_mac = re.search(r"MAC address:\s*([0-9a-f:]{17})", snmp_if, re.I)
    add("mac", _norm_mac(if_mac.group(1)) if if_mac else None, "SNMP (interfaces)")
    if cert.get("cn") and _MAC_ANY.fullmatch(cert["cn"].strip()):
        add("mac", _norm_mac(cert["cn"]), "certificado (commonName)")

    # --- Hostname ---
    if host.hostname and not _is_ip(host.hostname):
        add("hostname", host.hostname, "DNS inverso")
    add("hostname", _kv(smb, "fqdn"), "SMB (FQDN)")
    add("hostname", _kv(smb, "computer name"), "SMB (nombre de equipo)")
    add("hostname", _kv(smb, "netbios computer name"), "SMB (NetBIOS)")
    nb_name = re.search(r"NetBIOS name:\s*([^,\s]+)", nbstat, re.I)
    add("hostname", nb_name.group(1) if nb_name else None, "NetBIOS (nbstat)")
    # Nombre configurado en el propio equipo (TIA/STEP 7, EtherNet/IP)
    add("hostname", _kv(s7, "system name"), "s7-info (System Name)")
    add("hostname", _kv(enip, "device name"), "enip-info (Device Name)")
    cn = cert.get("cn")
    if cn and _HOSTNAME.match(cn) and not _MAC_ANY.fullmatch(cn) and cn != cert.get("org") and " " not in cn:
        add("hostname", cn, "certificado (commonName)")

    # --- Nombre del equipo (identificación del proyecto/estación) ---
    add("asset_name", _kv(s7, "system name"), "s7-info (System Name)")
    add("asset_name", _kv(s7, "plant identification"), "s7-info (Plant Identification)")
    add("asset_name", _kv(enip, "device name"), "enip-info")

    # --- Fabricante ---
    add("vendor", host.vendor, "OUI de la MAC")
    add("vendor", _kv(enip, "vendor"), "enip-info")
    if s7.strip() and _kv(s7, "module", "basic hardware"):
        add("vendor", "Siemens", "s7-info")
    if cert.get("org") and not _GENERIC_ORGS.search(cert["org"]):
        add("vendor", cert["org"], "certificado (organizationName)")

    # --- Modelo / producto (del equipo, no del servidor web) ---
    module = _kv(s7, "module")
    hw = _kv(s7, "basic hardware")
    mtype = _kv(s7, "module type")
    if module or hw:
        add("product", " · ".join(x for x in (mtype, module or hw) if x), "s7-info")
    add("platform", _s7_platform(module or hw, mtype), "s7-info")
    add("product", _kv(enip, "product name"), "enip-info")
    if snmp_desc.strip():
        add("product", snmp_desc.strip().splitlines()[0][:120], "SNMP (sysDescr)")
    if cls:
        ident = next((f for f in cls.get("fingerprints", []) if f.get("kind") == "identity"), None)
        title = scripts.get("http-title", "").strip().splitlines()[0] if scripts.get("http-title") else ""
        if ident and ident.get("source") == "http-title" and title and not _GENERIC_TITLES.search(title):
            add("product", title[:120], "http-title")

    # --- SO / firmware ---
    if cls and cls.get("os"):
        add("os", cls["os"], "detección de SO")
    fw = _kv(s7, "version", "basic firmware")
    add("os", f"Firmware {fw}" if fw else None, "s7-info")
    rev = _kv(enip, "revision")
    add("os", f"Firmware {rev}" if rev else None, "enip-info")

    # --- Número de serie ---
    add("serial", _kv(s7, "serial number"), "s7-info")
    add("serial", _kv(enip, "serial number"), "enip-info")

    out = []
    for field, values in found.items():
        if not values:
            continue
        value, source = values[0]
        out.append({
            "field": field, "label": LABELS[field], "value": value, "source": source,
            "alternatives": [{"value": v, "source": s} for v, s in values[1:]],
        })
    return out


def as_dict(attributes: list[dict] | None) -> dict[str, str]:
    return {a["field"]: a["value"] for a in (attributes or [])}