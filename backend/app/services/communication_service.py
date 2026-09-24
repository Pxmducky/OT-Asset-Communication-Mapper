from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models.asset import Asset
from app.models.communication import Communication
from app.schemas.communication import CommunicationCreate, CommunicationUpdate

KEY_FIELDS = ("source_asset_id", "destination_asset_id", "protocol", "source_port", "destination_port")


class CommunicationService:

    @staticmethod
    def _base_query():
        # selectinload evita una consulta por fila al leer IP/nombre de cada extremo
        return select(Communication).options(
            selectinload(Communication.source_asset),
            selectinload(Communication.destination_asset),
        )

    @staticmethod
    def get_all(db: Session, skip: int = 0, limit: int | None = None) -> list[Communication]:
        statement = CommunicationService._base_query().order_by(Communication.id).offset(skip)
        if limit is not None:
            statement = statement.limit(limit)
        return list(db.scalars(statement).all())

    @staticmethod
    def get_by_id(db: Session, communication_id: int) -> Communication | None:
        return db.scalar(CommunicationService._base_query().where(Communication.id == communication_id))

    @staticmethod
    def count(db: Session) -> int:
        return db.scalar(select(func.count(Communication.id))) or 0

    @staticmethod
    def get_for_asset(db: Session, asset_id: int) -> list[Communication]:
        statement = (
            CommunicationService._base_query()
            .where(
                or_(
                    Communication.source_asset_id == asset_id,
                    Communication.destination_asset_id == asset_id,
                )
            )
            .order_by(Communication.id)
        )
        return list(db.scalars(statement).all())

    @staticmethod
    def exists(
        db: Session,
        source_asset_id: int,
        destination_asset_id: int,
        protocol: str,
        source_port: str,
        destination_port: str,
        exclude_id: int | None = None,
    ) -> bool:
        statement = select(Communication.id).where(
            Communication.source_asset_id == source_asset_id,
            Communication.destination_asset_id == destination_asset_id,
            Communication.protocol == protocol,
            Communication.source_port == source_port,
            Communication.destination_port == destination_port,
        )
        if exclude_id is not None:
            statement = statement.where(Communication.id != exclude_id)
        return db.scalar(statement) is not None

    @staticmethod
    def _validate_endpoints(db: Session, source_asset_id: int, destination_asset_id: int) -> None:
        if source_asset_id == destination_asset_id:
            raise ValueError("El origen y el destino no pueden ser el mismo activo.")
        if db.get(Asset, source_asset_id) is None:
            raise ValueError("El activo origen no existe.")
        if db.get(Asset, destination_asset_id) is None:
            raise ValueError("El activo destino no existe.")

    @staticmethod
    def create(db: Session, data: CommunicationCreate) -> Communication:
        values = data.model_dump()
        CommunicationService._validate_endpoints(db, values["source_asset_id"], values["destination_asset_id"])

        if CommunicationService.exists(db, **{key: values[key] for key in KEY_FIELDS}):
            raise ValueError("Esa comunicación ya existe (mismo origen, destino, protocolo y puertos).")

        communication = Communication(**values)
        db.add(communication)
        db.commit()
        return CommunicationService.get_by_id(db, communication.id)

    @staticmethod
    def update(db: Session, communication: Communication, data: CommunicationUpdate) -> Communication:
        changes = data.model_dump(exclude_unset=True)

        for field in ("source_asset_id", "destination_asset_id", "protocol"):
            if field in changes and changes[field] is None:
                raise ValueError(f"El campo {field} no puede quedar vacío.")

        merged = {key: changes.get(key, getattr(communication, key)) for key in KEY_FIELDS}
        CommunicationService._validate_endpoints(db, merged["source_asset_id"], merged["destination_asset_id"])

        if CommunicationService.exists(db, **merged, exclude_id=communication.id):
            raise ValueError("Ya existe otra comunicación idéntica.")

        for field, value in changes.items():
            setattr(communication, field, value)

        db.commit()
        return CommunicationService.get_by_id(db, communication.id)

    @staticmethod
    def delete(db: Session, communication: Communication) -> None:
        db.delete(communication)
        db.commit()