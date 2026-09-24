from pydantic import BaseModel


class ExcelImportResponse(BaseModel):
    assets_created: int
    assets_updated: int
    communications_created: int
    communications_skipped: int
    rows_skipped: int
    errors: list[str]