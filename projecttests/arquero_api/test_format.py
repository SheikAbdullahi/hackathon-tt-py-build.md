"""Tests for format output (to-csv, to-markdown, to-json) and from-csv round-trip."""
from __future__ import annotations


DATA = [
    {"name": "Alice", "age": 30},
    {"name": "Bob",   "age": 25},
]


def test_to_csv_contains_header(aq):
    csv = aq.to_csv(DATA)
    assert "name" in csv
    assert "age" in csv


def test_to_csv_contains_values(aq):
    csv = aq.to_csv(DATA)
    assert "Alice" in csv
    assert "30" in csv


def test_to_csv_default_delimiter(aq):
    csv = aq.to_csv(DATA)
    first_line = csv.strip().splitlines()[0]
    assert "," in first_line


def test_to_csv_custom_delimiter(aq):
    csv = aq.to_csv(DATA, options={"delimiter": "\t"})
    first_line = csv.strip().splitlines()[0]
    assert "\t" in first_line


def test_to_csv_row_count(aq):
    csv = aq.to_csv(DATA)
    lines = [l for l in csv.strip().splitlines() if l]
    assert len(lines) == 3  # header + 2 data rows


def test_roundtrip_csv(aq):
    original = [{"x": 1, "y": 2}, {"x": 3, "y": 4}]
    csv = aq.to_csv(original)
    resp = aq.from_csv(csv)
    assert resp["numRows"] == 2
    assert set(resp["columnNames"]) == {"x", "y"}
    xs = {r["x"] for r in resp["rows"]}
    assert xs == {1, 3}


def test_to_markdown_contains_header(aq):
    md = aq.to_markdown(DATA)
    assert "name" in md
    assert "age" in md


def test_to_markdown_table_format(aq):
    md = aq.to_markdown(DATA)
    assert "|" in md  # Markdown table uses pipes


def test_to_markdown_contains_values(aq):
    md = aq.to_markdown(DATA)
    assert "Alice" in md
    assert "25" in md


def test_to_json_is_string(aq):
    result = aq.to_json(DATA)
    assert isinstance(result, str)


def test_to_json_parseable(aq):
    import json
    result = aq.to_json(DATA)
    parsed = json.loads(result)
    assert parsed is not None


def test_from_csv_roundtrip_with_nulls(aq):
    csv = "a,b\n1,\n3,4"
    resp = aq.from_csv(csv)
    assert resp["numRows"] == 2
    # first row b should be empty/null
    row0 = resp["rows"][0]
    assert row0["a"] == 1
