"""
Tool: read_failure_record

Reads a failure event JSON written by the Airflow callback
(see airflow/dags/transactions_etl_dag.py :: capture_failure_context).

This is the agent's entry point — without a failure record, there is
nothing to diagnose.
"""

from __future__ import annotations

import json
from pathlib import Path

FAILURE_LOG_DIR = Path("airflow/logs/failures")


SCHEMA = {
    "name": "read_failure_record",
    "description": (
        "Reads a single failure event JSON file produced by Airflow's "
        "on_failure_callback. Returns the captured context including "
        "the Glue JobRunId, the exception message, and links to logs. "
        "Use this as the first step of any diagnosis — it is the agent's "
        "entry point into the incident."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "filename": {
                "type": "string",
                "description": (
                    "Name of the failure file inside airflow/logs/failures/. "
                    "Example: '20260520T125955Z__manual_fm01_20260520T125819Z.json'. "
                    "If empty, the most recent failure file is loaded."
                ),
            },
        },
        "required": [],
    },
}


def execute(filename: str = "") -> dict:
    """Load a failure record from disk and return its parsed JSON."""
    if not FAILURE_LOG_DIR.exists():
        return {"error": f"Failure log dir does not exist: {FAILURE_LOG_DIR}"}

    if filename:
        path = FAILURE_LOG_DIR / filename
        if not path.exists():
            return {"error": f"File not found: {path}"}
    else:
        files = sorted(
            FAILURE_LOG_DIR.glob("*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if not files:
            return {"error": f"No failure records found in {FAILURE_LOG_DIR}"}
        path = files[0]

    try:
        return {
            "filename": path.name,
            "content": json.loads(path.read_text()),
        }
    except json.JSONDecodeError as e:
        return {"error": f"Invalid JSON in {path.name}: {e}"}
