"""Tests for basic table creation — covers from(), fromCSV(), table shape."""
from __future__ import annotations


PEOPLE = [
    {"name": "Alice", "age": 30, "city": "Oslo"},
    {"name": "Bob",   "age": 25, "city": "Bergen"},
    {"name": "Charlie", "age": 35, "city": "Oslo"},
]


def test_health(aq):
    resp = aq.health()
    assert resp["status"] == "ok"


def test_from_json_row_count(aq):
    resp = aq.from_json(PEOPLE)
    assert resp["numRows"] == 3


def test_from_json_col_count(aq):
    resp = aq.from_json(PEOPLE)
    assert resp["numCols"] == 3


def test_from_json_column_names(aq):
    resp = aq.from_json(PEOPLE)
    assert set(resp["columnNames"]) == {"name", "age", "city"}


def test_from_json_rows_content(aq):
    resp = aq.from_json(PEOPLE)
    names = [r["name"] for r in resp["rows"]]
    assert sorted(names) == ["Alice", "Bob", "Charlie"]


def test_from_json_empty(aq):
    resp = aq.from_json([])
    assert resp["numRows"] == 0
    assert resp["numCols"] == 0


def test_from_json_single_row(aq):
    resp = aq.from_json([{"x": 1}])
    assert resp["numRows"] == 1
    assert resp["rows"][0]["x"] == 1


def test_from_csv_basic(aq):
    csv = "name,age\nAlice,30\nBob,25"
    resp = aq.from_csv(csv)
    assert resp["numRows"] == 2
    assert set(resp["columnNames"]) == {"name", "age"}


def test_from_csv_values(aq):
    csv = "a,b\n1,2\n3,4"
    resp = aq.from_csv(csv)
    rows = resp["rows"]
    assert rows[0]["a"] == 1
    assert rows[1]["b"] == 4


def test_from_csv_custom_delimiter(aq):
    csv = "a;b\n1;2\n3;4"
    resp = aq.from_csv(csv, options={"delimiter": ";"})
    assert resp["numRows"] == 2
    assert resp["rows"][0]["a"] == 1
