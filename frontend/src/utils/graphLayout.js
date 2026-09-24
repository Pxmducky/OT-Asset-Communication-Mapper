import { MarkerType } from "@xyflow/react";

import { typeLabel } from "./constants";

const NODE_WIDTH = 150;
const NODE_HEIGHT = 118;
const GROUP_PADDING = 24;
const GROUP_HEADER = 46;
const GROUP_GAP = 70;
const MAX_ROW_WIDTH = 2800;

export function ipToNumber(ip) {
  if (!ip || !/^\d+\.\d+\.\d+\.\d+$/.test(ip)) return Number.MAX_SAFE_INTEGER;
  return ip.split(".").reduce((total, octet) => total * 256 + Number(octet), 0);
}

export function groupKey(asset, mode) {
  switch (mode) {
    case "plant":
      return asset.plant || "Sin planta asignada";
    case "vlan":
      return asset.vlan ? `VLAN ${asset.vlan}` : "Sin VLAN";
    case "subnet":
      return asset.ip && /^\d+\.\d+\.\d+\.\d+$/.test(asset.ip)
        ? `${asset.ip.split(".").slice(0, 3).join(".")}.0/24`
        : "Sin IPv4";
    case "type":
      return typeLabel(asset.asset_type);
    default: {
      const parts = [asset.plant, asset.building, asset.production_line];
      if (parts.every((part) => !part)) return "Sin ubicación asignada";
      return parts.map((part) => part || "—").join(" / ");
    }
  }
}

export function groupAssets(assets, mode) {
  const groups = new Map();
  for (const asset of assets) {
    const key = groupKey(asset, mode);
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(asset);
  }
  for (const members of groups.values()) {
    members.sort((a, b) => ipToNumber(a.ip) - ipToNumber(b.ip));
  }
  // Los grupos "Sin ..." van al final
  return [...groups.entries()].sort(([a], [b]) => {
    const aEmpty = a.startsWith("Sin "), bEmpty = b.startsWith("Sin ");
    if (aEmpty !== bEmpty) return aEmpty ? 1 : -1;
    return a.localeCompare(b, "es", { numeric: true });
  });
}

export function buildNodes(assets, groupMode) {
  const nodes = [];
  let x = 0;
  let y = 0;
  let rowHeight = 0;

  for (const [key, members] of groupAssets(assets, groupMode)) {
    const columns = Math.max(1, Math.ceil(Math.sqrt(members.length * 1.6)));
    const rows = Math.ceil(members.length / columns);
    const width = columns * NODE_WIDTH + GROUP_PADDING * 2;
    const height = rows * NODE_HEIGHT + GROUP_HEADER + GROUP_PADDING;

    if (x > 0 && x + width > MAX_ROW_WIDTH) {
      x = 0;
      y += rowHeight + GROUP_GAP;
      rowHeight = 0;
    }

    const groupId = `group:${key}`;
    nodes.push({
      id: groupId,
      type: "assetGroup",
      position: { x, y },
      data: { label: key, count: members.length },
      style: { width, height },
      selectable: false,
      zIndex: -1,
    });

    members.forEach((asset, index) => {
      nodes.push({
        id: String(asset.id),
        type: "asset",
        parentId: groupId,
        extent: "parent",
        position: {
          x: GROUP_PADDING + (index % columns) * NODE_WIDTH,
          y: GROUP_HEADER + Math.floor(index / columns) * NODE_HEIGHT,
        },
        data: { asset },
      });
    });

    x += width + GROUP_GAP;
    rowHeight = Math.max(rowHeight, height);
  }

  return nodes;
}

// Una sola línea por par de activos; las flechas indican el sentido
// y la etiqueta lista todos los protocolos entre ambos.
export function buildEdges(communications, visibleIds, selectedId, showLabels) {
  const pairs = new Map();

  for (const communication of communications) {
    const source = String(communication.source_asset_id);
    const target = String(communication.destination_asset_id);
    if (!visibleIds.has(source) || !visibleIds.has(target)) continue;

    const [a, b] = source < target ? [source, target] : [target, source];
    const key = `${a}|${b}`;
    if (!pairs.has(key)) pairs.set(key, { a, b, forward: false, backward: false, protocols: new Set() });

    const pair = pairs.get(key);
    if (source === a) pair.forward = true;
    else pair.backward = true;
    pair.protocols.add(communication.protocol);
  }

  const selected = selectedId ? String(selectedId) : null;

  return [...pairs.values()].map((pair) => {
    const highlighted = selected && (pair.a === selected || pair.b === selected);
    const color = highlighted ? "#f87171" : "#64748b";
    const marker = { type: MarkerType.ArrowClosed, color, width: 16, height: 16 };
    const protocols = [...pair.protocols].join(", ");

    return {
      id: `edge:${pair.a}|${pair.b}`,
      source: pair.forward ? pair.a : pair.b,
      target: pair.forward ? pair.b : pair.a,
      markerEnd: marker,
      markerStart: pair.forward && pair.backward ? marker : undefined,
      label: showLabels || highlighted ? protocols : undefined,
      labelStyle: { fill: "#e5e7eb", fontSize: 11 },
      labelBgStyle: { fill: "#111827" },
      labelBgPadding: [4, 2],
      animated: Boolean(highlighted),
      zIndex: highlighted ? 20 : 1,
      style: {
        stroke: color,
        strokeWidth: highlighted ? 2.2 : 1,
        opacity: selected && !highlighted ? 0.18 : 0.75,
      },
      data: { pair: [pair.a, pair.b], protocols },
    };
  });
}