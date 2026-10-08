"""Gestión de redes permitidas desde la interfaz, ahora con ubicación opcional
(planta/nave/línea/VLAN) que los activos descubiertos heredan.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.models import AllowedNetwork
from app.scanning.local_scanner import get_or_create_local_scanner
from app.schemas.network import NetworkCreate, NetworkResponse, NetworkUpdate

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
    net = AllowedNetwork(
        agent_id=agent.id, cidr=data.cidr, description=data.description,
        plant=data.plant, building=data.building,
        production_line=data.production_line, vlan=data.vlan,
    )
    db.add(net)
    db.commit()
    db.refresh(net)
    return net


@router.patch("/{network_id}", response_model=NetworkResponse)
def update_network(network_id: int, data: NetworkUpdate, db: Session = Depends(get_db)):
    net = db.scalar(select(AllowedNetwork).where(AllowedNetwork.id == network_id))
    if net is None:
        raise HTTPException(status_code=404, detail="Red no encontrada.")
    net.description = data.description
    net.plant = data.plant
    net.building = data.building
    net.production_line = data.production_line
    net.vlan = data.vlan
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