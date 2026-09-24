import { memo, useContext } from "react";
import { Handle, Position } from "@xyflow/react";

import AssetIcon from "./AssetIcon";
import { MapHighlightContext } from "./mapHighlightContext";

function AssetNode({ data }) {
  const { asset } = data;
  const { selectedId, neighborIds, matchIds } = useContext(MapHighlightContext);

  const id = String(asset.id);
  const isSelected = selectedId === id;
  const isNeighbor = neighborIds.has(id);
  const isMatch = matchIds.has(id);
  const isDimmed = selectedId !== null && !isSelected && !isNeighbor;

  const className = [
    "asset-node",
    isSelected && "is-selected",
    isNeighbor && "is-neighbor",
    isMatch && "is-match",
    isDimmed && "is-dimmed",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <div className={className} title={`${asset.asset_name}\n${asset.ip ?? "Sin IP"}\n${asset.asset_code}`}>
      <Handle type="target" position={Position.Top} />
      <AssetIcon type={asset.asset_type} size={42} />
      <strong>{asset.asset_name}</strong>
      <small>{asset.ip || "Sin IP"}</small>
      <Handle type="source" position={Position.Bottom} />
    </div>
  );
}

export default memo(AssetNode);