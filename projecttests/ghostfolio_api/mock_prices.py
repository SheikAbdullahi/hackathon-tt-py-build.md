"""
Mock market prices extracted from CurrentRateServiceMock in the TypeScript test suite.
(projects/ghostfolio/apps/api/src/app/portfolio/current-rate.service.mock.ts)

Used to seed deterministic market data into the API before running tests.
Format per symbol: list of {"date": "YYYY-MM-DD", "marketPrice": float}
"""

PRICES: dict[str, list[dict]] = {
    # Liability / cash placeholder (UUID symbol)
    "55196015-1365-4560-aa60-8751ae6d18f8": [
        {"date": "2022-01-31", "marketPrice": 3000},
    ],
    # Baloise Group (Swiss exchange)
    "BALN.SW": [
        {"date": "2021-11-12", "marketPrice": 146.0},
        {"date": "2021-11-22", "marketPrice": 142.9},
        {"date": "2021-11-26", "marketPrice": 139.9},
        {"date": "2021-11-30", "marketPrice": 136.6},
        {"date": "2021-12-12", "marketPrice": 142.0},
        {"date": "2021-12-17", "marketPrice": 143.9},
        {"date": "2021-12-18", "marketPrice": 148.9},
    ],
    # Bitcoin USD
    "BTCUSD": [
        {"date": "2015-01-01", "marketPrice": 314.25},
        {"date": "2017-12-31", "marketPrice": 14156.4},
        {"date": "2018-01-01", "marketPrice": 13657.2},
        {"date": "2021-12-12", "marketPrice": 50098.3},
        {"date": "2022-01-14", "marketPrice": 43099.7},
    ],
    # Google / Alphabet
    "GOOGL": [
        {"date": "2023-01-03", "marketPrice": 89.12},
        {"date": "2023-07-10", "marketPrice": 116.45},
    ],
    # Direxion Junior Gold Miners ETF
    "JNUG": [
        {"date": "2025-12-10", "marketPrice": 204.5599975585938},
        {"date": "2025-12-17", "marketPrice": 203.9700012207031},
        {"date": "2025-12-28", "marketPrice": 237.8000030517578},
    ],
    # Microsoft
    "MSFT": [
        {"date": "2021-09-16", "marketPrice": 89.12},
        {"date": "2021-11-16", "marketPrice": 339.51},
        {"date": "2023-07-09", "marketPrice": 337.22},
        {"date": "2023-07-10", "marketPrice": 331.83},
        # Fractional buy/sell scenario (test_msft_fractional.py)
        {"date": "2024-03-08", "marketPrice": 408.0},
        {"date": "2024-03-13", "marketPrice": 400.0},
        {"date": "2024-03-14", "marketPrice": 411.0},
    ],
    # Novartis (Swiss exchange)
    "NOVN.SW": [
        # buy-and-sell scenario (test_novn_buy_and_sell.py)
        {"date": "2022-03-07", "marketPrice": 75.8},
        {"date": "2022-04-08", "marketPrice": 85.73},
        {"date": "2022-04-11", "marketPrice": 87.8},
    ],
}


def prices_for(symbol: str) -> list[dict]:
    """Return the mock price list for a symbol, or [] if unknown.

    Also appends today's date with price 100.0 to represent the current market
    price returned by the yahoo-mock (regularMarketPrice=100 for all symbols).
    This lets the pytx stub forward-fill historical prices to 100.0 as the
    live current price without calling Yahoo Finance directly.
    """
    from datetime import date
    prices = list(PRICES.get(symbol, []))
    if prices:
        prices.append({"date": date.today().isoformat(), "marketPrice": 100.0})
    return prices
