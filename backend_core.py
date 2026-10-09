"""Capability-based discovery for local inference runtimes."""
from __future__ import annotations

import importlib.util
import json
import shutil
import socket
import urllib.error
import urllib.request

import runtime_drivers

def _port(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.25):
            return True
    except OSError:
        return False


def _get(url: str, timeout: float = 1.5):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return json.loads(response.read(512 * 1024) or b"{}")
    except (OSError, ValueError, urllib.error.URLError):
        return None


def status(strata_host: str, strata_port: int, catalog: dict | None = None) -> dict:
    """Detect runtimes by observed endpoints/install evidence only."""
    checkout = (catalog or {}).get("engine_root")
    return {"backends": runtime_drivers.discover_all(strata_host, strata_port, checkout)}
