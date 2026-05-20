"""
Tool: read_failure_modes_catalog

Returns the catalog of known failure modes (FM-01..FM-06).
This is the agent's grounding document — diagnoses MUST map to an FM ID
present in this catalog.
"""

from __future__ import annotations

from pathlib import Path

CATALOG_PATH = Path("docs/failure-modes.md")


SCHEMA = {
    "name": "read_failure_modes_catalog",
    "description": (
        "Loads the failure modes catalog (docs/failure-modes.md). This document "
        "is the authoritative taxonomy: every diagnosis must map to a known FM ID "
        "(FM-01..FM-06). Call this once at the start of a diagnosis to ground "
        "your reasoning in the project's documented failure modes."
    ),
    "input_schema": {
        "type": "object",
        "properties": {},
        "required": [],
    },
}


def execute() -> dict:
    """Return the markdown catalog as a string."""
    if not CATALOG_PATH.exists():
        return {"error": f"Catalog not found at {CATALOG_PATH}"}

    return {
        "path": str(CATALOG_PATH),
        "content": CATALOG_PATH.read_text(),
    }
