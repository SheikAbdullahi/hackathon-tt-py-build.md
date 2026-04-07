"""Thin HTTP client for the Arquero REST API."""
from __future__ import annotations

import requests


class ArqueroClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self._session = requests.Session()

    def _url(self, path: str) -> str:
        return f"{self.base_url}/{path.lstrip('/')}"

    def _post(self, path: str, **kwargs) -> dict:
        r = self._session.post(
            self._url(path),
            headers={"Content-Type": "application/json"},
            **kwargs,
        )
        r.raise_for_status()
        return r.json()

    def _get(self, path: str) -> dict:
        r = self._session.get(self._url(path))
        r.raise_for_status()
        return r.json()

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    def health(self) -> dict:
        return self._get("health")

    # ------------------------------------------------------------------
    # Table creation
    # ------------------------------------------------------------------

    def from_json(self, data: list[dict]) -> dict:
        return self._post("from-json", json={"data": data})

    def from_csv(self, csv: str, options: dict | None = None) -> dict:
        return self._post("from-csv", json={"csv": csv, "options": options})

    # ------------------------------------------------------------------
    # Column operations
    # ------------------------------------------------------------------

    def select(self, data: list[dict], columns: list[str]) -> dict:
        return self._post("select", json={"data": data, "columns": columns})

    def rename(self, data: list[dict], columns: dict[str, str]) -> dict:
        return self._post("rename", json={"data": data, "columns": columns})

    def relocate(self, data: list[dict], columns: list[str], options: dict | None = None) -> dict:
        return self._post("relocate", json={"data": data, "columns": columns, "options": options})

    def derive(self, data: list[dict], columns: dict[str, str]) -> dict:
        """columns: { name: "d => expr" } — expressions as JS arrow function strings."""
        return self._post("derive", json={"data": data, "columns": columns})

    def assign(self, data: list[dict], other: list[dict]) -> dict:
        return self._post("assign", json={"data": data, "other": other})

    # ------------------------------------------------------------------
    # Row operations
    # ------------------------------------------------------------------

    def filter(self, data: list[dict], expr: str) -> dict:
        """expr: JS arrow function string e.g. 'd => d.age > 25'"""
        return self._post("filter", json={"data": data, "expr": expr})

    def orderby(self, data: list[dict], exprs: list[str]) -> dict:
        """exprs: column names or JS expr strings e.g. ["desc('age')"]"""
        return self._post("orderby", json={"data": data, "exprs": exprs})

    def slice(self, data: list[dict], start: int, end: int | None = None) -> dict:
        return self._post("slice", json={"data": data, "start": start, "end": end})

    def sample(self, data: list[dict], n: int, options: dict | None = None) -> dict:
        return self._post("sample", json={"data": data, "n": n, "options": options})

    def dedupe(self, data: list[dict], columns: list[str] | None = None) -> dict:
        return self._post("dedupe", json={"data": data, "columns": columns})

    def impute(self, data: list[dict], values: dict) -> dict:
        return self._post("impute", json={"data": data, "values": values})

    # ------------------------------------------------------------------
    # Aggregation
    # ------------------------------------------------------------------

    def rollup(self, data: list[dict], rollup: dict[str, str]) -> dict:
        """rollup: { name: "d => op.sum(d.col)" }"""
        return self._post("rollup", json={"data": data, "rollup": rollup})

    def groupby_rollup(self, data: list[dict], by: list[str], rollup: dict[str, str]) -> dict:
        return self._post("groupby-rollup", json={"data": data, "by": by, "rollup": rollup})

    # ------------------------------------------------------------------
    # Reshaping
    # ------------------------------------------------------------------

    def fold(self, data: list[dict], columns: list[str], options: dict | None = None) -> dict:
        return self._post("fold", json={"data": data, "columns": columns, "options": options})

    def pivot(self, data: list[dict], on: list[str], values: list[str], options: dict | None = None) -> dict:
        return self._post("pivot", json={"data": data, "on": on, "values": values, "options": options})

    def spread(self, data: list[dict], columns: list[str], options: dict | None = None) -> dict:
        return self._post("spread", json={"data": data, "columns": columns, "options": options})

    def unroll(self, data: list[dict], columns: list[str], options: dict | None = None) -> dict:
        return self._post("unroll", json={"data": data, "columns": columns, "options": options})

    # ------------------------------------------------------------------
    # Joins
    # ------------------------------------------------------------------

    def join(self, left: list[dict], right: list[dict], on: str | list, how: str = "inner") -> dict:
        return self._post("join", json={"left": left, "right": right, "on": on, "how": how})

    def semijoin(self, left: list[dict], right: list[dict], on: str | list) -> dict:
        return self._post("semijoin", json={"left": left, "right": right, "on": on})

    def antijoin(self, left: list[dict], right: list[dict], on: str | list) -> dict:
        return self._post("antijoin", json={"left": left, "right": right, "on": on})

    def cross(self, left: list[dict], right: list[dict]) -> dict:
        return self._post("cross", json={"left": left, "right": right})

    # ------------------------------------------------------------------
    # Set operations
    # ------------------------------------------------------------------

    def union(self, tables: list[list[dict]]) -> dict:
        return self._post("union", json={"tables": tables})

    def intersect(self, tables: list[list[dict]]) -> dict:
        return self._post("intersect", json={"tables": tables})

    def except_(self, tables: list[list[dict]]) -> dict:
        return self._post("except", json={"tables": tables})

    def concat(self, tables: list[list[dict]]) -> dict:
        return self._post("concat", json={"tables": tables})

    # ------------------------------------------------------------------
    # Format output
    # ------------------------------------------------------------------

    def to_csv(self, data: list[dict], options: dict | None = None) -> str:
        return self._post("to-csv", json={"data": data, "options": options})["csv"]

    def to_markdown(self, data: list[dict]) -> str:
        return self._post("to-markdown", json={"data": data})["markdown"]

    def to_json(self, data: list[dict], options: dict | None = None) -> str:
        return self._post("to-json", json={"data": data, "options": options})["json"]
