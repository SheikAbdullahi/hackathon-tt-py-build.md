#!/usr/bin/env python3
"""
detect_direct_mappings.py — check that tt/ contains no project-specific import mappings.

The tt core must be project-agnostic.  Project-specific TypeScript module paths
(e.g. ``"@ghostfolio/api/…"``, ``"@calcom/lib/…"``) must NOT appear as string
literals inside tt/tt/*.py.  They belong in a per-project tt_import_map.json
file placed in the relevant scaffold directory.

A *project-specific* path is defined as a scoped npm specifier with two or more
path segments after the package name:

    @scope/package          ← allowed  (published library, e.g. @nestjs/common)
    @scope/package/subpath  ← VIOLATION (internal project module)

Exits with code 1 and prints an alert if any violations are found.
Run directly:
  python checks/detect_direct_mappings.py
Or as a test:
  pytest checks/detect_direct_mappings.py
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Source root — only scan first-party tt code, not .venv
# ---------------------------------------------------------------------------

TT_SRC = Path(__file__).parent.parent.parent.parent / "tt" / "tt"

# ---------------------------------------------------------------------------
# Detection pattern
# ---------------------------------------------------------------------------

# Matches a scoped npm module path with at least one sub-path segment, i.e.
# @scope/name/anything — these are always project-internal module paths, not
# published library references.
_PROJECT_PATH_RE = re.compile(
    r"@[A-Za-z][A-Za-z0-9_-]*/[A-Za-z0-9_.-]+/[A-Za-z0-9_./-]+"
)


# ---------------------------------------------------------------------------
# Scanning helpers
# ---------------------------------------------------------------------------

def _source_files() -> list[Path]:
    """Return all .py files under TT_SRC (excluding .venv)."""
    return sorted(
        p for p in TT_SRC.rglob("*.py")
        if ".venv" not in p.parts
    )


def _check_string_constants(tree: ast.Module, path: Path) -> list[str]:
    """Return violations for project-specific paths found in string literals."""
    violations: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if _PROJECT_PATH_RE.search(node.value):
                violations.append(
                    f"{path}:{node.lineno}: project-specific TS module path "
                    f"found in string literal: {node.value!r}"
                )
    return violations


def scan() -> list[str]:
    """Scan all source files; return violation strings (empty list = clean)."""
    all_violations: list[str] = []
    for path in _source_files():
        source = path.read_text(encoding="utf-8")
        try:
            tree = ast.parse(source, filename=str(path))
        except SyntaxError as exc:
            all_violations.append(f"{path}: SyntaxError during parse: {exc}")
            continue
        all_violations.extend(_check_string_constants(tree, path))
    return all_violations


# ---------------------------------------------------------------------------
# pytest-compatible test function
# ---------------------------------------------------------------------------

def test_no_direct_mappings_in_tt():
    """tt/ source must not contain project-specific TS module path strings."""
    violations = scan()
    if violations:
        report = "\n".join(violations)
        raise AssertionError(
            f"Project-specific import mappings detected in tt/ source "
            f"({len(violations)} finding(s)):\n{report}\n\n"
            "Move these mappings to the project's tt_import_map.json scaffold file."
        )


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    violations = scan()
    if violations:
        print("ALERT: Project-specific import mappings found in tt/ source!\n")
        for v in violations:
            print(f"  {v}")
        print(
            f"\n{len(violations)} finding(s) total.\n"
            "Move these mappings to the project's tt_import_map.json scaffold file."
        )
        sys.exit(1)
    else:
        print("OK: No project-specific import mappings found in tt/ source.")
        sys.exit(0)
