from app.database.database import SessionLocal
from app.models import Asset, Communication


def main():
    db = SessionLocal()

    try:
        asset_a = Asset(
            asset_name="TEST-PLC-01",
            asset_type="PLC",
            ip="192.168.10.10",
            vendor="Siemens",
            product="S7-1500",
        )

        asset_b = Asset(
            asset_name="TEST-HMI-01",
            asset_type="HMI",
            ip="192.168.10.20",
            vendor="Siemens",
            product="Comfort Panel",
        )

        db.add_all([asset_a, asset_b])
        db.commit()

        db.refresh(asset_a)
        db.refresh(asset_b)

        communication = Communication(
            source_asset_id=asset_a.id,
            destination_asset_id=asset_b.id,
            protocol="S7",
            source_port=102,
            destination_port=102,
        )

        db.add(communication)
        db.commit()

        print(f"Source asset: {asset_a.id} - {asset_a.asset_name}")
        print(f"Destination asset: {asset_b.id} - {asset_b.asset_name}")
        print(
            f"Communication: "
            f"{communication.source_asset_id} -> "
            f"{communication.destination_asset_id}"
        )

    finally:
        db.close()


if __name__ == "__main__":
    main()