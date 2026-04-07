"""Thin HTTP client for the Ghostfolio REST API."""
from __future__ import annotations

import requests


class GhostfolioClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self._session = requests.Session()
        self._auth_token: str | None = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _url(self, path: str) -> str:
        return f"{self.base_url}/api/v1/{path}"

    def _url_v2(self, path: str) -> str:
        return f"{self.base_url}/api/v2/{path}"

    def _headers(self) -> dict:
        h = {"Content-Type": "application/json"}
        if self._auth_token:
            h["Authorization"] = f"Bearer {self._auth_token}"
        return h

    def _get(self, url: str, **kwargs) -> dict:
        r = self._session.get(url, headers=self._headers(), **kwargs)
        r.raise_for_status()
        return r.json()

    def _post(self, url: str, **kwargs) -> dict:
        r = self._session.post(url, headers=self._headers(), **kwargs)
        r.raise_for_status()
        return r.json()

    def _put(self, url: str, **kwargs) -> dict:
        r = self._session.put(url, headers=self._headers(), **kwargs)
        r.raise_for_status()
        return r.json()

    def _delete(self, url: str, **kwargs):
        r = self._session.delete(url, headers=self._headers(), **kwargs)
        r.raise_for_status()

    # ------------------------------------------------------------------
    # Auth / user lifecycle
    # ------------------------------------------------------------------

    def create_user(self) -> tuple[str, str]:
        """POST /api/v1/user — returns (access_token, auth_token)."""
        data = self._post(self._url("user"))
        return data["accessToken"], data["authToken"]

    def set_auth(self, auth_token: str) -> None:
        self._auth_token = auth_token

    def update_user_settings(self, base_currency: str) -> dict:
        """PUT /api/v1/user/setting — set base currency."""
        return self._put(
            self._url("user/setting"),
            json={"baseCurrency": base_currency},
        )

    def delete_own_user(self, access_token: str) -> None:
        """DELETE /api/v1/user — deletes the authenticated user."""
        self._delete(self._url("user"), json={"accessToken": access_token})

    # ------------------------------------------------------------------
    # Activities / import
    # ------------------------------------------------------------------

    def import_activities(self, activities: list[dict], dry_run: bool = False) -> dict:
        """POST /api/v1/import — import a list of activities."""
        return self._post(
            self._url("import"),
            json={"activities": activities},
            params={"dryRun": "true" if dry_run else "false"},
        )

    # ------------------------------------------------------------------
    # Market data seeding (admin)
    # ------------------------------------------------------------------

    def seed_market_data(
        self, data_source: str, symbol: str, prices: list[dict]
    ) -> dict:
        """POST /api/v1/market-data/{dataSource}/{symbol}

        prices: [{"date": "YYYY-MM-DD", "marketPrice": float}, ...]
        Requires admin or own-asset-profile permissions.
        """
        return self._post(
            self._url(f"market-data/{data_source}/{symbol}"),
            json={"marketData": prices},
        )

    # ------------------------------------------------------------------
    # Portfolio endpoints
    # ------------------------------------------------------------------

    def get_performance(self, date_range: str = "max") -> dict:
        """GET /api/v2/portfolio/performance"""
        return self._get(
            self._url_v2("portfolio/performance"),
            params={"range": date_range},
        )

    def get_investments(
        self, group_by: str | None = None, date_range: str = "max"
    ) -> dict:
        """GET /api/v1/portfolio/investments"""
        params: dict = {"range": date_range}
        if group_by:
            params["groupBy"] = group_by
        return self._get(self._url("portfolio/investments"), params=params)

    def get_holdings(self, date_range: str = "max") -> dict:
        """GET /api/v1/portfolio/holdings"""
        return self._get(
            self._url("portfolio/holdings"),
            params={"range": date_range},
        )

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------

    def chart_by_date(self, chart: list[dict]) -> dict[str, dict]:
        """Index a chart array by date string for easy lookup."""
        return {entry["date"]: entry for entry in chart}
