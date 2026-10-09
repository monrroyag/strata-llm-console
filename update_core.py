"""Update de Strata: versión actual, detección de nuevas versiones y actualización
segura. La capa NUNCA toca los run-configs propios (configs/); sólo hace fetch y,
si el usuario lo pide, merge del repo de engine. Los cambios locales del repo
(serve/server.py adaptado) se preservan: se hace merge, no reset."""
from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from urllib.parse import urlparse

import state_store

BASE = Path(__file__).resolve().parent
CATALOG = BASE / "catalog.json"
OFFICIAL_REPO = "https://github.com/Niko1221/Strata.git"
ENGINE_INSTALL = BASE / "data" / "engine" / "Strata"


def _save_catalog(cat: dict) -> None:
    state_store.put("catalog", cat)
    state_store.atomic_json_export(CATALOG, cat, mode=0o600)


def validate_repo_url(repo: str) -> str:
    parsed = urlparse(repo)
    normalized = repo.rstrip("/")
    if parsed.scheme != "https" or parsed.netloc.lower() != "github.com" or normalized != OFFICIAL_REPO:
        raise ValueError("solo se permite el repositorio oficial de Strata")
    return OFFICIAL_REPO


def ensure_engine(cat: dict) -> dict:
    """Instala el engine oficial solo si falta; conserva la ruta si ya existe."""
    root = Path(cat.get("engine_root", "")).expanduser()
    if root.exists() and (root / ".git").exists():
        return {"present": True, "installed": False, "root": str(root)}
    repo = cat.get("update", {}).get("repo_url") or "https://github.com/Niko1221/Strata.git"
    ENGINE_INSTALL.parent.mkdir(parents=True, exist_ok=True)
    if ENGINE_INSTALL.exists() and not (ENGINE_INSTALL / ".git").exists():
        raise RuntimeError(f"ruta de instalación ocupada y no es un repo git: {ENGINE_INSTALL}")
    if not ENGINE_INSTALL.exists():
        subprocess.run(["git", "clone", "--origin", "origin", repo, str(ENGINE_INSTALL)], check=True,
                       capture_output=True, text=True, timeout=600)
    cat["engine_root"] = str(ENGINE_INSTALL)
    cat.setdefault("update", {})["repo_url"] = repo
    _save_catalog(cat)
    return {"present": True, "installed": True, "root": str(ENGINE_INSTALL), "repo_url": repo}


def _git(root: str, *args: str, timeout: int = 120) -> str:
    r = subprocess.run(["git", "-C", root, *args], capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError((r.stderr or r.stdout).strip()[:400])
    return r.stdout.strip()


def engine_version(root: str) -> str | None:
    """Versión declarada del engine en uso (serve/VERSION o MIN_ENGINE)."""
    for cand in (Path(root) / "VERSION", Path(root) / "serve" / "VERSION"):
        if cand.exists():
            return cand.read_text().strip()
    try:
        out = subprocess.run(["grep", "-rhoE", r"MIN_ENGINE\s*=\s*[\"'][0-9.]+", str(root / "serve")],
                             capture_output=True, text=True, timeout=10)
        for line in out.stdout.splitlines():
            return line.split("=")[-1].strip().strip("\"'")
    except Exception:
        pass
    return None


def check_update(cat: dict, fetch: bool = True) -> dict:
    """Read-only version check; installation is an explicit update operation."""
    root_path = Path(cat.get("engine_root", "")).expanduser()
    if not root_path.is_dir() or not (root_path / ".git").exists():
        return {"present": False, "installed": False, "update_available": False,
                "error": "engine no instalado; usa la acción de instalación explícita",
                "checked_at": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
    root = str(root_path)
    info = {"repo_url": cat.get("update", {}).get("repo_url") or
            _git(root, "config", "--get", "remote.origin.url"),
            "branch": "main", "checked_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "installed": False}
    try:
        if fetch:
            _git(root, "fetch", "origin", "--quiet", timeout=180)
        info["local_commit"] = _git(root, "rev-parse", "HEAD")
        info["remote_commit"] = _git(root, "rev-parse", "origin/main")
        behind, ahead = _git(root, "rev-list", "--left-right", "--count", "HEAD...origin/main").split()
        info["behind"], info["ahead"] = int(behind), int(ahead)
        info["update_available"] = info["behind"] > 0
        info["new_commits"] = [_git(root, "log", "--oneline", f"HEAD..origin/main", "-n", "1")]
        info["remote_version"] = None
        try:
            raw = subprocess.run(["git", "-C", root, "show", "origin/main:VERSION"],
                                 capture_output=True, text=True, timeout=15)
            if raw.returncode == 0:
                info["remote_version"] = raw.stdout.strip()
        except Exception:
            pass
        info["local_dirty"] = bool(_git(root, "status", "--porcelain"))
        cat.setdefault("update", {}).update(info)
        _save_catalog(cat)
    except Exception as exc:
        info["error"] = str(exc)
    return info


def do_update(cat: dict) -> dict:
    """Actualiza el repo oficial preservando cambios locales mediante stash/merge."""
    install = ensure_engine(cat)
    root = cat["engine_root"]
    before = _git(root, "rev-parse", "HEAD")
    dirty = _git(root, "status", "--porcelain")
    if dirty:
        # stash de los cambios locales para que el merge no los pise
        _git(root, "stash", "push", "-m", "strata-console pre-update", timeout=60)
    try:
        _git(root, "fetch", "origin", "main", timeout=300)
        out = _git(root, "merge", "--no-edit", "origin/main", timeout=300)
        if dirty:
            try:
                _git(root, "stash", "pop", timeout=60)
            except RuntimeError as exc:
                return {"status": "merge_ok_stash_conflict", "before": before,
                        "after": _git(root, "rev-parse", "HEAD"),
                        "note": f"hubo conflicto al re-aplicar cambios locales: {exc}"}
        return {"status": "updated", "before": before,
                "after": _git(root, "rev-parse", "HEAD"), "merge": out[:500],
                "note": "reinicia los modelos para usar el engine nuevo"}
    except RuntimeError as exc:
        try:
            _git(root, "merge", "--abort")
        except Exception:
            pass
        if dirty:
            try:
                _git(root, "stash", "pop", timeout=60)
            except Exception:
                pass
        return {"status": "failed", "before": before, "error": str(exc)}


def revert_update(cat: dict, to_commit: str) -> dict:
    root = cat["engine_root"]
    out = _git(root, "reset", "--hard", to_commit, timeout=60)
    return {"status": "reverted", "to": to_commit}
