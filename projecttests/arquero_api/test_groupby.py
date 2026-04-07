"""Tests for rollup() and groupby().rollup() — covers aggregate op functions."""
from __future__ import annotations


SALES = [
    {"cat": "A", "val": 10, "qty": 2},
    {"cat": "A", "val": 20, "qty": 3},
    {"cat": "B", "val": 5,  "qty": 1},
    {"cat": "B", "val": 15, "qty": 4},
    {"cat": "C", "val": 30, "qty": 1},
]

SCORES = [
    {"group": "X", "score": 80},
    {"group": "X", "score": 90},
    {"group": "X", "score": 70},
    {"group": "Y", "score": 60},
    {"group": "Y", "score": 100},
]


def test_rollup_count(aq):
    resp = aq.rollup(SALES, {"n": "d => op.count()"})
    assert resp["rows"][0]["n"] == 5


def test_rollup_sum(aq):
    resp = aq.rollup(SALES, {"total": "d => op.sum(d.val)"})
    assert resp["rows"][0]["total"] == 80


def test_rollup_mean(aq):
    resp = aq.rollup(SALES, {"avg": "d => op.mean(d.val)"})
    assert resp["rows"][0]["avg"] == 16.0


def test_rollup_min_max(aq):
    resp = aq.rollup(SALES, {
        "lo": "d => op.min(d.val)",
        "hi": "d => op.max(d.val)",
    })
    assert resp["rows"][0]["lo"] == 5
    assert resp["rows"][0]["hi"] == 30


def test_rollup_median(aq):
    resp = aq.rollup(SALES, {"med": "d => op.median(d.val)"})
    assert resp["rows"][0]["med"] == 15


def test_rollup_stdev(aq):
    resp = aq.rollup(SCORES, {"sd": "d => op.stdev(d.score)"})
    sd = resp["rows"][0]["sd"]
    assert sd is not None and sd > 0


def test_groupby_rollup_count(aq):
    resp = aq.groupby_rollup(SALES, ["cat"], {"n": "d => op.count()"})
    by_cat = {r["cat"]: r["n"] for r in resp["rows"]}
    assert by_cat == {"A": 2, "B": 2, "C": 1}


def test_groupby_rollup_sum(aq):
    resp = aq.groupby_rollup(SALES, ["cat"], {"total": "d => op.sum(d.val)"})
    by_cat = {r["cat"]: r["total"] for r in resp["rows"]}
    assert by_cat == {"A": 30, "B": 20, "C": 30}


def test_groupby_rollup_mean(aq):
    resp = aq.groupby_rollup(SALES, ["cat"], {"avg": "d => op.mean(d.val)"})
    by_cat = {r["cat"]: r["avg"] for r in resp["rows"]}
    assert by_cat["A"] == 15.0
    assert by_cat["B"] == 10.0


def test_groupby_rollup_multiple_aggs(aq):
    resp = aq.groupby_rollup(SALES, ["cat"], {
        "total_val": "d => op.sum(d.val)",
        "total_qty": "d => op.sum(d.qty)",
    })
    row_a = next(r for r in resp["rows"] if r["cat"] == "A")
    assert row_a["total_val"] == 30
    assert row_a["total_qty"] == 5


def test_groupby_rollup_multiple_keys(aq):
    data = [
        {"region": "EU", "cat": "A", "val": 10},
        {"region": "EU", "cat": "A", "val": 20},
        {"region": "US", "cat": "A", "val": 5},
    ]
    resp = aq.groupby_rollup(data, ["region", "cat"], {"total": "d => op.sum(d.val)"})
    assert resp["numRows"] == 2


def test_groupby_rollup_preserves_group_columns(aq):
    resp = aq.groupby_rollup(SCORES, ["group"], {"avg": "d => op.mean(d.score)"})
    assert "group" in resp["columnNames"]
    assert "avg" in resp["columnNames"]
