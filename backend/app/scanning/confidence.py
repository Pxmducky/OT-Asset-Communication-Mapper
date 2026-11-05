"""Clasificador V2: identidad del activo vs. señales de servicio.

Principios (V2):
  1. Una IDENTIFICACIÓN EXPLÍCITA del activo (s7-info con módulo, enip-info con
     Device Type, texto de producto en banner/título/cert/SNMP) no compite en
     igualdad con una SEÑAL (puerto abierto, protocolo que respondió sin datos).
  2. Niveles de identidad: control (NSE OT con datos) > producto (texto) > señal.
     Un PLC identificado por s7-info gana sobre un encabezado HTTPS de firewall.
  3. Las señales solas tienen tope (SIGNAL_CAP < APPLY_THRESHOLD): un puerto de
     impresión, el 102 o SNMP abierto NUNCA confirman un tipo por sí solos.
  4. SNMP abierto es evidencia de administración; solo el CONTENIDO de su
     respuesta (fabricante/modelo/descripción) puede identificar el equipo.
  5. Coincidencias de texto por palabra completa y por fuente; nada de buscar
     subcadenas en todo el resultado ('ipp' solo cuenta como servicio en 631).
  6. Productos ambiguos (factorytalk, wincc, mssql…) son servicios o pesos bajos
     repartidos, no definen el tipo.
  7. Si dos tipos tienen identidad fuerte y contradictoria → 'requiere revisión'
     (asset_type='unknown', puntuación por debajo del umbral de aplicación).
  8. 'score' es una PUNTUACIÓN de reglas (0–100), no una probabilidad calibrada.
"""
import re
from datetime import datetime, timezone

from app.scanning.attributes import extract_attributes
from app.scanning.parser import ParsedHost
from app.scanning.profiles import PROFILES

APPLY_THRESHOLD = 70
REVIEW_THRESHOLD = 40
SUGGEST_THRESHOLD = 25

SIGNAL_CAP = 55          # máximo que pueden sumar señales sin identidad
STRONG_ID = 70           # identidad considerada fuerte (para conflictos)

TYPE_SLUG = {
    "plc": "controller", "hmi": "HMI", "printers": "printer_scanner", "mes": "mes",
    "cnc": "cnc", "server": "server", "switch": "switch", "drive": "drive",
    "camera": "camera", "robot": "robot", "io_remote": "IO_module",
    "instrument": "instrument", "scada": "scada", "ups": "ups", "wap": "WAP",
    "ewon": "ewon", "mguard": "mguard", "insys": "insys",
}

_CONTROL_TYPES = {"plc", "hmi", "drive", "io_remote", "cnc", "robot", "scada"}
_BOGUS_OS = {"virtualbox", "slirp", "qemu", "voip adapter", "bridge", "embedded"}

_LEVEL_RANK = {"control": 3, "product": 2, "signal": 1, "os": 0}

# Fuentes de texto y cuánto valen como identidad (1.0 = identidad plena).
# La OUI de la MAC solo aporta como señal.
_SOURCE_FACTOR = {
    "product": 1.0, "http-title": 1.0, "ssl-cert": 1.0, "banner": 0.9,
    "snmp": 1.0, "http-headers": 0.8, "smb": 0.9, "oui": 0.3,
}

