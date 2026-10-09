#!/usr/bin/env python3
"""Run one catalogued model under the dedicated Strata service account."""
from __future__ import annotations

import os
import sys
from pathlib import Path

from console_core import CONFIGS, STATE_ROOT, find, load_catalog, validate_model_id


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: model_runner.py MODEL_ID", file=sys.stderr)
        return 2
    model_id = validate_model_id(argv[1])
    catalog = load_catalog()
    entry = find(catalog, model_id)
    if not entry:
        print(f"unknown model: {model_id}", file=sys.stderr)
        return 2
    raw_root = Path(str(catalog.get("engine_root", ""))).expanduser()
    root = (STATE_ROOT / raw_root).resolve() if not raw_root.is_absolute() else raw_root.resolve()
    python_bin = root / ".venv" / "bin" / "python"
    if not python_bin.is_file():
        python_bin = Path("/usr/bin/python3")
    config = CONFIGS / Path(entry["config"]).name
    server = root / "serve" / "server.py"
    if not config.is_file() or not server.is_file():
        print("engine checkout or model configuration is not ready", file=sys.stderr)
        return 3
    os.execv(str(python_bin), [str(python_bin), str(server), "--engine", "strata", "--config", str(config), "--port", str(int(entry["port"]))])
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
