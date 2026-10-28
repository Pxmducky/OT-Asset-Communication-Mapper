"""Clasificador por evidencias en niveles, con propiedad clara de la evidencia.

Jerarquía: identificación explícita (NSE/banner/cert) > protocolo OT > servicio
genérico > OS. El protocolo de CONTROL industrial (s7/enip/modbus confirmado por
NSE) es dueño del tipo PLC y gana sobre firewall/acceso remoto/servicios IT.
Separa el TIPO del activo de sus SERVICIOS/fingerprints, y no suma evidencia
duplicada (agrupa por 'group' y toma el máximo).
"""
from app.scanning.parser import ParsedHost
from app.scanning.profiles import PROFILES

APPLY_THRESHOLD = 70
REVIEW_THRESHOLD = 40
SUGGEST_THRESHOLD = 25

TYPE_SLUG = {
    "plc": "controller", "hmi": "HMI", "printers": "printer_scanner", "mes": "mes",
    "cnc": "cnc", "server": "server", "switch": "switch", "drive": "drive",
    "camera": "camera", "robot": "robot", "io_remote": "IO_module",
    "instrument": "instrument", "scada": "scada", "ups": "ups", "wap": "WAP",
    "ewon": "ewon", "mguard": "mguard",
}

# Tipos de control: ante empate, estos ganan el tipo (regla 6 del usuario).
_CONTROL_TYPES = {"plc", "hmi", "drive", "io_remote", "cnc", "robot", "scada"}

_BOGUS_OS = {"virtualbox", "slirp", "qemu", "voip adapter", "bridge", "embedded"}

# Identificaciones por texto (banner/cert/producto): (keywords, types, weight, group, label, is_service)
_TEXT_IDS = [
    (("mguard", "phoenix contact", "phoenix-contact", "innominate"), ("mguard",), 80, "mguard", "mGuard (Phoenix Contact)", True),
    (("wincc", "simatic hmi", "comfort panel", "unified panel", "operator panel", "ktp", "tp700", "tp900"), ("hmi",), 80, "hmi_id", "HMI Siemens (WinCC/Panel)", False),
    (("jetdirect", "laserjet", "ipp", "cups", "kyocera", "lexmark", "ricoh", "xerox", "zebra", "printer"), ("printers",), 78, "printer_id", "Impresora", False),
    (("hikvision", "dahua", "axis communications", "hanwha", "pelco", "ip camera", "nvr", "dvr"), ("camera",), 78, "camera_id", "Cámara IP", False),
    (("fanuc", "kuka", "motoman", "yaskawa", "staubli", "abb robot", "irc5", "r-30i"), ("robot",), 78, "robot_id", "Robot", False),
    (("sinumerik", "heidenhain", "mazak", "okuma", "haas"), ("cnc",), 78, "cnc_id", "CNC", False),
    (("ewon", "talk2m", "hms networks", "flexy", "cosy"), ("ewon",), 82, "ewon_id", "Ewon / HMS", True),
    (("sinamics", "powerflex", "altivar", "danfoss", "sew-eurodrive", "frequency converter", "variable frequency"), ("drive",), 76, "drive_id", "Variador / Drive", False),
    (("cisco", "catalyst", "aruba", "hirschmann", "moxa", "scalance", "juniper", "fortinet", "managed switch", "ethernet switch"), ("switch",), 58, "switch_id", "Switch gestionado", False),
    (("apc ", "eaton", "vertiv", "cyberpower", "uninterruptible power", "power distribution", "pdu"), ("ups",), 76, "ups_id", "UPS / PDU", False),
    (("aironet", "ubiquiti", "ruckus", "access point", "wireless lan", "wlan"), ("wap",), 70, "wap_id", "Access Point", False),
    (("microsoft sql server", "mssql"), ("mes", "server", "scada"), 45, "mssql", "Microsoft SQL Server", True),
    (("historian", "osisoft", "pi server", "wonderware", "aveva", "factorytalk", "ignition", "opc ua", "opc server", "kepware"), ("scada",), 60, "scada_id", "SCADA / OPC", False),
    (("windows server", "microsoft windows"), ("mes", "server", "scada"), 38, "windows", "Windows", False),
]

