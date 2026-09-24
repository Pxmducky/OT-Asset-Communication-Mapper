import { useEffect } from "react";
import {
  Background,
  Controls,
  MiniMap,
  ReactFlow,
  useNodesState,
  useReactFlow,
} from "@xyflow/react";

import "@xyflow/react/dist/style.css";

import AssetNode from "./AssetNode";
import GroupNode from "./GroupNode";
import { MapHighlightContext } from "./mapHighlightContext";
import { typeColor } from "../utils/constants";

const nodeTypes = { asset: AssetNode, assetGroup: GroupNode };

function NetworkMap({ layoutNodes, edges, highlight, centerRequest, onSelectAsset, onEditAsset, onConnectAssets, onClearSelection }) {
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const { fitView, getInternalNode, setCenter, getZoom } = useReactFlow();

  // Nuevo layout (datos, agrupación o filtro): reinicia posiciones y encuadra
  useEffect(() => {
    setNodes(layoutNodes);
    const frame = requestAnimationFrame(() => fitView({ padding: 0.08, duration: 300 }));
    return () => cancelAnimationFrame(frame);
  }, [layoutNodes, setNodes, fitView]);

  // Centrar un activo elegido desde la lista
  useEffect(() => {
    if (!centerRequest) return;
    const node = getInternalNode(String(centerRequest.id));
    if (!node) return;
    const { x, y } = node.internals.positionAbsolute;
    setCenter(x + 75, y + 55, { zoom: Math.max(getZoom(), 1.1), duration: 400 });
  }, [centerRequest, getInternalNode, setCenter, getZoom]);

  return (
    <MapHighlightContext.Provider value={highlight}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        onNodesChange={onNodesChange}
        onNodeClick={(_, node) => node.type === "asset" && onSelectAsset(Number(node.id))}
        onNodeDoubleClick={(_, node) => node.type === "asset" && onEditAsset(Number(node.id))}
        onEdgeClick={(_, edge) => onSelectAsset(Number(edge.source))}
        onConnect={({ source, target }) => onConnectAssets(Number(source), Number(target))}
        onPaneClick={onClearSelection}
        minZoom={0.05}
        maxZoom={2.5}
        onlyRenderVisibleElements
        proOptions={{ hideAttribution: true }}
      >
        <Background color="#1f2937" gap={24} />
        <Controls />
        <MiniMap
          pannable
          zoomable
          nodeColor={(node) => (node.type === "asset" ? typeColor(node.data.asset.asset_type) : "#1f2937")}
          maskColor="rgba(0, 0, 0, 0.6)"
          style={{ background: "#0b0f14" }}
        />
      </ReactFlow>
    </MapHighlightContext.Provider>
  );
}

export default NetworkMap;