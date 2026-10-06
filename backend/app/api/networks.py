"""Gestión de redes permitidas desde la interfaz (tu punto 5).

El usuario agrega/quita las subredes que luego podrá escanear. Estas redes son
la fuente de verdad para validar cada objetivo.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.models import AllowedNetwork
from app.scanning.local_scanner import get_or_create_local_scanner
from app.schemas.network import NetworkCreate, NetworkResponse

router = APIRouter(prefix="/api/networks", tags=["Networks"])


@router.get("", response_model=list[NetworkResponse])
def list_networks(db: Session = Depends(get_db)):
    agent = get_or_create_local_scanner(db)
    return sorted(agent.allowed_networks, key=lambda n: n.id)


@router.post("", response_model=NetworkResponse, status_code=201)
def add_network(data: NetworkCreate, db: Session = Depends(get_db)):
    agent = get_or_create_local_scanner(db)
    if any(n.cidr == data.cidr for n in agent.allowed_networks):
        raise HTTPException(status_code=409, detail=f"La red {data.cidr} ya está registrada.")
    net = AllowedNetwork(agent_id=agent.id, cidr=data.cidr, description=data.description)
    db.add(net)
    db.commit()
    db.refresh(net)
    return net


@router.delete("/{network_id}", response_model=dict)
def remove_network(network_id: int, db: Session = Depends(get_db)):
    net = db.scalar(select(AllowedNetwork).where(AllowedNetwork.id == network_id))
    if net is None:
        raise HTTPException(status_code=404, detail="Red no encontrada.")
    db.delete(net)
    db.commit()
    return {"deleted": network_id}