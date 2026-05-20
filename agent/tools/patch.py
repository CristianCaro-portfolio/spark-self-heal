"""
Tool: propose_patch

Writes the agent's proposed patched version of the pipeline to disk under
agent/patches/. The agent generates the FULL modified file contents.

The agent does NOT modify pipelines/jobs/transactions_etl.py directly.
That separation lets a human (or CI) review the patch before applying it.

This tool implements ADR-002 mode='propose':
  - Reads only the catalog and the current pipeline source
  - Writes to a dedicated patches/ directory
  - Never touches the production pipeline file
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

PATCH_DIR = Path("agent/patches")


SCHEMA = {
    "name": "propose_patch",
    "description": (
        "Writes a proposed patched version of pipelines/jobs/transactions_etl.py "
        "to disk under agent/patches/. The patched_content argument must be the "
        "COMPLETE Python source code of the modified file (not a diff). "
        "Use this only AFTER you have diagnosed the failure and decided on a fix. "
        "The patch is saved with a filename indicating the FM ID and a timestamp."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "fm_id": {
                "type": "string",
                "description": "The failure mode ID this patch addresses (e.g. 'FM-01').",
            },
            "summary": {
                "type": "string",
                "description": (
                    "One-sentence summary of the change (max 200 chars). "
                    "Will appear in commit message and PR title later."
                ),
            },
            "patched_content": {
                "type": "string",
                "description": (
                    "The COMPLETE new source code of pipelines/jobs/transactions_etl.py. "
                    "Must be valid Python. Do NOT include diff markers (---/+++/@@) - "
                    "give the entire file content as it should look after the patch."
                ),
            },
            "rationale": {
                "type": "string",
                "description": (
                    "2-4 sentence explanation of the change: what was wrong, "
                    "what the patch does, and why it's the right fix."
                ),
            },
        },
        "required": ["fm_id", "summary", "patched_content", "rationale"],
    },
}


def execute(fm_id: str, summary: str, patched_content: str, rationale: str) -> dict:
    """Persist the proposed patched file and metadata to disk."""
    PATCH_DIR.mkdir(parents=True, exist_ok=True)

    if not re.match(r"^FM-\d{2}$", fm_id):
        return {"error": f"Invalid fm_id format: {fm_id} (expected FM-XX)"}

    if "def main" not in patched_content and "import" not in patched_content:
        return {
            "error": (
                "patched_content does not look like a Python file "
                "(no 'import' or 'def main' found). Refusing to write."
            )
        }

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    base = f"{fm_id}__{timestamp}"

    patch_path = PATCH_DIR / f"{base}.py"
    meta_path = PATCH_DIR / f"{base}.meta.json"

    patch_path.write_text(patched_content)

    meta_path.write_text(json.dumps({
        "fm_id": fm_id,
        "summary": summary,
        "rationale": rationale,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "patched_file": str(patch_path),
        "line_count": patched_content.count("\n") + 1,
    }, indent=2))

    return {
        "patch_path": str(patch_path),
        "meta_path": str(meta_path),
        "line_count": patched_content.count("\n") + 1,
        "fm_id": fm_id,
        "summary": summary,
    }
