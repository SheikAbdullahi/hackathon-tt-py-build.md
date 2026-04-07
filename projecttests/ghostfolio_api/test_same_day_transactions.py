"""
Same-date BUY + SELL — exercises the TWI Number.EPSILON edge case.

When two transactions land on the same date, `differenceInDays()` returns 0.
The ROAI calculator guards against division-by-zero by substituting
Number.EPSILON (~2.22e-16) as the day count when computing the time-weighted
investment (TWI).  Without this guard the server would crash with division by
zero or produce NaN/Infinity in netPerformancePercentage.

Scenario:
  BUY  1 BALN.SW @ CHF 136.6, fee 0 — 2021-11-30
  SELL 1 BALN.SW @ CHF 142.9, fee 0 — 2021-11-30  ← same date as BUY
  Base currency: CHF

Key calculations:
  netPerformance = 142.9 − 136.6 = 6.3 CHF
  totalInvestment (BUY cost) = 136.6
  netPerformancePercentage = 6.3 / 136.6 ≈ 0.04612
  holdings = [] (position fully closed same day)

The critical assertion is that the API returns a *finite* netPerformancePercentage
(not NaN, not Infinity, not a server error) — proving the EPSILON guard fires.
"""
import math

import pytest

from .mock_prices import prices_for

_BUY_PRICE = 136.6
_SELL_PRICE = 142.9
_NET_PERF = _SELL_PRICE - _BUY_PRICE          # 6.3
_TOTAL_INVESTMENT = _BUY_PRICE                 # 136.6 (cost of the BUY)
_NET_PERF_PCT = _NET_PERF / _TOTAL_INVESTMENT  # ≈ 0.04612


@pytest.fixture
def same_day_buy_sell(gf):
    """
    BUY and SELL BALN.SW on the exact same date (2021-11-30), CHF base.
    Triggers the differenceInDays=0 → Number.EPSILON path in the ROAI TWI calc.
    """
    client, _ = gf
    client.update_user_settings("CHF")
    client.import_activities([
        {
            "currency": "CHF",
            "dataSource": "YAHOO",
            "date": "2021-11-30",
            "fee": 0,
            "quantity": 1,
            "symbol": "BALN.SW",
            "type": "BUY",
            "unitPrice": _BUY_PRICE,
        },
        {
            "currency": "CHF",
            "dataSource": "YAHOO",
            "date": "2021-11-30",
            "fee": 0,
            "quantity": 1,
            "symbol": "BALN.SW",
            "type": "SELL",
            "unitPrice": _SELL_PRICE,
        },
    ])
    client.seed_market_data("YAHOO", "BALN.SW", prices_for("BALN.SW"))
    return client


# ===========================================================================
# Critical safety check — no crash / NaN / Infinity from EPSILON guard
# ===========================================================================

def test_same_day_performance_endpoint_does_not_error(same_day_buy_sell):
    """
    The performance endpoint must return HTTP 200 with a 'performance' key.
    A missing EPSILON guard would cause division-by-zero, crashing the server.
    """
    perf = same_day_buy_sell.get_performance()
    assert "performance" in perf


def test_same_day_net_performance_percentage_is_finite(same_day_buy_sell):
    """
    netPerformancePercentage must be a finite number — not NaN or Infinity.
    The EPSILON guard replaces the zero day-count to keep the TWI denominator
    non-zero, so the resulting percentage is always finite.
    """
    perf = same_day_buy_sell.get_performance()
    pct = perf["performance"]["netPerformancePercentage"]
    assert math.isfinite(pct), f"netPerformancePercentage is not finite: {pct}"


# ===========================================================================
# Correctness checks
# ===========================================================================

def test_same_day_net_performance(same_day_buy_sell):
    """Realized gain = sell − buy = 142.9 − 136.6 = 6.3 CHF (no fees)."""
    perf = same_day_buy_sell.get_performance()
    assert perf["performance"]["netPerformance"] == pytest.approx(_NET_PERF, rel=1e-4)


def test_same_day_net_performance_percentage(same_day_buy_sell):
    """netPerformancePercentage = 6.3 / 136.6 ≈ 0.04612."""
    perf = same_day_buy_sell.get_performance()
    assert perf["performance"]["netPerformancePercentage"] == pytest.approx(
        _NET_PERF_PCT, rel=1e-3
    )


def test_same_day_holdings_empty(same_day_buy_sell):
    """Position opened and closed on the same day — no holding remains."""
    h = same_day_buy_sell.get_holdings()
    items = h["holdings"]
    if isinstance(items, dict):
        holding = items.get("BALN.SW")
    else:
        holding = next((x for x in items if x.get("symbol") == "BALN.SW"), None)

    if holding is not None:
        assert holding.get("quantity", 0) == pytest.approx(0.0, abs=1e-8)
