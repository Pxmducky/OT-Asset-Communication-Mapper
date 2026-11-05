"""Perfiles de escaneo (viven en el servidor; el agente solo ejecuta).

Cada perfil define los argumentos de nmap SIN el objetivo y SIN el formato de
salida: el ejecutor agrega '-oX -' (XML por stdout) y el objetivo al final.

V2: argumentos comunes y conservadores para OT (COMMON_SAFE) + puertos y
scripts específicos por tipo. La pasada UDP (udp_args) es opcional y solo se
usa como segunda opinión. Puertos y scripts son puntos de partida: deben
validarse contra los modelos reales del laboratorio/planta.

V2: el perfil "general" se ARMA SOLO con la unión de puertos y scripts de
todos los perfiles especializados. Cada vez que se mejora o agrega un perfil
(INSYS, PLC, HMI…), el escaneo general lo incluye automáticamente.
Los perfiles de equipos Windows agregan nbstat (nombre NetBIOS y MAC aun en
redes ruteadas).
"""

COMMON_SAFE = [
    "-sS",
    "-sV",
    "--version-light",
    "-T2",
    "--reason",
    "--max-rate", "30",
]


def tcp_profile(label, ports, scripts="banner,http-title,ssl-cert"):
    return {
        "label": label,
        "args": COMMON_SAFE + [
            "-p", ports,
            "--script", scripts,
        ],
    }


def udp_profile(profile, ports="161", scripts="snmp-info"):
    profile["udp_args"] = [
        "-sU", "-sV", "-T2",
        "--reason",
        "--max-rate", "15",
        "-p", ports,
        "--script", scripts,
    ]
    return profile


PROFILES: dict[str, dict] = {
    "discovery": {
        "label": "Descubrimiento (solo hosts vivos)",
        "args": [
            "-sn", "-PE", "-PP", "-PS22,80,443,102,502,44818",
            "-PA80,443,102,502,44818",
            "--max-rate", "50",
        ],
    },

    # "general" se construye al final con build_general()
    "general": {"label": "Descubrimiento general", "args": []},

    "plc": tcp_profile(
        "PLC / Controlador",
        "21,22,23,80,102,443,502,44818",
        "banner,http-title,ssl-cert,s7-info,enip-info,modbus-discover"
    ),

    "hmi": tcp_profile(
        "HMI / Panel de operador",
        "21,22,23,80,102,135,139,443,445,502,1883,3389,4840,"
        "5900,5985,8080,8443,44818",
        "banner,http-title,http-headers,ssl-cert,smb-os-discovery,"
        "s7-info,enip-info,modbus-discover,nbstat"
    ),

    "printers": udp_profile(tcp_profile(
        "Impresoras / Escáneres",
        "80,443,515,631,9100",
        "banner,http-title,ssl-cert"
    )),

    "mes": tcp_profile(
        "MES / Servidor de planta",
        "22,80,135,139,443,445,1433,1883,3306,3389,4840,5985",
        "banner,http-title,ssl-cert,smb-os-discovery,nbstat"
    ),

    "cnc": tcp_profile(
        "CNC / Controlador de máquina",
        "21,22,23,80,102,443,502,2222,3389,4840,5900,8080,8443,44818",
        "banner,ssh-hostkey,http-title,http-headers,ssl-cert,s7-info,enip-info,modbus-discover"
    ),

    "switch": udp_profile(tcp_profile(
        "Switch / Red gestionada",
        "22,23,80,443",
        "banner,http-title,ssl-cert"
    ), "161", "snmp-info,snmp-interfaces"),

    "server": tcp_profile(
        "Servidor / Historian",
        "22,80,135,139,443,445,1433,1883,3306,3389,4840,5985",
        "banner,http-title,ssl-cert,smb-os-discovery,nbstat"
    ),

    "drive": udp_profile(tcp_profile(
        "Variador / Drive",
        "80,443,502,44818",
        "banner,http-title,ssl-cert,modbus-discover,enip-info"
    )),

    "camera": tcp_profile(
        "Cámara IP",
        "80,443,554,8000,8080,8443,37777",
        "banner,http-title,ssl-cert,rtsp-methods"
    ),

    "robot": tcp_profile(
        "Robot industrial",
        "21,22,23,80,443,102,2222,3389,44818,5900",
        "banner,http-title,ssl-cert,enip-info"
    ),

    "io_remote": udp_profile(tcp_profile(
        "I/O remota / Gateway de campo",
        "80,102,443,502,2222,44818",
        "banner,http-title,ssl-cert,s7-info,enip-info,modbus-discover"
    )),

    "instrument": udp_profile(tcp_profile(
        "Instrumento / Báscula / Lector",
        "23,80,443,502,9100",
        "banner,http-title,ssl-cert,modbus-discover"
    )),

    "scada": tcp_profile(
        "SCADA / Servidor OPC",
        "22,80,135,139,443,445,1433,1883,3306,3389,4840,5985",
        "banner,http-title,ssl-cert,smb-os-discovery,nbstat"
    ),

    "ups": udp_profile(tcp_profile(
        "UPS / PDU",
        "80,443",
        "banner,http-title,ssl-cert"
    )),

    "wap": udp_profile(tcp_profile(
        "Access Point / Wi-Fi industrial",
        "22,23,80,443",
        "banner,http-title,ssl-cert"
    )),

    "ewon": tcp_profile(
        "Ewon / Router de acceso remoto",
        "80,443,1194",
        "banner,http-title,ssl-cert"
    ),

    "insys": udp_profile(tcp_profile(
        "INSYS (gateway de acceso remoto)",
        "21,22,23,80,443,502,990,1194,8080,8443",
        "banner,http-title,http-headers,ssl-cert,ssh-hostkey,ftp-syst"
    )),

    "mguard": udp_profile(tcp_profile(
        "mGuard (Phoenix Contact)",
        "22,80,443",
        "banner,http-title,ssl-cert"
    )),
}


