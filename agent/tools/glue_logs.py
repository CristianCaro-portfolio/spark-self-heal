"""
Tool: get_glue_logs

Fetches CloudWatch logs for a specific Glue JobRunId.

Glue writes to two log groups:
  /aws-glue/jobs/output  — stdout/stderr from the user script (our print/raise)
  /aws-glue/jobs/error   — driver-side exceptions when the script crashes

For diagnosis, the error log group is usually more informative.
"""

from __future__ import annotations

import boto3
from botocore.exceptions import ClientError

LOG_GROUP_OUTPUT = "/aws-glue/jobs/output"
LOG_GROUP_ERROR = "/aws-glue/jobs/error"

DEFAULT_MAX_EVENTS = 100


SCHEMA = {
    "name": "get_glue_logs",
    "description": (
        "Retrieves CloudWatch log events for a specific Glue Job run. "
        "Use this to inspect the stack trace and runtime output of a failed run. "
        "Prefer log_group='error' to find the root exception; use 'output' to "
        "see the user script's print statements and structured RuntimeErrors."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "job_run_id": {
                "type": "string",
                "description": "The Glue JobRunId, e.g. 'jr_b2f5c4509e8b4e163...'.",
            },
            "log_group": {
                "type": "string",
                "enum": ["output", "error"],
                "description": (
                    "Which log group to query. 'output' = user script stdout/stderr "
                    "(print, structured errors). 'error' = driver-side crashes."
                ),
            },
            "max_events": {
                "type": "integer",
                "description": f"Max log events to return. Default {DEFAULT_MAX_EVENTS}.",
            },
        },
        "required": ["job_run_id", "log_group"],
    },
}


def execute(job_run_id: str, log_group: str, max_events: int = DEFAULT_MAX_EVENTS) -> dict:
    """Fetch up to `max_events` CloudWatch log events for the given JobRunId."""
    log_group_name = LOG_GROUP_ERROR if log_group == "error" else LOG_GROUP_OUTPUT

    client = boto3.client("logs", region_name="us-east-1")

    try:
        response = client.get_log_events(
            logGroupName=log_group_name,
            logStreamName=job_run_id,
            limit=max_events,
            startFromHead=True,
        )
    except ClientError as e:
        return {
            "error": (
                f"CloudWatch lookup failed for {job_run_id} "
                f"in {log_group_name}: {e.response['Error']['Code']}"
            ),
            "hint": (
                "If the stream is missing, the job may not have produced logs yet, "
                "or 'continuous-cloudwatch-log' was not enabled."
            ),
        }

    events = response.get("events", [])

    return {
        "job_run_id": job_run_id,
        "log_group": log_group_name,
        "event_count": len(events),
        "events": [
            {"timestamp": e["timestamp"], "message": e["message"].rstrip()}
            for e in events
        ],
    }
