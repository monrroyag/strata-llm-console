"""Estado y aplicación segura del modo de conexión de Strata Console.

Por defecto sólo escucha en loopback. Cambiar a LAN requiere una acción explícita,
escribe un drop-in systemd y conserva la autenticación para clientes remotos.
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
from pathlib import Path

BASE = Path(__file__).resolve().parent
STATE = BASE / "data" / "connection.json"
DEFAULT_SERVICE = os.environ.get("STRATA_CONSOLE_SERVICE", "strata-llm-console.service")


def service_name() -> str:
    configured = os.environ.get("STRATA_CONSOLE_SERVICE")
    if configured:
        return configured
    for candidate in ("strata-llm-console.service", "hermes-strata-console.service"):
        result = subprocess.run(["systemctl", "--user", "is-active", candidate],
                                capture_output=True, text=True, check=False)
        if result.returncode == 0:
            return candidate
    return DEFAULT_SERVICE


UNIT_DIR = Path.home() / ".config" / "systemd" / "user" / f"{service_name()}.d"
OVERRIDE = UNIT_DIR / "network.conf"


def _load():
    try:
        data = json.loads(STATE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _save(data):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def host_ip():
    try:
        for ip in socket.gethostbyname_ex(socket.gethostname())[2]:
            if not ip.startswith("127."):
                return ip
    except OSError:
        pass
    return "no disponible"


def status(host, port, token_file):
    state = _load()
    lan = host not in ("127.0.0.1", "localhost", "::1")
    ip = host_ip()
    return {
        "mode": "lan" if lan else "local",
        "bind_host": host,
        "port": port,
        "local_url": f"http://127.0.0.1:{port}/v1",
        "lan_url": f"http://{ip}:{port}/v1" if lan else None,
        "panel_local_url": f"http://127.0.0.1:{port}/",
        "panel_lan_url": f"http://{ip}:{port}/" if lan else None,
        "auth_remote_required": True,
        "auth_header": "Authorization: Bearer $STRATA_CONSOLE_TOKEN",
        "token_file": str(token_file),
        "cors": bool(state.get("cors", False)),
        "tunnel_managed_separately": True,
        "restart_required": False,
    }


def apply(mode, cors=False):
    if mode not in ("local", "lan"):
        raise ValueError("mode debe ser local o lan")
    host = "127.0.0.1" if mode == "local" else "0.0.0.0"
    UNIT_DIR.mkdir(parents=True, exist_ok=True)
    OVERRIDE.write_text(
        "[Service]\n"
        f"Environment=STRATA_CONSOLE_HOST={host}\n"
        "Environment=STRATA_CONSOLE_PORT=8090\n",
        encoding="utf-8",
    )
    data = {"mode": mode, "cors": bool(cors)}
    _save(data)
    subprocess.run(["systemctl", "--user", "daemon-reload"], check=False,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return {"status": "saved", "mode": mode, "cors": bool(cors),
            "service": service_name(),
            "restart_required": True,
            "note": "La conexión se aplicará al reiniciar el servicio de la consola."}


def remote_allowed(client_ip: str, auth_ok: bool) -> bool:
    """Loopback puede usar Hermes sin token; cualquier cliente remoto debe autenticarse."""
    local = client_ip in ("127.0.0.1", "::1", "localhost")
    return local or auth_ok
