"""Agente FALSO para probar el contrato servidor<->agente sin red OT ni nmap.

Uso:
  python simulate_agent.py <agent_uid> <token> [base_url]

Hace poll una vez; si hay job, en vez de correr nmap sube tests/sample_nmap.xml
como si fuera el resultado. Sirve para validar poll -> running -> completed.
"""
import sys
from pathlib import Path

import httpx

BASE_URL = "http://127.0.0.1:8000"
SAMPLE = Path(__file__).parent / "tests" / "sample_nmap.xml"


def main():
    if len(sys.argv) < 3:
        print("Uso: python simulate_agent.py <agent_uid> <token> [base_url]")
        sys.exit(1)

    agent_uid, token = sys.argv[1], sys.argv[2]
    base = sys.argv[3] if len(sys.argv) > 3 else BASE_URL
    headers = {"X-Agent-Id": agent_uid, "Authorization": f"Bearer {token}"}

    poll = httpx.post(f"{base}/api/agent/poll", headers=headers)
    poll.raise_for_status()
    job = poll.json().get("job")
    if not job:
        print("No hay trabajos pendientes.")
        return

    print(f"Job recibido: scan {job['scan_id']} ({job['scan_profile']}) -> {job['target']}")
    print(f"nmap {' '.join(job['nmap_args'])} -oX - {job['target']}")

    result = httpx.post(
        f"{base}/api/agent/jobs/{job['scan_id']}/result",
        headers=headers,
        json={"status": "completed", "raw_xml": SAMPLE.read_text(encoding="utf-8")},
    )
    result.raise_for_status()
    print("Resultado subido:", result.json())


if __name__ == "__main__":
    main()