#!/usr/bin/env python3
"""
detect_explicit_implementation.py — Python-logic check for explicit domain
implementations inside the tt tool source (tt/tt/).

The tt tool must not contain specific business-logic implementations
(portfolio calculations, domain formulas, BUY/SELL processing, etc.) —
those should come from the translated source.

Detection strategy (four independent signals):

  1. Function body length — tt functions must be stubs or generic helpers;
     any function with more than MAX_FUNCTION_STATEMENTS non-trivial
     statements is flagged.

  2. Domain-specific identifiers — variable/attribute names drawn from the
     Ghostfolio domain (e.g. totalInvestment, grossPerformance, unitPrice)
     indicate business-logic computation, not generic tooling.

  3. Business-logic string comparisons — comparisons against activity-type
     literals ("BUY", "SELL", "DIVIDEND", …) inside functions signal that
     tt is processing domain events directly.

  4. Function body duplication — functions with >= MIN_DUPLICATE_LINES lines
     whose body (leading whitespace stripped per line) exactly matches a
     function in the translated output (translations/ghostfolio_pytx/).
     The scaffold directory is excluded from this check because scaffold
     files are intentionally copied verbatim to the output.

Usage:
  python checks/detect_explicit_implementation.py
  pytest checks/detect_explicit_implementation.py
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
TT_ROOT = PROJECT_ROOT / "tt" / "tt"
SCAFFOLD_ROOT = TT_ROOT / "scaffold"
TRANSLATION_ROOT = PROJECT_ROOT / "translations" / "ghostfolio_pytx"

# Functions with more than this many statements are considered non-stub
MAX_FUNCTION_STATEMENTS = 30

# Functions with at least this many lines are candidates for duplication check
MIN_DUPLICATE_LINES = 10

# Identifiers specific to the Ghostfolio / portfolio domain.
DOMAIN_IDENTIFIERS: frozenset[str] = frozenset({
    "totalInvestment", "total_investment",
    "grossPerformance", "gross_performance",
    "netPerformance", "net_performance",
    "grossFromSells", "gross_from_sells",
    "invFromBuys", "inv_from_buys",
    "qtyFromBuys", "qty_from_buys",
    "totalUnits", "total_units",
    "totalFees", "total_fees",
    "unitPrice", "unit_price",
    "marketPrice", "market_price",
    "cumulativeRealizedPnl", "cumulative_realized_pnl",
    "netPerformancePct", "net_performance_pct",
    "twi",
    "totalBoughtCost", "total_bought_cost",
    "priceHistory", "price_history",
    "investmentEntries", "investment_entries",
})

# String literals that signal direct domain-event processing
DOMAIN_EVENT_STRINGS: frozenset[str] = frozenset({
    "BUY", "SELL", "DIVIDEND", "FEE", "LIABILITY", "INTEREST",
})

# Domain-specific imports that should not appear in scaffold files.
# Scaffold should only contain HTTP wiring, not domain model construction.
SCAFFOLD_FORBIDDEN_IMPORTS: frozenset[str] = frozenset({
    "app.models", "app.helpers.portfolio", "app.helpers.calculation",
    "app.portfolio",
})

# Domain-specific substrings in function names inside scaffold files.
SCAFFOLD_DOMAIN_FUNC_KEYWORDS: frozenset[str] = frozenset({
    "market_symbol", "activities", "calculator", "symbol_metrics",
    "cost_basis", "investment", "portfolio", "holding",
})

# Domain field-name strings used as dict keys in scaffold — signals
# that the scaffold is constructing or destructuring domain objects.
SCAFFOLD_DOMAIN_DICT_KEYS: frozenset[str] = frozenset({
    "marketPrice", "unitPrice", "dataSource", "SymbolProfile",
    "feeInBaseCurrency", "assetSubClass",
})

# Scaffold functions allowed to use domain imports/keys for wiring delegation.
SCAFFOLD_WIRING_FUNCS: frozenset[str] = frozenset({
    "_try_calculator",
})


# ---------------------------------------------------------------------------
# AST helpers
# ---------------------------------------------------------------------------

def _count_statements(node: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    """Count non-trivial statements in a function body (excludes docstrings)."""
    count = 0
    for child in ast.walk(node):
        if child is node:
            continue
        if isinstance(child, ast.stmt):
            if (
                isinstance(child, ast.Expr)
                and isinstance(getattr(child, "value", None), ast.Constant)
                and isinstance(child.value.value, str)  # type: ignore[union-attr]
            ):
                continue
            count += 1
    return count


def _collect_names(node: ast.AST) -> list[tuple[int, str]]:
    """Collect all Name and Attribute nodes, returning (lineno, name) pairs."""
    results: list[tuple[int, str]] = []
    for child in ast.walk(node):
        if isinstance(child, ast.Name):
            results.append((child.lineno, child.id))
        elif isinstance(child, ast.Attribute):
            results.append((child.lineno, child.attr))
    return results


def _collect_string_comparisons(node: ast.AST) -> list[tuple[int, str]]:
    """Return (lineno, value) for string constants used in Compare nodes."""
    results: list[tuple[int, str]] = []
    for child in ast.walk(node):
        if isinstance(child, ast.Compare):
            for comparator in [child.left, *child.comparators]:
                if isinstance(comparator, ast.Constant) and isinstance(comparator.value, str):
                    results.append((child.lineno, comparator.value))
    return results


# ---------------------------------------------------------------------------
# Per-function checks (signals 1–3)
# ---------------------------------------------------------------------------

def _check_function(
    func: ast.FunctionDef | ast.AsyncFunctionDef,
    path: Path,
    *,
    skip_domain: bool = False,
) -> list[str]:
    violations: list[str] = []

    if skip_domain:
        # Scaffold files are checked by signals 5–7; skip generic checks.
        return violations

    # Signal 1: function body length
    n_stmts = _count_statements(func)
    if n_stmts > MAX_FUNCTION_STATEMENTS:
        violations.append(
            f"{path}:{func.lineno}: function '{func.name}' has {n_stmts} statements "
            f"(max {MAX_FUNCTION_STATEMENTS} for tt tool code) — "
            "move business logic to translated source"
        )
        return violations

    # Signal 2: domain-specific variable/attribute names
    for lineno, name in _collect_names(func):
        if name in DOMAIN_IDENTIFIERS:
            violations.append(
                f"{path}:{lineno}: function '{func.name}' uses domain identifier "
                f"'{name}' — tt must not implement domain-specific calculations"
            )
            break

    # Signal 3: business-logic string comparisons
    for lineno, value in _collect_string_comparisons(func):
        if value in DOMAIN_EVENT_STRINGS:
            violations.append(
                f"{path}:{lineno}: function '{func.name}' compares against domain "
                f"event string {value!r} — activity-type processing belongs in "
                "translated code, not tt"
            )
            break

    return violations


# ---------------------------------------------------------------------------
# Scaffold-specific checks (signals 5–7)
# ---------------------------------------------------------------------------

def _check_scaffold_imports(tree: ast.AST, path: Path) -> list[str]:
    """Signal 5: scaffold files must not import domain-specific modules.

    Imports inside SCAFFOLD_WIRING_FUNCS are exempt (delegation wiring).
    """
    # Collect line ranges of wiring functions to exempt their imports
    wiring_ranges: list[tuple[int, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name in SCAFFOLD_WIRING_FUNCS and node.end_lineno:
                wiring_ranges.append((node.lineno, node.end_lineno))

    violations: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            if any(s <= node.lineno <= e for s, e in wiring_ranges):
                continue
            for forbidden in SCAFFOLD_FORBIDDEN_IMPORTS:
                if node.module == forbidden or node.module.startswith(forbidden + "."):
                    violations.append(
                        f"{path}:{node.lineno}: scaffold imports domain module "
                        f"'{node.module}' — scaffold must only contain HTTP wiring"
                    )
    return violations


def _check_scaffold_func_names(tree: ast.AST, path: Path) -> list[str]:
    """Signal 6: private scaffold helpers must not reference domain concepts.

    Skips SCAFFOLD_WIRING_FUNCS (thin delegation layer) and public endpoints.
    """
    violations: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not node.name.startswith("_"):
                continue
            if node.name in SCAFFOLD_WIRING_FUNCS:
                continue
            for kw in SCAFFOLD_DOMAIN_FUNC_KEYWORDS:
                if kw in node.name:
                    violations.append(
                        f"{path}:{node.lineno}: scaffold helper '{node.name}' "
                        f"contains domain keyword '{kw}' — domain logic belongs "
                        "in translated code"
                    )
                    break
    return violations


def _check_scaffold_domain_keys(tree: ast.AST, path: Path) -> list[str]:
    """Signal 7: private scaffold helpers must not access domain-specific dict keys.

    Skips SCAFFOLD_WIRING_FUNCS and public endpoints.
    """
    violations: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not node.name.startswith("_") or node.name in SCAFFOLD_WIRING_FUNCS:
            continue
        seen: set[str] = set()
        for child in ast.walk(node):
            if isinstance(child, ast.Constant) and isinstance(child.value, str):
                if child.value in SCAFFOLD_DOMAIN_DICT_KEYS and child.value not in seen:
                    seen.add(child.value)
                    violations.append(
                        f"{path}:{child.lineno}: scaffold helper '{node.name}' "
                        f"uses domain dict key '{child.value}' — domain object "
                        "construction belongs in translated code"
                    )
    return violations


# ---------------------------------------------------------------------------
# Duplication check (signal 4)
# ---------------------------------------------------------------------------

def _normalized_body(path: Path, node: ast.FunctionDef | ast.AsyncFunctionDef) -> tuple[str, ...]:
    """Return the function's source lines with leading whitespace stripped."""
    lines = path.read_text(encoding="utf-8").splitlines()
    body_lines = lines[node.lineno - 1 : node.end_lineno]
    return tuple(line.strip() for line in body_lines if line.strip())


