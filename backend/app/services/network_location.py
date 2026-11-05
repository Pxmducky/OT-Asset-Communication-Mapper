"""Ubicación de activos según los segmentos (redes permitidas).

Cada red dada de alta puede traer planta / nave / línea / VLAN. Un activo cuya
IP cae dentro de un segmento toma esos datos (el segmento más específico gana)
y queda ligado a él con asset.network_id.

- Alta o edición de un segmento → se reubican los activos que caen en él.
- Importación de Excel o aprobación de escaneo → se ubican los activos.
- Baja de un segmento → a sus activos se les quitan los datos que venían de
  ese segmento (solo si siguen iguales; lo que el usuario cambió a mano se
  respeta) y se reubican en otro segmento si caen en uno más amplio.
"""
import ipaddress
from types import SimpleNamespace

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AllowedNetwork, Asset

FIELDS = ("plant", "building", "production_line", "vlan")


def snapshot(net: AllowedNetwork) -> SimpleNamespace:
    """Copia de los valores del segmento (para limpiar después de editarlo)."""
    return SimpleNamespace(id=net.id, **{f: getattr(net, f) for f in FIELDS})


def _networks(db: Session, exclude_id: int | None = None) -> list[tuple]:
    out = []
    for net in db.scalars(select(AllowedNetwork)):
        if net.id == exclude_id:
            continue
        try:
            out.append((ipaddress.ip_network(net.cidr, strict=False), net))
        except ValueError:
            continue
    out.sort(key=lambda x: -x[0].prefixlen)  # más específico primero
    return out


def _chain(ip: str | None, nets: list[tuple]) -> list:
    """Segmentos que contienen la IP, del más específico al más amplio."""
    if not ip:
        return []
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return []
    return [net for network, net in nets if addr.version == network.version and addr in network]


def _in_network(ip: str | None, net: AllowedNetwork) -> bool:
    try:
        return ipaddress.ip_address(ip) in ipaddress.ip_network(net.cidr, strict=False)
    except (TypeError, ValueError):
        return False


def _clear(asset: Asset, source) -> bool:
    """Quita los datos que venían del segmento, si no fueron modificados."""
    changed = False
    for f in FIELDS:
        value = getattr(source, f)
        if value not in (None, "") and getattr(asset, f) == value:
            setattr(asset, f, None)
            changed = True
    if asset.network_id == source.id:
        asset.network_id = None
        changed = True
    return changed


def _apply(asset: Asset, chain: list) -> bool:
    """Cada campo lo da el segmento más específico que lo tenga definido."""
    changed = False
    for f in FIELDS:
        value = next((getattr(n, f) for n in chain if getattr(n, f) not in (None, "")), None)
        if value is not None and getattr(asset, f) != value:
            setattr(asset, f, value)
            changed = True
    if asset.network_id != chain[0].id:
        asset.network_id = chain[0].id
        changed = True
    return changed


def assign(db: Session, assets: list[Asset] | None = None, exclude_id: int | None = None) -> int:
    """Ubica los activos (todos si assets es None). Devuelve cuántos cambiaron."""
    nets = _networks(db, exclude_id)
    by_id = {net.id: net for _, net in nets}
    if assets is None:
        assets = db.scalars(select(Asset).where(Asset.ip.is_not(None))).all()

    changed = 0
    for asset in assets:
        chain = _chain(asset.ip, nets)
        touched = False
        if asset.network_id and all(n.id != asset.network_id for n in chain):
            old = by_id.get(asset.network_id)
            if old is not None:
                touched |= _clear(asset, old)
            else:
                asset.network_id = None
                touched = True
        if chain:
            touched |= _apply(asset, chain)
        changed += int(touched)
    return changed


def assign_one(db: Session, asset: Asset) -> bool:
    return assign(db, [asset]) > 0


def _affected(db: Session, net: AllowedNetwork) -> list[Asset]:
    """Activos dentro del segmento o ligados a él."""
    return [
        a for a in db.scalars(select(Asset).where(Asset.ip.is_not(None)))
        if a.network_id == net.id or _in_network(a.ip, net)
    ]


def on_network_saved(db: Session, net: AllowedNetwork, previous: SimpleNamespace | None = None) -> int:
    """Tras crear/editar un segmento: limpia los valores anteriores y reubica."""
    if previous is not None:
        for asset in _affected(db, net):
            _clear(asset, previous)
        db.flush()
    return assign(db)


def on_network_deleted(db: Session, net: AllowedNetwork) -> int:
    """Antes de borrar un segmento: quita sus datos de los activos y reubica."""
    affected = _affected(db, net)
    for asset in affected:
        _clear(asset, net)
    db.flush()
    assign(db, affected, exclude_id=net.id)
    return len(affected)