"""
Smoke test for the agent tools. Runs each tool standalone (no LLM)
and prints a snippet of the result. Helps catch tool bugs before
integrating with Claude.
"""

from __future__ import annotations

import json
import sys

from agent.tools import DISPATCH


def run_tool(name: str, **kwargs) -> None:
    print(f"\n{'=' * 60}")
    print(f"TOOL: {name}")
    print(f"ARGS: {kwargs}")
    print("-" * 60)
    fn = DISPATCH.get(name)
    if not fn:
        print(f"ERROR: tool {name} not found in dispatch")
        return
    try:
        result = fn(**kwargs)
        if "content" in result and isinstance(result["content"], str):
            result["content"] = result["content"][:300] + "... [truncated]"
        if "events" in result and isinstance(result["events"], list):
            preview = result["events"][:3]
            if len(result["events"]) > 3:
                preview.append(f"... [{len(result['events']) - 3} more]")
            result["events"] = preview
        print(json.dumps(result, indent=2, default=str))
    except Exception as e:
        print(f"EXCEPTION: {type(e).__name__}: {e}")


def main() -> int:
    run_tool("read_failure_modes_catalog")
    run_tool("read_pipeline_code")
    run_tool("read_failure_record")

    record_result = DISPATCH["read_failure_record"]()
    if "content" in record_result:
        job_run_id = record_result["content"].get("glue_job_run_id")
        if job_run_id:
            run_tool(
                "get_glue_logs",
                job_run_id=job_run_id,
                log_group="output",
                max_events=20,
            )
        else:
            print("\n[WARN] No glue_job_run_id in failure record, skipping log fetch")
    return 0


if __name__ == "__main__":
    sys.exit(main())
