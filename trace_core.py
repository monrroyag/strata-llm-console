"""Trazabilidad local y acotada de requests OpenAI-compatible.

No guarda secretos completos ni crece sin límite: conserva una ventana de 100
requests y limita cada prompt/razonamiento/respuesta a pocos KB para evitar OOM.
"""
from __future__ import annotations

import json
import threading
import time
import uuid
from collections import deque
from pathlib import Path

BASE = Path(__file__).resolve().parent
STORE = BASE / "data" / "traces.jsonl"
MAX_TRACES = 100
MAX_TEXT = 12000
_lock = threading.Lock()
_recent: deque[dict] = deque(maxlen=MAX_TRACES)
_loaded = False


def _clip(value, limit=MAX_TEXT):
    text = str(value or "")
    return text if len(text) <= limit else text[:limit] + "\n… [recortado]"


def _load_once():
    global _loaded
    if _loaded:
        return
    _loaded = True
    try:
        latest = {}
        for line in STORE.read_text(encoding="utf-8").splitlines()[-MAX_TRACES * 20:]:
            row = json.loads(line)
            if isinstance(row, dict) and row.get("id"):
                latest[row["id"]] = row
        for row in list(latest.values())[-MAX_TRACES:]:
            _recent.append(row)
    except (OSError, ValueError):
        pass


def _persist(row):
    STORE.parent.mkdir(parents=True, exist_ok=True)
    with STORE.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    if STORE.stat().st_size > 8_000_000:
        STORE.write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in _recent) + "\n", encoding="utf-8")


def begin(path, model, body, stream=False):
    messages = body.get("messages") if isinstance(body, dict) else None
    prompt = ""
    if isinstance(messages, list):
        for item in reversed(messages):
            if isinstance(item, dict) and item.get("role") == "user":
                content = item.get("content", "")
                prompt = content if isinstance(content, str) else json.dumps(content, ensure_ascii=False)
                break
    now = time.time()
    row = {"id": "trace_" + uuid.uuid4().hex[:16], "path": path, "model": model,
           "started_at": now, "finished_at": None, "duration_ms": None,
           "status": "running", "stream": bool(stream), "prompt": _clip(prompt, 3000),
           "reasoning": "", "response": "", "tool_calls": [], "usage": None,
           "finish_reason": None, "error": None}
    with _lock:
        _load_once()
        _recent.append(row)
        _persist(row)
    return row["id"]


def append(trace_id, reasoning="", response="", tool_call=None):
    if not any((reasoning, response, tool_call)):
        return
    with _lock:
        _load_once()
        row = next((x for x in _recent if x["id"] == trace_id), None)
        if not row:
            return
        if reasoning:
            row["reasoning"] = _clip(row["reasoning"] + str(reasoning))
        if response:
            row["response"] = _clip(row["response"] + str(response))
        if tool_call:
            row["tool_calls"].append(tool_call)
        # La persistencia ocurre al cerrar la request; no escribimos un JSONL por cada delta SSE.
        # El estado sigue disponible en memoria para el panel mientras la request está activa.


def finish(trace_id, status=200, payload=None, error=None):
    with _lock:
        _load_once()
        row = next((x for x in _recent if x["id"] == trace_id), None)
        if not row:
            return
        row["finished_at"] = time.time()
        row["duration_ms"] = round((row["finished_at"] - row["started_at"]) * 1000, 1)
        row["status"] = "completed" if status < 400 and not error else "error"
        if error:
            row["error"] = _clip(error, 2000)
        if isinstance(payload, dict):
            row["usage"] = payload.get("usage")
            choices = payload.get("choices") or []
            if choices:
                choice = choices[0] or {}
                row["finish_reason"] = choice.get("finish_reason")
                message = choice.get("message") or {}
                append_reason = message.get("reasoning_content") or ""
                append_response = message.get("content") or ""
                if append_reason:
                    row["reasoning"] = _clip(append_reason)
                if append_response:
                    row["response"] = _clip(append_response)
            if payload.get("output"):
                for item in payload["output"]:
                    if item.get("type") == "reasoning":
                        text = "".join(p.get("text", "") for p in item.get("content", []))
                        row["reasoning"] = _clip(text)
                    elif item.get("type") == "message":
                        row["response"] = _clip("".join(p.get("text", "") for p in item.get("content", [])))
        _persist(row)


_sse_buffers: dict[str, str] = {}


def append_sse(trace_id, raw):
    try:
        text = raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else raw
        with _lock:
            text = _sse_buffers.get(trace_id, "") + text
            lines = text.splitlines(keepends=True)
            _sse_buffers[trace_id] = lines.pop() if lines and not lines[-1].endswith(("\n", "\r")) else ""
        for line in lines:
            line = line.strip()
            if not line.startswith("data: ") or line == "data: [DONE]":
                continue
            data = json.loads(line[6:])
            choice = (data.get("choices") or [{}])[0]
            delta = choice.get("delta") or {}
            append(trace_id, delta.get("reasoning_content", ""), delta.get("content", ""))
            with _lock:
                row = next((x for x in _recent if x["id"] == trace_id), None)
                if row:
                    if choice.get("finish_reason") is not None:
                        row["finish_reason"] = choice.get("finish_reason")
                    if data.get("usage") is not None:
                        row["usage"] = data.get("usage")
    except (ValueError, TypeError, json.JSONDecodeError):
        pass


def list_traces(limit=50):
    with _lock:
        _load_once()
        return [dict(x) for x in list(_recent)[-min(int(limit), MAX_TRACES):][::-1]]


def get(trace_id):
    with _lock:
        _load_once()
        row = next((x for x in _recent if x["id"] == trace_id), None)
        return dict(row) if row else None
