"""Túnel seguro hacia el gateway 8090: cloudflared quick tunnel.

La autenticación remota pertenece al gateway de la consola: el cliente usa el
mismo token Bearer/X-Strata-Token que valida el control plane. Este módulo no
inyecta ni persiste una segunda API key en los modelos.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import threading
import time
import urllib.request
from pathlib import Path

import state_store
from paths import CODE_ROOT, STATE_ROOT, runtime_path

BASE = CODE_ROOT
BIN = runtime_path("bin", "cloudflared")
STATE = runtime_path("data", "tunnel.json")
LOGF = runtime_path("logs", "tunnel.log")
CONFIGS = runtime_path("configs")
URL_RE = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")
CLOUDFLARED_VERSION = os.environ.get("STRATA_CONSOLE_CLOUDFLARED_VERSION", "2026.10.0")
CLOUDFLARED_SHA256 = os.environ.get("STRATA_CONSOLE_CLOUDFLARED_SHA256", "d33ff2d14475178d2012c2c56beba87389ac5ded27649519f198a7d3134a99db")
CLOUDFLARED_MAX_BYTES = 256 * 1024 * 1024

_proc: subprocess.Popen | None = None
_lock = threading.Lock()


def _save(st: dict) -> None:
    if STATE != BASE / "data" / "tunnel.json":
        STATE.parent.mkdir(parents=True, exist_ok=True)
        state_store.atomic_json_export(STATE, st, mode=0o600)
        return
    state_store.put("tunnel", st)
    state_store.atomic_json_export(STATE, st, mode=0o600)


def _load() -> dict:
    if STATE != BASE / "data" / "tunnel.json":
        try:
            if STATE.exists():
                data = json.loads(STATE.read_text(encoding="utf-8"))
                return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}
        return {}
    data = state_store.load_or_migrate("tunnel", STATE, {})
    return data if isinstance(data, dict) else {}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def ensure_binary() -> str:
    if BIN.exists() and _sha256(BIN).lower() == CLOUDFLARED_SHA256.lower():
        return str(BIN)
    BIN.parent.mkdir(parents=True, exist_ok=True)
    url = f"https://github.com/cloudflare/cloudflared/releases/download/{CLOUDFLARED_VERSION}/cloudflared-linux-amd64"
    tmp = BIN.with_suffix(f".{os.getpid()}.tmp")
    digest = hashlib.sha256()
    size = 0
    try:
        with urllib.request.urlopen(url, timeout=120) as resp, tmp.open("wb") as fh:
            while True:
                chunk = resp.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > CLOUDFLARED_MAX_BYTES:
                    raise ValueError("binario cloudflared supera el límite de descarga")
                digest.update(chunk)
                fh.write(chunk)
        if digest.hexdigest().lower() != CLOUDFLARED_SHA256.lower():
            raise ValueError("checksum SHA-256 de cloudflared no coincide con la versión fijada")
        tmp.chmod(0o755)
        tmp.replace(BIN)
    finally:
        try:
            tmp.unlink()
        except FileNotFoundError:
            pass
    return str(BIN)


def api_key_set() -> bool:
    """Informational legacy flag; tunnel authentication is console-token based."""
    for cfg in CONFIGS.glob("*.json"):
        try:
            if json.loads(cfg.read_text(encoding="utf-8")).get("api_key"):
                return True
        except Exception:
            continue
    return False


def set_api_key_on_models(key: str) -> list[str]:
    touched = []
    for cfg in CONFIGS.glob("*.json"):
        try:
            data = json.loads(cfg.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not data.get("api_key"):
            data["api_key"] = key
            cfg.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            cfg.chmod(0o600)
            touched.append(cfg.name)
    return touched


def status(public: bool = False) -> dict:
    st = _load()
    running = _proc is not None and _proc.poll() is None
    if not running and st.get("pid"):
        try:
            os.kill(int(st["pid"]), 0)
            running = True
        except (OSError, ValueError):
            st["url"] = None
            st.pop("pid", None)
            _save(st)
    st["running"] = running
    st["api_key_set"] = api_key_set()
    if public:
        return {key: st.get(key) for key in ("running", "url", "started_at", "api_key_set", "auth_mode")}
    return st


def start(port: int = 8090, force_key: bool = True) -> dict:
    global _proc
    with _lock:
        st = _load()
        if st.get("running") or (_proc and _proc.poll() is None):
            return {"status": "already_running", "url": st.get("url")}
        binary = ensure_binary()
        # The console gateway is the single authentication boundary. The
        # legacy force_key argument is retained for API compatibility but no
        # longer creates a durable model credential before startup.
        LOGF.parent.mkdir(exist_ok=True)
        _proc = subprocess.Popen(
            [binary, "tunnel", "--no-autoupdate", "--url", f"http://127.0.0.1:{port}"],
            stdout=open(LOGF, "ab"), stderr=subprocess.STDOUT,
            start_new_session=True)
        st["pid"] = _proc.pid
        st["started_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
        deadline = time.monotonic() + 30
        url = None
        while time.monotonic() < deadline:
            time.sleep(2)
            try:
                m = URL_RE.search(LOGF.read_text(errors="ignore"))
                if m:
                    url = m.group(0)
                    break
            except OSError:
                pass
        st["url"] = url
        st["auth_mode"] = "console_token"
        _save(st)
        return {"status": "started" if url else "starting", "url": url, "pid": _proc.pid,
                "auth_mode": "console_token",
                "note": "el túnel expone el gateway; los clientes deben usar el token de la consola en Authorization: Bearer o X-Strata-Token"}


def stop() -> dict:
    global _proc
    with _lock:
        st = _load()
        if _proc and _proc.poll() is None:
            _proc.terminate()
            try:
                _proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                _proc.kill()
        elif st.get("pid"):
            try:
                os.kill(st["pid"], 15)
            except OSError:
                pass
        st["url"] = None
        _save(st)
        return {"status": "stopped"}
