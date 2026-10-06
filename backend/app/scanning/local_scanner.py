"""El 'escáner local': fila interna en la tabla agents que representa al propio
servidor (modo integrado). El usuario nunca la ve ni la configura.

Las redes permitidas viven en la base (las administra el usuario desde la
interfaz). El .env solo se usa como SEMILLA inicial si la base aún no tiene redes.
"""
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.config import get_scanner_settings
from app.models import Agent, AllowedNetwork
from app.scanning.targets import TargetMalformedError, parse_network

log = logging.getLogger("ot-scanner")

LOCAL_AGENT_UID = "local"


def get_or_create_local_scanner(db: Session) -> Agent:
    agent = db.scalar(
        select(Agent).options(selectinload(Agent.allowed_networks)).where(Agent.agent_uid == LOCAL_AGENT_UID)
    )
    if agent is None:
        agent = Agent(
            agent_uid=LOCAL_AGENT_UID,
            name="Escáner local (modo integrado)",
            description="Ejecuta nmap en el propio servidor.",
            token_hash="local-integrated-no-token",
            status="active",
        )
        db.add(agent)
        db.commit()
        db.refresh(agent)
    return agent


def seed_networks_if_empty(db: Session, agent: Agent) -> None:
    """Solo la primera vez: si no hay redes, las toma del .env como punto de partida.
    Si ya hay (porque el usuario las administra desde la UI), no toca nada.
    """
    if agent.allowed_networks:
        return
    for raw in get_scanner_settings().allowed_networks:
        try:
            cidr = str(parse_network(raw))
        except TargetMalformedError:
            log.warning("Red inválida en SCANNER_ALLOWED_NETWORKS, se ignora: %s", raw)
            continue
        db.add(AllowedNetwork(agent_id=agent.id, cidr=cidr, description="semilla (.env)"))
    db.commit()
    db.refresh(agent)


def ensure_local_scanner(db: Session) -> Agent:
    agent = get_or_create_local_scanner(db)
    seed_networks_if_empty(db, agent)
    return agent