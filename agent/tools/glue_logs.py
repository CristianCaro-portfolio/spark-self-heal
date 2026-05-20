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

DEFAULT_MAX_EVENTS = 30
HARD_CAP_MAX_EVENTS = 100
MAX_MESSAGE_CHARS = 800


SCHEMA = {
    "name": "get_glue_logs",
    "description": (
        "Retrieves CloudWatch log events for a specific Glue Job run. "
        "Use this when get_glue_job_run_metadata's ErrorMessage is not enough "
        "and you need the surrounding stack trace or print output. "
        "By default returns the END of the stream (where the failure traceback lives). "
        "Each message is truncated to ~800 chars to keep the context window small."
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
                "description": (
                    f"Max log events to return. Default {DEFAULT_MAX_EVENTS}, "
                    f"hard-capped at {HARD_CAP_MAX_EVENTS} to protect the context window."
                ),
            },
            "from_head": {
                "type": "boolean",
                "description": (
                    "If true, reads from the start of the stream (job bootstrap). "
                    "If false (default), reads from the end (where failures appear)."
                ),
            },
        },
        "required": ["job_run_id", "log_group"],
    },
}


def execute(
    job_run_id: str,
    log_group: str,
    max_events: int = DEFAULT_MAX_EVENTS,
    from_head: bool = False,
) -> dict:
    """Fetch CloudWatch log events for the given JobRunId, truncated for token safety."""
    log_group_name = LOG_GROUP_ERROR if log_group == "error" else LOG_GROUP_OUTPUT
    capped_limit = min(int(max_events), HARD_CAP_MAX_EVENTS)

    client = boto3.client("logs", region_name="us-east-1")

    try:
        response = client.get_log_events(
            logGroupName=log_group_name,
            logStreamName=job_run_id,
            limit=capped_limit,
            startFromHead=from_head,
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
        "from_head": from_head,
        "event_count": len(events),
        "max_message_chars": MAX_MESSAGE_CHARS,
        "events": [
            {
                "timestamp": e["timestamp"],
                "message": e["message"].rstrip()[:MAX_MESSAGE_CHARS],
            }
            for e in events
        ],
    }
