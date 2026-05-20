"""
spark-self-heal :: diagnose

High-level entry point: given a failure file (or the latest one),
run the agentic loop and return a structured result.

When mode='full', the agent both diagnoses and proposes a patch.
When mode='diagnose', the agent only diagnoses (no patch).
"""

from __future__ import annotations

import json
import re
from typing import Literal

from agent.llm import AgentRun, run_agent
from agent.prompts import SYSTEM_PROMPT_DIAGNOSE, SYSTEM_PROMPT_FULL

Mode = Literal["diagnose", "full"]


def diagnose_failure(
    filename: str = "",
    mode: Mode = "full",
    verbose: bool = True,
) -> dict:
    """
    Run the agent against a failure record file.

    Args:
        filename: Name of the file in airflow/logs/failures/. Empty = most recent.
        mode:     'diagnose' = phase 1 only; 'full' = phase 1 + phase 2.
        verbose:  Print step-by-step progress.

    Returns:
        dict with keys: result (parsed JSON), raw_text, iterations, tokens.
    """
    system_prompt = SYSTEM_PROMPT_FULL if mode == "full" else SYSTEM_PROMPT_DIAGNOSE

    user_prompt = (
        f"Process the failure recorded in '{filename}'. "
        "If empty, use the most recent failure record. "
        "Follow the system instructions exactly. "
        "Return ONE JSON code block at the end."
    )

    run: AgentRun = run_agent(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        verbose=verbose,
    )

    parsed = _extract_json(run.final_text)

    return {
        "result": parsed,
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
