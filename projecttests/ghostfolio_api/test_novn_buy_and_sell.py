"""
NOVN.SW buy + full sell — fully closed position, positive gain, zero fees.

Exercises the ROAI calculator's time-weighted investment (TWI) logic as the
denominator for netPerformancePercentage when totalInvestment=0 (closed position).

Scenario (from portfolio-calculator-novn-buy-and-sell.spec.ts):
  BUY  2 NOVN.SW @ CHF 75.80, fee 0 — 2022-03-07
  SELL 2 NOVN.SW @ CHF 85.73, fee 0 — 2022-04-08
  Base currency: CHF

Key calculations:
  totalInvestment  = 0                           (position closed)
  netPerformance   = 2 × (85.73 − 75.80) = 19.86
  TWI              = 2 × 75.80 = 151.6          (original cost basis, single BUY)
  netPerformancePercentage = 19.86 / 151.6 ≈ 0.13100

Investment deltas by month:
  2022-03: +151.6  (BUY)
  2022-04: -151.6  (SELL at avg cost 75.80 × 2)
  → net annual investment for 2022 = 0

Complementary to test_deeper.py::baln_closed which tests a loss scenario with
fees. This test covers a gain scenario with no fees, confirming the TWI
denominator is used consistently for both positive and negative returns.
"""
import pytest

from .mock_prices import prices_for

_BUY_PRICE = 75.8
_SELL_PRICE = 85.73
_QUANTITY = 2
_COST_BASIS = _QUANTITY * _BUY_PRICE        # 151.6
_NET_PERF = _QUANTITY * (_SELL_PRICE - _BUY_PRICE)  # 19.86
_TWI = _COST_BASIS                           # 151.6 (no intermediate transactions)
_NET_PERF_PCT = _NET_PERF / _TWI            # ≈ 0.13100


@pytest.fixture
def novn_buy_and_sell(gf):
    """
    BUY 2 NOVN.SW @ 75.80 CHF on 2022-03-07,
    SELL 2 NOVN.SW @ 85.73 CHF on 2022-04-08.
    Base currency CHF.
    """
    client, _ = gf
    client.update_user_settings("CHF")
    client.import_activities([
        {
            "currency": "CHF",
            "dataSource": "YAHOO",
            "date": "2022-03-07",
            "fee": 0,
            "quantity": _QUANTITY,
            "symbol": "NOVN.SW",
            "type": "BUY",
            "unitPrice": _BUY_PRICE,
        },
        {
            "currency": "CHF",
            "dataSource": "YAHOO",
            "date": "2022-04-08",
            "fee": 0,
            "quantity": _QUANTITY,
            "symbol": "NOVN.SW",
            "type": "SELL",
            "unitPrice": _SELL_PRICE,
        },
    ])
    client.seed_market_data("YAHOO", "NOVN.SW", prices_for("NOVN.SW"))
    return client


# ===========================================================================
# Performance endpoint
# ===========================================================================

def test_closed_position_total_investment_is_zero(novn_buy_and_sell):
    """After full sell, totalInvestment = 0 (no open position remains)."""
    perf = novn_buy_and_sell.get_performance()
    assert perf["performance"]["totalInvestment"] == pytest.approx(0.0, abs=1e-4)


def test_closed_position_net_performance(novn_buy_and_sell):
    """
    Realized gain = 2 × (85.73 − 75.80) = 19.86 CHF.
    No fees, so netPerformance = grossPerformance = 19.86.
    """
    perf = novn_buy_and_sell.get_performance()
    assert perf["performance"]["netPerformance"] == pytest.approx(_NET_PERF, rel=1e-4)


def test_closed_position_net_performance_percentage_uses_twi(novn_buy_and_sell):
    """
    For a fully closed position totalInvestment=0, so the ROAI calculator uses
    the time-weighted investment (TWI = 151.6) as the denominator instead of zero.

    netPerformancePercentage = 19.86 / 151.6 ≈ 0.13100
    """
    perf = novn_buy_and_sell.get_performance()
    assert perf["performance"]["netPerformancePercentage"] == pytest.approx(
        _NET_PERF_PCT, rel=1e-3
    )


# ===========================================================================
# Investments endpoint
# ===========================================================================

def test_investments_by_day(novn_buy_and_sell):
    """Daily investment deltas: BUY date +151.6, SELL date -151.6."""
    inv = novn_buy_and_sell.get_investments()
    by_date = {e["date"]: e["investment"] for e in inv["investments"]}
    assert by_date.get("2022-03-07", None) == pytest.approx(_COST_BASIS, rel=1e-4)
    assert by_date.get("2022-04-08", None) == pytest.approx(-_COST_BASIS, rel=1e-4)


def test_investments_by_month(novn_buy_and_sell):
    """
    Monthly grouping:
      2022-03: +151.6 (BUY)
      2022-04: -151.6 (SELL, cost basis returned)
    """
    inv = novn_buy_and_sell.get_investments(group_by="month")
    by_date = {e["date"]: e["investment"] for e in inv["investments"]}
    assert by_date.get("2022-03-01", None) == pytest.approx(_COST_BASIS, rel=1e-4)
    assert by_date.get("2022-04-01", None) == pytest.approx(-_COST_BASIS, rel=1e-4)


def test_investments_by_year(novn_buy_and_sell):
    """
    Annual grouping: BUY and SELL both in 2022, so net annual investment = 0.
    """
    inv = novn_buy_and_sell.get_investments(group_by="year")
    by_date = {e["date"]: e["investment"] for e in inv["investments"]}
    assert by_date.get("2022-01-01", 0) == pytest.approx(0.0, abs=1e-4)


# ===========================================================================
# Holdings endpoint
# ===========================================================================

def test_holdings_empty_after_full_sell(novn_buy_and_sell):
    """
    After selling all shares, NOVN.SW must not appear as an open holding
    (or must have quantity=0 if present in the response).
    """
    h = novn_buy_and_sell.get_holdings()
    items = h["holdings"]
    if isinstance(items, dict):
        holding = items.get("NOVN.SW")
    else:
        holding = next((x for x in items if x.get("symbol") == "NOVN.SW"), None)

    if holding is not None:
        assert holding.get("quantity", 0) == pytest.approx(0.0, abs=1e-8)
