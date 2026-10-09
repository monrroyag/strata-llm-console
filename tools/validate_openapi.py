#!/usr/bin/env python3
"""Fail CI when public OpenAPI paths drift from console_server.py routes."""
from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / "console_server.py"
SPEC = ROOT / "docs" / "api" / "openapi.json"


def discovered_paths() -> set[str]:
    tree = ast.parse(SERVER.read_text(encoding="utf-8"))
    paths: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare) and len(node.ops) == 1 and isinstance(node.ops[0], ast.Eq):
            for side in (node.left, *node.comparators):
                if isinstance(side, ast.Constant) and isinstance(side.value, str) and side.value.startswith(("/api/", "/v1/", "/health")):
                    paths.add(side.value)
    return paths


def contract_paths() -> set[str]:
    data = json.loads(SPEC.read_text(encoding="utf-8"))
    return set(data.get("paths", {}))


def main() -> int:
    source = discovered_paths()
    contract = contract_paths()
    ignored = {"/api/openapi.json"}
    missing_exact = sorted((source - ignored) - contract)
    # Prefix branches are represented by explicit public resources in OpenAPI.
    required_prefix_paths = {
        "/api/traces/{trace_id}",
        "/api/evaluations/{job_id}",
        "/api/evaluations/{job_id}/apply",
        "/api/jobs/{job_id}",
        "/api/jobs/{job_id}/cancel",
    }
    missing_templates = sorted(required_prefix_paths - contract)
    if missing_exact or missing_templates:
        print(json.dumps({"missing_exact": missing_exact, "missing_templates": missing_templates}, indent=2))
        return 1
    print(f"OpenAPI route coverage OK: {len(source - ignored)} exact source paths, {len(required_prefix_paths)} templates")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
