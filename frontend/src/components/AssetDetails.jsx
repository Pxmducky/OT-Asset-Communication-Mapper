import AssetIcon from "./AssetIcon";
import { typeLabel } from "../utils/constants";

function DetailRow({ label, value }) {
  return (
    <div className="detail-row">
      <span>{label}</span>
      <strong>{value || "—"}</strong>
    </div>
  );
}

function CommunicationItem({ communication, outgoing, peer, onSelectAsset, onEdit, onDelete }) {
  const ports = [communication.source_port, communication.destination_port].some(Boolean)
    ? `${communication.source_port || "*"} → ${communication.destination_port || "*"}`
    : "sin puertos";

  return (
    <div className="connection-item">
      <span className={`direction ${outgoing ? "outgoing" : "incoming"}`}>{outgoing ? "→" : "←"}</span>

      <button type="button" className="connection-peer" onClick={() => peer && onSelectAsset(peer.id)}>
        {peer && <AssetIcon type={peer.asset_type} size={26} />}
        <div>
          <strong>{peer?.asset_name ?? "?"}</strong>
          <small>
            {peer?.ip ?? "Sin IP"} · <b>{communication.protocol}</b> · {ports}
          </small>
          {communication.description && <small className="connection-note">{communication.description}</small>}
        </div>
      </button>

      <div className="connection-actions">
        <button type="button" className="icon-button" title="Editar" onClick={() => onEdit(communication)}>
          ✎
        </button>
        <button type="button" className="icon-button danger" title="Eliminar" onClick={() => onDelete(communication)}>
          🗑
        </button>
      </div>
    </div>
  );
}

function AssetDetails({
  asset,
  communications,
  assetsById,
  onEdit,
  onDelete,
  onAddCommunication,
  onEditCommunication,
  onDeleteCommunication,
  onSelectAsset,
}) {
  if (!asset) {
    return (
      <div className="empty-details">
        <p>Selecciona un activo en el mapa o en la lista para ver sus datos y comunicaciones.</p>
        <p className="hint">
          Tip: arrastra desde el punto inferior de un activo hasta otro para crear una comunicación.
        </p>
      </div>
    );
  }

  const outgoing = communications.filter((c) => c.source_asset_id === asset.id);
  const incoming = communications.filter((c) => c.destination_asset_id === asset.id);
  const protocols = [...new Set(communications.map((c) => c.protocol))].sort();

  const itemProps = { onSelectAsset, onEdit: onEditCommunication, onDelete: onDeleteCommunication };

  return (
    <div className="asset-details">
      <div className="details-header">
        <AssetIcon type={asset.asset_type} size={56} />
        <div>
          <span className="asset-type">{typeLabel(asset.asset_type)}</span>
          <h2>{asset.asset_name}</h2>
          <span className="asset-code">{asset.asset_code}</span>
        </div>
      </div>

      <div className="details-actions">
        <button type="button" className="button secondary" onClick={() => onEdit(asset)}>
          Editar
        </button>
        <button type="button" className="button danger" onClick={() => onDelete(asset)}>
          Eliminar
        </button>
      </div>

      {asset.description && <p className="asset-description">{asset.description}</p>}

      <section className="details-section">
        <h3>Ubicación</h3>
        <DetailRow label="Planta" value={asset.plant} />
        <DetailRow label="Nave" value={asset.building} />
        <DetailRow label="Línea" value={asset.production_line} />
      </section>

      <section className="details-section">
        <h3>Red</h3>
        <DetailRow label="IP" value={asset.ip} />
        <DetailRow label="MAC" value={asset.mac} />
        <DetailRow label="VLAN" value={asset.vlan} />
        <DetailRow label="Hostname" value={asset.hostname} />
      </section>

      <section className="details-section">
        <h3>Equipo</h3>
        <DetailRow label="Fabricante" value={asset.vendor} />
        <DetailRow label="Producto" value={asset.product} />
      </section>

      <section className="details-section">
        <div className="section-title">
          <h3>Comunicaciones</h3>
          <button type="button" className="button primary small" onClick={() => onAddCommunication(asset)}>
            + Agregar
          </button>
        </div>

        <div className="communication-summary">
          <div>
            <strong>{outgoing.length}</strong>
            <span>Salientes</span>
          </div>
          <div>
            <strong>{incoming.length}</strong>
            <span>Entrantes</span>
          </div>
          <div>
            <strong>{protocols.length}</strong>
            <span>Protocolos</span>
          </div>
        </div>

        {protocols.length > 0 && (
          <div className="protocol-tags">
            {protocols.map((protocol) => (
              <span key={protocol}>{protocol}</span>
            ))}
          </div>
        )}

        {outgoing.length > 0 && <h4>Salientes</h4>}
        {outgoing.map((c) => (
          <CommunicationItem key={c.id} communication={c} outgoing peer={assetsById.get(c.destination_asset_id)} {...itemProps} />
        ))}

        {incoming.length > 0 && <h4>Entrantes</h4>}
        {incoming.map((c) => (
          <CommunicationItem key={c.id} communication={c} outgoing={false} peer={assetsById.get(c.source_asset_id)} {...itemProps} />
        ))}

        {communications.length === 0 && <p className="empty">Este activo no tiene comunicaciones.</p>}
      </section>
    </div>
  );
}

export default AssetDetails;