"""Porcentaje de confianza por host, según el tipo de escaneo pedido.

Mide qué tan bien coincide el host con el TIPO esperado. Ignora el <osmatch>
basura (NAT/bridge/VoIP/virtualización) y resuelve el SO desde señales fiables:
smb-os-discovery > ostype/CPE de servicios > osmatch filtrado.
"""
from app.scanning.parser import ParsedHost

# Familias de <osmatch> que NO son el equipo real (gateways intermedios)
_BOGUS_OS = {"virtualbox", "slirp", "qemu", "voip adapter", "bridge", "embedded"}

# Umbrales (ajustables)
APPLY_THRESHOLD = 70   # >= : se aplica solo y queda confirmado
REVIEW_THRESHOLD = 40  # >= : va a bandeja de revisión; por debajo, se guarda sin aplicar

# Expectativas por perfil: puertos "firma", palabras de SO/fabricante y scripts esperados.
PROFILE_EXPECTATIONS: dict[str, dict] = {
    "plc":       {"ports": {102, 502, 44818, 2222}, "os": [], "vendor": ["siemens", "rockwell", "allen", "omron", "schneider", "beckhoff", "mitsubishi"], "scripts": ["s7-info", "modbus-discover", "enip-info"], "type": "PLC"},
    "hmi":       {"ports": {102, 502, 44818, 5900}, "os": [], "vendor": ["siemens", "rockwell", "pro-face", "omron"], "scripts": ["s7-info", "enip-info", "modbus-discover"], "type": "HMI"},
    "printers":  {"ports": {9100, 515, 631}, "os": [], "vendor": ["hp", "zebra", "epson", "brother", "lexmark"], "scripts": ["snmp-info"], "type": "Impresora"},
    "mes":       {"ports": {135, 139, 445, 3389}, "os": ["windows"], "vendor": [], "scripts": ["smb-os-discovery"], "type": "MES"},
    "cnc":       {"ports": {5900, 3389, 8193}, "os": [], "vendor": ["fanuc", "siemens", "haas", "mazak"], "scripts": [], "type": "CNC"},
    "server":    {"ports": {135, 139, 445, 3389, 22}, "os": ["windows", "linux"], "vendor": [], "scripts": ["smb-os-discovery"], "type": "Servidor"},
    "switch":    {"ports": {161, 22, 23}, "os": [], "vendor": ["cisco", "hirschmann", "moxa", "scalance", "siemens"], "scripts": ["snmp-info"], "type": "Switch"},
    "drive":     {"ports": {502, 44818}, "os": [], "vendor": ["sew", "danfoss", "abb", "siemens", "rockwell"], "scripts": ["modbus-discover", "enip-info"], "type": "Variador"},
    "camera":    {"ports": {554, 37777, 8000}, "os": [], "vendor": ["hikvision", "dahua", "axis", "bosch"], "scripts": ["rtsp-methods"], "type": "Cámara IP"},
    "discovery": {"ports": set(), "os": [], "vendor": [], "scripts": [], "type": "Desconocido"},
}

W_UP, W_PORTS, W_IDENTITY, W_SCRIPT, W_OUI = 15, 35, 30, 20, 10


def _text_blob(host: ParsedHost) -> str:
    parts: list[str] = [host.vendor or ""]
    for p in host.ports:
        parts += [p.service or "", p.product or "", p.ostype or "", *(p.cpe or [])]
    parts += list(host.host_scripts.values())
    return " ".join(parts).lower()


def resolve_os(host: ParsedHost) -> str | None:
    smb = host.host_scripts.get("smb-os-discovery", "")
    for line in smb.splitlines():
        if line.strip().lower().startswith("os:"):
            return line.split(":", 1)[1].strip()
    blob = _text_blob(host)
    if "microsoft:windows" in blob or "windows" in blob:
        return "Windows"
    if "linux" in blob:
        return "Linux"
    for om in sorted(host.osmatches, key=lambda m: -m["accuracy"]):
        fam = (om.get("family") or "").lower()
        if fam and not any(b in fam for b in _BOGUS_OS) and not any(b in (om["name"] or "").lower() for b in _BOGUS_OS):
            return om["name"]
    return None


def score_host(host: ParsedHost, scan_profile: str) -> dict:
    exp = PROFILE_EXPECTATIONS.get(scan_profile, PROFILE_EXPECTATIONS["discovery"])
    reasons: list[str] = []
    score = 0

    if host.up:
        score += W_UP
        reasons.append("host activo")

    # discovery: solo liveness, nunca auto-confirma
    if scan_profile == "discovery":
        return {"score": min(score + 25, REVIEW_THRESHOLD + 5), "os": resolve_os(host),
                "asset_type": exp["type"], "reasons": reasons + ["descubrimiento (sin clasificar)"]}

    open_ports = host.open_ports
    blob = _text_blob(host)

    sig = exp["ports"]
    if sig:
        frac = len(open_ports & sig) / len(sig)
        score += round(W_PORTS * frac)
        if frac:
            reasons.append(f"puertos del tipo: {sorted(open_ports & sig)}")

    os_hit = any(k in blob for k in exp["os"])
    vendor_hit = any(k in blob for k in exp["vendor"])
    if os_hit or vendor_hit:
        score += W_IDENTITY
        reasons.append("SO/fabricante esperado" if os_hit else "fabricante esperado")

    script_hit = any(host.host_scripts.get(s) or any(p.scripts.get(s) for p in host.ports) for s in exp["scripts"])
    if script_hit:
        score += W_SCRIPT
        reasons.append("protocolo confirmado por script")

    if host.mac and vendor_hit:
        score += W_OUI
        reasons.append("MAC de fabricante OT")

    score = max(0, min(100, score))
    if sig and not (open_ports & sig):
        reasons.append("⚠ no coincide con el tipo pedido")
    return {"score": score, "os": resolve_os(host), "asset_type": exp["type"], "reasons": reasons}