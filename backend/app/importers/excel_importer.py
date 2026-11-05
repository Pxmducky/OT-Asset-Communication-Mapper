"""Importador de Excel V2: interpreta archivos SIN estructura fija.

Cómo interpreta cada hoja:
  1. Busca la fila de encabezados (no tiene que ser la primera: ignora títulos,
     logos o filas vacías al inicio).
  2. Reconoce cada encabezado por sinónimos en español/inglés, sin importar
     acentos, mayúsculas, espacios o signos ("IP Origen", "Src IP", "From",
     "Dirección IP", "Nombre del equipo", "Marca", "Modelo"...).
  3. Si un encabezado no se reconoce, mira los VALORES: una columna llena de
     IPs o de MACs se identifica sola. Dos columnas de IPs sin encabezado claro
     se toman como origen y destino.
  4. Hoja con origen + destino → comunicaciones. Hoja con IP, MAC, hostname,
     nombre o código → inventario de activos.

Cómo combina con lo que ya existe:
  - Un activo se encuentra por código, IP, MAC, hostname o nombre (único).
  - Hoja de INVENTARIO sobre un activo que vino de Excel (p. ej. creado antes
    desde un Excel de comunicaciones) → EDITA sus campos con los del inventario.
  - Sobre activos creados a mano o por escaneo → solo COMPLETA campos vacíos.
  - Una celda vacía nunca borra un dato.
  - Las comunicaciones que ya existen se omiten.
"""
import ipaddress
import re
import unicodedata
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path

from openpyxl import load_workbook
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Asset, Communication
from app.services.asset_service import AssetService

MAX_ERRORS = 100
MAX_NOTES = 40
HEADER_SCAN_ROWS = 30     # filas donde se busca el encabezado
SAMPLE_ROWS = 40          # filas para detectar columnas por su contenido

ASSET_FIELDS = (
    "asset_name", "asset_type", "mac", "hostname", "vendor", "product", "os",
    "description", "plant", "building", "production_line", "vlan",
)

# ---------------------------------------------------------------------------
# normalización de texto
# ---------------------------------------------------------------------------

def _norm(value) -> str:
    text = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-z0-9]+", " ", text.lower())
    return re.sub(r"\s+", " ", text).strip()


_STOPWORDS = {"de", "del", "la", "el", "los", "las", "the", "of", "a", "en", "y", "and", "no", "num", "n"}

# Palabras que indican el lado de una comunicación
_SIDE_WORDS = {
    "source": {"origen", "source", "src", "from", "fuente", "desde", "emisor", "sender", "initiator",
               "orig", "sourceip", "srcip", "local"},
    "destination": {"destino", "destination", "dst", "dest", "to", "hacia", "receptor", "receiver",
                    "target", "destinationip", "dstip", "remoto", "remota", "remote", "peer"},
}

# campo → sinónimos (ya normalizados). Se prefiere la coincidencia más larga.
_FIELD_SYNONYMS = {
    "ip": ["ip", "ipv4", "ip address", "direccion ip", "direccion", "address", "ip addr", "dir ip"],
    "mac": ["mac", "mac address", "direccion mac", "macaddress", "mac addr"],
    "hostname": ["hostname", "host", "host name", "nombre de host", "dns", "fqdn", "nombre host"],
    "asset_name": ["nombre", "name", "asset name", "nombre activo", "activo", "equipo", "nombre equipo",
                   "dispositivo", "device", "device name", "asset", "nombre dispositivo"],
    "asset_code": ["asset code", "codigo", "code", "id activo", "asset id", "codigo activo", "id", "tag",
                   "asset tag", "identificador", "etiqueta", "id equipo", "id dispositivo"],
    "asset_type": ["tipo", "type", "asset type", "tipo activo", "tipo equipo", "categoria", "category",
                   "clase", "device type", "tipo dispositivo", "rol", "role", "funcion"],
    "vendor": ["fabricante", "vendor", "marca", "manufacturer", "brand", "proveedor", "make"],
    "product": ["producto", "product", "modelo", "model", "part number", "numero de parte", "referencia",
                "referencia producto", "mlfb", "catalogo", "catalog number", "pn"],
    "os": ["os", "sistema operativo", "operating system", "so", "firmware", "version firmware",
           "fw", "sw version"],
    "description": ["descripcion", "description", "comentarios", "comentario", "notas", "nota", "notes",
                    "observaciones", "comments", "detalle", "uso"],
    "plant": ["planta", "plant", "site", "sitio", "sede", "ubicacion", "location"],
    "building": ["nave", "edificio", "building", "area", "zona", "zone", "hall"],
    "production_line": ["linea", "line", "linea de produccion", "production line", "celda", "cell",
                        "proceso", "process", "maquina", "machine", "estacion"],
    "vlan": ["vlan", "vlan id"],
    "protocol": ["protocolo", "protocol", "proto", "servicio", "service"],
    "port": ["puerto", "port", "puertos", "ports", "tcp port", "udp port", "dport", "sport"],
}

