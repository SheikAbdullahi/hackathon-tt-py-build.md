"""
MSFT fractional buy + buy + full sell — tests fractional quantity handling.

Exercises the ROAI calculator with non-integer share quantities and verifies
that cost basis correctly reaches zero after selling the full (fractional) position.

Scenario (from portfolio-calculator-msft-buy-and-sell.spec.ts):
  BUY  0.3333... MSFT @ USD 408, fee 0 — 2024-03-08
  BUY  0.6666... MSFT @ USD 400, fee 0 — 2024-03-13
  SELL 1.0       MSFT @ USD 411, fee 0 — 2024-03-14
  Base currency: USD

Key calculations:
  cost_buy1 = 0.3333... × 408 ≈ 136.00
  cost_buy2 = 0.6666... × 400 ≈ 266.67
  total_cost ≈ 402.67  (average price ≈ 402.67 per share)

  sell_proceeds = 1 × 411 = 411
  realized_gain = 411 − 402.67 ≈ 8.33
  netPerformance ≈ 8.33  (no fees)
  totalInvestment = 0    (position fully closed)

  All three transactions fall in the same month (March 2024), so:
    investments by month: 2024-03 ≈ 0
    investments by year:  2024    ≈ 0

The TS unit test only asserts position.investment=0, position.quantity=0.
These API-level tests verify the same invariants plus realized performance.
"""
import pytest

from .mock_prices import prices_for

_QTY1 = 0.3333333333333333
_QTY2 = 0.6666666666666666
_PRICE1 = 408.0
_PRICE2 = 400.0
_SELL_PRICE = 411.0

_COST_BUY1 = _QTY1 * _PRICE1          # ≈ 136.00
_COST_BUY2 = _QTY2 * _PRICE2          # ≈ 266.67
_TOTAL_COST = _COST_BUY1 + _COST_BUY2  # ≈ 402.67
_SELL_PROCEEDS = (_QTY1 + _QTY2) * _SELL_PRICE  # = 1.0 × 411 = 411.0
_NET_PERF = _SELL_PROCEEDS - _TOTAL_COST  # ≈ 8.33


@pytest.fixture
def msft_fractional(gf):
    """
    Two fractional BUY activities followed by a SELL that closes the position.
    USD base currency.
    """
    client, _ = gf
    client.update_user_settings("USD")
    client.import_activities([
        {
            "currency": "USD",
            "dataSource": "YAHOO",
            "date": "2024-03-08",
            "fee": 0,
            "quantity": _QTY1,
            "symbol": "MSFT",
            "type": "BUY",
            "unitPrice": _PRICE1,
        },
        {
            "currency": "USD",
            "dataSource": "YAHOO",
            "date": "2024-03-13",
            "fee": 0,
            "quantity": _QTY2,
            "symbol": "MSFT",
            "type": "BUY",
            "unitPrice": _PRICE2,
        },
        {
            "currency": "USD",
            "dataSource": "YAHOO",
            "date": "2024-03-14",
            "fee": 0,
            "quantity": _QTY1 + _QTY2,
            "symbol": "MSFT",
            "type": "SELL",
            "unitPrice": _SELL_PRICE,
        },
    ])
    client.seed_market_data("YAHOO", "MSFT", prices_for("MSFT"))
    return client


# ===========================================================================
# Performance endpoint
# ===========================================================================

def test_fractional_closed_total_investment_is_zero(msft_fractional):
    """
    After selling the full (fractional) position, totalInvestment = 0.

    Mirrors the TS unit test assertion: position.investment.toNumber() === 0.
    """
    perf = msft_fractional.get_performance()
    assert perf["performance"]["totalInvestment"] == pytest.approx(0.0, abs=1e-4)


def test_fractional_closed_net_performance(msft_fractional):
    """
    Realized gain = sell proceeds − total cost = 411 − 402.67 ≈ 8.33.
    No fees, position fully closed (no unrealized component).
    """
    perf = msft_fractional.get_performance()
    assert perf["performance"]["netPerformance"] == pytest.approx(_NET_PERF, abs=0.01)


# ===========================================================================
# Investments endpoint
# ===========================================================================

def test_fractional_investments_by_month_net_zero(msft_fractional):
    """
    All three activities fall in 2024-03, so the monthly investment delta is 0.
    (BUY +402.67, SELL -402.67 within the same month.)
    """
    inv = msft_fractional.get_investments(group_by="month")
    by_date = {e["date"]: e["investment"] for e in inv["investments"]}
    assert by_date.get("2024-03-01", 0) == pytest.approx(0.0, abs=0.01)


def test_fractional_investments_by_year_net_zero(msft_fractional):
    """
    All three activities fall in 2024, so the annual investment delta is 0.
    """
    inv = msft_fractional.get_investments(group_by="year")
    by_date = {e["date"]: e["investment"] for e in inv["investments"]}
    assert by_date.get("2024-01-01", 0) == pytest.approx(0.0, abs=0.01)


# ===========================================================================
# Holdings endpoint
# ===========================================================================

def test_fractional_holdings_empty_after_full_sell(msft_fractional):
    """
    After selling all shares, MSFT must not appear as an open holding
    (or must have quantity=0 if present in the response).

    Mirrors the TS unit test assertion: position.quantity.toNumber() === 0.
    """
    h = msft_fractional.get_holdings()
    items = h["holdings"]
    if isinstance(items, dict):
        holding = items.get("MSFT")
    else:
        holding = next((x for x in items if x.get("symbol") == "MSFT"), None)

    if holding is not None:
        assert holding.get("quantity", 0) == pytest.approx(0.0, abs=1e-8)