# Scripts/puertos que el general agrega aunque ningún perfil los use
_GENERAL_EXTRA_TCP = {"21", "22", "23", "80", "443", "20000", "34964"}
_GENERAL_EXTRA_SCRIPTS = {"modbus-discover", "s7-info", "enip-info", "nbstat"}
_GENERAL_EXTRA_UDP = {"161", "47808"}


def _arg(args: list[str], flag: str) -> str:
    return args[args.index(flag) + 1] if flag in args else ""


def _sort_ports(ports: set[str]) -> str:
    return ",".join(sorted((p for p in ports if p), key=lambda x: int(x)))


def build_general() -> dict:
    tcp, scripts, udp, udp_scripts = set(_GENERAL_EXTRA_TCP), set(_GENERAL_EXTRA_SCRIPTS), set(_GENERAL_EXTRA_UDP), set()
    for name, prof in PROFILES.items():
        if name in ("general", "discovery"):
            continue
        tcp |= set(_arg(prof["args"], "-p").split(","))
        scripts |= set(_arg(prof["args"], "--script").split(","))
        if prof.get("udp_args"):
            udp |= set(_arg(prof["udp_args"], "-p").split(","))
            udp_scripts |= set(_arg(prof["udp_args"], "--script").split(","))
    profile = tcp_profile("Descubrimiento general", _sort_ports(tcp), ",".join(sorted(s for s in scripts if s)))
    return udp_profile(profile, _sort_ports(udp), ",".join(sorted(s for s in (udp_scripts or {"snmp-info"}) if s)))


PROFILES["general"] = build_general()


def profile_exists(name: str) -> bool:
    return name in PROFILES


def get_profile_args(name: str) -> list[str]:
    return list(PROFILES[name]["args"])


def list_profiles() -> list[dict]:
    return [
        {"value": name, "label": data["label"]}
        for name, data in PROFILES.items()
    ]


def get_profile_udp_args(name: str) -> list[str]:
    return list(PROFILES.get(name, {}).get("udp_args", []))