import { useCallback, useEffect, useMemo, useState } from "react";
import { ReactFlowProvider } from "@xyflow/react";

import { assetApi, communicationApi, excelApi, getErrorMessage, graphApi } from "../services/api";
import { buildEdges, buildNodes, groupAssets } from "../utils/graphLayout";

import AssetDetails from "../components/AssetDetails";
import AssetForm from "../components/AssetForm";
import AssetList from "../components/AssetList";
import CommunicationForm from "../components/CommunicationForm";
import ImportResult from "../components/ImportResult";
import Modal from "../components/Modal";
import NetworkMap from "../components/NetworkMap";
import Toolbar from "../components/Toolbar";

const SEARCH_FIELDS = [
  "asset_code", "asset_name", "asset_type", "ip", "mac", "hostname", "vendor",
  "product", "plant", "building", "production_line", "vlan", "description",
];

function MapperPage() {
  const [assets, setAssets] = useState([]);
  const [communications, setCommunications] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(null);

  const [selectedId, setSelectedId] = useState(null);
  const [centerRequest, setCenterRequest] = useState(null);
  const [groupMode, setGroupMode] = useState("location");
  const [focusMode, setFocusMode] = useState(false);
  const [showLabels, setShowLabels] = useState(false);
  const [search, setSearch] = useState("");

  // dialog: { kind: "asset", asset } | { kind: "communication", communication, preset } | { kind: "import", result }
  const [dialog, setDialog] = useState(null);
  const [dialogError, setDialogError] = useState(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState(null);

  const loadData = useCallback(async () => {
    try {
      setLoadError(null);
      const data = await graphApi.get();
      setAssets(data.assets);
      setCommunications(data.communications);
    } catch (error) {
      setLoadError(getErrorMessage(error));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  useEffect(() => {
    if (!notice) return undefined;
    const timer = setTimeout(() => setNotice(null), 4000);
    return () => clearTimeout(timer);
  }, [notice]);

  // ---------- datos derivados ----------

  const assetsById = useMemo(() => new Map(assets.map((asset) => [asset.id, asset])), [assets]);

  const communicationsByAsset = useMemo(() => {
    const map = new Map();
    for (const communication of communications) {
      for (const id of [communication.source_asset_id, communication.destination_asset_id]) {
        if (!map.has(id)) map.set(id, []);
        map.get(id).push(communication);
      }
    }
    return map;
  }, [communications]);

  const commCounts = useMemo(
    () => new Map([...communicationsByAsset.entries()].map(([id, list]) => [id, list.length])),
    [communicationsByAsset]
  );

  const selectedAsset = selectedId ? assetsById.get(selectedId) ?? null : null;
  const selectedCommunications = useMemo(
    () => (selectedId ? communicationsByAsset.get(selectedId) ?? [] : []),
    [selectedId, communicationsByAsset]
  );

  const neighborIds = useMemo(() => {
    const ids = new Set();
    for (const c of selectedCommunications) {
      ids.add(String(c.source_asset_id));
      ids.add(String(c.destination_asset_id));
    }
    if (selectedId) ids.delete(String(selectedId));
    return ids;
  }, [selectedCommunications, selectedId]);

  const matchingAssets = useMemo(() => {
    const term = search.trim().toLowerCase();
    if (!term) return assets;
    return assets.filter((asset) =>
      SEARCH_FIELDS.some((field) => String(asset[field] ?? "").toLowerCase().includes(term))
    );
  }, [assets, search]);

  const matchIds = useMemo(
    () => (search.trim() ? new Set(matchingAssets.map((asset) => String(asset.id))) : new Set()),
    [matchingAssets, search]
  );

  const effectiveFocus = focusMode && selectedAsset !== null;

  const mapAssets = useMemo(() => {
    if (!effectiveFocus) return assets;
    return assets.filter((asset) => asset.id === selectedId || neighborIds.has(String(asset.id)));
  }, [assets, effectiveFocus, selectedId, neighborIds]);

  const layoutNodes = useMemo(() => buildNodes(mapAssets, groupMode), [mapAssets, groupMode]);

  const edges = useMemo(() => {
    const visible = new Set(mapAssets.map((asset) => String(asset.id)));
    return buildEdges(communications, visible, selectedId, showLabels);
  }, [communications, mapAssets, selectedId, showLabels]);

  const highlight = useMemo(
    () => ({ selectedId: selectedId ? String(selectedId) : null, neighborIds, matchIds }),
    [selectedId, neighborIds, matchIds]
  );

  const listGroups = useMemo(() => groupAssets(matchingAssets, groupMode), [matchingAssets, groupMode]);

  // ---------- selección ----------

  const selectAsset = useCallback((id) => setSelectedId(id), []);

  const selectAndCenter = useCallback((id) => {
    setSelectedId(id);
    setCenterRequest({ id, nonce: Date.now() });
  }, []);

  const clearSelection = useCallback(() => {
    setSelectedId(null);
    setFocusMode(false);
  }, []);

  // ---------- diálogos ----------

  const openDialog = useCallback((value) => {
    setDialogError(null);
    setDialog(value);
  }, []);

  const closeDialog = useCallback(() => setDialog(null), []);

  const editAssetById = useCallback((id) => openDialog({ kind: "asset", asset: assetsById.get(id) }), [assetsById, openDialog]);

  const newCommunication = useCallback(
    (preset = {}) => openDialog({ kind: "communication", communication: null, preset }),
    [openDialog]
  );

  const connectAssets = useCallback(
    (sourceId, destinationId) => newCommunication({ source_asset_id: sourceId, destination_asset_id: destinationId }),
    [newCommunication]
  );

  // ---------- CRUD ----------

  async function saveAsset(payload) {
    setBusy(true);
    setDialogError(null);
    try {
      const saved = dialog.asset ? await assetApi.update(dialog.asset.id, payload) : await assetApi.create(payload);
      await loadData();
      setDialog(null);
      selectAndCenter(saved.id);
      setNotice(dialog.asset ? "Activo actualizado." : `Activo ${saved.asset_code} creado.`);
    } catch (error) {
      setDialogError(getErrorMessage(error));
    } finally {
      setBusy(false);
    }
  }

  async function deleteAsset(asset) {
    const total = commCounts.get(asset.id) ?? 0;
    if (!window.confirm(`¿Eliminar ${asset.asset_name} (${asset.ip ?? "sin IP"})?\nTambién se eliminarán sus ${total} comunicaciones.`)) {
      return;
    }
    try {
      await assetApi.delete(asset.id);
      setSelectedId(null);
      setFocusMode(false);
      await loadData();
      setNotice("Activo eliminado.");
    } catch (error) {
      setNotice(getErrorMessage(error));
    }
  }

  async function saveCommunication(payload, createReverse) {
    setBusy(true);
    setDialogError(null);
    try {
      if (dialog.communication) {
        await communicationApi.update(dialog.communication.id, payload);
      } else {
        await communicationApi.create(payload);
        if (createReverse) {
          await communicationApi.create({
            ...payload,
            source_asset_id: payload.destination_asset_id,
            destination_asset_id: payload.source_asset_id,
            source_port: payload.destination_port,
            destination_port: payload.source_port,
          });
        }
      }
      await loadData();
      setDialog(null);
      setNotice("Comunicación guardada.");
    } catch (error) {
      setDialogError(getErrorMessage(error));
      await loadData(); // por si el sentido directo sí se guardó
    } finally {
      setBusy(false);
    }
  }

  async function deleteCommunication(communication) {
    const text = `${communication.source_name} → ${communication.destination_name} (${communication.protocol})`;
    if (!window.confirm(`¿Eliminar la comunicación ${text}?`)) return;
    try {
      await communicationApi.delete(communication.id);
      await loadData();
      setNotice("Comunicación eliminada.");
    } catch (error) {
      setNotice(getErrorMessage(error));
    }
  }

  // ---------- Excel ----------

  async function importExcel(file) {
    setBusy(true);
    try {
      const result = await excelApi.importFile(file);
      await loadData();
      openDialog({ kind: "import", result });
    } catch (error) {
      setNotice(`Error al importar: ${getErrorMessage(error)}`);
    } finally {
      setBusy(false);
    }
  }

  async function exportExcel() {
    setBusy(true);
    try {
      await excelApi.exportFile();
    } catch (error) {
      setNotice(`Error al exportar: ${getErrorMessage(error)}`);
    } finally {
      setBusy(false);
    }
  }

  // ---------- render ----------

  if (loading) return <div className="loading-screen">Cargando OT Asset Mapper…</div>;

  if (loadError) {
    return (
      <div className="error-screen">
        <h2>Error</h2>
        <p>{loadError}</p>
        <button type="button" className="button primary" onClick={loadData}>
          Reintentar
        </button>
      </div>
    );
  }

  return (
    <div className="mapper">
      <header className="topbar">
        <div>
          <h1>OT Asset Mapper</h1>
          <span>Inventario y mapa de comunicaciones</span>
        </div>
        <div className="topbar-stats">
          <div>
            <strong>{assets.length}</strong>
            <span>Activos</span>
          </div>
          <div>
            <strong>{communications.length}</strong>
            <span>Comunicaciones</span>
          </div>
          <div>
            <strong>{edges.length}</strong>
            <span>Enlaces en mapa</span>
          </div>
        </div>
      </header>

      <Toolbar
        groupMode={groupMode}
        onGroupModeChange={setGroupMode}
        focusMode={effectiveFocus}
        onFocusModeChange={setFocusMode}
        canFocus={selectedAsset !== null}
        showLabels={showLabels}
        onShowLabelsChange={setShowLabels}
        onImport={importExcel}
        onExport={exportExcel}
        onNewCommunication={() => newCommunication(selectedId ? { source_asset_id: selectedId } : {})}
        busy={busy}
      />

      <main className="workspace">
        <aside className="sidebar">
          <AssetList
            groups={listGroups}
            total={assets.length}
            selectedId={selectedId}
            search={search}
            onSearchChange={setSearch}
            onSelect={selectAndCenter}
            onCreate={() => openDialog({ kind: "asset", asset: null })}
            commCounts={commCounts}
          />
        </aside>

        <section className="map-container">
          <ReactFlowProvider>
            <NetworkMap
              layoutNodes={layoutNodes}
              edges={edges}
              highlight={highlight}
              centerRequest={centerRequest}
              onSelectAsset={selectAsset}
              onEditAsset={editAssetById}
              onConnectAssets={connectAssets}
              onClearSelection={clearSelection}
            />
          </ReactFlowProvider>
        </section>

        <aside className="details-panel">
          <AssetDetails
            asset={selectedAsset}
            communications={selectedCommunications}
            assetsById={assetsById}
            onEdit={(asset) => openDialog({ kind: "asset", asset })}
            onDelete={deleteAsset}
            onAddCommunication={(asset) => newCommunication({ source_asset_id: asset.id })}
            onEditCommunication={(communication) => openDialog({ kind: "communication", communication })}
            onDeleteCommunication={deleteCommunication}
            onSelectAsset={selectAndCenter}
          />
        </aside>
      </main>

      {notice && <div className="toast">{notice}</div>}

      {dialog?.kind === "asset" && (
        <Modal title={dialog.asset ? `Editar ${dialog.asset.asset_name}` : "Nuevo activo"} onClose={closeDialog} width={760}>
          <AssetForm
            asset={dialog.asset}
            assets={assets}
            onSubmit={saveAsset}
            onCancel={closeDialog}
            busy={busy}
            serverError={dialogError}
          />
        </Modal>
      )}

      {dialog?.kind === "communication" && (
        <Modal title={dialog.communication ? "Editar comunicación" : "Nueva comunicación"} onClose={closeDialog}>
          <CommunicationForm
            communication={dialog.communication}
            preset={dialog.preset}
            assets={assets}
            onSubmit={saveCommunication}
            onCancel={closeDialog}
            busy={busy}
            serverError={dialogError}
          />
      </Modal>
      )}
{dialog?.kind === "import" && (
        <Modal title="Resultado de la importación" onClose={closeDialog} width={560}>
          <ImportResult result={dialog.result} onClose={closeDialog} />
        </Modal>
      )}
    </div>
  );
}

export default MapperPage;
