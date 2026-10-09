"""Bounded 10-minute monitor for Strata and the console repository."""
from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

import state_store
import update_core
from console_core import BASE, load_catalog

INTERVAL = 600
STRATA_REPO = "Niko1221/Strata"
CONSOLE_REPO = "monrroyag/strata-llm-console"
_CACHE_KEY = "update_monitor"
_LOCK = threading.RLock()
_CACHE: dict = state_store.get(_CACHE_KEY) or {}
_THREAD: threading.Thread | None = None


def _github(path: str) -> dict:
    request = urllib.request.Request(
        f"https://api.github.com{path}",
        headers={"Accept": "application/vnd.github+json", "User-Agent": "strata-llm-console-update-monitor"},
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.loads(response.read(2 * 1024 * 1024) or b"{}")


def _git(root: Path, *args: str) -> str | None:
    try:
        return update_core._git(str(root), *args, timeout=20)
    except Exception:
        return None


def _console_version() -> str | None:
    try:
        value = (BASE / "VERSION").read_text(encoding="utf-8").strip()
        return value or None
    except OSError:
        return None


def _strata(cat: dict) -> dict:
    root = update_core._engine_root(cat)
    local_commit = _git(root, "rev-parse", "HEAD") if (root / ".git").exists() else None
    result = {
        "kind": "engine",
        "label": "Strata engine",
        "repo": f"https://github.com/{STRATA_REPO}",
        "installed": bool(local_commit),
        "install_required": not bool(local_commit),
        "local_commit": local_commit,
        "latest_commit": None,
        "update_available": False,
        "changes": [],
        "changelog_url": f"https://github.com/{STRATA_REPO}/commits/main",
    }
    if not local_commit:
        return result
    try:
        remote = _github(f"/repos/{STRATA_REPO}/commits/main")
        latest = remote.get("sha")
        commit = remote.get("commit") or {}
        result["latest_commit"] = latest
        result["update_available"] = bool(latest and latest != local_commit)
        if latest and latest != local_commit:
            result["changes"] = [{"commit": latest[:12], "date": (commit.get("committer") or {}).get("date", "")[:10],
                                   "subject": (commit.get("message") or "").splitlines()[0][:240]}]
            result["changelog_url"] = f"https://github.com/{STRATA_REPO}/compare/{local_commit}...{latest}"
    except (OSError, ValueError, urllib.error.URLError) as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"[:240]
    return result


def _console() -> dict:
    current = _console_version()
    result = {
        "kind": "console",
        "label": "Strata LLM Console",
        "repo": f"https://github.com/{CONSOLE_REPO}",
        "current_version": current,
        "latest_version": None,
        "update_available": False,
        "changes": [],
        "changelog_url": f"https://github.com/{CONSOLE_REPO}/releases",
    }
    try:
        release = _github(f"/repos/{CONSOLE_REPO}/releases/latest")
        tag = str(release.get("tag_name") or "")
        latest = tag[1:] if tag.startswith("v") else tag
        result["latest_version"] = latest or None
        result["release_url"] = release.get("html_url")
        result["published_at"] = release.get("published_at")
        body = str(release.get("body") or "")
        result["release_notes"] = body[:6000]
        result["update_available"] = bool(current and latest and current != latest)
        if result["update_available"]:
            result["changes"] = [{"commit": tag, "date": str(release.get("published_at") or "")[:10],
                                   "subject": line.strip()[:240]} for line in body.splitlines()
                                  if line.strip() and not line.lstrip().startswith("<!--")][:8]
            result["changelog_url"] = release.get("html_url") or result["changelog_url"]
    except (OSError, ValueError, urllib.error.URLError) as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"[:240]
    return result


def check_once() -> dict:
    try:
        cat = load_catalog()
        engine = _strata(cat)
    except Exception as exc:
        engine = {"kind": "engine", "label": "Strata engine", "installed": False,
                  "install_required": True, "update_available": False,
                  "error": f"{type(exc).__name__}: {exc}"[:240]}
    console = _console()
    updates = [item for item in (engine, console) if item.get("update_available") or item.get("install_required")]
    result = {"checked_at": time.time(), "next_check_at": time.time() + INTERVAL,
              "interval_seconds": INTERVAL, "updates": updates,
              "engine": engine, "console": console}
    with _LOCK:
        _CACHE.clear()
        _CACHE.update(result)
        state_store.put(_CACHE_KEY, result)
    return dict(result)


def status() -> dict:
    with _LOCK:
        return dict(_CACHE)


def _loop() -> None:
    while True:
        try:
            check_once()
        except Exception:
            pass
        time.sleep(INTERVAL)


def start() -> None:
    global _THREAD
    with _LOCK:
        if _THREAD and _THREAD.is_alive():
            return
        _THREAD = threading.Thread(target=_loop, name="strata-update-monitor", daemon=True)
        _THREAD.start()
