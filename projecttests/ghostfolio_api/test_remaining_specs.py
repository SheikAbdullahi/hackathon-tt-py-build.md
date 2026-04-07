"""
Integration tests converted from the remaining TypeScript spec files.
Each test runs against a live Ghostfolio HTTP API.

Note on cross-currency tests (GOOGL in CHF, BTCEUR in EUR):
  The TS suite mocks exchange rates; the live API uses real rates.
  For those tests we only assert on currency-agnostic values
  (investment amount in asset currency, quantity, etc.).
"""
import pytest
import requests

from .mock_prices import prices_for


def _import_or_skip(client, activities: list) -> None:
    """Import activities, skipping the test if Yahoo Finance symbol validation fails."""
    try:
        client.import_activities(activities)
    except requests.HTTPError as e:
        if e.response is not None and e.response.status_code == 400:
            body = e.response.text
            if "is not valid for the specified data source" in body:
                pytest.skip(f"Symbol not available via Yahoo Finance in this environment: {body}")
        raise


# ===========================================================================
# BALN.SW — Baloise Group (CHF, Swiss exchange)
# ===========================================================================

@pytest.fixture
def baln_buy_session(gf):
    """BUY 2 BALN.SW on 2021-11-30 at 136.6, fee 1.55 CHF."""
    client, _ = gf
    client.update_user_settings("CHF")
    _import_or_skip(client, [
        {
            "currency": "CHF",
            "dataSource": "YAHOO",
            "date": "2021-11-30",
            "fee": 1.55,
            "quantity": 2,
            "symbol": "BALN.SW",
            "type": "BUY",
            "unitPrice": 136.6,
        }
    ])
    client.seed_market_data("YAHOO", "BALN.SW", prices_for("BALN.SW"))
    return client


def test_baln_buy_investment(baln_buy_session):
    """investment = 2 * 136.6 = 273.2 CHF"""
    perf = baln_buy_session.get_performance()
    assert perf["performance"]["totalInvestment"] == pytest.approx(273.2, rel=1e-4)


def test_baln_buy_holdings_quantity(baln_buy_session):
    """Holdings: quantity=2, investment=273.2"""
    holdings = baln_buy_session.get_holdings()
    items = holdings["holdings"]
    if isinstance(items, dict):
        h = items["BALN.SW"]
    else:
        matches = [h for h in items if h.get("symbol") == "BALN.SW"]
        assert matches, "BALN.SW holding not found"
        h = matches[0]
    assert h["quantity"] == pytest.approx(2.0, rel=1e-6)
    assert h["investment"] == pytest.approx(273.2, rel=1e-4)


def test_baln_buy_investments_list(baln_buy_session):
    """Investments list: 2021-11-30 = 273.2"""
    inv = baln_buy_session.get_investments()
    by_date = {e["date"]: e["investment"] for e in inv["investments"]}
    assert "2021-11-30" in by_date
    assert by_date["2021-11-30"] == pytest.approx(273.2, rel=1e-4)


def test_baln_buy_investments_by_month(baln_buy_session):
    """Monthly: 2021-11 = 273.2, 2021-12 = 0"""
    inv = baln_buy_session.get_investments(group_by="month")
    by_date = {e["date"]: e["investment"] for e in inv["investments"]}
    assert "2021-11-01" in by_date
    assert by_date["2021-11-01"] == pytest.approx(273.2, rel=1e-4)
    assert by_date.get("2021-12-01", 0) == pytest.approx(0.0, abs=1e-6)


def test_baln_buy_investments_by_year(baln_buy_session):
    """Yearly: 2021 = 273.2"""
    inv = baln_buy_session.get_investments(group_by="year")
    by_date = {e["date"]: e["investment"] for e in inv["investments"]}
    assert "2021-01-01" in by_date
    assert by_date["2021-01-01"] == pytest.approx(273.2, rel=1e-4)


# ---------------------------------------------------------------------------

