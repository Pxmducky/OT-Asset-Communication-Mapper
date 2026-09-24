
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Asset, Communication


ASSETS_REQUIRED_COLUMNS = {
    "asset_code",
    "asset_name",
    "asset_type",
    "ip",
    "mac",
    "hostname",
    "vendor",
    "product",
}

COMMUNICATIONS_REQUIRED_COLUMNS = {
    "source_asset",
    "destination_asset",
    "source",
    "destination",
    "protocol",
    "source_port",
    "destination_port",
    "source_name",
    "destination_name",
}


@dataclass
class ImportResult:
    assets_created: int = 0
    assets_updated: int = 0
    communications_created: int = 0
    communications_updated: int = 0
    communications_skipped: int = 0
    errors: int = 0


class ExcelImportError(Exception):
    """Raised when the Excel file cannot be imported safely."""


class ExcelImporter:
    def __init__(self, db: Session):
        self.db = db

    def import_file(self, file_path: str | Path) -> ImportResult:
        path = Path(file_path)

        if not path.exists():
            raise ExcelImportError(
                f"Excel file not found: {path}"
            )

        if path.suffix.lower() not in {".xlsx", ".xls"}:
            raise ExcelImportError(
                "The file must be an Excel workbook (.xlsx or .xls)."
            )

        try:
            workbook = pd.ExcelFile(path)
        except Exception as exc:
            raise ExcelImportError(
                f"Could not open Excel file: {exc}"
            ) from exc

        self._validate_sheets(workbook.sheet_names)

        try:
            assets_df = pd.read_excel(
                workbook,
                sheet_name="Assets",
                dtype=object,
            )

            communications_df = pd.read_excel(
                workbook,
                sheet_name="Communications",
                dtype=object,
            )
        except Exception as exc:
            raise ExcelImportError(
                f"Could not read Excel sheets: {exc}"
            ) from exc

        self._validate_columns(
            assets_df,
            ASSETS_REQUIRED_COLUMNS,
            "Assets",
        )

        self._validate_columns(
            communications_df,
            COMMUNICATIONS_REQUIRED_COLUMNS,
            "Communications",
        )

        result = ImportResult()

        try:
            self._import_assets(
                assets_df,
                result,
            )

            self._import_communications(
                communications_df,
                result,
            )

            self.db.commit()

        except Exception:
            self.db.rollback()
            raise

        return result

    @staticmethod
    def _validate_sheets(sheet_names: list[str]) -> None:
        required_sheets = {
            "Assets",
            "Communications",
        }

        missing = required_sheets - set(sheet_names)

        if missing:
            missing_text = ", ".join(sorted(missing))

            raise ExcelImportError(
                f"Missing required sheet(s): {missing_text}"
            )

    @staticmethod
    def _validate_columns(
        dataframe: pd.DataFrame,
        required_columns: set[str],
        sheet_name: str,
    ) -> None:
        actual_columns = set(dataframe.columns)

        missing = required_columns - actual_columns

        if missing:
            missing_text = ", ".join(sorted(missing))

            raise ExcelImportError(
                f"Sheet '{sheet_name}' is missing "
                f"required column(s): {missing_text}"
            )

    def _import_assets(
        self,
        dataframe: pd.DataFrame,
        result: ImportResult,
    ) -> None:
        for row_number, row in dataframe.iterrows():
            excel_row = row_number + 2

            asset_code = self._clean_required(
                row["asset_code"]
            )

            asset_name = self._clean_required(
                row["asset_name"]
            )

            asset_type = self._clean_required(
                row["asset_type"]
            )

            if not asset_code:
                raise ExcelImportError(
                    f"Assets row {excel_row}: "
                    "asset_code is required."
                )

            if not asset_name:
                raise ExcelImportError(
                    f"Assets row {excel_row}: "
                    "asset_name is required."
                )

            if not asset_type:
                raise ExcelImportError(
                    f"Assets row {excel_row}: "
                    "asset_type is required."
                )

            existing = self.db.scalar(
                select(Asset).where(
                    Asset.asset_code == asset_code
                )
            )

            values = {
                "asset_name": asset_name,
                "asset_type": asset_type,
                "ip": self._clean_optional(row["ip"]),
                "mac": self._clean_optional(row["mac"]),
                "hostname": self._clean_optional(
                    row["hostname"]
                ),
                "vendor": self._clean_optional(
                    row["vendor"]
                ),
                "product": self._clean_optional(
                    row["product"]
                ),
            }

            if existing:
                for field, value in values.items():
                    setattr(existing, field, value)

                result.assets_updated += 1

            else:
                asset = Asset(
                    asset_code=asset_code,
                    **values,
                )

                self.db.add(asset)

                result.assets_created += 1

        self.db.flush()

    def _import_communications(
        self,
        dataframe: pd.DataFrame,
        result: ImportResult,
    ) -> None:
        assets = self._load_assets_by_code()

        for row_number, row in dataframe.iterrows():
            excel_row = row_number + 2

            source_asset_code = self._clean_required(
                row["source_asset"]
            )

            destination_asset_code = self._clean_required(
                row["destination_asset"]
            )

            source = self._clean_required(
                row["source"]
            )

            destination = self._clean_required(
                row["destination"]
            )

            protocol = self._clean_required(
                row["protocol"]
            )

            if not source_asset_code:
                raise ExcelImportError(
                    f"Communications row {excel_row}: "
                    "source_asset is required."
                )

            if not destination_asset_code:
                raise ExcelImportError(
                    f"Communications row {excel_row}: "
                    "destination_asset is required."
                )

            if not source:
                raise ExcelImportError(
                    f"Communications row {excel_row}: "
                    "source is required."
                )

            if not destination:
                raise ExcelImportError(
                    f"Communications row {excel_row}: "
                    "destination is required."
                )

            if not protocol:
                raise ExcelImportError(
                    f"Communications row {excel_row}: "
                    "protocol is required."
                )

            source_asset = assets.get(source_asset_code)

            destination_asset = assets.get(
                destination_asset_code
            )

            if source_asset is None:
                raise ExcelImportError(
                    f"Communications row {excel_row}: "
                    f"source asset '{source_asset_code}' "
                    "does not exist in Assets."
                )

            if destination_asset is None:
                raise ExcelImportError(
                    f"Communications row {excel_row}: "
                    f"destination asset "
                    f"'{destination_asset_code}' "
                    "does not exist in Assets."
                )

            source_port = self._clean_port(
                row["source_port"]
            )

            destination_port = self._clean_port(
                row["destination_port"]
            )

            source_name = self._clean_optional(
                row["source_name"]
            )

            destination_name = self._clean_optional(
                row["destination_name"]
            )

            existing = self.db.scalar(
                select(Communication).where(
                    Communication.source_asset_id
                    == source_asset.id,
                    Communication.destination_asset_id
                    == destination_asset.id,
                    Communication.protocol
                    == protocol,
                    Communication.source_port
                    == source_port,
                    Communication.destination_port
                    == destination_port,
                )
            )

            values = {
                "source": source,
                "destination": destination,
                "source_name": source_name,
                "destination_name": destination_name,
            }

            if existing:
                for field, value in values.items():
                    setattr(existing, field, value)

                result.communications_updated += 1

            else:
                communication = Communication(
                    source_asset_id=source_asset.id,
                    destination_asset_id=destination_asset.id,
                    protocol=protocol,
                    source_port=source_port,
                    destination_port=destination_port,
                    **values,
                )

                self.db.add(communication)

                result.communications_created += 1

        self.db.flush()

    def _load_assets_by_code(self) -> dict[str, Asset]:
        assets = self.db.scalars(
            select(Asset)
        ).all()

        return {
            asset.asset_code: asset
            for asset in assets
        }

    @staticmethod
    def _clean_required(value) -> str:
        if pd.isna(value):
            return ""

        value = str(value).strip()

        if not value:
            return ""

        return value

    @staticmethod
    def _clean_optional(value) -> str | None:
        if pd.isna(value):
            return None

        value = str(value).strip()

        if not value:
            return None

        return value

    @staticmethod
    def _clean_port(value) -> str | None:
        """
        Keeps the original port representation.

        Examples:
            tcp/62917
            tcp/62917, tcp/53351, tcp/54760
            tcp/9100
            None
        """

        if pd.isna(value):
            return None

        value = str(value).strip()

        if not value:
            return None

        return value
