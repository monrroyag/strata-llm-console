"""Transaccional runtime state for the console.

The SQLite store is the canonical source for control-plane metadata. Legacy JSON
files remain as sanitized compatibility exports and are imported once when the
store has no value for a key.
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path

BASE = Path(__file__).resolve().parent
DB = BASE / "data" / "state.sqlite3"
_LOCK = threading.RLock()


@contextmanager
def connection():
    DB.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB, timeout=10, isolation_level=None)
    con.row_factory = sqlite3.Row
    try:
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("PRAGMA synchronous=FULL")
        con.execute("PRAGMA busy_timeout=10000")
        con.execute("""CREATE TABLE IF NOT EXISTS runtime_state (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at REAL NOT NULL
        )""")
        try:
            DB.chmod(0o600)
        except OSError:
            pass
        yield con
    finally:
        con.close()


def _decode(value: str):
    return json.loads(value)


def get(key: str):
    with _LOCK, connection() as con:
        row = con.execute("SELECT value FROM runtime_state WHERE key=?", (key,)).fetchone()
        return _decode(row["value"]) if row else None


def put(key: str, value) -> None:
    encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    now = time.time()
    with _LOCK, connection() as con:
        con.execute("BEGIN IMMEDIATE")
        con.execute("""INSERT INTO runtime_state(key,value,updated_at) VALUES(?,?,?)
                     ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at""",
                    (key, encoded, now))
        con.execute("COMMIT")


def delete(key: str) -> None:
    with _LOCK, connection() as con:
        con.execute("BEGIN IMMEDIATE")
        con.execute("DELETE FROM runtime_state WHERE key=?", (key,))
        con.execute("COMMIT")


def load_or_migrate(key: str, legacy_path: Path, default):
    current = get(key)
    if current is not None:
        return current
    try:
        current = json.loads(legacy_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        current = default
    put(key, current)
    return current


def atomic_json_export(path: Path, value, mode: int = 0o600) -> None:
    """Write a compatibility JSON export without torn files."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    payload = json.dumps(value, indent=2, ensure_ascii=False) + "\n"
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    fd = os.open(tmp, flags, mode)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fd = None
            fh.write(payload)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
        try:
            path.chmod(mode)
            dir_fd = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
        except OSError:
            pass
    finally:
        if fd is not None:
            os.close(fd)
        try:
            tmp.unlink()
        except FileNotFoundError:
            pass


# Create the schema at import time so startup failures are visible immediately.
with connection():
    pass
