"""
Deeper API tests exposing complex TypeScript logic not yet implemented in the pytx stub.

These tests target two of the most algorithmically complex areas of the Ghostfolio
ROAI portfolio calculator that are hard to translate and are NOT implemented in the
pytx stub (translations/ghostfolio_pytx/app/main.py):

1. Time-Weighted Investment (TWI) denominator for netPerformancePercentage
   -----------------------------------------------------------------------
   For a FULLY CLOSED position totalInvestment=0, but the real Ghostfolio
   divides by the time-weighted investment rather than by zero.  The pytx
   stub returns 0.0 because of a simple "if total_investment > 0 else 0.0"
   guard.

   Source: portfolio-calculator-baln-buy-and-sell.spec.ts
     netPerformancePercentage = -15.8 / 285.8 ≈ -0.05528
     (285.8 = time-weighted denominator, not totalInvestment which is 0)

2. Unrealized P&L with market prices from yahoo-mock for open positions
   that also have DIVIDEND activities
   --------------------------------------------------------------------
   The pytx stub ignores market prices entirely for performance calculations.
   It also completely ignores DIVIDEND activities (no cost-basis change, but
   the open position's current value must still be fetched from the live
   price feed).

   Source: portfolio-calculator-msft-buy-with-dividend.spec.ts
     currentValueInBaseCurrency = 1 × yahoo-mock price (100)
     netPerformance = currentValue − investment − fees

Tests that FAIL against the pytx stub (not yet implemented):
  test_fully_closed_net_performance_percentage
  test_msft_dividend_current_value_in_base_currency
  test_msft_dividend_net_performance
  test_msft_dividend_net_performance_percentage
  test_msft_dividend_holding_market_price
"""
import pytest

from .mock_prices import prices_for

# Yahoo-mock always returns 100.0 as the current (live) market price.
_YAHOO_MOCK_PRICE = 100.0


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def baln_closed(gf):
    """
    BALN.SW buy+sell (fully closed position):
      BUY  2 @ CHF 142.9, fee 1.55  — 2021-11-22
      SELL 2 @ CHF 136.6, fee 1.65  — 2021-11-30
    All shares sold; position is fully closed.
    """
    client, _ = gf
    client.update_user_settings("CHF")
    client.import_activities([
        {
            "currency": "CHF",
            "dataSource": "YAHOO",
            "date": "2021-11-22",
            "fee": 1.55,
            "quantity": 2,
            "symbol": "BALN.SW",
            "type": "BUY",
            "unitPrice": 142.9,
        },
        {
            "currency": "CHF",
            "dataSource": "YAHOO",
            "date": "2021-11-30",
            "fee": 1.65,
            "quantity": 2,
            "symbol": "BALN.SW",
            "type": "SELL",
            "unitPrice": 136.6,
        },
    ])
    client.seed_market_data("YAHOO", "BALN.SW", prices_for("BALN.SW"))
    return client


@pytest.fixture
def msft_with_dividend(gf):
    """
    MSFT buy + dividend (open position):
      BUY 1 MSFT @ USD 298.58, fee 19 — 2021-09-16
      DIVIDEND 1 MSFT @ USD 0.62, fee 0 — 2021-11-16
    Position remains open (1 share held).
    """
    client, _ = gf
    client.update_user_settings("USD")
    client.import_activities([
        {
            "currency": "USD",
            "dataSource": "YAHOO",
            "date": "2021-09-16",
            "fee": 19,
            "quantity": 1,
            "symbol": "MSFT",
            "type": "BUY",
            "unitPrice": 298.58,
        },
        {
            "currency": "USD",
            "dataSource": "YAHOO",
            "date": "2021-11-16",
            "fee": 0,
            "quantity": 1,
            "symbol": "MSFT",
            "type": "DIVIDEND",
            "unitPrice": 0.62,
        },
    ])
    client.seed_market_data("YAHOO", "MSFT", prices_for("MSFT"))
    return client


# ===========================================================================
# BALN.SW — time-weighted investment (TWI) as performance denominator
# ===========================================================================

def test_fully_closed_net_performance_percentage(baln_closed):
    """
    For a fully closed position totalInvestment=0.  The real Ghostfolio uses the
    time-weighted investment (TWI=285.8) as the denominator instead of zero.

    Calculation:
      grossPerformance = 2×136.6 − 2×142.9 = 273.2 − 285.8 = −12.6
      netPerformance   = −12.6 − (1.55+1.65) = −15.8
      TWI              = 2 × 142.9 = 285.8  (original investment before closure)
      netPerformancePercentage = −15.8 / 285.8 ≈ −0.05528

    The pytx stub returns 0.0 because totalInvestment=0 triggers a
    division-by-zero guard that ignores the TWI denominator entirely.

    Source: portfolio-calculator-baln-buy-and-sell.spec.ts
    """
    perf = baln_closed.get_performance()
    expected = -15.8 / 285.8  # ≈ -0.05528341497550735
    assert perf["performance"]["netPerformancePercentage"] == pytest.approx(
        expected, rel=1e-3
    )


