#!/usr/bin/env python3
"""
detect_scaffold_bloat.py — detect scaffold files that contain more than API wiring.

Scaffold files copied by tt into the translation output must contain only:
  - FastAPI endpoint functions (decorated with @app.*)
  - A dataclass for in-memory state (UserState)
  - Token/auth helpers (_make_tokens, _get_user)
  - Module-level constants and the FastAPI app instance

Any private helper function (name starts with '_') beyond the minimal auth
wiring indicates that domain logic has crept into the scaffold.  The tt tool
must not pre-produce logic in scaffold files that gets copied verbatim into
the translation — the translated code must be actually translated code.

Usage:
  python detect_scaffold_bloat.py
  pytest detect_scaffold_bloat.py
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
SCAFFOLD_ROOT = PROJECT_ROOT / "tt" / "tt" / "scaffold"

# Private helper functions that are allowed in scaffold (minimal HTTP wiring).
ALLOWED_PRIVATE_FUNCS: frozenset[str] = frozenset({
    "_make_tokens",
    "_get_user",
    "_try_calculator",  # thin delegation to translated code
})

# Maximum number of non-trivial statements allowed in any single endpoint function.
# Beyond this, the endpoint is doing computation that should be in translated code.
MAX_ENDPOINT_STATEMENTS = 40


def _count_statements(node: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    """Count non-trivial statements (excludes docstrings)."""
    count = 0
    for child in ast.walk(node):
        if child is node:
            continue
        if isinstance(child, ast.stmt):
            if (
                isinstance(child, ast.Expr)
                and isinstance(getattr(child, "value", None), ast.Constant)
                and isinstance(child.value.value, str)
            ):
                continue
            count += 1
    return count


def _is_endpoint(func: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """Check if a function has a FastAPI route decorator (@app.*)."""
    for dec in func.decorator_list:
        if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute):
            if isinstance(dec.func.value, ast.Name) and dec.func.value.id == "app":
                return True
        if isinstance(dec, ast.Attribute):
            if isinstance(dec.value, ast.Name) and dec.value.id == "app":
                return True
    return False


def scan() -> list[str]:
    """Scan scaffold for bloat; return violation strings."""
    if not SCAFFOLD_ROOT.exists():
        return []

    violations: list[str] = []
    # Only check main.py — helper libraries (date_fns, lodash, models) are
    # generic runtime support, not domain logic.
    for path in sorted(SCAFFOLD_ROOT.rglob("main.py")):
        source = path.read_text(encoding="utf-8")
        try:
            tree = ast.parse(source, filename=str(path))
        except SyntaxError:
            continue

        for node in ast.iter_child_nodes(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue

            # Check 1: disallowed private helpers
            if (
                node.name.startswith("_")
                and node.name not in ALLOWED_PRIVATE_FUNCS
            ):
                violations.append(
                    f"{path}:{node.lineno}: scaffold has private helper "
                    f"'{node.name}' beyond API wiring — domain logic must "
                    "come from translated source, not scaffold"
                )

            # Check 2: endpoint functions that are too large
            if _is_endpoint(node):
                n_stmts = _count_statements(node)
                if n_stmts > MAX_ENDPOINT_STATEMENTS:
                    violations.append(
                        f"{path}:{node.lineno}: endpoint '{node.name}' has "
                        f"{n_stmts} statements (max {MAX_ENDPOINT_STATEMENTS}) "
                        "— extract logic to translated code"
                    )

    return violations


def test_scaffold_is_minimal():
    """Scaffold must only contain API endpoint wiring, not domain logic."""
    violations = scan()
    if violations:
        report = "\n".join(violations)
        raise AssertionError(
            f"Scaffold bloat detected ({len(violations)} finding(s)):\n{report}"
        )


if __name__ == "__main__":
    violations = scan()
    if violations:
        print("ALERT: Scaffold contains more than API wiring!\n")
        for v in violations:
            print(f"  {v}")
        print(f"\n{len(violations)} finding(s) total.")
        sys.exit(1)
    else:
        print("OK: Scaffold is minimal.")
        sys.exit(0)
