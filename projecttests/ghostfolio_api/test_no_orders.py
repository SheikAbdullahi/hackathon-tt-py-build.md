"""
Converted from:
  projects/ghostfolio/apps/api/src/app/portfolio/calculator/roai/
  portfolio-calculator-no-orders.spec.ts

Original: TS timer frozen at 2021-12-18, empty activities, currency CHF.
"""
import pytest


def test_no_orders_performance_is_empty(gf):
    """With no activities the portfolio has no chart data and zero performance."""
    client, _access_token = gf
    client.update_user_settings("CHF")

    perf = client.get_performance()

    assert perf["chart"] == []

    p = perf["performance"]
    assert p["currentValueInBaseCurrency"] == 0
    assert p["totalInvestment"] == 0
    assert p["netPerformance"] == 0


def test_no_orders_investments_are_empty(gf):
    """With no activities the investments list is empty."""
    client, _access_token = gf
    client.update_user_settings("CHF")

    inv = client.get_investments()
    assert inv["investments"] == []


def test_no_orders_investments_by_month_are_empty(gf):
    client, _access_token = gf
    client.update_user_settings("CHF")

    inv = client.get_investments(group_by="month")
    assert inv["investments"] == []


def test_no_orders_investments_by_year_are_empty(gf):
    client, _access_token = gf
    client.update_user_settings("CHF")

    inv = client.get_investments(group_by="year")
    assert inv["investments"] == []
