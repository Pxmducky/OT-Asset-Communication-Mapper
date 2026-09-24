import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.database import Base, get_db
from app.main import app

engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)


@event.listens_for(engine, "connect")
def enable_foreign_keys(dbapi_connection, connection_record):
    dbapi_connection.execute("PRAGMA foreign_keys=ON")


TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)


@pytest.fixture()
def client():
    Base.metadata.create_all(engine)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)


def new_asset(client, ip, name="PLC-01", **extra):
    payload = {
        "asset_name": name, "asset_type": "controller", "ip": ip, "vlan": 10,
        "plant": "Planta 1", "building": "Nave A", "production_line": "Línea 3", **extra,
    }
    response = client.post("/api/assets", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def test_asset_validation(client):
    assert client.post("/api/assets", json={"asset_name": "X", "asset_type": "HMI", "ip": "1.2.3"}).status_code == 422
    first = new_asset(client, "10.0.0.1")
    assert first["asset_code"] == "AST-001"
    assert client.post("/api/assets", json={**first, "asset_code": None}).status_code == 409  # IP repetida


def test_update_can_clear_field_and_rename_propagates(client):
    plc = new_asset(client, "10.0.0.1", mac="AA-BB-CC-DD-EE-FF")
    hmi = new_asset(client, "10.0.0.2", name="HMI-01")
    assert plc["mac"] == "aa:bb:cc:dd:ee:ff"

    communication = client.post("/api/communications", json={
        "source_asset_id": hmi["id"], "destination_asset_id": plc["id"], "protocol": "S7", "destination_port": "tcp/102",
    }).json()
    assert communication["protocol"] == "s7"

    client.put(f"/api/assets/{plc['id']}", json={"mac": None, "asset_name": "PLC-LINEA3"})
    assert client.get(f"/api/assets/{plc['id']}").json()["mac"] is None
    assert client.get(f"/api/communications/{communication['id']}").json()["destination_name"] == "PLC-LINEA3"


def test_duplicate_and_self_communication(client):
    a = new_asset(client, "10.0.0.1")
    b = new_asset(client, "10.0.0.2")
    payload = {"source_asset_id": a["id"], "destination_asset_id": b["id"], "protocol": "modbus"}
    assert client.post("/api/communications", json=payload).status_code == 201
    assert client.post("/api/communications", json=payload).status_code == 409
    assert client.post("/api/communications", json={**payload, "destination_asset_id": a["id"]}).status_code == 409


def test_graph_returns_everything_and_delete_cascades(client):
    hub = new_asset(client, "10.0.0.1")
    for i in range(2, 1203):
        peer = new_asset(client, f"10.0.{i // 250}.{i % 250 + 1}", name=f"N{i}")
        client.post("/api/communications", json={
            "source_asset_id": peer["id"], "destination_asset_id": hub["id"], "protocol": "snmp",
        })
    graph = client.get("/api/graph").json()
    assert len(graph["communications"]) == 1201

    client.delete(f"/api/assets/{hub['id']}")
    assert client.get("/api/communications/count").json()["count"] == 0


def test_excel_round_trip_skips_existing(client):
    a = new_asset(client, "10.0.0.1")
    b = new_asset(client, "10.0.0.2", name="SCADA")
    client.post("/api/communications", json={
        "source_asset_id": a["id"], "destination_asset_id": b["id"], "protocol": "opcua",
    })
    exported = client.get("/api/excel/export")
    assert exported.status_code == 200

    files = {"file": ("inv.xlsx", exported.content, "application/octet-stream")}
    result = client.post("/api/excel/import", files=files).json()
    assert result["communications_created"] == 0
    assert result["communications_skipped"] == 1
    assert result["assets_created"] == 0