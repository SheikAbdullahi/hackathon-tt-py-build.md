#!/usr/bin/env python3
"""
Minimal HTTPS mock for Yahoo Finance APIs used by yahoo-finance2.

Handles:
  GET /quote/AAPL                       (finance.yahoo.com)  -> 200 + Set-Cookie
  GET /v1/test/getcrumb                 (query1.finance.yahoo.com) -> "mock-crumb"
  GET /v10/finance/quoteSummary/{sym}   -> quoteSummary JSON
  GET /v7/finance/quote                 -> quote JSON
  GET /v8/finance/chart/{sym}           -> chart JSON (empty)

Schema notes (from yahoo-finance2 quoteSummary-iface.schema.js):
  Price required: maxAge, priceHint, quoteType, symbol, underlyingSymbol,
                  shortName, longName, lastMarket, fromCurrency
  SummaryProfile required: companyOfficers (array), maxAge
  TopHoldings required: maxAge, holdings, equityHoldings, bondHoldings,
                        bondRatings, sectorWeightings
  TopHoldingsEquityHoldings required: priceToBook, priceToCashflow,
                                      priceToEarnings, priceToSales
"""

import json
import ssl
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

CERT_FILE = "/tmp/mock-cert.pem"
KEY_FILE = "/tmp/mock-key.pem"

# ---------------------------------------------------------------------------
# Per-symbol mock data
# ---------------------------------------------------------------------------
SYMBOL_DATA = {
    "BALN.SW": {
        "longName": "Baloise Holding AG",
        "shortName": "BALN.SW",
        "quoteType": "EQUITY",
        "currency": "CHF",
        "exchange": "EBS",
        "country": "Switzerland",
        "sector": "Financial Services",
    },
    "NOVN.SW": {
        "longName": "Novartis AG",
        "shortName": "NOVN.SW",
        "quoteType": "EQUITY",
        "currency": "CHF",
        "exchange": "EBS",
        "country": "Switzerland",
        "sector": "Healthcare",
    },
    "BTCUSD": {
        "longName": "Bitcoin USD",
        "shortName": "BTC-USD",
        "quoteType": "CRYPTOCURRENCY",
        "currency": "USD",
        "exchange": "CCC",
        "country": None,
        "sector": None,
    },
    "GOOGL": {
        "longName": "Alphabet Inc.",
        "shortName": "Alphabet Inc.",
        "quoteType": "EQUITY",
        "currency": "USD",
        "exchange": "NMS",
        "country": "United States",
        "sector": "Communication Services",
    },
    "MSFT": {
        "longName": "Microsoft Corporation",
        "shortName": "Microsoft Corporation",
        "quoteType": "EQUITY",
        "currency": "USD",
        "exchange": "NMS",
        "country": "United States",
        "sector": "Technology",
    },
    "JNUG": {
        "longName": "Direxion Daily Junior Gold Miners Index Bull 2X Shares",
        "shortName": "JNUG",
        "quoteType": "ETF",
        "currency": "USD",
        "exchange": "PCX",
        "country": None,
        "sector": None,
    },
    "AAPL": {
        "longName": "Apple Inc.",
        "shortName": "Apple Inc.",
        "quoteType": "EQUITY",
        "currency": "USD",
        "exchange": "NMS",
        "country": "United States",
        "sector": "Technology",
    },
}

_DEFAULT = {
    "longName": None,
    "shortName": None,
    "quoteType": "EQUITY",
    "currency": "USD",
    "exchange": "NYQ",
    "country": None,
    "sector": None,
}


def _sym_data(symbol: str) -> dict:
    d = SYMBOL_DATA.get(symbol, _DEFAULT).copy()
    d.setdefault("longName", symbol)
    d.setdefault("shortName", symbol)
    return d


def _equity_holdings():
    """Minimal TopHoldingsEquityHoldings (all required fields)."""
    return {
        "priceToBook": 1.0,
        "priceToCashflow": 1.0,
        "priceToEarnings": 1.0,
        "priceToSales": 1.0,
    }


