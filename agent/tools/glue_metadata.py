"""
Tool: get_glue_job_run_metadata

Returns the metadata of a specific Glue Job run via the Glue API,
including the `ErrorMessage` field that Glue sets when a job fails.

This is the cheapest path to the root cause: instead of pulling tens of
kilobytes of CloudWatch logs and parsing them, the Glue API exposes a
short structured exception string set by the script's last raise.

Prefer this tool over get_glue_logs unless you need to inspect the full
stack trace or print output.
"""

from __future__ import annotations

import boto3
from botocore.exceptions import ClientError


SCHEMA = {
    "name": "get_glue_job_run_metadata",
    "description": (
        "Returns the metadata of a specific Glue Job run, including the "
        "ErrorMessage field set when the job fails. This is the fastest "
        "path to the root cause: the ErrorMessage typically contains a "
        "short, structured exception string (e.g. "
        "'RuntimeError: Schema drift detected ... unexpected=[\"fraud_score\"]'). "
        "Call this FIRST when diagnosing a failure; only fall back to "
        "get_glue_logs if the ErrorMessage is missing or unclear."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "job_name": {
                "type": "string",
                "description": (
                    "The Glue Job name. For this project it is always "
                    "'spark-self-heal-transactions-etl'."
                ),
            },
            "job_run_id": {
                "type": "string",
                "description": "The Glue JobRunId, e.g. 'jr_b2f5c4509e8b4e163...'.",
            },
        },
        "required": ["job_name", "job_run_id"],
    },
}


def execute(job_name: str, job_run_id: str) -> dict:
    """Fetch a single Glue job run's metadata."""
    client = boto3.client("glue", region_name="us-east-1")
    try:
        response = client.get_job_run(JobName=job_name, RunId=job_run_id)
    except ClientError as e:
        return {
            "error": (
                f"Glue API failure for {job_name}/{job_run_id}: "
                f"{e.response['Error']['Code']} :: {e.response['Error']['Message']}"
            ),
        }

    run = response.get("JobRun", {})
    return {
        "job_name": job_name,
        "job_run_id": job_run_id,
        "state": run.get("JobRunState"),
        "error_message": run.get("ErrorMessage"),
        "started_on": str(run.get("StartedOn", "")),
        "completed_on": str(run.get("CompletedOn", "")),
        "execution_time_sec": run.get("ExecutionTime"),
    }
