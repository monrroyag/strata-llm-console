"""Túnel seguro hacia el gateway 8090: cloudflared quick tunnel (gratuito,
TLS extremo a extremo, sin abrir puertos en el router). El acceso queda
protegido por la API key de Strata: sin key configurada el túnel se niega."""
from __future__ import annotations

import json
import os
import re
import secrets
import subprocess
import threading
import time
import urllib.request
from pathlib import Path

import state_store

BASE = Path(__file__).resolve().parent
BIN = BASE / "bin" / "cloudflared"
STATE = BASE / "data" / "tunnel.json"
LOGF = BASE / "logs" / "tunnel.log"
URL_RE = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")

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


def ensure_binary() -> str:
    if BIN.exists():
        return str(BIN)
    BIN.parent.mkdir(parents=True, exist_ok=True)
    url = ("https://github.com/cloudflare/cloudflared/releases/latest/"
           "download/cloudflared-linux-amd64")
    tmp = BIN.with_suffix(".tmp")
    with urllib.request.urlopen(url, timeout=120) as resp, tmp.open("wb") as fh:
        fh.write(resp.read())
    tmp.chmod(0o755)
    tmp.replace(BIN)
    return str(BIN)


def api_key_set() -> bool:
    """El gateway sólo debe exponerse si el/los modelos exigen api key."""
    for cfg in (BASE / "configs").glob("*.json"):
        try:
            if json.loads(cfg.read_text(encoding="utf-8")).get("api_key"):
                return True
        except Exception:
            continue
    return False


def set_api_key_on_models(key: str) -> list[str]:
    touched = []
    for cfg in (BASE / "configs").glob("*.json"):
        try:
            data = json.loads(cfg.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not data.get("api_key"):
            data["api_key"] = key
            cfg.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
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
        return {key: st.get(key) for key in ("running", "url", "started_at", "api_key_set")}
    return st


def start(port: int = 8090, force_key: bool = True) -> dict:
    global _proc
    with _lock:
        st = _load()
        if st.get("running") or (_proc and _proc.poll() is None):
            return {"status": "already_running", "url": st.get("url")}
        generated_key = None
        if not api_key_set() and force_key:
            generated_key = secrets.token_urlsafe(32)
            touched = set_api_key_on_models(generated_key)
            st["key_files"] = touched
        binary = ensure_binary()
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
        _save(st)
        out = {"status": "started" if url else "starting", "url": url, "pid": _proc.pid}
        if generated_key:
            out["api_key_generated"] = generated_key
            out["note"] = ("se generó una API key para los modelos (archivos: "
                           + ", ".join(st.get("key_files", [])) + "). Los modelos deben "
                           "reiniciarse para exigirla; el cliente remoto la envía como "
                           "Authorization: Bearer <key>")
        return out


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
