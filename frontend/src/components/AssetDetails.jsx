
function AssetDetails({
  asset,
  communications,
}) {
  if (!asset) {
    return (
      <div className="empty-details">
        <p>
          Selecciona un activo
          para ver sus detalles.
        </p>
      </div>
    );
  }


  const outgoing =
    communications.filter(
      (communication) =>
        communication.source_asset_id ===
        asset.id
    );


  const incoming =
    communications.filter(
      (communication) =>
        communication.destination_asset_id ===
        asset.id
    );


  return (
    <div className="asset-details">

      <div className="details-header">

        <span className="asset-type">
          {asset.asset_type}
        </span>

        <h2>
          {asset.asset_name}
        </h2>

        <span className="asset-code">
          {asset.asset_code}
        </span>

      </div>


      <section className="details-section">

        <h3>
          Identificación
        </h3>

        <DetailRow
          label="IP"
          value={asset.ip}
        />

        <DetailRow
          label="MAC"
          value={asset.mac}
        />

        <DetailRow
          label="Hostname"
          value={asset.hostname}
        />

        <DetailRow
          label="Fabricante"
          value={asset.vendor}
        />

        <DetailRow
          label="Producto"
          value={asset.product}
        />

      </section>


      <section className="details-section">

        <h3>
          Comunicaciones
        </h3>

        <div className="communication-summary">

          <div>
            <strong>
              {outgoing.length}
            </strong>

            <span>
              Salientes
            </span>
          </div>

          <div>
            <strong>
              {incoming.length}
            </strong>

            <span>
              Entrantes
            </span>
          </div>

        </div>

      </section>


      <section className="details-section">

        <h3>
          Conexiones
        </h3>

        <div className="connection-list">

          {communications.map(
            (communication) => {

              const outgoing =
                communication.source_asset_id ===
                asset.id;

              return (
                <div
                  className="connection-item"
                  key={
                    communication.id
                  }
                >

                  <span
                    className={
                      outgoing
                        ? "direction outgoing"
                        : "direction incoming"
                    }
                  >
                    {outgoing
                      ? "→"
                      : "←"}
                  </span>

                  <div>

                    <strong>
                      {outgoing
                        ? communication.destination_name
                        : communication.source_name}
                    </strong>

                    <small>
                      {communication.protocol}
                    </small>

                  </div>

                </div>
              );
            }
          )}

        </div>

      </section>

    </div>
  );
}


function DetailRow({
  label,
  value,
}) {
  return (
    <div className="detail-row">

      <span>
        {label}
      </span>

      <strong>
        {value || "—"}
      </strong>

    </div>
  );
}


export default AssetDetails;