_SYNONYM_INDEX = sorted(
    ((tuple(t for t in s.split() if t not in _STOPWORDS), f) for f, syns in _FIELD_SYNONYMS.items() for s in syns),
    key=lambda x: -len(x[0]),
)

# Tipos de activo libres → valores de la app
_TYPE_SYNONYMS = [
    (("plc", "controlador", "controller", "cpu", "pac", "rtu"), "controller"),
    (("hmi", "panel", "pantalla", "operator panel", "panelview", "ktp", "touch"), "HMI"),
    (("estacion de ingenieria", "engineering", "ews", "programadora"), "engineering_station"),
    (("historian", "historiador"), "historian"),
    (("scada", "opc"), "scada"),
    (("mes",), "mes"),
    (("servidor", "server", "broker", "mqtt", "siem", "ids", "ips", "nids", "log collector", "dns", "ntp"), "server"),
    (("pc", "computadora", "laptop", "workstation", "computer", "desktop"), "computer"),
    (("io", "i o", "e s", "remote io", "et200", "modulo"), "IO_module"),
    (("variador", "drive", "vfd", "inverter", "servo"), "drive"),
    (("switch", "conmutador"), "switch"),
    (("router", "enrutador"), "router"),
    (("firewall", "cortafuegos", "fw"), "firewall"),
    (("access point", "ap", "wap", "wifi", "wi fi", "inalambrico"), "WAP"),
    (("impresora", "printer", "escaner", "scanner", "etiquetadora"), "printer_scanner"),
    (("cnc",), "cnc"),
    (("camara", "camera", "cctv", "nvr", "dvr"), "camera"),
    (("robot", "cobot"), "robot"),
    (("barcode", "codigo de barras", "lector", "reader", "rfid"), "instrument"),
    (("vision", "vision system", "camara de vision"), "camera"),
    (("instrumento", "instrument", "bascula", "sensor", "medidor", "transmisor", "flowmeter"), "instrument"),
    (("motor", "valvula", "valve", "actuador", "actuator", "field device", "dispositivo de campo"), "OT_device"),
    (("ot device", "dispositivo ot"), "OT_device"),
    (("it device", "dispositivo it", "telefono", "phone", "voip"), "IT_device"),
    (("ups", "pdu", "no break"), "ups"),
    (("ewon",), "ewon"),
    (("mguard",), "mguard"),
]

_PORT_PROTOCOL = {
    "502": "modbus", "102": "s7", "44818": "enip", "2222": "enip", "4840": "opcua", "20000": "dnp3",
    "47808": "bacnet", "1883": "mqtt", "80": "http", "443": "https", "22": "ssh", "23": "telnet",
    "3389": "rdp", "5900": "vnc", "161": "snmp", "445": "smb", "1433": "mssql", "21": "ftp",
    "34964": "profinet", "9100": "jetdirect",
}

_KNOWN_PROTOCOLS = set(_PORT_PROTOCOL.values()) | {
    "tcp", "udp", "icmp", "ethernet ip", "ethernetip", "cip", "profinet", "profibus", "iec 104",
    "iec104", "iec 61850", "mms", "goose", "opc da", "opc ua", "ntp", "dns", "dhcp", "syslog", "ldap",
    "smtp", "sftp", "tftp", "s7comm", "s7 comm", "fins", "melsec", "slmp", "bacnet ip",
}

_REF_PATTERN = re.compile(r"^[\w][\w .\-/#]{0,49}$", re.UNICODE)

MAC_PATTERN = re.compile(r"^([0-9a-f]{2}:){5}[0-9a-f]{2}$")
_IP_IN_TEXT = re.compile(r"^\s*(\d{1,3}(?:\.\d{1,3}){3})(?:/\d{1,2})?(?::(\d{1,5}))?\s*$")


