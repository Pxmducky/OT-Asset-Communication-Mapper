
import { useMemo, useState } from "react";


function AssetList({
  assets,
  selectedAsset,
  onSelect,
}) {
  const [search, setSearch] =
    useState("");


  const filteredAssets = useMemo(() => {
    const value =
      search
        .trim()
        .toLowerCase();

    if (!value) {
      return assets;
    }

    return assets.filter(
      (asset) =>
        asset.asset_name
          ?.toLowerCase()
          .includes(value) ||
        asset.asset_code
          ?.toLowerCase()
          .includes(value) ||
        asset.ip
          ?.toLowerCase()
          .includes(value) ||
        asset.asset_type
          ?.toLowerCase()
          .includes(value)
    );
  }, [assets, search]);


  return (
    <div className="asset-list">

      <div className="sidebar-header">

        <h2>
          Assets
        </h2>

        <span>
          {assets.length}
        </span>

      </div>


      <input
        className="search-input"
        type="text"
        placeholder="Buscar activo..."
        value={search}
        onChange={(event) =>
          setSearch(
            event.target.value
          )
        }
      />


      <div className="asset-items">

        {filteredAssets.map(
          (asset) => {

            const selected =
              selectedAsset?.id ===
              asset.id;

            return (
              <button
                key={asset.id}
                className={
                  selected
                    ? "asset-item selected"
                    : "asset-item"
                }
                onClick={() =>
                  onSelect(asset)
                }
              >

                <div className="asset-item-title">
                  {asset.asset_name}
                </div>

                <div className="asset-item-meta">
                  {asset.asset_type}
                </div>

                <div className="asset-item-ip">
                  {asset.ip || "Sin IP"}
                </div>

              </button>
            );
          }
        )}

      </div>

    </div>
  );
}


export default AssetList;
