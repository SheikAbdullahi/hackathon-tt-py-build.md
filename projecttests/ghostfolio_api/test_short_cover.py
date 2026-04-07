"""
Short open + BUY to cover — exercises the BUY-on-negative-investment branch.

The ROAI calculator's `computeTransactionPoints()` has four branches for
updating the cost basis depending on whether the current position is long or
short and whether the activity is a BUY or SELL:

  BUY  into long   (investment ≥ 0): investment += qty × unitPrice
  BUY  to cover short (investment < 0): investment += qty × avgPrice  ← this test
  SELL from long   (investment ≥ 0): investment -= qty × avgPrice
  SELL to open short (investment < 0): investment -= qty × unitPrice

Using unitPrice vs avgPrice for the BUY-to-cover branch is not obvious.
A wrong branch silently produces an incorrect cost basis and wrong P&L.

Scenario:
  SELL 1 BTCUSD @ USD 50098.30 — 2021-12-12  (open short at high price)
  BUY  1 BTCUSD @ USD 43099.70 — 2022-01-14  (cover at lower price → profit)
  Base currency: USD

Key calculations:
  netPerformance     = 50098.3 − 43099.7 = 6998.6  (short profit)
  totalInvestment    = 43099.7  (BUY cost recorded as the remaining investment)
  netPerformancePercentage = 6998.6 / 43099.7 ≈ 0.16238
  holdings           = []  (short fully covered, quantity = 0)
"""
import pytest

from .mock_prices import prices_for

_SELL_PRICE = 50098.3   # open short at this price
_BUY_PRICE  = 43099.7   # cover at this lower price
_NET_PERF   = _SELL_PRICE - _BUY_PRICE        # 6998.6 (profit)
_TOTAL_INV  = _BUY_PRICE                       # 43099.7
_NET_PERF_PCT = _NET_PERF / _TOTAL_INV         # ≈ 0.16238


@pytest.fixture
def btcusd_short_cover(gf):
    """
    SELL 1 BTCUSD to open a short, then BUY 1 BTCUSD to cover.
    Uses existing BTCUSD prices seeded in mock_prices (2021-12-12 and 2022-01-14).
    """
    client, _ = gf
    client.update_user_settings("USD")
    client.import_activities([
        {
            "currency": "USD",
            "dataSource": "YAHOO",
            "date": "2021-12-12",
            "fee": 0,
            "quantity": 1,
            "symbol": "BTCUSD",
            "type": "SELL",
            "unitPrice": _SELL_PRICE,
        },
        {
            "currency": "USD",
            "dataSource": "YAHOO",
            "date": "2022-01-14",
            "fee": 0,
            "quantity": 1,
            "symbol": "BTCUSD",
            "type": "BUY",
            "unitPrice": _BUY_PRICE,
        },
    ])
    client.seed_market_data("YAHOO", "BTCUSD", prices_for("BTCUSD"))
    return client


# ===========================================================================
# Performance endpoint
# ===========================================================================

def test_short_cover_net_performance(btcusd_short_cover):
    """
    Profit from the short = sell proceeds − buy cost = 50098.3 − 43099.7 = 6998.6.
    This value is only correct if the BUY-to-cover branch uses avgPrice (not
    unitPrice) when computing the investment delta.
    """
    perf = btcusd_short_cover.get_performance()
    assert perf["performance"]["netPerformance"] == pytest.approx(_NET_PERF, rel=1e-4)


def test_short_cover_total_investment(btcusd_short_cover):
    """
    After covering the short, totalInvestment reflects the BUY cost (43099.7).
    This confirms the investment ledger correctly records the cover transaction.
    """
    perf = btcusd_short_cover.get_performance()
    assert perf["performance"]["totalInvestment"] == pytest.approx(_TOTAL_INV, rel=1e-4)


def test_short_cover_net_performance_percentage(btcusd_short_cover):
    """netPerformancePercentage = 6998.6 / 43099.7 ≈ 0.16238."""
    perf = btcusd_short_cover.get_performance()
    assert perf["performance"]["netPerformancePercentage"] == pytest.approx(
        _NET_PERF_PCT, rel=1e-3
    )


# ===========================================================================
# Holdings endpoint
# ===========================================================================

def test_short_cover_holdings_empty(btcusd_short_cover):
    """
    After covering the short the net quantity is zero — no holding remains.
    Confirms that the BUY-to-cover correctly zeroes out the short position.
    """
    h = btcusd_short_cover.get_holdings()
    items = h["holdings"]
    if isinstance(items, dict):
        holding = items.get("BTCUSD")
    else:
        holding = next((x for x in items if x.get("symbol") == "BTCUSD"), None)

    if holding is not None:
        assert holding.get("quantity", 0) == pytest.approx(0.0, abs=1e-8)


# ===========================================================================
# Investments endpoint
# ===========================================================================

def test_short_cover_investments_by_year(btcusd_short_cover):
    """
    2021: SELL opens the short — no cash investment (short proceeds, not cost)
    2022: BUY to cover — investment = 43099.7 (cost paid to close position)
    """
    inv = btcusd_short_cover.get_investments(group_by="year")
    by_date = {e["date"]: e["investment"] for e in inv["investments"]}
    assert by_date.get("2022-01-01", 0) == pytest.approx(_BUY_PRICE, rel=1e-4)
