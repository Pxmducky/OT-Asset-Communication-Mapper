"""Perfiles de escaneo (viven en el servidor; el agente solo ejecuta).

Cada perfil define los argumentos de nmap SIN el objetivo y SIN el formato de
salida: el agente agrega '-oX -' (XML por stdout) y el objetivo al final. Afinar
un perfil se hace aquí, sin tocar los agentes desplegados.

Basado en los comandos del usuario y refinado: salida XML, rates conservadores
para OT, y scripts NSE que existen en nmap. Se añadieron tipos extra.
"""

PROFILES: dict[str, dict] = {
    "discovery": {
        "label": "Descubrimiento (solo hosts vivos)",
        # Barrido ARP sin escaneo de puertos: rápido y suave, ideal antes de un /24.
        "args": ["-sn", "-PR", "--max-rate", "100"],
    },
    "plc": {
        "label": "PLC / Controlador",
        "args": [
            "-sS", "-sV", "-O", "--reason", "-T2", "--max-rate", "40",
            "-p", "21,22,23,80,443,502,102,44818,3389",
            "--script", "banner,http-title,ssl-cert,s7-info,enip-info,modbus-discover",
        ],
    },
    "hmi": {
        "label": "HMI",
        "args": [
            "-sS", "-sV", "-T2", "--max-rate", "40",
            "-p", "21,23,80,443,502,102,44818",
            "--script", "s7-info,enip-info,modbus-discover,http-title",
        ],
    },
    "printers": {
        "label": "Impresoras / Escáneres",
        "args": [
            "-sS", "-sV", "-T3", "--max-rate", "100",
            "-p", "80,443,9100,515,161",
            "--script", "http-title,snmp-info",
        ],
    },
    "mes": {
        "label": "MES / Servidor de planta",
        "args": [
            "-sS", "-sV", "-O", "-T3", "--max-rate", "80",
            "-p", "80,443,135,139,445,3389,1433,3306",
            "--script", "smb-os-discovery,http-title",
        ],
    },
    "cnc": {
        "label": "CNC",
        "args": [
            "-sS", "-sV", "-T2", "--max-rate", "40",
            "-p", "21,23,80,443,3389,5900",
            "--script", "http-title",
        ],
    },
    # ---- tipos añadidos ----
    "switch": {
        "label": "Switch / Red gestionada",
        "args": [
            "-sS", "-sV", "-T3", "--max-rate", "100",
            "-p", "22,23,80,161,443",
            "--script", "snmp-info,snmp-interfaces,http-title",
        ],
    },
    "server": {
        "label": "Servidor / Historian",
        "args": [
            "-sS", "-sV", "-O", "-T3", "--max-rate", "80",
            "-p", "22,80,135,139,443,445,1433,3306,3389,5985",
            "--script", "smb-os-discovery,http-title,ssl-cert",
        ],
    },
    "drive": {
        "label": "Variador / Drive",
        "args": [
            "-sS", "-sV", "-T2", "--max-rate", "40",
            "-p", "80,161,443,502,44818",
            "--script", "modbus-discover,enip-info,snmp-info",
        ],
    },
    "camera": {
        "label": "Cámara IP",
        "args": [
            "-sS", "-sV", "-T3", "--max-rate", "80",
            "-p", "80,443,554,8000,8080,37777",
            "--script", "http-title,rtsp-methods",
        ],
    },
}


def profile_exists(name: str) -> bool:
    return name in PROFILES


def get_profile_args(name: str) -> list[str]:
    """Copia de los argumentos del perfil (sin objetivo ni salida)."""
    return list(PROFILES[name]["args"])


def list_profiles() -> list[dict]:
    return [{"value": name, "label": data["label"]} for name, data in PROFILES.items()]