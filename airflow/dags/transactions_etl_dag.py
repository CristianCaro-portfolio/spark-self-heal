"""
spark-self-heal :: transactions_etl_dag
========================================

Triggers the Glue Job `spark-self-heal-transactions-etl` on AWS and
waits for completion. On failure, captures the JobRunId and run context
into a JSON file that the self-healing agent (Phase 4) will consume.

DAG: not scheduled by default. Triggered manually or by external event.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from airflow.decorators import dag
from airflow.providers.amazon.aws.operators.glue import GlueJobOperator
from airflow.providers.amazon.aws.sensors.glue import GlueJobSensor

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

GLUE_JOB_NAME = "spark-self-heal-transactions-etl"
AWS_CONN_ID = "aws_default"   # uses AWS_PROFILE env var from docker-compose
AWS_REGION = "us-east-1"

# Where failure events get persisted for the agent to consume
FAILURE_LOG_DIR = Path("/opt/airflow/logs/failures")


# ---------------------------------------------------------------------------
# Failure callback — runs on ANY task failure within this DAG
# ---------------------------------------------------------------------------

def capture_failure_context(context: dict) -> None:
    """
    Persists failure metadata to disk for the self-healing agent.

    Triggered automatically by Airflow when any task in the DAG fails.
    The agent (Phase 4) polls FAILURE_LOG_DIR for new files.
    """
    FAILURE_LOG_DIR.mkdir(parents=True, exist_ok=True)

    ti = context["task_instance"]
    dag_run = context["dag_run"]

    # Try to recover the Glue JobRunId from XCom (set by the operator)
    job_run_id = ti.xcom_pull(task_ids="trigger_glue_job") if ti else None

    failure_record = {
        "captured_at":     datetime.now(timezone.utc).isoformat(),
        "dag_id":          dag_run.dag_id,
        "run_id":          dag_run.run_id,
        "task_id":         ti.task_id if ti else None,
        "try_number":      ti.try_number if ti else None,
        "glue_job_name":   GLUE_JOB_NAME,
        "glue_job_run_id": job_run_id,
        "exception":       str(context.get("exception", "")),
        "log_url":         ti.log_url if ti else None,
    }

    # File name encodes timestamp + DAG run for the agent to triage
    filename = f"{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}__{dag_run.run_id}.json"
    out_path = FAILURE_LOG_DIR / filename

    out_path.write_text(json.dumps(failure_record, indent=2))
    print(f"[FAILURE_CALLBACK] wrote {out_path}")


# ---------------------------------------------------------------------------
# DAG definition
# ---------------------------------------------------------------------------

@dag(
    dag_id="transactions_etl",
    description="Trigger Glue Job on AWS and capture failures for the self-healing agent",
    start_date=datetime(2026, 5, 20),
    schedule=None,                          # manual trigger only
    catchup=False,
    max_active_runs=1,
    default_args={
        "owner": "cristian",
        "retries": 0,                       # the agent handles retries, not Airflow
        "retry_delay": timedelta(minutes=2),
        "on_failure_callback": capture_failure_context,
    },
    tags=["spark-self-heal", "glue", "fintech"],
)
def transactions_etl_dag():

    trigger_glue_job = GlueJobOperator(
        task_id="trigger_glue_job",
        job_name=GLUE_JOB_NAME,
        aws_conn_id=AWS_CONN_ID,
        region_name=AWS_REGION,
        wait_for_completion=False,          # we use a separate sensor task
        # script_args could override Glue defaults here if needed
    )

    wait_for_completion = GlueJobSensor(
        task_id="wait_for_completion",
        job_name=GLUE_JOB_NAME,
        run_id="{{ ti.xcom_pull(task_ids='trigger_glue_job') }}",
        aws_conn_id=AWS_CONN_ID,
        poke_interval=30,                   # check every 30s
        timeout=60 * 15,                    # max 15 min before sensor itself fails
        mode="poke",                        # blocking; for portfolio scale this is fine
    )

    trigger_glue_job >> wait_for_completion


transactions_etl_dag()
