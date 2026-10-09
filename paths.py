"""Portable code/runtime paths for installed and source checkouts."""
from __future__ import annotations

import os
import sys
from pathlib import Path

_SOURCE_ROOT = Path(__file__).resolve().parent
_INSTALLED_ASSETS = Path(sys.prefix) / "strata-llm-console"
CODE_ROOT = _SOURCE_ROOT if (_SOURCE_ROOT / "web").is_dir() else _INSTALLED_ASSETS
_DEFAULT_STATE_ROOT = CODE_ROOT if CODE_ROOT == _SOURCE_ROOT else Path.home() / ".local" / "state" / "strata-llm-console"
STATE_ROOT = Path(os.environ.get("STRATA_CONSOLE_STATE_DIR", str(_DEFAULT_STATE_ROOT))).expanduser().resolve()


def runtime_path(*parts: str) -> Path:
    return STATE_ROOT.joinpath(*parts)


def code_path(*parts: str) -> Path:
    return CODE_ROOT.joinpath(*parts)
