"""
Arquero API skeleton — Python translation target.

All endpoints return structurally correct responses so that the integration
test suite can run without crashing.  Operations that require expression
evaluation (derive, filter, rollup) are stubbed out; purely structural
operations (select, rename, slice, set-ops, etc.) are implemented with
plain Python.

State: stateless — each request is self-contained.
"""
from __future__ import annotations

import csv as csv_module
import io
import json
import random
from typing import Any

from fastapi import FastAPI

app = FastAPI(title="Arquero pytx skeleton")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _shape(rows: list[dict]) -> dict:
    col_names = list(rows[0].keys()) if rows else []
    return {
        "rows": rows,
        "numRows": len(rows),
        "numCols": len(col_names),
        "columnNames": col_names,
    }


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Table creation
# ---------------------------------------------------------------------------

@app.post("/from-json")
def from_json(body: dict[str, Any]) -> dict:
    rows = list(body.get("data") or [])
    return _shape(rows)


@app.post("/from-csv")
def from_csv_endpoint(body: dict[str, Any]) -> dict:
    csv_str = body.get("csv", "")
    options = body.get("options") or {}
    delimiter = options.get("delimiter", ",")
    reader = csv_module.DictReader(io.StringIO(csv_str), delimiter=delimiter)
    rows: list[dict] = []
    for row in reader:
        parsed: dict = {}
        for k, v in row.items():
            if v is None or v == "":
                parsed[k] = None
            else:
                try:
                    parsed[k] = int(v)
                except ValueError:
                    try:
                        parsed[k] = float(v)
                    except ValueError:
                        parsed[k] = v
        rows.append(parsed)
    return _shape(rows)


# ---------------------------------------------------------------------------
# Column operations
# ---------------------------------------------------------------------------

@app.post("/select")
def select(body: dict[str, Any]) -> dict:
    rows = list(body.get("data") or [])
    cols = list(body.get("columns") or [])
    result = [{c: r[c] for c in cols if c in r} for r in rows]
    col_names = cols
    return {"rows": result, "numRows": len(result), "numCols": len(col_names), "columnNames": col_names}


@app.post("/rename")
def rename(body: dict[str, Any]) -> dict:
    rows = list(body.get("data") or [])
    mapping: dict[str, str] = body.get("columns") or {}
    result = [{mapping.get(k, k): v for k, v in r.items()} for r in rows]
    return _shape(result)


@app.post("/relocate")
def relocate(body: dict[str, Any]) -> dict:
    rows = list(body.get("data") or [])
    cols: list[str] = body.get("columns") or []
    options: dict = body.get("options") or {}
    if not rows:
        return _shape(rows)
    all_cols = list(rows[0].keys())
    remaining = [c for c in all_cols if c not in cols]
    if "before" in options:
        idx = remaining.index(options["before"]) if options["before"] in remaining else 0
        order = remaining[:idx] + cols + remaining[idx:]
    elif "after" in options:
        idx = remaining.index(options["after"]) + 1 if options["after"] in remaining else len(remaining)
        order = remaining[:idx] + cols + remaining[idx:]
    else:
        order = cols + remaining
    result = [{c: r[c] for c in order if c in r} for r in rows]
    return {"rows": result, "numRows": len(result), "numCols": len(order), "columnNames": order}


@app.post("/derive")
def derive(body: dict[str, Any]) -> dict:
    """Stub — returns original rows without computing new columns."""
    return _shape(list(body.get("data") or []))


@app.post("/assign")
def assign(body: dict[str, Any]) -> dict:
    left = list(body.get("data") or [])
    other = list(body.get("other") or [])
    result = [{**left[i], **other[i]} for i in range(min(len(left), len(other)))]
    return _shape(result)


# ---------------------------------------------------------------------------
# Row operations
# ---------------------------------------------------------------------------

@app.post("/filter")
def filter_rows(body: dict[str, Any]) -> dict:
    """Stub — returns all rows unfiltered."""
    return _shape(list(body.get("data") or []))


@app.post("/orderby")
def orderby(body: dict[str, Any]) -> dict:
    rows = list(body.get("data") or [])
    exprs: list[str] = body.get("exprs") or []
    for expr in reversed(exprs):
        expr = expr.strip()
        if expr.startswith("desc("):
            # Extract column name from desc('col')
            col = expr[5:].rstrip(")").strip("'\"")
            rows = sorted(rows, key=lambda r: (r.get(col) is None, r.get(col)), reverse=True)
        elif expr.startswith("asc("):
            col = expr[4:].rstrip(")").strip("'\"")
            rows = sorted(rows, key=lambda r: (r.get(col) is None, r.get(col)))
        elif "=>" not in expr:
            rows = sorted(rows, key=lambda r, c=expr: (r.get(c) is None, r.get(c)))
    return _shape(rows)


