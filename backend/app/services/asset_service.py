from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.asset import Asset
from app.schemas.asset import AssetCreate, AssetUpdate


class AssetService:

    @staticmethod
    def get_all(
        db: Session,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Asset]:
        statement = (
            select(Asset)
            .order_by(Asset.id)
            .offset(skip)
            .limit(limit)
        )

        return list(
            db.scalars(statement).all()
        )

    @staticmethod
    def get_by_id(
        db: Session,
        asset_id: int,
    ) -> Asset | None:
        statement = select(Asset).where(
            Asset.id == asset_id
        )

        return db.scalar(statement)

    @staticmethod
    def get_by_code(
        db: Session,
        asset_code: str,
    ) -> Asset | None:
        statement = select(Asset).where(
            Asset.asset_code == asset_code
        )

        return db.scalar(statement)

    @staticmethod
    def count(
        db: Session,
    ) -> int:
        statement = select(
            func.count(Asset.id)
        )

        return db.scalar(statement) or 0

    @staticmethod
    def create(
        db: Session,
        data: AssetCreate,
    ) -> Asset:

        existing = AssetService.get_by_code(
            db,
            data.asset_code,
        )

        if existing is not None:
            raise ValueError(
                f"Asset code already exists: "
                f"{data.asset_code}"
            )

        asset = Asset(
            asset_code=data.asset_code,
            asset_name=data.asset_name,
            asset_type=data.asset_type,
            ip=data.ip,
            mac=data.mac,
            hostname=data.hostname,
            vendor=data.vendor,
            product=data.product,
        )

        db.add(asset)
        db.commit()
        db.refresh(asset)

        return asset

    @staticmethod
    def update(
        db: Session,
        asset: Asset,
        data: AssetUpdate,
    ) -> Asset:

        if (
            data.asset_code is not None
            and data.asset_code != asset.asset_code
        ):
            existing = AssetService.get_by_code(
                db,
                data.asset_code,
            )

            if (
                existing is not None
                and existing.id != asset.id
            ):
                raise ValueError(
                    f"Asset code already exists: "
                    f"{data.asset_code}"
                )

            asset.asset_code = data.asset_code

        if data.asset_name is not None:
            asset.asset_name = data.asset_name

        if data.asset_type is not None:
            asset.asset_type = data.asset_type

        if data.ip is not None:
            asset.ip = data.ip

        if data.mac is not None:
            asset.mac = data.mac

        if data.hostname is not None:
            asset.hostname = data.hostname

        if data.vendor is not None:
            asset.vendor = data.vendor

        if data.product is not None:
            asset.product = data.product

        db.commit()
        db.refresh(asset)

        return asset

    @staticmethod
    def delete(
        db: Session,
        asset: Asset,
    ) -> None:

        db.delete(asset)
        db.commit()