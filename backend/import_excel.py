import sys
from pathlib import Path

from app.database.database import SessionLocal
from app.importers.excel_importer import ExcelImporter, ExcelImportError


def main():
    if len(sys.argv) != 2:
        print(
            "Usage: python import_excel.py "
            "/mnt/Linux/ot_assets_communication.code.xlsx"
        )
        sys.exit(1)

    excel_path = Path(sys.argv[1])

    db = SessionLocal()

    try:
        importer = ExcelImporter(db)

        result = importer.import_file(excel_path)

        print()
        print("=== IMPORT RESULT ===")
        print(
            f"Assets created: "
            f"{result.assets_created}"
        )
        print(
            f"Assets updated: "
            f"{result.assets_updated}"
        )
        print(
            f"Communications created: "
            f"{result.communications_created}"
        )
        print(
            f"Communications updated: "
            f"{result.communications_updated}"
        )
        print(
            f"Communications skipped: "
            f"{result.communications_skipped}"
        )
        print(f"Errors: {result.errors}")
        print("=====================")

    except ExcelImportError as exc:
        db.rollback()
        print()
        print(f"IMPORT ERROR: {exc}")
        sys.exit(1)

    except Exception as exc:
        db.rollback()
        print()
        print(f"UNEXPECTED ERROR: {exc}")
        sys.exit(1)

    finally:
        db.close()


if __name__ == "__main__":
    main()