def _map_header(raw) -> tuple[str | None, str | None]:
    """Encabezado → (lado, campo). lado: source|destination|None."""
    tokens = _norm(raw).split()
    if not tokens:
        return None, None
    # "sourceip"/"srcip" pegados
    side = None
    rest = []
    for t in tokens:
        hit = next((s for s, words in _SIDE_WORDS.items() if t in words), None)
        if hit and side is None:
            side = hit
            if t.endswith("ip") and t not in ("ip",):
                rest.append("ip")
            continue
        if t not in _STOPWORDS:
            rest.append(t)
    if side and not rest:
        return side, "ip"
    if side and rest in (["asset"], ["activo"], ["equipo"], ["device"]):
        return side, "asset_code"
    rest_t = tuple(rest)
    for syn, fld in _SYNONYM_INDEX:
        n = len(syn)
        if any(rest_t[i:i + n] == syn for i in range(len(rest_t) - n + 1)):
            return side, fld
    return side, None


VALID_TYPES = {
    "controller", "HMI", "engineering_station", "server", "historian", "computer", "IO_module", "drive",
    "OT_device", "switch", "router", "firewall", "WAP", "printer_scanner", "IT_device", "mes", "cnc",
    "camera", "robot", "instrument", "scada", "ups", "ewon", "mguard", "insys", "unknown",
}
_VALID_BY_LOWER = {t.lower(): t for t in VALID_TYPES}


_EXACT_HEADERS = (
    {syn for syns in _FIELD_SYNONYMS.values() for syn in syns}
    | {w for words in _SIDE_WORDS.values() for w in words}
    | {f"{w} {f}" for words in _SIDE_WORDS.values() for w in words for f in ("ip", "port", "name", "mac")}
    | {f"{f} {w}" for words in _SIDE_WORDS.values() for w in words for f in ("ip", "puerto", "nombre", "mac")}
)


def _normalize_type(value: str | None) -> tuple[str | None, str | None]:
    """Tipo libre → (tipo de la app, tipo original si no se reconoció)."""
    if not value:
        return None, None
    raw = value.strip()
    if raw.lower() in _VALID_BY_LOWER:
        return _VALID_BY_LOWER[raw.lower()], None
    text = f" {_norm(raw)} "
    for keys, slug in _TYPE_SYNONYMS:
        if any(f" {k} " in text for k in keys):
            return slug, None
    return "unknown", raw


def _split_ip(value: str) -> tuple[str | None, str | None, bool]:
    """'10.0.0.1', '10.0.0.1/24', '10.0.0.1:502' → (ip, puerto, válida)."""
    value = (value or "").strip()
    if not value:
        return None, None, True
    m = _IP_IN_TEXT.match(value)
    candidate, port = (m.group(1), m.group(2)) if m else (value, None)
    try:
        return str(ipaddress.ip_address(candidate)), port, True
    except ValueError:
        return None, None, False


def _looks_ip(value: str) -> bool:
    ip, _, ok = _split_ip(value)
    return bool(ip) and ok


def _parse_mac(value: str) -> str | None:
    v = re.sub(r"[^0-9a-f]", "", (value or "").lower())
    if len(v) != 12:
        return None
    return ":".join(v[i:i + 2] for i in range(0, 12, 2))


def _parse_vlan(value: str) -> int | None:
    match = re.search(r"\d+", value or "")
    if match and 1 <= int(match.group()) <= 4094:
        return int(match.group())
    return None


@dataclass
class ImportResult:
    assets_created: int = 0
    assets_updated: int = 0
    communications_created: int = 0
    communications_skipped: int = 0
    rows_skipped: int = 0
    errors: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def add_error(self, message: str) -> None:
        if len(self.errors) < MAX_ERRORS:
            self.errors.append(message)

    def add_note(self, message: str) -> None:
        if len(self.notes) < MAX_NOTES:
            self.notes.append(message)


class ExcelImportError(Exception):
    """El archivo no se puede importar de forma segura."""


