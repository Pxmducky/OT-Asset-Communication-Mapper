export const ASSET_TYPES = [
    { value: "controller", label: "PLC / Controlador" },
    { value: "HMI", label: "HMI" },
    { value: "engineering_station", label: "Estación de ingeniería" },
    { value: "server", label: "Servidor" },
    { value: "historian", label: "Historian" },
    { value: "computer", label: "Computadora" },
    { value: "IO_module", label: "Módulo I/O" },
    { value: "drive", label: "Variador" },
    { value: "OT_device", label: "Dispositivo OT" },
    { value: "switch", label: "Switch" },
    { value: "router", label: "Router" },
    { value: "firewall", label: "Firewall" },
    { value: "WAP", label: "Access point" },
    { value: "printer_scanner", label: "Impresora / Escáner" },
    { value: "IT_device", label: "Dispositivo IT" },
    { value: "unknown", label: "Desconocido" },
  ];
  
  export const TYPE_COLORS = {
    controller: "#f97316",
    HMI: "#a855f7",
    engineering_station: "#6366f1",
    server: "#3b82f6",
    historian: "#0ea5e9",
    computer: "#2563eb",
    IO_module: "#ea580c",
    drive: "#eab308",
    OT_device: "#14b8a6",
    switch: "#22c55e",
    router: "#16a34a",
    firewall: "#ef4444",
    WAP: "#06b6d4",
    printer_scanner: "#94a3b8",
    IT_device: "#64748b",
    unknown: "#475569",
  };
  
  // Para usar imágenes propias: copia los archivos a frontend/public/icons/
  // y agrega aquí el tipo. Ejemplo: controller: "/icons/plc.png"
  export const CUSTOM_ICONS = {};
  
  export const PROTOCOLS = [
    "s7", "s7plus", "cotp", "profinet", "modbus", "ethernetip", "cip", "opcua", "opcda",
    "dnp3", "iec104", "iec61850", "bacnet", "mqtt", "snmp", "snmp-v3", "http", "https",
    "ssh", "telnet", "rdp", "vnc", "smb", "dce-rpc", "netbios-ns", "dns", "ntp",
    "ldap", "kerberos", "ftp", "tftp", "dhcp", "syslog", "icmp", "other",
  ];
  
  export const GROUP_MODES = [
    { value: "location", label: "Planta / Nave / Línea" },
    { value: "plant", label: "Planta" },
    { value: "vlan", label: "VLAN" },
    { value: "subnet", label: "Subred /24" },
    { value: "type", label: "Tipo de activo" },
  ];
  
  export function typeLabel(value) {
    return ASSET_TYPES.find((type) => type.value === value)?.label ?? value ?? "Desconocido";
  }
  
  export function typeColor(value) {
    return TYPE_COLORS[value] ?? TYPE_COLORS.unknown;
  }