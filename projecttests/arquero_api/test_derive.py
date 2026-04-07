"""Tests for derive() — covers computed columns, op functions, multiple columns."""
from __future__ import annotations


NUMBERS = [
    {"a": 1, "b": 2},
    {"a": 3, "b": 4},
    {"a": 5, "b": 6},
]

WORDS = [
    {"first": "hello", "last": "world"},
    {"first": "foo",   "last": "bar"},
]


def test_derive_sum_column(aq):
    resp = aq.derive(NUMBERS, {"c": "d => d.a + d.b"})
    c_values = [r["c"] for r in resp["rows"]]
    assert c_values == [3, 7, 11]


def test_derive_product_column(aq):
    resp = aq.derive(NUMBERS, {"prod": "d => d.a * d.b"})
    assert resp["rows"][0]["prod"] == 2
    assert resp["rows"][1]["prod"] == 12


def test_derive_preserves_original_columns(aq):
    resp = aq.derive(NUMBERS, {"c": "d => d.a + d.b"})
    assert set(resp["columnNames"]) == {"a", "b", "c"}


def test_derive_multiple_columns(aq):
    resp = aq.derive(NUMBERS, {
        "sum": "d => d.a + d.b",
        "diff": "d => d.b - d.a",
    })
    assert resp["rows"][0]["sum"] == 3
    assert resp["rows"][0]["diff"] == 1


def test_derive_constant(aq):
    resp = aq.derive(NUMBERS, {"flag": "() => 1"})
    assert all(r["flag"] == 1 for r in resp["rows"])


def test_derive_string_concat(aq):
    resp = aq.derive(WORDS, {"full": "d => d.first + ' ' + d.last"})
    assert resp["rows"][0]["full"] == "hello world"


def test_derive_op_abs(aq):
    data = [{"x": -3}, {"x": 5}, {"x": -1}]
    resp = aq.derive(data, {"abs_x": "d => op.abs(d.x)"})
    assert [r["abs_x"] for r in resp["rows"]] == [3, 5, 1]


def test_derive_op_sqrt(aq):
    data = [{"x": 4}, {"x": 9}, {"x": 16}]
    resp = aq.derive(data, {"root": "d => op.sqrt(d.x)"})
    assert resp["rows"][0]["root"] == 2.0
    assert resp["rows"][1]["root"] == 3.0


def test_derive_op_pow(aq):
    data = [{"x": 2}, {"x": 3}]
    resp = aq.derive(data, {"squared": "d => op.pow(d.x, 2)"})
    assert [r["squared"] for r in resp["rows"]] == [4, 9]


def test_derive_overwrite_column(aq):
    resp = aq.derive(NUMBERS, {"a": "d => d.a * 10"})
    assert resp["rows"][0]["a"] == 10
    assert resp["rows"][1]["a"] == 30
