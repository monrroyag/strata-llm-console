"""Detección ligera de backends locales sin iniciar procesos ni consumir GPU."""
from __future__ import annotations

import importlib.util
import shutil
import socket
import urllib.request


def _port(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.25):
            return True
    except OSError:
        return False


def status(strata_host: str, strata_port: int) -> dict:
    ollama_bin = shutil.which("ollama")
    vllm_bin = shutil.which("vllm")
    vllm_module = importlib.util.find_spec("vllm") is not None
    return {"backends": [
        {"id": "strata", "label": "Strata", "available": True, "running": strata_host not in ("127.0.0.1", "localhost") or _port(strata_port),
         "api": f"http://127.0.0.1:{strata_port}/v1", "features": ["OpenAI", "Anthropic", "SSE", "reasoning", "MTP", "vision"]},
        {"id": "ollama", "label": "Ollama", "available": bool(ollama_bin), "running": _port(11434),
         "api": "http://127.0.0.1:11434/api", "features": ["pull", "list", "show", "delete", "running"]},
        {"id": "vllm", "label": "vLLM", "available": bool(vllm_bin or vllm_module), "running": _port(8000),
         "api": "http://127.0.0.1:8000/v1", "features": ["OpenAI", "continuous batching", "prefix cache", "Prometheus metrics"]},
    ]}
