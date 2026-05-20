"""
Tool: read_pipeline_code

Returns the source code of the PySpark pipeline.
The agent needs this to propose targeted patches.
"""

from __future__ import annotations

from pathlib import Path

PIPELINE_PATH = Path("pipelines/jobs/transactions_etl.py")


SCHEMA = {
    "name": "read_pipeline_code",
    "description": (
        "Loads the source code of the PySpark Glue job under diagnosis "
        "(pipelines/jobs/transactions_etl.py). Use this to identify the "
        "specific lines that need patching once a failure mode is diagnosed."
    ),
    "input_schema": {
        "type": "object",
        "properties": {},
        "required": [],
    },
}


def execute() -> dict:
    """Return the pipeline source code as a string."""
    if not PIPELINE_PATH.exists():
        return {"error": f"Pipeline source not found at {PIPELINE_PATH}"}

    code = PIPELINE_PATH.read_text()
    return {
        "path": str(PIPELINE_PATH),
        "line_count": code.count("\n") + 1,
        "content": code,
    }
