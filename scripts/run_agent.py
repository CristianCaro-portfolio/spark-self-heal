"""
Run the spark-self-heal agent on a failure record.

Usage:
  python -m scripts.run_agent                       # latest, full mode
  python -m scripts.run_agent --diagnose-only       # latest, no patch
  python -m scripts.run_agent <filename>            # specific file, full mode
  python -m scripts.run_agent <filename> --diagnose-only
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
    args = sys.argv[1:]
    mode = "full"
    filename = ""

    for a in args:
        if a == "--diagnose-only":
            mode = "diagnose"
        elif not a.startswith("--"):
            filename = a

    print(f"\n{'=' * 60}")
    print(f"spark-self-heal :: agent ({mode} mode)")
    print(f"target: {filename or '(latest failure)'}")
    print(f"{'=' * 60}")

    result = diagnose_failure(filename=filename, mode=mode, verbose=True)

    print(f"\n{'=' * 60}")
    print("FINAL RESULT")
    print(f"{'=' * 60}")
    if result["result"]:
        print(json.dumps(result["result"], indent=2))
    else:
        print("[!] Could not extract structured JSON. Raw text:")
        print(result["raw_text"])

    print(f"\n{'-' * 60}")
    print(f"Iterations: {result['iterations']}")
    print(f"Tokens: {result['tokens']['input']} in / {result['tokens']['output']} out")
    cost = result["tokens"]["input"] * 3e-6 + result["tokens"]["output"] * 15e-6
    print(f"Estimated cost: ${cost:.4f} USD")
    print(f"{'-' * 60}")

    res = result["result"]
    if not res:
        return 1

    if mode == "diagnose":
        return 0 if res.get("fm_id", "none") != "none" else 1

    p1 = res.get("phase_1", {})
    p2 = res.get("phase_2", {})
    diagnosed = p1.get("fm_id", "none") != "none"
    patched = bool(p2.get("patch_proposed"))
    return 0 if (diagnosed and patched) else 1


if __name__ == "__main__":
    sys.exit(main())
