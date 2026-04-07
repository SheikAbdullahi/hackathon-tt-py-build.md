"""Tests for select, rename, relocate, orderby, slice, dedupe, fold, pivot,
union, intersect, except, concat, spread, unroll, impute, assign, sample.
"""
from __future__ import annotations


PEOPLE = [
    {"name": "Alice",   "age": 30, "city": "Oslo"},
    {"name": "Bob",     "age": 25, "city": "Bergen"},
    {"name": "Charlie", "age": 35, "city": "Oslo"},
    {"name": "Diana",   "age": 25, "city": "Oslo"},
]


# ---------------------------------------------------------------------------
# select
# ---------------------------------------------------------------------------

def test_select_subset(aq):
    resp = aq.select(PEOPLE, ["name", "age"])
    assert resp["columnNames"] == ["name", "age"]
    assert resp["numCols"] == 2


def test_select_single_column(aq):
    resp = aq.select(PEOPLE, ["city"])
    assert resp["numCols"] == 1
    assert all("city" in r for r in resp["rows"])


# ---------------------------------------------------------------------------
# rename
# ---------------------------------------------------------------------------

def test_rename_column(aq):
    resp = aq.rename(PEOPLE, {"name": "full_name"})
    assert "full_name" in resp["columnNames"]
    assert "name" not in resp["columnNames"]


def test_rename_multiple(aq):
    resp = aq.rename(PEOPLE, {"name": "full_name", "age": "years"})
    assert "full_name" in resp["columnNames"]
    assert "years" in resp["columnNames"]


# ---------------------------------------------------------------------------
# relocate
# ---------------------------------------------------------------------------

def test_relocate_before(aq):
    resp = aq.relocate(PEOPLE, ["city"], options={"before": "name"})
    assert resp["columnNames"][0] == "city"


# ---------------------------------------------------------------------------
# orderby
# ---------------------------------------------------------------------------

def test_orderby_asc(aq):
    resp = aq.orderby(PEOPLE, ["age"])
    ages = [r["age"] for r in resp["rows"]]
    assert ages == sorted(ages)


def test_orderby_desc(aq):
    resp = aq.orderby(PEOPLE, ["desc('age')"])
    ages = [r["age"] for r in resp["rows"]]
    assert ages == sorted(ages, reverse=True)


def test_orderby_multiple_columns(aq):
    resp = aq.orderby(PEOPLE, ["age", "name"])
    # Both Bob and Diana are age 25; they should be sorted by name after
    rows = resp["rows"]
    age25 = [r for r in rows if r["age"] == 25]
    assert age25[0]["name"] == "Bob"
    assert age25[1]["name"] == "Diana"


# ---------------------------------------------------------------------------
# slice
# ---------------------------------------------------------------------------

def test_slice_first_two(aq):
    resp = aq.slice(PEOPLE, 0, 2)
    assert resp["numRows"] == 2


def test_slice_middle(aq):
    resp = aq.slice(PEOPLE, 1, 3)
    assert resp["numRows"] == 2


# ---------------------------------------------------------------------------
# dedupe
# ---------------------------------------------------------------------------

def test_dedupe_removes_duplicates(aq):
    data = [{"x": 1}, {"x": 1}, {"x": 2}]
    resp = aq.dedupe(data)
    assert resp["numRows"] == 2


def test_dedupe_by_column(aq):
    resp = aq.dedupe(PEOPLE, columns=["city"])
    # Oslo appears 3 times, Bergen once → 2 distinct cities
    assert resp["numRows"] == 2


def test_dedupe_no_duplicates(aq):
    resp = aq.dedupe(PEOPLE)
    assert resp["numRows"] == len(PEOPLE)


# ---------------------------------------------------------------------------
# fold
# ---------------------------------------------------------------------------

def test_fold_creates_key_value_rows(aq):
    data = [{"id": 1, "jan": 10, "feb": 20}]
    resp = aq.fold(data, ["jan", "feb"])
    assert resp["numRows"] == 2
    keys = {r["key"] for r in resp["rows"]}
    assert keys == {"jan", "feb"}


def test_fold_values_column(aq):
    data = [{"id": 1, "jan": 10, "feb": 20}]
    resp = aq.fold(data, ["jan", "feb"])
    vals = {r["key"]: r["value"] for r in resp["rows"]}
    assert vals == {"jan": 10, "feb": 20}