# ---------------------------------------------------------------------------
# Reglas de texto: (patrones, {tipo: peso}, group, etiqueta, can_be_service)
#   can_be_service=True → si otro tipo gana con identidad de mayor nivel, esta
#   evidencia se guarda como servicio/fingerprint y NO genera conflicto.
# Los patrones son regex evaluados con límites de palabra.
# ---------------------------------------------------------------------------
_TEXT_RULES = [
    # HMI: paneles y runtimes específicos
    ((r"simatic hmi", r"comfort panel", r"unified comfort", r"basic panel", r"mobile panel",
      r"ktp\s?\d{3,4}", r"tp\s?\d{3,4}", r"mp\s?\d{3}", r"panelview", r"factorytalk view me",
      r"factorytalk view machine edition", r"pro-?face", r"gp-pro", r"weintek", r"easyview",
      r"beijer", r"ix runtime", r"ix panel", r"operator panel", r"movicon", r"intouch machine edition",
      r"wincc runtime advanced", r"wincc rt advanced", r"sm@rtserver"),
     {"hmi": 85}, "hmi_id", "Panel / Runtime HMI", False),
    # La palabra HMI en título/producto/cert es identidad razonable, no plena
    ((r"siemens hmi", r"hmi"), {"hmi": 72}, "hmi_word", "Texto 'HMI'", False),
    # WinCC genérico: puede ser panel o SCADA → peso bajo repartido
    ((r"wincc", r"wincc unified"), {"hmi": 45, "scada": 45}, "wincc", "Siemens WinCC", True),
    # FactoryTalk View SE: más SCADA que HMI
    ((r"factorytalk view se", r"factorytalk view site edition"), {"scada": 55, "hmi": 35},
     "ftview_se", "FactoryTalk View SE", True),
    # FactoryTalk genérico: solo servicio
    ((r"factorytalk", r"rslinx"), {}, "factorytalk", "Rockwell FactoryTalk", True),
    # Impresoras: fabricante / producto de impresión (NO puertos)
    ((r"jetdirect", r"laserjet", r"officejet", r"pagewide", r"kyocera", r"ecosys", r"lexmark",
      r"ricoh", r"xerox", r"workcentre", r"zebra", r"zt\d{3}", r"brother", r"epson", r"canon",
      r"imagerunner", r"sharp mx", r"konica", r"bizhub", r"printer", r"impresora", r"print server"),
     {"printers": 80}, "printer_id", "Impresora", False),
    ((r"cups",), {"printers": 30}, "cups", "CUPS", True),
    # Cámaras
    ((r"hikvision", r"dahua", r"axis communications", r"hanwha", r"pelco", r"ip camera",
      r"network camera", r"nvr", r"dvr"),
     {"camera": 80}, "camera_id", "Cámara IP", False),
    # Robots
    ((r"fanuc", r"kuka", r"motoman", r"yaskawa", r"staubli", r"abb robot", r"irc5",
      r"omnicore", r"r-30i\w*"),
     {"robot": 80}, "robot_id", "Robot", False),
    # CNC
    ((r"sinumerik", r"heidenhain", r"mazak", r"okuma", r"haas", r"fanuc series"),
     {"cnc": 80}, "cnc_id", "CNC", False),
    # lshd: servidor SSH embebido típico de NCU SINUMERIK (apoyo, no identidad)
    ((r"lshd",), {"cnc": 25}, "lshd", "SSH lshd (embebido)", True),
    # Acceso remoto / seguridad perimetral
    ((r"ewon", r"talk2m", r"flexy", r"cosy"), {"ewon": 82}, "ewon_id", "Ewon / HMS", True),
    ((r"insys", r"insys microelectronics", r"insys-tec", r"insys icom", r"icom os", r"mro-l\d+",
      r"mrx\d*", r"ebw-\w+"),
     {"insys": 88}, "insys_id", "INSYS (gateway de acceso remoto)", False),
    ((r"mguard", r"innominate"), {"mguard": 80}, "mguard_id", "mGuard (Phoenix Contact)", True),
    # Variadores
    ((r"sinamics", r"powerflex", r"altivar", r"danfoss", r"sew-eurodrive", r"movidrive",
      r"frequency converter", r"variable frequency drive"),
     {"drive": 80}, "drive_id", "Variador / Drive", False),
    # Red
    ((r"catalyst", r"cisco ios", r"aruba", r"hirschmann", r"moxa", r"scalance [xw]\w*",
      r"stratix", r"juniper", r"managed switch", r"ethernet switch"),
     {"switch": 70}, "switch_id", "Switch gestionado", True),
    ((r"fortinet", r"fortigate", r"palo alto"), {}, "firewall", "Firewall", True),
    ((r"aironet", r"ubiquiti", r"unifi", r"ruckus", r"access point", r"wireless lan controller"),
     {"wap": 75}, "wap_id", "Access Point", False),
    # Energía
    ((r"apc", r"smart-ups", r"eaton", r"vertiv", r"liebert", r"cyberpower",
      r"uninterruptible power", r"\bpdu\b"),
     {"ups": 78}, "ups_id", "UPS / PDU", False),
    # SCADA / Historian / OPC (servicios de servidor)
    ((r"historian", r"osisoft", r"pi server", r"wonderware", r"aveva", r"ignition",
      r"kepware", r"kepserverex"),
     {"scada": 60, "server": 30}, "scada_id", "SCADA / Historian / OPC", True),
    ((r"opc ua", r"opc server"), {}, "opc", "Servidor OPC", True),
    # Bases de datos / SO: solo servicio
    ((r"microsoft sql server", r"mssql"), {"mes": 10, "server": 10, "scada": 10},
     "mssql", "Microsoft SQL Server", True),
]

