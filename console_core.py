#!/usr/bin/env python3
"""Strata Console: gateway OpenAI-compatible + panel de control de modelos.

Capa separada del nucleo de Strata: vive en ~/.hermes/strata-console y usa SUS
propias copias de los run-configs (configs/*.json). Actualizar Strata no la toca.
"""
from __future__ import annotations

import json
import os
import re
import secrets
import subprocess
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

BASE = Path(__file__).resolve().parent
CATALOG = BASE / "catalog.json"
CONFIGS = BASE / "configs"
LOGS = BASE / "logs"
TOKEN_FILE = BASE / "token"
HOST = os.environ.get("STRATA_CONSOLE_HOST", "127.0.0.1")
PORT = int(os.environ.get("STRATA_CONSOLE_PORT", "8090"))
START_TIMEOUT = 420
POLL = 2

lock = threading.Lock()
try:
    active: str | None = json.loads(CATALOG.read_text(encoding="utf-8")).get("default_model")
except (OSError, ValueError, TypeError):
    active = None
jobs: dict[str, dict] = {}


def load_catalog() -> dict:
    return json.loads(CATALOG.read_text(encoding="utf-8"))


def save_catalog(cat: dict) -> None:
    tmp = CATALOG.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(cat, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(CATALOG)


def model_ids(cat: dict) -> list[str]:
    return [m["id"] for m in cat["models"]]


def get_active() -> str | None:
    return active


def find(cat: dict, mid: str) -> dict | None:
    return next((m for m in cat["models"] if m["id"] == mid), None)


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40]


def unit_name(entry: dict) -> str:
    return entry.get("unit") or f"strata-console-{slug(entry['id'])}"


def http_json(url: str, method: str = "GET", body: bytes | None = None, timeout: int = 5):
    req = urllib.request.Request(url, data=body, method=method)
    if body:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read() or b"{}")


def ready(port: int, mid: str) -> bool:
    try:
        data = http_json(f"http://{HOST}:{port}/v1/models")
        return any(row.get("id") == mid for row in data.get("data", []))
    except (OSError, ValueError, urllib.error.URLError):
        return False


