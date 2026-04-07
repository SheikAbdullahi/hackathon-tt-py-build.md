"""
Advanced API tests targeting Ghostfolio-specific portfolio metrics.

These tests exercise calculations NOT yet implemented in the stub translation
(translations/ghostfolio_pytx/app/main.py) but present in the real Ghostfolio
API and its ROAI portfolio calculator.  They are intended to fail against the
stub and pass only when the full calculation logic is wired in.

Derived from:
  portfolio-calculator-btcusd.spec.ts          (1 BUY, open position)
  portfolio-calculator-btcusd-buy-and-sell-partially.spec.ts  (2 BUY, 1 SELL)

Current-price note:
  The yahoo-mock returns regularMarketPrice=100 for every symbol.
  Ghostfolio uses this for today's market value / currentValueInBaseCurrency.
  Historical seeded prices are used only to build the chart time-series.

Tests that FAIL against the stub (not yet implemented):
  test_open_position_current_value_in_base_currency
  test_open_position_net_performance_includes_unrealized
  test_open_position_net_performance_percentage
  test_holding_market_price
  test_chart_entry_net_performance_absolute
  test_chart_entry_investment_value_per_date
  test_partial_sell_holding_market_price
  test_partial_sell_net_performance_combines_realized_and_unrealized

Tests that PASS against the stub (correct baseline):
  test_partial_sell_total_investment
  test_partial_sell_investments_by_year
"""
import pytest

from .mock_prices import prices_for

# ---------------------------------------------------------------------------
# Shared activity data
# ---------------------------------------------------------------------------

_BTCUSD_BUY = {
    "currency": "USD",
    "dataSource": "YAHOO",
    "date": "2021-12-12",
    "fee": 4.46,
    "quantity": 1,
    "symbol": "BTCUSD",
    "type": "BUY",
    "unitPrice": 44558.42,
}

_BTCUSD_PARTIAL_SELL = [
    {
        "currency": "USD",
        "dataSource": "YAHOO",
        "date": "2015-01-01",
        "fee": 0,
        "quantity": 2,
        "symbol": "BTCUSD",
        "type": "BUY",
        "unitPrice": 320.43,
    },
    {
        "currency": "USD",
        "dataSource": "YAHOO",
        "date": "2017-12-31",
        "fee": 0,
        "quantity": 1,
        "symbol": "BTCUSD",
        "type": "SELL",
        "unitPrice": 14156.4,
    },
]

# Yahoo-mock always returns 100.0 as the current (live) market price.
_YAHOO_MOCK_PRICE = 100.0


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def btcusd_open(gf):
    """1 BTC bought 2021-12-12 at 44558.42 with fee 4.46; BTCUSD prices seeded."""
    client, _ = gf
    client.update_user_settings("USD")
    client.import_activities([_BTCUSD_BUY])
    client.seed_market_data("YAHOO", "BTCUSD", prices_for("BTCUSD"))
    return client


@pytest.fixture
def btcusd_partial_sell(gf):
    """2 BTC bought 2015-01-01 at 320.43, 1 sold 2017-12-31 at 14156.4; prices seeded."""
    client, _ = gf
    client.update_user_settings("USD")
    client.import_activities(_BTCUSD_PARTIAL_SELL)
    client.seed_market_data("YAHOO", "BTCUSD", prices_for("BTCUSD"))
    return client


# ===========================================================================
# Open position — current market value in performance endpoint
# ===========================================================================

def test_open_position_current_value_in_base_currency(btcusd_open):
    """
    currentValueInBaseCurrency must reflect actual market value of holdings.

    Current price comes from the yahoo-mock (regularMarketPrice=100).
    1 BTC × 100 = 100.
    The stub always returns 0 for this field.
    """
    perf = btcusd_open.get_performance()
    assert perf["performance"]["currentValueInBaseCurrency"] == pytest.approx(
        _YAHOO_MOCK_PRICE, rel=1e-4
    )


def test_open_position_net_performance_includes_unrealized(btcusd_open):
    """
    netPerformance must include unrealized P&L for open positions.

    current_value (100) - investment (44558.42) - fee (4.46) = -44462.88.
    The stub computes realized_pnl (0) - fees (4.46) = -4.46 instead.
    """
    perf = btcusd_open.get_performance()
    expected = _YAHOO_MOCK_PRICE - 44558.42 - 4.46  # -44462.88
    assert perf["performance"]["netPerformance"] == pytest.approx(expected, rel=1e-3)


def test_open_position_net_performance_percentage(btcusd_open):
    """
    netPerformancePercentage = netPerformance / totalInvestment.
    (-44462.88) / 44558.42 ≈ -0.99786.
    The stub always returns 0.0 for this field.
    """
    perf = btcusd_open.get_performance()
    net_perf = _YAHOO_MOCK_PRICE - 44558.42 - 4.46
    expected = net_perf / 44558.42
    assert perf["performance"]["netPerformancePercentage"] == pytest.approx(
        expected, rel=1e-3
    )


# ===========================================================================
# Holdings — marketPrice field (from live yahoo-mock)
# ===========================================================================