_COMPILED = [
    (re.compile(r"\b(?:" + "|".join(p) + r")\b", re.IGNORECASE), w, g, lbl, svc)
    for p, w, g, lbl, svc in _TEXT_RULES
]

# Señales por puerto abierto (nunca confirman solas): (port, transport, {tipo: peso}, label, group)
_PORT_SIGNALS = [
    (102, "tcp", {"plc": 20, "hmi": 20, "io_remote": 15}, "ISO-TSAP/S7", "s7"),
    (502, "tcp", {"plc": 20, "drive": 15, "io_remote": 15, "instrument": 15}, "Modbus", "modbus"),
    (44818, "tcp", {"plc": 20, "drive": 15, "robot": 15, "io_remote": 15, "hmi": 10}, "EtherNet/IP", "enip"),
    (2222, "tcp", {"plc": 15, "robot": 15, "io_remote": 15}, "EtherNet/IP I/O", "enip_io"),
    (4840, "tcp", {"scada": 20, "hmi": 10, "server": 10}, "OPC UA", "opcua"),
    (20000, "tcp", {"plc": 15}, "DNP3", "dnp3"),
    (9100, "tcp", {"printers": 25, "instrument": 10}, "JetDirect/RAW", "print"),
    (515, "tcp", {"printers": 25}, "LPD", "print"),
    (554, "tcp", {"camera": 35}, "RTSP", "rtsp"),
    (37777, "tcp", {"camera": 35}, "Dahua", "rtsp"),
    (1194, "tcp", {"ewon": 25}, "OpenVPN", "vpn"),
    (47808, "udp", {"instrument": 15}, "BACnet", "bacnet"),
    (1433, "tcp", {"mes": 12, "server": 12, "scada": 12}, "MSSQL", "db"),
    (3306, "tcp", {"mes": 12, "server": 12}, "MySQL", "db"),
    (445, "tcp", {"mes": 10, "server": 10, "scada": 10, "hmi": 5}, "SMB", "smb"),
    (135, "tcp", {"mes": 8, "server": 8, "scada": 8, "hmi": 5}, "MSRPC", "smb"),
    (5985, "tcp", {"server": 8, "mes": 8, "scada": 8}, "WinRM", "winrm"),
]

# Servicios genéricos (muy débiles)
_GENERIC_PORTS = [
    (80, "tcp", 5, "HTTP"), (443, "tcp", 5, "HTTPS"), (22, "tcp", 3, "SSH"),
    (23, "tcp", 3, "Telnet"), (3389, "tcp", 5, "RDP"), (5900, "tcp", 8, "VNC"),
]
_GENERIC_TYPES = {
    80: ("plc", "hmi", "printers", "camera", "drive", "ups", "wap", "ewon", "mguard", "instrument", "robot", "io_remote"),
    443: ("plc", "hmi", "printers", "camera", "drive", "ups", "wap", "ewon", "mguard", "instrument", "robot", "io_remote"),
    22: ("switch", "server", "wap", "mguard", "ewon"),
    23: ("switch", "cnc", "instrument", "wap"),
    3389: ("mes", "server", "scada", "cnc", "hmi", "robot"),
    5900: ("hmi", "cnc", "robot"),
}

_SERVICE_PORTS = {80: "HTTP", 443: "HTTPS", 22: "SSH", 23: "Telnet", 3389: "RDP", 5900: "VNC"}

# enip-info "Device Type" → tipo
_ENIP_DEVICE_TYPES = [
    (("programmable logic controller",), {"plc": 92}),
    (("human-machine interface", "human machine interface", "operator interface"), {"hmi": 92}),
    (("ac drive", "dc drive", "motion control", "servo drive"), {"drive": 88}),
    (("communications adapter", "communication adapter", "generic device"), {"io_remote": 70}),
    (("robot",), {"robot": 88}),
]

