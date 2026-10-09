"""Measured configuration evaluation for a local Strata model.

The evaluator is intentionally exclusive: while it owns the active model, normal
inference requests receive 423 so benchmark samples are comparable.
"""
from __future__ import annotations

import json
import math
import statistics
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

import job_core
import optimize_core
from console_core import BASE, find, safe_child, switch_to, systemctl, unit_name, validate_model_id

_LOCK = threading.Lock()
_ACTIVE: str | None = None

FLAG_MAP = {
    "max_context": "--max-context", "kv": "--kv", "spec": "--spec",
    "spec_min_p": "--spec-min-p", "kv_resident": "--kv-resident",
    "lookup_chain": "--lookup-chain", "suffix_draft": "--suffix-draft",
    "vram_reserve_mib": "--vram-reserve-mib", "pcie_frac": "--pcie-frac",
    "expert_cache": "--expert-cache", "adapt_swaps": "--adapt-swaps",
    "adapt_decay": "--adapt-decay", "prefill": "--prefill",
    "prompt_cache": "--prompt-cache", "conversation_cache_mib": "--conversation-cache-mib",
    "pool_workers": "--pool-workers", "batch": "--batch",
    "rope_scaling": "--rope-scaling", "expert_profile": "--expert-profile",
    "expert_profile_save": "--expert-profile-save", "control_vector": "--control-vector-scaled",
}
BOOL_MAP = {"kv_grow": "--kv-grow", "vision": "--vision", "vram_elastic": "--vram-elastic"}


def is_blocked() -> bool:
    with _LOCK:
        return _ACTIVE is not None


def active_job() -> str | None:
    with _LOCK:
        return _ACTIVE


def _set_flag(args: list, flag: str, value):
    if flag in args:
        index = args.index(flag)
        if index + 1 < len(args):
            args[index + 1] = str(value)
        return
    args.extend([flag, str(value)])


