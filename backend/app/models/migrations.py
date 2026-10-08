from sqlalchemy import text
from sqlalchemy.engine import Engine

_ASSET_COLUMNS = {
    "status": "VARCHAR(20) NOT NULL DEFAULT 'confirmed'",
    "confidence": "INTEGER",
    "discovery_source": "VARCHAR(20) NOT NULL DEFAULT 'manual'",
    "last_seen": "DATETIME",
    "os": "VARCHAR(255)",
}

_ALLOWED_NETWORK_COLUMNS = {
    "plant": "VARCHAR(100)",
    "building": "VARCHAR(100)",
    "production_line": "VARCHAR(100)",
    "vlan": "INTEGER",
}


def _add_missing(connection, table: str, columns: dict) -> None:
    existing = {row[1] for row in connection.execute(text(f"PRAGMA table_info({table})"))}
    for column, ddl in columns.items():
        if column not in existing:
            connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))


def run_lightweight_migrations(engine: Engine) -> None:
    """Agrega columnas nuevas que falten a tablas ya existentes (solo SQLite)."""
    with engine.begin() as connection:
        tables = {
            row[0]
            for row in connection.execute(text("SELECT name FROM sqlite_master WHERE type = 'table'"))
        }
        if "assets" in tables:
            _add_missing(connection, "assets", _ASSET_COLUMNS)
        if "allowed_networks" in tables:
            _add_missing(connection, "allowed_networks", _ALLOWED_NETWORK_COLUMNS)