_HMI_IN_S7 = re.compile(r"\b(?:hmi|ktp\s?\d+|tp\s?\d{3,4}|mp\s?\d{3}|comfort|panel|wincc)\b", re.IGNORECASE)
# CPU S7 integrada en un control numérico (SINUMERIK): no es un PLC convencional
_CNC_IN_S7 = re.compile(
    r"\b6FC5\b|\bsinumerik\b|\bncu\s?\d{3}\b|\b(?:840|828|802)\s?d(?:sl)?\b|\bppu\s?\d+\b"
    r"|^\s*system name:\s*sin[-_ ]",
    re.IGNORECASE | re.MULTILINE,
)
_S7_FIELDS = ("module", "basic hardware", "basic firmware", "version", "system name",
              "module type", "serial number", "plant identification", "copyright")


# ---------------------------------------------------------------------------
# utilidades
# ---------------------------------------------------------------------------

def _scripts_by_id(host: ParsedHost) -> dict:
    d: dict[str, str] = {}
    for k, v in host.host_scripts.items():
        d[k] = (d.get(k, "") + "\n" + (v or "")).strip()
    for p in host.ports:
        for k, v in p.scripts.items():
            d[k] = (d.get(k, "") + "\n" + (v or "")).strip()
    return d


def _text_sources(host: ParsedHost, scripts: dict) -> list[tuple[str, str]]:
    """Textos separados por fuente (no se mezcla todo en un solo blob)."""
    out: list[tuple[str, str]] = []
    for p in host.ports:
        if p.state != "open":
            continue
        prod = " ".join(x for x in (p.product, p.version, *(p.cpe or [])) if x)
        if prod:
            out.append(("product", prod))
    for sid, src in (("http-title", "http-title"), ("ssl-cert", "ssl-cert"), ("banner", "banner"),
                     ("http-headers", "http-headers"), ("snmp-info", "snmp"),
                     ("snmp-sysdescr", "snmp"), ("smb-os-discovery", "smb")):
        if scripts.get(sid, "").strip():
            out.append((src, scripts[sid]))
    if host.vendor:
        out.append(("oui", host.vendor))
    return out


def _cert_summary(text: str) -> str | None:
    """Datos auditables del certificado: organización, llave, firma y vigencia."""
    org = re.search(r"organizationName=([^/\n]+)", text)
    bits = re.search(r"Public Key bits:\s*(\d+)", text)
    ktype = re.search(r"Public Key type:\s*(\w+)", text)
    sig = re.search(r"Signature Algorithm:\s*(\S+)", text)
    until = re.search(r"Not valid after:\s*(\S+)", text)
    parts = []
    if org:
        parts.append(f"O={org.group(1).strip()}")
    if ktype or bits:
        parts.append(f"Llave: {(ktype.group(1).upper() if ktype else '')} {bits.group(1) if bits else ''}".strip())
    if sig:
        parts.append(f"Firma: {sig.group(1)}")
    if until:
        expires = until.group(1)[:10]
        expired = expires < datetime.now(timezone.utc).strftime("%Y-%m-%d")
        parts.append(f"Vence: {expires}{' (VENCIDO)' if expired else ''}")
    weak = []
    if bits and int(bits.group(1)) < 2048:
        weak.append("llave < 2048 bits")
    if sig and re.search(r"sha1|md5", sig.group(1), re.IGNORECASE):
        weak.append("firma SHA-1/MD5")
    if weak:
        parts.append("Debilidades: " + ", ".join(weak))
    return "; ".join(parts) or None


def resolve_os(host: ParsedHost) -> str | None:
    smb = host.host_scripts.get("smb-os-discovery", "")
    for line in smb.splitlines():
        if line.strip().lower().startswith("os:"):
            return line.split(":", 1)[1].strip()
    for p in host.ports:
        text = " ".join(x for x in (p.ostype, p.product, *(p.cpe or [])) if x).lower()
        if "microsoft:windows" in text or "windows" in text:
            return "Windows"
        if "linux" in text:
            return "Linux"
    for om in sorted(host.osmatches, key=lambda m: -m["accuracy"]):
        fam = (om.get("family") or "").lower()
        if fam and not any(b in fam for b in _BOGUS_OS) and not any(b in (om["name"] or "").lower() for b in _BOGUS_OS):
            return om["name"]
    return None