def _extract_long_functions(
    path: Path,
) -> list[tuple[str, int, tuple[str, ...]]]:
    """Return (name, lineno, normalized_body) for functions >= MIN_DUPLICATE_LINES lines."""
    source = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError:
        return []
    results = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.end_lineno is None:
                continue
            n_lines = node.end_lineno - node.lineno + 1
            if n_lines >= MIN_DUPLICATE_LINES:
                results.append((node.name, node.lineno, _normalized_body(path, node)))
    return results


def _check_duplicates(
    tt_files: list[Path],
    translation_files: list[Path],
) -> list[str]:
    """Flag functions in tt/ (excl. scaffold) whose body duplicates translated output."""
    # Build lookup: normalized body → first occurrence in translation
    translation_index: dict[tuple[str, ...], tuple[Path, int, str]] = {}
    for path in translation_files:
        for name, lineno, body in _extract_long_functions(path):
            if body not in translation_index:
                translation_index[body] = (path, lineno, name)

    violations: list[str] = []
    for path in tt_files:
        if path.is_relative_to(SCAFFOLD_ROOT):
            continue  # scaffold is intentionally copied verbatim
        for name, lineno, body in _extract_long_functions(path):
            if body in translation_index:
                tx_path, tx_lineno, tx_name = translation_index[body]
                violations.append(
                    f"{path}:{lineno}: function '{name}' ({len(body)} lines) "
                    f"duplicates translated output "
                    f"{tx_path.relative_to(TRANSLATION_ROOT)}:{tx_lineno} '{tx_name}'"
                )
    return violations


