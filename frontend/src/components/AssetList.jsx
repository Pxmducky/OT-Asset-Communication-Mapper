import { useState } from "react";

import AssetIcon from "./AssetIcon";

function AssetList({ groups, total, selectedId, search, onSearchChange, onSelect, onCreate, commCounts }) {
  const [collapsed, setCollapsed] = useState(() => new Set());

  function toggle(key) {
    setCollapsed((current) => {
      const next = new Set(current);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  const shown = groups.reduce((sum, [, members]) => sum + members.length, 0);

  return (
    <div className="asset-list">
      <div className="sidebar-header">
        <h2>Activos</h2>
        <span>{search ? `${shown} de ${total}` : total}</span>
      </div>

      <button type="button" className="button primary full" onClick={onCreate}>
        + Nuevo activo
      </button>

      <input
        className="search-input"
        type="search"
        placeholder="Buscar IP, nombre, MAC, planta…"
        value={search}
        onChange={(event) => onSearchChange(event.target.value)}
      />

      <div className="asset-items">
        {groups.map(([key, members]) => (
          <section key={key} className="asset-group">
            <button type="button" className="asset-group-header" onClick={() => toggle(key)}>
              <span>{collapsed.has(key) ? "▸" : "▾"}</span>
              <strong>{key}</strong>
              <small>{members.length}</small>
            </button>

            {!collapsed.has(key) &&
              members.map((asset) => (
                <button
                  type="button"
                  key={asset.id}
                  className={`asset-item ${selectedId === asset.id ? "selected" : ""}`}
                  onClick={() => onSelect(asset.id)}
                >
                  <AssetIcon type={asset.asset_type} size={28} />
                  <div>
                    <div className="asset-item-title">{asset.asset_name}</div>
                    <div className="asset-item-meta">
                      {asset.ip || "Sin IP"} · {commCounts.get(asset.id) ?? 0} com.
                    </div>
                  </div>
                </button>
              ))}
          </section>
        ))}
        {groups.length === 0 && <p className="empty">Sin resultados.</p>}
      </div>
    </div>
  );
}

export default AssetList;