def systemctl(action: str, unit: str) -> None:
    subprocess.run(["systemctl", "--user", action, unit], check=False,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def ensure_unit(entry: dict, cat: dict) -> str:
    """Crea el unit systemd del modelo si falta. Nunca toca los units ya existentes."""
    unit = unit_name(entry)
    path = Path.home() / ".config" / "systemd" / "user" / f"{unit}.service"
    if path.exists():
        return unit
    cfg = json.loads((BASE / entry["config"]).read_text(encoding="utf-8"))
    root = cat["engine_root"]
    body = f"""[Unit]
Description=Strata Console {entry['id']}

[Service]
Type=simple
WorkingDirectory={root}
Environment=STRATA_MAX_OUTPUT_TOKENS=4096
ExecStart=/bin/bash -lc 'cd "{root}" && exec .venv/bin/python serve/server.py --engine strata --config "{BASE / entry["config"]}" --port {entry["port"]}'
Restart=on-failure
RestartSec=10
TimeoutStartSec=0
KillSignal=SIGINT

[Install]
WantedBy=default.target
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    subprocess.run(["systemctl", "--user", "daemon-reload"], check=False)
    return unit


def switch_to(mid: str, cat: dict) -> int:
    global active
    entry = find(cat, mid)
    if not entry:
        raise KeyError(mid)
    port = int(entry["port"])
    with lock:
        if ready(port, mid):
            active = mid
            return port
        for other in cat["models"]:
            if int(other["port"]) != port:
                systemctl("stop", unit_name(other))
                if other.get("legacy_unit"):
                    systemctl("stop", other["legacy_unit"])
        unit = ensure_unit(entry, cat)
        subprocess.run(["systemctl", "--user", "restart", unit], check=True, timeout=60)
        deadline = time.monotonic() + START_TIMEOUT
        while time.monotonic() < deadline:
            if ready(port, mid):
                active = mid
                return port
            time.sleep(POLL)
        raise TimeoutError(f"Strata no estuvo listo en {START_TIMEOUT}s: {mid}")


def status_of(entry: dict) -> dict:
    port = int(entry["port"])
    out = {"id": entry["id"], "label": entry.get("label", entry["id"]), "port": port,
           "note": entry.get("note", ""), "running": False, "loaded": False,
           "busy": None, "phase": None, "queued": None,
           "vram_free_mib": None, "engine": None, "kv": None, "context": None,
           "tok_s": None, "tok_s_mean": None, "prefill_tok_s": None,
           "prompt_tokens": None, "generated": None, "max_tokens": None,
           "expert_cache_mib": None, "expert_slots": None, "spec": None,
           "mtp_max": None, "arena_mib": None, "images": None,
           "active": active == entry["id"]}
    try:
        h = http_json(f"http://{HOST}:{port}/health")
        out["running"] = True
        out["loaded"] = bool(h.get("loaded"))
        out["context"] = h.get("max_context")
        out["images"] = h.get("images")
    except (OSError, ValueError, urllib.error.URLError):
        return out
    try:
        m = http_json(f"http://{HOST}:{port}/metrics")
        eng, live = m.get("engine", {}), m.get("live", {})
        for src, dst in (("vram_free_mib", "vram_free_mib"), ("version", "engine"), ("kv", "kv"),
                         ("expert_cache_mib", "expert_cache_mib"), ("expert_slots", "expert_slots"),
                         ("spec", "spec"), ("mtp_max", "mtp_max"), ("arena_mib", "arena_mib")):
            out[dst] = eng.get(src)
        out["busy"] = live.get("state") == "generating"
        out["state"] = live.get("state")
        out["phase"] = live.get("phase")
        out["queued"] = live.get("queued")
        out["tok_s"] = live.get("tok_s")
        out["tok_s_mean"] = live.get("tok_s_mean")
        out["prefill_tok_s"] = live.get("prefill_tok_s_mean")
        out["prompt_tokens"] = live.get("prompt_tokens")
        out["generated"] = live.get("generated")
        out["max_tokens"] = live.get("max_tokens")
    except (OSError, ValueError, urllib.error.URLError):
        pass
    return out


def detail_of(entry: dict) -> dict:
    """Todo lo que Strata expone en /metrics: engine fino + ultimos requests con tok/s,
    hit rate de cache y aceptacion de drafts MTP."""
    port = int(entry["port"])
    try:
        m = http_json(f"http://{HOST}:{port}/metrics", timeout=6)
    except (OSError, ValueError, urllib.error.URLError):
        return {"id": entry["id"], "available": False}
    reqs = []
    for r in (m.get("requests") or [])[:25]:
        reqs.append({"t": r.get("time"), "dur_s": r.get("duration_s"), "finish": r.get("finish"),
                     "prompt": r.get("prompt_tokens"), "reused": r.get("reused"),
                     "out": r.get("output_tokens"), "decode_tok_s": r.get("decode_tok_s"),
                     "hit_rate": r.get("hit_rate"), "prompt_ms": r.get("prompt_ms"),
                     "decode_ms": r.get("decode_ms"), "pcie_share": r.get("pcie_share"),
                     "drafts_offered": r.get("drafts_offered"), "drafts_accepted": r.get("drafts_accepted"),
                     "recoveries": r.get("reasoning_recoveries")})
    return {"id": entry["id"], "available": True, "engine": m.get("engine", {}),
            "live": m.get("live", {}), "requests": reqs}


def gpu_state() -> dict:
    try:
        raw = subprocess.run(["nvidia-smi", "--query-gpu=memory.used,memory.total,utilization.gpu,temperature.gpu,power.draw",
                              "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=8)
        used, total, util, temp, power = [x.strip() for x in raw.stdout.strip().split(",")]
        return {"used_mib": int(used), "total_mib": int(total), "util": int(util),
                "temp_c": int(temp), "power_w": float(power)}
    except Exception:
        return {}


def ram_state() -> dict:
    try:
        with open("/proc/meminfo") as fh:
            vals = {}
            for line in fh:
                k, v = line.split(":", 1)
                vals[k] = int(v.strip().split()[0])
        total, avail = vals["MemTotal"], vals["MemAvailable"]
        return {"total_mib": total // 1024, "used_mib": (total - avail) // 1024}
    except Exception:
        return {}
