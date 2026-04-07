"""
Ghostfolio pytx — FastAPI entry point.

The scaffold provides HTTP endpoints that delegate portfolio calculations to
the translated calculator. See PORTFOLIO_CALCULATOR_INTERFACE.md for the
interface contract that the translated code must implement.
"""
from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse

app = FastAPI(title="Ghostfolio pytx")

# ---------------------------------------------------------------------------
# In-memory store
# ---------------------------------------------------------------------------

@dataclass
class UserState:
    access_token: str
    auth_token: str
    base_currency: str = "USD"
    activities: list[dict] = field(default_factory=list)
    market_data: dict[str, dict[str, list[dict]]] = field(default_factory=dict)


_lock = threading.Lock()
_users: dict[str, UserState] = {}
_access_to_auth: dict[str, str] = {}


def _make_tokens() -> tuple[str, str]:
    return str(uuid.uuid4()), str(uuid.uuid4())


def _get_user(authorization: str | None = Header(default=None)) -> UserState:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing token")
    token = authorization.removeprefix("Bearer ")
    with _lock:
        user = _users.get(token)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unknown token")
    return user


# Translated calculator delegation
# ---------------------------------------------------------------------------


def _try_calculator(user: UserState) -> dict | None:
    """Call translated calculator for all symbols; return {sym: metrics} or None."""
    try:
        from apps.api.src.app.portfolio.calculator.roai.portfolio_calculator import (
            RoaiPortfolioCalculator,
        )
        from app.models import PortfolioOrderItem, SymbolProfile
        from decimal import Decimal
        from datetime import date as D, timedelta

        calc = RoaiPortfolioCalculator()
        calc.activities = [
            PortfolioOrderItem(
                date=a["date"],
                fee=Decimal(str(a.get("fee") or 0)),
                quantity=Decimal(str(a.get("quantity") or 0)),
                symbol_profile=SymbolProfile(
                    symbol=a.get("symbol", ""),
                    data_source=a.get("dataSource", "YAHOO"),
                ),
                type=a.get("type", "BUY"),
                unit_price=Decimal(str(a.get("unitPrice") or 0)),
            )
            for a in user.activities
        ]

        mmap: dict[str, dict[str, Decimal]] = {}
        for p, sym in (
            (p, sym) for ds in user.market_data.values() for sym, ps in ds.items() for p in ps
        ):
            mmap.setdefault(p["date"], {})[sym] = Decimal(str(p["marketPrice"]))
        today = D.today().isoformat()
        mmap.setdefault(today, {})

        all_dates = sorted(mmap)
        chart_map = {d: True for d in all_dates}
        ex_rates = {d: 1.0 for d in all_dates}

        first = min(a["date"] for a in user.activities)
        start = D.fromisoformat(first) - timedelta(days=1)
        symbols = list({a.get("symbol") for a in user.activities if a.get("symbol")})

        results: dict[str, dict] = {}
        for sym in symbols:
            ds = next((a["dataSource"] for a in user.activities if a.get("symbol") == sym), "YAHOO")
            m = calc.get_symbol_metrics(
                chart_date_map=chart_map, data_source=ds, end=D.today(),
                exchange_rates=ex_rates, market_symbol_map=mmap,
                start=start, symbol=sym,
            )
            if m is not None:
                results[sym] = m if isinstance(m, dict) else vars(m)
        return results
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


@app.get("/api/v1/health")
def health() -> dict:
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# User lifecycle
# ---------------------------------------------------------------------------


@app.post("/api/v1/user")
def create_user() -> dict:
    access_token, auth_token = _make_tokens()
    user = UserState(access_token=access_token, auth_token=auth_token)
    with _lock:
        _users[auth_token] = user
        _access_to_auth[access_token] = auth_token
    return {"accessToken": access_token, "authToken": auth_token}


@app.put("/api/v1/user/setting")
def update_user_setting(body: dict[str, Any], user: UserState = Depends(_get_user)) -> dict:
    if "baseCurrency" in body:
        user.base_currency = body["baseCurrency"]
    return {"baseCurrency": user.base_currency}


@app.delete("/api/v1/user")
def delete_user(body: dict[str, Any], user: UserState = Depends(_get_user)) -> JSONResponse:
    with _lock:
        auth = _access_to_auth.pop(body.get("accessToken", ""), None)
        if auth:
            _users.pop(auth, None)
    return JSONResponse(status_code=status.HTTP_200_OK, content={})


# ---------------------------------------------------------------------------
# Activities import & market data seeding
# ---------------------------------------------------------------------------


@app.post("/api/v1/import")
async def import_activities(request: Request, user: UserState = Depends(_get_user)) -> dict:
    body = await request.json()
    activities = body.get("activities", [])
    user.activities.extend(activities)
    return {"activities": activities}


@app.post("/api/v1/market-data/{data_source}/{symbol}")
async def seed_market_data(
    data_source: str, symbol: str, request: Request, user: UserState = Depends(_get_user),
) -> dict:
    body = await request.json()
    user.market_data.setdefault(data_source, {})[symbol] = body.get("marketData", [])
    return {}


# ---------------------------------------------------------------------------
# Portfolio — performance (v2)
# ---------------------------------------------------------------------------

@app.get("/api/v2/portfolio/performance")
def get_performance(range: str = "max", user: UserState = Depends(_get_user)) -> dict:
    """Delegate to translated calculator, fall back to zeros."""
    calc = _try_calculator(user) if user.activities else None
    ti = sum(float(m.get("total_investment", 0)) for m in calc.values()) if calc else 0.0
    gp = sum(float(m.get("gross_performance", 0)) for m in calc.values()) if calc else 0.0
    fees = sum(float(m.get("fees_with_currency_effect", 0)) for m in calc.values()) if calc else 0.0
    net = gp - fees
    cv = sum(
        float(v) for m in calc.values() for v in (m.get("current_values") or {}).values()
    ) if calc else 0.0
    twi = sum(float(m.get("time_weighted_investment", 0)) for m in calc.values()) if calc else 0.0
    denom = twi if twi > 1e-10 else (ti if abs(ti) > 1e-10 else 1.0)
    pct = net / denom if abs(denom) > 1e-10 else 0.0
    return {
        "chart": [],
        "firstOrderDate": user.activities[0]["date"] if user.activities else None,
        "performance": {
            "currentNetWorth": cv,
            "currentValue": cv,
            "currentValueInBaseCurrency": cv,
            "netPerformance": net,
            "netPerformancePercentage": pct,
            "netPerformancePercentageWithCurrencyEffect": pct,
            "netPerformanceWithCurrencyEffect": net,
            "totalFees": fees,
            "totalInvestment": ti,
            "totalLiabilities": 0.0,
            "totalValueables": 0.0,
        },
    }


# ---------------------------------------------------------------------------
# Portfolio — investments (v1)
# ---------------------------------------------------------------------------

@app.get("/api/v1/portfolio/investments")
def get_investments(range: str = "max", groupBy: str | None = None, user: UserState = Depends(_get_user)) -> dict:
    """Stub: returns empty investments list."""
    return {"investments": []}


# ---------------------------------------------------------------------------
# Portfolio — holdings (v1)
# ---------------------------------------------------------------------------

@app.get("/api/v1/portfolio/holdings")
def get_holdings(range: str = "max", user: UserState = Depends(_get_user)) -> dict:
    """Stub: returns empty holdings dict."""
    return {"holdings": {}}
