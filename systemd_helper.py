#!/usr/bin/env python3
"""Narrow privileged bridge for the Debian system service.

The unprivileged console can only request controlled model-template units and
its own connection drop-in. Arguments are validated before invoking systemctl.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

MODEL_UNIT = re.compile(r"^strata-console-model@[a-z0-9][a-z0-9._-]{0,63}\.service$")
ACTIONS = {"start", "restart", "stop", "enable", "disable"}
SERVICE = "strata-llm-console.service"
DROPIN = Path("/etc/systemd/system/strata-llm-console.service.d/network.conf")


def run(*args: str) -> int:
    return subprocess.run(list(args), check=False).returncode


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        return 2
    action = argv[1]
    if action == "model" and len(argv) == 4:
        requested, model_id = argv[2], argv[3]
        unit = f"strata-console-model@{model_id}.service"
        if requested not in ACTIONS or not MODEL_UNIT.fullmatch(unit):
            return 2
        return run("/usr/bin/systemctl", requested, unit)
    if action == "connection" and len(argv) == 3:
        mode = argv[2]
        if mode not in {"local", "lan"}:
            return 2
        DROPIN.parent.mkdir(parents=True, exist_ok=True)
        host = "127.0.0.1" if mode == "local" else "0.0.0.0"
        DROPIN.write_text(f"[Service]\nEnvironment=STRATA_CONSOLE_HOST={host}\n", encoding="utf-8")
        os.chmod(DROPIN, 0o644)
        return run("/usr/bin/systemctl", "daemon-reload")
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
