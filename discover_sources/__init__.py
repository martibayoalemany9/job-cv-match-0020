"""Multi-source job discovery (Apify, Greenhouse, Lever, Gmail, eFC, APIs)."""
from __future__ import annotations

__all__ = [
    "discover_all",
]


def discover_all(**kwargs):
    from discover_all_sources import discover_all as _main

    return _main(**kwargs)