def _apply_config(path: Path, config: dict):
    data = json.loads(path.read_text(encoding="utf-8"))
    args = list(data.get("args", []))
    sampling = config.get("sampling")
    if sampling:
        data.setdefault("sampling", {}).update(sampling)
    for key, value in config.items():
        if key == "sampling":
            continue
        if key in BOOL_MAP:
            flag = BOOL_MAP[key]
            if value and flag not in args:
                args.append(flag)
            elif not value and flag in args:
                args.remove(flag)
        elif key in FLAG_MAP:
            _set_flag(args, FLAG_MAP[key], value)
        else:
            data[key] = value
    data["args"] = args
    tmp = path.with_name(f".{path.name}.evaluation.tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def _prompt(kind: str, chars: int) -> str:
    if kind == "short":
        return "Give a concise operational summary of the current task in three bullet points."
    seed = ("This is a deterministic long-context evaluation segment. Preserve facts, "
            "do not invent values, and return a concise final answer. ")
    repeats = max(1, min(chars // len(seed), 120000))
    return (seed * repeats)[:max(1024, min(chars, 500000))]


def _request(port: int, model: str, prompt: str, timeout: int = 180) -> dict:
    body = json.dumps({"model": model, "messages": [{"role": "user", "content": prompt}],
                       "temperature": 0, "max_tokens": 64, "stream": False}).encode()
    started = time.perf_counter()
    try:
        req = urllib.request.Request(f"http://127.0.0.1:{port}/v1/chat/completions",
                                     data=body, headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=timeout) as response:
            payload = json.loads(response.read(8 * 1024 * 1024) or b"{}")
        duration = time.perf_counter() - started
        usage = payload.get("usage") or {}
        usage_available = bool(usage.get("completion_tokens") is not None)
        prompt_tokens = int(usage.get("prompt_tokens") or max(1, len(prompt) // 4))
        output_tokens = int(usage.get("completion_tokens") or 0) if usage_available else None
        return {"ok": True, "duration_ms": round(duration * 1000, 1),
                "prompt_tokens": prompt_tokens, "completion_tokens": output_tokens,
                "usage_available": usage_available,
                "decode_tok_s": round(output_tokens / duration, 2) if output_tokens and output_tokens > 0 else None,
                "error": None}
    except (OSError, ValueError, urllib.error.URLError, TimeoutError) as exc:
        return {"ok": False, "duration_ms": round((time.perf_counter() - started) * 1000, 1),
                "prompt_tokens": max(1, len(prompt) // 4), "completion_tokens": 0,
                "usage_available": False, "decode_tok_s": None, "error": f"{type(exc).__name__}: {exc}"[:500]}


def _percentile(values: list[float], pct: float):
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, math.ceil(pct * len(ordered)) - 1))
    return round(ordered[index], 2)


def _aggregate(samples: list[dict]) -> dict:
    ok = [row for row in samples if row["ok"]]
    latencies = [row["duration_ms"] for row in ok]
    speeds = [row["decode_tok_s"] for row in ok if row.get("decode_tok_s")]
    return {
        "samples": len(samples), "successful": len(ok), "errors": len(samples) - len(ok),
        "success_rate": round(len(ok) / len(samples), 3) if samples else 0,
        "usage_coverage": round(sum(1 for row in ok if row.get("usage_available")) / len(ok), 3) if ok else 0,
        "latency_ms": {"p50": _percentile(latencies, .50), "p95": _percentile(latencies, .95),
                        "mean": round(statistics.mean(latencies), 2) if latencies else None,
                        "stdev": round(statistics.stdev(latencies), 2) if len(latencies) > 1 else 0},
        "decode_tok_s": {"mean": round(statistics.mean(speeds), 2) if speeds else None,
                          "min": round(min(speeds), 2) if speeds else None,
                          "max": round(max(speeds), 2) if speeds else None,
                          "stdev": round(statistics.stdev(speeds), 2) if len(speeds) > 1 else 0},
        "errors_detail": [row["error"] for row in samples if row.get("error")][:5],
    }


def _score(short: dict, long: dict) -> dict:
    speed = (short["decode_tok_s"]["mean"] or 0) * .35 + (long["decode_tok_s"]["mean"] or 0) * .65
    reliability = ((short["success_rate"] + long["success_rate"]) / 2) * 100
    measurement_quality = ((short.get("usage_coverage", 0) + long.get("usage_coverage", 0)) / 2) * 100
    latency = long["latency_ms"]["p95"] or 999999
    stability = max(0, 100 - ((long["latency_ms"]["stdev"] or 0) / max(1, long["latency_ms"]["mean"] or 1) * 100))
    score = speed + reliability * .8 + stability * .2 + measurement_quality * .15 - min(50, latency / 10000)
    return {"score": round(score, 2), "speed_component": round(speed, 2),
            "reliability_component": round(reliability, 2), "stability_component": round(stability, 2),
            "measurement_quality": round(measurement_quality, 2),
            "long_short_speed_ratio": round((long["decode_tok_s"]["mean"] or 0) / max(.01, short["decode_tok_s"]["mean"] or .01), 3)}


def _candidates(ctx: int, profile: str, entry: dict) -> list[dict]:
    plan = optimize_core.optimize(ctx, profile, entry=entry)
    raw = [plan.get("recommended")] + list(plan.get("alternatives") or [])
    unique = []
    seen = set()
    for candidate in raw:
        if not candidate or not candidate.get("config"):
            continue
        key = json.dumps(candidate["config"], sort_keys=True)
        if key not in seen:
            seen.add(key)
            unique.append({"config": candidate["config"], "why": candidate.get("why"), "estimates": candidate.get("estimates"), "risks": candidate.get("risks", [])})
        if len(unique) >= 6:
            break
    return unique


def run(job_id: str, cat: dict, model_id: str, context: int, profile: str, runs: int, long_chars: int):
    global _ACTIVE
    with _LOCK:
        if _ACTIVE is not None:
            raise RuntimeError("ya existe una evaluación activa")
        _ACTIVE = job_id
    entry = find(cat, validate_model_id(model_id))
    if not entry:
        with _LOCK: _ACTIVE = None
        raise ValueError("modelo desconocido")
    path = safe_child(BASE / "configs", Path(entry["config"]).name)
    original = path.read_text(encoding="utf-8")
    candidates = _candidates(context, profile, entry)
    if not candidates:
        with _LOCK: _ACTIVE = None
        raise RuntimeError("el optimizador no produjo candidatos evaluables")
    results = []
    total = len(candidates) * 2 * runs + len(candidates)
    completed = 0
    try:
        for index, candidate in enumerate(candidates):
            if job_core.is_cancel_requested(job_id):
                return {"model": entry["id"], "cancelled": True, "results": results}
            _apply_config(path, candidate["config"])
            systemctl("stop", unit_name(entry))
            if entry.get("legacy_unit"):
                systemctl("stop", entry["legacy_unit"])
            switch_to(entry["id"], cat)
            # Warm-up is excluded from the score so the first-load penalty is visible separately.
            warmup = _request(entry["port"], entry["id"], _prompt("short", 128))
            short_samples, long_samples = [], []
            for kind, target in (("short", short_samples), ("long", long_samples)):
                prompt = _prompt(kind, long_chars if kind == "long" else 256)
                for _ in range(runs):
                    if job_core.is_cancel_requested(job_id):
                        return {"model": entry["id"], "cancelled": True, "results": results}
                    target.append(_request(entry["port"], entry["id"], prompt))
                    completed += 1
                    job_core.progress(job_id, int(completed / total * 100))
            short_metrics, long_metrics = _aggregate(short_samples), _aggregate(long_samples)
            results.append({"candidate_index": index, "config": candidate["config"], "why": candidate["why"],
                            "estimates": candidate["estimates"], "risks": candidate["risks"],
                            "warmup": warmup, "short": short_metrics, "long": long_metrics,
                            "score": _score(short_metrics, long_metrics)})
            completed += 1
            job_core.progress(job_id, int(completed / total * 100))
        results.sort(key=lambda row: -row["score"]["score"])
        for rank, row in enumerate(results, 1): row["rank"] = rank
        return {"model": entry["id"], "context": context, "profile": profile,
                "runs_per_prompt": runs, "long_prompt_chars": long_chars,
                "blocked_inference": True, "measured": True, "results": results,
                "recommended_candidate": results[0]["candidate_index"] if results else None,
                "note": "Resultados medidos con prompts cortos y largos; la primera carga se muestra como warmup y no se mezcla con el score."}
    finally:
        path.write_text(original, encoding="utf-8")
        try:
            systemctl("stop", unit_name(entry))
            if entry.get("legacy_unit"):
                systemctl("stop", entry["legacy_unit"])
            switch_to(entry["id"], cat)
        except Exception:
            pass
        with _LOCK:
            _ACTIVE = None


def submit(cat: dict, model_id: str, context: int, profile: str, runs: int, long_chars: int, key: str | None = None):
    model_id = validate_model_id(model_id)
    return job_core.submit("configuration.evaluation",
                           {"model": model_id, "context": context, "profile": profile, "runs": runs, "long_prompt_chars": long_chars},
                           lambda job_id: run(job_id, cat, model_id, context, profile, runs, long_chars), key)


def apply_result(job_id: str, candidate_index: int, cat: dict):
    job = job_core.get(job_id)
    if not job or job.get("status") != "succeeded":
        raise ValueError("la evaluación no está terminada correctamente")
    result = job.get("result") or {}
    rows = result.get("results") or []
    selected = next((row for row in rows if row.get("candidate_index") == int(candidate_index)), None)
    if not selected:
        raise ValueError("candidato de evaluación inexistente")
    model_id = result.get("model") or ""
    entry = find(cat, model_id)
    if not entry:
        raise ValueError("modelo de la evaluación ya no existe")
    path = safe_child(BASE / "configs", Path(entry["config"]).name)
    backup = path.with_suffix(".json.before-evaluation-apply")
    backup.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    _apply_config(path, selected["config"])
    systemctl("stop", unit_name(entry))
    if entry.get("legacy_unit"):
        systemctl("stop", entry["legacy_unit"])
    port = switch_to(entry["id"], cat)
    return {"status": "applied", "model": entry["id"], "candidate_index": int(candidate_index), "port": port, "backup": str(backup)}
