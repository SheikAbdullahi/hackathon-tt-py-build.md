#!/usr/bin/env python3
"""
Use Claude to explain the coding strategy of the tt translator.

Reads tt/tt/translator.py and asks Claude (claude-opus-4-6, adaptive thinking)
to produce a concise explanation of how the rule-based TS→Python translation works.

Usage:
  uv run --project tt python checks/explain_tt_strategy.py
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.resolve()
TRANSLATOR_PATH = REPO_ROOT / "tt"

PROMPT = """\
You are reviewing a Python source file that implements a rule-based TypeScript-to-Python \
translator for the Ghostfolio portfolio calculator codebase. No LLMs are involved in the \
translation itself — only regex passes.

Read the source below and write a concise technical explanation of the coding strategy:
- How the translation pipeline is structured (passes, their order, why order matters)
- What each major pass does and what TS construct it handles
- Key design decisions and trade-offs (e.g. no AST, regex only, approximate output)
- Any notable patterns, helper mappings, or edge cases handled

Keep the explanation under 400 words. Be specific and technical.

--- translator.py ---
{source}
--- end ---
"""


def main() -> int:
    import anthropic

    if not TRANSLATOR_PATH.exists():
        print(f"ERROR: {TRANSLATOR_PATH} not found", file=sys.stderr)
        return 1

    source = TRANSLATOR_PATH.read_text(encoding="utf-8")
    client = anthropic.Anthropic()

    print("=== tt translation strategy (via Claude) ===\n")

    with client.messages.stream(
        model="claude-opus-4-6",
        max_tokens=1024,
        thinking={"type": "adaptive"},
        messages=[
            {
                "role": "user",
                "content": PROMPT.format(source=source),
            }
        ],
    ) as stream:
        for text in stream.text_stream:
            print(text, end="", flush=True)

    print("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