def test_fully_closed_net_performance_value(baln_closed):
    """
    netPerformance for a fully closed position equals realized P&L minus fees.

    netPerformance = (sell_proceeds − buy_cost) − fees
                   = (2×136.6 − 2×142.9) − 3.2
                   = −12.6 − 3.2 = −15.8

    The pytx stub correctly computes realized_pnl − fees for this case,
    so this test also passes against the stub (serves as a baseline sanity check).

    Source: portfolio-calculator-baln-buy-and-sell.spec.ts
    """
    perf = baln_closed.get_performance()
    assert perf["performance"]["netPerformance"] == pytest.approx(-15.8, rel=1e-4)


# ===========================================================================
# MSFT — open position with dividend activity
# ===========================================================================

def test_msft_dividend_current_value_in_base_currency(msft_with_dividend):
    """
    currentValueInBaseCurrency must reflect the live market price (yahoo-mock=100)
    for the 1 open MSFT share, even when a DIVIDEND activity is also present.

    Expected: 1 × 100 = 100.0
    The pytx stub always returns 0.0 for this field (market prices ignored).
    """
    perf = msft_with_dividend.get_performance()
    assert perf["performance"]["currentValueInBaseCurrency"] == pytest.approx(
        _YAHOO_MOCK_PRICE, rel=1e-4
    )


def test_msft_dividend_net_performance(msft_with_dividend):
    """
    netPerformance for an open position includes unrealized gain/loss.

    currentValue  = 1 × 100 = 100          (yahoo-mock)
    investment    = 298.58                  (DIVIDEND does not change cost basis)
    fees          = 19                      (BUY fee only)
    netPerformance = 100 − 298.58 − 19 = −217.58

    The pytx stub computes realized_pnl(0) − fees(19) = −19, ignoring
    unrealized P&L from the live market price.
    """
    perf = msft_with_dividend.get_performance()
    expected = _YAHOO_MOCK_PRICE - 298.58 - 19  # -217.58
    assert perf["performance"]["netPerformance"] == pytest.approx(expected, rel=1e-3)


def test_msft_dividend_net_performance_percentage(msft_with_dividend):
    """
    netPerformancePercentage = netPerformance / totalInvestment.

    netPerformance   = 100 − 298.58 − 19 = −217.58
    totalInvestment  = 298.58
    percentage       = −217.58 / 298.58 ≈ −0.7285

    The pytx stub always returns 0.0 for this field.
    """
    perf = msft_with_dividend.get_performance()
    net_perf = _YAHOO_MOCK_PRICE - 298.58 - 19
    expected = net_perf / 298.58  # ≈ -0.7285
    assert perf["performance"]["netPerformancePercentage"] == pytest.approx(
        expected, rel=1e-3
    )


def test_msft_dividend_holding_market_price(msft_with_dividend):
    """
    The MSFT holding must expose marketPrice (current live price from yahoo-mock=100),
    even though the portfolio also contains a DIVIDEND activity for MSFT.

    The pytx stub's holdings only contain {quantity, investment} and omit marketPrice.
    """
    h = msft_with_dividend.get_holdings()
    items = h["holdings"]
    holding = (
        items.get("MSFT")
        if isinstance(items, dict)
        else next((x for x in items if x.get("symbol") == "MSFT"), None)
    )
    assert holding is not None, "MSFT holding not found"
    assert "marketPrice" in holding, "marketPrice field missing from holding"
    assert holding["marketPrice"] == pytest.approx(_YAHOO_MOCK_PRICE, rel=1e-4)


def test_msft_dividend_total_investment_unchanged(msft_with_dividend):
    """
    A DIVIDEND activity must NOT change totalInvestment — only BUY/SELL affect
    the cost basis.

    totalInvestment = 1 × 298.58 = 298.58 (BUY cost; dividend excluded)

    This PASSES with the pytx stub's cost-basis implementation (DIVIDEND is
    silently ignored, leaving investment unchanged).  It serves as a baseline
    to confirm dividend isolation.
    """
    perf = msft_with_dividend.get_performance()
    assert perf["performance"]["totalInvestment"] == pytest.approx(298.58, rel=1e-4)