# Protocolo OT por puerto abierto (nivel 2, medio): (port, transport, types, label, group)
_OT_PORTS = [
    (102, "tcp", ("plc", "hmi", "io_remote"), "ISO-TSAP/S7", "s7"),
    (502, "tcp", ("plc", "drive", "io_remote", "instrument"), "Modbus", "modbus"),
    (44818, "tcp", ("plc", "drive", "robot", "io_remote"), "EtherNet/IP", "enip"),
    (2222, "tcp", ("plc", "robot", "io_remote"), "EtherNet/IP I/O", "enip"),
    (4840, "tcp", ("scada",), "OPC UA", "opcua"),
    (20000, "tcp", ("plc",), "DNP3", "dnp3"),
    (9100, "tcp", ("printers",), "JetDirect", "print_proto"),
    (515, "tcp", ("printers",), "LPD", "print_proto"),
    (631, "tcp", ("printers",), "IPP", "print_proto"),
    (554, "tcp", ("camera",), "RTSP", "rtsp"),
    (1194, "tcp", ("ewon",), "OpenVPN", "vpn"),
    (161, "udp", ("switch", "ups", "wap", "printers", "drive", "instrument"), "SNMP", "snmp"),
    (47808, "udp", ("instrument",), "BACnet", "bacnet"),
    (1433, "tcp", ("mes", "server", "scada"), "MSSQL", "db"),
    (3306, "tcp", ("mes", "server"), "MySQL", "db"),
    (445, "tcp", ("mes", "server", "scada"), "SMB", "smb"),
    (135, "tcp", ("mes", "server", "scada"), "MSRPC", "smb"),
    (37777, "tcp", ("camera",), "Dahua", "cam_proto"),
]

# Servicios genéricos (nivel 3, débil): (port, transport, types, label)
_GENERIC_PORTS = [
    (80, "tcp", ("plc", "hmi", "printers", "camera", "drive", "ups", "wap", "ewon", "mguard", "scada", "instrument", "robot", "io_remote"), "HTTP"),
    (443, "tcp", ("plc", "hmi", "printers", "camera", "drive", "ups", "wap", "ewon", "mguard", "scada", "instrument", "robot", "io_remote"), "HTTPS"),
    (22, "tcp", ("switch", "server", "wap", "mguard", "ewon"), "SSH"),
    (23, "tcp", ("switch", "cnc", "instrument", "wap", "printers"), "Telnet"),
    (3389, "tcp", ("mes", "server", "scada", "cnc", "hmi", "robot"), "RDP"),
    (5900, "tcp", ("hmi", "cnc", "robot"), "VNC"),
]

_SERVICE_PORTS = {80: "HTTP", 443: "HTTPS", 22: "SSH", 23: "Telnet", 3389: "RDP", 5900: "VNC"}


def _scripts_by_id(host: ParsedHost) -> dict:
    d: dict[str, str] = {}
    for k, v in host.host_scripts.items():
        d[k] = (d.get(k, "") + " " + (v or "")).strip()
    for p in host.ports:
        for k, v in p.scripts.items():
            d[k] = (d.get(k, "") + " " + (v or "")).strip()
    return d


def _blob(host: ParsedHost, scripts: dict) -> str:
    parts = [host.vendor or ""]
    for p in host.ports:
        parts += [p.service or "", p.product or "", p.ostype or "", *(p.cpe or [])]
    parts += list(scripts.values())
    return " ".join(parts).lower()


def resolve_os(host: ParsedHost) -> str | None:
    smb = host.host_scripts.get("smb-os-discovery", "")
    for line in smb.splitlines():
        if line.strip().lower().startswith("os:"):
            return line.split(":", 1)[1].strip()
    scripts = _scripts_by_id(host)
    blob = _blob(host, scripts)
    if "microsoft:windows" in blob or "windows" in blob:
        return "Windows"
    if "linux" in blob:
        return "Linux"
    for om in sorted(host.osmatches, key=lambda m: -m["accuracy"]):
        fam = (om.get("family") or "").lower()
        if fam and not any(b in fam for b in _BOGUS_OS) and not any(b in (om["name"] or "").lower() for b in _BOGUS_OS):
            return om["name"]
    return None


def _parse_s7(text: str) -> str | None:
    bits = []
    for line in text.splitlines():
        low = line.lower()
        if any(k in low for k in ("module type", "system name", "module:", "basic firmware", "version", "basic hardware")):
            bits.append(line.strip())
    return "; ".join(bits) if bits else None