# ---------------------------------------------------------------------------
# File lists
# ---------------------------------------------------------------------------

def _tt_files() -> list[Path]:
    if not TT_ROOT.exists():
        return []
    return sorted(p for p in TT_ROOT.rglob("*.py") if p.is_file())


def _translation_files() -> list[Path]:
    if not TRANSLATION_ROOT.exists():
        return []
    return sorted(p for p in TRANSLATION_ROOT.rglob("*.py") if p.is_file())


# ---------------------------------------------------------------------------
# Scanner
# ---------------------------------------------------------------------------

def scan() -> list[str]:
    """Scan tt/ source files; return violation strings (empty list = clean)."""
    tt = _tt_files()
    all_violations: list[str] = []

    # Signals 1–3: per-function AST checks across all tt/tt/ files
    # Scaffold files are checked by signals 5–7 instead (signals 2–3 would
    # false-positive on endpoint stubs that naturally use domain words).
    for path in tt:
        source = path.read_text(encoding="utf-8")
        try:
            tree = ast.parse(source, filename=str(path))
        except SyntaxError as exc:
            all_violations.append(f"{path}: SyntaxError: {exc}")
            continue

        is_scaffold = path.is_relative_to(SCAFFOLD_ROOT)

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                all_violations.extend(_check_function(node, path, skip_domain=is_scaffold))

        # Signals 5–7: scaffold-specific checks
        if is_scaffold:
            all_violations.extend(_check_scaffold_imports(tree, path))
            all_violations.extend(_check_scaffold_func_names(tree, path))
            all_violations.extend(_check_scaffold_domain_keys(tree, path))

    # Signal 4: duplication against translated output
    tx = _translation_files()
    if tx:
        all_violations.extend(_check_duplicates(tt, tx))

    return all_violations


# ---------------------------------------------------------------------------
# pytest-compatible test
# ---------------------------------------------------------------------------

def test_no_explicit_implementation_in_tt():
    """tt tool must not contain domain-specific business logic."""
    violations = scan()
    if violations:
        report = "\n".join(violations)
        raise AssertionError(
            f"Explicit domain implementation detected in tt/ "
            f"({len(violations)} finding(s)):\n{report}\n\n"
            "Business logic must come from translated source, not tt."
        )


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    violations = scan()
    if violations:
        print("ALERT: Explicit domain implementation found in tt/!\n")
        for v in violations:
            print(f"  {v}")
        print(
            f"\n{len(violations)} finding(s) total.\n"
            "Business logic must come from translated source, not tt."
        )
        sys.exit(1)
    else:
        print("OK: No explicit domain implementations found in tt/.")
        sys.exit(0)
