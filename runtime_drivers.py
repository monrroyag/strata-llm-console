"""Capability-first discovery for the official Strata engine.

Discovery only probes the already-running Strata API and inspects an existing
checkout. It never starts a process or treats another runtime as supported.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


MAX_PROBE_BYTES = 512 * 1024


@dataclass(frozen=True)
class RuntimeSnapshot:
    id: str
    label: str
    available: bool
    running: bool
    health: str
    api: str
    features: tuple[str, ...] = ()
    model_count: int | None = None
    evidence: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        result = {
            "id": self.id,
            "label": self.label,
            "available": self.available,
            "running": self.running,
            "health": self.health,
            "api": self.api,
            "features": list(self.features),
            "evidence": self.evidence,
        }
        if self.model_count is not None:
            result["model_count"] = self.model_count
        return result


class StrataDriver:
    id = "strata"
    label = "Strata"

    def __init__(self, host: str, port: int, checkout: str | None = None, timeout: float = 1.5):
        self.host = host
        self.port = port
        self.base_url = f"http://127.0.0.1:{port}"
        self.timeout = timeout
        self.checkout = Path(checkout).expanduser() if checkout else None

    def _request(self, path: str):
        request = urllib.request.Request(
            self.base_url + path,
            headers={"Accept": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read(MAX_PROBE_BYTES)
                return response.status, json.loads(raw or b"{}")
        except (OSError, ValueError, urllib.error.URLError, json.JSONDecodeError):
            return None, None

    def list_models(self) -> list[dict[str, Any]]:
        status, payload = self._request("/v1/models")
        return (payload or {}).get("data", []) if status and status < 300 else []

    def discover(self) -> RuntimeSnapshot:
        health_status, _ = self._request("/health")
        models = self.list_models() if health_status else []
        checkout_present = bool(self.checkout and (self.checkout / ".git").is_dir())
        return RuntimeSnapshot(
            self.id,
            self.label,
            checkout_present or health_status is not None,
            health_status is not None,
            "reachable" if health_status is not None else ("installed" if checkout_present else "offline"),
            self.base_url + "/v1",
            ("OpenAI", "Anthropic", "SSE", "model lifecycle", "reasoning passthrough", "vision"),
            len(models),
            {
                "checkout": str(self.checkout) if self.checkout else None,
                "checkout_present": checkout_present,
                "health_http": health_status,
            },
        )


def discover_all(strata_host: str, strata_port: int, checkout: str | None = None) -> list[dict[str, Any]]:
    """Return the single supported engine capability snapshot."""
    return [StrataDriver(strata_host, strata_port, checkout).discover().as_dict()]