def collect_evidence(host: ParsedHost) -> list[dict]:
    scripts = _scripts_by_id(host)
    blob = _blob(host, scripts)
    open_ports = {(p.port, p.transport) for p in host.ports if p.state == "open"}
    ev: list[dict] = []

    def add(level, group, label, weights, is_service=False, detail=None, port=None, transport=None, source=None):
        ev.append({"level": level, "group": group, "label": label, "weights": weights,
                   "is_service": is_service, "detail": detail, "port": port,
                   "transport": transport, "source": source})

    # --- Nivel 1: identificación explícita (NSE de control) — el PLC es dueño ---
    s7 = scripts.get("s7-info", "")
    if s7.strip():
        detail = _parse_s7(s7)
        if detail:
            add("strong", "s7", f"s7-info: {detail}", {"plc": 95, "io_remote": 25, "hmi": 18},
                detail=detail, port=102, source="s7-info")
        else:
            add("strong", "s7", "s7-info (dispositivo S7)", {"plc": 72, "io_remote": 22, "hmi": 18},
                port=102, source="s7-info")
    if scripts.get("enip-info", "").strip():
        add("strong", "enip", "enip-info (EtherNet/IP · CIP)", {"plc": 72, "drive": 42, "robot": 42, "io_remote": 35}, source="enip-info")
    if scripts.get("modbus-discover", "").strip():
        add("strong", "modbus", "modbus-discover (Modbus)", {"plc": 68, "drive": 45, "io_remote": 35, "instrument": 30}, source="modbus-discover")
    if scripts.get("rtsp-methods", "").strip() or (554, "tcp") in open_ports:
        add("strong", "rtsp", "RTSP (cámara)", {"camera": 82}, port=554, source="rtsp-methods")
    if (161, "udp") in open_ports or scripts.get("snmp-info", "").strip():
        add("strong", "snmp", "SNMP (snmp-info)", {"switch": 52, "ups": 52, "wap": 48, "printers": 40, "drive": 30, "instrument": 30}, port=161, transport="udp", source="snmp-info")

    # identificaciones por texto (banner/cert/producto)
    for keywords, types, weight, group, label, is_service in _TEXT_IDS:
        if any(k in blob for k in keywords):
            add("strong", group, label, {t: weight for t in types}, is_service=is_service, source="banner/cert")

    # --- Nivel 2: protocolo OT (puerto abierto) ---
    for port, transport, types, label, group in _OT_PORTS:
        if (port, transport) in open_ports:
            add("medium", group, f"{port}/{transport} · {label}", {t: 22 for t in types}, port=port, transport=transport)

    # --- Nivel 3: servicios genéricos ---
    for port, transport, types, label in _GENERIC_PORTS:
        if (port, transport) in open_ports:
            add("weak", f"svc{port}", f"{port}/{transport} · {label}", {t: 7 for t in types}, port=port, transport=transport)

    # --- Nivel 4: OS (casi nulo) ---
    os_name = resolve_os(host)
    if os_name and "windows" in os_name.lower():
        add("os", "os", f"OS: {os_name}", {"mes": 2, "server": 2, "scada": 2})

    return ev


def _fingerprints_from(ev: list[dict], host: ParsedHost, winner: str | None) -> list[dict]:
    out, seen = [], set()

    def push(kind, label, detail=None, port=None, transport=None, source=None):
        if label in seen:
            return
        seen.add(label)
        out.append({"kind": kind, "label": label, "detail": detail, "port": port, "transport": transport, "source": source})

    # Identidad del tipo ganador (su evidencia fuerte de mayor peso)
    if winner:
        best = None
        for e in ev:
            if e["level"] == "strong" and not e["is_service"] and winner in e["weights"]:
                if best is None or e["weights"][winner] > best["weights"][winner]:
                    best = e
        if best:
            push("identity", best["label"], best.get("detail"), best.get("port"), best.get("transport"), best.get("source"))

    # Otros servicios/fingerprints: identificaciones de servicio, o fuertes de OTRO tipo
    for e in ev:
        if e["level"] == "strong" and (e["is_service"] or (winner and winner not in e["weights"])):
            push("service", e["label"], e.get("detail"), e.get("port"), e.get("transport"), e.get("source"))

    # Servicios de administración (RDP/HTTPS/SSH/VNC…)
    for p in host.ports:
        if p.state == "open" and p.port in _SERVICE_PORTS:
            label = f"{_SERVICE_PORTS[p.port]} ({p.product})" if p.product else _SERVICE_PORTS[p.port]
            push("service", label, port=p.port, transport=p.transport, source="service")
    return out


def classify_host(host: ParsedHost) -> dict:
    ev = collect_evidence(host)

    # Agrupa por tipo y group (no suma evidencia duplicada: toma el máximo por group)
    groups: dict[str, dict] = {}
    for e in ev:
        for t, w in e["weights"].items():
            g = groups.setdefault(t, {})
            if w > g.get(e["group"], 0):
                g[e["group"]] = w
    scores = {t: min(100, sum(g.values())) for t, g in groups.items()}

    # Ranking: por puntaje; ante empate, los tipos de control ganan
    ranking = sorted(
        ({"profile": t, "label": PROFILES.get(t, {}).get("label", t), "type": TYPE_SLUG.get(t, t), "score": s}
         for t, s in scores.items()),
        key=lambda r: (-r["score"], 0 if r["profile"] in _CONTROL_TYPES else 1),
    )[:5]

    winner = ranking[0]["profile"] if ranking and ranking[0]["score"] > 0 else None
    winner_score = ranking[0]["score"] if winner else 0
    winner_label = ranking[0]["label"] if winner else "Desconocido"

    evidences = sorted(
        ({"level": e["level"], "label": e["label"], "points": e["weights"].get(winner, 0)}
         for e in ev if winner and winner in e["weights"]),
        key=lambda x: -x["points"],
    )[:8]

    fingerprints = _fingerprints_from(ev, host, winner)

    return {
        "winner": winner,
        "winner_label": winner_label,
        "asset_type": TYPE_SLUG.get(winner, "unknown") if winner_score >= REVIEW_THRESHOLD else "unknown",
        "score": winner_score,
        "os": resolve_os(host),
        "scores": scores,
        "ranking": ranking,
        "evidences": evidences,
        "fingerprints": fingerprints,
    }