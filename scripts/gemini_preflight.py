"""Live Gemini pre-flight for the model tiers named in DECISIONS.md Entry #26.

Makes one ``generateContent`` call against each of the Flash and Pro model
strings resolved from ``gemini_factory`` (env-var overridable). Prints the
model name, HTTP-equivalent status, and latency in ms. Exits non-zero if
either call fails.

This is the re-runnable version of the one-off pre-flight behind Entry #26.
Preview models can be deprecated with as little as 2 weeks' notice — do NOT
rely on the initial 2026-07-13 check being valid indefinitely.

Usage:
    export GEMINI_API_KEY=...
    python scripts/gemini_preflight.py
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.agents.gemini_factory import (  # noqa: E402
    GeminiError,
    flash,
    pro,
)

_PROMPT = "Reply with exactly the word: OK"


def _probe(label: str, model_name: str, generate) -> tuple[bool, float, str]:
    start = time.perf_counter()
    try:
        text = generate(_PROMPT).strip()
    except GeminiError as exc:
        elapsed_ms = (time.perf_counter() - start) * 1000
        print(f"[{label}] model={model_name} status=ERROR latency={elapsed_ms:.0f}ms detail={exc}")
        return False, elapsed_ms, ""
    elapsed_ms = (time.perf_counter() - start) * 1000
    print(f"[{label}] model={model_name} status=200 latency={elapsed_ms:.0f}ms reply={text!r}")
    return True, elapsed_ms, text


def main() -> int:
    if not os.environ.get("GEMINI_API_KEY"):
        print("ERROR: GEMINI_API_KEY not set", file=sys.stderr)
        return 1

    flash_client = flash()
    pro_client = pro()

    flash_ok, _, _ = _probe("flash", flash_client.model_name, flash_client.generate_content)
    pro_ok, _, _ = _probe("pro", pro_client.model_name, pro_client.generate_content)

    if flash_ok and pro_ok:
        print("PRE-FLIGHT PASS: both tiers reachable.")
        return 0
    print(
        "PRE-FLIGHT FAIL: at least one tier unreachable. Per DECISIONS.md "
        "Entry #26, set GEMINI_PRO_MODEL=gemini-3.5-flash to fall back.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