def _parse_s7(text: str) -> dict:
    """Conserva modelo, módulo, versión, etc. como evidencia auditable."""
    fields: dict[str, str] = {}
    for line in text.splitlines():
        if ":" not in line:
            continue
        key, val = line.split(":", 1)
        k = key.strip().lower()
        if k in _S7_FIELDS and val.strip():
            fields[key.strip()] = val.strip()
    return fields


def _parse_kv(text: str, key: str) -> str | None:
    for line in text.splitlines():
        if line.strip().lower().startswith(key + ":"):
            return line.split(":", 1)[1].strip()
    return None


# ---------------------------------------------------------------------------
# evidencia
# ---------------------------------------------------------------------------

def collect_evidence(host: ParsedHost) -> list[dict]:
    scripts = _scripts_by_id(host)
    open_ports = {(p.port, p.transport) for p in host.ports if p.state == "open"}
    port_service = {(p.port, p.transport): (p.service or "").lower() for p in host.ports if p.state == "open"}
    ev: list[dict] = []

    def add(level, group, label, weights, is_service=False, detail=None, port=None,
            transport=None, source=None):
        ev.append({"level": level, "group": group, "label": label, "weights": weights,
                   "is_service": is_service, "detail": detail, "port": port,
                   "transport": transport, "source": source})

    # --- Nivel CONTROL: NSE OT con datos de identidad ---
    s7 = scripts.get("s7-info", "")
    if s7.strip():
        fields = _parse_s7(s7)
        detail = "; ".join(f"{k}: {v}" for k, v in fields.items()) or None
        if fields and _CNC_IN_S7.search(s7):
            add("control", "s7", "Siemens S7 · CPU de control numérico (SINUMERIK)",
                {"cnc": 95, "plc": 30}, detail=detail, port=102, source="s7-info")
        elif fields and _HMI_IN_S7.search(s7):
            add("control", "s7", "Siemens S7 · Panel HMI", {"hmi": 90, "plc": 20},
                detail=detail, port=102, source="s7-info")
        elif fields:
            add("control", "s7", "Siemens S7 · CPU / PLC", {"plc": 95, "io_remote": 20, "hmi": 10},
                detail=detail, port=102, source="s7-info")
        else:
            add("signal", "s7", "s7-info respondió (sin datos de módulo)",
                {"plc": 35, "hmi": 25, "io_remote": 20}, port=102, source="s7-info")

    enip = scripts.get("enip-info", "")
    if enip.strip():
        dev = (_parse_kv(enip, "device type") or "").lower()
        name = _parse_kv(enip, "product name")
        vendor = _parse_kv(enip, "vendor")
        detail = "; ".join(x for x in (f"Device Type: {dev}" if dev else None,
                                        f"Product: {name}" if name else None,
                                        f"Vendor: {vendor}" if vendor else None) if x) or None
        matched = False
        for keys, weights in _ENIP_DEVICE_TYPES:
            if any(k in dev for k in keys):
                add("control", "enip", f"EtherNet/IP · {dev.title() or 'dispositivo'}", weights, detail=detail,
                    port=44818, source="enip-info")
                matched = True
                break
        if not matched:
            add("signal", "enip", "EtherNet/IP respondió (tipo no reconocido)",
                {"plc": 35, "drive": 25, "robot": 25, "io_remote": 25, "hmi": 15},
                detail=detail, port=44818, source="enip-info")

    if scripts.get("modbus-discover", "").strip():
        add("signal", "modbus", "modbus-discover respondió (Modbus)",
            {"plc": 35, "drive": 25, "io_remote": 25, "instrument": 25},
            detail=scripts["modbus-discover"][:200], port=502, source="modbus-discover")

    if scripts.get("rtsp-methods", "").strip():
        add("signal", "rtsp", "rtsp-methods respondió (RTSP)", {"camera": 45}, port=554, source="rtsp-methods")

    # SNMP: administración. Solo su contenido identifica (vía reglas de texto abajo).
    if (161, "udp") in open_ports or scripts.get("snmp-info", "").strip():
        add("signal", "snmp_mgmt", "SNMP (administración de red)", {}, is_service=True,
            port=161, transport="udp", source="snmp-info")

    # --- Nivel PRODUCTO: reglas de texto por fuente y por palabra completa ---
    best_text: dict[str, dict] = {}
    for src, text in _text_sources(host, scripts):
        factor = _SOURCE_FACTOR.get(src, 0.8)
        for rx, weights, group, label, svc in _COMPILED:
            m = rx.search(text)
            if not m:
                continue
            w = {t: round(v * factor) for t, v in weights.items()}
            level = "signal" if src == "oui" else "product"
            key = f"{group}:{level}"
            score = max(w.values(), default=0)
            prev = best_text.get(key)
            if prev is None or score > max(prev["weights"].values(), default=0):
                best_text[key] = {"level": level, "group": group, "weights": w, "is_service": svc,
                                  "label": f"{label} ({src}: '{m.group(0)}')", "source": src,
                                  "detail": _cert_summary(text) if src == "ssl-cert" else None}
    for e in best_text.values():
        add(e["level"], e["group"], e["label"], e["weights"], is_service=e["is_service"],
            source=e["source"], detail=e["detail"])

    # Autenticación HTTP Basic (credenciales viajan en base64)
    auth = re.search(r"WWW-Authenticate:\s*(Basic|Digest|NTLM|Negotiate)", scripts.get("http-headers", ""), re.IGNORECASE)
    if auth:
        add("signal", "http_auth", f"Autenticación HTTP {auth.group(1).capitalize()}", {}, is_service=True,
            source="http-headers")

    # IPP: solo si el servicio en 631 se identifica como ipp (no subcadena)
    if (631, "tcp") in open_ports and port_service.get((631, "tcp")) in ("ipp", "ipps"):
        add("signal", "print", "631/tcp · IPP", {"printers": 25}, port=631, transport="tcp")

    # --- Señales por puerto ---
    for port, transport, weights, label, group in _PORT_SIGNALS:
        if (port, transport) in open_ports:
            add("signal", group, f"{port}/{transport} · {label}", weights, port=port, transport=transport)

    # Combinación típica de panel: VNC + protocolo de control sin identidad de PLC
    if (5900, "tcp") in open_ports and ((102, "tcp") in open_ports or (44818, "tcp") in open_ports):
        add("signal", "hmi_combo", "VNC + protocolo de control (patrón de panel HMI)", {"hmi": 30})

    for port, transport, w, label in _GENERIC_PORTS:
        if (port, transport) in open_ports:
            add("signal", f"svc{port}", f"{port}/{transport} · {label}",
                {t: w for t in _GENERIC_TYPES[port]}, port=port, transport=transport)

    # --- SO (casi nulo) ---
    os_name = resolve_os(host)
    if os_name and "windows" in os_name.lower():
        add("os", "os", f"OS: {os_name}", {"mes": 2, "server": 2, "scada": 2, "hmi": 2})

    return ev