@app.post("/slice")
def slice_rows(body: dict[str, Any]) -> dict:
    rows = list(body.get("data") or [])
    start = body.get("start") or 0
    end = body.get("end")
    return _shape(rows[start:end])


@app.post("/sample")
def sample(body: dict[str, Any]) -> dict:
    rows = list(body.get("data") or [])
    n = body.get("n") or 1
    return _shape(random.sample(rows, min(n, len(rows))))


@app.post("/dedupe")
def dedupe(body: dict[str, Any]) -> dict:
    rows = list(body.get("data") or [])
    columns: list[str] | None = body.get("columns")
    seen: set = set()
    result = []
    for r in rows:
        key = tuple(r.get(c) for c in columns) if columns else tuple(sorted(r.items()))
        if key not in seen:
            seen.add(key)
            result.append(r)
    return _shape(result)


@app.post("/impute")
def impute(body: dict[str, Any]) -> dict:
    rows = list(body.get("data") or [])
    values: dict = body.get("values") or {}
    result = [{k: (values[k] if v is None and k in values else v) for k, v in r.items()} for r in rows]
    return _shape(result)


# ---------------------------------------------------------------------------
# Aggregation — stubs
# ---------------------------------------------------------------------------

@app.post("/rollup")
def rollup(body: dict[str, Any]) -> dict:
    """Stub — returns one row with None for each aggregation column."""
    rollup_def: dict = body.get("rollup") or {}
    return _shape([{k: None for k in rollup_def}])


@app.post("/groupby-rollup")
def groupby_rollup(body: dict[str, Any]) -> dict:
    """Stub — returns one row per group with None aggregation values."""
    rows = list(body.get("data") or [])
    by: list[str] = body.get("by") or []
    rollup_def: dict = body.get("rollup") or {}
    seen: list[tuple] = []
    result = []
    for r in rows:
        key = tuple(r.get(c) for c in by)
        if key not in seen:
            seen.append(key)
            result.append({**dict(zip(by, key)), **{k: None for k in rollup_def}})
    return _shape(result)


# ---------------------------------------------------------------------------
# Reshaping — stubs
# ---------------------------------------------------------------------------

@app.post("/fold")
def fold(body: dict[str, Any]) -> dict:
    """Stub — returns an empty result with key/value columns."""
    options: dict = body.get("options") or {}
    key_col, val_col = (options.get("as") or ["key", "value"])[:2]
    data = list(body.get("data") or [])
    cols: list[str] = body.get("columns") or []
    id_cols = [c for c in (list(data[0].keys()) if data else []) if c not in cols]
    rows = []
    for r in data:
        for c in cols:
            rows.append({**{ic: r[ic] for ic in id_cols}, key_col: c, val_col: r.get(c)})
    return _shape(rows)


@app.post("/pivot")
def pivot(body: dict[str, Any]) -> dict:
    """Stub — returns a single wide row with None values."""
    data = list(body.get("data") or [])
    on: list[str] = body.get("on") or []
    if not data or not on:
        return _shape([])
    key_col = on[0]
    keys = list(dict.fromkeys(str(r.get(key_col)) for r in data))
    return _shape([{k: None for k in keys}])


@app.post("/spread")
def spread(body: dict[str, Any]) -> dict:
    """Stub — returns data unchanged."""
    return _shape(list(body.get("data") or []))


@app.post("/unroll")
def unroll(body: dict[str, Any]) -> dict:
    rows = list(body.get("data") or [])
    columns: list[str] = body.get("columns") or []
    result = []
    for r in rows:
        col = columns[0] if columns else None
        if col and isinstance(r.get(col), list):
            for v in r[col]:
                result.append({**r, col: v})
        else:
            result.append(r)
    return _shape(result)


# ---------------------------------------------------------------------------
# Joins
# ---------------------------------------------------------------------------

