import { CUSTOM_ICONS, typeColor } from "../utils/constants";

const STROKE = {
  fill: "none",
  stroke: "#fff",
  strokeWidth: 2.2,
  strokeLinecap: "round",
  strokeLinejoin: "round",
};
const DOT = { fill: "#fff" };

function Glyph({ type }) {
  switch (type) {
    case "controller": // PLC: rack con módulos y LEDs
      return (
        <g {...STROKE}>
          <rect x="8" y="12" width="32" height="24" rx="2" />
          <path d="M15 12v24M22 12v24M29 12v24" />
          <circle cx="11.5" cy="17" r="1.2" {...DOT} />
          <circle cx="11.5" cy="22" r="1.2" {...DOT} />
          <path d="M18 18h1M25 18h1M32 18h4M32 23h4M32 28h4" />
        </g>
      );
    case "HMI": // panel táctil con botones
      return (
        <g {...STROKE}>
          <rect x="7" y="10" width="34" height="26" rx="3" />
          <rect x="11" y="14" width="20" height="18" rx="1" />
          <circle cx="36" cy="17" r="1.5" {...DOT} />
          <circle cx="36" cy="23" r="1.5" {...DOT} />
          <circle cx="36" cy="29" r="1.5" {...DOT} />
          <path d="M14 27l4-5 3 3 5-6" />
        </g>
      );
    case "server": // servidor de rack
      return (
        <g {...STROKE}>
          <rect x="10" y="8" width="28" height="9" rx="1.5" />
          <rect x="10" y="19.5" width="28" height="9" rx="1.5" />
          <rect x="10" y="31" width="28" height="9" rx="1.5" />
          <circle cx="15" cy="12.5" r="1" {...DOT} />
          <circle cx="15" cy="24" r="1" {...DOT} />
          <circle cx="15" cy="35.5" r="1" {...DOT} />
          <path d="M24 12.5h9M24 24h9M24 35.5h9" />
        </g>
      );
    case "historian": // base de datos
      return (
        <g {...STROKE}>
          <ellipse cx="24" cy="12" rx="13" ry="4.5" />
          <path d="M11 12v24c0 2.5 5.8 4.5 13 4.5s13-2 13-4.5V12" />
          <path d="M11 20c0 2.5 5.8 4.5 13 4.5s13-2 13-4.5M11 28c0 2.5 5.8 4.5 13 4.5s13-2 13-4.5" />
        </g>
      );
    case "engineering_station": // monitor + engrane
      return (
        <g {...STROKE}>
          <rect x="7" y="9" width="34" height="22" rx="2" />
          <path d="M18 39h12M24 31v8" />
          <circle cx="24" cy="20" r="4" />
          <path d="M24 13v2.5M24 24.5V27M17 20h2.5M28.5 20H31" />
        </g>
      );
    case "computer":
    case "IT_device": // monitor
      return (
        <g {...STROKE}>
          <rect x="7" y="9" width="34" height="22" rx="2" />
          <path d="M18 39h12M24 31v8" />
          {type === "IT_device" && <path d="M13 15h14M13 20h20M13 25h10" />}
        </g>
      );
    case "IO_module": // módulo con bornes
      return (
        <g {...STROKE}>
          <rect x="13" y="7" width="22" height="34" rx="2" />
          <path d="M13 14h22M13 34h22" />
          <circle cx="19" cy="19" r="1.3" {...DOT} />
          <circle cx="19" cy="24" r="1.3" {...DOT} />
          <circle cx="19" cy="29" r="1.3" {...DOT} />
          <circle cx="29" cy="19" r="1.3" {...DOT} />
          <circle cx="29" cy="24" r="1.3" {...DOT} />
          <circle cx="29" cy="29" r="1.3" {...DOT} />
        </g>
      );
    case "drive": // variador con ventilador
      return (
        <g {...STROKE}>
          <rect x="11" y="7" width="26" height="34" rx="2" />
          <rect x="16" y="11" width="16" height="7" rx="1" />
          <circle cx="24" cy="30" r="6" />
          <path d="M24 24v12M18 30h12" />
        </g>
      );
    case "switch": // switch con puertos
      return (
        <g {...STROKE}>
          <rect x="5" y="17" width="38" height="14" rx="2" />
          <path d="M10 22v4M15 22v4M20 22v4M25 22v4M30 22v4" />
          <circle cx="37" cy="24" r="1.3" {...DOT} />
        </g>
      );
    case "router": // router con flechas
      return (
        <g {...STROKE}>
          <circle cx="24" cy="24" r="15" />
          <path d="M16 20h13l-3-3M32 28H19l3 3" />
        </g>
      );
    case "firewall": // muro de ladrillos
      return (
        <g {...STROKE}>
          <rect x="8" y="10" width="32" height="28" rx="1.5" />
          <path d="M8 19.3h32M8 28.6h32M20 10v9.3M30 19.3v9.3M18 28.6V38M28 10v9.3M14 19.3v9.3M34 28.6V38" />
        </g>
      );
    case "WAP": // access point
      return (
        <g {...STROKE}>
          <path d="M14 18a14 14 0 0 1 20 0M18 22.5a8 8 0 0 1 12 0" />
          <circle cx="24" cy="27" r="1.6" {...DOT} />
          <rect x="11" y="32" width="26" height="7" rx="3.5" />
        </g>
      );
    case "printer_scanner":
      return (
        <g {...STROKE}>
          <path d="M15 17V8h18v9" />
          <rect x="8" y="17" width="32" height="14" rx="2" />
          <rect x="15" y="27" width="18" height="12" />
          <path d="M19 32h10M19 35.5h7" />
        </g>
      );
    case "OT_device": // engrane industrial
      return (
        <g {...STROKE}>
          <circle cx="24" cy="24" r="6" />
          <path d="M24 9v5M24 34v5M9 24h5M34 24h5M13.4 13.4l3.5 3.5M31.1 31.1l3.5 3.5M13.4 34.6l3.5-3.5M31.1 16.9l3.5-3.5" />
        </g>
      );
    default: // desconocido
      return (
        <g {...STROKE}>
          <circle cx="24" cy="24" r="15" />
          <path d="M19.5 19.5a4.5 4.5 0 1 1 6.3 4.1c-1.2.6-1.8 1.4-1.8 2.7v1" />
          <circle cx="24" cy="32" r="1.3" {...DOT} />
        </g>
      );
  }
}

function AssetIcon({ type, size = 40 }) {
  const custom = CUSTOM_ICONS[type];
  if (custom) {
    return <img src={custom} width={size} height={size} alt={type} className="asset-icon-image" draggable={false} />;
  }

  return (
    <svg width={size} height={size} viewBox="0 0 48 48" aria-hidden="true">
      <rect x="1" y="1" width="46" height="46" rx="10" fill={typeColor(type)} />
      <Glyph type={type} />
    </svg>
  );
}

export default AssetIcon;