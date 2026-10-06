from sqlalchemy import text
from sqlalchemy.engine import Engine

# Columnas nuevas de la Fase 1 en la tabla 'assets'.
# SQLite solo permite ADD COLUMN (no DROP/ALTER de columnas), así que esto es
# idempotente: solo agrega las que falten. Las tablas nuevas las crea create_all().
_ASSET_COLUMNS = {
    "status": "VARCHAR(20) NOT NULL DEFAULT 'confirmed'",
    "confidence": "INTEGER",
    "discovery_source": "VARCHAR(20) NOT NULL DEFAULT 'manual'",
    "last_seen": "DATETIME",
    "os": "VARCHAR(255)",
}


def run_lightweight_migrations(engine: Engine) -> None:
    """Agrega a tablas ya existentes las columnas nuevas que falten (solo SQLite).

    create_all() crea las tablas nuevas, pero nunca modifica una tabla que ya
    existe. Por eso las columnas nuevas de 'assets' se agregan aquí: si la columna
    ya está, no se toca; los registros existentes toman el DEFAULT.
    """
    with engine.begin() as connection:
        tables = {
            row[0]
            for row in connection.execute(text("SELECT name FROM sqlite_master WHERE type = 'table'"))
        }
        if "assets" not in tables:
            return  # BD nueva: create_all ya creó 'assets' con todas las columnas

        existing = {row[1] for row in connection.execute(text("PRAGMA table_info(assets)"))}
        for column, ddl in _ASSET_COLUMNS.items():
            if column not in existing:
                connection.execute(text(f"ALTER TABLE assets ADD COLUMN {column} {ddl}"))