# ---------------------------------------------------------------------------
# puntuación
# ---------------------------------------------------------------------------

def _score_types(ev: list[dict]) -> dict[str, dict]:
    """Por tipo: identidad (máximo + pequeño extra), señales (tope) y nivel."""
    acc: dict[str, dict] = {}
    for e in ev:
        for t, w in e["weights"].items():
            if w <= 0:
                continue
            a = acc.setdefault(t, {"identity": {}, "signal": {}, "level": 0})
            bucket = "identity" if e["level"] in ("control", "product") else "signal"
            if w > a[bucket].get(e["group"], 0):
                a[bucket][e["group"]] = w
            a["level"] = max(a["level"], _LEVEL_RANK[e["level"]])

    out = {}
    for t, a in acc.items():
        ids = sorted(a["identity"].values(), reverse=True)
        id_score = (ids[0] + 0.2 * sum(ids[1:])) if ids else 0
        sig = min(SIGNAL_CAP, sum(a["signal"].values()))
        score = min(100, round(id_score + 0.3 * sig)) if id_score else sig
        out[t] = {"score": score, "level": a["level"], "identity": ids[0] if ids else 0}
    return out


def _best_identity(ev: list[dict], t: str) -> dict | None:
    best = None
    for e in ev:
        if e["level"] in ("control", "product") and e["weights"].get(t, 0) > 0:
            if best is None or (_LEVEL_RANK[e["level"]], e["weights"][t]) > (_LEVEL_RANK[best["level"]], best["weights"][t]):
                best = e
    return best