@app.post("/join")
def join(body: dict[str, Any]) -> dict:
    left = list(body.get("left") or [])
    right = list(body.get("right") or [])
    on = body.get("on")
    how = body.get("how", "inner")
    left_col, right_col = (on[0], on[1]) if isinstance(on, list) and len(on) == 2 else (on, on)
    right_index: dict[Any, list[dict]] = {}
    for r in right:
        k = r.get(right_col)
        right_index.setdefault(k, []).append(r)
    result = []
    matched_right: set[int] = set()
    for l in left:
        k = l.get(left_col)
        matches = right_index.get(k, [])
        if matches:
            for r in matches:
                matched_right.add(id(r))
                merged = {**l}
                for rk, rv in r.items():
                    if rk != right_col:
                        merged[rk] = rv
                result.append(merged)
        elif how in ("left", "full"):
            result.append(dict(l))
    if how in ("right", "full"):
        for r in right:
            if id(r) not in matched_right:
                result.append(dict(r))
    return _shape(result)


@app.post("/semijoin")
def semijoin(body: dict[str, Any]) -> dict:
    left = list(body.get("left") or [])
    right = list(body.get("right") or [])
    on = body.get("on")
    left_col, right_col = (on[0], on[1]) if isinstance(on, list) and len(on) == 2 else (on, on)
    right_keys = {r.get(right_col) for r in right}
    return _shape([r for r in left if r.get(left_col) in right_keys])


@app.post("/antijoin")
def antijoin(body: dict[str, Any]) -> dict:
    left = list(body.get("left") or [])
    right = list(body.get("right") or [])
    on = body.get("on")
    left_col, right_col = (on[0], on[1]) if isinstance(on, list) and len(on) == 2 else (on, on)
    right_keys = {r.get(right_col) for r in right}
    return _shape([r for r in left if r.get(left_col) not in right_keys])


@app.post("/cross")
def cross(body: dict[str, Any]) -> dict:
    left = list(body.get("left") or [])
    right = list(body.get("right") or [])
    return _shape([{**l, **r} for l in left for r in right])


# ---------------------------------------------------------------------------
# Set operations
# ---------------------------------------------------------------------------

def _dedup(rows: list[dict]) -> list[dict]:
    seen: set = set()
    result = []
    for r in rows:
        k = tuple(sorted(r.items()))
        if k not in seen:
            seen.add(k)
            result.append(r)
    return result


@app.post("/union")
def union(body: dict[str, Any]) -> dict:
    tables: list[list[dict]] = body.get("tables") or []
    combined = [r for t in tables for r in t]
    return _shape(_dedup(combined))


@app.post("/intersect")
def intersect(body: dict[str, Any]) -> dict:
    tables: list[list[dict]] = body.get("tables") or []
    if not tables:
        return _shape([])
    sets = [set(tuple(sorted(r.items())) for r in t) for t in tables]
    common = sets[0]
    for s in sets[1:]:
        common &= s
    result = [dict(k) for k in common]
    return _shape(result)


@app.post("/except")
def except_op(body: dict[str, Any]) -> dict:
    tables: list[list[dict]] = body.get("tables") or []
    if not tables:
        return _shape([])
    exclude: set = set()
    for t in tables[1:]:
        for r in t:
            exclude.add(tuple(sorted(r.items())))
    result = [r for r in tables[0] if tuple(sorted(r.items())) not in exclude]
    return _shape(result)


@app.post("/concat")
def concat(body: dict[str, Any]) -> dict:
    tables: list[list[dict]] = body.get("tables") or []
    return _shape([r for t in tables for r in t])


# ---------------------------------------------------------------------------
# Format output
# ---------------------------------------------------------------------------

@app.post("/to-csv")
def to_csv(body: dict[str, Any]) -> dict:
    rows = list(body.get("data") or [])
    options: dict = body.get("options") or {}
    delimiter = options.get("delimiter", ",")
    if not rows:
        return {"csv": ""}
    buf = io.StringIO()
    writer = csv_module.DictWriter(buf, fieldnames=list(rows[0].keys()), delimiter=delimiter)
    writer.writeheader()
    writer.writerows(rows)
    return {"csv": buf.getvalue()}


@app.post("/to-markdown")
def to_markdown(body: dict[str, Any]) -> dict:
    rows = list(body.get("data") or [])
    if not rows:
        return {"markdown": ""}
    cols = list(rows[0].keys())
    header = "| " + " | ".join(cols) + " |"
    sep = "| " + " | ".join("---" for _ in cols) + " |"
    lines = [header, sep]
    for r in rows:
        lines.append("| " + " | ".join(str(r.get(c, "")) for c in cols) + " |")
    return {"markdown": "\n".join(lines)}


@app.post("/to-json")
def to_json_endpoint(body: dict[str, Any]) -> dict:
    rows = list(body.get("data") or [])
    return {"json": json.dumps(rows)}
