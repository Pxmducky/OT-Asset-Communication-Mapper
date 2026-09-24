import ipaddress
import re
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path

from openpyxl import load_workbook
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Asset, Communication
from app.services.asset_service import AssetService

# Encabezados alternativos -> nombre interno
HEADER_ALIASES = {
    "from": "source", "src": "source", "source_ip": "source", "origen": "source", "ip_origen": "source",
    "to": "destination", "dst": "destination", "destination_ip": "destination",
    "destino": "destination", "ip_destino": "destination",
    "from_ports": "source_port", "source_ports": "source_port", "puerto_origen": "source_port",
    "to_ports": "destination_port", "destination_ports": "destination_port", "puerto_destino": "destination_port",
    "protocolo": "protocol",
    "codigo": "asset_code", "código": "asset_code",
    "nombre": "asset_name", "tipo": "asset_type", "fabricante": "vendor", "producto": "product",
    "descripcion": "description", "descripción": "description",
    "planta": "plant", "nave": "building",
    "linea": "production_line", "línea": "production_line", "line": "production_line",
    "linea_de_produccion": "production_line", "línea_de_producción": "production_line",
}

ASSET_FIELDS = (
    "asset_name", "asset_type", "mac", "hostname", "vendor", "product",
    "description", "plant", "building", "production_line", "vlan",
)

# Prefijos de columnas con datos del activo en hojas de comunicaciones
SIDE_PREFIXES = {
    "source": ("source_", "from_"),
    "destination": ("destination_", "to_"),
}

MAC_PATTERN = re.compile(r"^([0-9a-f]{2}:){5}[0-9a-f]{2}$")
MAX_ERRORS = 100


@dataclass
class ImportResult:
    assets_created: int = 0
    assets_updated: int = 0
    communications_created: int = 0
    communications_skipped: int = 0
    rows_skipped: int = 0
    errors: list[str] = field(default_factory=list)

    def add_error(self, message: str) -> None:
        if len(self.errors) < MAX_ERRORS:
            self.errors.append(message)


class ExcelImportError(Exception):
    """El archivo no se puede importar de forma segura."""


