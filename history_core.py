"""Métricas históricas por modelo + verificación de fit en el PC.

Cada muestreo guarda en data/history/<id>.jsonl: tok/s, VRAM, KV, contexto y el
SETUP completo (flags) para poder comparar rendimiento ENTRE configuraciones.
El fit check estima si un GGUF cabe en la 3090 + RAM antes de darle alta."""
from __future__ import annotations

import json
import os
import re
import subprocess
import threading
import time
from collections import deque
from pathlib import Path

BASE = Path(__file__).resolve().parent
HIST = BASE / "data" / "history"
HIST.mkdir(parents=True, exist_ok=True)

MAX_ROWS = 5000
MODEL_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
_HISTORY_LOCK = threading.RLock()


def _history_path(mid: str) -> Path:
    if not MODEL_ID_RE.fullmatch(str(mid or "")):
        raise ValueError("modelo inválido")
    return HIST / f"{mid}.jsonl"


def _setup_snapshot(entry: dict, cat: dict) -> dict:
    try:
        cfg = json.loads((BASE / entry["config"]).read_text(encoding="utf-8"))
        args = cfg.get("args", [])
        flags = {}
        i = 0
        while i < len(args):
            if args[i].startswith("--") and i + 1 < len(args) and not args[i + 1].startswith("--"):
                flags[args[i]] = args[i + 1]
                i += 2
            else:
                flags.setdefault(args[i], True)
                i += 1
        return {"max_context": flags.get("--max-context"), "kv": flags.get("--kv"),
                "spec": flags.get("--spec"), "spec_min_p": flags.get("--spec-min-p"),
                "mtp": bool(flags.get("--mtp")), "lookup_chain": flags.get("--lookup-chain"),
                "vram_reserve_mib": flags.get("--vram-reserve-mib"),
                "pcie_frac": flags.get("--pcie-frac"),
                "sampling": cfg.get("sampling") or {}}
    except Exception:
        return {}


def record(entry: dict, metrics: dict) -> None:
    """Append de un sample con el setup vigente (llamado desde el sampler)."""
    live = metrics.get("live", {})
    eng = metrics.get("engine", {})
    row = {"t": int(time.time()),
           "tok_s": live.get("tok_s"), "tok_s_mean": live.get("tok_s_mean"),
           "prefill_tok_s": live.get("prefill_tok_s_mean"),
           "vram_free_mib": eng.get("vram_free_mib"),
           "expert_cache_mib": eng.get("expert_cache_mib"),
           "expert_slots": eng.get("expert_slots"),
           "max_context": eng.get("max_context"), "kv": eng.get("kv"),
           "spec": eng.get("spec"), "mtp_max": eng.get("mtp_max"),
           "requests": len(metrics.get("requests") or []),
           "setup": _setup_snapshot(entry, {})}
    path = _history_path(entry["id"])
    with _HISTORY_LOCK:
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.touch(mode=0o600)
        path.chmod(0o600)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            fh.flush()
        try:
            oversized = path.stat().st_size > 8_000_000
        except OSError:
            oversized = False
        if oversized:
            lines = deque(maxlen=MAX_ROWS)
            with path.open(encoding="utf-8") as fh:
                lines.extend(fh)
            tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
            with tmp.open("w", encoding="utf-8") as fh:
                fh.writelines(lines)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, path)
            path.chmod(0o600)


def history(mid: str, since: int = 0, limit: int = 500) -> list[dict]:
    path = _history_path(mid)
    if not path.exists():
        return []
    with _HISTORY_LOCK:
        rows = deque(maxlen=max(1, min(int(limit), MAX_ROWS)))
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                if r.get("t", 0) >= since:
                    rows.append(r)
        return list(rows)


def compare_setups(mid: str) -> list[dict]:
    """Agrega rendimiento por setup distinto: el panel muestra qué configuración
    rindió mejor para este modelo."""
    buckets: dict[str, dict] = {}
    for r in history(mid, limit=5000):
        key = json.dumps(r.get("setup") or {}, sort_keys=True)
        b = buckets.setdefault(key, {"setup": r.get("setup"), "n": 0, "tok_s": [], "prefill": []})
        b["n"] += 1
        if r.get("tok_s_mean"):
            b["tok_s"].append(r["tok_s_mean"])
        if r.get("prefill_tok_s"):
            b["prefill"].append(r["prefill_tok_s"])
    out = []
    for b in buckets.values():
        out.append({"setup": b["setup"], "samples": b["n"],
                    "tok_s_mean_avg": round(sum(b["tok_s"]) / len(b["tok_s"]), 1) if b["tok_s"] else None,
                    "prefill_avg": round(sum(b["prefill"]) / len(b["prefill"]), 1) if b["prefill"] else None})
    out.sort(key=lambda x: -(x["tok_s_mean_avg"] or 0))
    return out


def fit_check(gguf_paths: list[str], max_context: int = 200000, kv: str = "q4_0") -> dict:
    """Estima si el modelo cabe: pesos GGUF + KV estimado vs VRAM 24 GB y RAM.
    Regla práctica Strata: pesos en RAM/arena + cache de expertos en VRAM;
    el KV q4_0 ~ 0.5 B/pos*capa orden llama.cpp; se usa una cota conservadora."""
    import os
    import shutil
    total_bytes = 0
    for p in gguf_paths:
        if os.path.exists(p):
            total_bytes += os.path.getsize(p)
    weights_gib = total_bytes / 2**30
    # KV: cota conservadora ~2.2 GiB por 100k de contexto en q4_0 para este arch
    kv_gib = (max_context / 100_000) * 2.2 * {"fp16": 4.0, "int8": 2.0, "q4_0": 1.0, "k8v4": 0.77}.get(kv, 1.0)
    try:
        with open("/proc/meminfo") as fh:
            mem = {l.split(":")[0]: int(l.split()[1]) // 1024 for l in fh}
        ram_avail_gib = mem.get("MemAvailable", 0) / 1024
        ram_total_gib = mem.get("MemTotal", 0) / 1024
    except Exception:
        ram_avail_gib = ram_total_gib = None
    disk_free_gib = shutil.disk_usage(str(BASE)).free / 2**30
    try:
        raw = subprocess.run(["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=8)
        vram_total_gib = max(int(line.strip()) for line in raw.stdout.splitlines() if line.strip()) / 1024
    except (OSError, ValueError, subprocess.SubprocessError):
        vram_total_gib = None
    need_ram = weights_gib * 1.15 + kv_gib * 0.3
    fits_ram = (ram_avail_gib is None) or (need_ram <= ram_avail_gib)
    fits_vram = vram_total_gib is None or kv_gib <= vram_total_gib
    fits = fits_ram and fits_vram
    return {"weights_gib": round(weights_gib, 2), "kv_est_gib": round(kv_gib, 2),
            "ram_total_gib": round(ram_total_gib or 0, 1), "ram_avail_gib": round(ram_avail_gib or 0, 1),
            "ram_needed_est_gib": round(need_ram, 1), "vram_total_gib": round(vram_total_gib, 1) if vram_total_gib is not None else None,
            "disk_free_gib": round(disk_free_gib, 1),
            "fits": fits,
            "verdict": ("cabe holgado" if fits and need_ram < (ram_avail_gib or 99) * 0.7 else
                        "cabe justo: baja contexto o usa --kv q4_0/--kv-grow" if fits else
                        "NO cabe con este contexto: reduce --max-context o cambia de cuantización")}