def test_holding_market_price(btcusd_open):
    """
    Holdings must expose marketPrice — the current live price fetched from
    Yahoo Finance (yahoo-mock always returns 100).
    The stub returns only {quantity, investment} and omits marketPrice.
    """
    h = btcusd_open.get_holdings()
    items = h["holdings"]
    holding = (
        items.get("BTCUSD")
        if isinstance(items, dict)
        else next((x for x in items if x.get("symbol") == "BTCUSD"), None)
    )
    assert holding is not None, "BTCUSD holding not found"
    assert "marketPrice" in holding, "marketPrice field missing from holding"
    assert holding["marketPrice"] == pytest.approx(_YAHOO_MOCK_PRICE, rel=1e-4)


# ===========================================================================
# Chart — additional required fields
# ===========================================================================

def test_chart_entry_net_performance_absolute(btcusd_open):
    """
    Chart entries must include netPerformance as an absolute value (not only
    as a percentage via netPerformanceInPercentage).

    On 2021-12-12 (buy date, seeded closing price 50098.3):
      netPerformance = 50098.3 - 44558.42 - 4.46 = 5535.42

    Chart uses seeded historical prices, not the yahoo-mock current price.

    Derived from portfolio-calculator-btcusd.spec.ts historicalData[1]:
      netPerformance: 5535.42
    """
    perf = btcusd_open.get_performance()
    by_date = btcusd_open.chart_by_date(perf["chart"])
    assert "2021-12-12" in by_date
    entry = by_date["2021-12-12"]
    assert "netPerformance" in entry, "chart entry missing netPerformance field"
    assert entry["netPerformance"] == pytest.approx(5535.42, rel=1e-4)


def test_chart_entry_investment_value_per_date(btcusd_open):
    """
    Chart entries must include investmentValueWithCurrencyEffect — the amount
    of investment added or removed on that specific date (delta, not cumulative).

    On 2021-12-11 (day before buy): 0 (no investment change).
    On 2021-12-12 (buy date):       44558.42 (full investment on this date).

    Derived from portfolio-calculator-btcusd.spec.ts:
      historicalData[0].investmentValueWithCurrencyEffect: 0
      historicalData[1].investmentValueWithCurrencyEffect: 44558.42
    """
    perf = btcusd_open.get_performance()
    by_date = btcusd_open.chart_by_date(perf["chart"])

    pre_buy = by_date.get("2021-12-11", {})
    assert "investmentValueWithCurrencyEffect" in pre_buy, (
        "chart entry missing investmentValueWithCurrencyEffect"
    )
    assert pre_buy["investmentValueWithCurrencyEffect"] == pytest.approx(0.0, abs=1e-6)

    buy_day = by_date["2021-12-12"]
    assert buy_day["investmentValueWithCurrencyEffect"] == pytest.approx(
        44558.42, rel=1e-4
    )


# ===========================================================================
# Partial sell — remaining holding and combined net performance
# ===========================================================================

def test_partial_sell_total_investment(btcusd_partial_sell):
    """
    After buying 2 BTC at 320.43 and selling 1 (avg cost 320.43),
    totalInvestment = 320.43 (cost of the 1 remaining unit).

    This PASSES with the stub's average-cost implementation.
    """
    perf = btcusd_partial_sell.get_performance()
    assert perf["performance"]["totalInvestment"] == pytest.approx(320.43, rel=1e-4)


def test_partial_sell_investments_by_year(btcusd_partial_sell):
    """
    Yearly investment grouping for the partial sell scenario:
      2015: +640.86  (buy 2 × 320.43)
      2017: -320.43  (sell 1 at avg cost 320.43)

    This PASSES with the stub's delta-based investment tracking.
    """
    inv = btcusd_partial_sell.get_investments(group_by="year")
    by_date = {e["date"]: e["investment"] for e in inv["investments"]}
    assert by_date.get("2015-01-01") == pytest.approx(640.86, rel=1e-4)
    assert by_date.get("2017-01-01") == pytest.approx(-320.43, rel=1e-4)


def test_partial_sell_holding_market_price(btcusd_partial_sell):
    """
    After a partial sell the remaining holding must still expose marketPrice
    (current live price from yahoo-mock = 100).
    The stub omits marketPrice from holdings.
    """
    h = btcusd_partial_sell.get_holdings()
    items = h["holdings"]
    holding = (
        items.get("BTCUSD")
        if isinstance(items, dict)
        else next((x for x in items if x.get("symbol") == "BTCUSD"), None)
    )
    assert holding is not None, "BTCUSD holding not found after partial sell"
    assert "marketPrice" in holding, "marketPrice field missing from holding"
    assert holding["marketPrice"] == pytest.approx(_YAHOO_MOCK_PRICE, rel=1e-4)


def test_partial_sell_net_performance_combines_realized_and_unrealized(
    btcusd_partial_sell,
):
    """
    After selling 1 of 2 BTC, netPerformance combines:
      Realized:   1 × (14156.4 − 320.43) =  13835.97
      Unrealized: 1 × (100    − 320.43)  =   −220.43  (yahoo-mock price for remaining)
      Fees:       0
      Total:      13615.54

    The stub returns only realized_pnl (13835.97), omitting unrealized gains/losses.

    Derived from portfolio-calculator-btcusd-buy-and-sell-partially.spec.ts
    (USD equivalent using yahoo-mock current price instead of frozen 2018 date).
    """
    perf = btcusd_partial_sell.get_performance()
    realized = 14156.4 - 320.43              # 13835.97
    unrealized = _YAHOO_MOCK_PRICE - 320.43  # −220.43
    expected = realized + unrealized         # 13615.54
    assert perf["performance"]["netPerformance"] == pytest.approx(expected, rel=1e-3)