class ExcelImporter:
    """Importa activos y comunicaciones y los COMBINA con el inventario actual.

    - Las comunicaciones que ya existen se omiten.
    - Los activos se identifican por IP (o por asset_code) y nunca se
      sobrescriben: solo se completan los campos que estén vacíos.
    - No depende de fórmulas: los activos se resuelven por IP.

    Formatos aceptados (se detectan por los encabezados de cada hoja):
    - Hoja de activos: columna 'ip' (+ asset_code, asset_name, planta, nave...).
    - Hoja de comunicaciones: 'source'/'destination' o 'from'/'to',
      protocol, puertos y opcionalmente from_asset_name, to_mac, etc.
    """

    def __init__(self, db: Session):
        self.db = db
        self.result = ImportResult()
        self._by_ip: dict[str, Asset] = {}
        self._by_code: dict[str, Asset] = {}
        self._next_number = 0
        self._existing_keys: set[tuple] = set()
        self._created_ids: set[int] = set()
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
            headers, rows = self._read_sheet(sheet)
            if {"source", "destination"} <= headers:
                communication_sheets.append((sheet.title, rows))
            elif "ip" in headers:
                asset_sheets.append((sheet.title, rows))
        workbook.close()

        if not asset_sheets and not communication_sheets:
            raise ExcelImportError(
                "No se encontró una hoja de activos (columna 'ip') ni de comunicaciones "
                "(columnas 'source'/'destination' o 'from'/'to')."
            )

        self._load_existing()
        try:
            for title, rows in asset_sheets:
                self._import_assets(title, rows)
            for title, rows in communication_sheets:
                self._import_communications(title, rows)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        return self.result

    # ---------- lectura ----------

    @staticmethod
    def _normalize_header(value) -> str:
        header = str(value).strip().lower().replace(" ", "_").replace("-", "_")
        return HEADER_ALIASES.get(header, header)

    @staticmethod
    def _clean(value) -> str:
        if value is None:
            return ""
        if isinstance(value, float) and value.is_integer():
            value = int(value)
        return str(value).strip()

    def _read_sheet(self, sheet) -> tuple[set[str], list[tuple[int, dict]]]:
        headers: list[str] | None = None
        rows: list[tuple[int, dict]] = []
        for row_number, values in enumerate(sheet.iter_rows(values_only=True), start=1):
            if values is None or all(v in (None, "") for v in values):
                continue
            if headers is None:
                headers = [self._normalize_header(v) if v is not None else "" for v in values]
                continue
            row = {
                header: self._clean(values[index])
                for index, header in enumerate(headers)
                if header and index < len(values)
            }
            rows.append((row_number, row))
        return set(headers or []), rows

    def _load_existing(self) -> None:
        for asset in self.db.scalars(select(Asset)):
            self._by_code[asset.asset_code] = asset
            if asset.ip:
                self._by_ip[asset.ip] = asset
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

    # ---------- normalización ----------

    @staticmethod
    def _parse_ip(value: str) -> tuple[str | None, bool]:
        """Devuelve (ip_normalizada, es_valida)."""
        if not value:
            return None, True
        try:
            return str(ipaddress.ip_address(value)), True
        except ValueError:
            return None, False

    @staticmethod
    def _parse_vlan(value: str) -> int | None:
        match = re.search(r"\d+", value or "")
        if match and 1 <= int(match.group()) <= 4094:
            return int(match.group())
        return None

    @staticmethod
    def _parse_mac(value: str) -> str | None:
        value = (value or "").lower().replace("-", ":")
        return value if MAC_PATTERN.match(value) else None

    def _asset_values(self, row: dict, prefixes: tuple[str, ...]) -> dict:
        def pick(*names):
            for prefix in prefixes:
                for name in names:
                    if row.get(prefix + name):
                        return row[prefix + name]
            return ""

        values = {name: pick(name) for name in ASSET_FIELDS}
        values["asset_name"] = values["asset_name"] or pick("name")
        values["asset_type"] = values["asset_type"] or pick("type")
        values["mac"] = self._parse_mac(values["mac"])
        values["vlan"] = self._parse_vlan(values["vlan"])
        return {key: (value if value != "" else None) for key, value in values.items()}

    # ---------- activos ----------

    def _create_asset(self, ip: str | None, values: dict, code: str | None = None) -> Asset:
        if not code or code in self._by_code:
            self._next_number += 1
            code = AssetService.format_code(self._next_number)
        else:
            self._next_number = max(self._next_number, AssetService.code_number(code))

        values = dict(values)
        values["asset_name"] = values.get("asset_name") or ip or code
        values["asset_type"] = values.get("asset_type") or "unknown"

        asset = Asset(asset_code=code, ip=ip, **values)
        self.db.add(asset)
        self.db.flush()

        self._by_code[code] = asset
        if ip:
            self._by_ip[ip] = asset
        self._created_ids.add(asset.id)
        self.result.assets_created += 1
        return asset

    def _fill(self, asset: Asset, values: dict, overwrite: bool = False) -> None:
        changed = False
        for name, value in values.items():
            if value is None:
                continue
            current = getattr(asset, name)
            # Un nombre igual a la IP se considera "sin nombre"
            is_empty = current in (None, "") or (name == "asset_name" and current == asset.ip)
            if (overwrite or is_empty) and current != value:
                setattr(asset, name, value)
                changed = True
        if changed and asset.id not in self._created_ids:
            self.result.assets_updated += 1

    def _import_assets(self, title: str, rows: list[tuple[int, dict]]) -> None:
        for row_number, row in rows:
            ip, valid = self._parse_ip(row.get("ip", ""))
            code = row.get("asset_code") or None
            if not valid:
                self.result.rows_skipped += 1
                self.result.add_error(f"{title} fila {row_number}: IP inválida '{row.get('ip')}'.")
                continue
            if not ip and not code:
                self.result.rows_skipped += 1
                self.result.add_error(f"{title} fila {row_number}: sin IP ni asset_code.")
                continue

            values = self._asset_values(row, ("",))
            asset = (self._by_code.get(code) if code else None) or (self._by_ip.get(ip) if ip else None)
            if asset is None:
                self._create_asset(ip, values, code)
            else:
                self._fill(asset, values)

    # ---------- comunicaciones ----------

    def _resolve(self, row: dict, side: str, title: str, row_number: int) -> Asset | None:
        label = "origen" if side == "source" else "destino"
        ip, valid = self._parse_ip(row.get(side, ""))
        if not valid:
            self.result.add_error(f"{title} fila {row_number}: IP de {label} inválida '{row.get(side)}'.")
            return None

        values = self._asset_values(row, SIDE_PREFIXES[side])
        code = row.get(f"{side}_asset") or None
        asset = self._by_ip.get(ip) if ip else None
        if asset is None and code:
            asset = self._by_code.get(code)

        if asset is None:
            if not ip:
                self.result.add_error(f"{title} fila {row_number}: el {label} no tiene IP ni un asset_code conocido.")
                return None
            asset = self._create_asset(ip, values)
            if side == "destination":
                # Los datos 'to_*' de muchos exports son copia de 'from_*';
                # si luego aparece como origen, se corrigen con sus propios datos.
                self._provisional_ids.add(asset.id)
            return asset

        if side == "source" and asset.id in self._provisional_ids:
            self._fill(asset, values, overwrite=True)
            self._provisional_ids.discard(asset.id)
        else:
            self._fill(asset, values)
        return asset

    def _import_communications(self, title: str, rows: list[tuple[int, dict]]) -> None:
        for row_number, row in rows:
            protocol = row.get("protocol", "").lower()
            if not protocol:
                self.result.rows_skipped += 1
                self.result.add_error(f"{title} fila {row_number}: falta el protocolo.")
                continue

            source = self._resolve(row, "source", title, row_number)
            destination = self._resolve(row, "destination", title, row_number)
            if source is None or destination is None:
                self.result.rows_skipped += 1
                continue
            if source.id == destination.id:
                self.result.rows_skipped += 1
                self.result.add_error(f"{title} fila {row_number}: origen y destino son el mismo activo.")
                continue

            source_port = row.get("source_port", "")
            destination_port = row.get("destination_port", "")
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
                    description=row.get("description") or None,
                )
            )
            self._existing_keys.add(key)
            self.result.communications_created += 1