def test_fold_custom_key_value_names(aq):
    data = [{"id": 1, "x": 5, "y": 8}]
    resp = aq.fold(data, ["x", "y"], options={"as": ["col", "val"]})
    assert "col" in resp["columnNames"]
    assert "val" in resp["columnNames"]


# ---------------------------------------------------------------------------
# pivot
# ---------------------------------------------------------------------------

def test_pivot_wide(aq):
    data = [
        {"key": "a", "val": 1},
        {"key": "b", "val": 2},
    ]
    resp = aq.pivot(data, on=["key"], values=["val"])
    assert resp["numRows"] == 1
    assert "a" in resp["columnNames"]
    assert "b" in resp["columnNames"]


# ---------------------------------------------------------------------------
# union / intersect / except / concat
# ---------------------------------------------------------------------------

def test_union_deduplicates(aq):
    t1 = [{"x": 1}, {"x": 2}]
    t2 = [{"x": 2}, {"x": 3}]
    resp = aq.union([t1, t2])
    xs = {r["x"] for r in resp["rows"]}
    assert xs == {1, 2, 3}


def test_intersect(aq):
    t1 = [{"x": 1}, {"x": 2}, {"x": 3}]
    t2 = [{"x": 2}, {"x": 3}, {"x": 4}]
    resp = aq.intersect([t1, t2])
    xs = {r["x"] for r in resp["rows"]}
    assert xs == {2, 3}


def test_except(aq):
    t1 = [{"x": 1}, {"x": 2}, {"x": 3}]
    t2 = [{"x": 2}, {"x": 3}]
    resp = aq.except_([t1, t2])
    xs = {r["x"] for r in resp["rows"]}
    assert xs == {1}


def test_concat_keeps_duplicates(aq):
    t1 = [{"x": 1}, {"x": 2}]
    t2 = [{"x": 2}, {"x": 3}]
    resp = aq.concat([t1, t2])
    assert resp["numRows"] == 4


# ---------------------------------------------------------------------------
# spread
# ---------------------------------------------------------------------------

def test_spread_array_column(aq):
    data = [{"id": 1, "vals": [10, 20, 30]}]
    resp = aq.spread(data, ["vals"])
    assert resp["numRows"] == 1
    assert resp["numCols"] > 1  # val_1, val_2, val_3


def test_spread_limits(aq):
    data = [{"id": 1, "vals": [10, 20, 30, 40]}]
    resp = aq.spread(data, ["vals"], options={"limit": 2})
    col_names = resp["columnNames"]
    # Only 2 spread columns + id
    assert resp["numCols"] == 3


# ---------------------------------------------------------------------------
# unroll
# ---------------------------------------------------------------------------

def test_unroll_array_column(aq):
    data = [{"id": 1, "tags": ["a", "b", "c"]}, {"id": 2, "tags": ["x"]}]
    resp = aq.unroll(data, ["tags"])
    assert resp["numRows"] == 4  # 3 + 1


def test_unroll_preserves_other_columns(aq):
    data = [{"id": 1, "tags": ["a", "b"]}]
    resp = aq.unroll(data, ["tags"])
    assert "id" in resp["columnNames"]
    assert resp["rows"][0]["id"] == 1


# ---------------------------------------------------------------------------
# impute
# ---------------------------------------------------------------------------

def test_impute_fills_none(aq):
    data = [{"x": 1}, {"x": None}, {"x": 3}]
    resp = aq.impute(data, {"x": 0})
    vals = [r["x"] for r in resp["rows"]]
    assert vals == [1, 0, 3]


# ---------------------------------------------------------------------------
# assign
# ---------------------------------------------------------------------------

def test_assign_adds_column(aq):
    data  = [{"a": 1}, {"a": 2}]
    other = [{"b": 10}, {"b": 20}]
    resp = aq.assign(data, other)
    assert "a" in resp["columnNames"]
    assert "b" in resp["columnNames"]
    assert resp["rows"][0]["b"] == 10


# ---------------------------------------------------------------------------
# sample
# ---------------------------------------------------------------------------

def test_sample_count(aq):
    resp = aq.sample(PEOPLE, 2)
    assert resp["numRows"] == 2


def test_sample_preserves_columns(aq):
    resp = aq.sample(PEOPLE, 1)
    assert set(resp["columnNames"]) == {"name", "age", "city"}
