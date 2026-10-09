"""Durable, bounded jobs for slow lifecycle and update operations."""
from __future__ import annotations

import json
import sqlite3
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path
from typing import Callable

BASE = Path(__file__).resolve().parent
DB = BASE / "data" / "jobs.sqlite3"
_LOCK = threading.Lock()
_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="strata-job")


def _connect():
    DB.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB, timeout=10)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA busy_timeout=10000")
    return con


@contextmanager
def _db():
    con = _connect()
    try:
        yield con
        con.commit()
    finally:
        con.close()


def init():
    with _db() as con:
        con.execute("""CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY,
            kind TEXT NOT NULL,
            status TEXT NOT NULL,
            payload TEXT NOT NULL,
            result TEXT,
            error TEXT,
            progress INTEGER NOT NULL DEFAULT 0,
            cancel_requested INTEGER NOT NULL DEFAULT 0,
            idempotency_key TEXT,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        )""")
        con.execute("CREATE UNIQUE INDEX IF NOT EXISTS jobs_idempotency ON jobs(idempotency_key) WHERE idempotency_key IS NOT NULL")
        con.execute("UPDATE jobs SET status='failed', error='console restarted while job was running', updated_at=? WHERE status IN ('queued','running')", (time.time(),))


init()


def _row(row):
    if not row:
        return None
    out = dict(row)
    for key in ("payload", "result"):
        if out.get(key):
            try:
                out[key] = json.loads(out[key])
            except (TypeError, ValueError):
                pass
    out["cancel_requested"] = bool(out.get("cancel_requested"))
    return out


def get(job_id: str):
    with _db() as con:
        return _row(con.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone())


def list_jobs(limit: int = 50):
    limit = max(1, min(int(limit), 100))
    with _db() as con:
        return [_row(row) for row in con.execute("SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,))]


def _update(job_id, **values):
    values["updated_at"] = time.time()
    assignments = ", ".join(f"{key}=?" for key in values)
    params = list(values.values()) + [job_id]
    with _db() as con:
        con.execute(f"UPDATE jobs SET {assignments} WHERE id=?", params)


def is_cancel_requested(job_id):
    row = get(job_id)
    return bool(row and row.get("cancel_requested"))


def progress(job_id, value: int):
    _update(job_id, progress=max(0, min(int(value), 100)))


def cancel(job_id: str) -> bool:
    row = get(job_id)
    if not row or row["status"] not in ("queued", "running"):
        return False
    _update(job_id, cancel_requested=1)
    return True


def _run(job_id: str, fn: Callable[[str], object]):
    _update(job_id, status="running", progress=1)
    try:
        result = fn(job_id)
        if is_cancel_requested(job_id):
            _update(job_id, status="cancelled", progress=100, result=json.dumps(result or {}))
        else:
            _update(job_id, status="succeeded", progress=100, result=json.dumps(result or {}))
    except Exception as exc:  # job errors are returned through the API, not lost in a worker
        _update(job_id, status="failed", progress=100, error=f"{type(exc).__name__}: {exc}")


def submit(kind: str, payload: dict, fn: Callable[[str], object], idempotency_key: str | None = None):
    now = time.time()
    with _LOCK:
        if idempotency_key:
            with _db() as con:
                existing = con.execute("SELECT * FROM jobs WHERE idempotency_key=? AND status IN ('queued','running')", (idempotency_key,)).fetchone()
                if existing:
                    return _row(existing)
        job_id = "job_" + uuid.uuid4().hex[:20]
        with _db() as con:
            con.execute("INSERT INTO jobs(id,kind,status,payload,idempotency_key,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",
                        (job_id, kind, "queued", json.dumps(payload, ensure_ascii=False), idempotency_key, now, now))
        _EXECUTOR.submit(_run, job_id, fn)
        return get(job_id)
