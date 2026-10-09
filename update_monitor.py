"""Bounded 10-minute monitor for Strata and the console repository."""
from __future__ import annotations

import json
import os
import re
import subprocess
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

import state_store
import update_core
from console_core import BASE, load_catalog

INTERVAL = 600
STRATA_REPO = os.environ.get("STRATA_CONSOLE_ENGINE_REPO", "Niko1221/Strata")

def _derive_console_repo() -> str:
    configured = os.environ.get("STRATA_CONSOLE_REPO")
    if configured:
        configured = configured.strip()
        match = re.search(r"github\.com[:/]([^/]+/[^/]+?)(?:\.git)?$", configured)
        return match.group(1) if match else configured.removesuffix(".git")
    try:
        remote = subprocess.run(["git", "-C", str(BASE), "config", "--get", "remote.origin.url"], capture_output=True, text=True, timeout=5, check=False).stdout.strip()
        match = re.search(r"github\.com[:/]([^/]+/[^/]+?)(?:\.git)?$", remote)
        if match:
            return match.group(1)
    except (OSError, subprocess.SubprocessError):
        pass
    return "monrroyag/strata-llm-console"


CONSOLE_REPO = _derive_console_repo()
_CACHE_KEY = "update_monitor"
_LOCK = threading.RLock()
_CACHE: dict = state_store.get(_CACHE_KEY) or {}
_HTTP_CACHE: dict = _CACHE.get("http_cache") or {}
_THREAD: threading.Thread | None = None


def _github(path: str, cache_key: str) -> dict:
    cached = _HTTP_CACHE.get(cache_key) or {}
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "strata-llm-console-update-monitor"}
    if cached.get("etag"):
        headers["If-None-Match"] = cached["etag"]
    request = urllib.request.Request(f"https://api.github.com{path}", headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            payload = json.loads(response.read(2 * 1024 * 1024) or b"{}")
            _HTTP_CACHE[cache_key] = {"etag": response.headers.get("ETag"), "payload": payload, "checked_at": time.time()}
            return payload
    except urllib.error.HTTPError as exc:
        if exc.code == 304 and isinstance(cached.get("payload"), dict):
            cached["checked_at"] = time.time()
            _HTTP_CACHE[cache_key] = cached
            return cached["payload"]
        raise


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
        remote = _github(f"/repos/{STRATA_REPO}/commits/main", "strata_commit")
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


def _version_tuple(value: str | None) -> tuple[int, int, int] | None:
    match = re.search(r"(?:^|v)(\d+)(?:\.(\d+))?(?:\.(\d+))?", str(value or ""))
    return (int(match.group(1)), int(match.group(2) or 0), int(match.group(3) or 0)) if match else None


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
        release = _github(f"/repos/{CONSOLE_REPO}/releases/latest", "console_release")
        tag = str(release.get("tag_name") or "")
        latest = tag[1:] if tag.startswith("v") else tag
        result["latest_version"] = latest or None
        result["release_url"] = release.get("html_url")
        result["published_at"] = release.get("published_at")
        body = str(release.get("body") or "")
        result["release_notes"] = body[:6000]
        current_v, latest_v = _version_tuple(current), _version_tuple(latest)
        result["comparison"] = "semver" if current_v and latest_v else "string"
        result["local_build_ahead"] = bool(current_v and latest_v and current_v > latest_v)
        result["update_available"] = bool(current and latest and ((latest_v > current_v) if current_v and latest_v else current != latest))
        if result["local_build_ahead"]:
            result["comparison_note"] = "local build is newer than the latest published release"
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
              "engine": engine, "console": console, "http_cache": _HTTP_CACHE}
    with _LOCK:
        _CACHE.clear()
        _CACHE.update(result)
        state_store.put(_CACHE_KEY, result)
    return dict(result)


def status() -> dict:
    with _LOCK:
        result = dict(_CACHE)
    checked = result.get("checked_at")
    age = max(0, time.time() - float(checked)) if checked else None
    result["cache_age_seconds"] = round(age, 1) if age is not None else None
    result["stale"] = age is None or age > INTERVAL * 2
    result["monitor_state"] = "stale" if result["stale"] else "fresh"
    return result


def _loop() -> None:
    while True:
        try:
            check_once()
        except Exception as exc:
            with _LOCK:
                _CACHE["monitor_error"] = f"{type(exc).__name__}: {exc}"[:240]
                _CACHE["monitor_error_at"] = time.time()
                state_store.put(_CACHE_KEY, dict(_CACHE))
        time.sleep(INTERVAL)


def start() -> None:
    global _THREAD
    with _LOCK:
        if _THREAD and _THREAD.is_alive():
            return
        _THREAD = threading.Thread(target=_loop, name="strata-update-monitor", daemon=True)
        _THREAD.start()
