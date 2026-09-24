from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.asset import Asset
from app.models.communication import Communication
from app.schemas.communication import (
    CommunicationCreate,
    CommunicationUpdate,
)


class CommunicationService:

    @staticmethod
    def get_all(
        db: Session,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Communication]:

        statement = (
            select(Communication)
            .order_by(Communication.id)
            .offset(skip)
            .limit(limit)
        )

        return list(
            db.scalars(statement).all()
        )

    @staticmethod
    def get_by_id(
        db: Session,
        communication_id: int,
    ) -> Communication | None:

        statement = select(
            Communication
        ).where(
            Communication.id == communication_id
        )

        return db.scalar(statement)

    @staticmethod
    def count(
        db: Session,
    ) -> int:

        statement = select(
            func.count(Communication.id)
        )

        return db.scalar(statement) or 0

    @staticmethod
    def get_for_asset(
        db: Session,
        asset_id: int,
    ) -> list[Communication]:

        statement = (
            select(Communication)
            .where(
                (
                    Communication.source_asset_id
                    == asset_id
                )
                |
                (
                    Communication.destination_asset_id
                    == asset_id
                )
            )
            .order_by(
                Communication.id
            )
        )

        return list(
            db.scalars(statement).all()
        )

    @staticmethod
    def create(
        db: Session,
        data: CommunicationCreate,
    ) -> Communication:

        source_asset = db.scalar(
            select(Asset).where(
                Asset.id
                == data.source_asset_id
            )
        )

        if source_asset is None:
            raise ValueError(
                "Source asset not found."
            )

        destination_asset = db.scalar(
            select(Asset).where(
                Asset.id
                == data.destination_asset_id
            )
        )

        if destination_asset is None:
            raise ValueError(
                "Destination asset not found."
            )

        existing = db.scalar(
            select(Communication).where(
                Communication.source_asset_id
                == data.source_asset_id,
                Communication.destination_asset_id
                == data.destination_asset_id,
                Communication.protocol
                == data.protocol,
                Communication.source_port
                == data.source_port,
                Communication.destination_port
                == data.destination_port,
            )
        )

        if existing is not None:
            raise ValueError(
                "Communication already exists."
            )

        communication = Communication(
            source_asset_id=data.source_asset_id,
            destination_asset_id=data.destination_asset_id,
            source=data.source,
            destination=data.destination,
            protocol=data.protocol,
            source_port=data.source_port,
            destination_port=data.destination_port,
            source_name=data.source_name,
            destination_name=data.destination_name,
        )

        db.add(communication)
        db.commit()
        db.refresh(communication)

        return communication

    @staticmethod
    def update(
        db: Session,
        communication: Communication,
        data: CommunicationUpdate,
    ) -> Communication:

        if data.source_asset_id is not None:

            source_asset = db.scalar(
                select(Asset).where(
                    Asset.id
                    == data.source_asset_id
                )
            )

            if source_asset is None:
                raise ValueError(
                    "Source asset not found."
                )

            communication.source_asset_id = (
                data.source_asset_id
            )

        if data.destination_asset_id is not None:

            destination_asset = db.scalar(
                select(Asset).where(
                    Asset.id
                    == data.destination_asset_id
                )
            )

            if destination_asset is None:
                raise ValueError(
                    "Destination asset not found."
                )

            communication.destination_asset_id = (
                data.destination_asset_id
            )

        if data.source is not None:
            communication.source = data.source

        if data.destination is not None:
            communication.destination = (
                data.destination
            )

        if data.protocol is not None:
            communication.protocol = (
                data.protocol
            )

        if data.source_port is not None:
            communication.source_port = (
                data.source_port
            )

        if data.destination_port is not None:
            communication.destination_port = (
                data.destination_port
            )

        if data.source_name is not None:
            communication.source_name = (
                data.source_name
            )

        if data.destination_name is not None:
            communication.destination_name = (
                data.destination_name
            )

        db.commit()
        db.refresh(communication)

        return communication

    @staticmethod
    def delete(
        db: Session,
        communication: Communication,
    ) -> None:

        db.delete(communication)
        db.commit()