import { memo } from "react";

function GroupNode({ data }) {
  return (
    <div className="group-node">
      <div className="group-node-header">
        <span>{data.label}</span>
        <small>{data.count} activos</small>
      </div>
    </div>
  );
}

export default memo(GroupNode);