"""Capability-first runtime drivers.

Drivers only discover or call an already-running runtime. They never spawn a
runtime as a side effect of detection.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import json
import shutil
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


class RuntimeDriver:
    id = "runtime"
    label = "Runtime"

    def discover(self) -> RuntimeSnapshot:
        raise NotImplementedError

    def list_models(self) -> list[dict[str, Any]]:
        return []


class _HTTPDriver(RuntimeDriver):
    def __init__(self, base_url: str, timeout: float = 1.5):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _request(self, path: str, method: str = "GET", payload: dict | None = None):
        body = json.dumps(payload).encode() if payload is not None else None
        request = urllib.request.Request(
            self.base_url + path,
            data=body,
            method=method,
            headers={"Accept": "application/json", "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read(MAX_PROBE_BYTES)
                return response.status, json.loads(raw or b"{}")
        except (OSError, ValueError, urllib.error.URLError, json.JSONDecodeError):
            return None, None


class StrataDriver(_HTTPDriver):
    id = "strata"
    label = "Strata"

    def __init__(self, host: str, port: int, checkout: str | None = None):
        super().__init__(f"http://127.0.0.1:{port}")
        self.host = host
        self.port = port
        self.checkout = Path(checkout).expanduser() if checkout else None

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
            {"checkout": str(self.checkout) if self.checkout else None, "checkout_present": checkout_present, "health_http": health_status},
        )


class OllamaDriver(_HTTPDriver):
    id = "ollama"
    label = "Ollama"

    def __init__(self, base_url: str = "http://127.0.0.1:11434"):
        super().__init__(base_url)
        self.binary = shutil.which("ollama")

    def list_models(self) -> list[dict[str, Any]]:
        status, payload = self._request("/api/tags")
        return (payload or {}).get("models", []) if status and status < 300 else []

    def discover(self) -> RuntimeSnapshot:
        status, payload = self._request("/api/tags")
        running_status, running_payload = self._request("/api/ps")
        endpoint = status is not None
        models = (payload or {}).get("models", [])
        return RuntimeSnapshot(
            self.id,
            self.label,
            bool(self.binary or endpoint),
            endpoint,
            "reachable" if endpoint else ("installed" if self.binary else "offline"),
            self.base_url + "/api",
            ("list", "show", "pull", "delete", "generate", "running") if endpoint else ("detect",),
            len(models),
            {"binary": self.binary is not None, "tags_http": status, "ps_http": running_status, "running_models": len((running_payload or {}).get("models", []))},
        )

    def delete_model(self, name: str) -> dict[str, Any] | None:
        _, payload = self._request("/api/delete", method="DELETE", payload={"name": name})
        return payload


class VllmDriver(_HTTPDriver):
    id = "vllm"
    label = "vLLM"

    def __init__(self, base_url: str = "http://127.0.0.1:8000"):
        super().__init__(base_url)
        self.binary = shutil.which("vllm")
        try:
            import importlib.util
            self.module = importlib.util.find_spec("vllm") is not None
        except (ImportError, ValueError):
            self.module = False

    def list_models(self) -> list[dict[str, Any]]:
        status, payload = self._request("/v1/models")
        return (payload or {}).get("data", []) if status and status < 300 else []

    def discover(self) -> RuntimeSnapshot:
        status, payload = self._request("/v1/models")
        endpoint = status is not None
        models = (payload or {}).get("data", [])
        return RuntimeSnapshot(
            self.id,
            self.label,
            bool(self.binary or self.module or endpoint),
            endpoint,
            "reachable" if endpoint else ("installed" if self.binary or self.module else "offline"),
            self.base_url + "/v1",
            ("OpenAI", "continuous batching", "prefix cache", "metrics") if endpoint else ("detect",),
            len(models),
            {"binary": self.binary is not None, "module": self.module, "models_http": status},
        )


def discover_all(strata_host: str, strata_port: int, checkout: str | None = None) -> list[dict[str, Any]]:
    drivers: list[RuntimeDriver] = [
        StrataDriver(strata_host, strata_port, checkout),
        OllamaDriver(),
        VllmDriver(),
    ]
    return [driver.discover().as_dict() for driver in drivers]
