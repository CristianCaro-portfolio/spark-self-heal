"""
spark-self-heal :: diagnose

High-level entry point: given a failure file (or the latest one),
run the diagnostic agent and return a structured result.
"""

from __future__ import annotations

import json
import re

from agent.llm import AgentRun, run_agent
from agent.prompts import SYSTEM_PROMPT_DIAGNOSE


def diagnose_failure(filename: str = "", verbose: bool = True) -> dict:
    """
    Diagnose the failure described by a failure record file.

    Args:
        filename: Name of the file in airflow/logs/failures/. Empty = most recent.
        verbose:  Print the agent's step-by-step reasoning.

    Returns:
        dict with keys: diagnosis (parsed JSON), run (AgentRun), raw_text.
    """
    user_prompt = (
        f"Diagnose the failure recorded in '{filename}'. "
        "If empty, use the most recent failure record. "
        "Follow the system instructions exactly and return your diagnosis "
        "as a single JSON code block."
    )

    run: AgentRun = run_agent(
        system_prompt=SYSTEM_PROMPT_DIAGNOSE,
        user_prompt=user_prompt,
        verbose=verbose,
    )

    diagnosis = _extract_json(run.final_text)

    return {
        "diagnosis": diagnosis,
        "raw_text": run.final_text,
        "iterations": len(run.steps),
        "tokens": {
            "input": run.total_input_tokens,
            "output": run.total_output_tokens,
        },
    }


def _extract_json(text: str) -> dict | None:
    """Pull the fenced JSON block out of the model's final answer."""
    match = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        return None
