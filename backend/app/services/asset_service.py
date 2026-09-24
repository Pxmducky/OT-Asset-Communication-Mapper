from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.asset import Asset
from app.schemas.asset import AssetCreate, AssetUpdate

CODE_PREFIX = "AST-"
NON_NULLABLE_FIELDS = ("asset_code", "asset_name", "asset_type")


class AssetService:

    @staticmethod
    def get_all(db: Session, skip: int = 0, limit: int | None = None) -> list[Asset]:
        statement = select(Asset).order_by(Asset.id).offset(skip)
        if limit is not None:
            statement = statement.limit(limit)
        return list(db.scalars(statement).all())

    @staticmethod
    def get_by_id(db: Session, asset_id: int) -> Asset | None:
        return db.get(Asset, asset_id)

    @staticmethod
    def get_by_code(db: Session, asset_code: str) -> Asset | None:
        return db.scalar(select(Asset).where(Asset.asset_code == asset_code))

    @staticmethod
    def get_by_ip(db: Session, ip: str) -> Asset | None:
        return db.scalar(select(Asset).where(Asset.ip == ip))

    @staticmethod
    def count(db: Session) -> int:
        return db.scalar(select(func.count(Asset.id))) or 0

    # ---------- códigos AST-### ----------

    @staticmethod
    def format_code(number: int) -> str:
        return f"{CODE_PREFIX}{number:03d}"

    @staticmethod
    def code_number(code: str | None) -> int:
        if code and code.startswith(CODE_PREFIX) and code[len(CODE_PREFIX):].isdigit():
            return int(code[len(CODE_PREFIX):])
        return 0

    @staticmethod
    def max_code_number(db: Session) -> int:
        codes = db.scalars(select(Asset.asset_code).where(Asset.asset_code.like(f"{CODE_PREFIX}%"))).all()
        return max((AssetService.code_number(code) for code in codes), default=0)

    @staticmethod
    def next_code(db: Session) -> str:
        return AssetService.format_code(AssetService.max_code_number(db) + 1)

    # ---------- validaciones ----------

    @staticmethod
    def _ensure_unique_code(db: Session, code: str, asset_id: int | None = None) -> None:
        existing = AssetService.get_by_code(db, code)
        if existing is not None and existing.id != asset_id:
            raise ValueError(f"El código {code} ya está asignado a {existing.asset_name}.")

    @staticmethod
    def _ensure_unique_ip(db: Session, ip: str | None, asset_id: int | None = None) -> None:
        if not ip:
            return
        existing = AssetService.get_by_ip(db, ip)
        if existing is not None and existing.id != asset_id:
            raise ValueError(f"La IP {ip} ya está asignada a {existing.asset_name} ({existing.asset_code}).")

    # ---------- CRUD ----------

    @staticmethod
    def create(db: Session, data: AssetCreate) -> Asset:
        values = data.model_dump()
        code = values.pop("asset_code") or AssetService.next_code(db)

        AssetService._ensure_unique_code(db, code)
        AssetService._ensure_unique_ip(db, values["ip"])

        asset = Asset(asset_code=code, **values)
        db.add(asset)
        db.commit()
        db.refresh(asset)
        return asset

    @staticmethod
    def update(db: Session, asset: Asset, data: AssetUpdate) -> Asset:
        # exclude_unset distingue "no lo envié" de "lo quiero vacío" (null)
        changes = data.model_dump(exclude_unset=True)

        for field in NON_NULLABLE_FIELDS:
            if field in changes and changes[field] is None:
                raise ValueError(f"El campo {field} no puede quedar vacío.")

        if "asset_code" in changes:
            AssetService._ensure_unique_code(db, changes["asset_code"], asset.id)
        if "ip" in changes:
            AssetService._ensure_unique_ip(db, changes["ip"], asset.id)

        for field, value in changes.items():
            setattr(asset, field, value)

        db.commit()
        db.refresh(asset)
        return asset

    @staticmethod
    def delete(db: Session, asset: Asset) -> None:
        # Las comunicaciones del activo se eliminan en cascada
        db.delete(asset)
        db.commit()