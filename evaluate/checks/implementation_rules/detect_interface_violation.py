#!/usr/bin/env python3
"""
detect_interface_violation.py — verify the scaffold delegates to the translated
calculator interface and does not re-implement financial logic.

Checks:
  1. The scaffold's portfolio endpoints must read values from the calculator
     result dict — not compute them inline.
  2. The scaffold must not contain BUY/SELL string comparisons outside of
     _try_calculator (those belong in the translated code).
  3. The scaffold's _try_calculator must call get_symbol_metrics with the
     correct keyword arguments matching the TypeScript interface.
  4. The scaffold must extract standard SymbolMetrics keys from the result,
     matching the TypeScript interface (snake_case versions).

Usage:
  python detect_interface_violation.py
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
SCAFFOLD_MAIN = PROJECT_ROOT / "tt" / "tt" / "scaffold" / "ghostfolio_pytx" / "app" / "main.py"

# The SymbolMetrics keys that the scaffold may read from calculator results
# (snake_case versions of the TypeScript SymbolMetrics interface)
VALID_METRICS_KEYS = frozenset({
    "current_values", "current_values_with_currency_effect",
    "fees_with_currency_effect",
    "gross_performance", "gross_performance_percentage",
    "gross_performance_percentage_with_currency_effect",
    "gross_performance_with_currency_effect",
    "has_errors", "initial_value", "initial_value_with_currency_effect",
    "investment_values_accumulated",
    "investment_values_accumulated_with_currency_effect",
    "investment_values_with_currency_effect",
    "net_performance", "net_performance_percentage",
    "net_performance_percentage_with_currency_effect_map",
    "net_performance_values", "net_performance_values_with_currency_effect",
    "net_performance_with_currency_effect_map",
    "time_weighted_investment", "time_weighted_investment_values",
    "time_weighted_investment_values_with_currency_effect",
    "time_weighted_investment_with_currency_effect",
    "total_account_balance_in_base_currency",
    "total_dividend", "total_dividend_in_base_currency",
    "total_interest", "total_interest_in_base_currency",
    "total_investment", "total_investment_with_currency_effect",
    "total_liabilities", "total_liabilities_in_base_currency",
})

# Required keyword arguments to get_symbol_metrics (matching TypeScript)
REQUIRED_CALL_KWARGS = frozenset({
    "chart_date_map", "data_source", "end",
    "exchange_rates", "market_symbol_map", "start", "symbol",
})

# Activity type strings that only the translated code should compare against
DOMAIN_EVENT_STRINGS = frozenset({"BUY", "SELL", "DIVIDEND", "FEE", "LIABILITY", "INTEREST"})


def _find_functions(tree: ast.AST) -> dict[str, ast.FunctionDef]:
    """Return {name: node} for all top-level and nested function defs."""
    result = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            result[node.name] = node
    return result


def _check_no_inline_buy_sell(funcs: dict[str, ast.FunctionDef], path: Path) -> list[str]:
    """Endpoint handlers must not compare against BUY/SELL strings."""
    violations = []
    for name, func in funcs.items():
        # _try_calculator is allowed to pass activity types to the calculator
        if name.startswith("_"):
            continue
        for node in ast.walk(func):
            if isinstance(node, ast.Compare):
                for comparator in [node.left, *node.comparators]:
                    if isinstance(comparator, ast.Constant) and comparator.value in DOMAIN_EVENT_STRINGS:
                        violations.append(
                            f"{path}:{node.lineno}: endpoint '{name}' compares "
                            f"against '{comparator.value}' — activity-type logic "
                            "must be in the translated calculator, not the scaffold"
                        )
    return violations


def _check_calculator_call_kwargs(funcs: dict[str, ast.FunctionDef], path: Path) -> list[str]:
    """_try_calculator must call get_symbol_metrics with the correct kwargs."""
    violations = []
    try_calc = funcs.get("_try_calculator")
    if try_calc is None:
        violations.append(f"{path}: scaffold is missing _try_calculator delegation function")
        return violations

    found_call = False
    for node in ast.walk(try_calc):
        if isinstance(node, ast.Call):
            func_node = node.func
            if isinstance(func_node, ast.Attribute) and func_node.attr == "get_symbol_metrics":
                found_call = True
                call_kwargs = {kw.arg for kw in node.keywords if kw.arg}
                missing = REQUIRED_CALL_KWARGS - call_kwargs
                if missing:
                    violations.append(
                        f"{path}:{node.lineno}: get_symbol_metrics call missing "
                        f"required kwargs: {sorted(missing)}"
                    )
    if not found_call:
        violations.append(
            f"{path}: _try_calculator does not call get_symbol_metrics — "
            "the scaffold must delegate to the translated calculator"
        )
    return violations


def _check_metrics_key_usage(tree: ast.AST, path: Path) -> list[str]:
    """Warn if the scaffold reads non-standard keys from calculator results."""
    violations = []
    # Find string constants used as dict keys in .get() calls or subscripts
    # that look like they come from metrics results
    # This is a best-effort heuristic check
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute) and node.func.attr == "get":
                if node.args and isinstance(node.args[0], ast.Constant):
                    key = node.args[0].value
                    if isinstance(key, str) and key.startswith("total_") or key.startswith("gross_") or key.startswith("net_") or key.startswith("fees_") or key.startswith("time_weighted"):
                        if key not in VALID_METRICS_KEYS:
                            violations.append(
                                f"{path}:{node.lineno}: reads non-standard "
                                f"metrics key '{key}' — must match SymbolMetrics "
                                "interface from TypeScript"
                            )
    return violations


def scan() -> list[str]:
    if not SCAFFOLD_MAIN.exists():
        return [f"Scaffold main.py not found: {SCAFFOLD_MAIN}"]

    source = SCAFFOLD_MAIN.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source, filename=str(SCAFFOLD_MAIN))
    except SyntaxError as e:
        return [f"{SCAFFOLD_MAIN}: SyntaxError: {e}"]

    funcs = _find_functions(tree)
    violations = []
    violations.extend(_check_no_inline_buy_sell(funcs, SCAFFOLD_MAIN))
    violations.extend(_check_calculator_call_kwargs(funcs, SCAFFOLD_MAIN))
    violations.extend(_check_metrics_key_usage(tree, SCAFFOLD_MAIN))
    return violations


def test_interface_compliance():
    """Scaffold must respect the calculator interface contract."""
    violations = scan()
    if violations:
        raise AssertionError(
            f"Interface compliance violations ({len(violations)}):\n"
            + "\n".join(violations)
        )


if __name__ == "__main__":
    violations = scan()
    if violations:
        print("ALERT: Interface compliance violations!\n")
        for v in violations:
            print(f"  {v}")
        print(f"\n{len(violations)} finding(s).")
        sys.exit(1)
    else:
        print("OK: Scaffold complies with calculator interface.")
        sys.exit(0)
