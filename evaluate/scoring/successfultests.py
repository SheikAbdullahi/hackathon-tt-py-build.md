#!/usr/bin/env python3
"""
Test scoring for the ghostfolio_pytx API test suite.

Assigns a complexity score (1-10) to each test. Passing tests contribute their
score to the total. The current maximum achievable score is 258 (all 77 passing).
No individual test scores above 7.

Usage:
  # Run against an already-running server (KEEP_UP=1 spinup, or standalone):
  GHOSTFOLIO_API_URL=http://localhost:3335 uv run --project tt python checks/test_scoring.py

  # Default URL is http://localhost:3335
  uv run --project tt python checks/test_scoring.py
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Score map: test_name → complexity (1=trivial … 10=extremely complex)
# Max currently assigned: 7
# ---------------------------------------------------------------------------
SCORES: dict[str, int] = {
    # Empty portfolio — trivial baseline
    "test_no_orders_performance_is_empty":          1,
    "test_no_orders_investments_are_empty":          1,
    "test_no_orders_investments_by_month_are_empty": 1,
    "test_no_orders_investments_by_year_are_empty":  1,

    # Single BUY, chart + holdings + investments
    "test_btcusd_chart_day_before_first_activity":          2,
    "test_btcusd_chart_on_buy_date":                        2,
    "test_btcusd_chart_on_2022_01_14":                      2,
    "test_btcusd_chart_excludes_dates_before_first_activity": 2,
    "test_btcusd_chart_includes_year_boundary":             2,
    "test_btcusd_holding_values":                           2,
    "test_btcusd_investments_list":                         2,
    "test_btcusd_investments_by_month_dec_2021":            2,
    "test_btcusd_investments_by_year_2021":                 2,

    # remaining_specs — buy/sell/investment grouping for various symbols
    "test_baln_buy_investment":                    2,
    "test_baln_buy_holdings_quantity":             2,
    "test_baln_buy_investments_list":              2,
    "test_baln_buy_investments_by_month":          2,
    "test_baln_buy_investments_by_year":           2,
    "test_baln_buy_and_buy_investment":            2,
    "test_baln_buy_and_buy_holdings":              2,
    "test_baln_buy_and_buy_investments_by_month":  2,
    "test_baln_buy_and_buy_investments_by_year":   2,
    "test_baln_buy_and_sell_investment_is_zero":       3,
    "test_baln_buy_and_sell_investments_by_month":     3,
    "test_baln_buy_and_sell_investments_by_year":      3,
    "test_baln_buy_and_sell_in_two_investment_is_zero":    3,
    "test_baln_buy_and_sell_in_two_investments_by_month":  3,
    "test_baln_buy_and_sell_in_two_investments_by_year":   3,
    "test_btceur_investment":                      2,
    "test_btceur_chart_includes_year_boundary":    2,
    "test_btceur_chart_excludes_before_buy":       2,
    "test_btceur_investments_by_month":            2,
    "test_btceur_investments_by_year":             2,
    "test_btcusd_short_investments_list":          3,
    "test_btcusd_short_performance_accessible":    2,
    "test_fee_total_investment_is_zero":           2,
    "test_fee_performance_accessible":             2,
    "test_googl_buy_investment":                   2,
    "test_googl_buy_holdings_quantity":            2,
    "test_googl_buy_investments_by_month":         2,
    "test_googl_buy_investments_by_year":          2,
    "test_jnug_investment_is_zero":                3,
    "test_jnug_net_performance":                   4,
    "test_jnug_investments_by_month":              2,
    "test_jnug_investments_by_year":               2,
    "test_liability_performance_accessible":       2,
    "test_liability_investment_is_zero":           2,
    "test_msft_buy_and_sell_investment_near_zero": 3,
    "test_msft_dividend_investment":               3,
    "test_msft_dividend_holdings":                 3,
    "test_novn_buy_and_sell_partially_investment":          3,
    "test_novn_buy_and_sell_partially_holdings":            3,
    "test_novn_buy_and_sell_partially_investments_by_month": 3,
    "test_novn_buy_and_sell_partially_investments_by_year":  3,
    "test_novn_buy_and_sell_investment_is_zero":   3,
    "test_novn_buy_and_sell_net_performance":      4,
    "test_novn_buy_and_sell_investments_by_month": 3,
    "test_novn_buy_and_sell_investments_by_year":  3,
    "test_valuable_investment":                    2,
    "test_valuable_holdings":                      2,

    # advanced — unrealized P&L, market prices, chart fields
    "test_open_position_current_value_in_base_currency":        4,
    "test_open_position_net_performance_includes_unrealized":    5,
    "test_open_position_net_performance_percentage":             5,
    "test_holding_market_price":                                 4,
    "test_chart_entry_net_performance_absolute":                 5,
    "test_chart_entry_investment_value_per_date":                5,
    "test_partial_sell_total_investment":                        3,
    "test_partial_sell_investments_by_year":                     3,
    "test_partial_sell_holding_market_price":                    4,
    "test_partial_sell_net_performance_combines_realized_and_unrealized": 6,

    # deeper — TWI denominator, dividend with open position
    "test_fully_closed_net_performance_percentage":          7,
    "test_fully_closed_net_performance_value":               5,
    "test_msft_dividend_current_value_in_base_currency":     5,
    "test_msft_dividend_net_performance":                    6,
    "test_msft_dividend_net_performance_percentage":         6,
    "test_msft_dividend_holding_market_price":               5,
    "test_msft_dividend_total_investment_unchanged":         3,
}

DEFAULT_SCORE = 2  # fallback for unrecognised tests
MAX_SCORE = sum(SCORES.values())


def run_pytest(repo_root: Path, api_url: str) -> list[tuple[str, bool]]:
    """Run pytest -v and return list of (test_name, passed)."""
    import os
    env = {**os.environ, "GHOSTFOLIO_API_URL": api_url}
    cmd = [
        "uv", "run", "--project", str(repo_root / "tt"),
        "pytest", str(repo_root / "projecttests" / "ghostfolio_api"),
        "-v", "--tb=no", "--no-header",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=repo_root, env=env)

    results: list[tuple[str, bool]] = []
    for line in result.stdout.splitlines():
        if (" PASSED" in line or " FAILED" in line) and "::" in line:
            test_id = line.strip().split()[0]          # path::test_name
            test_name = test_id.split("::")[-1]
            passed = " PASSED" in line
            results.append((test_name, passed))
    return results


def score(results: list[tuple[str, bool]]) -> tuple[int, int, int, int]:
    """Return (achieved, max_possible, n_passed, n_total)."""
    achieved = 0
    max_possible = 0
    for name, passed in results:
        pts = SCORES.get(name, DEFAULT_SCORE)
        max_possible += pts
        if passed:
            achieved += pts
    return achieved, max_possible, sum(1 for _, p in results if p), len(results)


def run(api_url: str | None = None) -> dict:
    """Return scoring result dict for use by other scripts."""
    import os
    repo_root = Path(__file__).parent.parent.parent.resolve()
    api_url = api_url or os.environ.get("GHOSTFOLIO_API_URL", "http://localhost:3335")
    results = run_pytest(repo_root, api_url)
    if not results:
        return {"error": "no test results collected", "score": 0, "max_score": MAX_SCORE, "percentage": 0.0}
    achieved, max_possible, n_passed, n_total = score(results)
    return {
        "achieved": achieved,
        "max_possible": max_possible,
        "theoretical_max": max_possible,
        "n_passed": n_passed,
        "n_total": n_total,
        "percentage": round(achieved / max_possible * 100, 2) if max_possible else 0.0,
    }


def main() -> int:
    import os
    repo_root = Path(__file__).parent.parent.parent.resolve()
    api_url = os.environ.get("GHOSTFOLIO_API_URL", "http://localhost:3335")

    print(f"Scoring tests against {api_url} ...")
    results = run_pytest(repo_root, api_url)

    if not results:
        print("ERROR: no test results collected — is the server running?", file=sys.stderr)
        return 1

    achieved, max_possible, n_passed, n_total = score(results)
    n_failed = n_total - n_passed

    print(f"\nResults:  {n_passed}/{n_total} passed,  {n_failed} failed")
    print(f"Score:    {achieved}/{max_possible}")

    if n_failed:
        print("\nFailed tests:")
        for name, passed in results:
            if not passed:
                pts = SCORES.get(name, DEFAULT_SCORE)
                print(f"  - {name}  ({pts} pts)")

    return 0 if n_failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
