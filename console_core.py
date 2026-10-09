#!/usr/bin/env python3
"""Strata Console: gateway OpenAI-compatible + panel de control de modelos.

Capa separada del nucleo de Strata: vive en ~/.hermes/strata-console y usa SUS
propias copias de los run-configs (configs/*.json). Actualizar Strata no la toca.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import stat
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
MODEL_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
MAX_BODY_BYTES = 8 * 1024 * 1024

lock = threading.Lock()
try:
    active: str | None = json.loads(CATALOG.read_text(encoding="utf-8")).get("default_model")
except (OSError, ValueError, TypeError):
    active = None
jobs: dict[str, dict] = {}


def validate_catalog(cat: dict) -> dict:
    if not isinstance(cat, dict) or not isinstance(cat.get("models"), list):
        raise ValueError("catálogo inválido: models debe ser una lista")
    ids = set()
    ports = set()
    for model in cat["models"]:
        mid = validate_model_id(model.get("id"))
        if mid in ids:
            raise ValueError(f"id duplicado en catálogo: {mid}")
        ids.add(mid)
        port = int(model.get("port"))
        if not 1024 <= port <= 65535 or port == PORT or port in ports:
            raise ValueError(f"puerto inválido o duplicado en catálogo: {port}")
        ports.add(port)
        config = str(model.get("config", ""))
        if not config.startswith("configs/") or Path(config).name != config[8:] or not config.endswith(".json"):
            raise ValueError(f"configuración fuera de configs: {config}")
    default = cat.get("default_model")
    if default is not None and default not in ids:
        raise ValueError("default_model no existe en el catálogo")
    return cat


def load_catalog() -> dict:
    return validate_catalog(json.loads(CATALOG.read_text(encoding="utf-8")))


def save_catalog(cat: dict) -> None:
    validate_catalog(cat)
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


def validate_model_id(mid: str | None) -> str:
    mid = str(mid or "").strip().lower()
    if not MODEL_ID_RE.fullmatch(mid):
        raise ValueError("id de modelo inválido: usa 1-64 caracteres [a-z0-9._-]")
    return mid


def safe_child(base: Path, relative: str) -> Path:
    candidate = (base / str(relative)).resolve()
    root = base.resolve()
    if not candidate.is_relative_to(root):
        raise ValueError("ruta fuera del directorio permitido")
    return candidate


def unit_name(entry: dict) -> str:
    mid = validate_model_id(entry["id"])
    return entry.get("unit") or f"strata-console-{slug(mid)}"


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


def systemctl(action: str, unit: str) -> bool:
    result = subprocess.run(["systemctl", "--user", action, unit], check=False,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return result.returncode == 0


def _systemd_quote(value: str) -> str:
    value = str(value)
    if any(ch in value for ch in ('"', "\n", "\r", "\\")):
        raise ValueError("ruta incompatible con systemd")
    return f'"{value}"' if any(ch.isspace() for ch in value) else value


def ensure_unit(entry: dict, cat: dict) -> str:
    """Create a native systemd unit without invoking a shell."""
    unit = unit_name(entry)
    path = Path.home() / ".config" / "systemd" / "user" / f"{unit}.service"
    if path.exists():
        return unit
    cfg_path = safe_child(CONFIGS, Path(entry["config"]).name)
    root = Path(cat["engine_root"]).expanduser().resolve()
    if not root.is_dir():
        raise ValueError(f"engine_root no existe: {root}")
    python_bin = root / ".venv" / "bin" / "python"
    if not python_bin.is_file():
        python_bin = Path("/usr/bin/python3")
    port = int(entry["port"])
    body = f"""[Unit]
Description=Strata Console {validate_model_id(entry['id'])}

[Service]
Type=simple
WorkingDirectory={_systemd_quote(str(root))}
Environment=STRATA_MAX_OUTPUT_TOKENS=4096
ExecStart={_systemd_quote(str(python_bin))} {_systemd_quote(str(root / 'serve' / 'server.py'))} --engine strata --config {_systemd_quote(str(cfg_path))} --port {port}
Restart=on-failure
RestartSec=10
TimeoutStartSec=0
KillSignal=SIGINT

[Install]
WantedBy=default.target
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    path.chmod(0o600)
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
        if not systemctl("restart", unit):
            raise RuntimeError(f"systemd no pudo reiniciar {unit}")
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
