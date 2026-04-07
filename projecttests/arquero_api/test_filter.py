"""Tests for filter() — covers predicate evaluation, compound conditions."""
from __future__ import annotations


PEOPLE = [
    {"name": "Alice",   "age": 30, "score": 85.0},
    {"name": "Bob",     "age": 25, "score": 92.5},
    {"name": "Charlie", "age": 35, "score": 78.0},
    {"name": "Diana",   "age": 28, "score": 92.5},
]


def test_filter_greater_than(aq):
    resp = aq.filter(PEOPLE, "d => d.age > 28")
    names = {r["name"] for r in resp["rows"]}
    assert names == {"Alice", "Charlie"}


def test_filter_less_than(aq):
    resp = aq.filter(PEOPLE, "d => d.age < 30")
    names = {r["name"] for r in resp["rows"]}
    assert names == {"Bob", "Diana"}


def test_filter_equals(aq):
    resp = aq.filter(PEOPLE, "d => d.name === 'Alice'")
    assert resp["numRows"] == 1
    assert resp["rows"][0]["name"] == "Alice"


def test_filter_compound_and(aq):
    resp = aq.filter(PEOPLE, "d => d.age > 25 && d.score > 90")
    # Only Bob (age 25 excluded) and Diana (age 28, score 92.5) qualify
    names = {r["name"] for r in resp["rows"]}
    assert names == {"Diana"}


def test_filter_compound_or(aq):
    resp = aq.filter(PEOPLE, "d => d.age < 26 || d.age > 33")
    names = {r["name"] for r in resp["rows"]}
    assert names == {"Bob", "Charlie"}


def test_filter_no_match(aq):
    resp = aq.filter(PEOPLE, "d => d.age > 100")
    assert resp["numRows"] == 0
    assert resp["rows"] == []


def test_filter_all_match(aq):
    resp = aq.filter(PEOPLE, "d => d.age > 0")
    assert resp["numRows"] == len(PEOPLE)


def test_filter_float_comparison(aq):
    resp = aq.filter(PEOPLE, "d => d.score === 92.5")
    names = {r["name"] for r in resp["rows"]}
    assert names == {"Bob", "Diana"}


def test_filter_preserves_columns(aq):
    resp = aq.filter(PEOPLE, "d => d.age === 30")
    assert set(resp["columnNames"]) == {"name", "age", "score"}
