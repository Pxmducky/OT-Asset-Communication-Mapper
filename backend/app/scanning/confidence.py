"""Clasificación y confianza.

Clave del rediseño: ya NO se puntúa contra el tipo que pidió el usuario, sino
contra TODOS los tipos. El de mayor puntaje gana (clasifica el resultado, no el
botón). El botón solo decide qué puertos abre nmap.

Ignora el <osmatch> basura (NAT/bridge/VoIP) y resuelve el SO desde señales
fiables: smb-os-discovery > ostype/CPE de servicios > osmatch filtrado.
"""
from app.scanning.parser import ParsedHost
from app.scanning.profiles import PROFILES

_BOGUS_OS = {"virtualbox", "slirp", "qemu", "voip adapter", "bridge", "embedded"}

# Umbrales (ajustables)
APPLY_THRESHOLD = 70    # >= : se crea y queda confirmado
REVIEW_THRESHOLD = 40   # >= : va a revisión
SUGGEST_THRESHOLD = 25  # >= : vale la pena recomendar un escaneo específico

# Perfiles que NO son un tipo de activo (son de descubrimiento), se excluyen al clasificar.
_NON_TYPES = {"discovery", "general"}

PROFILE_EXPECTATIONS: dict[str, dict] = {
    "plc":        {"ports": {102, 502, 44818, 2222}, "os": [], "vendor": ["siemens", "rockwell", "allen", "omron", "schneider", "beckhoff", "mitsubishi"], "scripts": ["s7-info", "modbus-discover", "enip-info"], "type": "controller"},
    "hmi":        {"ports": {102, 502, 44818, 5900}, "os": [], "vendor": ["siemens", "rockwell", "pro-face", "omron"], "scripts": ["s7-info", "enip-info", "modbus-discover"], "type": "HMI"},
    "printers":   {"ports": {9100, 515, 631}, "os": [], "vendor": ["hp", "zebra", "epson", "brother", "lexmark"], "scripts": ["snmp-info"], "type": "printer_scanner"},
    "mes":        {"ports": {135, 139, 445, 3389}, "os": ["windows"], "vendor": [], "scripts": ["smb-os-discovery"], "type": "mes"},
    "cnc":        {"ports": {5900, 3389, 8193}, "os": [], "vendor": ["fanuc", "siemens", "haas", "mazak"], "scripts": [], "type": "cnc"},
    "server":     {"ports": {135, 139, 445, 3389, 22}, "os": ["windows", "linux"], "vendor": [], "scripts": ["smb-os-discovery"], "type": "server"},
    "switch":     {"ports": {161, 22, 23}, "os": [], "vendor": ["cisco", "hirschmann", "moxa", "scalance", "siemens"], "scripts": ["snmp-info"], "type": "switch"},
    "drive":      {"ports": {502, 44818}, "os": [], "vendor": ["sew", "danfoss", "abb", "siemens", "rockwell"], "scripts": ["modbus-discover", "enip-info"], "type": "drive"},
    "camera":     {"ports": {554, 37777, 8000}, "os": [], "vendor": ["hikvision", "dahua", "axis", "bosch"], "scripts": ["rtsp-methods"], "type": "camera"},
    "robot":      {"ports": {2222, 44818, 80}, "os": [], "vendor": ["fanuc", "abb", "kuka", "motoman", "yaskawa", "staubli", "kawasaki"], "scripts": ["enip-info", "http-title"], "type": "robot"},
    "io_remote":  {"ports": {102, 502, 44818}, "os": [], "vendor": ["siemens", "beckhoff", "wago", "turck", "phoenix", "murr", "balluff"], "scripts": ["modbus-discover", "enip-info", "s7-info", "snmp-info"], "type": "IO_module"},
    "instrument": {"ports": {502, 9100, 161}, "os": [], "vendor": ["mettler", "toledo", "cognex", "keyence", "sick", "banner", "datalogic"], "scripts": ["snmp-info"], "type": "instrument"},
    "scada":      {"ports": {4840, 135, 1433}, "os": ["windows"], "vendor": ["kepware", "inductive", "wonderware", "aveva", "ge"], "scripts": ["smb-os-discovery"], "type": "scada"},
    "ups":        {"ports": {161}, "os": [], "vendor": ["apc", "eaton", "schneider", "tripp", "vertiv", "cyberpower"], "scripts": ["snmp-info"], "type": "ups"},
    "wap":        {"ports": {161, 443}, "os": [], "vendor": ["cisco", "aruba", "ubiquiti", "moxa", "siemens", "hirschmann"], "scripts": ["snmp-info"], "type": "WAP"},
    "ewon":       {"ports": {80, 443}, "os": [], "vendor": ["ewon", "hms"], "scripts": ["http-title", "ssl-cert"], "type": "ewon"},
    "mguard":     {"ports": {443, 22}, "os": [], "vendor": ["phoenix", "mguard", "innominate"], "scripts": ["ssl-cert", "http-title", "snmp-info"], "type": "mguard"},
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


def _score_against(host: ParsedHost, profile: str) -> tuple[int, list[str]]:
    """Puntúa un host contra UN tipo concreto."""
    exp = PROFILE_EXPECTATIONS.get(profile)
    reasons: list[str] = []
    score = W_UP if host.up else 0
    if not exp:
        return score, reasons

    open_ports = host.open_ports
    blob = _text_blob(host)

    sig = exp["ports"]
    if sig:
        inter = open_ports & sig
        if inter:
            score += round(W_PORTS * len(inter) / len(sig))
            reasons.append(f"puertos del tipo: {sorted(inter)}")

    os_hit = any(k in blob for k in exp["os"])
    vendor_hit = any(k in blob for k in exp["vendor"])
    if os_hit or vendor_hit:
        score += W_IDENTITY
        reasons.append("SO/fabricante esperado")

    if any(host.host_scripts.get(s) or any(p.scripts.get(s) for p in host.ports) for s in exp["scripts"]):
        score += W_SCRIPT
        reasons.append("protocolo confirmado por script")

    if host.mac and vendor_hit:
        score += W_OUI
        reasons.append("MAC de fabricante OT")

    return max(0, min(100, score)), reasons


def score_for_profile(host: ParsedHost, profile: str) -> int:
    """Puntaje del host para el tipo que pidió el usuario (para el Caso 2)."""
    return _score_against(host, profile)[0]


def classify_host(host: ParsedHost) -> dict:
    """Evalúa el host contra TODOS los tipos y devuelve el ganador + ranking."""
    results = []
    for profile, exp in PROFILE_EXPECTATIONS.items():
        sc, reasons = _score_against(host, profile)
        results.append({
            "profile": profile,
            "label": PROFILES.get(profile, {}).get("label", profile),
            "type": exp["type"],
            "score": sc,
            "reasons": reasons,
        })
    results.sort(key=lambda r: -r["score"])
    winner = results[0]
    return {
        "winner": winner["profile"],
        "winner_label": winner["label"],
        "asset_type": winner["type"] if winner["score"] >= REVIEW_THRESHOLD else "unknown",
        "score": winner["score"],
        "os": resolve_os(host),
        "ranking": results[:5],
    }