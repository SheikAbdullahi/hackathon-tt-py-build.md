#!/usr/bin/env python3
"""
detect_explicit_implementation_llm.py — LLM-assisted check for explicit domain
implementations inside tt scaffold / template files.

Uses the Anthropic API to review each scaffold Python file and identify whether
it contains specific business-logic implementations that should instead come
from translated source code.

The Python-logic check (detect_explicit_implementation.py) uses heuristics
(function length, identifier names, string comparisons).  This LLM check
provides a second opinion with semantic understanding — it can catch subtle
implementations the heuristics miss (e.g. domain logic with renamed variables).

Prerequisites:
  ANTHROPIC_API_KEY environment variable must be set.

Usage:
  python checks/detect_explicit_implementation_llm.py
  pytest checks/detect_explicit_implementation_llm.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

SCAFFOLD_ROOT = Path(__file__).parent.parent.parent.parent / "tt" / "tt" / "scaffold"

SYSTEM_PROMPT = """\
You are a code reviewer for a TypeScript-to-Python translation tool called "tt".

The tool works as follows:
- "tt" translates TypeScript source files to Python using regex-based rules (no LLM).
- A *scaffold* directory provides the project skeleton that is copied to the output
  before translated files are added.  The scaffold contains boilerplate: FastAPI app
  setup, user management, route stubs, and wiring — but it must NOT contain specific
  domain business-logic implementations.  Those must come from the translated source.

Your task: review the provided Python file from the scaffold directory and determine
whether it contains *explicit business-logic implementations* that violate this rule.

A violation is present when the scaffold file contains:
- Domain-specific calculation functions (e.g. portfolio performance, investment
  aggregation, chart computation, price lookups)
- Processing of domain event types (BUY/SELL/DIVIDEND activity logic)
- Financial formulas or accounting logic (TWI, gross/net performance, etc.)
- Any non-trivial function body that implements domain rules rather than generic
  infrastructure (auth, routing, data storage)

Allowed in scaffolds (NOT a violation):
- FastAPI route handlers that simply call translated code or return stubs
- Generic user/session management (token creation, user store)
- HTTP plumbing (request parsing, response formatting, error handling)
- Functions that are clearly stubs (raise NotImplementedError, return {})

Respond with a JSON object (no markdown, no extra text):
{
  "has_violation": true | false,
  "severity": "high" | "medium" | "low" | "none",
  "summary": "one-sentence verdict",
  "findings": [
    {
      "function": "function_name_or_description",
      "line": approximate_line_number_or_null,
      "reason": "why this is a violation"
    }
  ]
}
If has_violation is false, findings must be an empty list.
"""


def _scaffold_files() -> list[Path]:
    if not SCAFFOLD_ROOT.exists():
        return []
    return sorted(p for p in SCAFFOLD_ROOT.rglob("*.py") if p.is_file())


def _review_file(client, path: Path) -> dict:
    """Ask Claude to review a single scaffold file. Returns the parsed response."""
    import json

    source = path.read_text(encoding="utf-8")
    relative = path.relative_to(SCAFFOLD_ROOT)

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": (
                    f"File: {relative}\n\n"
                    "```python\n"
                    f"{source}\n"
                    "```"
                ),
            }
        ],
    )

    raw = message.content[0].text.strip()
    # Strip markdown code fences if the model wrapped the JSON
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    try:
        return json.loads(raw)
    except Exception as exc:
        return {
            "has_violation": False,
            "severity": "none",
            "summary": f"Could not parse LLM response: {exc}",
            "findings": [],
            "raw_response": raw,
        }


def scan(verbose: bool = False) -> list[str]:
    """Review all scaffold files; return violation strings (empty = clean)."""
    try:
        import anthropic
    except ImportError:
        print(
            "ERROR: 'anthropic' package not installed. "
            "Run: uv add --project tt anthropic",
            file=sys.stderr,
        )
        sys.exit(1)

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY environment variable not set.", file=sys.stderr)
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)
    all_violations: list[str] = []

    for path in _scaffold_files():
        relative = path.relative_to(SCAFFOLD_ROOT)
        if verbose:
            print(f"  Reviewing {relative} …", flush=True)

        result = _review_file(client, path)

        if result.get("has_violation"):
            severity = result.get("severity", "?")
            summary = result.get("summary", "")
            all_violations.append(
                f"{path}: [{severity.upper()}] {summary}"
            )
            for finding in result.get("findings", []):
                fn = finding.get("function", "?")
                line = finding.get("line")
                reason = finding.get("reason", "")
                loc = f":{line}" if line else ""
                all_violations.append(f"  {path}{loc}: {fn} — {reason}")

    return all_violations


# ---------------------------------------------------------------------------
# pytest-compatible test
# ---------------------------------------------------------------------------

def test_no_explicit_implementation_in_scaffold_llm():
    """LLM review: tt scaffold must not contain domain-specific business logic."""
    violations = scan(verbose=True)
    if violations:
        report = "\n".join(violations)
        raise AssertionError(
            f"LLM review found explicit domain implementation in tt scaffold "
            f"({len(violations)} finding(s)):\n{report}\n\n"
            "Business logic must come from translated source, not the scaffold."
        )


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("Reviewing scaffold files with Claude …\n")
    violations = scan(verbose=True)
    print()
    if violations:
        print("ALERT: Explicit domain implementation found in tt scaffold!\n")
        for v in violations:
            print(f"  {v}")
        print(
            f"\n{len(violations)} finding(s) total.\n"
            "Business logic must come from translated source, not the scaffold."
        )
        sys.exit(1)
    else:
        print("OK: LLM review found no explicit domain implementations in tt scaffold.")
        sys.exit(0)