def _detect_conflict(ev: list[dict], typed: dict, winner: str) -> tuple[bool, str | None, list[str]]:
    w_best = _best_identity(ev, winner)
    if not w_best or w_best["weights"][winner] < STRONG_ID:
        return False, None, []
    rivals = []
    for t, info in typed.items():
        if t == winner or info["identity"] < STRONG_ID:
            continue
        r_best = _best_identity(ev, t)
        if r_best is None or r_best["group"] == w_best["group"]:
            continue
        # evidencia de servicio de menor nivel → no es conflicto, es servicio
        if r_best["is_service"] and _LEVEL_RANK[r_best["level"]] < _LEVEL_RANK[w_best["level"]]:
            continue
        rivals.append(t)
    if not rivals:
        return False, None, []
    labels = [PROFILES.get(x, {}).get("label", x) for x in [winner, *rivals]]
    reason = "Evidencia fuerte y contradictoria: " + " vs ".join(labels)
    return True, reason, [winner, *rivals]


def _fingerprints_from(ev: list[dict], host: ParsedHost, winner: str | None) -> list[dict]:
    out, seen = [], set()

    def push(kind, label, detail=None, port=None, transport=None, source=None):
        if label in seen:
            return
        seen.add(label)
        out.append({"kind": kind, "label": label, "detail": detail, "port": port,
                    "transport": transport, "source": source})

    best = _best_identity(ev, winner) if winner else None
    if best:
        push("identity", best["label"], best.get("detail"), best.get("port"), best.get("transport"), best.get("source"))

    for e in ev:
        if e is best:
            continue
        if e["level"] in ("control", "product") and (e["is_service"] or not winner or winner not in e["weights"]):
            push("service", e["label"], e.get("detail"), e.get("port"), e.get("transport"), e.get("source"))
        elif e["group"] == "snmp_mgmt":
            push("service", e["label"], port=161, transport="udp", source="snmp-info")
        elif e["group"] == "http_auth":
            push("service", e["label"], source="http-headers")

    for p in host.ports:
        if p.state == "open" and p.port in _SERVICE_PORTS:
            label = f"{_SERVICE_PORTS[p.port]} ({p.product})" if p.product else _SERVICE_PORTS[p.port]
            push("service", label, port=p.port, transport=p.transport, source="service")
    return out


def classify_host(host: ParsedHost) -> dict:
    ev = collect_evidence(host)
    typed = _score_types(ev)
    scores = {t: v["score"] for t, v in typed.items()}

    # Ranking: primero el NIVEL de identidad, luego la puntuación, luego tipos de control
    ranking = sorted(
        ({"profile": t, "label": PROFILES.get(t, {}).get("label", t), "type": TYPE_SLUG.get(t, t),
          "score": v["score"], "level": v["level"]}
         for t, v in typed.items() if v["score"] > 0),
        key=lambda r: (-r["level"], -r["score"], 0 if r["profile"] in _CONTROL_TYPES else 1),
    )[:5]

    winner = ranking[0]["profile"] if ranking else None
    winner_score = ranking[0]["score"] if winner else 0
    winner_label = ranking[0]["label"] if winner else "Desconocido"

    needs_review, reason, candidates = (False, None, [])
    if winner:
        needs_review, reason, candidates = _detect_conflict(ev, typed, winner)
    if needs_review:
        winner_score = min(winner_score, APPLY_THRESHOLD - 1)  # nunca se aplica solo

    evidences = sorted(
        ({"level": e["level"], "label": e["label"], "points": e["weights"].get(winner, 0)}
         for e in ev if winner and e["weights"].get(winner, 0) > 0),
        key=lambda x: -x["points"],
    )[:8]

    if needs_review:
        asset_type = "unknown"
    else:
        asset_type = TYPE_SLUG.get(winner, "unknown") if winner_score >= REVIEW_THRESHOLD else "unknown"

    result = {
        "winner": winner,
        "winner_label": winner_label,
        "asset_type": asset_type,
        "score": winner_score,
        "os": resolve_os(host),
        "scores": scores,
        "ranking": ranking,
        "evidences": evidences,
        "fingerprints": _fingerprints_from(ev, host, winner),
        "needs_review": needs_review,
        "review_reason": reason,
        "candidates": candidates,
    }
    result["attributes"] = extract_attributes(host, result)
    return result