def make_quote_summary(symbol: str) -> dict:
    d = _sym_data(symbol)
    price = {
        # Required fields
        "maxAge": 1,
        "priceHint": 2,
        "quoteType": d["quoteType"],
        "symbol": symbol,
        "underlyingSymbol": None,
        "shortName": d["shortName"],
        "longName": d["longName"],
        "lastMarket": None,
        "fromCurrency": None,
        # Optional but used by Ghostfolio
        "currency": d["currency"],
        "exchange": d["exchange"],
        "exchangeName": d["exchange"],
        "regularMarketPrice": 100.0,
        "marketState": "CLOSED",
    }
    summary_profile = {
        "maxAge": 1,
        "companyOfficers": [],
    }
    if d.get("country"):
        summary_profile["country"] = d["country"]
    if d.get("sector"):
        summary_profile["sector"] = d["sector"]

    top_holdings = {
        "maxAge": 1,
        "holdings": [],
        "equityHoldings": _equity_holdings(),
        "bondHoldings": {},
        "bondRatings": [],
        "sectorWeightings": [],
    }
    return {
        "quoteSummary": {
            "result": [
                {
                    "price": price,
                    "summaryProfile": summary_profile,
                    "topHoldings": top_holdings,
                }
            ],
            "error": None,
        }
    }


def make_quote(symbol: str) -> dict:
    d = _sym_data(symbol)
    return {
        "symbol": symbol,
        "quoteType": d["quoteType"],
        "shortName": d["shortName"],
        "longName": d["longName"],
        "currency": d["currency"],
        "regularMarketPrice": 100.0,
    }


# ---------------------------------------------------------------------------
# HTTP handler
# ---------------------------------------------------------------------------
class MockYahooHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):  # noqa: A002
        print(f"[yahoo-mock] {self.address_string()} - {format % args}", file=sys.stderr, flush=True)

    def send_json(self, data, status=200):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_text(self, text, status=200):
        body = text.encode()
        self.send_response(status)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        # Cookie seed endpoint (finance.yahoo.com/quote/*)
        if path.startswith("/quote/"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header(
                "Set-Cookie",
                "B=mock_cookie_value; Domain=.yahoo.com; Path=/; Secure",
            )
            body = b"<html><body>mock</body></html>"
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        # Crumb endpoint (query1.finance.yahoo.com/v1/test/getcrumb)
        if path == "/v1/test/getcrumb":
            self.send_text("mock-crumb-12345")
            return

        # quoteSummary (query2.finance.yahoo.com/v10/finance/quoteSummary/{sym})
        if path.startswith("/v10/finance/quoteSummary/"):
            symbol = path.removeprefix("/v10/finance/quoteSummary/")
            self.send_json(make_quote_summary(symbol))
            return

        # quote (v7)
        if path == "/v7/finance/quote":
            qs = parse_qs(parsed.query)
            symbols = qs.get("symbols", ["UNKNOWN"])[0].split(",")
            self.send_json(
                {"quoteResponse": {"result": [make_quote(s) for s in symbols], "error": None}}
            )
            return

        # chart (v8) – return empty dataset; we seed real prices via the admin API
        if path.startswith("/v8/finance/chart/"):
            symbol = path.removeprefix("/v8/finance/chart/").split("?")[0]
            d = _sym_data(symbol)
            self.send_json(
                {
                    "chart": {
                        "result": [
                            {
                                "meta": {
                                    "currency": d["currency"],
                                    "symbol": symbol,
                                    "exchangeName": d["exchange"],
                                    "regularMarketPrice": 100.0,
                                    "dataGranularity": "1d",
                                },
                                "timestamp": [],
                                "indicators": {
                                    "quote": [
                                        {
                                            "close": [],
                                            "open": [],
                                            "high": [],
                                            "low": [],
                                            "volume": [],
                                        }
                                    ],
                                    "adjclose": [{"adjclose": []}],
                                },
                            }
                        ],
                        "error": None,
                    }
                }
            )
            return

        # historical download (v7/finance/download)
        if path.startswith("/v7/finance/download/"):
            self.send_text("Date,Open,High,Low,Close,Adj Close,Volume\n")
            return

        self.send_response(404)
        self.end_headers()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def generate_cert():
    subprocess.run(
        [
            "openssl",
            "req",
            "-x509",
            "-newkey",
            "rsa:2048",
            "-keyout",
            KEY_FILE,
            "-out",
            CERT_FILE,
            "-days",
            "3650",
            "-nodes",
            "-subj",
            "/CN=finance.yahoo.com",
            "-addext",
            "subjectAltName=DNS:finance.yahoo.com,"
            "DNS:query1.finance.yahoo.com,"
            "DNS:query2.finance.yahoo.com",
        ],
        check=True,
        capture_output=True,
    )
    print("[yahoo-mock] Self-signed certificate generated.", file=sys.stderr, flush=True)


if __name__ == "__main__":
    generate_cert()

    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(CERT_FILE, KEY_FILE)

    server = HTTPServer(("0.0.0.0", 443), MockYahooHandler)
    server.socket = context.wrap_socket(server.socket, server_side=True)

    print("[yahoo-mock] Listening on :443 (HTTPS)", file=sys.stderr, flush=True)
    server.serve_forever()