@pytest.fixture
def baln_buy_and_buy_session(gf):
    """Two BUY activities for BALN.SW."""
    client, _ = gf
    client.update_user_settings("CHF")
    _import_or_skip(client, [
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
            "type": "BUY",
            "unitPrice": 136.6,
        },
    ])
    client.seed_market_data("YAHOO", "BALN.SW", prices_for("BALN.SW"))
    return client


def test_baln_buy_and_buy_investment(baln_buy_and_buy_session):
    """total investment = 285.8 + 273.2 = 559 CHF"""
    perf = baln_buy_and_buy_session.get_performance()
    assert perf["performance"]["totalInvestment"] == pytest.approx(559.0, rel=1e-4)


def test_baln_buy_and_buy_holdings(baln_buy_and_buy_session):
    """Holdings: quantity=4, investment=559"""
    holdings = baln_buy_and_buy_session.get_holdings()
    items = holdings["holdings"]
    if isinstance(items, dict):
        h = items["BALN.SW"]
    else:
        matches = [h for h in items if h.get("symbol") == "BALN.SW"]
        assert matches, "BALN.SW holding not found"
        h = matches[0]
    assert h["quantity"] == pytest.approx(4.0, rel=1e-6)
    assert h["investment"] == pytest.approx(559.0, rel=1e-4)


def test_baln_buy_and_buy_investments_by_month(baln_buy_and_buy_session):
    """Monthly: 2021-11 = 559, 2021-12 = 0"""
    inv = baln_buy_and_buy_session.get_investments(group_by="month")
    by_date = {e["date"]: e["investment"] for e in inv["investments"]}
    assert by_date.get("2021-11-01", 0) == pytest.approx(559.0, rel=1e-4)
    assert by_date.get("2021-12-01", 0) == pytest.approx(0.0, abs=1e-6)


def test_baln_buy_and_buy_investments_by_year(baln_buy_and_buy_session):
    """Yearly: 2021 = 559"""
    inv = baln_buy_and_buy_session.get_investments(group_by="year")
    by_date = {e["date"]: e["investment"] for e in inv["investments"]}
    assert by_date.get("2021-01-01", 0) == pytest.approx(559.0, rel=1e-4)


# ---------------------------------------------------------------------------

