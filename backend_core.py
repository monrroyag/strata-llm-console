"""Capability-based discovery for local inference runtimes."""
from __future__ import annotations

import importlib.util
import json
import shutil
import socket
import urllib.error
import urllib.request


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


def status(strata_host: str, strata_port: int) -> dict:
    strata_running = strata_host not in ("127.0.0.1", "localhost") or _port(strata_port)
    ollama_probe = _get("http://127.0.0.1:11434/api/tags")
    vllm_probe = _get("http://127.0.0.1:8000/v1/models")
    ollama_bin = shutil.which("ollama")
    vllm_bin = shutil.which("vllm")
    vllm_module = importlib.util.find_spec("vllm") is not None
    return {"backends": [
        {
            "id": "strata", "label": "Strata", "available": True, "running": strata_running,
            "api": f"http://127.0.0.1:{strata_port}/v1",
            "health": "reachable" if strata_running else "offline",
            "features": ["OpenAI", "Anthropic", "SSE", "reasoning", "MTP", "vision"],
        },
        {
            "id": "ollama", "label": "Ollama", "available": bool(ollama_bin or ollama_probe),
            "running": ollama_probe is not None, "api": "http://127.0.0.1:11434/api",
            "health": "reachable" if ollama_probe is not None else "offline",
            "model_count": len((ollama_probe or {}).get("models", [])),
            "features": ["pull", "list", "show", "delete", "running"] if ollama_probe is not None else ["detect"],
        },
        {
            "id": "vllm", "label": "vLLM", "available": bool(vllm_bin or vllm_module or vllm_probe),
            "running": vllm_probe is not None, "api": "http://127.0.0.1:8000/v1",
            "health": "reachable" if vllm_probe is not None else "offline",
            "model_count": len((vllm_probe or {}).get("data", [])),
            "features": ["OpenAI", "continuous batching", "prefix cache", "Prometheus metrics"] if vllm_probe is not None else ["detect"],
        },
    ]}
