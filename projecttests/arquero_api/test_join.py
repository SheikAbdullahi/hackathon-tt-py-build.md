"""Tests for join(), semijoin(), antijoin(), cross() — covers all join types."""
from __future__ import annotations


EMPLOYEES = [
    {"id": 1, "name": "Alice",   "dept_id": 10},
    {"id": 2, "name": "Bob",     "dept_id": 20},
    {"id": 3, "name": "Charlie", "dept_id": 10},
    {"id": 4, "name": "Diana",   "dept_id": 30},  # dept 30 has no match
]

DEPARTMENTS = [
    {"dept_id": 10, "dept_name": "Engineering"},
    {"dept_id": 20, "dept_name": "Marketing"},
    # dept 30 is missing intentionally
]


def test_inner_join_row_count(aq):
    resp = aq.join(EMPLOYEES, DEPARTMENTS, on="dept_id", how="inner")
    assert resp["numRows"] == 3  # Diana (dept 30) excluded


def test_inner_join_column_names(aq):
    resp = aq.join(EMPLOYEES, DEPARTMENTS, on="dept_id", how="inner")
    assert "name" in resp["columnNames"]
    assert "dept_name" in resp["columnNames"]


def test_inner_join_values(aq):
    resp = aq.join(EMPLOYEES, DEPARTMENTS, on="dept_id", how="inner")
    alice = next(r for r in resp["rows"] if r["name"] == "Alice")
    assert alice["dept_name"] == "Engineering"


def test_left_join_row_count(aq):
    resp = aq.join(EMPLOYEES, DEPARTMENTS, on="dept_id", how="left")
    assert resp["numRows"] == 4  # Diana kept with null dept_name


def test_left_join_null_for_missing(aq):
    resp = aq.join(EMPLOYEES, DEPARTMENTS, on="dept_id", how="left")
    diana = next(r for r in resp["rows"] if r["name"] == "Diana")
    assert diana.get("dept_name") is None


def test_full_join_row_count(aq):
    resp = aq.join(EMPLOYEES, DEPARTMENTS, on="dept_id", how="full")
    # All employees + any unmatched departments — at least 4 rows
    assert resp["numRows"] >= 4


def test_semijoin_keeps_only_matches(aq):
    resp = aq.semijoin(EMPLOYEES, DEPARTMENTS, on="dept_id")
    names = {r["name"] for r in resp["rows"]}
    assert names == {"Alice", "Bob", "Charlie"}
    # semijoin returns only left-table columns
    assert "dept_name" not in resp["columnNames"]


def test_antijoin_keeps_only_non_matches(aq):
    resp = aq.antijoin(EMPLOYEES, DEPARTMENTS, on="dept_id")
    names = {r["name"] for r in resp["rows"]}
    assert names == {"Diana"}


def test_cross_row_count(aq):
    left = [{"x": 1}, {"x": 2}]
    right = [{"y": "a"}, {"y": "b"}, {"y": "c"}]
    resp = aq.cross(left, right)
    assert resp["numRows"] == 6  # 2 × 3


def test_cross_column_names(aq):
    left = [{"x": 1}]
    right = [{"y": 2}]
    resp = aq.cross(left, right)
    assert "x" in resp["columnNames"]
    assert "y" in resp["columnNames"]


def test_join_on_different_key_names(aq):
    # arquero on=["leftCol","rightCol"] joins where left.leftCol == right.rightCol
    left  = [{"emp_id": 1, "name": "Alice"}, {"emp_id": 2, "name": "Bob"}]
    right = [{"dept_emp_id": 1, "dept": "Engineering"}]
    resp = aq.join(left, right, on=["emp_id", "dept_emp_id"], how="inner")
    assert resp["numRows"] == 1
    assert resp["rows"][0]["name"] == "Alice"