class ExcelImporter:
    def __init__(self, db: Session, import_id: int | None = None):
        self.db = db
        self.import_id = import_id
        self.result = ImportResult()
        self._by_ip: dict[str, Asset] = {}
        self._by_code: dict[str, Asset] = {}
        self._by_mac: dict[str, Asset] = {}
        self._by_host: dict[str, Asset] = {}
        self._by_name: dict[str, Asset | None] = {}   # None = nombre repetido (ambiguo)
        self._next_number = 0
        self._existing_keys: set[tuple] = set()
        self._created_ids: set[int] = set()
        self._updated_ids: set[int] = set()
        self._provisional_ids: set[int] = set()

    # ---------- entrada ----------

    def import_file(self, file_path: str | Path) -> ImportResult:
        path = Path(file_path)
        if not path.exists():
            raise ExcelImportError(f"No existe el archivo: {path}")
        if path.suffix.lower() not in {".xlsx", ".xlsm"}:
            raise ExcelImportError("El archivo debe ser .xlsx o .xlsm")
        return self.import_bytes(path.read_bytes())

    def import_bytes(self, content: bytes) -> ImportResult:
        try:
            workbook = load_workbook(BytesIO(content), read_only=True, data_only=True)
        except Exception as exc:
            raise ExcelImportError(f"No se pudo abrir el Excel: {exc}") from exc

        asset_sheets, communication_sheets = [], []
        for sheet in workbook.worksheets:
            kind, rows = self._read_sheet(sheet)
            if kind == "communications":
                communication_sheets.append((sheet.title, rows))
            elif kind == "assets":
                asset_sheets.append((sheet.title, rows))
        workbook.close()

        if not asset_sheets and not communication_sheets:
            raise ExcelImportError(
                "No se reconoció ninguna hoja de activos ni de comunicaciones. Se necesita al menos una "
                "columna de IP, MAC, hostname o nombre (inventario), u origen y destino (comunicaciones)."
            )

        self._load_existing()
        try:
            # Inventario primero: las comunicaciones pueden referirse a los activos
            # por su ID/nombre, y solo completan lo que el inventario no trae.
            for title, rows in asset_sheets:
                self._import_assets(title, rows)
            for title, rows in communication_sheets:
                self._import_communications(title, rows)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        self.result.assets_updated = len(self._updated_ids - self._created_ids)
        return self.result

    # ---------- lectura flexible ----------

    @staticmethod
    def _clean(value) -> str:
        if value is None:
            return ""
        if isinstance(value, float) and value.is_integer():
            value = int(value)
        return str(value).strip()

    def _find_header(self, raw_rows: list[tuple]) -> tuple[int, dict[int, tuple]]:
        """Fila con más encabezados reconocidos dentro de las primeras filas."""
        best_idx, best_map, best_score = -1, {}, 0
        for idx, values in enumerate(raw_rows[:HEADER_SCAN_ROWS]):
            mapping = {}
            for col, v in enumerate(values):
                if v is None or self._clean(v) == "" or _looks_ip(self._clean(v)):
                    continue
                side, fld = _map_header(v)
                if fld:
                    mapping[col] = (side, fld)
            score = len(mapping) + sum(1 for s, f in mapping.values() if f == "ip")
            if score > best_score:
                best_idx, best_map, best_score = idx, mapping, score
        if best_score < 2:
            return -1, {}
        return best_idx, best_map

    def _is_header_row(self, values: tuple) -> bool:
        cells = [self._clean(v) for v in values if self._clean(v)]
        if any(_looks_ip(v) for v in cells):
            return False
        return sum(1 for v in cells if _norm(v) in _EXACT_HEADERS) >= 2

    def _detect_by_values(self, data: list[tuple], mapping: dict[int, tuple], width: int) -> dict[int, tuple]:
        """Columnas no reconocidas: se identifican por su contenido (IP / MAC)."""
        sample = data[:SAMPLE_ROWS]
        ip_cols, mac_cols, proto_cols = [], [], []
        for col in range(width):
            if col in mapping:
                continue
            vals = [self._clean(r[col]) for r in sample if col < len(r) and self._clean(r[col])]
            if len(vals) < 2:
                continue
            if sum(_looks_ip(v) for v in vals) / len(vals) >= 0.7:
                ip_cols.append(col)
            elif sum(bool(_parse_mac(v)) for v in vals) / len(vals) >= 0.7:
                mac_cols.append(col)
            elif sum(_norm(v) in _KNOWN_PROTOCOLS for v in vals) / len(vals) >= 0.6:
                proto_cols.append(col)

        fields = set(mapping.values())
        src, dst, plain = ("source", "ip") in fields, ("destination", "ip") in fields, (None, "ip") in fields

        # "IP" + "Destino" (o "Origen" + "IP"): la IP sin lado es el otro extremo
        if plain and (src ^ dst):
            col = next(c for c, v in mapping.items() if v == (None, "ip"))
            mapping[col] = ("source", "ip") if dst else ("destination", "ip")
            src = dst = True
            plain = False

        if ip_cols:
            if src and not dst:
                mapping[ip_cols[0]] = ("destination", "ip")
            elif dst and not src:
                mapping[ip_cols[0]] = ("source", "ip")
            elif not src and not dst:
                if not plain and len(ip_cols) >= 2:
                    mapping[ip_cols[0]] = ("source", "ip")
                    mapping[ip_cols[1]] = ("destination", "ip")
                elif not plain:
                    mapping[ip_cols[0]] = (None, "ip")
        fields = set(mapping.values())
        if proto_cols and (None, "protocol") not in fields:
            mapping[proto_cols[0]] = (None, "protocol")
        if mac_cols and (None, "mac") not in fields:
            mapping[mac_cols[0]] = (None, "mac")
        return mapping

    def _read_sheet(self, sheet) -> tuple[str | None, list[tuple[int, dict]]]:
        raw: list[tuple[int, tuple]] = []
        for row_number, values in enumerate(sheet.iter_rows(values_only=True), start=1):
            if values is None or all(v in (None, "") for v in values):
                continue
            raw.append((row_number, values))
        if not raw:
            return None, []

        header_idx, mapping = self._find_header([v for _, v in raw])
        data_rows = raw[header_idx + 1:] if header_idx >= 0 else raw
        width = max((len(v) for _, v in raw), default=0)
        mapping = self._detect_by_values([v for _, v in data_rows], mapping, width)

        # Sin duplicados: primera columna por (lado, campo)
        seen, final = set(), {}
        for col in sorted(mapping):
            if mapping[col] not in seen:
                seen.add(mapping[col])
                final[col] = mapping[col]

        fields = set(final.values())
        is_comm = ("source", "ip") in fields and ("destination", "ip") in fields
        plain = {f for s, f in fields if s is None}
        # Inventario: necesita un identificador real (no basta un nombre + tipo,
        # como en hojas de variables, VLANs o catálogos de protocolos)
        is_asset = not is_comm and (
            bool(plain & {"ip", "mac", "hostname"}) or {"asset_code", "asset_name"} <= plain
        )
        if not (is_comm or is_asset):
            if final or header_idx >= 0:
                self.result.add_note(f"Hoja '{sheet.title}': no se reconoció como inventario ni comunicaciones; se omitió.")
            return None, []

        kind = "communications" if is_comm else "assets"
        header_vals = raw[header_idx][1] if header_idx >= 0 else ()
        described = []
        for col, (side, fld) in final.items():
            name = self._clean(header_vals[col]) if col < len(header_vals) and header_vals[col] else f"col {col + 1}"
            target = f"{'origen' if side == 'source' else 'destino'} · {fld}" if side else fld
            described.append(f"{name} → {target}")
        ignored = [self._clean(h) for c, h in enumerate(header_vals) if h and c not in final]
        self.result.add_note(
            f"Hoja '{sheet.title}' ({'comunicaciones' if is_comm else 'inventario'}): " + "; ".join(described)
            + (f". Columnas guardadas en la descripción: {', '.join(ignored)}" if ignored else "")
        )

        extra_cols = {c: self._clean(h) for c, h in enumerate(header_vals) if h and c not in final}
        rows: list[tuple[int, dict]] = []
        for row_number, values in data_rows:
            if self._is_header_row(values):
                continue  # encabezado repetido a mitad de la hoja
            row: dict[str, str] = {}
            extras = [f"{name}: {self._clean(values[c])}" for c, name in extra_cols.items()
                      if c < len(values) and self._clean(values[c])]
            if extras:
                row["_extra"] = "; ".join(extras)
            for col, (side, fld) in final.items():
                if col >= len(values):
                    continue
                val = self._clean(values[col])
                if not val:
                    continue
                if fld == "port":
                    key = f"{side or 'destination'}_port"
                elif side:
                    key = side if fld == "ip" else f"{side}_{fld}"
                else:
                    key = fld
                row[key] = val
            if set(row) - {"_extra"}:
                rows.append((row_number, row))
        return kind, rows

    # ---------- inventario existente ----------

    def _index(self, asset: Asset) -> None:
        self._by_code[asset.asset_code] = asset
        if asset.ip:
            self._by_ip[asset.ip] = asset
        if asset.mac:
            self._by_mac[asset.mac.lower()] = asset
        if asset.hostname:
            self._by_host[asset.hostname.lower()] = asset
        if asset.asset_name and asset.asset_name != asset.ip:
            key = asset.asset_name.strip().lower()
            self._by_name[key] = None if key in self._by_name and self._by_name[key] is not asset else asset

    def _load_existing(self) -> None:
        for asset in self.db.scalars(select(Asset)):
            self._index(asset)
        self._next_number = AssetService.max_code_number(self.db)
        existing = self.db.execute(
            select(
                Communication.source_asset_id,
                Communication.destination_asset_id,
                Communication.protocol,
                Communication.source_port,
                Communication.destination_port,
            )
        ).all()
        self._existing_keys = {self._key(*row) for row in existing}

    @staticmethod
    def _key(source_id, destination_id, protocol, source_port, destination_port) -> tuple:
        return (source_id, destination_id, (protocol or "").lower(), source_port or "", destination_port or "")

    def _find(self, ip=None, code=None, mac=None, hostname=None, name=None) -> Asset | None:
        """Busca primero por IP. Código, MAC, hostname y nombre solo cuentan si
        no contradicen la IP (varias IPs pueden compartir MAC de un gateway)."""
        if ip and ip in self._by_ip:
            return self._by_ip[ip]
        candidates = (
            self._by_code.get(code) if code else None,
            self._by_mac.get(mac.lower()) if mac else None,
            self._by_host.get(hostname.lower()) if hostname else None,
            self._by_name.get(name.strip().lower()) if name else None,
        )
        for cand in candidates:
            if cand is not None and (not ip or not cand.ip or cand.ip == ip):
                return cand
        return None

    def _find_ref(self, ref: str) -> Asset | None:
        """Referencia que no es IP (ID/tag, nombre o hostname)."""
        key = ref.strip()
        return (
            self._by_code.get(key)
            or self._by_host.get(key.lower())
            or self._by_name.get(key.lower())
        )

    # ---------- valores ----------

    def _asset_values(self, row: dict, prefix: str = "") -> dict:
        values = {name: row.get(prefix + name) or None for name in ASSET_FIELDS}
        values["mac"] = _parse_mac(values["mac"] or "")
        values["vlan"] = _parse_vlan(values["vlan"] or "")
        values["asset_type"], original_type = _normalize_type(values["asset_type"])
        extra = row.get("_extra") if not prefix else None
        if original_type:
            extra = "; ".join(x for x in (f"Tipo original: {original_type}", extra) if x)
            if values["asset_type"] == "unknown":
                values["asset_type"] = None   # no pisa un tipo ya conocido con 'unknown'
        if extra:
            values["description"] = " · ".join(x for x in (values["description"], extra) if x)
        return values

    def _create_asset(self, ip: str | None, values: dict, code: str | None = None) -> Asset:
        if not code or code in self._by_code:
            self._next_number += 1
            code = AssetService.format_code(self._next_number)
        else:
            self._next_number = max(self._next_number, AssetService.code_number(code))

        values = dict(values)
        values["asset_name"] = values.get("asset_name") or values.get("hostname") or ip or code
        values["asset_type"] = values.get("asset_type") or "unknown"

        asset = Asset(asset_code=code, ip=ip, discovery_source="excel", import_id=self.import_id, **values)
        self.db.add(asset)
        self.db.flush()

        self._index(asset)
        self._created_ids.add(asset.id)
        self.result.assets_created += 1
        return asset

    def _fill(self, asset: Asset, values: dict, overwrite: bool = False) -> None:
        changed = False
        for name, value in values.items():
            if value is None:
                continue
            current = getattr(asset, name)
            is_empty = (
                current in (None, "")
                or (name == "asset_name" and current in (asset.ip, asset.asset_code))
                or (name == "asset_type" and current == "unknown")
            )
            if (overwrite or is_empty) and current != value:
                setattr(asset, name, value)
                changed = True
        if changed:
            self._index(asset)
            self._updated_ids.add(asset.id)

    # ---------- inventario ----------

    def _import_assets(self, title: str, rows: list[tuple[int, dict]]) -> None:
        for row_number, row in rows:
            ip, _, valid = _split_ip(row.get("ip", ""))
            if not valid:
                self.result.rows_skipped += 1
                self.result.add_error(f"{title} fila {row_number}: IP inválida '{row.get('ip')}'.")
                continue
            code = row.get("asset_code") or None
            values = self._asset_values(row)
            if not any((ip, code, values["mac"], values["hostname"], values["asset_name"])):
                self.result.rows_skipped += 1
                continue
            # Fila sin IP/MAC/código con un solo dato: probablemente título o total
            if not (ip or code or values["mac"]) and sum(v is not None for v in values.values()) < 2:
                self.result.rows_skipped += 1
                continue

            asset = self._find(ip, code, values["mac"], values["hostname"], values["asset_name"])
            if asset is None:
                self._create_asset(ip, values, code)
                continue
            if ip and not asset.ip and ip not in self._by_ip:
                asset.ip = ip
                self._by_ip[ip] = asset
                self._updated_ids.add(asset.id)
            # El inventario manda sobre lo que vino de Excel; respeta lo manual/escaneo
            self._fill(asset, values, overwrite=(asset.discovery_source == "excel"))
            # Sin nombre real pero con hostname: el hostname sirve de nombre
            if asset.hostname and asset.asset_name in (None, "", asset.ip, asset.asset_code):
                asset.asset_name = asset.hostname
                self._updated_ids.add(asset.id)

    # ---------- comunicaciones ----------

    def _resolve(self, row: dict, side: str, title: str, row_number: int) -> tuple[Asset | None, str | None]:
        label = "origen" if side == "source" else "destino"
        raw = row.get(side, "")
        ip, port, valid = _split_ip(raw)
        values = self._asset_values(row, f"{side}_")
        code = row.get(f"{side}_asset_code") or None

        if not valid:
            # No es IP: es una referencia al activo (ID/tag, nombre o hostname)
            if not _REF_PATTERN.match(raw.strip()):
                self.result.add_error(f"{title} fila {row_number}: {label} no reconocido '{raw}'.")
                return None, None
            asset = self._find_ref(raw)
            if asset is None:
                ref = raw.strip()
                asset = self._create_asset(None, {**values, "asset_name": values["asset_name"] or ref},
                                           ref if len(ref) <= 50 else None)
                self._provisional_ids.add(asset.id)
            else:
                self._fill(asset, values)
            return asset, None

        asset = self._find(ip, code, values["mac"], values["hostname"], None)
        if asset is None:
            if not ip:
                if code and code in self._by_code:
                    return self._by_code[code], port
                self.result.add_error(f"{title} fila {row_number}: el {label} no tiene IP ni un ID conocido.")
                return None, None
            asset = self._create_asset(ip, values, code)
            if side == "destination":
                self._provisional_ids.add(asset.id)
            return asset, port

        if side == "source" and asset.id in self._provisional_ids:
            self._fill(asset, values, overwrite=True)
            self._provisional_ids.discard(asset.id)
        else:
            self._fill(asset, values)
        return asset, port

    def _import_communications(self, title: str, rows: list[tuple[int, dict]]) -> None:
        for row_number, row in rows:
            source, src_port_in_ip = self._resolve(row, "source", title, row_number)
            destination, dst_port_in_ip = self._resolve(row, "destination", title, row_number)
            if source is None or destination is None:
                self.result.rows_skipped += 1
                continue
            if source.id == destination.id:
                self.result.rows_skipped += 1
                self.result.add_error(f"{title} fila {row_number}: origen y destino son el mismo activo.")
                continue

            source_port = row.get("source_port") or src_port_in_ip or ""
            destination_port = row.get("destination_port") or dst_port_in_ip or ""
            protocol = (row.get("protocol") or "").strip().lower()
            if not protocol:
                first_port = re.split(r"[^\d]+", destination_port.strip())[0] if destination_port else ""
                protocol = _PORT_PROTOCOL.get(first_port, "unknown")

            key = self._key(source.id, destination.id, protocol, source_port, destination_port)
            if key in self._existing_keys:
                self.result.communications_skipped += 1
                continue

            self.db.add(
                Communication(
                    source_asset_id=source.id,
                    destination_asset_id=destination.id,
                    protocol=protocol,
                    source_port=source_port,
                    destination_port=destination_port,
                    description=" · ".join(x for x in (row.get("description"), row.get("_extra")) if x) or None,
                    import_id=self.import_id,
                )
            )
            self._existing_keys.add(key)
            self.result.communications_created += 1