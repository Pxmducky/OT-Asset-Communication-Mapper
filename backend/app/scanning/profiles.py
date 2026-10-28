"""Perfiles de escaneo (viven en el servidor; el agente solo ejecuta).

Cada perfil define los argumentos de nmap SIN el objetivo y SIN el formato de
salida: el agente agrega '-oX -' (XML por stdout) y el objetivo al final. Afinar
un perfil se hace aquí, sin tocar los agentes desplegados.

Basado en los comandos del usuario y refinado: salida XML, rates conservadores
para OT, y scripts NSE que existen en nmap. Se añadieron tipos extra.
"""
PROFILES: dict[str, dict] = {

    # ============================================================
    # 1. DISCOVERY
    # ============================================================
    "discovery": {
        "label": "Descubrimiento (solo hosts vivos)",
        "args": [
            "-sn",
            "-PR",
            "-PS22,80,443,102,502,3389,44818",
            "-PA80,443,102,502,44818",
            "--max-rate", "100",
        ],
    },

    # ============================================================
    # 2. GENERAL
    # ============================================================
    "general": {
        "label": "Descubrir red / IP (general)",

        # Escaneo TCP general.
        # Su objetivo es obtener evidencia suficiente para decidir
        # qué perfil especializado aplicar posteriormente.
        "args": [
            "-sS",
            "-sV",
            "-T3",
            "--max-rate", "100",

            "-p",
            (
                "21,22,23,80,102,135,139,443,445,"
                "502,515,554,631,1433,1883,2222,3306,"
                "3389,4840,5900,8000,8080,9100,"
                "20000,34964,37777,44818"
            ),

            "--script",
            (
                "banner,"
                "http-title,"
                "smb-os-discovery,"
                "s7-info,"
                "modbus-discover,"
                "enip-info,"
                "ssl-cert,"
                "rtsp-methods"
            ),
        ],

        # UDP separado para no confundir SNMP/BACnet con TCP.
        "udp_args": [
            "-sU",
            "-sV",
            "-T2",
            "--max-rate", "40",

            "-p",
            "161,47808",

            "--script",
            "snmp-info",
        ],
    },

    # ============================================================
    # 3. PLC
    # ============================================================
    "plc": {
        "label": "PLC / Controlador",

        "args": [
            "-sS",
            "-sV",
            "-T2",
            "--max-rate", "40",

            "-p",
            "21,22,23,80,102,443,502,3389,44818",

            "--script",
            (
                "banner,"
                "http-title,"
                "ssl-cert,"
                "s7-info,"
                "enip-info,"
                "modbus-discover"
            ),
        ],
    },

    # ============================================================
    # 4. HMI
    # ============================================================
    "hmi": {
        "label": "HMI",

        "args": [
            "-sS",
            "-sV",
            "-T2",
            "--max-rate", "40",

            "-p",
            "21,22,23,80,102,443,502,3389,5900,44818",

            "--script",
            (
                "banner,"
                "http-title,"
                "ssl-cert,"
                "s7-info,"
                "enip-info,"
                "modbus-discover"
            ),
        ],
    },

    # ============================================================
    # 5. PRINTERS
    # ============================================================
    "printers": {
        "label": "Impresoras / Escáneres",

        "args": [
            "-sS",
            "-sV",
            "-T3",
            "--max-rate", "80",

            "-p",
            "80,443,515,631,9100",

            "--script",
            (
                "banner,"
                "http-title,"
                "ssl-cert"
            ),
        ],

        "udp_args": [
            "-sU",
            "-sV",
            "-T2",
            "--max-rate", "40",

            "-p",
            "161",

            "--script",
            "snmp-info",
        ],
    },

    # ============================================================
    # 6. MES
    # ============================================================
    "mes": {
        "label": "MES / Servidor de planta",

        "args": [
            "-sS",
            "-sV",
            "-T3",
            "--max-rate", "80",

            "-p",
            (
                "22,80,135,139,443,445,"
                "1433,1883,3306,3389,4840"
            ),

            "--script",
            (
                "banner,"
                "http-title,"
                "smb-os-discovery,"
                "ssl-cert"
            ),
        ],
    },

    # ============================================================
    # 7. CNC
    # ============================================================
    "cnc": {
        "label": "CNC",

        "args": [
            "-sS",
            "-sV",
            "-T2",
            "--max-rate", "40",

            "-p",
            "21,22,23,80,443,2222,3389,5900",

            "--script",
            (
                "banner,"
                "http-title,"
                "ssl-cert"
            ),
        ],
    },

    # ============================================================
    # 8. SWITCH
    # ============================================================
    "switch": {
        "label": "Switch / Red gestionada",

        "args": [
            "-sS",
            "-sV",
            "-T3",
            "--max-rate", "80",

            "-p",
            "22,23,80,443",

            "--script",
            (
                "banner,"
                "http-title,"
                "ssl-cert"
            ),
        ],

        # SNMP realmente utiliza UDP/161.
        "udp_args": [
            "-sU",
            "-sV",
            "-T2",
            "--max-rate", "40",

            "-p",
            "161",

            "--script",
            "snmp-info,snmp-interfaces",
        ],
    },

    # ============================================================
    # 9. SERVER / HISTORIAN
    # ============================================================
    "server": {
        "label": "Servidor / Historian",

        "args": [
            "-sS",
            "-sV",
            "-T3",
            "--max-rate", "80",

            "-p",
            (
                "22,80,135,139,443,445,"
                "1433,1883,3306,3389,4840,5985"
            ),

            "--script",
            (
                "banner,"
                "smb-os-discovery,"
                "http-title,"
                "ssl-cert"
            ),
        ],
    },

    # ============================================================
    # 10. DRIVE
    # ============================================================
    "drive": {
        "label": "Variador / Drive",

        "args": [
            "-sS",
            "-sV",
            "-T2",
            "--max-rate", "40",

            "-p",
            "80,443,502,44818",

            "--script",
            (
                "banner,"
                "http-title,"
                "ssl-cert,"
                "modbus-discover,"
                "enip-info"
            ),
        ],

        "udp_args": [
            "-sU",
            "-sV",
            "-T2",
            "--max-rate", "40",

            "-p",
            "161",

            "--script",
            "snmp-info",
        ],
    },

    # ============================================================
    # 11. CAMERA
    # ============================================================
    "camera": {
        "label": "Cámara IP",

        "args": [
            "-sS",
            "-sV",
            "-T3",
            "--max-rate", "80",

            "-p",
            "80,443,554,8000,8080,37777",

            "--script",
            (
                "banner,"
                "http-title,"
                "ssl-cert,"
                "rtsp-methods"
            ),
        ],
    },

    # ============================================================
    # 12. ROBOT
    # ============================================================
    "robot": {
        "label": "Robot (FANUC/ABB/KUKA)",

        "args": [
            "-sS",
            "-sV",
            "-T2",
            "--max-rate", "40",

            "-p",
            "21,22,80,443,2222,3389,44818,5900",

            "--script",
            (
                "banner,"
                "http-title,"
                "ssl-cert,"
                "enip-info"
            ),
        ],
    },

    # ============================================================
    # 13. I/O REMOTE
    # ============================================================
    "io_remote": {
        "label": "I/O remota / Gateway de campo",

        "args": [
            "-sS",
            "-sV",
            "-T2",
            "--max-rate", "40",

            "-p",
            "80,102,443,502,2222,44818",

            "--script",
            (
                "banner,"
                "http-title,"
                "ssl-cert,"
                "modbus-discover,"
                "enip-info,"
                "s7-info"
            ),
        ],

        "udp_args": [
            "-sU",
            "-sV",
            "-T2",
            "--max-rate", "40",

            "-p",
            "161",

            "--script",
            "snmp-info",
        ],
    },

    # ============================================================
    # 14. INSTRUMENT
    # ============================================================
    "instrument": {
        "label": "Instrumento / Báscula / Lector",

        "args": [
            "-sS",
            "-sV",
            "-T3",
            "--max-rate", "60",

            "-p",
            "23,80,443,502,9100",

            "--script",
            (
                "banner,"
                "http-title,"
                "ssl-cert,"
                "modbus-discover"
            ),
        ],

        "udp_args": [
            "-sU",
            "-sV",
            "-T2",
            "--max-rate", "40",

            "-p",
            "161",

            "--script",
            "snmp-info",
        ],
    },

    # ============================================================
    # 15. SCADA
    # ============================================================
    "scada": {
        "label": "SCADA / Servidor OPC",

        "args": [
            "-sS",
            "-sV",
            "-T3",
            "--max-rate", "80",

            "-p",
            (
                "22,80,135,139,443,445,"
                "1433,1883,3306,3389,4840,5985"
            ),

            "--script",
            (
                "banner,"
                "http-title,"
                "smb-os-discovery,"
                "ssl-cert"
            ),
        ],
    },

    # ============================================================
    # 16. UPS
    # ============================================================
    "ups": {
        "label": "UPS / PDU",

        "args": [
            "-sS",
            "-sV",
            "-T3",
            "--max-rate", "60",

            "-p",
            "80,443",

            "--script",
            (
                "banner,"
                "http-title,"
                "ssl-cert"
            ),
        ],

        "udp_args": [
            "-sU",
            "-sV",
            "-T2",
            "--max-rate", "40",

            "-p",
            "161",

            "--script",
            "snmp-info",
        ],
    },

    # ============================================================
    # 17. WAP
    # ============================================================
    "wap": {
        "label": "Access Point / Wi-Fi industrial",

        "args": [
            "-sS",
            "-sV",
            "-T3",
            "--max-rate", "80",

            "-p",
            "22,23,80,443",

            "--script",
            (
                "banner,"
                "http-title,"
                "ssl-cert"
            ),
        ],

        "udp_args": [
            "-sU",
            "-sV",
            "-T2",
            "--max-rate", "40",

            "-p",
            "161",

            "--script",
            "snmp-info",
        ],
    },

    # ============================================================
    # 18. EWON
    # ============================================================
    "ewon": {
        "label": "Ewon / Router de acceso remoto",

        "args": [
            "-sS",
            "-sV",
            "-T3",
            "--max-rate", "60",

            "-p",
            "80,443,1194",

            "--script",
            (
                "banner,"
                "http-title,"
                "ssl-cert"
            ),
        ],
    },

    # ============================================================
    # 19. mGUARD
    # ============================================================
    "mguard": {
        "label": "mGuard (Phoenix Contact)",

        "args": [
            "-sS",
            "-sV",
            "-T3",
            "--max-rate", "60",

            "-p",
            "22,80,443",

            "--script",
            (
                "banner,"
                "ssl-cert,"
                "http-title"
            ),
        ],

        "udp_args": [
            "-sU",
            "-sV",
            "-T2",
            "--max-rate", "40",

            "-p",
            "161",

            "--script",
            "snmp-info",
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

def get_profile_udp_args(name: str) -> list[str]:
    """Args de la pasada UDP del perfil, o lista vacía si no tiene."""
    return list(PROFILES.get(name, {}).get("udp_args", []))