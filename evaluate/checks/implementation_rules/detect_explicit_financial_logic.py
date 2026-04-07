#!/usr/bin/env python3
"""
detect_explicit_financial_logic.py — detect financial calculation code in scaffold files.

Scaffold files must only contain HTTP endpoint wiring (routing, request parsing,
response formatting).  Any financial computation — cost-basis tracking, performance
calculations, price forward-filling, investment ledger updates — must come from
the translated source, not be pre-written in the scaffold.

Detection signals:

  1. Financial arithmetic patterns — assignment expressions that multiply, divide,
     or accumulate values using patterns like ``qty * price``, ``inv / units``,
     ``total += delta``.  A function with more than MAX_FINANCIAL_OPS such
     patterns is flagged.

  2. Financial variable names — local variables whose names strongly imply
     financial computation (e.g. ``inv_buys``, ``qty_buys``, ``gps``,
     ``fees_total``, ``last_avg``, ``net_perf``).

  3. Nested loops over activities or market data — iterating over activities
     inside a date loop (or vice versa) indicates chart/timeline generation,
     which is financial logic.

Usage:
  python detect_explicit_financial_logic.py
  pytest detect_explicit_financial_logic.py
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
SCAFFOLD_ROOT = PROJECT_ROOT / "tt" / "tt" / "scaffold"

# A function with more than this many financial arithmetic operations is flagged.
MAX_FINANCIAL_OPS = 3

# Variable names that strongly indicate financial computation.
FINANCIAL_VAR_NAMES: frozenset[str] = frozenset({
    "inv_buys", "qty_buys", "gps", "gross_from_sells",
    "fees_total", "last_avg", "net_perf", "gross_performance",
    "total_gps", "c_inv", "c_units", "c_fees",
    "inv_from_buys", "qty_from_buys", "total_bought_cost",
    "tx_inv", "tx", "gps_delta",
})

# Patterns in source lines that indicate financial arithmetic.
# We check for augmented assignments and multiplicative expressions involving
# financial-flavoured identifiers.
FINANCIAL_IDENT_PARTS: frozenset[str] = frozenset({
    "inv", "units", "qty", "price", "fee", "gps", "avg",
})


def _count_financial_ops(func: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    """Count assignment statements that look like financial arithmetic."""
    count = 0
    for node in ast.walk(func):
        # Augmented assign: x += expr, x -= expr
        if isinstance(node, ast.AugAssign):
            if isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)):
                count += 1
        # Regular assign with BinOp: x = a * b, x = a / b, x = a + b
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.BinOp):
            if isinstance(node.value.op, (ast.Mult, ast.Div)):
                count += 1
            elif isinstance(node.value.op, (ast.Add, ast.Sub)):
                # Only count add/sub if target name has financial flavour
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        parts = target.id.lower().split("_")
                        if FINANCIAL_IDENT_PARTS & set(parts):
                            count += 1
                            break
    return count


def _collect_financial_var_names(
    func: ast.FunctionDef | ast.AsyncFunctionDef,
) -> list[tuple[int, str]]:
    """Return (lineno, name) for local variables with financial names."""
    results: list[tuple[int, str]] = []
    for node in ast.walk(func):
        if isinstance(node, ast.Name) and node.id in FINANCIAL_VAR_NAMES:
            results.append((node.lineno, node.id))
    return results


def _has_nested_activity_loop(func: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """Detect nested statement-level for/while loops inside a function.

    Nested loops in the scaffold are a strong signal of financial computation
    that should live in the translated calculator instead:

    - Chart/timeline generation iterates over dates (outer loop) and computes
      per-symbol values (inner loop) — this is domain logic.
    - Performance calculation iterates over activities (outer loop) and
      accumulates per-symbol state (inner loop) — also domain logic.

    Simple data-preparation patterns like list comprehensions and generator
    expressions are NOT flagged — only actual ``for``/``while`` statements
    nested inside other ``for``/``while`` statements.  This allows the
    delegation layer (``_try_calculator``) to use comprehensions for building
    the activity list and market-data map without triggering a false positive.
    """
    for node in ast.walk(func):
        if not isinstance(node, (ast.For, ast.While)):
            continue
        # ast.For/ast.While are always ast.stmt, but comprehension generators
        # (inside ListComp, SetComp, GeneratorExp) are ast.comprehension nodes
        # and will not match this isinstance check.
        if not isinstance(node, ast.stmt):
            continue
        for child in ast.walk(node):
            if child is node:
                continue
            if isinstance(child, (ast.For, ast.While)) and isinstance(child, ast.stmt):
                return True
    return False


def scan() -> list[str]:
    """Scan scaffold files for financial logic; return violation strings."""
    if not SCAFFOLD_ROOT.exists():
        return []

    violations: list[str] = []
    for path in sorted(SCAFFOLD_ROOT.rglob("*.py")):
        source = path.read_text(encoding="utf-8")
        try:
            tree = ast.parse(source, filename=str(path))
        except SyntaxError:
            continue

        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue

            # Signal 1: too many financial arithmetic operations
            n_ops = _count_financial_ops(node)
            if n_ops > MAX_FINANCIAL_OPS:
                violations.append(
                    f"{path}:{node.lineno}: function '{node.name}' has "
                    f"{n_ops} financial arithmetic operations (max "
                    f"{MAX_FINANCIAL_OPS}) — financial calculations must "
                    "come from translated source"
                )

            # Signal 2: financial variable names
            fin_vars = _collect_financial_var_names(node)
            if fin_vars:
                lineno, name = fin_vars[0]
                violations.append(
                    f"{path}:{lineno}: function '{node.name}' uses "
                    f"financial variable '{name}' — cost-basis/performance "
                    "logic belongs in translated code"
                )

            # Signal 3: nested loops (chart/timeline generation)
            if _has_nested_activity_loop(node):
                violations.append(
                    f"{path}:{node.lineno}: function '{node.name}' has "
                    "nested loops — chart/timeline generation belongs "
                    "in translated code"
                )

    return violations


def test_no_financial_logic_in_scaffold():
    """Scaffold must not contain financial calculation logic."""
    violations = scan()
    if violations:
        report = "\n".join(violations)
        raise AssertionError(
            f"Financial logic detected in scaffold "
            f"({len(violations)} finding(s)):\n{report}"
        )


if __name__ == "__main__":
    violations = scan()
    if violations:
        print("ALERT: Financial logic found in scaffold!\n")
        for v in violations:
            print(f"  {v}")
        print(f"\n{len(violations)} finding(s) total.")
        sys.exit(1)
    else:
        print("OK: No financial logic in scaffold.")
        sys.exit(0)
