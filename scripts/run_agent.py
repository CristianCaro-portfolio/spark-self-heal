"""
Run the diagnostic agent against the most recent failure record (or
a specific file passed as the first argument).

Usage:
  python -m scripts.run_agent                                # latest
  python -m scripts.run_agent 20260520T125955Z__manual_fm01_...json
"""

from __future__ import annotations

import json
import sys

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from agent.diagnose import diagnose_failure


def main() -> int:
    filename = sys.argv[1] if len(sys.argv) > 1 else ""

    print(f"\n{'=' * 60}")
    print(f"spark-self-heal :: diagnose")
    print(f"target: {filename or '(latest failure)'}")
    print(f"{'=' * 60}")

    result = diagnose_failure(filename=filename, verbose=True)

    print(f"\n{'=' * 60}")
    print("FINAL DIAGNOSIS")
    print(f"{'=' * 60}")
    if result["diagnosis"]:
        print(json.dumps(result["diagnosis"], indent=2))
    else:
        print("[!] Could not extract structured JSON. Raw text:")
        print(result["raw_text"])

    print(f"\n{'-' * 60}")
    print(f"Iterations: {result['iterations']}")
    print(f"Tokens: {result['tokens']['input']} in / {result['tokens']['output']} out")
    cost = result['tokens']['input'] * 3e-6 + result['tokens']['output'] * 15e-6
    print(f"Estimated cost: ${cost:.4f} USD")
    print(f"{'-' * 60}")

    return 0 if result["diagnosis"] else 1


if __name__ == "__main__":
    sys.exit(main())
