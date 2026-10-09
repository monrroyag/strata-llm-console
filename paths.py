"""Portable code/runtime paths for installed and source checkouts."""
from __future__ import annotations

import os
from pathlib import Path

CODE_ROOT = Path(__file__).resolve().parent
STATE_ROOT = Path(os.environ.get("STRATA_CONSOLE_STATE_DIR", str(CODE_ROOT))).expanduser().resolve()


def runtime_path(*parts: str) -> Path:
    return STATE_ROOT.joinpath(*parts)


def code_path(*parts: str) -> Path:
    return CODE_ROOT.joinpath(*parts)
