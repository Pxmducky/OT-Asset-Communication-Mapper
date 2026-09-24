
import { useEffect, useMemo, useState } from "react";

import {
  Background,
  Controls,
  MiniMap,
  ReactFlow,
  useEdgesState,
  useNodesState,
} from "@xyflow/react";

import "@xyflow/react/dist/style.css";

import {
  assetApi,
  communicationApi,
} from "../services/api";

import AssetList from "../components/AssetList";
import AssetDetails from "../components/AssetDetails";


function MapperPage() {
  const [assets, setAssets] = useState([]);
  const [communications, setCommunications] = useState([]);

  const [selectedAsset, setSelectedAsset] =
    useState(null);

  const [loading, setLoading] = useState(true);

  const [error, setError] = useState(null);


  useEffect(() => {
    loadData();
  }, []);


  async function loadData() {
    try {
      setLoading(true);
      setError(null);

      const [
        assetsData,
        communicationsData,
      ] = await Promise.all([
        assetApi.getAll(),
        communicationApi.getAll(),
      ]);

      setAssets(assetsData);
      setCommunications(
        communicationsData
      );

      if (assetsData.length > 0) {
        setSelectedAsset(
          assetsData[0]
        );
      }

    } catch (err) {
      console.error(err);

      setError(
        "No fue posible cargar los datos del servidor."
      );

    } finally {
      setLoading(false);
    }
  }


  const nodes = useMemo(() => {
    return assets.map(
      (asset, index) => ({
        id: String(asset.id),

        position: {
          x: (index % 5) * 260,
          y: Math.floor(index / 5) * 160,
        },

        data: {
          label: (
            <div className="asset-node">
              <strong>
                {asset.asset_name}
              </strong>

              <span>
                {asset.asset_type}
              </span>

              <small>
                {asset.ip || "No IP"}
              </small>
            </div>
          ),
        },

        type: "default",
      })
    );
  }, [assets]);


  const edges = useMemo(() => {
    return communications
      .filter(
        (communication) =>
          communication.source_asset_id &&
          communication.destination_asset_id
      )
      .map(
        (communication) => ({
          id: `communication-${communication.id}`,

          source: String(
            communication.source_asset_id
          ),

          target: String(
            communication.destination_asset_id
          ),

          label:
            communication.protocol,

          animated: false,
        })
      );
  }, [communications]);


  function handleSelectAsset(asset) {
    setSelectedAsset(asset);
  }


  if (loading) {
    return (
      <div className="loading-screen">
        Cargando OT Asset Mapper...
      </div>
    );
  }


  if (error) {
    return (
      <div className="error-screen">
        <h2>Error</h2>

        <p>{error}</p>

        <button onClick={loadData}>
          Reintentar
        </button>
      </div>
    );
  }


  return (
    <div className="mapper">

      <header className="topbar">

        <div>
          <h1>
            OT Asset Mapper
          </h1>

          <span>
            Inventory & Communication Mapping
          </span>
        </div>

        <div className="topbar-stats">

          <div>
            <strong>
              {assets.length}
            </strong>

            <span>
              Assets
            </span>
          </div>

          <div>
            <strong>
              {communications.length}
            </strong>

            <span>
              Communications
            </span>
          </div>

        </div>

      </header>


      <main className="workspace">

        <aside className="sidebar">

          <AssetList
            assets={assets}
            selectedAsset={selectedAsset}
            onSelect={handleSelectAsset}
          />

        </aside>


        <section className="map-container">

          <ReactFlow
            nodes={nodes}
            edges={edges}
            fitView
          >

            <Background />

            <Controls />

            <MiniMap />

          </ReactFlow>

        </section>


        <aside className="details-panel">

          <AssetDetails
            asset={selectedAsset}
            communications={
              selectedAsset
                ? communications.filter(
                    (communication) =>
                      communication.source_asset_id ===
                        selectedAsset.id ||
                      communication.destination_asset_id ===
                        selectedAsset.id
                  )
                : []
            }
          />

        </aside>

      </main>

    </div>
  );
}


export default MapperPage;