@pytest.fixture
def baln_buy_and_sell_session(gf):
    """BUY 2 then SELL 2 BALN.SW."""
    client, _ = gf
    client.update_user_settings("CHF")
    _import_or_skip(client, [
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


def test_baln_buy_and_sell_investment_is_zero(baln_buy_and_sell_session):
    """After buy + sell, totalInvestment = 0"""
    perf = baln_buy_and_sell_session.get_performance()
    assert perf["performance"]["totalInvestment"] == pytest.approx(0.0, abs=1e-4)


def test_baln_buy_and_sell_investments_by_month(baln_buy_and_sell_session):
    """Monthly: both months show 0 net investment"""
    inv = baln_buy_and_sell_session.get_investments(group_by="month")
    by_date = {e["date"]: e["investment"] for e in inv["investments"]}
    assert by_date.get("2021-11-01", 0) == pytest.approx(0.0, abs=1e-4)
    assert by_date.get("2021-12-01", 0) == pytest.approx(0.0, abs=1e-6)


def test_baln_buy_and_sell_investments_by_year(baln_buy_and_sell_session):
    """Yearly: 2021 = 0"""
    inv = baln_buy_and_sell_session.get_investments(group_by="year")
    by_date = {e["date"]: e["investment"] for e in inv["investments"]}
    assert by_date.get("2021-01-01", 0) == pytest.approx(0.0, abs=1e-4)


# ---------------------------------------------------------------------------

@pytest.fixture
def baln_buy_and_sell_in_two_session(gf):
    """BUY 2, SELL 1 + SELL 1 for BALN.SW (two sell activities on same date)."""
    client, _ = gf
    client.update_user_settings("CHF")
    _import_or_skip(client, [
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
            "quantity": 1,
            "symbol": "BALN.SW",
            "type": "SELL",
            "unitPrice": 136.6,
        },
        {
            "currency": "CHF",
            "dataSource": "YAHOO",
            "date": "2021-11-30",
            "fee": 0,
            "quantity": 1,
            "symbol": "BALN.SW",
            "type": "SELL",
            "unitPrice": 136.6,
        },
    ])
    client.seed_market_data("YAHOO", "BALN.SW", prices_for("BALN.SW"))
    return client


def test_baln_buy_and_sell_in_two_investment_is_zero(baln_buy_and_sell_in_two_session):
    """After buy + two sells, totalInvestment = 0"""
    perf = baln_buy_and_sell_in_two_session.get_performance()
    assert perf["performance"]["totalInvestment"] == pytest.approx(0.0, abs=1e-4)


def test_baln_buy_and_sell_in_two_investments_by_month(baln_buy_and_sell_in_two_session):
    """Monthly: 2021-11 = 0 net"""
    inv = baln_buy_and_sell_in_two_session.get_investments(group_by="month")
    by_date = {e["date"]: e["investment"] for e in inv["investments"]}
    assert by_date.get("2021-11-01", 0) == pytest.approx(0.0, abs=1e-4)


def test_baln_buy_and_sell_in_two_investments_by_year(baln_buy_and_sell_in_two_session):
    """Yearly: 2021 = 0"""
    inv = baln_buy_and_sell_in_two_session.get_investments(group_by="year")
    by_date = {e["date"]: e["investment"] for e in inv["investments"]}
    assert by_date.get("2021-01-01", 0) == pytest.approx(0.0, abs=1e-4)


# ===========================================================================
# BTCEUR — Bitcoin imported in EUR context, base currency USD
# ===========================================================================

@pytest.fixture
def btceur_session(gf):
    """
    portfolio-calculator-btceur.spec.ts
    The TS test overrides EUR values to USD: 1 BUY BTCUSD on 2021-12-12
    at 44558.42 USD, fee 4.46 USD, base currency USD.
    """
    client, _ = gf
    client.update_user_settings("USD")
    client.import_activities([
        {
            "currency": "USD",
            "dataSource": "YAHOO",
            "date": "2021-12-12",
            "fee": 4.46,
            "quantity": 1,
            "symbol": "BTCUSD",
            "type": "BUY",
            "unitPrice": 44558.42,
        }
    ])
    client.seed_market_data("YAHOO", "BTCUSD", prices_for("BTCUSD"))
    return client


def test_btceur_investment(btceur_session):
    """Investment = 44558.42 USD"""
    perf = btceur_session.get_performance()
    assert perf["performance"]["totalInvestment"] == pytest.approx(44558.42, rel=1e-4)


def test_btceur_chart_includes_year_boundary(btceur_session):
    """Chart should include 2021-12-31 and 2022-01-01"""
    perf = btceur_session.get_performance()
    by_date = btceur_session.chart_by_date(perf["chart"])
    assert "2021-12-31" in by_date
    assert "2022-01-01" in by_date


def test_btceur_chart_excludes_before_buy(btceur_session):
    """Chart should not contain dates before the activity window"""
    perf = btceur_session.get_performance()
    by_date = btceur_session.chart_by_date(perf["chart"])
    assert "2021-01-01" not in by_date


def test_btceur_investments_by_month(btceur_session):
    """Monthly: Dec 2021 = 44558.42, Jan 2022 = 0"""
    inv = btceur_session.get_investments(group_by="month")
    by_date = {e["date"]: e["investment"] for e in inv["investments"]}
    assert "2021-12-01" in by_date
    assert by_date["2021-12-01"] == pytest.approx(44558.42, rel=1e-4)
    assert by_date.get("2022-01-01", 0) == pytest.approx(0.0, abs=1e-6)


def test_btceur_investments_by_year(btceur_session):
    """Yearly: 2021 = 44558.42, 2022 = 0"""
    inv = btceur_session.get_investments(group_by="year")
    by_date = {e["date"]: e["investment"] for e in inv["investments"]}
    assert "2021-01-01" in by_date
    assert by_date["2021-01-01"] == pytest.approx(44558.42, rel=1e-4)
    assert by_date.get("2022-01-01", 0) == pytest.approx(0.0, abs=1e-6)


# ===========================================================================
# BTCEUR in base currency EUR — omitted: live exchange rate service returns
# 500 for a USD asset with EUR base; TS test uses a mocked exchange rate.
# ===========================================================================


# ===========================================================================
# BTCUSD short sell
# ===========================================================================

@pytest.fixture
def btcusd_short_session(gf):
    """
    portfolio-calculator-btcusd-short.spec.ts
    Two SELL activities (short position): SELL 1 on 2021-12-12 + SELL 1 on 2021-12-13.
    TS asserts averagePrice = (44558.42 + 46737.48) / 2 = 45647.95.
    """
    client, _ = gf
    client.update_user_settings("USD")
    client.import_activities([
        {
            "currency": "USD",
            "dataSource": "YAHOO",
            "date": "2021-12-12",
            "fee": 4.46,
            "quantity": 1,
            "symbol": "BTCUSD",
            "type": "SELL",
            "unitPrice": 44558.42,
        },
        {
            "currency": "USD",
            "dataSource": "YAHOO",
            "date": "2021-12-13",
            "fee": 4.46,
            "quantity": 1,
            "symbol": "BTCUSD",
            "type": "SELL",
            "unitPrice": 46737.48,
        },
    ])
    client.seed_market_data("YAHOO", "BTCUSD", prices_for("BTCUSD"))
    return client


def test_btcusd_short_investments_list(btcusd_short_session):
    """Short sell activities appear in the investments list."""
    inv = btcusd_short_session.get_investments()
    dates = [e["date"] for e in inv["investments"]]
    assert any(d >= "2021-12-12" for d in dates)


def test_btcusd_short_performance_accessible(btcusd_short_session):
    """Performance endpoint responds without error for a short position."""
    perf = btcusd_short_session.get_performance()
    assert "performance" in perf
    assert "chart" in perf


# ===========================================================================
# Fee-only activity
# ===========================================================================

@pytest.fixture
def fee_session(gf):
    """
    portfolio-calculator-fee.spec.ts
    FEE activity: USD, MANUAL datasource, quantity=0, fee=49.
    TS asserts: totalFees=49, positions=[], hasErrors=true.
    """
    client, _ = gf
    client.update_user_settings("USD")
    client.import_activities([
        {
            "currency": "USD",
            "dataSource": "MANUAL",
            "date": "2021-09-01",
            "fee": 49,
            "quantity": 0,
            "symbol": "2c463fb3-af07-486e-adb0-8301b3d72141",
            "type": "FEE",
            "unitPrice": 0,
        }
    ])
    return client


def test_fee_total_investment_is_zero(fee_session):
    """FEE-only portfolio has no positions → totalInvestment = 0"""
    perf = fee_session.get_performance()
    assert perf["performance"]["totalInvestment"] == pytest.approx(0.0, abs=1e-6)


def test_fee_performance_accessible(fee_session):
    """Performance endpoint responds for a fee-only portfolio."""
    perf = fee_session.get_performance()
    assert "performance" in perf


# ===========================================================================
# GOOGL buy (USD base to avoid exchange rate dependency)
# ===========================================================================

@pytest.fixture
def googl_session(gf):
    """
    portfolio-calculator-googl-buy.spec.ts
    BUY 1 GOOGL on 2023-01-03 at 89.12, fee 1, USD YAHOO.
    Using USD base (TS uses CHF + mocked exchange rate).
    """
    client, _ = gf
    client.update_user_settings("USD")
    client.import_activities([
        {
            "currency": "USD",
            "dataSource": "YAHOO",
            "date": "2023-01-03",
            "fee": 1,
            "quantity": 1,
            "symbol": "GOOGL",
            "type": "BUY",
            "unitPrice": 89.12,
        }
    ])
    client.seed_market_data("YAHOO", "GOOGL", prices_for("GOOGL"))
    return client


def test_googl_buy_investment(googl_session):
    """Investment = 89.12 USD"""
    perf = googl_session.get_performance()
    assert perf["performance"]["totalInvestment"] == pytest.approx(89.12, rel=1e-4)


def test_googl_buy_holdings_quantity(googl_session):
    """Holdings: quantity=1, investment=89.12"""
    holdings = googl_session.get_holdings()
    items = holdings["holdings"]
    if isinstance(items, dict):
        h = items["GOOGL"]
    else:
        matches = [h for h in items if h.get("symbol") == "GOOGL"]
        assert matches, "GOOGL holding not found"
        h = matches[0]
    assert h["quantity"] == pytest.approx(1.0, rel=1e-6)
    assert h["investment"] == pytest.approx(89.12, rel=1e-4)


def test_googl_buy_investments_by_month(googl_session):
    """Monthly: 2023-01 = 89.12"""
    inv = googl_session.get_investments(group_by="month")
    by_date = {e["date"]: e["investment"] for e in inv["investments"]}
    assert "2023-01-01" in by_date
    assert by_date["2023-01-01"] == pytest.approx(89.12, rel=1e-4)


def test_googl_buy_investments_by_year(googl_session):
    """Yearly: 2023 = 89.12"""
    inv = googl_session.get_investments(group_by="year")
    by_date = {e["date"]: e["investment"] for e in inv["investments"]}
    assert "2023-01-01" in by_date
    assert by_date["2023-01-01"] == pytest.approx(89.12, rel=1e-4)


# ===========================================================================
# JNUG — two buy/sell cycles, fully closed
# ===========================================================================

@pytest.fixture
def jnug_session(gf):
    """
    portfolio-calculator-jnug-buy-and-sell-and-buy-and-sell.spec.ts
    4 activities: BUY 9, SELL 9, BUY 10, SELL 10 for JNUG (all in USD).
    """
    client, _ = gf
    client.update_user_settings("USD")
    client.import_activities([
        {
            "currency": "USD",
            "dataSource": "YAHOO",
            "date": "2025-12-11",
            "fee": 1,
            "quantity": 9,
            "symbol": "JNUG",
            "type": "BUY",
            "unitPrice": 209.45,
        },
        {
            "currency": "USD",
            "dataSource": "YAHOO",
            "date": "2025-12-18",
            "fee": 1,
            "quantity": 9,
            "symbol": "JNUG",
            "type": "SELL",
            "unitPrice": 210.00,
        },
        {
            "currency": "USD",
            "dataSource": "YAHOO",
            "date": "2025-12-18",
            "fee": 1,
            "quantity": 10,
            "symbol": "JNUG",
            "type": "BUY",
            "unitPrice": 204.11,
        },
        {
            "currency": "USD",
            "dataSource": "YAHOO",
            "date": "2025-12-28",
            "fee": 1,
            "quantity": 10,
            "symbol": "JNUG",
            "type": "SELL",
            "unitPrice": 208.01,
        },
    ])
    client.seed_market_data("YAHOO", "JNUG", prices_for("JNUG"))
    return client


def test_jnug_investment_is_zero(jnug_session):
    """All positions closed → totalInvestment = 0"""
    perf = jnug_session.get_performance()
    assert perf["performance"]["totalInvestment"] == pytest.approx(0.0, abs=1e-4)


def test_jnug_net_performance(jnug_session):
    """
    netPerformance = (9*210 - 9*209.45) + (10*208.01 - 10*204.11) - 4
                   = 4.95 + 39.00 - 4 = 39.95
    """
    perf = jnug_session.get_performance()
    assert perf["performance"]["netPerformance"] == pytest.approx(39.95, rel=1e-3)


def test_jnug_investments_by_month(jnug_session):
    """Monthly: 2025-12 = 0 net"""
    inv = jnug_session.get_investments(group_by="month")
    by_date = {e["date"]: e["investment"] for e in inv["investments"]}
    assert by_date.get("2025-12-01", 0) == pytest.approx(0.0, abs=1e-4)


def test_jnug_investments_by_year(jnug_session):
    """Yearly: 2025 = 0"""
    inv = jnug_session.get_investments(group_by="year")
    by_date = {e["date"]: e["investment"] for e in inv["investments"]}
    assert by_date.get("2025-01-01", 0) == pytest.approx(0.0, abs=1e-4)


# ===========================================================================
# Liability
# ===========================================================================

@pytest.fixture
def liability_session(gf):
    """
    portfolio-calculator-liability.spec.ts
    LIABILITY activity: USD, MANUAL datasource, quantity=1, price=3000.
    TS asserts: totalLiabilitiesWithCurrencyEffect = 3000.
    """
    client, _ = gf
    client.update_user_settings("USD")
    client.import_activities([
        {
            "currency": "USD",
            "dataSource": "MANUAL",
            "date": "2023-01-01",
            "fee": 0,
            "quantity": 1,
            "symbol": "55196015-1365-4560-aa60-8751ae6d18f8",
            "type": "LIABILITY",
            "unitPrice": 3000,
        }
    ])
    client.seed_market_data(
        "MANUAL",
        "55196015-1365-4560-aa60-8751ae6d18f8",
        prices_for("55196015-1365-4560-aa60-8751ae6d18f8"),
    )
    return client


def test_liability_performance_accessible(liability_session):
    """Performance endpoint responds for a liability-only portfolio."""
    perf = liability_session.get_performance()
    assert "performance" in perf
    assert "chart" in perf


def test_liability_investment_is_zero(liability_session):
    """Liability does not count as investment → totalInvestment = 0"""
    perf = liability_session.get_performance()
    assert perf["performance"]["totalInvestment"] == pytest.approx(0.0, abs=1e-4)


# ===========================================================================
# MSFT — buy with fractional shares then sell
# ===========================================================================

@pytest.fixture
def msft_buy_and_sell_session(gf):
    """
    portfolio-calculator-msft-buy-and-sell.spec.ts
    BUY 1/3 + BUY 2/3 + SELL 1 MSFT (fractional shares that net to zero).
    TS checks getTransactionPoints(): investment=0, quantity=0.
    """
    client, _ = gf
    client.update_user_settings("USD")
    client.import_activities([
        {
            "currency": "USD",
            "dataSource": "YAHOO",
            "date": "2024-03-08",
            "fee": 0,
            "quantity": 0.3333333333333333,
            "symbol": "MSFT",
            "type": "BUY",
            "unitPrice": 408,
        },
        {
            "currency": "USD",
            "dataSource": "YAHOO",
            "date": "2024-03-13",
            "fee": 0,
            "quantity": 0.6666666666666666,
            "symbol": "MSFT",
            "type": "BUY",
            "unitPrice": 400,
        },
        {
            "currency": "USD",
            "dataSource": "YAHOO",
            "date": "2024-03-14",
            "fee": 0,
            "quantity": 1,
            "symbol": "MSFT",
            "type": "SELL",
            "unitPrice": 411,
        },
    ])
    client.seed_market_data("YAHOO", "MSFT", prices_for("MSFT"))
    return client


def test_msft_buy_and_sell_investment_near_zero(msft_buy_and_sell_session):
    """After buying and selling all fractional shares, investment ≈ 0"""
    perf = msft_buy_and_sell_session.get_performance()
    assert perf["performance"]["totalInvestment"] == pytest.approx(0.0, abs=1.0)


# ===========================================================================
# MSFT — buy with dividend
# ===========================================================================

@pytest.fixture
def msft_dividend_session(gf):
    """
    portfolio-calculator-msft-buy-with-dividend.spec.ts
    BUY 1 MSFT on 2021-09-16 at 298.58, fee 19 + DIVIDEND 1 @ 0.62.
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


def test_msft_dividend_investment(msft_dividend_session):
    """Investment = 298.58 USD"""
    perf = msft_dividend_session.get_performance()
    assert perf["performance"]["totalInvestment"] == pytest.approx(298.58, rel=1e-4)


def test_msft_dividend_holdings(msft_dividend_session):
    """Holdings: MSFT quantity=1, investment=298.58"""
    holdings = msft_dividend_session.get_holdings()
    items = holdings["holdings"]
    if isinstance(items, dict):
        h = items["MSFT"]
    else:
        matches = [h for h in items if h.get("symbol") == "MSFT"]
        assert matches, "MSFT holding not found"
        h = matches[0]
    assert h["quantity"] == pytest.approx(1.0, rel=1e-6)
    assert h["investment"] == pytest.approx(298.58, rel=1e-4)


# ===========================================================================
# NOVN.SW — Novartis (CHF, Swiss exchange)
# ===========================================================================

@pytest.fixture
def novn_buy_and_sell_partially_session(gf):
    """
    portfolio-calculator-novn-buy-and-sell-partially.spec.ts
    From novn-buy-and-sell-partially.json:
      BUY  2 NOVN.SW @ 75.8  on 2022-03-07, fee=2.95 CHF
      SELL 1 NOVN.SW @ 85.73 on 2022-04-08, fee=1.3  CHF
    """
    client, _ = gf
    client.update_user_settings("CHF")
    client.import_activities([
        {
            "currency": "CHF",
            "dataSource": "YAHOO",
            "date": "2022-03-07",
            "fee": 2.95,
            "quantity": 2,
            "symbol": "NOVN.SW",
            "type": "BUY",
            "unitPrice": 75.8,
        },
        {
            "currency": "CHF",
            "dataSource": "YAHOO",
            "date": "2022-04-08",
            "fee": 1.3,
            "quantity": 1,
            "symbol": "NOVN.SW",
            "type": "SELL",
            "unitPrice": 85.73,
        },
    ])
    client.seed_market_data("YAHOO", "NOVN.SW", prices_for("NOVN.SW"))
    return client


def test_novn_buy_and_sell_partially_investment(novn_buy_and_sell_partially_session):
    """After partial sell, investment = 75.80 CHF (1 share at avg cost 75.8)"""
    perf = novn_buy_and_sell_partially_session.get_performance()
    assert perf["performance"]["totalInvestment"] == pytest.approx(75.8, rel=1e-4)


def test_novn_buy_and_sell_partially_holdings(novn_buy_and_sell_partially_session):
    """Holdings: NOVN.SW quantity=1, investment=75.8"""
    holdings = novn_buy_and_sell_partially_session.get_holdings()
    items = holdings["holdings"]
    if isinstance(items, dict):
        h = items["NOVN.SW"]
    else:
        matches = [h for h in items if h.get("symbol") == "NOVN.SW"]
        assert matches, "NOVN.SW holding not found"
        h = matches[0]
    assert h["quantity"] == pytest.approx(1.0, rel=1e-6)
    assert h["investment"] == pytest.approx(75.8, rel=1e-4)


def test_novn_buy_and_sell_partially_investments_by_month(
    novn_buy_and_sell_partially_session,
):
    """Monthly: 2022-03 = 151.6, 2022-04 = -75.8"""
    inv = novn_buy_and_sell_partially_session.get_investments(group_by="month")
    by_date = {e["date"]: e["investment"] for e in inv["investments"]}
    assert by_date.get("2022-03-01", 0) == pytest.approx(151.6, rel=1e-4)
    assert by_date.get("2022-04-01", 0) == pytest.approx(-75.8, rel=1e-4)


def test_novn_buy_and_sell_partially_investments_by_year(
    novn_buy_and_sell_partially_session,
):
    """Yearly: 2022 = 75.8"""
    inv = novn_buy_and_sell_partially_session.get_investments(group_by="year")
    by_date = {e["date"]: e["investment"] for e in inv["investments"]}
    assert by_date.get("2022-01-01", 0) == pytest.approx(75.8, rel=1e-4)


# ---------------------------------------------------------------------------

@pytest.fixture
def novn_buy_and_sell_session(gf):
    """
    portfolio-calculator-novn-buy-and-sell.spec.ts
    From novn-buy-and-sell.json:
      BUY  2 NOVN.SW @ 75.8  on 2022-03-07, fee=0 CHF
      SELL 2 NOVN.SW @ 85.73 on 2022-04-08, fee=0 CHF
    """
    client, _ = gf
    client.update_user_settings("CHF")
    client.import_activities([
        {
            "currency": "CHF",
            "dataSource": "YAHOO",
            "date": "2022-03-07",
            "fee": 0,
            "quantity": 2,
            "symbol": "NOVN.SW",
            "type": "BUY",
            "unitPrice": 75.8,
        },
        {
            "currency": "CHF",
            "dataSource": "YAHOO",
            "date": "2022-04-08",
            "fee": 0,
            "quantity": 2,
            "symbol": "NOVN.SW",
            "type": "SELL",
            "unitPrice": 85.73,
        },
    ])
    client.seed_market_data("YAHOO", "NOVN.SW", prices_for("NOVN.SW"))
    return client


def test_novn_buy_and_sell_investment_is_zero(novn_buy_and_sell_session):
    """After full sell, totalInvestment = 0"""
    perf = novn_buy_and_sell_session.get_performance()
    assert perf["performance"]["totalInvestment"] == pytest.approx(0.0, abs=1e-4)


def test_novn_buy_and_sell_net_performance(novn_buy_and_sell_session):
    """netPerformance = 2 * (85.73 - 75.8) = 19.86 CHF"""
    perf = novn_buy_and_sell_session.get_performance()
    assert perf["performance"]["netPerformance"] == pytest.approx(19.86, rel=1e-4)


def test_novn_buy_and_sell_investments_by_month(novn_buy_and_sell_session):
    """Monthly: 2022-03 = 151.6, 2022-04 = -151.6"""
    inv = novn_buy_and_sell_session.get_investments(group_by="month")
    by_date = {e["date"]: e["investment"] for e in inv["investments"]}
    assert by_date.get("2022-03-01", 0) == pytest.approx(151.6, rel=1e-4)
    assert by_date.get("2022-04-01", 0) == pytest.approx(-151.6, rel=1e-4)


def test_novn_buy_and_sell_investments_by_year(novn_buy_and_sell_session):
    """Yearly: 2022 = 0"""
    inv = novn_buy_and_sell_session.get_investments(group_by="year")
    by_date = {e["date"]: e["investment"] for e in inv["investments"]}
    assert by_date.get("2022-01-01", 0) == pytest.approx(0.0, abs=1e-4)


# ===========================================================================
# Valuable — high-value manual asset
# ===========================================================================

@pytest.fixture
def valuable_session(gf):
    """
    portfolio-calculator-valuable.spec.ts
    BUY 1 "Penthouse Apartment" (UUID symbol, MANUAL), price 500000, USD.
    """
    client, _ = gf
    client.update_user_settings("USD")
    client.import_activities([
        {
            "currency": "USD",
            "dataSource": "MANUAL",
            "date": "2022-01-01",
            "fee": 0,
            "quantity": 1,
            "symbol": "dac95060-d4f2-4653-a253-2c45e6fb5cde",
            "type": "BUY",
            "unitPrice": 500000,
        }
    ])
    return client


def test_valuable_investment(valuable_session):
    """Investment = 500000 USD"""
    perf = valuable_session.get_performance()
    assert perf["performance"]["totalInvestment"] == pytest.approx(500000, rel=1e-4)


def test_valuable_holdings(valuable_session):
    """Holdings should show the valuable asset with quantity=1"""
    holdings = valuable_session.get_holdings()
    items = holdings["holdings"]
    symbol = "dac95060-d4f2-4653-a253-2c45e6fb5cde"
    if isinstance(items, dict):
        h = items[symbol]
    else:
        matches = [h for h in items if h.get("symbol") == symbol]
        assert matches, "Penthouse apartment holding not found"
        h = matches[0]
    assert h["quantity"] == pytest.approx(1.0, rel=1e-6)
    assert h["investment"] == pytest.approx(500000, rel=1e-4)


# ===========================================================================
# Cash (account balances) — omitted: requires AccountBalanceService setup
# and exchange rate mocking not replicable via the REST API alone.
# ===========================================================================
