"""
spark-self-heal :: LLM client with tool-use loop

Implements the agentic loop:
  user prompt  ->  Claude  ->  tool_use blocks  ->  execute tools locally
              ^                                              |
              |--------- tool_result blocks <----------------

The loop terminates when Claude returns stop_reason="end_turn".

A hard cap (MAX_ITERATIONS) protects against runaway loops in case the
model gets stuck in a tool-calling cycle.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any

from anthropic import Anthropic

from agent.tools import DISPATCH, SCHEMAS

MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5")
MAX_TOKENS = 4096
MAX_ITERATIONS = 10


@dataclass
class AgentStep:
    """One iteration of the agentic loop."""
    iteration: int
    text: str = ""
    tool_calls: list[dict] = field(default_factory=list)
    tool_results: list[dict] = field(default_factory=list)
    stop_reason: str = ""


@dataclass
class AgentRun:
    """The full record of an agent run."""
    final_text: str = ""
    steps: list[AgentStep] = field(default_factory=list)
    total_input_tokens: int = 0
    total_output_tokens: int = 0


def run_agent(system_prompt: str, user_prompt: str, verbose: bool = True) -> AgentRun:
    """
    Run the agentic loop until Claude stops with end_turn or the iteration cap.

    Args:
        system_prompt: The agent's role and rules (loaded from agent/prompts.py).
        user_prompt:   The specific task for this run (e.g. "diagnose this failure").
        verbose:       If True, print step-by-step progress to stdout.

    Returns:
        AgentRun: full trace including final text answer.
    """
    client = Anthropic()
    run = AgentRun()

    messages: list[dict] = [{"role": "user", "content": user_prompt}]

    for iteration in range(1, MAX_ITERATIONS + 1):
        step = AgentStep(iteration=iteration)
        if verbose:
            print(f"\n{'=' * 60}")
            print(f"ITERATION {iteration}")
            print(f"{'=' * 60}")

        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=system_prompt,
            tools=SCHEMAS,
            messages=messages,
        )

        run.total_input_tokens += response.usage.input_tokens
        run.total_output_tokens += response.usage.output_tokens
        step.stop_reason = response.stop_reason or ""

        text_blocks = [b for b in response.content if b.type == "text"]
        tool_use_blocks = [b for b in response.content if b.type == "tool_use"]

        if text_blocks:
            step.text = "\n".join(b.text for b in text_blocks)
            if verbose:
                print(f"\n[claude text]\n{step.text}")

        if response.stop_reason == "end_turn" and not tool_use_blocks:
            run.final_text = step.text
            run.steps.append(step)
            if verbose:
                print(f"\n[end_turn] agent finished after {iteration} iteration(s)")
            break

        tool_result_blocks: list[dict] = []
        for tool_block in tool_use_blocks:
            tool_name = tool_block.name
            tool_input = tool_block.input
            tool_id = tool_block.id

            if verbose:
                print(f"\n[tool_call] {tool_name}({json.dumps(tool_input)[:120]})")

            step.tool_calls.append({
                "name": tool_name,
                "input": tool_input,
                "id": tool_id,
            })

            try:
                result = DISPATCH[tool_name](**tool_input)
            except Exception as e:
                result = {"error": f"Tool execution raised: {type(e).__name__}: {e}"}

            step.tool_results.append({"id": tool_id, "result": result})

            if verbose:
                summary = _summarize_result(result)
                print(f"[tool_result] {summary}")

            tool_result_blocks.append({
                "type": "tool_result",
                "tool_use_id": tool_id,
                "content": json.dumps(result, default=str),
            })

        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": tool_result_blocks})

        run.steps.append(step)
    else:
        if verbose:
            print(f"\n[WARN] hit max iterations ({MAX_ITERATIONS}) without end_turn")
        run.final_text = (
            "Agent stopped due to iteration cap. "
            "Inspect run.steps for partial diagnosis."
        )

    return run


def _summarize_result(result: Any) -> str:
    """One-line preview of a tool result for verbose logging."""
    if isinstance(result, dict):
        if "error" in result:
            return f"ERROR: {result['error']}"
        if "content" in result:
            content = result["content"]
            length = len(content) if isinstance(content, str) else "n/a"
            return f"OK (content len={length})"
        if "events" in result:
            return f"OK ({result.get('event_count', '?')} events)"
        return f"OK ({list(result.keys())})"
    return str(result)[:80]
