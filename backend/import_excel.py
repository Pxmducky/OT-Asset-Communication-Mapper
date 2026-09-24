import sys
from pathlib import Path

from app.database.database import SessionLocal
from app.database.models import create_tables
from app.importers.excel_importer import ExcelImporter, ExcelImportError


def main():
    if len(sys.argv) != 2:
        print("Uso: python import_excel.py /mnt/Linux/ot_assets_communication.code.xlsx")
        sys.exit(1)

    create_tables()
    db = SessionLocal()
    try:
        result = ExcelImporter(db).import_file(Path(sys.argv[1]))
    except ExcelImportError as exc:
        print(f"\nERROR DE IMPORTACIÓN: {exc}")
        sys.exit(1)
    finally:
        db.close()

    print("\n=== RESULTADO ===")
    print(f"Activos creados:            {result.assets_created}")
    print(f"Activos completados:        {result.assets_updated}")
    print(f"Comunicaciones creadas:     {result.communications_created}")
    print(f"Comunicaciones existentes:  {result.communications_skipped}")
    print(f"Filas omitidas:             {result.rows_skipped}")
    for error in result.errors:
        print(f"  - {error}")


if __name__ == "__main__":
    main()