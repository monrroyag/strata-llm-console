"""Evidence-based discovery for the official Strata engine only."""
from __future__ import annotations

import runtime_drivers


def status(strata_host: str, strata_port: int, catalog: dict | None = None) -> dict:
    """Detect the Strata checkout and live API without starting processes."""
    checkout = (catalog or {}).get("engine_root")
    return {"backends": runtime_drivers.discover_all(strata_host, strata_port, checkout)}
